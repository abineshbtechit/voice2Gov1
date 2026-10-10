"""Unit tests for Phase 1.7 AdminService (ADM-01 to ADM-05)."""

from datetime import UTC, datetime

import pytest

from app.exceptions.base import (
    ForbiddenException,
    ValidationException,
)
from app.schemas.admin import SettingUpdateRequest
from app.schemas.user import UserResponse, UserRole, UserStatus
from app.services.admin_service import AdminService
from app.services.priority_service import PriorityService
from tests.fakes import (
    FakeAdminSettingsRepository,
    FakeAuditLogRepository,
    FakeComplaintLookup,
    FakeDepartmentRepository,
    FakeOrganizationRepository,
    FakeUserRepository,
)

ADMIN_1_ID = "507f1f77bcf86cd799439001"
ADMIN_2_ID = "507f1f77bcf86cd799439002"
USER_CITIZEN_ID = "507f1f77bcf86cd799439003"
ORG1_ID = "507f1f77bcf86cd799439011"
DEPT1_ID = "507f1f77bcf86cd799439021"


@pytest.fixture
def user_repo() -> FakeUserRepository:
    repo = FakeUserRepository()
    repo.seed(ADMIN_1_ID, role="admin", status="active", email="admin1@test.gov")
    repo.seed(ADMIN_2_ID, role="admin", status="active", email="admin2@test.gov")
    repo.seed(USER_CITIZEN_ID, role="citizen", status="active", email="citizen@test.gov")
    return repo


@pytest.fixture
def org_repo() -> FakeOrganizationRepository:
    repo = FakeOrganizationRepository()
    repo.seed(ORG1_ID, name="Municipal Corp", code="MC", is_active=True)
    return repo


@pytest.fixture
def dept_repo() -> FakeDepartmentRepository:
    repo = FakeDepartmentRepository()
    repo.seed(DEPT1_ID, organization_id=ORG1_ID, name="Sanitation", code="SAN", is_active=True)
    return repo


@pytest.fixture
def complaint_repo() -> FakeComplaintLookup:
    repo = FakeComplaintLookup()
    repo.seed(
        "comp1",
        complaint_number="CMP-001",
        organization_id=ORG1_ID,
        department_id=DEPT1_ID,
        status="COMPLETED",
        created_at=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
        completed_at=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
        sla_deadline=datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
    )
    repo.seed(
        "comp2",
        complaint_number="CMP-002",
        organization_id=ORG1_ID,
        department_id=DEPT1_ID,
        status="SUBMITTED",
        created_at=datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
    )
    return repo


@pytest.fixture
def settings_repo() -> FakeAdminSettingsRepository:
    repo = FakeAdminSettingsRepository()
    return repo


@pytest.fixture
def audit_repo() -> FakeAuditLogRepository:
    return FakeAuditLogRepository()


@pytest.fixture
def priority_service(settings_repo: FakeAdminSettingsRepository) -> PriorityService:
    # Build PriorityService with settings_repo
    return PriorityService(settings_repo=settings_repo)


@pytest.fixture
def admin_service(
    user_repo: FakeUserRepository,
    org_repo: FakeOrganizationRepository,
    dept_repo: FakeDepartmentRepository,
    complaint_repo: FakeComplaintLookup,
    settings_repo: FakeAdminSettingsRepository,
    audit_repo: FakeAuditLogRepository,
    priority_service: PriorityService,
) -> AdminService:
    return AdminService(
        user_repo=user_repo,
        org_repo=org_repo,
        dept_repo=dept_repo,
        complaint_repo=complaint_repo,
        settings_repo=settings_repo,
        audit_repo=audit_repo,
        priority_service=priority_service,
    )


def make_admin(uid: str = ADMIN_1_ID) -> UserResponse:
    now = datetime.now(UTC)
    return UserResponse(
        id=uid,
        email="admin@test.gov",
        phone="+15551234567",
        full_name="Admin",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        is_verified=True,
        created_at=now,
        updated_at=now,
    )


# -----------------------------------------------------------------------------
# ADM-01: Admin Dashboard Stats
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_dashboard_stats(admin_service: AdminService) -> None:
    stats = await admin_service.get_dashboard_stats()
    assert stats.total_users == 3
    assert stats.total_organizations == 1
    assert stats.total_departments == 1
    assert stats.total_complaints == 2
    assert stats.complaints_by_status.get("COMPLETED") == 1
    assert stats.complaints_by_status.get("SUBMITTED") == 1
    assert stats.avg_resolution_hours == 2.0
    assert stats.sla_compliance_rate == 1.0


# -----------------------------------------------------------------------------
# ADM-02: Admin User Management & Guards
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_suspend_and_activate_user(
    admin_service: AdminService, audit_repo: FakeAuditLogRepository
) -> None:
    admin = make_admin(ADMIN_1_ID)

    # Suspend citizen
    suspended = await admin_service.suspend_user(USER_CITIZEN_ID, reason="Misconduct", current_user=admin)
    assert suspended.status == UserStatus.SUSPENDED
    assert any(log["action"] == "user.suspend" for log in audit_repo.logs)

    # Activate citizen
    activated = await admin_service.activate_user(USER_CITIZEN_ID, current_user=admin)
    assert activated.status == UserStatus.ACTIVE
    assert any(log["action"] == "user.activate" for log in audit_repo.logs)


@pytest.mark.asyncio
async def test_admin_self_suspension_prevented(admin_service: AdminService) -> None:
    admin = make_admin(ADMIN_1_ID)
    with pytest.raises(ForbiddenException, match="cannot suspend their own account"):
        await admin_service.suspend_user(ADMIN_1_ID, reason="Self suspend", current_user=admin)


@pytest.mark.asyncio
async def test_last_admin_suspension_prevented(
    admin_service: AdminService, user_repo: FakeUserRepository
) -> None:
    # First suspend ADMIN_2
    admin1 = make_admin(ADMIN_1_ID)
    await admin_service.suspend_user(ADMIN_2_ID, reason="Second admin suspend", current_user=admin1)

    # Now there is only 1 active admin (ADMIN_1).
    # If another admin or call tries to suspend ADMIN_1, last admin protection fires:
    # Simulate actor who is not ADMIN_1 attempting to suspend ADMIN_1
    other_actor = make_admin(ADMIN_2_ID)
    with pytest.raises(ForbiddenException, match="last active administrator"):
        await admin_service.suspend_user(ADMIN_1_ID, reason="Suspend only admin left", current_user=other_actor)


# -----------------------------------------------------------------------------
# ADM-03 & ADM-04: Immutable Audit Review
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_log_query(admin_service: AdminService, audit_repo: FakeAuditLogRepository) -> None:
    entity_id = "507f1f77bcf86cd799439099"
    await audit_repo.log_event(
        actor_id=ADMIN_1_ID,
        actor_role="admin",
        action="test.action",
        entity_type="test_entity",
        entity_id=entity_id,
        metadata={"detail": "some info"},
    )

    logs = await admin_service.get_audit_logs()
    assert len(logs) == 1
    assert logs[0].action == "test.action"
    assert logs[0].actor_id == ADMIN_1_ID
    assert logs[0].entity_id == entity_id


# -----------------------------------------------------------------------------
# ADM-05: System Settings & Priority Weight Validation
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_general_setting(admin_service: AdminService) -> None:
    admin = make_admin(ADMIN_1_ID)
    req = SettingUpdateRequest(value=20, description="Max upload size")
    res = await admin_service.update_setting("general.max_file_size_mb", req, admin)
    assert res.key == "general.max_file_size_mb"
    assert res.value == 20


@pytest.mark.asyncio
async def test_priority_weights_must_sum_to_one(admin_service: AdminService) -> None:
    admin = make_admin(ADMIN_1_ID)
    # Default weights: comm 0.3, sev 0.4, age 0.2, org 0.1 (sum = 1.0)
    # Trying to set comm to 0.5 without adjusting others makes sum = 1.2 -> must fail
    req = SettingUpdateRequest(value=0.5)
    with pytest.raises(ValidationException, match="must sum to exactly 1.0"):
        await admin_service.update_setting("priority.weights.community_engagement", req, admin)


@pytest.mark.asyncio
async def test_priority_weights_valid_update_and_cache_invalidation(
    admin_service: AdminService,
    settings_repo: FakeAdminSettingsRepository,
    priority_service: PriorityService,
) -> None:
    admin = make_admin(ADMIN_1_ID)
    # Change sev from 0.40 to 0.35 and org from 0.10 to 0.15 (sum stays 1.0)
    # Invalidate cache so priority_service picks up repo changes
    await settings_repo.set_setting("priority.weights.severity", 0.35, "priority")
    priority_service.invalidate_cache()

    req = SettingUpdateRequest(value=0.15)
    res = await admin_service.update_setting("priority.weights.organization_boost", req, admin)
    assert res.value == 0.15

    # Verify priority_service reflects updated weights
    weights = await priority_service.get_weights()
    assert weights.severity == 0.35
    assert weights.organization_boost == 0.15


@pytest.mark.asyncio
async def test_reject_legacy_weight_keys(admin_service: AdminService) -> None:
    admin = make_admin(ADMIN_1_ID)
    # Attempting to set legacy weight keys must be rejected with INVALID_WEIGHT_CONFIGURATION
    legacy_keys = [
        "priority.weights.upvote_weight",
        "priority.weights.urgency_weight",
        "priority.weights.severity_weight",
        "priority.weights.upvote",
        "priority.weights.urgency",
    ]
    for key in legacy_keys:
        req = SettingUpdateRequest(value=0.33)
        with pytest.raises(ValidationException) as exc_info:
            await admin_service.update_setting(key, req, admin)
        assert exc_info.value.error_code == "INVALID_WEIGHT_CONFIGURATION"
        assert "Invalid priority weight setting key" in str(exc_info.value)
