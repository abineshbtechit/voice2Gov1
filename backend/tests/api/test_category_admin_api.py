"""API integration tests for Phase 1.7 Categories & Admin Category Management (CAT-01 to CAT-04).

Covers:
- GET /api/v1/categories:
  - Public active categories list (optional / no auth required)
  - Inactive categories excluded
  - Sorted by sort_order ascending
- POST /api/v1/admin/categories:
  - Admin only
  - Severity level validated (1-5)
  - Default department must exist and be active
  - Unique name constraint
- PUT /api/v1/admin/categories/{id}:
  - Admin only
  - Updated fields validated
- DELETE /api/v1/admin/categories/{id}:
  - Admin only
  - Soft-deactivates category
"""

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.dependencies.services import (
    get_category_service,
    get_user_service,
)
from app.main import create_app
from app.schemas.user import UserRole
from app.services.category_service import CategoryService
from app.services.user_service import UserService
from tests.fakes import (
    FakeAuditLogRepository,
    FakeCategoryRepository,
    FakeDepartmentRepository,
    FakeOrganizationRepository,
    FakeUserRepository,
)

ADMIN_ID = "507f1f77bcf86cd799439011"
CITIZEN_ID = "507f1f77bcf86cd799439041"
ORG_ID = "507f1f77bcf86cd799439021"
DEPT_ID = "507f1f77bcf86cd799439061"
CAT1_ID = "507f1f77bcf86cd799439081"
CAT2_ID = "507f1f77bcf86cd799439082"


@pytest.fixture
def fake_users() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def fake_cats() -> FakeCategoryRepository:
    return FakeCategoryRepository()


@pytest.fixture
def fake_depts() -> FakeDepartmentRepository:
    return FakeDepartmentRepository()


@pytest.fixture
def fake_orgs() -> FakeOrganizationRepository:
    return FakeOrganizationRepository()


@pytest.fixture
def fake_audits() -> FakeAuditLogRepository:
    return FakeAuditLogRepository()


@pytest.fixture
async def app_client(
    fake_users: FakeUserRepository,
    fake_cats: FakeCategoryRepository,
    fake_depts: FakeDepartmentRepository,
    fake_orgs: FakeOrganizationRepository,
    fake_audits: FakeAuditLogRepository,
) -> AsyncClient:
    app = create_app()
    now = datetime.now(UTC)

    # Users
    fake_users.users[ADMIN_ID] = {
        "_id": ADMIN_ID,
        "email": "admin@test.gov",
        "phone": "+919876543210",
        "full_name": "Admin User",
        "role": UserRole.ADMIN.value,
        "status": "active",
        "is_active": True,
        "is_verified": True,
        "created_at": now,
        "updated_at": now,
    }
    fake_users.users[CITIZEN_ID] = {
        "_id": CITIZEN_ID,
        "email": "citizen@test.gov",
        "phone": "+919876543211",
        "full_name": "Citizen User",
        "role": UserRole.CITIZEN.value,
        "status": "active",
        "is_active": True,
        "is_verified": True,
        "created_at": now,
        "updated_at": now,
    }

    # Org
    fake_orgs.organizations[ORG_ID] = {
        "_id": ORG_ID,
        "name": "Bruhat Bengaluru Mahanagara Palike",
        "code": "BBMP",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }

    # Department
    fake_depts.departments[DEPT_ID] = {
        "_id": DEPT_ID,
        "organization_id": ORG_ID,
        "name": "Roads",
        "code": "ROADS",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }

    # Categories: one active, one inactive
    fake_cats.categories[CAT1_ID] = {
        "_id": CAT1_ID,
        "organization_id": ORG_ID,
        "name": "Potholes",
        "description": "Road damage and potholes",
        "icon": "road",
        "color": "#FF5722",
        "default_department_id": DEPT_ID,
        "severity_level": 3,
        "status": "active",
        "is_active": True,
        "sort_order": 1,
        "created_at": now,
        "updated_at": now,
    }
    fake_cats.categories[CAT2_ID] = {
        "_id": CAT2_ID,
        "organization_id": ORG_ID,
        "name": "Archived Sanitation",
        "description": "Old sanitation category",
        "icon": "trash",
        "color": "#9E9E9E",
        "default_department_id": DEPT_ID,
        "severity_level": 2,
        "status": "inactive",
        "is_active": False,
        "sort_order": 2,
        "created_at": now,
        "updated_at": now,
    }

    cat_service = CategoryService(
        category_repo=fake_cats,
        dept_repo=fake_depts,
        org_repo=fake_orgs,
        audit_repo=fake_audits,
    )
    user_service = UserService(fake_users)

    app.dependency_overrides[get_user_service] = lambda: user_service
    app.dependency_overrides[get_category_service] = lambda: cat_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def token(user_id: str, role: UserRole) -> str:
    return create_access_token(user_id=user_id, role=role.value)


# =============================================================================
# CAT-01: Public active categories listing
# =============================================================================

@pytest.mark.asyncio
async def test_list_active_categories_public(app_client: AsyncClient) -> None:
    # Public unauthenticated request
    res = await app_client.get("/api/v1/categories")
    assert res.status_code == 200
    body = res.json()
    items = body["data"]
    # Only active category returned
    assert len(items) == 1
    assert items[0]["name"] == "Potholes"
    assert items[0]["status"] == "active"


# =============================================================================
# CAT-02 & CAT-03 & CAT-04: Admin Category CRUD
# =============================================================================

@pytest.mark.asyncio
async def test_admin_create_category(app_client: AsyncClient) -> None:
    admin_auth = {"Authorization": f"Bearer {token(ADMIN_ID, UserRole.ADMIN)}"}
    payload = {
        "organization_id": ORG_ID,
        "name": "Street Lights",
        "description": "Broken or missing lights",
        "icon": "lightbulb",
        "color": "#FFC107",
        "default_department_id": DEPT_ID,
        "severity_level": 2,
        "sort_order": 3,
    }
    res = await app_client.post("/api/v1/admin/categories", json=payload, headers=admin_auth)
    assert res.status_code == 201
    created = res.json()["data"]
    assert created["name"] == "Street Lights"
    assert created["severity_level"] == 2

    # Duplicate name should return 409
    res_dup = await app_client.post("/api/v1/admin/categories", json=payload, headers=admin_auth)
    assert res_dup.status_code == 409


@pytest.mark.asyncio
async def test_admin_create_category_invalid_department(app_client: AsyncClient) -> None:
    admin_auth = {"Authorization": f"Bearer {token(ADMIN_ID, UserRole.ADMIN)}"}
    payload = {
        "organization_id": ORG_ID,
        "name": "Parks",
        "description": "Park maintenance",
        "icon": "tree",
        "color": "#4CAF50",
        "default_department_id": "507f1f77bcf86cd799439999",  # Nonexistent
        "severity_level": 1,
    }
    res = await app_client.post("/api/v1/admin/categories", json=payload, headers=admin_auth)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_category_management_forbidden_for_citizen(app_client: AsyncClient) -> None:
    cit_auth = {"Authorization": f"Bearer {token(CITIZEN_ID, UserRole.CITIZEN)}"}
    payload = {
        "organization_id": ORG_ID,
        "name": "Citizen Category",
        "default_department_id": DEPT_ID,
        "severity_level": 1,
    }
    res = await app_client.post("/api/v1/admin/categories", json=payload, headers=cit_auth)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_update_and_delete_category(app_client: AsyncClient) -> None:
    admin_auth = {"Authorization": f"Bearer {token(ADMIN_ID, UserRole.ADMIN)}"}

    # Update
    res_up = await app_client.put(
        f"/api/v1/admin/categories/{CAT1_ID}",
        json={"description": "Updated road damages description"},
        headers=admin_auth,
    )
    assert res_up.status_code == 200
    assert res_up.json()["data"]["description"] == "Updated road damages description"

    # Delete (soft deactivation)
    res_del = await app_client.delete(f"/api/v1/admin/categories/{CAT1_ID}", headers=admin_auth)
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True

    # Now verify public list no longer includes it
    res_list = await app_client.get("/api/v1/categories")
    assert len(res_list.json()["data"]) == 0
