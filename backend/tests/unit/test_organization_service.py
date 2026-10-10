"""Unit tests for Phase 1.7 Organization & Department service logic."""

from datetime import UTC, datetime

import pytest

from app.exceptions.base import (
    ConflictException,
    ForbiddenException,
    ValidationException,
)
from app.schemas.department import DepartmentCreateRequest
from app.schemas.organization import (
    OrganizationCreateRequest,
    OrganizationUpdateRequest,
)
from app.schemas.user import UserResponse, UserRole, UserStatus
from app.services.organization_service import OrganizationService
from tests.fakes import (
    FakeAuditLogRepository,
    FakeComplaintLookup,
    FakeDepartmentRepository,
    FakeOrganizationRepository,
    FakeUserRepository,
)

ORG1_ID = "507f1f77bcf86cd799439001"
ORG2_ID = "507f1f77bcf86cd799439002"
ADMIN_USER_ID = "507f1f77bcf86cd799439011"
ORG1_ADMIN_ID = "507f1f77bcf86cd799439012"
ORG2_ADMIN_ID = "507f1f77bcf86cd799439013"
ORG1_STAFF_ID = "507f1f77bcf86cd799439014"
CITIZEN_ID = "507f1f77bcf86cd799439015"


@pytest.fixture
def org_repo() -> FakeOrganizationRepository:
    repo = FakeOrganizationRepository()
    repo.seed(ORG1_ID, name="Municipal Corporation 1", code="MC1", is_active=True)
    repo.seed(ORG2_ID, name="Municipal Corporation 2", code="MC2", is_active=True)
    return repo


@pytest.fixture
def dept_repo() -> FakeDepartmentRepository:
    repo = FakeDepartmentRepository()
    repo.seed("dept1", organization_id=ORG1_ID, name="Roads", code="RD", is_active=True)
    repo.seed("dept2", organization_id=ORG2_ID, name="Water", code="WT", is_active=True)
    return repo


@pytest.fixture
def user_repo() -> FakeUserRepository:
    repo = FakeUserRepository()
    repo.seed(ADMIN_USER_ID, role="admin", email="admin@test.gov")
    repo.seed(ORG1_ADMIN_ID, role="organization_admin", organization_id=ORG1_ID, email="org1admin@test.gov")
    repo.seed(ORG2_ADMIN_ID, role="organization_admin", organization_id=ORG2_ID, email="org2admin@test.gov")
    repo.seed(ORG1_STAFF_ID, role="organization_staff", organization_id=ORG1_ID, department_id="dept1", email="staff1@test.gov")
    repo.seed(CITIZEN_ID, role="citizen", email="citizen@test.gov")
    return repo


@pytest.fixture
def complaint_repo() -> FakeComplaintLookup:
    return FakeComplaintLookup()


@pytest.fixture
def audit_repo() -> FakeAuditLogRepository:
    return FakeAuditLogRepository()


@pytest.fixture
def org_service(
    org_repo: FakeOrganizationRepository,
    dept_repo: FakeDepartmentRepository,
    user_repo: FakeUserRepository,
    complaint_repo: FakeComplaintLookup,
    audit_repo: FakeAuditLogRepository,
) -> OrganizationService:
    return OrganizationService(
        org_repo=org_repo,
        dept_repo=dept_repo,
        user_repo=user_repo,
        complaint_repo=complaint_repo,
        audit_repo=audit_repo,
    )


def make_user(
    uid: str,
    role: UserRole,
    org_id: str | None = None,
    dept_id: str | None = None,
) -> UserResponse:
    now = datetime.now(UTC)
    return UserResponse(
        id=uid,
        email="test@voice2gov.org",
        phone="+15551234567",
        full_name="Test User",
        role=role,
        status=UserStatus.ACTIVE,
        organization_id=org_id,
        department_id=dept_id,
        is_verified=True,
        created_at=now,
        updated_at=now,
    )


# -----------------------------------------------------------------------------
# Organization Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_create_organization_success(
    org_service: OrganizationService, audit_repo: FakeAuditLogRepository
) -> None:
    admin = make_user(ADMIN_USER_ID, UserRole.ADMIN)
    req = OrganizationCreateRequest(name="New City Org", code="NCO")
    resp = await org_service.create_organization(req, admin)
    assert resp.name == "New City Org"
    assert resp.code == "NCO"
    assert resp.is_active is True
    assert len(audit_repo.logs) == 1
    assert audit_repo.logs[0]["action"] == "organization.create"


@pytest.mark.asyncio
async def test_create_organization_duplicate_code(org_service: OrganizationService) -> None:
    admin = make_user(ADMIN_USER_ID, UserRole.ADMIN)
    req = OrganizationCreateRequest(name="Another Org", code="MC1")
    with pytest.raises(ConflictException, match="already exists"):
        await org_service.create_organization(req, admin)


@pytest.mark.asyncio
async def test_create_organization_duplicate_name(org_service: OrganizationService) -> None:
    admin = make_user(ADMIN_USER_ID, UserRole.ADMIN)
    req = OrganizationCreateRequest(name="Municipal Corporation 1", code="MC99")
    with pytest.raises(ConflictException, match="already exists"):
        await org_service.create_organization(req, admin)


@pytest.mark.asyncio
async def test_org_tenant_isolation_view(org_service: OrganizationService) -> None:
    org1_admin = make_user(ORG1_ADMIN_ID, UserRole.ORGANIZATION_ADMIN, org_id=ORG1_ID)
    # Allowed to view own org
    org = await org_service.get_organization(ORG1_ID, org1_admin)
    assert org.id == ORG1_ID

    # Forbidden to view another org
    with pytest.raises(ForbiddenException, match="Cross-organization"):
        await org_service.get_organization(ORG2_ID, org1_admin)


@pytest.mark.asyncio
async def test_admin_update_organization(org_service: OrganizationService, audit_repo: FakeAuditLogRepository) -> None:
    admin = make_user(ADMIN_USER_ID, UserRole.ADMIN)
    req = OrganizationUpdateRequest(description="Updated description")
    updated = await org_service.update_organization(ORG1_ID, req, admin)
    assert updated.description == "Updated description"
    assert any(log["action"] == "organization.update" for log in audit_repo.logs)

    # Forbidden for organization_admin per authoritative API contract
    org1_admin = make_user(ORG1_ADMIN_ID, UserRole.ORGANIZATION_ADMIN, org_id=ORG1_ID)
    with pytest.raises(ForbiddenException, match="Admin required"):
        await org_service.update_organization(ORG1_ID, req, org1_admin)

    # Forbidden for staff and citizen
    staff = make_user(ORG1_STAFF_ID, UserRole.ORGANIZATION_STAFF, org_id=ORG1_ID)
    with pytest.raises(ForbiddenException):
        await org_service.update_organization(ORG1_ID, req, staff)

    citizen = make_user(CITIZEN_ID, UserRole.CITIZEN)
    with pytest.raises(ForbiddenException):
        await org_service.update_organization(ORG1_ID, req, citizen)


@pytest.mark.asyncio
async def test_admin_toggle_org_status(org_service: OrganizationService, audit_repo: FakeAuditLogRepository) -> None:
    admin = make_user(ADMIN_USER_ID, UserRole.ADMIN)
    updated = await org_service.toggle_organization_status(ORG1_ID, False, admin)
    assert updated.is_active is False
    assert any(log["action"] == "organization.status_change" for log in audit_repo.logs)


# -----------------------------------------------------------------------------
# Department Tests & Tenant Isolation
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_org_admin_create_department_in_own_org(org_service: OrganizationService) -> None:
    org1_admin = make_user(ORG1_ADMIN_ID, UserRole.ORGANIZATION_ADMIN, org_id=ORG1_ID)
    req = DepartmentCreateRequest(name="Sanitation", code="SAN")
    resp = await org_service.create_department(req, org1_admin)
    assert resp.organization_id == ORG1_ID
    assert resp.name == "Sanitation"
    assert resp.code == "SAN"


@pytest.mark.asyncio
async def test_org_admin_cannot_assign_head_from_other_org(org_service: OrganizationService) -> None:
    org1_admin = make_user(ORG1_ADMIN_ID, UserRole.ORGANIZATION_ADMIN, org_id=ORG1_ID)
    # ORG2_ADMIN_ID belongs to ORG2
    req = DepartmentCreateRequest(name="Sanitation", code="SAN", head_user_id=ORG2_ADMIN_ID)
    with pytest.raises(ValidationException, match="same organization"):
        await org_service.create_department(req, org1_admin)


@pytest.mark.asyncio
async def test_department_duplicate_code_in_same_org(org_service: OrganizationService) -> None:
    org1_admin = make_user(ORG1_ADMIN_ID, UserRole.ORGANIZATION_ADMIN, org_id=ORG1_ID)
    # "RD" already exists in ORG1
    req = DepartmentCreateRequest(name="New Roads", code="RD")
    with pytest.raises(ConflictException, match="Department code already exists"):
        await org_service.create_department(req, org1_admin)


@pytest.mark.asyncio
async def test_cross_tenant_department_access(org_service: OrganizationService) -> None:
    org1_staff = make_user(ORG1_STAFF_ID, UserRole.ORGANIZATION_STAFF, org_id=ORG1_ID)
    # dept2 is in ORG2
    with pytest.raises(ForbiddenException, match="Cross-organization"):
        await org_service.get_department("dept2", org1_staff)


@pytest.mark.asyncio
async def test_org_admin_cannot_delete_other_org_department(org_service: OrganizationService) -> None:
    org1_admin = make_user(ORG1_ADMIN_ID, UserRole.ORGANIZATION_ADMIN, org_id=ORG1_ID)
    # dept2 belongs to ORG2
    with pytest.raises(ForbiddenException):
        await org_service.delete_department("dept2", org1_admin)


# -----------------------------------------------------------------------------
# Organization Complaint Dashboard & Priority Queue Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_org_complaints_queue_isolation(
    org_service: OrganizationService, complaint_repo: FakeComplaintLookup
) -> None:
    complaint_repo.seed(
        "c1",
        complaint_number="CMP-001",
        title="Pothole in Org 1",
        organization_id=ORG1_ID,
        department_id="dept1",
        status="SUBMITTED",
        priority_score=40.0,
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    complaint_repo.seed(
        "c2",
        complaint_number="CMP-002",
        title="Water leak in Org 2",
        organization_id=ORG2_ID,
        department_id="dept2",
        status="SUBMITTED",
        priority_score=80.0,
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
    )

    org1_admin = make_user(ORG1_ADMIN_ID, UserRole.ORGANIZATION_ADMIN, org_id=ORG1_ID)
    res = await org_service.get_my_org_complaints(org1_admin)
    items = res["items"]
    assert len(items) == 1
    assert items[0]["id"] == "c1"
    assert items[0]["organization_id"] == ORG1_ID

    # Priority queue test
    complaint_repo.seed(
        "c3",
        complaint_number="CMP-003",
        title="Critical Bridge crack Org 1",
        organization_id=ORG1_ID,
        department_id="dept1",
        status="SUBMITTED",
        priority_score=95.0,
        created_at=datetime(2024, 1, 3, tzinfo=UTC),
    )

    pqueue = await org_service.get_my_org_priority_queue(org1_admin)
    q_items = pqueue["items"]
    assert len(q_items) == 2
    # c3 priority 95.0 should come before c1 priority 40.0
    assert q_items[0]["id"] == "c3"
    assert q_items[1]["id"] == "c1"
