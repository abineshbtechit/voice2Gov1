"""Unit tests for Phase 1.7 CategoryService (CAT-01 to CAT-04)."""

from datetime import UTC, datetime

import pytest

from app.exceptions.base import (
    ConflictException,
    ValidationException,
)
from app.schemas.category import (
    CategoryCreateRequest,
    CategoryStatus,
    CategoryUpdateRequest,
)
from app.schemas.user import UserResponse, UserRole, UserStatus
from app.services.category_service import CategoryService
from tests.fakes import (
    FakeAuditLogRepository,
    FakeCategoryRepository,
    FakeDepartmentRepository,
    FakeOrganizationRepository,
)

ORG1_ID = "507f1f77bcf86cd799439001"
ORG2_ID = "507f1f77bcf86cd799439002"
ADMIN_USER_ID = "507f1f77bcf86cd799439011"
DEPT1_ID = "507f1f77bcf86cd799439021"
DEPT2_ID = "507f1f77bcf86cd799439022"


CAT1_ID = "507f1f77bcf86cd799439031"


@pytest.fixture
def org_repo() -> FakeOrganizationRepository:
    repo = FakeOrganizationRepository()
    repo.seed(ORG1_ID, name="Org 1", code="O1", is_active=True)
    repo.seed(ORG2_ID, name="Org 2", code="O2", is_active=True)
    return repo


@pytest.fixture
def dept_repo() -> FakeDepartmentRepository:
    repo = FakeDepartmentRepository()
    repo.seed(DEPT1_ID, organization_id=ORG1_ID, name="Roads", code="RD", is_active=True)
    repo.seed(DEPT2_ID, organization_id=ORG2_ID, name="Water", code="WT", is_active=True)
    return repo


@pytest.fixture
def cat_repo() -> FakeCategoryRepository:
    repo = FakeCategoryRepository()
    repo.seed(
        CAT1_ID,
        organization_id=ORG1_ID,
        name="Pothole",
        default_department_id=DEPT1_ID,
        severity_level=3,
        status="active",
        sort_order=1,
    )
    return repo


@pytest.fixture
def audit_repo() -> FakeAuditLogRepository:
    return FakeAuditLogRepository()


@pytest.fixture
def cat_service(
    cat_repo: FakeCategoryRepository,
    dept_repo: FakeDepartmentRepository,
    org_repo: FakeOrganizationRepository,
    audit_repo: FakeAuditLogRepository,
) -> CategoryService:
    return CategoryService(
        category_repo=cat_repo,
        dept_repo=dept_repo,
        org_repo=org_repo,
        audit_repo=audit_repo,
    )


def make_admin() -> UserResponse:
    now = datetime.now(UTC)
    return UserResponse(
        id=ADMIN_USER_ID,
        email="admin@test.gov",
        phone="+15551234567",
        full_name="Admin",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        is_verified=True,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_list_active_categories(cat_service: CategoryService) -> None:
    cats = await cat_service.list_active_categories(organization_id=ORG1_ID)
    assert len(cats) == 1
    assert cats[0].name == "Pothole"
    assert cats[0].default_department_id == DEPT1_ID


@pytest.mark.asyncio
async def test_create_category_success(
    cat_service: CategoryService, audit_repo: FakeAuditLogRepository
) -> None:
    admin = make_admin()
    req = CategoryCreateRequest(
        organization_id=ORG1_ID,
        name="Streetlight Out",
        default_department_id=DEPT1_ID,
        severity_level=2,
    )
    cat = await cat_service.create_category(req, admin)
    assert cat.name == "Streetlight Out"
    assert cat.organization_id == ORG1_ID
    assert cat.default_department_id == DEPT1_ID
    assert cat.status == CategoryStatus.ACTIVE
    assert any(log["action"] == "category.create" for log in audit_repo.logs)


@pytest.mark.asyncio
async def test_create_category_invalid_department_cross_org(cat_service: CategoryService) -> None:
    admin = make_admin()
    # DEPT2_ID belongs to ORG2, not ORG1
    req = CategoryCreateRequest(
        organization_id=ORG1_ID,
        name="Garbage Dump",
        default_department_id=DEPT2_ID,
        severity_level=2,
    )
    with pytest.raises(ValidationException, match="Default department does not exist"):
        await cat_service.create_category(req, admin)


@pytest.mark.asyncio
async def test_create_category_duplicate_name_in_org(cat_service: CategoryService) -> None:
    admin = make_admin()
    req = CategoryCreateRequest(
        organization_id=ORG1_ID,
        name="Pothole",
        default_department_id=DEPT1_ID,
        severity_level=4,
    )
    with pytest.raises(ConflictException, match="already exists"):
        await cat_service.create_category(req, admin)


@pytest.mark.asyncio
async def test_update_category(cat_service: CategoryService, audit_repo: FakeAuditLogRepository) -> None:
    admin = make_admin()
    req = CategoryUpdateRequest(severity_level=4, description="Major road hazards")
    updated = await cat_service.update_category(CAT1_ID, req, admin)
    assert updated.severity_level == 4
    assert updated.description == "Major road hazards"
    assert any(log["action"] == "category.update" for log in audit_repo.logs)


@pytest.mark.asyncio
async def test_delete_category_soft_delete(
    cat_service: CategoryService, audit_repo: FakeAuditLogRepository
) -> None:
    admin = make_admin()
    success = await cat_service.delete_category(CAT1_ID, admin)
    assert success is True
    assert any(log["action"] == "category.delete" for log in audit_repo.logs)

    # Now verify active category listing excludes cat1
    active = await cat_service.list_active_categories(organization_id=ORG1_ID)
    assert len(active) == 0
