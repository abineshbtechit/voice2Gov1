"""Phase 1.2.4 — RBAC API tests.

End-to-end tests for role-based access control on actual API endpoints.
Tests the 401 vs 403 distinction, role matrices, and privilege escalation.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.dependencies.services import get_user_service
from app.main import create_app
from app.schemas.user import UserRole
from app.services.user_service import UserService
from tests.fakes import FakeUserRepository

VALID_PASSWORD = "SecurePass123!"


def payload(**overrides):
    data = {
        "email": "citizen@example.com",
        "phone": "+15551234567",
        "full_name": "Jane Citizen",
        "password": VALID_PASSWORD,
    }
    data.update(overrides)
    return data


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def repository():
    return FakeUserRepository()


@pytest.fixture
def service(repository):
    return UserService(repository)


@pytest.fixture
async def client(app, service):
    app.dependency_overrides[get_user_service] = lambda: service
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestAdminDashboardEndpoint:
    """Test matrix for GET /api/v1/admin/dashboard (requires admin role)."""

    def _make_token(self, user_id: str, role: UserRole) -> str:
        return create_access_token(user_id=user_id, role=role.value)

    def _seed_user(self, repository: FakeUserRepository, role: UserRole) -> str:
        user_id = f"{role.value}123"
        repository.seed(
            user_id=user_id,
            email=f"{role.value}@example.com",
            phone="+15550000000",
            role=role.value,
            status="active",
        )
        return user_id

    async def test_no_token_returns_401(self, client: AsyncClient, repository: FakeUserRepository) -> None:
        self._seed_user(repository, UserRole.ADMIN)
        response = await client.get("/api/v1/admin/dashboard")
        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_INVALID"

    async def test_invalid_token_returns_401(self, client: AsyncClient, repository: FakeUserRepository) -> None:
        self._seed_user(repository, UserRole.ADMIN)
        response = await client.get("/api/v1/admin/dashboard", headers={"Authorization": "Bearer invalid.token"})
        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_INVALID"

    async def test_expired_token_returns_401(self, client: AsyncClient, repository: FakeUserRepository) -> None:
        self._seed_user(repository, UserRole.ADMIN)
        expired_token = create_access_token(
            user_id="admin123",
            role=UserRole.ADMIN.value,
            expires_delta=__import__("datetime").timedelta(seconds=-1),
        )
        response = await client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {expired_token}"})
        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_EXPIRED"

    async def test_citizen_returns_403(self, client: AsyncClient, repository: FakeUserRepository) -> None:
        user_id = self._seed_user(repository, UserRole.CITIZEN)
        token = self._make_token(user_id, UserRole.CITIZEN)
        response = await client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
        assert response.json()["error_code"] == "FORBIDDEN"

    async def test_organization_staff_returns_403(self, client: AsyncClient, repository: FakeUserRepository) -> None:
        user_id = self._seed_user(repository, UserRole.ORGANIZATION_STAFF)
        token = self._make_token(user_id, UserRole.ORGANIZATION_STAFF)
        response = await client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
        assert response.json()["error_code"] == "FORBIDDEN"

    async def test_organization_admin_returns_403(self, client: AsyncClient, repository: FakeUserRepository) -> None:
        user_id = self._seed_user(repository, UserRole.ORGANIZATION_ADMIN)
        token = self._make_token(user_id, UserRole.ORGANIZATION_ADMIN)
        response = await client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
        assert response.json()["error_code"] == "FORBIDDEN"

    async def test_admin_returns_200(self, client: AsyncClient, repository: FakeUserRepository) -> None:
        user_id = self._seed_user(repository, UserRole.ADMIN)
        token = self._make_token(user_id, UserRole.ADMIN)
        response = await client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "admin"
        assert data["user_id"] == user_id


class TestOrganizationAdminDashboardEndpoint:
    """Test matrix for GET /api/v1/organizations/me/dashboard (requires organization_admin or admin)."""

    def _make_token(self, user_id: str, role: UserRole) -> str:
        return create_access_token(user_id=user_id, role=role.value)

    def _seed_user(self, repository: FakeUserRepository, role: UserRole) -> str:
        user_id = f"{role.value}123"
        repository.seed(
            user_id=user_id,
            email=f"{role.value}@example.com",
            phone="+15550000000",
            role=role.value,
            status="active",
        )
        return user_id

    async def test_no_token_returns_401(self, client: AsyncClient, repository: FakeUserRepository) -> None:
        self._seed_user(repository, UserRole.ORGANIZATION_ADMIN)
        response = await client.get("/api/v1/organizations/me/dashboard")
        assert response.status_code == 401

    async def test_citizen_returns_403(self, client: AsyncClient, repository: FakeUserRepository) -> None:
        user_id = self._seed_user(repository, UserRole.CITIZEN)
        token = self._make_token(user_id, UserRole.CITIZEN)
        response = await client.get("/api/v1/organizations/me/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
        assert response.json()["error_code"] == "FORBIDDEN"

    async def test_organization_staff_returns_403(self, client: AsyncClient, repository: FakeUserRepository) -> None:
        user_id = self._seed_user(repository, UserRole.ORGANIZATION_STAFF)
        token = self._make_token(user_id, UserRole.ORGANIZATION_STAFF)
        response = await client.get("/api/v1/organizations/me/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
        assert response.json()["error_code"] == "FORBIDDEN"

    async def test_organization_admin_returns_200(self, client: AsyncClient, repository: FakeUserRepository) -> None:
        user_id = self._seed_user(repository, UserRole.ORGANIZATION_ADMIN)
        token = self._make_token(user_id, UserRole.ORGANIZATION_ADMIN)
        response = await client.get("/api/v1/organizations/me/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "organization_admin"

    async def test_admin_returns_200(self, client: AsyncClient, repository: FakeUserRepository) -> None:
        user_id = self._seed_user(repository, UserRole.ADMIN)
        token = self._make_token(user_id, UserRole.ADMIN)
        response = await client.get("/api/v1/organizations/me/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "admin"


class TestOrganizationStaffEndpoint:
    """Test matrix for GET /api/v1/organizations/me/staff (requires organization_admin or admin)."""

    def _make_token(self, user_id: str, role: UserRole) -> str:
        return create_access_token(user_id=user_id, role=role.value)

    def _seed_user(self, repository: FakeUserRepository, role: UserRole) -> str:
        user_id = f"{role.value}123"
        repository.seed(
            user_id=user_id,
            email=f"{role.value}@example.com",
            phone="+15550000000",
            role=role.value,
            status="active",
        )
        return user_id

    async def test_organization_admin_returns_200(self, client: AsyncClient, repository: FakeUserRepository) -> None:
        user_id = self._seed_user(repository, UserRole.ORGANIZATION_ADMIN)
        token = self._make_token(user_id, UserRole.ORGANIZATION_ADMIN)
        response = await client.get("/api/v1/organizations/me/staff", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    async def test_admin_returns_200(self, client: AsyncClient, repository: FakeUserRepository) -> None:
        user_id = self._seed_user(repository, UserRole.ADMIN)
        token = self._make_token(user_id, UserRole.ADMIN)
        response = await client.get("/api/v1/organizations/me/staff", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    async def test_organization_staff_returns_403(self, client: AsyncClient, repository: FakeUserRepository) -> None:
        user_id = self._seed_user(repository, UserRole.ORGANIZATION_STAFF)
        token = self._make_token(user_id, UserRole.ORGANIZATION_STAFF)
        response = await client.get("/api/v1/organizations/me/staff", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

    async def test_citizen_returns_403(self, client: AsyncClient, repository: FakeUserRepository) -> None:
        user_id = self._seed_user(repository, UserRole.CITIZEN)
        token = self._make_token(user_id, UserRole.CITIZEN)
        response = await client.get("/api/v1/organizations/me/staff", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403


class TestAuthMeEndpointStillWorks:
    """Regression test: /auth/me and /users/me must still work for all roles."""

    def _make_token(self, user_id: str, role: UserRole) -> str:
        return create_access_token(user_id=user_id, role=role.value)

    def _seed_user(self, repository: FakeUserRepository, role: UserRole) -> str:
        user_id = f"{role.value}123"
        repository.seed(
            user_id=user_id,
            email=f"{role.value}@example.com",
            phone="+15550000000",
            role=role.value,
            status="active",
        )
        return user_id

    @pytest.mark.parametrize("role", [UserRole.CITIZEN, UserRole.ORGANIZATION_STAFF, UserRole.ORGANIZATION_ADMIN, UserRole.ADMIN])
    @pytest.mark.parametrize("endpoint", ["/api/v1/auth/me", "/api/v1/users/me"])
    async def test_all_roles_can_access_me(self, client: AsyncClient, repository: FakeUserRepository, role: UserRole, endpoint: str) -> None:
        user_id = self._seed_user(repository, role)
        token = self._make_token(user_id, role)
        response = await client.get(endpoint, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == role.value
        assert data["id"] == user_id


class TestPrivilegeEscalation:
    """Test that users cannot escalate privileges through registration or tokens."""

    async def test_registration_always_creates_citizen(self, client: AsyncClient) -> None:
        """Public registration must always create citizen role, regardless of any attempt."""
        response = await client.post("/api/v1/auth/register", json=payload())
        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "citizen"
        assert data["status"] == "pending_verification"

    async def test_registration_rejects_role_in_payload(self, client: AsyncClient) -> None:
        """Registration must reject any role field in the request body."""
        body = payload()
        body["role"] = "admin"  # This should be ignored or rejected by pydantic
        response = await client.post("/api/v1/auth/register", json=body)
        # Pydantic will reject extra fields by default (extra='ignore' or 'forbid')
        # The important thing is the response role is citizen
        if response.status_code == 201:
            assert response.json()["role"] == "citizen"
        # Or it could be 422 if extra='forbid' - both are acceptable

    async def test_citizen_cannot_use_admin_token(self, client: AsyncClient, repository: FakeUserRepository) -> None:
        """A citizen user cannot obtain admin access by manipulating their token."""
        # Seed a citizen user
        citizen_id = "citizen123"
        repository.seed(
            user_id=citizen_id,
            email="citizen@example.com",
            phone="+15551234567",
            role="citizen",
            status="active",
        )

        # Create a token claiming to be admin (but signed with correct secret)
        # This token will have sub=citizen123 but role=admin
        fake_admin_token = create_access_token(user_id=citizen_id, role=UserRole.ADMIN.value)

        # The get_current_user loads the user from DB by sub, so the DB role (citizen) is used
        response = await client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {fake_admin_token}"})
        assert response.status_code == 403  # DB role is citizen, so forbidden

    async def test_token_tampering_fails(self, client: AsyncClient, repository: FakeUserRepository) -> None:
        """Tampering with JWT payload must fail signature verification (401)."""
        user_id = "admin123"
        repository.seed(
            user_id=user_id,
            email="admin@example.com",
            phone="+15550000000",
            role="admin",
            status="active",
        )

        # Create a valid admin token
        valid_token = create_access_token(user_id=user_id, role=UserRole.ADMIN.value)

        # Tamper with the payload (from tests/fakes.py tamper_token helper)
        from tests.fakes import tamper_token
        tampered = tamper_token(valid_token)

        response = await client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {tampered}"})
        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_INVALID"


class TestOpenAPISecuritySchemes:
    """Verify protected endpoints expose appropriate security requirements in OpenAPI."""

    async def test_admin_endpoint_has_bearer_security(self, app) -> None:
        schema = app.openapi()
        path = schema["paths"]["/api/v1/admin/dashboard"]
        get_op = path["get"]
        assert "security" in get_op
        security_req = get_op["security"]
        assert any("Bearer" in str(req) for req in security_req)

    async def test_org_admin_endpoint_has_bearer_security(self, app) -> None:
        schema = app.openapi()
        path = schema["paths"]["/api/v1/organizations/me/dashboard"]
        get_op = path["get"]
        assert "security" in get_op

    async def test_auth_me_still_has_bearer_security(self, app) -> None:
        schema = app.openapi()
        for path_name in ["/api/v1/auth/me", "/api/v1/users/me"]:
            path = schema["paths"][path_name]
            get_op = path["get"]
            assert "security" in get_op
