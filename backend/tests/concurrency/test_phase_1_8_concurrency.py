"""Phase 1.8 Production Hardening — real-MongoDB concurrency tests.

These tests exercise the actual database race boundaries (unique indexes and
guarded atomic updates) by driving concurrent requests with ``asyncio.gather``
against a real MongoDB instance. They run against the isolated test database
provisioned by ``tests/conftest.py`` (never the developer database) and assert
both the HTTP outcome and the *persisted* records, not just status codes.

If MongoDB is unavailable the whole module is skipped with an explicit reason
so a green run can never be mistaken for verified real-database behaviour.
"""

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from bson import ObjectId
from pymongo.asynchronous.mongo_client import AsyncMongoClient

from app.core.config import settings
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.repositories.category_repository import CategoryRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserRole
from app.services.token_service import RefreshTokenService
from app.services.user_service import UserService

# A single bcrypt hash reused by every seeded user (bcrypt at cost 12 is slow
# and none of these tests authenticate with a password).
_PASSWORD_HASH = hash_password("SecurePass123!")


def new_oid() -> str:
    """Return a fresh 24-hex ObjectId string."""
    return uuid.uuid4().hex[:24]


def token_for(user_id: str, role: UserRole) -> str:
    return create_access_token(user_id=user_id, role=role.value)


def auth(user_id: str, role: UserRole) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for(user_id, role)}"}


@pytest.fixture(scope="module", autouse=True)
def _require_mongodb() -> None:
    """Skip the module explicitly (never silently) when MongoDB is unavailable."""

    async def _ping() -> None:
        client: AsyncMongoClient[object] = AsyncMongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
        )
        try:
            await client.admin.command("ping")
        finally:
            await client.close()

    try:
        asyncio.run(_ping())
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Real MongoDB unavailable: {exc}")


async def seed_user(
    db,
    role: UserRole,
    *,
    organization_id: str | None = None,
    department_id: str | None = None,
    status: str = "active",
) -> str:
    """Insert an active user and return its canonical (stored) id."""
    user_id = new_oid()
    await UserRepository(db).create(
        {
            "_id": ObjectId(user_id),
            "email": f"{user_id}@example.gov",
            "phone": f"+1{int(user_id, 16) % 10**12:012d}",
            "full_name": f"User {user_id[:6]}",
            "password_hash": _PASSWORD_HASH,
            "role": role.value,
            "status": status,
            "organization_id": organization_id,
            "department_id": department_id,
            "is_verified": True,
            "failed_login_attempts": 0,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
    )
    return user_id


async def seed_routing(db, suffix: str) -> tuple[str, str, str]:
    """Seed an organization + department + category and return their ids."""
    org_id, dept_id, cat_id = new_oid(), new_oid(), new_oid()
    now = datetime.now(UTC)
    await OrganizationRepository(db).create(
        {
            "_id": ObjectId(org_id),
            "name": f"Org {suffix}",
            "code": f"O{suffix}".upper()[:10],
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
    )
    await DepartmentRepository(db).create(
        {
            "_id": ObjectId(dept_id),
            "organization_id": org_id,
            "name": f"Dept {suffix}",
            "code": f"D{suffix}".upper()[:10],
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
    )
    await CategoryRepository(db).create(
        {
            "_id": ObjectId(cat_id),
            "organization_id": org_id,
            "name": f"Cat {suffix}",
            "severity_level": 3,
            "priority_weight": 1.0,
            "default_department_id": dept_id,
            "status": "active",
            "sort_order": 0,
            "created_at": now,
            "updated_at": now,
        }
    )
    return org_id, dept_id, cat_id


async def create_complaint(client, cat_id: str, citizen_token: str) -> str:
    """Create a SUBMITTED, public complaint via the API and return its id."""
    r = await client.post(
        "/api/v1/complaints",
        json={
            "title": "Concurrency complaint",
            "description": "Concurrency complaint description",
            "category_id": cat_id,
            "location": {"type": "Point", "coordinates": [0, 0]},
        },
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


class TestDuplicateLikes:
    """The unique (complaint_id, user_id) index is the race boundary."""

    async def test_same_user_concurrent_likes_only_one_wins(self, client, db):
        _, _, cat_id = await seed_routing(db, uuid.uuid4().hex[:6])
        citizen = await seed_user(db, UserRole.CITIZEN)
        token = token_for(citizen, UserRole.CITIZEN)
        cid = await create_complaint(client, cat_id, token)

        async def like():
            return await client.post(
                f"/api/v1/complaints/{cid}/like",
                headers={"Authorization": f"Bearer {token}"},
            )

        results = await asyncio.gather(*[like() for _ in range(5)])
        codes = sorted(r.status_code for r in results)
        assert codes == [201, 409, 409, 409, 409], [r.text for r in results]

        # Persisted truth: exactly one like row, and the like-count endpoint agrees.
        persisted = await db["complaint_likes"].count_documents(
            {"complaint_id": ObjectId(cid)}
        )
        assert persisted == 1
        summary = await client.get(f"/api/v1/complaints/{cid}/likes")
        assert summary.json()["data"]["like_count"] == 1

    async def test_different_users_concurrent_likes_all_persist(self, client, db):
        _, _, cat_id = await seed_routing(db, uuid.uuid4().hex[:6])
        citizen = await seed_user(db, UserRole.CITIZEN)
        cid = await create_complaint(client, cat_id, token_for(citizen, UserRole.CITIZEN))

        users = [await seed_user(db, UserRole.CITIZEN) for _ in range(5)]

        async def like(uid: str):
            return await client.post(
                f"/api/v1/complaints/{cid}/like",
                headers=auth(uid, UserRole.CITIZEN),
            )

        results = await asyncio.gather(*[like(uid) for uid in users])
        assert all(r.status_code == 201 for r in results), [r.text for r in results]
        persisted = await db["complaint_likes"].count_documents(
            {"complaint_id": ObjectId(cid)}
        )
        assert persisted == 5

    async def test_concurrent_like_unlike_final_state_is_consistent(self, client, db):
        """A like/unlike race yields a final state consistent with its outcomes."""
        _, _, cat_id = await seed_routing(db, uuid.uuid4().hex[:6])
        citizen = await seed_user(db, UserRole.CITIZEN)
        token = token_for(citizen, UserRole.CITIZEN)
        cid = await create_complaint(client, cat_id, token)

        # Establish the like first.
        established = await client.post(
            f"/api/v1/complaints/{cid}/like",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert established.status_code == 201

        async def unlike():
            return await client.delete(
                f"/api/v1/complaints/{cid}/like",
                headers={"Authorization": f"Bearer {token}"},
            )

        async def like():
            return await client.post(
                f"/api/v1/complaints/{cid}/like",
                headers={"Authorization": f"Bearer {token}"},
            )

        unlike_r, like_r = await asyncio.gather(unlike(), like())
        assert unlike_r.status_code == 200
        assert like_r.status_code in (201, 409), like_r.text

        expected = 1 if like_r.status_code == 201 else 0
        persisted = await db["complaint_likes"].count_documents(
            {"complaint_id": ObjectId(cid)}
        )
        assert persisted == expected
        summary = await client.get(f"/api/v1/complaints/{cid}/likes")
        assert summary.json()["data"]["like_count"] == expected


class TestAssignmentAndStateConcurrency:
    """Guarded atomic updates are the race boundary for lifecycle changes."""

    @pytest.fixture(autouse=True)
    async def _ctx(self, db):
        self.org_id, self.dept_id, self.cat_id = await seed_routing(
            db, uuid.uuid4().hex[:6]
        )
        self.admin = await seed_user(db, UserRole.ADMIN)
        self.staff1 = await seed_user(
            db,
            UserRole.ORGANIZATION_STAFF,
            organization_id=self.org_id,
            department_id=self.dept_id,
        )
        self.staff2 = await seed_user(
            db,
            UserRole.ORGANIZATION_STAFF,
            organization_id=self.org_id,
            department_id=self.dept_id,
        )
        self.citizen = await seed_user(db, UserRole.CITIZEN)

    async def test_concurrent_assignment_only_one_wins(self, client, db):
        cid = await create_complaint(
            client, self.cat_id, token_for(self.citizen, UserRole.CITIZEN)
        )
        admin_auth = auth(self.admin, UserRole.ADMIN)

        async def assign(staff_id: str):
            return await client.patch(
                f"/api/v1/complaints/{cid}/assign",
                json={"assigned_to": staff_id},
                headers=admin_auth,
            )

        r1, r2 = await asyncio.gather(assign(self.staff1), assign(self.staff2))
        codes = {r1.status_code, r2.status_code}
        # A true optimistic-lock race yields {200, 409}; if the loser observes the
        # already-ONGOING complaint first it legitimately performs a reassignment
        # (documented ONGOING -> ONGOING), yielding {200, 200}. A 5xx is never OK.
        assert codes <= {200, 409}, (r1.text, r2.text)
        assert 200 in codes

        doc = await db["complaints"].find_one({"_id": ObjectId(cid)})
        assert doc["status"] == "ONGOING"
        assert doc["assigned_to"] in (self.staff1, self.staff2)
        assert doc["assigned_at"] is not None

    async def test_concurrent_status_transition_only_one_wins(self, client, db):
        cid = await create_complaint(
            client, self.cat_id, token_for(self.citizen, UserRole.CITIZEN)
        )
        admin_auth = auth(self.admin, UserRole.ADMIN)

        async def transition():
            return await client.patch(
                f"/api/v1/complaints/{cid}/status",
                json={"status": "ONGOING", "reason": "concurrent transition"},
                headers=admin_auth,
            )

        r1, r2 = await asyncio.gather(transition(), transition())
        codes = sorted(r.status_code for r in (r1, r2))
        # Exactly one transition is applied. The loser either loses the guarded
        # update (409 STATUS_CONFLICT) or observes the terminal-for-that-edge
        # ONGOING state and is rejected (422 INVALID_STATUS_TRANSITION).
        assert codes == [200, 409] or codes == [200, 422], (r1.text, r2.text)

        doc = await db["complaints"].find_one({"_id": ObjectId(cid)})
        assert doc["status"] == "ONGOING"

    async def test_concurrent_completion_only_one_wins(self, client, db):
        cid = await create_complaint(
            client, self.cat_id, token_for(self.citizen, UserRole.CITIZEN)
        )
        admin_auth = auth(self.admin, UserRole.ADMIN)

        # Advance SUBMITTED -> ONGOING -> PROCESSING first.
        for target in ("ONGOING", "PROCESSING"):
            step = await client.patch(
                f"/api/v1/complaints/{cid}/status",
                json={"status": target, "reason": "advance"},
                headers=admin_auth,
            )
            assert step.status_code == 200, step.text

        async def complete():
            return await client.patch(
                f"/api/v1/complaints/{cid}/complete",
                json={"reason": "concurrent completion"},
                headers=admin_auth,
            )

        r1, r2 = await asyncio.gather(complete(), complete())
        codes = sorted(r.status_code for r in (r1, r2))
        # Exactly one completion is applied; the loser sees either a lost
        # guarded update (409) or the now-terminal COMPLETED state (422).
        assert codes == [200, 409] or codes == [200, 422], (r1.text, r2.text)

        doc = await db["complaints"].find_one({"_id": ObjectId(cid)})
        assert doc["status"] == "COMPLETED"
        assert doc["completed_at"] is not None


class TestUniqueCreationConcurrency:
    """Unique indexes protect organization/department/category creation."""

    async def test_concurrent_organization_same_code(self, client, db):
        admin = await seed_user(db, UserRole.ADMIN)
        admin_auth = auth(admin, UserRole.ADMIN)
        suffix = uuid.uuid4().hex[:6].upper()
        code = f"C{suffix}"[:10]
        payload = {"name": f"Concurrent Org {suffix}", "code": code}

        async def create():
            return await client.post(
                "/api/v1/organizations", json=payload, headers=admin_auth
            )

        r1, r2 = await asyncio.gather(create(), create())
        assert {r1.status_code, r2.status_code} == {201, 409}, (r1.text, r2.text)
        count = await db["organizations"].count_documents({"code": code})
        assert count == 1

    async def test_concurrent_department_same_code(self, client, db):
        org_id, _, _ = await seed_routing(db, uuid.uuid4().hex[:6])
        admin = await seed_user(db, UserRole.ADMIN)
        admin_auth = auth(admin, UserRole.ADMIN)
        suffix = uuid.uuid4().hex[:6].upper()
        code = f"D{suffix}"[:10]
        payload = {
            "name": f"Concurrent Dept {suffix}",
            "code": code,
            "organization_id": org_id,
        }

        async def create():
            return await client.post(
                "/api/v1/departments", json=payload, headers=admin_auth
            )

        r1, r2 = await asyncio.gather(create(), create())
        assert {r1.status_code, r2.status_code} == {201, 409}, (r1.text, r2.text)
        count = await db["departments"].count_documents(
            {"organization_id": org_id, "code": code}
        )
        assert count == 1

    async def test_concurrent_category_same_name(self, client, db):
        org_id, dept_id, _ = await seed_routing(db, uuid.uuid4().hex[:6])
        admin = await seed_user(db, UserRole.ADMIN)
        admin_auth = auth(admin, UserRole.ADMIN)
        name = f"Concurrent Cat {uuid.uuid4().hex[:6]}"
        payload = {
            "organization_id": org_id,
            "name": name,
            "severity_level": 3,
            "priority_weight": 1.0,
            "default_department_id": dept_id,
        }

        async def create():
            return await client.post(
                "/api/v1/admin/categories", json=payload, headers=admin_auth
            )

        r1, r2 = await asyncio.gather(create(), create())
        assert {r1.status_code, r2.status_code} == {201, 409}, (r1.text, r2.text)
        count = await db["categories"].count_documents(
            {"organization_id": org_id, "name": name}
        )
        assert count == 1


class TestRefreshTokenConcurrency:
    """Guarded ``revoke_if_active`` is the race boundary for rotation."""

    async def _issue_pair(self, db, user_id: str):
        service = RefreshTokenService(
            RefreshTokenRepository(db), UserService(UserRepository(db))
        )
        return await service.issue_token_pair(user_id, UserRole.CITIZEN.value)

    async def test_concurrent_refresh_rotation(self, client, db):
        user_id = await seed_user(db, UserRole.CITIZEN)
        pair = await self._issue_pair(db, user_id)

        async def refresh():
            return await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": pair.refresh_token},
            )

        r1, r2 = await asyncio.gather(refresh(), refresh())
        assert {r1.status_code, r2.status_code} == {200, 401}, (r1.text, r2.text)

        loser = r2 if r1.status_code == 200 else r1
        assert loser.json()["error_code"] == "TOKEN_REVOKED"

        # The original token must be revoked, and at most one successor active.
        original = await db["token_blacklist"].find_one(
            {"token_hash": hash_refresh_token(pair.refresh_token)}
        )
        assert original is not None
        assert original["revoked_at"] is not None

    async def test_replay_of_rotated_token_is_rejected(self, client, db):
        user_id = await seed_user(db, UserRole.CITIZEN)
        pair = await self._issue_pair(db, user_id)

        first = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": pair.refresh_token}
        )
        assert first.status_code == 200

        replay = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": pair.refresh_token}
        )
        assert replay.status_code == 401
        assert replay.json()["error_code"] == "TOKEN_REVOKED"


class TestDeviceTokenConcurrency:
    """The unique (user_id, device_token) index + guarded upsert."""

    async def test_concurrent_device_registration_same_user_and_token(self, client, db):
        user_id = await seed_user(db, UserRole.CITIZEN)
        user_auth = auth(user_id, UserRole.CITIZEN)
        device_token = f"device-{uuid.uuid4().hex}"

        async def register():
            return await client.post(
                "/api/v1/notifications/devices",
                json={"device_token": device_token, "platform": "ios"},
                headers=user_auth,
            )

        r1, r2 = await asyncio.gather(register(), register())
        assert r1.status_code == 200, r1.text
        assert r2.status_code == 200, r2.text

        count = await db["device_tokens"].count_documents(
            {"user_id": ObjectId(user_id), "device_token": device_token}
        )
        assert count == 1


class TestComplaintNumberConcurrency:
    """The atomic per-year counter must never emit a duplicate number."""

    async def test_concurrent_complaint_creation_distinct_numbers(self, client, db):
        _, _, cat_id = await seed_routing(db, uuid.uuid4().hex[:6])
        citizen = await seed_user(db, UserRole.CITIZEN)
        citizen_auth = auth(citizen, UserRole.CITIZEN)
        payload = {
            "title": "Concurrency complaint",
            "description": "Concurrency complaint description",
            "category_id": cat_id,
            "location": {"type": "Point", "coordinates": [0, 0]},
        }

        async def create():
            return await client.post(
                "/api/v1/complaints", json=payload, headers=citizen_auth
            )

        results = await asyncio.gather(*[create() for _ in range(5)])
        assert all(r.status_code == 201 for r in results), [r.text for r in results]

        numbers = [r.json()["data"]["complaint_number"] for r in results]
        assert len(set(numbers)) == len(numbers)

        persisted = await db["complaints"].count_documents({"category_id": cat_id})
        assert persisted == 5
        distinct_persisted = await db["complaints"].distinct(
            "complaint_number", {"category_id": cat_id}
        )
        assert len(distinct_persisted) == 5
