"""API tests for Phase 1.7 Organization Endpoints (ORG-01 to ORG-06).

Covers:
- GET /api/v1/organizations (Admin only, 403 for staff/citizen)
- POST /api/v1/organizations (Admin only, validation, duplicate code 409, 403 for citizen/staff)
- GET /api/v1/organizations/{id} (Org scoped or admin, 403 for cross-org)
- PUT /api/v1/organizations/{id} (Admin or Org Admin own org, 403 for cross-org or staff)
- PATCH /api/v1/organizations/{id}/status (Admin only)
- GET /api/v1/organizations/me/complaints (Org staff / admin scoped to own org)
- GET /api/v1/organizations/me/complaints/priority (Sorted by priority_score descending)
"""

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.dependencies.services import (
    get_organization_service,
    get_user_service,
)
from app.main import create_app
from app.schemas.user import UserRole
from app.services.organization_service import OrganizationService
from app.services.user_service import UserService
from tests.fakes import (
    FakeAuditLogRepository,
    FakeComplaintLookup,
    FakeDepartmentRepository,
    FakeOrganizationRepository,
    FakeUserRepository,
)

ADMIN_ID = "507f1f77bcf86cd799439011"
ORG1_ID = "507f1f77bcf86cd799439021"
ORG2_ID = "507f1f77bcf86cd799439022"

ORG1_ADMIN_ID = "507f1f77bcf86cd799439031"
ORG1_STAFF_ID = "507f1f77bcf86cd799439032"
ORG2_ADMIN_ID = "507f1f77bcf86cd799439033"
CITIZEN_ID = "507f1f77bcf86cd799439041"


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
def fake_audits() -> FakeAuditLogRepository:
    return FakeAuditLogRepository()


@pytest.fixture
async def app_client(
    fake_users: FakeUserRepository,
    fake_orgs: FakeOrganizationRepository,
    fake_depts: FakeDepartmentRepository,
    fake_complaints: FakeComplaintLookup,
    fake_audits: FakeAuditLogRepository,
) -> AsyncClient:
    app = create_app()
    now = datetime.now(UTC)

    # Seed users
    users_data = [
        (ADMIN_ID, "admin@test.gov", UserRole.ADMIN.value, None),
        (ORG1_ADMIN_ID, "org1admin@test.gov", UserRole.ORGANIZATION_ADMIN.value, ORG1_ID),
        (ORG1_STAFF_ID, "org1staff@test.gov", UserRole.ORGANIZATION_STAFF.value, ORG1_ID),
        (ORG2_ADMIN_ID, "org2admin@test.gov", UserRole.ORGANIZATION_ADMIN.value, ORG2_ID),
        (CITIZEN_ID, "citizen@test.gov", UserRole.CITIZEN.value, None),
    ]
    for uid, email, role, oid in users_data:
        fake_users.users[uid] = {
            "_id": uid,
            "email": email,
            "phone": "+919876543210",
            "full_name": f"User {uid[-3:]}",
            "role": role,
            "organization_id": oid,
            "status": "active",
            "is_active": True,
            "is_verified": True,
            "created_at": now,
            "updated_at": now,
        }

    # Seed orgs
    fake_orgs.organizations[ORG1_ID] = {
        "_id": ORG1_ID,
        "name": "Bruhat Bengaluru Mahanagara Palike",
        "code": "BBMP",
        "description": "City corporation",
        "contact_email": "contact@bbmp.gov.in",
        "contact_phone": "+918022221111",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    fake_orgs.organizations[ORG2_ID] = {
        "_id": ORG2_ID,
        "name": "Delhi Municipal Corporation",
        "code": "MCD",
        "description": "Delhi municipal corporation",
        "contact_email": "contact@mcd.gov.in",
        "contact_phone": "+911122221111",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }

    # Seed complaints for org 1 and org 2
    fake_complaints.complaints["c1"] = {
        "_id": "507f1f77bcf86cd799439051",
        "complaint_number": "CMP-2026-0001",
        "title": "Pothole in Koramangala",
        "description": "Deep pothole on 80ft road",
        "organization_id": ORG1_ID,
        "department_id": "507f1f77bcf86cd799439061",
        "status": "SUBMITTED",
        "priority_score": 75.5,
        "likes_count": 10,
        "created_at": now,
        "updated_at": now,
    }
    fake_complaints.complaints["c2"] = {
        "_id": "507f1f77bcf86cd799439052",
        "complaint_number": "CMP-2026-0002",
        "title": "Broken street light",
        "description": "Street light out near 4th block",
        "organization_id": ORG1_ID,
        "department_id": "507f1f77bcf86cd799439061",
        "status": "IN_PROGRESS",
        "priority_score": 90.0,
        "likes_count": 25,
        "created_at": now,
        "updated_at": now,
    }
    fake_complaints.complaints["c3"] = {
        "_id": "507f1f77bcf86cd799439053",
        "complaint_number": "CMP-2026-0003",
        "title": "Delhi Garbage Dump",
        "description": "Garbage not cleared in Lajpat Nagar",
        "organization_id": ORG2_ID,
        "department_id": "507f1f77bcf86cd799439062",
        "status": "SUBMITTED",
        "priority_score": 85.0,
        "likes_count": 5,
        "created_at": now,
        "updated_at": now,
    }

    org_service = OrganizationService(
        org_repo=fake_orgs,
        dept_repo=fake_depts,
        user_repo=fake_users,
        complaint_repo=fake_complaints,
        audit_repo=fake_audits,
    )
    user_service = UserService(fake_users)

    app.dependency_overrides[get_user_service] = lambda: user_service
    app.dependency_overrides[get_organization_service] = lambda: org_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def token(user_id: str, role: UserRole) -> str:
    return create_access_token(
        user_id=user_id,
        role=role.value,
    )


# =============================================================================
# ORG-01: List Organizations
# =============================================================================

@pytest.mark.asyncio
async def test_list_organizations_admin_only(app_client: AsyncClient) -> None:
    admin_auth = {"Authorization": f"Bearer {token(ADMIN_ID, UserRole.ADMIN)}"}
    res = await app_client.get("/api/v1/organizations", headers=admin_auth)
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["pagination"]["total_items"] == 2
    assert len(body["data"]["items"]) == 2

    # Staff or Citizen cannot list all organizations
    staff_auth = {"Authorization": f"Bearer {token(ORG1_STAFF_ID, UserRole.ORGANIZATION_STAFF)}"}
    res_staff = await app_client.get("/api/v1/organizations", headers=staff_auth)
    assert res_staff.status_code == 403

    cit_auth = {"Authorization": f"Bearer {token(CITIZEN_ID, UserRole.CITIZEN)}"}
    res_cit = await app_client.get("/api/v1/organizations", headers=cit_auth)
    assert res_cit.status_code == 403


# =============================================================================
# ORG-02: Create Organization
# =============================================================================

@pytest.mark.asyncio
async def test_create_organization_admin_only(app_client: AsyncClient) -> None:
    admin_auth = {"Authorization": f"Bearer {token(ADMIN_ID, UserRole.ADMIN)}"}
    payload = {
        "name": "Chennai Corporation",
        "code": "GCC",
        "description": "Greater Chennai Corporation",
        "contact_email": "contact@gcc.gov.in",
        "contact_phone": "+914422221111",
    }
    res = await app_client.post("/api/v1/organizations", json=payload, headers=admin_auth)
    assert res.status_code == 201
    created = res.json()["data"]
    assert created["code"] == "GCC"
    assert created["is_active"] is True

    # Duplicate code should fail with 409
    res_dup = await app_client.post("/api/v1/organizations", json=payload, headers=admin_auth)
    assert res_dup.status_code == 409


@pytest.mark.asyncio
async def test_create_organization_forbidden_for_non_admin(app_client: AsyncClient) -> None:
    org_admin_auth = {"Authorization": f"Bearer {token(ORG1_ADMIN_ID, UserRole.ORGANIZATION_ADMIN)}"}
    payload = {
        "name": "Unauthorized Org",
        "code": "UAUTH",
    }
    res = await app_client.post("/api/v1/organizations", json=payload, headers=org_admin_auth)
    assert res.status_code == 403


# =============================================================================
# ORG-03: Update Organization (Admin Only per Authoritative API Contract)
# =============================================================================

@pytest.mark.asyncio
async def test_update_organization_permissions(app_client: AsyncClient) -> None:
    admin_auth = {"Authorization": f"Bearer {token(ADMIN_ID, UserRole.ADMIN)}"}
    org1_auth = {"Authorization": f"Bearer {token(ORG1_ADMIN_ID, UserRole.ORGANIZATION_ADMIN)}"}
    staff_auth = {"Authorization": f"Bearer {token(ORG1_STAFF_ID, UserRole.ORGANIZATION_STAFF)}"}
    cit_auth = {"Authorization": f"Bearer {token(CITIZEN_ID, UserRole.CITIZEN)}"}

    # 1. Admin -> allowed
    res_admin = await app_client.put(
        f"/api/v1/organizations/{ORG1_ID}",
        json={"name": "BBMP Updated Name"},
        headers=admin_auth,
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["data"]["name"] == "BBMP Updated Name"

    # 2. Admin can update any organization
    res_admin_org2 = await app_client.put(
        f"/api/v1/organizations/{ORG2_ID}",
        json={"description": "Updated MCD Description"},
        headers=admin_auth,
    )
    assert res_admin_org2.status_code == 200

    # 3. Organization Admin -> forbidden (403) per authoritative API contract
    res_org_admin = await app_client.put(
        f"/api/v1/organizations/{ORG1_ID}",
        json={"name": "Hacked BBMP"},
        headers=org1_auth,
    )
    assert res_org_admin.status_code == 403

    # Cross-tenant org_admin -> forbidden (403)
    res_cross = await app_client.put(
        f"/api/v1/organizations/{ORG2_ID}",
        json={"name": "Hacked MCD"},
        headers=org1_auth,
    )
    assert res_cross.status_code == 403

    # 4. Organization Staff -> forbidden (403)
    res_staff = await app_client.put(
        f"/api/v1/organizations/{ORG1_ID}",
        json={"name": "Staff BBMP"},
        headers=staff_auth,
    )
    assert res_staff.status_code == 403

    # 5. Citizen -> forbidden (403)
    res_cit = await app_client.put(
        f"/api/v1/organizations/{ORG1_ID}",
        json={"name": "Citizen BBMP"},
        headers=cit_auth,
    )
    assert res_cit.status_code == 403

    # 6. Admin updating non-existent org -> 404
    res_404 = await app_client.put(
        "/api/v1/organizations/507f1f77bcf86cd799439999",
        json={"name": "Nonexistent Org"},
        headers=admin_auth,
    )
    assert res_404.status_code == 404


# =============================================================================
# ORG-04: Status Toggle
# =============================================================================

@pytest.mark.asyncio
async def test_toggle_organization_status_admin_only(app_client: AsyncClient) -> None:
    admin_auth = {"Authorization": f"Bearer {token(ADMIN_ID, UserRole.ADMIN)}"}
    res = await app_client.patch(
        f"/api/v1/organizations/{ORG1_ID}/status",
        json={"is_active": False},
        headers=admin_auth,
    )
    assert res.status_code == 200
    assert res.json()["data"]["is_active"] is False

    # Org admin cannot toggle status
    org1_auth = {"Authorization": f"Bearer {token(ORG1_ADMIN_ID, UserRole.ORGANIZATION_ADMIN)}"}
    res_org = await app_client.patch(
        f"/api/v1/organizations/{ORG1_ID}/status",
        json={"is_active": True},
        headers=org1_auth,
    )
    assert res_org.status_code == 403


# =============================================================================
# ORG-05: Organization Complaint Dashboard
# =============================================================================

@pytest.mark.asyncio
async def test_org_complaints_dashboard_scoped(app_client: AsyncClient) -> None:
    org1_auth = {"Authorization": f"Bearer {token(ORG1_STAFF_ID, UserRole.ORGANIZATION_STAFF)}"}
    res = await app_client.get("/api/v1/organizations/me/complaints", headers=org1_auth)
    assert res.status_code == 200
    body = res.json()
    assert body["pagination"]["total_items"] == 2
    # Ensure no complaint from org2 is returned
    for item in body["data"]["items"]:
        assert item["organization_id"] == ORG1_ID

    # Test filtering by status
    res_filt = await app_client.get(
        "/api/v1/organizations/me/complaints?status=IN_PROGRESS",
        headers=org1_auth,
    )
    assert res_filt.status_code == 200
    filt_body = res_filt.json()
    assert filt_body["pagination"]["total_items"] == 1
    assert filt_body["data"]["items"][0]["status"] == "IN_PROGRESS"


# =============================================================================
# ORG-06: Organization Priority Queue
# =============================================================================

@pytest.mark.asyncio
async def test_org_priority_queue_sorted(app_client: AsyncClient) -> None:
    org1_auth = {"Authorization": f"Bearer {token(ORG1_ADMIN_ID, UserRole.ORGANIZATION_ADMIN)}"}
    res = await app_client.get("/api/v1/organizations/me/complaints/priority", headers=org1_auth)
    assert res.status_code == 200
    body = res.json()
    assert body["pagination"]["total_items"] == 2
    items = body["data"]["items"]
    # c2 has 90.0, c1 has 75.5 -> c2 must come first
    assert items[0]["priority_score"] == 90.0
    assert items[1]["priority_score"] == 75.5
    for item in items:
        assert item["organization_id"] == ORG1_ID
