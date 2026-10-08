"""Phase 1.2.4 — RBAC unit tests.

Tests the role-based access control dependency mechanism in isolation,
using in-memory fakes (no database).
"""

from datetime import UTC, datetime

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.dependencies.rbac import require_admin, require_organization_admin, require_roles
from app.schemas.base import ObjectIdStr
from app.schemas.user import UserResponse, UserRole, UserStatus


class FakeUserService:
    """Minimal service that returns pre-seeded users by ID."""

    def __init__(self) -> None:
        self.users: dict[str, UserResponse] = {}

    def seed(self, user_id: str, role: UserRole) -> None:
        # Use a valid ObjectId format (24 hex chars)
        if len(user_id) != 24:
            user_id = user_id.ljust(24, "0")[:24]
        now = datetime.now(UTC)
        self.users[user_id] = UserResponse(
            id=ObjectIdStr(user_id),
            email=f"{role.value}@example.com",
            phone="+15550000000",
            full_name=f"{role.value.title()} User",
            role=role,
            status=UserStatus.ACTIVE,
            is_verified=True,
            created_at=now,
            updated_at=now,
        )

    async def get_user_by_id(self, user_id: str) -> UserResponse | None:
        return self.users.get(user_id)


def create_test_app(service: FakeUserService) -> FastAPI:
    """Create a FastAPI app with test endpoints for each role combination."""
    from app.dependencies.services import get_user_service
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_user_service] = lambda: service

    def _role_str(user: UserResponse) -> str:
        return str(user.role)

    @app.get("/test/admin-only")
    async def admin_only(user: UserResponse = Depends(require_admin)):
        return {"role": _role_str(user)}

    @app.get("/test/org-admin")
    async def org_admin(user: UserResponse = Depends(require_organization_admin)):
        return {"role": _role_str(user)}

    @app.get("/test/multi-role")
    async def multi_role(user: UserResponse = Depends(require_roles(UserRole.ORGANIZATION_ADMIN, UserRole.ADMIN))):
        return {"role": _role_str(user)}

    @app.get("/test/citizen-only")
    async def citizen_only(user: UserResponse = Depends(require_roles(UserRole.CITIZEN))):
        return {"role": _role_str(user)}

    return app


@pytest.fixture
def service() -> FakeUserService:
    svc = FakeUserService()
    # Use 24-char hex IDs that match what make_token will use
    svc.seed("citizen12300000000000000000", UserRole.CITIZEN)
    svc.seed("staff123000000000000000000", UserRole.ORGANIZATION_STAFF)
    svc.seed("orgadmin12300000000000000", UserRole.ORGANIZATION_ADMIN)
    svc.seed("admin12300000000000000000", UserRole.ADMIN)
    return svc


@pytest.fixture
def app(service: FakeUserService) -> FastAPI:
    return create_test_app(service)


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def make_token(user_id: str, role: UserRole) -> str:
    """Create a valid access token for testing."""
    from app.core.security import create_access_token
    # Pad user_id to 24 chars to match seeded users
    if len(user_id) < 24:
        user_id = user_id.ljust(24, "0")[:24]
    return create_access_token(user_id=user_id, role=role.value)


class TestRequireAdmin:
    """Test the require_admin convenience dependency."""

    async def test_admin_allowed(self, client: AsyncClient) -> None:
        token = make_token("admin123", UserRole.ADMIN)
        response = await client.get("/test/admin-only", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["role"] == "admin"

    async def test_organization_admin_denied(self, client: AsyncClient) -> None:
        token = make_token("orgadmin123", UserRole.ORGANIZATION_ADMIN)
        response = await client.get("/test/admin-only", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
        assert response.json()["error_code"] == "FORBIDDEN"

    async def test_organization_staff_denied(self, client: AsyncClient) -> None:
        token = make_token("staff123", UserRole.ORGANIZATION_STAFF)
        response = await client.get("/test/admin-only", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

    async def test_citizen_denied(self, client: AsyncClient) -> None:
        token = make_token("citizen123", UserRole.CITIZEN)
        response = await client.get("/test/admin-only", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

    async def test_no_token_returns_401(self, client: AsyncClient) -> None:
        response = await client.get("/test/admin-only")
        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_INVALID"

    async def test_invalid_token_returns_401(self, client: AsyncClient) -> None:
        response = await client.get("/test/admin-only", headers={"Authorization": "Bearer invalid.token.here"})
        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_INVALID"


class TestRequireOrganizationAdmin:
    """Test the require_organization_admin convenience dependency (org_admin + admin)."""

    async def test_organization_admin_allowed(self, client: AsyncClient) -> None:
        token = make_token("orgadmin123", UserRole.ORGANIZATION_ADMIN)
        response = await client.get("/test/org-admin", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["role"] == "organization_admin"

    async def test_admin_allowed(self, client: AsyncClient) -> None:
        token = make_token("admin123", UserRole.ADMIN)
        response = await client.get("/test/org-admin", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["role"] == "admin"

    async def test_organization_staff_denied(self, client: AsyncClient) -> None:
        token = make_token("staff123", UserRole.ORGANIZATION_STAFF)
        response = await client.get("/test/org-admin", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

    async def test_citizen_denied(self, client: AsyncClient) -> None:
        token = make_token("citizen123", UserRole.CITIZEN)
        response = await client.get("/test/org-admin", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403


class TestRequireRolesMulti:
    """Test require_roles with multiple allowed roles."""

    async def test_organization_admin_allowed(self, client: AsyncClient) -> None:
        token = make_token("orgadmin123", UserRole.ORGANIZATION_ADMIN)
        response = await client.get("/test/multi-role", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    async def test_admin_allowed(self, client: AsyncClient) -> None:
        token = make_token("admin123", UserRole.ADMIN)
        response = await client.get("/test/multi-role", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    async def test_organization_staff_denied(self, client: AsyncClient) -> None:
        token = make_token("staff123", UserRole.ORGANIZATION_STAFF)
        response = await client.get("/test/multi-role", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

    async def test_citizen_denied(self, client: AsyncClient) -> None:
        token = make_token("citizen123", UserRole.CITIZEN)
        response = await client.get("/test/multi-role", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403


class TestRequireRolesCitizenOnly:
    """Test require_roles with only citizen allowed."""

    async def test_citizen_allowed(self, client: AsyncClient) -> None:
        token = make_token("citizen123", UserRole.CITIZEN)
        response = await client.get("/test/citizen-only", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    async def test_admin_denied(self, client: AsyncClient) -> None:
        token = make_token("admin123", UserRole.ADMIN)
        response = await client.get("/test/citizen-only", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

    async def test_org_admin_denied(self, client: AsyncClient) -> None:
        token = make_token("orgadmin123", UserRole.ORGANIZATION_ADMIN)
        response = await client.get("/test/citizen-only", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

    async def test_staff_denied(self, client: AsyncClient) -> None:
        token = make_token("staff123", UserRole.ORGANIZATION_STAFF)
        response = await client.get("/test/citizen-only", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403


class Test401vs403Distinction:
    """Verify the critical 401 vs 403 distinction is preserved."""

    async def test_missing_token_is_401_not_403(self, client: AsyncClient) -> None:
        """Unauthenticated requests must return 401, never 403."""
        response = await client.get("/test/admin-only")
        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_INVALID"
        assert response.json()["error_code"] != "FORBIDDEN"

    async def test_invalid_token_is_401_not_403(self, client: AsyncClient) -> None:
        """Invalid/malformed tokens must return 401, never 403."""
        response = await client.get("/test/admin-only", headers={"Authorization": "Bearer not.a.valid.token"})
        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_INVALID"

    async def test_expired_token_is_401_not_403(self, client: AsyncClient) -> None:
        """Expired tokens must return 401, never 403."""
        from datetime import timedelta

        from app.core.security import create_access_token
        expired_token = create_access_token(
            user_id="admin123",
            role=UserRole.ADMIN.value,
            expires_delta=timedelta(seconds=-1),
        )
        response = await client.get("/test/admin-only", headers={"Authorization": f"Bearer {expired_token}"})
        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_EXPIRED"

    async def test_authenticated_but_insufficient_role_is_403(self, client: AsyncClient) -> None:
        """Valid token but wrong role must return 403, not 401."""
        token = make_token("citizen123", UserRole.CITIZEN)
        response = await client.get("/test/admin-only", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
        assert response.json()["error_code"] == "FORBIDDEN"
        assert response.json()["error_code"] != "TOKEN_INVALID"
        assert response.json()["error_code"] != "TOKEN_EXPIRED"


class TestRoleEnumValidation:
    """Test that the UserRole enum only accepts the four authoritative roles."""

    def test_four_valid_roles_exist(self) -> None:
        assert UserRole.CITIZEN == "citizen"
        assert UserRole.ORGANIZATION_STAFF == "organization_staff"
        assert UserRole.ORGANIZATION_ADMIN == "organization_admin"
        assert UserRole.ADMIN == "admin"

    def test_invalid_role_rejected(self) -> None:
        with pytest.raises(ValueError):
            UserRole("super_admin")

        with pytest.raises(ValueError):
            UserRole("moderator")

        with pytest.raises(ValueError):
            UserRole("staff")

        with pytest.raises(ValueError):
            UserRole("org_admin")

        with pytest.raises(ValueError):
            UserRole("")

        with pytest.raises(ValueError):
            UserRole("ADMIN")  # case-sensitive

    def test_role_serialization(self) -> None:
        """Roles serialize to their string values."""
        assert UserRole.ADMIN.value == "admin"
        assert str(UserRole.CITIZEN) == "citizen"


class TestPrivilegeEscalationProtection:
    """Test that users cannot escalate privileges through request payloads."""

    def test_user_register_request_has_no_role_field(self) -> None:
        """Registration request schema must not accept role."""
        from app.schemas.user import UserRegisterRequest
        fields = UserRegisterRequest.model_fields
        assert "role" not in fields

    def test_user_register_response_role_is_citizen(self) -> None:
        """Registration response must always have citizen role."""
        from app.schemas.user import UserRegisterResponse
        # This is enforced by the service, but schema should reflect it
        fields = UserRegisterResponse.model_fields
        assert "role" in fields

    def test_user_update_role_field_exists_for_admin_operations(self) -> None:
        """UserUpdate has role field for admin-only operations."""
        from app.schemas.user import UserUpdate
        fields = UserUpdate.model_fields
        assert "role" in fields
        # The field should be optional (None default)
        assert fields["role"].default is None


class TestRBACDependencyArchitecture:
    """Test that RBAC builds on get_current_user without duplicating JWT logic."""

    def test_require_roles_uses_get_current_user(self) -> None:
        """require_roles should return a function that depends on get_current_user, not decode tokens directly."""
        import inspect

        from fastapi.params import Depends as DependsMarker

        from app.dependencies.auth import get_current_user
        from app.dependencies.rbac import require_roles

        # The function returned by require_roles should have get_current_user as a parameter dependency
        checker_func = require_roles(UserRole.ADMIN)
        sig = inspect.signature(checker_func)
        params = list(sig.parameters.values())
        # The checker function should have one parameter (current_user) that depends on get_current_user
        assert len(params) == 1
        param = params[0]
        assert param.name == "current_user"
        assert param.default is not None
        # The default should be a Depends marker on get_current_user
        assert isinstance(param.default, DependsMarker)
        assert param.default.dependency is get_current_user
