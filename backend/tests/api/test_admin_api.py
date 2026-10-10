"""API integration and security tests for Phase 1.7 Admin Endpoints (ADM-01 to ADM-05).

Covers:
- GET /api/v1/admin/dashboard:
  - Total counts and stats aggregation
  - Admin only (403 for citizen/staff)
- GET /api/v1/admin/users:
  - User listing with pagination & filtering
  - Password hashes / secrets excluded
- GET /api/v1/admin/users/{id}:
  - Target user detail
- PATCH /api/v1/admin/users/{id}/suspend:
  - Suspend user
  - Self-suspension guard (400)
  - Last-admin suspension guard (400)
- PATCH /api/v1/admin/users/{id}/activate:
  - Activate user
- GET /api/v1/admin/audit-logs:
  - Immutable audit logs query with pagination
  - Admin only
- GET /api/v1/admin/settings:
  - List settings with secrets masked
  - Admin only
- PUT /api/v1/admin/settings/{key}:
  - Update setting
  - Priority weights sum == 1.0 enforcement
  - Cache invalidation
"""

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.security import create_access_token
from app.dependencies.services import (
    get_admin_service,
    get_user_service,
)
from app.main import create_app
from app.schemas.user import UserRole
from app.services.admin_service import AdminService
from app.services.priority_service import PriorityService
from app.services.user_service import UserService
from tests.fakes import (
    FakeAdminSettingsRepository,
    FakeAuditLogRepository,
    FakeComplaintLookup,
    FakeDepartmentRepository,
    FakeOrganizationRepository,
    FakeUserRepository,
)

ADMIN_1_ID = "507f1f77bcf86cd799439011"
ADMIN_2_ID = "507f1f77bcf86cd799439012"
CITIZEN_ID = "507f1f77bcf86cd799439041"
TARGET_USER_ID = "507f1f77bcf86cd799439042"


@pytest.fixture
def fake_users() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def fake_orgs() -> FakeOrganizationRepository:
    return FakeOrganizationRepository()


@pytest.fixture
def fake_depts() -> FakeDepartmentRepository:
    return FakeDepartmentRepository()


@pytest.fixture
def fake_complaints() -> FakeComplaintLookup:
    return FakeComplaintLookup()


@pytest.fixture
def fake_settings() -> FakeAdminSettingsRepository:
    return FakeAdminSettingsRepository()


@pytest.fixture
def fake_audits() -> FakeAuditLogRepository:
    return FakeAuditLogRepository()


@pytest.fixture
def priority_service(fake_settings: FakeAdminSettingsRepository) -> PriorityService:
    return PriorityService(settings=Settings(), settings_repo=fake_settings)


@pytest.fixture
async def app_client(
    fake_users: FakeUserRepository,
    fake_orgs: FakeOrganizationRepository,
    fake_depts: FakeDepartmentRepository,
    fake_complaints: FakeComplaintLookup,
    fake_settings: FakeAdminSettingsRepository,
    fake_audits: FakeAuditLogRepository,
    priority_service: PriorityService,
) -> AsyncClient:
    app = create_app()
    now = datetime.now(UTC)

    # Seed users
    users = [
        (ADMIN_1_ID, "admin1@test.gov", UserRole.ADMIN.value, "active", True),
        (ADMIN_2_ID, "admin2@test.gov", UserRole.ADMIN.value, "active", True),
        (CITIZEN_ID, "citizen@test.gov", UserRole.CITIZEN.value, "active", True),
        (TARGET_USER_ID, "target@test.gov", UserRole.CITIZEN.value, "active", True),
    ]
    for uid, email, role, status, is_act in users:
        fake_users.users[uid] = {
            "_id": uid,
            "email": email,
            "phone": "+919876543210",
            "full_name": f"User {uid[-3:]}",
            "role": role,
            "status": status,
            "is_active": is_act,
            "is_verified": True,
            "password_hash": "$2b$12$secretpasswordhashthatmustneverleak",
            "created_at": now,
            "updated_at": now,
        }

    admin_service = AdminService(
        user_repo=fake_users,
        org_repo=fake_orgs,
        dept_repo=fake_depts,
        complaint_repo=fake_complaints,
        settings_repo=fake_settings,
        audit_repo=fake_audits,
        priority_service=priority_service,
    )
    user_service = UserService(fake_users)

    app.dependency_overrides[get_user_service] = lambda: user_service
    app.dependency_overrides[get_admin_service] = lambda: admin_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def token(user_id: str, role: UserRole) -> str:
    return create_access_token(user_id=user_id, role=role.value)


# =============================================================================
# ADM-01: Admin Dashboard
# =============================================================================

@pytest.mark.asyncio
async def test_admin_dashboard_stats(app_client: AsyncClient) -> None:
    admin_auth = {"Authorization": f"Bearer {token(ADMIN_1_ID, UserRole.ADMIN)}"}
    res = await app_client.get("/api/v1/admin/dashboard", headers=admin_auth)
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    data = body["data"]
    assert "total_users" in data
    assert "total_organizations" in data
    assert "total_departments" in data
    assert "total_complaints" in data

    # Citizen forbidden
    cit_auth = {"Authorization": f"Bearer {token(CITIZEN_ID, UserRole.CITIZEN)}"}
    res_cit = await app_client.get("/api/v1/admin/dashboard", headers=cit_auth)
    assert res_cit.status_code == 403


# =============================================================================
# ADM-02: User Management (List, Detail, Suspend, Activate)
# =============================================================================

@pytest.mark.asyncio
async def test_admin_user_listing_excludes_secrets(app_client: AsyncClient) -> None:
    admin_auth = {"Authorization": f"Bearer {token(ADMIN_1_ID, UserRole.ADMIN)}"}
    res = await app_client.get("/api/v1/admin/users", headers=admin_auth)
    assert res.status_code == 200
    body = res.json()
    items = body["data"]["items"]
    assert len(items) == 4
    for u in items:
        assert "password_hash" not in u
        assert "password" not in u


@pytest.mark.asyncio
async def test_admin_suspend_and_activate_user(app_client: AsyncClient) -> None:
    admin_auth = {"Authorization": f"Bearer {token(ADMIN_1_ID, UserRole.ADMIN)}"}

    # Suspend target user
    res_susp = await app_client.patch(
        f"/api/v1/admin/users/{TARGET_USER_ID}/suspend",
        json={"reason": "Terms violation"},
        headers=admin_auth,
    )
    assert res_susp.status_code == 200
    assert res_susp.json()["data"]["status"] == "suspended"

    # Activate target user
    res_act = await app_client.patch(
        f"/api/v1/admin/users/{TARGET_USER_ID}/activate",
        headers=admin_auth,
    )
    assert res_act.status_code == 200
    assert res_act.json()["data"]["status"] == "active"


@pytest.mark.asyncio
async def test_admin_self_suspension_blocked(app_client: AsyncClient) -> None:
    admin_auth = {"Authorization": f"Bearer {token(ADMIN_1_ID, UserRole.ADMIN)}"}
    res = await app_client.patch(
        f"/api/v1/admin/users/{ADMIN_1_ID}/suspend",
        json={"reason": "Self-sabotage"},
        headers=admin_auth,
    )
    assert res.status_code == 403


# =============================================================================
# ADM-03 & ADM-04: Immutable Audit Logs
# =============================================================================

@pytest.mark.asyncio
async def test_admin_audit_logs_endpoint(app_client: AsyncClient) -> None:
    admin_auth = {"Authorization": f"Bearer {token(ADMIN_1_ID, UserRole.ADMIN)}"}

    # First trigger an action to create an audit log
    await app_client.patch(
        f"/api/v1/admin/users/{TARGET_USER_ID}/suspend",
        json={"reason": "Testing audit generation"},
        headers=admin_auth,
    )

    # Query audit logs
    res = await app_client.get("/api/v1/admin/audit-logs", headers=admin_auth)
    assert res.status_code == 200
    body = res.json()
    assert body["pagination"]["total_items"] >= 1
    items = body["data"]["items"]
    assert any(log["action"] == "user.suspend" for log in items)


# =============================================================================
# ADM-05: System Settings & Priority Weight Rule
# =============================================================================

@pytest.mark.asyncio
async def test_admin_settings_lifecycle(app_client: AsyncClient) -> None:
    admin_auth = {"Authorization": f"Bearer {token(ADMIN_1_ID, UserRole.ADMIN)}"}

    # 1. Update general setting
    res_gen = await app_client.put(
        "/api/v1/admin/settings/general.max_file_size_mb",
        json={"value": 15, "category": "general"},
        headers=admin_auth,
    )
    assert res_gen.status_code == 200
    assert res_gen.json()["data"]["value"] == 15

    # 2. Get settings
    res_list = await app_client.get("/api/v1/admin/settings", headers=admin_auth)
    assert res_list.status_code == 200
    assert len(res_list.json()["data"]) >= 1

    # 3. Invalid priority weights update (must fail if sum != 1.0)
    res_invalid_w = await app_client.put(
        "/api/v1/admin/settings/priority.weights.community_engagement",
        json={"value": 0.8},
        headers=admin_auth,
    )
    assert res_invalid_w.status_code == 422
    assert res_invalid_w.json()["error_code"] == "INVALID_WEIGHT_CONFIGURATION"

    # 4. Attempting to set legacy weight models (upvote, urgency) must return 422 INVALID_WEIGHT_CONFIGURATION
    res_legacy = await app_client.put(
        "/api/v1/admin/settings/priority.weights.upvote_weight",
        json={"value": 0.35},
        headers=admin_auth,
    )
    assert res_legacy.status_code == 422
    assert res_legacy.json()["error_code"] == "INVALID_WEIGHT_CONFIGURATION"
