"""Integration tests for POST and GET /api/v1/complaints/{id}/updates (Phase 1.3.6)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.dependencies.services import get_complaint_service, get_user_service
from app.main import create_app
from app.schemas.complaint import ComplaintStatus
from app.schemas.complaint_update import UpdateType
from app.schemas.user import UserRole
from app.services.complaint_service import ComplaintService
from app.services.user_service import UserService
from tests.fakes import (
    FakeComplaintImageRepository,
    FakeComplaintLookup,
    FakeComplaintUpdateRepository,
    FakeUserRepository,
)

ORG_A_ID = "507f1f77bcf86cd799439012"
ORG_B_ID = "507f1f77bcf86cd799439099"
DEPT_A1_ID = "507f1f77bcf86cd799439014"
DEPT_A2_ID = "507f1f77bcf86cd799439018"

CITIZEN_ID = "507f1f77bcf86cd799439011"
OTHER_CITIZEN_ID = "507f1f77bcf86cd799439091"
STAFF_DEPT1_ID = "507f1f77bcf86cd799439021"
STAFF_DEPT2_ID = "507f1f77bcf86cd799439022"
ORG_ADMIN_ID = "507f1f77bcf86cd799439031"
GLOBAL_ADMIN_ID = "507f1f77bcf86cd799439041"

COMPLAINT_ID = "507f1f77bcf86cd799439051"
IMAGE_PROGRESS_ID = "507f1f77bcf86cd799439061"
IMAGE_EVIDENCE_ID = "507f1f77bcf86cd799439062"
OTHER_COMPLAINT_IMAGE_ID = "507f1f77bcf86cd799439063"


@pytest.fixture
def fake_users() -> FakeUserRepository:
    repo = FakeUserRepository()
    repo.seed(
        user_id=CITIZEN_ID,
        email="citizen@example.com",
        phone="+15550000001",
        role=UserRole.CITIZEN.value,
    )
    repo.seed(
        user_id=OTHER_CITIZEN_ID,
        email="other_citizen@example.com",
        phone="+15550000002",
        role=UserRole.CITIZEN.value,
    )
    repo.seed(
        user_id=STAFF_DEPT1_ID,
        email="staff1@org-a.com",
        phone="+15550000003",
        role=UserRole.ORGANIZATION_STAFF.value,
        organization_id=ORG_A_ID,
        department_id=DEPT_A1_ID,
    )
    repo.seed(
        user_id=STAFF_DEPT2_ID,
        email="staff2@org-a.com",
        phone="+15550000004",
        role=UserRole.ORGANIZATION_STAFF.value,
        organization_id=ORG_A_ID,
        department_id=DEPT_A2_ID,
    )
    repo.seed(
        user_id=ORG_ADMIN_ID,
        email="admin@org-a.com",
        phone="+15550000005",
        role=UserRole.ORGANIZATION_ADMIN.value,
        organization_id=ORG_A_ID,
    )
    repo.seed(
        user_id=GLOBAL_ADMIN_ID,
        email="admin@gov.com",
        phone="+15550000006",
        role=UserRole.ADMIN.value,
    )
    return repo


@pytest.fixture
def fake_complaints() -> FakeComplaintLookup:
    repo = FakeComplaintLookup()
    repo.seed(
        COMPLAINT_ID,
        complaint_number="CMP-2024-000001",
        user_id=CITIZEN_ID,
        organization_id=ORG_A_ID,
        department_id=DEPT_A1_ID,
        status=ComplaintStatus.ONGOING.value,
        assigned_to=STAFF_DEPT1_ID,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    return repo


@pytest.fixture
def fake_updates() -> FakeComplaintUpdateRepository:
    return FakeComplaintUpdateRepository()


@pytest.fixture
def fake_images() -> FakeComplaintImageRepository:
    repo = FakeComplaintImageRepository()
    repo.seed(
        IMAGE_PROGRESS_ID,
        complaint_id=COMPLAINT_ID,
        image_type="progress",
        is_deleted=False,
    )
    repo.seed(
        IMAGE_EVIDENCE_ID,
        complaint_id=COMPLAINT_ID,
        image_type="evidence",
        is_deleted=False,
    )
    repo.seed(
        OTHER_COMPLAINT_IMAGE_ID,
        complaint_id="507f1f77bcf86cd799439099",
        image_type="progress",
        is_deleted=False,
    )
    return repo


@pytest.fixture
def app(
    fake_users: FakeUserRepository,
    fake_complaints: FakeComplaintLookup,
    fake_updates: FakeComplaintUpdateRepository,
    fake_images: FakeComplaintImageRepository,
):
    app = create_app()
    user_service = UserService(fake_users)
    complaint_service = ComplaintService(
        complaint_repo=fake_complaints,  # type: ignore
        category_repo=AsyncMock(),
        department_repo=AsyncMock(),
        complaint_update_repo=fake_updates,  # type: ignore
        complaint_image_repo=fake_images,  # type: ignore
    )
    app.dependency_overrides[get_user_service] = lambda: user_service
    app.dependency_overrides[get_complaint_service] = lambda: complaint_service
    return app


def auth_header(user_id: str, role: UserRole) -> dict[str, str]:
    token = create_access_token(user_id=user_id, role=role.value)
    return {"Authorization": f"Bearer {token}"}


class TestComplaintUpdatesAPI:
    @pytest.mark.asyncio
    async def test_citizen_cannot_post_update(self, app) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/complaints/{COMPLAINT_ID}/updates",
                json={"message": "Citizen trying to update"},
                headers=auth_header(CITIZEN_ID, UserRole.CITIZEN),
            )
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_staff_department_mismatch_rejected(self, app) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/complaints/{COMPLAINT_ID}/updates",
                json={"message": "Staff from dept 2 updating dept 1 complaint"},
                headers=auth_header(STAFF_DEPT2_ID, UserRole.ORGANIZATION_STAFF),
            )
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_staff_successful_progress_note(self, app) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/complaints/{COMPLAINT_ID}/updates",
                json={
                    "update_type": "progress_note",
                    "message": "Crew inspected the road damage.",
                    "is_public": True,
                },
                headers=auth_header(STAFF_DEPT1_ID, UserRole.ORGANIZATION_STAFF),
            )
            assert resp.status_code == 201
            body = resp.json()
            assert body["success"] is True
            assert body["data"]["message"] == "Crew inspected the road damage."
            assert body["data"]["updated_by"] == STAFF_DEPT1_ID
            assert body["data"]["organization_id"] == ORG_A_ID
            assert body["data"]["department_id"] == DEPT_A1_ID

    @pytest.mark.asyncio
    async def test_cannot_inject_status_change_via_post(self, app) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/complaints/{COMPLAINT_ID}/updates",
                json={
                    "update_type": "status_change",
                    "message": "Trying to spoof status change",
                },
                headers=auth_header(STAFF_DEPT1_ID, UserRole.ORGANIZATION_STAFF),
            )
            assert resp.status_code == 422
            assert resp.json()["error_code"] == "INVALID_UPDATE_TYPE"

    @pytest.mark.asyncio
    async def test_image_reference_validation(self, app) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Nonexistent image
            resp = await client.post(
                f"/api/v1/complaints/{COMPLAINT_ID}/updates",
                json={"message": "With fake image", "images": ["507f1f77bcf86cd799439999"]},
                headers=auth_header(STAFF_DEPT1_ID, UserRole.ORGANIZATION_STAFF),
            )
            assert resp.status_code == 422
            assert resp.json()["error_code"] == "INVALID_IMAGE_REFERENCE"

            # 2. Image belonging to another complaint
            resp = await client.post(
                f"/api/v1/complaints/{COMPLAINT_ID}/updates",
                json={"message": "With other complaint image", "images": [OTHER_COMPLAINT_IMAGE_ID]},
                headers=auth_header(STAFF_DEPT1_ID, UserRole.ORGANIZATION_STAFF),
            )
            assert resp.status_code == 422
            assert resp.json()["error_code"] == "INVALID_IMAGE_REFERENCE"

            # 3. Evidence image rejected (only progress or completion allowed)
            resp = await client.post(
                f"/api/v1/complaints/{COMPLAINT_ID}/updates",
                json={"message": "With evidence image", "images": [IMAGE_EVIDENCE_ID]},
                headers=auth_header(STAFF_DEPT1_ID, UserRole.ORGANIZATION_STAFF),
            )
            assert resp.status_code == 422
            assert resp.json()["error_code"] == "INVALID_IMAGE_TYPE"

            # 4. Valid progress image accepted
            resp = await client.post(
                f"/api/v1/complaints/{COMPLAINT_ID}/updates",
                json={"message": "Valid progress update with image", "images": [IMAGE_PROGRESS_ID]},
                headers=auth_header(STAFF_DEPT1_ID, UserRole.ORGANIZATION_STAFF),
            )
            assert resp.status_code == 201
            assert resp.json()["data"]["images"] == [IMAGE_PROGRESS_ID]

    @pytest.mark.asyncio
    async def test_cross_tenant_complaint_access_hidden(self, app, fake_users) -> None:
        fake_users.seed(
            user_id="507f1f77bcf86cd799439088",
            email="foreign@org-b.com",
            phone="+15550000088",
            role=UserRole.ORGANIZATION_STAFF.value,
            organization_id=ORG_B_ID,
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/complaints/{COMPLAINT_ID}/updates",
                json={"message": "Cross tenant update attempt"},
                headers=auth_header("507f1f77bcf86cd799439088", UserRole.ORGANIZATION_STAFF),
            )
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_updates_visibility_filtering(self, app, fake_updates) -> None:
        now = datetime.now(UTC)
        await fake_updates.create({
            "complaint_id": COMPLAINT_ID,
            "organization_id": ORG_A_ID,
            "department_id": DEPT_A1_ID,
            "updated_by": STAFF_DEPT1_ID,
            "update_type": UpdateType.PROGRESS_NOTE.value,
            "message": "Public update note",
            "images": [],
            "is_public": True,
            "created_at": now,
        })
        await fake_updates.create({
            "complaint_id": COMPLAINT_ID,
            "organization_id": ORG_A_ID,
            "department_id": DEPT_A1_ID,
            "updated_by": STAFF_DEPT1_ID,
            "update_type": UpdateType.PROGRESS_NOTE.value,
            "message": "Internal staff-only note",
            "images": [],
            "is_public": False,
            "created_at": now,
        })

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Citizen owner sees only is_public == True
            resp_owner = await client.get(
                f"/api/v1/complaints/{COMPLAINT_ID}/updates",
                headers=auth_header(CITIZEN_ID, UserRole.CITIZEN),
            )
            assert resp_owner.status_code == 200
            items = resp_owner.json()["data"]
            assert len(items) == 1
            assert items[0]["message"] == "Public update note"

            # Other citizen gets 404 (not their complaint)
            resp_other = await client.get(
                f"/api/v1/complaints/{COMPLAINT_ID}/updates",
                headers=auth_header(OTHER_CITIZEN_ID, UserRole.CITIZEN),
            )
            assert resp_other.status_code == 404

            # Staff sees all (public + internal)
            resp_staff = await client.get(
                f"/api/v1/complaints/{COMPLAINT_ID}/updates",
                headers=auth_header(STAFF_DEPT1_ID, UserRole.ORGANIZATION_STAFF),
            )
            assert resp_staff.status_code == 200
            assert len(resp_staff.json()["data"]) == 2

            # Global admin sees all
            resp_admin = await client.get(
                f"/api/v1/complaints/{COMPLAINT_ID}/updates",
                headers=auth_header(GLOBAL_ADMIN_ID, UserRole.ADMIN),
            )
            assert resp_admin.status_code == 200
            assert len(resp_admin.json()["data"]) == 2

    @pytest.mark.asyncio
    async def test_complaint_missing_department_fails_update_creation(
        self,
        app,
        fake_complaints: FakeComplaintLookup,
    ) -> None:
        """If a complaint has no department_id, creating an update must fail rather than persisting null."""
        corrupt_complaint_id = "507f1f77bcf86cd799439088"
        fake_complaints.seed(
            corrupt_complaint_id,
            user_id=CITIZEN_ID,
            organization_id=ORG_A_ID,
            department_id=None,
            status=ComplaintStatus.SUBMITTED.value,
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/complaints/{corrupt_complaint_id}/updates",
                json={"message": "Progress on complaint with no department"},
                headers=auth_header(ORG_ADMIN_ID, UserRole.ORGANIZATION_ADMIN),
            )
            assert resp.status_code == 422
            assert resp.json()["error_code"] == "MISSING_DEPARTMENT"
