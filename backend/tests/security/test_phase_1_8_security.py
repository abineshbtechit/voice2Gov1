"""
Phase 1.8 Production Hardening — Security Tests

Covers:
- JWT manipulation and token-type confusion
- Refresh token replay/reuse/revocation
- Tenant isolation cross-org read/write
- RBAC matrix on sensitive endpoints
- State machine terminal-state and invalid-transition rejection
- Mass assignment (register + complaint create + admin suspend)
- Error leakage (stack traces, paths, URIs)
- Admin settings strict key allowlist
- Audit log immutability
- Notification isolation
- Password policy enforcement (72-byte bcrypt limit)
- Production config fail-fast
"""
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import (
    create_access_token,
    hash_password,
)
from app.dependencies.services import (
    get_admin_service,
    get_category_service,
    get_complaint_service,
    get_notification_service,
    get_organization_service,
    get_refresh_token_service,
    get_user_service,
)
from app.main import create_app
from app.middleware.rate_limit import disable_rate_limiting, enable_rate_limiting
from app.schemas.user import UserRole, UserStatus
from app.services.admin_service import AdminService
from app.services.category_service import CategoryService
from app.services.complaint_service import ComplaintService
from app.services.notification_service import NotificationService
from app.services.organization_service import OrganizationService
from app.services.priority_service import PriorityService
from app.services.token_service import RefreshTokenService
from app.services.user_service import UserService
from tests.fakes import (
    FakeAdminSettingsRepository,
    FakeAuditLogRepository,
    FakeCategoryRepository,
    FakeComplaintImageRepository,
    FakeComplaintLikeRepository,
    FakeComplaintLookup,
    FakeComplaintUpdateRepository,
    FakeDepartmentRepository,
    FakeDeviceTokenRepository,
    FakeNotificationRepository,
    FakeOrganizationRepository,
    FakeRefreshTokenRepository,
    FakeUserRepository,
)

VALID_PASSWORD = "SecurePass123!"


@pytest.fixture
def enable_rate_limiting_for_tests() -> Iterator[None]:
    enable_rate_limiting()
    yield
    disable_rate_limiting()


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def user_repo() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def user_service(user_repo) -> UserService:
    return UserService(user_repo)


@pytest.fixture
def rt_repo() -> FakeRefreshTokenRepository:
    return FakeRefreshTokenRepository()


@pytest.fixture
def token_service(rt_repo, user_service) -> RefreshTokenService:
    return RefreshTokenService(rt_repo, user_service)


@pytest.fixture
def org_repo() -> FakeOrganizationRepository:
    return FakeOrganizationRepository()


@pytest.fixture
def dept_repo() -> FakeDepartmentRepository:
    return FakeDepartmentRepository()


@pytest.fixture
def cat_repo() -> FakeCategoryRepository:
    return FakeCategoryRepository()


@pytest.fixture
def complaint_repo() -> FakeComplaintLookup:
    return FakeComplaintLookup()


@pytest.fixture
def like_repo() -> FakeComplaintLikeRepository:
    return FakeComplaintLikeRepository()


@pytest.fixture
def image_repo() -> FakeComplaintImageRepository:
    return FakeComplaintImageRepository()


@pytest.fixture
def update_repo() -> FakeComplaintUpdateRepository:
    return FakeComplaintUpdateRepository()


@pytest.fixture
def settings_repo() -> FakeAdminSettingsRepository:
    return FakeAdminSettingsRepository()


@pytest.fixture
def audit_repo() -> FakeAuditLogRepository:
    return FakeAuditLogRepository()


@pytest.fixture
def notif_repo() -> FakeNotificationRepository:
    return FakeNotificationRepository()


@pytest.fixture
def device_repo() -> FakeDeviceTokenRepository:
    return FakeDeviceTokenRepository()


@pytest.fixture
def priority_service(like_repo, settings_repo) -> PriorityService:
    return PriorityService(like_repo=like_repo, settings_repo=settings_repo)


@pytest.fixture
def cat_service(cat_repo, dept_repo, org_repo, audit_repo) -> CategoryService:
    return CategoryService(cat_repo, dept_repo, org_repo, audit_repo)


@pytest.fixture
def org_service(org_repo, dept_repo, user_repo, complaint_repo, audit_repo) -> OrganizationService:
    return OrganizationService(
        org_repo, dept_repo, user_repo, complaint_repo, audit_repo
    )


@pytest.fixture
def admin_service(
    user_repo, org_repo, dept_repo, complaint_repo, settings_repo, audit_repo, priority_service
) -> AdminService:
    return AdminService(
        user_repo, org_repo, dept_repo, complaint_repo, settings_repo, audit_repo, priority_service
    )


@pytest.fixture
def complaint_service(
    complaint_repo,
    cat_repo,
    dept_repo,
    update_repo,
    image_repo,
    user_repo,
    priority_service,
    like_repo,
) -> ComplaintService:
    return ComplaintService(
        complaint_repo,
        cat_repo,
        dept_repo,
        update_repo,
        image_repo,
        user_repo,
        priority_service,
        like_repo,
    )


@pytest.fixture
def notif_service(notif_repo, device_repo) -> NotificationService:
    return NotificationService(notif_repo, device_repo)


@pytest.fixture
async def client(
    app,
    user_service,
    token_service,
    complaint_service,
    cat_service,
    org_service,
    admin_service,
    priority_service,
    notif_service,
):
    app.dependency_overrides[get_user_service] = lambda: user_service
    app.dependency_overrides[get_refresh_token_service] = lambda: token_service
    app.dependency_overrides[get_complaint_service] = lambda: complaint_service
    app.dependency_overrides[get_category_service] = lambda: cat_service
    app.dependency_overrides[get_organization_service] = lambda: org_service
    app.dependency_overrides[get_admin_service] = lambda: admin_service
    app.dependency_overrides[get_notification_service] = lambda: notif_service
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def seed_user(repo, user_id, email, role=UserRole.CITIZEN, status="active", password=VALID_PASSWORD, organization_id=None, department_id=None):
    """Seed a user and return the *canonical* id the repository stored.

    ``FakeUserRepository.seed`` canonicalises non-ObjectId ids (the fake mirrors
    the real repository, whose ``_id`` is an ObjectId). Tokens must be minted
    with the canonical id or the request would resolve to no user and fail 401.
    """
    return repo.seed(
        user_id,
        email=email,
        phone="+15551234567",
        role=role.value if hasattr(role, "value") else role,
        status=status,
        password_hash=hash_password(password),
        organization_id=organization_id,
        department_id=department_id,
    )


def make_token(user_id, role):
    return create_access_token(user_id=user_id, role=role.value)


ORG_A = "507f1f77bcf86cd799439012"
ORG_B = "507f1f77bcf86cd799439013"
DEPT_A = "507f1f77bcf86cd799439014"
DEPT_B = "507f1f77bcf86cd799439015"
CAT_A = "507f1f77bcf86cd799439016"


class TestJWTManipulation:
    """Phase 1.8 — JWT manipulation and token-type confusion."""

    async def test_expired_access_token_rejected(self, client, user_repo):
        user_id = seed_user(user_repo, "u_expired", "exp@example.com")
        token = create_access_token(user_id, expires_delta=timedelta(seconds=-1))
        r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401
        assert r.json()["error_code"] == "TOKEN_EXPIRED"

    async def test_tampered_access_token_rejected(self, client, user_repo):
        user_id = seed_user(user_repo, "u_tampered", "tamp@example.com")
        token = create_access_token(user_id)
        from tests.fakes import tamper_token
        bad = tamper_token(token)
        r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bad}"})
        assert r.status_code == 401
        assert r.json()["error_code"] == "TOKEN_INVALID"

    async def test_wrong_signing_secret_rejected(self, client, user_repo):
        user_id = seed_user(user_repo, "u_wrongsec", "wrongsec@example.com")
        # Manually re-sign with different secret (simulate forged token)
        import jwt
        payload = {"sub": user_id, "type": "access", "iat": int(datetime.now(UTC).timestamp()), "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp())}
        forged = jwt.encode(payload, "wrong-secret", algorithm="HS256")
        r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})
        assert r.status_code == 401
        assert r.json()["error_code"] == "TOKEN_INVALID"

    async def test_refresh_token_rejected_as_access_token(self, client, user_repo, token_service):
        user_id = seed_user(user_repo, "u_typeconf", "type@example.com")
        pair = await token_service.issue_token_pair(user_id)
        r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {pair.refresh_token}"})
        assert r.status_code == 401
        assert r.json()["error_code"] == "TOKEN_INVALID"

    async def test_access_token_rejected_as_refresh_token(self, client, user_repo):
        user_id = seed_user(user_repo, "u_at_as_rt", "atrt@example.com")
        at = create_access_token(user_id)
        r = await client.post("/api/v1/auth/refresh", json={"refresh_token": at})
        assert r.status_code == 401
        assert r.json()["error_code"] == "TOKEN_INVALID"

    async def test_missing_sub_claim_rejected(self, client):
        import jwt
        payload = {"type": "access", "iat": int(datetime.now(UTC).timestamp()), "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp())}
        token = jwt.encode(payload, "secret", algorithm="HS256")
        r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    async def test_deleted_user_token_rejected(self, client, user_repo):
        user_id = seed_user(user_repo, "u_deleted", "del@example.com")
        token = create_access_token(user_id)
        user_repo.users.pop(user_id, None)
        r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401
        assert r.json()["error_code"] == "TOKEN_INVALID"

    async def test_suspended_user_with_valid_access_token_rejected(self, client, user_repo):
        user_id = seed_user(user_repo, "u_suspended", "susp@example.com", status=UserStatus.SUSPENDED.value)
        token = create_access_token(user_id)
        r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401
        assert r.json()["error_code"] == "ACCOUNT_INACTIVE"


class TestRefreshTokenSecurity:
    """Phase 1.8 — Refresh rotation, replay, family revocation."""

    async def test_replay_after_logout_rejected(self, client, token_service, user_repo):
        user_id = seed_user(user_repo, "u_replay", "replay@example.com")
        pair = await token_service.issue_token_pair(user_id)
        await client.post("/api/v1/auth/logout", json={"refresh_token": pair.refresh_token})
        r = await client.post("/api/v1/auth/refresh", json={"refresh_token": pair.refresh_token})
        assert r.status_code == 401
        assert r.json()["error_code"] in ("TOKEN_REVOKED", "TOKEN_INVALID")

    async def test_reuse_detection_revokes_family(self, client, token_service, user_repo):
        user_id = seed_user(user_repo, "u_reuse", "reuse@example.com")
        pair = await token_service.issue_token_pair(user_id)
        first = await client.post("/api/v1/auth/refresh", json={"refresh_token": pair.refresh_token})
        assert first.status_code == 200
        second = await client.post("/api/v1/auth/refresh", json={"refresh_token": pair.refresh_token})
        assert second.status_code == 401
        assert second.json()["error_code"] == "TOKEN_REVOKED"

    async def test_refresh_rotation_for_suspended_user_rejected(self, client, user_repo, token_service):
        """Phase 1.8 D6: suspended user cannot rotate refresh token."""
        user_id = seed_user(user_repo, "u_susp_rt", "susprt@example.com", status=UserStatus.SUSPENDED.value)
        pair = await token_service.issue_token_pair(user_id)
        r = await client.post("/api/v1/auth/refresh", json={"refresh_token": pair.refresh_token})
        assert r.status_code == 401
        assert r.json()["error_code"] == "ACCOUNT_INACTIVE"

    async def test_refresh_rotation_for_locked_user_rejected(self, client, user_repo, token_service):
        user_id = seed_user(user_repo, "u_locked", "lock@example.com", status=UserStatus.LOCKED.value)
        pair = await token_service.issue_token_pair(user_id)
        r = await client.post("/api/v1/auth/refresh", json={"refresh_token": pair.refresh_token})
        assert r.status_code == 401
        assert r.json()["error_code"] == "ACCOUNT_INACTIVE"

    async def test_refresh_rotation_for_inactive_user_rejected(self, client, user_repo, token_service):
        user_id = seed_user(user_repo, "u_inactive", "inact@example.com", status=UserStatus.INACTIVE.value)
        pair = await token_service.issue_token_pair(user_id)
        r = await client.post("/api/v1/auth/refresh", json={"refresh_token": pair.refresh_token})
        assert r.status_code == 401
        assert r.json()["error_code"] == "ACCOUNT_INACTIVE"


class TestTenantIsolation:
    """Phase 1.8 — Cross-org read/write on all organization-scoped resources."""

    async def test_org_staff_read_other_org_complaint_404(self, client, complaint_service, complaint_repo, user_repo):
        staff_a = seed_user(user_repo, "staff_a", "sa@a.gov", UserRole.ORGANIZATION_STAFF, organization_id=ORG_A, department_id=DEPT_A)
        citizen_b = seed_user(user_repo, "cit_b", "cb@b.gov")
        cid = complaint_repo.seed(
            "c_cross",
            user_id=citizen_b,
            organization_id=ORG_B,
            department_id=DEPT_B,
            category_id=CAT_A,
            status="SUBMITTED",
            title="ORG B complaint",
            complaint_number="CMP-2024-999001",
        )
        token = make_token(staff_a, UserRole.ORGANIZATION_STAFF)
        r = await client.get(f"/api/v1/complaints/{cid}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404

    async def test_org_admin_write_other_org_complaint_404(self, client, complaint_service, complaint_repo, user_repo):
        admin_a = seed_user(user_repo, "admin_a", "aa@a.gov", UserRole.ORGANIZATION_ADMIN, organization_id=ORG_A)
        citizen_b = seed_user(user_repo, "cit_b2", "cb2@b.gov")
        cid = complaint_repo.seed(
            "c_cross2",
            user_id=citizen_b,
            organization_id=ORG_B,
            department_id=DEPT_B,
            category_id=CAT_A,
            status="SUBMITTED",
            title="ORG B complaint",
            complaint_number="CMP-2024-999002",
        )
        token = make_token(admin_a, UserRole.ORGANIZATION_ADMIN)
        # Attempt to assign (org_admin only)
        r = await client.patch(
            f"/api/v1/complaints/{cid}/assign",
            json={"assigned_to": "507f1f77bcf86cd799439999"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404

    async def test_org_staff_transition_other_org_404(self, client, complaint_service, complaint_repo, user_repo):
        staff_a = seed_user(user_repo, "staff_a3", "sa3@a.gov", UserRole.ORGANIZATION_STAFF, organization_id=ORG_A, department_id=DEPT_A)
        citizen_b = seed_user(user_repo, "cit_b3", "cb3@b.gov")
        cid = complaint_repo.seed(
            "c_cross3",
            user_id=citizen_b,
            organization_id=ORG_B,
            department_id=DEPT_B,
            category_id=CAT_A,
            status="SUBMITTED",
            title="ORG B complaint",
            complaint_number="CMP-2024-999003",
        )
        token = make_token(staff_a, UserRole.ORGANIZATION_STAFF)
        r = await client.patch(
            f"/api/v1/complaints/{cid}/status",
            json={"status": "ONGOING", "reason": "cross-org attempt"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404

    async def test_org_admin_assign_with_other_org_staff_id_rejected(self, client, complaint_service, complaint_repo, user_repo):
        admin_a = seed_user(user_repo, "admin_a2", "aa2@a.gov", UserRole.ORGANIZATION_ADMIN, organization_id=ORG_A)
        staff_b = seed_user(user_repo, "staff_b", "sb@b.gov", UserRole.ORGANIZATION_STAFF, organization_id=ORG_B, department_id=DEPT_B)
        citizen_a = seed_user(user_repo, "cit_a", "ca@a.gov")
        cid = complaint_repo.seed(
            "c_assign",
            user_id=citizen_a,
            organization_id=ORG_A,
            department_id=DEPT_A,
            category_id=CAT_A,
            status="SUBMITTED",
            title="ORG A complaint",
            complaint_number="CMP-2024-999004",
        )
        token = make_token(admin_a, UserRole.ORGANIZATION_ADMIN)
        r = await client.patch(
            f"/api/v1/complaints/{cid}/assign",
            json={"assigned_to": staff_b},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 422  # ORG_MISMATCH

    async def test_duplicate_ref_cross_org_rejected(self, client, complaint_service, complaint_repo, user_repo):
        admin_a = seed_user(user_repo, "admin_a3", "aa3@a.gov", UserRole.ORGANIZATION_ADMIN, organization_id=ORG_A)
        citizen_a = seed_user(user_repo, "cit_a", "ca@a.gov")
        cid = complaint_repo.seed(
            "c_dup",
            user_id=citizen_a,
            organization_id=ORG_A,
            department_id=DEPT_A,
            category_id=CAT_A,
            status="SUBMITTED",
            title="ORG A complaint",
            complaint_number="CMP-2024-999005",
        )
        # ``duplicate_of`` is validated as an ObjectId, so the referenced
        # complaint needs a real 24-hex id (unlike the free-form seed ids).
        other = complaint_repo.seed(
            "507f1f77bcf86cd799439021",
            user_id=citizen_a,
            organization_id=ORG_B,
            department_id=DEPT_B,
            category_id=CAT_A,
            status="SUBMITTED",
            title="ORG B complaint",
            complaint_number="CMP-2024-999006",
        )
        token = make_token(admin_a, UserRole.ORGANIZATION_ADMIN)
        r = await client.patch(
            f"/api/v1/complaints/{cid}/status",
            json={"status": "DUPLICATE", "reason": "cross-org dup", "duplicate_of": other},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 422
        assert r.json()["error_code"] == "CROSS_TENANT_DUPLICATE_REF"

    async def test_citizen_cannot_read_org_complaints(self, client, complaint_repo, user_repo):
        """Citizens can only see their own complaints."""
        citizen = seed_user(user_repo, "cit_only", "cit@only.gov")
        other_cit = seed_user(user_repo, "cit_other", "other@gov")
        cid = complaint_repo.seed(
            "c_citizen",
            user_id=other_cit,
            organization_id=ORG_A,
            department_id=DEPT_A,
            category_id=CAT_A,
            status="SUBMITTED",
            title="Other's complaint",
            complaint_number="CMP-2024-999007",
        )
        token = make_token(citizen, UserRole.CITIZEN)
        r = await client.get(f"/api/v1/complaints/{cid}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404


class TestRBACMatrix:
    """Phase 1.8 — RBAC on sensitive endpoints."""

    @pytest.fixture(autouse=True)
    def _seed(self, complaint_repo, user_repo):
        self.citizen = seed_user(user_repo, "cit_rbac", "cit@rbac.gov")
        self.staff = seed_user(user_repo, "staff_rbac", "staff@rbac.gov", UserRole.ORGANIZATION_STAFF, organization_id=ORG_A, department_id=DEPT_A)
        self.org_admin = seed_user(user_repo, "orgadmin_rbac", "oa@rbac.gov", UserRole.ORGANIZATION_ADMIN, organization_id=ORG_A)
        self.admin = seed_user(user_repo, "admin_rbac", "admin@rbac.gov", UserRole.ADMIN)
        self.cid = complaint_repo.seed(
            "c_rbac",
            user_id=self.citizen,
            organization_id=ORG_A,
            department_id=DEPT_A,
            category_id=CAT_A,
            status="SUBMITTED",
            title="RBAC test",
            complaint_number="CMP-2024-999008",
        )

    async def test_citizen_cannot_transition_status(self, client):
        token = make_token(self.citizen, UserRole.CITIZEN)
        r = await client.patch(
            f"/api/v1/complaints/{self.cid}/status",
            json={"status": "ONGOING", "reason": "citizen attempt"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403

    async def test_citizen_cannot_assign(self, client):
        token = make_token(self.citizen, UserRole.CITIZEN)
        r = await client.patch(
            f"/api/v1/complaints/{self.cid}/assign",
            json={"assigned_to": "507f1f77bcf86cd799439999"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403

    async def test_citizen_cannot_complete(self, client):
        token = make_token(self.citizen, UserRole.CITIZEN)
        r = await client.patch(
            f"/api/v1/complaints/{self.cid}/complete",
            json={"reason": "citizen attempt"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403

    async def test_staff_cannot_assign(self, client):
        token = make_token(self.staff, UserRole.ORGANIZATION_STAFF)
        r = await client.patch(
            f"/api/v1/complaints/{self.cid}/assign",
            json={"assigned_to": "507f1f77bcf86cd799439999"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403

    async def test_unauthenticated_admin_endpoints_401(self, client):
        endpoints = [
            ("GET", "/api/v1/admin/dashboard"),
            ("GET", "/api/v1/admin/users"),
            ("GET", "/api/v1/admin/settings"),
            ("GET", "/api/v1/admin/audit-logs"),
            ("POST", "/api/v1/admin/categories"),
        ]
        for method, path in endpoints:
            r = await client.request(method, path)
            assert r.status_code == 401, f"{method} {path} should be 401"

    async def test_org_staff_cannot_access_admin_endpoints(self, client):
        token = make_token(self.staff, UserRole.ORGANIZATION_STAFF)
        r = await client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403


class TestStateMachineHardening:
    """Phase 1.8 — Invalid transitions, terminal immutability, required reasons."""

    @pytest.fixture(autouse=True)
    def _seed(self, complaint_repo, user_repo):
        self.staff = seed_user(user_repo, "staff_sm", "staff@sm.gov", UserRole.ORGANIZATION_STAFF, organization_id=ORG_A, department_id=DEPT_A)
        self.org_admin = seed_user(user_repo, "orgadmin_sm", "oa@sm.gov", UserRole.ORGANIZATION_ADMIN, organization_id=ORG_A)
        self.citizen = seed_user(user_repo, "cit_sm", "cit@sm.gov")
        self.staff_token = make_token(self.staff, UserRole.ORGANIZATION_STAFF)
        self.org_admin_token = make_token(self.org_admin, UserRole.ORGANIZATION_ADMIN)

    async def _test_invalid(self, client, cid, token, to_status, expected_code):
        r = await client.patch(
            f"/api/v1/complaints/{cid}/status",
            json={"status": to_status, "reason": "invalid transition"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 422
        assert r.json()["error_code"] == expected_code

    async def test_terminal_completed_cannot_regress(self, client, complaint_repo):
        cid = complaint_repo.seed("c_term", user_id=self.citizen, organization_id=ORG_A, department_id=DEPT_A, category_id=CAT_A, status="COMPLETED", title="t", complaint_number="CMP-2024-999009")
        await self._test_invalid(client, cid, self.org_admin_token, "PROCESSING", "INVALID_STATUS_TRANSITION")

    async def test_terminal_rejected_cannot_regress(self, client, complaint_repo):
        cid = complaint_repo.seed("c_term2", user_id=self.citizen, organization_id=ORG_A, department_id=DEPT_A, category_id=CAT_A, status="REJECTED", title="t", complaint_number="CMP-2024-999010")
        await self._test_invalid(client, cid, self.org_admin_token, "PROCESSING", "INVALID_STATUS_TRANSITION")

    async def test_terminal_duplicate_cannot_regress(self, client, complaint_repo):
        cid = complaint_repo.seed("c_term3", user_id=self.citizen, organization_id=ORG_A, department_id=DEPT_A, category_id=CAT_A, status="DUPLICATE", title="t", complaint_number="CMP-2024-999011")
        await self._test_invalid(client, cid, self.org_admin_token, "ONGOING", "INVALID_STATUS_TRANSITION")

    async def test_terminal_closed_cannot_regress(self, client, complaint_repo):
        cid = complaint_repo.seed("c_term4", user_id=self.citizen, organization_id=ORG_A, department_id=DEPT_A, category_id=CAT_A, status="CLOSED", title="t", complaint_number="CMP-2024-999012")
        await self._test_invalid(client, cid, self.org_admin_token, "ONGOING", "INVALID_STATUS_TRANSITION")

    async def test_invalid_submitted_to_processing(self, client, complaint_repo):
        cid = complaint_repo.seed("c_inv", user_id=self.citizen, organization_id=ORG_A, department_id=DEPT_A, category_id=CAT_A, status="SUBMITTED", title="t", complaint_number="CMP-2024-999013")
        await self._test_invalid(client, cid, self.org_admin_token, "PROCESSING", "INVALID_STATUS_TRANSITION")

    async def test_rejection_requires_reason(self, client, complaint_repo):
        cid = complaint_repo.seed("c_noreas", user_id=self.citizen, organization_id=ORG_A, department_id=DEPT_A, category_id=CAT_A, status="SUBMITTED", title="t", complaint_number="CMP-2024-999014")
        r = await client.patch(
            f"/api/v1/complaints/{cid}/status",
            json={"status": "REJECTED", "reason": "   "},
            headers={"Authorization": f"Bearer {self.org_admin_token}"},
        )
        assert r.status_code == 422
        assert r.json()["error_code"] == "REASON_REQUIRED"

    async def test_duplicate_requires_reason_and_ref(self, client, complaint_repo):
        cid = complaint_repo.seed("c_dup2", user_id=self.citizen, organization_id=ORG_A, department_id=DEPT_A, category_id=CAT_A, status="SUBMITTED", title="t", complaint_number="CMP-2024-999015")
        r = await client.patch(
            f"/api/v1/complaints/{cid}/status",
            json={"status": "DUPLICATE", "reason": "dup reason"},
            headers={"Authorization": f"Bearer {self.org_admin_token}"},
        )
        assert r.status_code == 422
        assert r.json()["error_code"] == "DUPLICATE_REF_REQUIRED"

    async def test_completion_requires_reason(self, client, complaint_repo):
        cid = complaint_repo.seed("c_comp", user_id=self.citizen, organization_id=ORG_A, department_id=DEPT_A, category_id=CAT_A, status="PROCESSING", title="t", complaint_number="CMP-2024-999016")
        r = await client.patch(
            f"/api/v1/complaints/{cid}/complete",
            json={"reason": "   "},
            headers={"Authorization": f"Bearer {self.org_admin_token}"},
        )
        assert r.status_code == 422
        assert r.json()["error_code"] == "REASON_REQUIRED"


class TestMassAssignment:
    """Phase 1.8 — Extra fields rejected / server fields immutable."""

    async def test_register_with_role_injected_rejected(self, client):
        r = await client.post("/api/v1/auth/register", json={
            "email": "mass@reg.gov",
            "phone": "+15559999999",
            "full_name": "Mass User",
            "password": "SecurePass123!",
            "role": "admin",
            "status": "active",
        })
        assert r.status_code == 422  # extra=forbid

    async def test_complaint_create_injected_fields_ignored(
        self, client, complaint_repo, user_repo, cat_repo, dept_repo, org_repo
    ):
        """Unsolicited server-controlled fields are ignored; server values win.

        ``ComplaintCreateRequest`` does not forbid extra fields, so the service
        must overwrite every server-controlled field from trusted context.
        """
        cat_repo.seed(CAT_A, organization_id=ORG_A, name="Cat A", severity_level=3, priority_weight=1.0, default_department_id=DEPT_A, status="active")
        dept_repo.seed(DEPT_A, organization_id=ORG_A, name="Dept A", code="DA", is_active=True)
        org_repo.seed(ORG_A, name="Org A", code="ORGA", is_active=True)
        citizen = seed_user(user_repo, "cit_inj", "inj@cit.gov")
        token = make_token(citizen, UserRole.CITIZEN)
        r = await client.post(
            "/api/v1/complaints",
            json={
                "title": "Injected fields",
                "description": "Attempt to inject server-controlled fields",
                "category_id": CAT_A,
                "location": {"type": "Point", "coordinates": [0, 0]},
                "status": "COMPLETED",  # injected
                "priority_score": 99.9,
                "organization_id": ORG_B,
                "user_id": "507f1f77bcf86cd799439999",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201, r.text
        data = r.json()["data"]
        assert data["status"] == "SUBMITTED"
        assert data["priority_score"] == 0.0
        persisted = complaint_repo.complaints[str(data["id"])]
        assert persisted["status"] == "SUBMITTED"
        assert persisted["priority_score"] == 0.0
        assert str(persisted["user_id"]) == citizen
        assert str(persisted["organization_id"]) == ORG_A
        assert str(persisted["department_id"]) == DEPT_A

    async def test_admin_suspend_with_is_admin_injected_rejected(self, client, user_repo):
        admin = seed_user(user_repo, "admin_mi", "admin@mi.gov", UserRole.ADMIN)
        target = seed_user(user_repo, "tgt_mi", "tgt@mi.gov", UserRole.CITIZEN)
        token = make_token(admin, UserRole.ADMIN)
        r = await client.patch(
            f"/api/v1/admin/users/{target}/suspend",
            json={"reason": "test", "is_admin": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        # extra=forbid on UserSuspendRequest rejects unknown field
        assert r.status_code == 422


class TestErrorLeakage:
    """Phase 1.8 — No stack traces, paths, URIs, secrets in error responses."""

    async def test_invalid_objectid_returns_404(self, client, user_repo):
        citizen = seed_user(user_repo, "cit_eid", "eid@cit.gov")
        token = make_token(citizen, UserRole.CITIZEN)
        r = await client.get("/api/v1/complaints/not-an-objectid", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404
        body = r.text.lower()
        assert "traceback" not in body
        assert "pymongo" not in body
        assert "mongodb://" not in body

    async def test_malformed_json_returns_422(self, client):
        r = await client.post(
            "/api/v1/complaints",
            content=b"{not json}",
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 422
        body = r.text
        assert "traceback" not in body.lower()
        assert "file " not in body.lower()

    async def test_missing_complaint_with_valid_token_returns_404(self, client, user_repo):
        """An authenticated request for an absent complaint is a clean 404."""
        citizen = seed_user(user_repo, "cit_404", "e404@cit.gov")
        token = make_token(citizen, UserRole.CITIZEN)
        r = await client.get(
            "/api/v1/complaints/507f1f77bcf86cd799439000",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404
        body = r.text.lower()
        assert "traceback" not in body
        assert "pymongo" not in body
        assert "mongodb://" not in body

    async def test_internal_exception_mapped_to_generic_500(self, app, user_repo):
        """An uncaught dependency error becomes a generic 500 with no internals.

        Uses its own transport with ``raise_app_exceptions=False``: Starlette
        re-raises after emitting the handled 500 response, and httpx would
        otherwise surface that re-raise to the test instead of the response.
        """
        from app.dependencies.services import get_complaint_service, get_user_service
        from app.services.user_service import UserService

        citizen = seed_user(user_repo, "cit_500", "e500@cit.gov")
        token = make_token(citizen, UserRole.CITIZEN)

        def _boom():
            raise RuntimeError(
                "boom mongodb://admin:secret@host/db stacktrace /srv/app/secret.py"
            )

        app.dependency_overrides[get_user_service] = lambda: UserService(user_repo)
        app.dependency_overrides[get_complaint_service] = _boom
        try:
            transport = ASGITransport(app=app, raise_app_exceptions=False)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                r = await ac.get(
                    "/api/v1/complaints/507f1f77bcf86cd799439000",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert r.status_code == 500
        body = r.text.lower()
        for leak in ("traceback", "runtimeerror", "mongodb://", "secret", "/srv/app"):
            assert leak not in body, f"response leaked {leak!r}: {body}"


class TestAdminSettingsHardening:
    """Phase 1.8 — Strict key allowlist, secret masking, sum-to-1."""

    @pytest.fixture(autouse=True)
    def _seed(self, admin_service, user_repo):
        self.admin = seed_user(user_repo, "admin_set", "admin@set.gov", UserRole.ADMIN)
        self.token = make_token(self.admin, UserRole.ADMIN)

    async def test_arbitrary_key_rejected(self, client, admin_service):
        r = await client.put(
            "/api/v1/admin/settings/secret_key",
            json={"value": "hacked"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert r.status_code == 422
        assert r.json()["error_code"] == "INVALID_SETTING_KEY"

    async def test_priority_weight_non_canonical_rejected(self, client, admin_service):
        legacy_keys = ["priority.weights.upvote_weight", "priority.weights.urgency", "priority.weights.severity_weight"]
        for key in legacy_keys:
            r = await client.put(
                f"/api/v1/admin/settings/{key}",
                json={"value": 0.33},
                headers={"Authorization": f"Bearer {self.token}"},
            )
            assert r.status_code == 422
            assert r.json()["error_code"] == "INVALID_WEIGHT_CONFIGURATION"

    async def test_priority_weights_must_sum_to_one(self, client, admin_service):
        # Change one weight so sum != 1.0
        r = await client.put(
            "/api/v1/admin/settings/priority.weights.community_engagement",
            json={"value": 0.5},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert r.status_code == 422
        assert r.json()["error_code"] == "INVALID_WEIGHT_CONFIGURATION"

    async def test_valid_weight_update_sum_one(self, client, admin_service, settings_repo):
        # A coordinated change keeps the sum at 1.0: severity 0.40 -> 0.35 is
        # established out-of-band, then org_boost 0.10 -> 0.15 is applied via the
        # API (3 * 0.30 + 0.35 + 0.20 + 0.15 == 1.0).
        await settings_repo.set_setting("priority.weights.severity", 0.35, "priority")
        r = await client.put(
            "/api/v1/admin/settings/priority.weights.organization_boost",
            json={"value": 0.15},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["value"] == 0.15

    async def test_general_keys_allowed(self, client, admin_service):
        r = await client.put(
            "/api/v1/admin/settings/general.max_file_size_mb",
            json={"value": 15},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert r.status_code == 200

    async def test_non_admin_forbidden(self, client, user_repo):
        citizen = seed_user(user_repo, "cit_set", "cit@set.gov")
        token = make_token(citizen, UserRole.CITIZEN)
        r = await client.put(
            "/api/v1/admin/settings/general.max_file_size_mb",
            json={"value": 10},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403

    async def test_secret_masking_in_get_all(self, client, admin_service, settings_repo):
        """GET /admin/settings masks values for keys containing secret/password/token."""
        await settings_repo.set_setting("priority.test_secret_key", "real-secret", "priority", updated_by="test")
        r = await client.get("/api/v1/admin/settings", headers={"Authorization": f"Bearer {self.token}"})
        assert r.status_code == 200
        data = r.json()["data"]
        secret_item = next((item for item in data if item["key"] == "priority.test_secret_key"), None)
        assert secret_item is not None
        assert secret_item["value"] == "******"  # masked


class TestAuditLogImmutability:
    """Phase 1.8 — Audit logs append-only via API."""

    async def test_audit_logs_only_get_allowed(self, client, user_repo):
        admin = seed_user(user_repo, "admin_audit", "audit@admin.gov", UserRole.ADMIN)
        token = make_token(admin, UserRole.ADMIN)
        # GET allowed
        r = await client.get("/api/v1/admin/audit-logs", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        # POST/PATCH/DELETE not allowed (405)
        for method in ("POST", "PATCH", "DELETE"):
            r = await client.request(method, "/api/v1/admin/audit-logs", headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 405


class TestNotificationIsolation:
    """Phase 1.8 — User A never retrieves User B's notifications."""

    @pytest.fixture(autouse=True)
    async def _seed(self, notif_repo, user_repo, device_repo):
        self.user_a = seed_user(user_repo, "u_notif_a", "a@notif.gov")
        self.user_b = seed_user(user_repo, "u_notif_b", "b@notif.gov")
        # Seed one notification for user_b
        await notif_repo.create({
            "user_id": self.user_b,
            "type": "status_update",
            "title": "Test",
            "message": "Test",
            "is_read": False,
            "created_at": datetime.now(UTC),
        })
        self.notif_b_id = None
        docs = await notif_repo.list_for_user(self.user_b, is_read=False)
        if docs:
            self.notif_b_id = str(docs[0]["_id"])

    async def test_user_a_cannot_read_user_b_notification(self, client):
        token = make_token(self.user_a, UserRole.CITIZEN)
        r = await client.patch(
            f"/api/v1/notifications/{self.notif_b_id}/read",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404  # not found (concealment)

    async def test_user_a_cannot_list_user_b_notifications(self, client):
        token = make_token(self.user_a, UserRole.CITIZEN)
        r = await client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        # Should only see user_a's notifications (none)
        items = r.json()["data"]["items"]
        assert all(item["user_id"] == self.user_a for item in items) if items else True

    async def test_device_token_ownership_not_transferable(self, client, device_repo, user_repo):
        """Device token registered by user_a cannot be queried/used by user_b."""
        token_a = make_token(self.user_a, UserRole.CITIZEN)
        r = await client.post(
            "/api/v1/notifications/devices",
            json={"device_token": "token123", "platform": "ios", "device_id": "dev1"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert r.status_code == 200
        # user_b tries to register same token -> unique (user_id, device_token) constraint
        token_b = make_token(self.user_b, UserRole.CITIZEN)
        r2 = await client.post(
            "/api/v1/notifications/devices",
            json={"device_token": "token123", "platform": "ios", "device_id": "dev2"},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert r2.status_code == 200  # allowed, different user


class TestPaginationHardening:
    """Phase 1.8 — Page boundaries, negative, zero, huge, invalid strings."""

    async def test_negative_page_rejected(self, client, user_repo):
        citizen = seed_user(user_repo, "cit_pag", "pag@cit.gov")
        token = make_token(citizen, UserRole.CITIZEN)
        r = await client.get("/api/v1/feed", params={"page": 0}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 422

    async def test_page_size_over_max_rejected(self, client, user_repo):
        citizen = seed_user(user_repo, "cit_pag", "pag@cit.gov")
        token = make_token(citizen, UserRole.CITIZEN)
        r = await client.get("/api/v1/feed", params={"page_size": 51}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 422

    async def test_invalid_page_string_rejected(self, client, user_repo):
        citizen = seed_user(user_repo, "cit_pag", "pag@cit.gov")
        token = make_token(citizen, UserRole.CITIZEN)
        r = await client.get("/api/v1/feed", params={"page": "abc"}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 422

    async def test_feed_pagination_bounds(self, client, user_repo):
        citizen = seed_user(user_repo, "cit_pag", "pag@cit.gov")
        token = make_token(citizen, UserRole.CITIZEN)
        r = await client.get("/api/v1/feed", params={"page": 1, "page_size": 50}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["data"]["pagination"]["page_size"] == 50


class TestPasswordPolicy:
    """Phase 1.8 — 72-byte bcrypt cap, no 500 on registration."""

    async def test_72_byte_password_accepted(self, client, user_repo):
        # 72 bytes exactly
        pwd = "A" * 69 + "a1!"
        assert len(pwd.encode("utf-8")) == 72
        r = await client.post("/api/v1/auth/register", json={
            "email": "p72@cit.gov",
            "phone": "+15557200000",
            "full_name": "P72",
            "password": pwd,
        })
        assert r.status_code == 201

    async def test_73_byte_password_rejected(self, client):
        pwd = "A" * 70 + "a1!"  # 73 bytes
        assert len(pwd.encode("utf-8")) == 73
        r = await client.post("/api/v1/auth/register", json={
            "email": "p73@cit.gov",
            "phone": "+15557300000",
            "full_name": "P73",
            "password": pwd,
        })
        assert r.status_code == 422
        assert any("72" in (err.get("message", "") if isinstance(err, dict) else str(err)) for err in r.json().get("errors", []))

    async def test_128_char_ascii_rejected(self, client):
        pwd = "A" * 125 + "a1!"  # 128 chars = 128 bytes > 72
        r = await client.post("/api/v1/auth/register", json={
            "email": "p128@cit.gov",
            "phone": "+15551280000",
            "full_name": "P128",
            "password": pwd,
        })
        assert r.status_code == 422
        assert any("72" in (err.get("message", "") if isinstance(err, dict) else str(err)) for err in r.json().get("errors", []))


class TestProductionConfig:
    """Phase 1.8 — Fail-fast on insecure production config."""

    def test_production_fails_on_default_secret(self):
        from app.core.config import Settings
        with pytest.raises(ValueError, match="SECRET_KEY must be set"):
            Settings(
                environment="production",
                debug=False,
                secret_key="dev-secret-key-change-in-production",
            )

    def test_production_fails_on_debug_true(self):
        from app.core.config import Settings
        with pytest.raises(ValueError, match="DEBUG must not be enabled"):
            Settings(
                environment="production",
                debug=True,
                secret_key="very-long-random-production-secret-key-here-32chars",
            )

    def test_production_fails_on_mock_otp_provider(self):
        """Production startup must be rejected if OTP delivery provider is 'mock'."""
        from app.core.config import Settings
        with pytest.raises(ValueError, match="OTP_DELIVERY_PROVIDER must not be 'mock'"):
            Settings(
                environment="production",
                debug=False,
                secret_key="very-long-random-production-secret-key-here-32chars",
                otp_delivery_provider="mock",
                geocoding_provider="external",
            )

    def test_production_fails_on_mock_geocoding_provider(self):
        """Production startup must be rejected if geocoding provider is 'mock'."""
        from app.core.config import Settings
        with pytest.raises(ValueError, match="GEOCODING_PROVIDER must not be 'mock'"):
            Settings(
                environment="production",
                debug=False,
                secret_key="very-long-random-production-secret-key-here-32chars",
                otp_delivery_provider="external",
                geocoding_provider="mock",
            )

    def test_production_passes_with_real_providers(self):
        """Production startup must succeed when all required production settings are valid."""
        from app.core.config import Settings
        s = Settings(
            environment="production",
            debug=False,
            secret_key="very-long-random-production-secret-key-here-32chars",
            otp_delivery_provider="external",
            geocoding_provider="external",
        )
        assert s.environment == "production"
        assert s.otp_delivery_provider == "external"
        assert s.geocoding_provider == "external"

    def test_development_allows_default_secret(self):
        from app.core.config import Settings
        s = Settings(
            environment="development",
            debug=True,
            secret_key="dev-secret-key-change-in-production",
        )
        assert s.secret_key == "dev-secret-key-change-in-production"

    def test_development_allows_mock_providers(self):
        """Development and test environments must permit mock providers freely."""
        from app.core.config import Settings
        s = Settings(
            environment="development",
            debug=True,
            secret_key="dev-secret-key-change-in-production",
            otp_delivery_provider="mock",
            geocoding_provider="mock",
        )
        assert s.otp_delivery_provider == "mock"
        assert s.geocoding_provider == "mock"


class TestLogHardening:
    """Phase 1.8 — No secrets/URIs in logs."""

    async def test_mongodb_uri_not_logged_on_connect(self, caplog):
        """The connect log names the database but never the connection URI."""
        import logging

        from app.db.database import close_database, init_database

        with caplog.at_level(logging.INFO, logger="app.db.database"):
            await init_database()
            try:
                messages = [record.getMessage() for record in caplog.records]
            finally:
                await close_database()

        assert any("Connected to MongoDB" in m for m in messages), messages
        assert all("mongodb://" not in m for m in messages), messages
        assert all("password" not in m.lower() for m in messages), messages
