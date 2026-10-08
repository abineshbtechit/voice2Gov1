"""Phase 1.2.5 — Tenant isolation unit tests.

Tests the organization-scoped tenant isolation dependency mechanism in isolation,
using in-memory fakes (no database).
"""

from datetime import UTC, datetime

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.dependencies.tenant import (
    get_current_organization,
    require_organization_context,
    require_same_organization,
)
from app.schemas.base import ObjectIdStr
from app.schemas.user import UserResponse, UserRole, UserStatus


class FakeUserService:
    """Minimal service that returns pre-seeded users by ID."""

    def __init__(self) -> None:
        self.users: dict[str, UserResponse] = {}

    def seed(self, user_id: str, role: UserRole, organization_id: str | None = None, department_id: str | None = None) -> None:
        # Use a valid ObjectId format (24 hex chars)
        if len(user_id) < 24:
            user_id = user_id.ljust(24, "0")[:24]
        now = datetime.now(UTC)
        self.users[user_id] = UserResponse(
            id=ObjectIdStr(user_id),
            email=f"{role.value}@example.com",
            phone="+15550000000",
            full_name=f"{role.value.title()} User",
            role=role,
            status=UserStatus.ACTIVE,
            organization_id=ObjectIdStr(organization_id) if organization_id else None,
            department_id=ObjectIdStr(department_id) if department_id else None,
            is_verified=True,
            created_at=now,
            updated_at=now,
        )

    async def get_user_by_id(self, user_id: str) -> UserResponse | None:
        return self.users.get(user_id)


def create_test_app(service: FakeUserService) -> FastAPI:
    """Create a FastAPI app with test endpoints for tenant isolation."""
    from app.dependencies.services import get_user_service
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_user_service] = lambda: service

    @app.get("/test/org-context")
    async def org_context(org_id: str = Depends(require_organization_context)):
        return {"organization_id": org_id}

    @app.get("/test/same-org/{resource_org_id}")
    async def same_org(
        resource_org_id: str,
        user: UserResponse = Depends(require_same_organization),
    ):
        return {"user_org": str(user.organization_id), "resource_org": resource_org_id}

    @app.get("/test/current-org")
    async def current_org(org_id: str | None = Depends(get_current_organization)):
        return {"organization_id": org_id}

    return app


@pytest.fixture
def service() -> FakeUserService:
    svc = FakeUserService()
    # ORG_A users
    svc.seed("citizenA000000000000000000", UserRole.CITIZEN)
    svc.seed("staffA00000000000000000000", UserRole.ORGANIZATION_STAFF, organization_id="orgA0000000000000000000000")
    svc.seed("orgAdminA00000000000000000", UserRole.ORGANIZATION_ADMIN, organization_id="orgA0000000000000000000000")
    # ORG_B users
    svc.seed("citizenB000000000000000000", UserRole.CITIZEN)
    svc.seed("staffB00000000000000000000", UserRole.ORGANIZATION_STAFF, organization_id="orgB0000000000000000000000")
    svc.seed("orgAdminB00000000000000000", UserRole.ORGANIZATION_ADMIN, organization_id="orgB0000000000000000000000")
    # Admin
    svc.seed("admin000000000000000000000", UserRole.ADMIN)
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
    if len(user_id) < 24:
        user_id = user_id.ljust(24, "0")[:24]
    return create_access_token(user_id=user_id, role=role.value)


class TestGetCurrentOrganization:
    """Test the get_current_organization dependency."""

    async def test_org_staff_returns_org_id(self, client: AsyncClient) -> None:
        token = make_token("staffA00000000000000000000", UserRole.ORGANIZATION_STAFF)
        response = await client.get("/test/current-org", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["organization_id"] == "orgA0000000000000000000000"

    async def test_org_admin_returns_org_id(self, client: AsyncClient) -> None:
        token = make_token("orgAdminA00000000000000000", UserRole.ORGANIZATION_ADMIN)
        response = await client.get("/test/current-org", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["organization_id"] == "orgA0000000000000000000000"

    async def test_citizen_returns_none(self, client: AsyncClient) -> None:
        token = make_token("citizenA000000000000000000", UserRole.CITIZEN)
        response = await client.get("/test/current-org", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["organization_id"] is None

    async def test_admin_returns_none(self, client: AsyncClient) -> None:
        token = make_token("admin000000000000000000000", UserRole.ADMIN)
        response = await client.get("/test/current-org", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["organization_id"] is None

    async def test_no_token_returns_401(self, client: AsyncClient) -> None:
        response = await client.get("/test/current-org")
        assert response.status_code == 401


class TestRequireOrganizationContext:
    """Test the require_organization_context dependency."""

    async def test_org_staff_returns_org_id(self, client: AsyncClient) -> None:
        token = make_token("staffA00000000000000000000", UserRole.ORGANIZATION_STAFF)
        response = await client.get("/test/org-context", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["organization_id"] == "orgA0000000000000000000000"

    async def test_org_admin_returns_org_id(self, client: AsyncClient) -> None:
        token = make_token("orgAdminA00000000000000000", UserRole.ORGANIZATION_ADMIN)
        response = await client.get("/test/org-context", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["organization_id"] == "orgA0000000000000000000000"

    async def test_citizen_returns_403(self, client: AsyncClient) -> None:
        token = make_token("citizenA000000000000000000", UserRole.CITIZEN)
        response = await client.get("/test/org-context", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
        assert response.json()["error_code"] == "FORBIDDEN"

    async def test_admin_returns_403(self, client: AsyncClient) -> None:
        """Admin should get 403 because they have global access, not org-scoped."""
        token = make_token("admin000000000000000000000", UserRole.ADMIN)
        response = await client.get("/test/org-context", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
        assert response.json()["error_code"] == "FORBIDDEN"

    async def test_staff_without_org_returns_403(self, client: AsyncClient, service: FakeUserService) -> None:
        # Seed staff without organization_id
        svc = service
        svc.seed("staffNoOrg000000000000000", UserRole.ORGANIZATION_STAFF, organization_id=None)
        token = make_token("staffNoOrg000000000000000", UserRole.ORGANIZATION_STAFF)
        response = await client.get("/test/org-context", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403


class TestRequireSameOrganization:
    """Test the require_same_organization dependency."""

    async def test_same_org_allowed(self, client: AsyncClient) -> None:
        token = make_token("staffA00000000000000000000", UserRole.ORGANIZATION_STAFF)
        response = await client.get(
            "/test/same-org/orgA0000000000000000000000",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    async def test_different_org_denied(self, client: AsyncClient) -> None:
        token = make_token("staffA00000000000000000000", UserRole.ORGANIZATION_STAFF)
        response = await client.get(
            "/test/same-org/orgB0000000000000000000000",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403
        assert response.json()["error_code"] == "FORBIDDEN"

    async def test_admin_bypasses_check(self, client: AsyncClient) -> None:
        token = make_token("admin000000000000000000000", UserRole.ADMIN)
        response = await client.get(
            "/test/same-org/orgB0000000000000000000000",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    async def test_citizen_denied(self, client: AsyncClient) -> None:
        token = make_token("citizenA000000000000000000", UserRole.CITIZEN)
        response = await client.get(
            "/test/same-org/orgA0000000000000000000000",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403

    async def test_staff_no_org_denied(self, client: AsyncClient, service: FakeUserService) -> None:
        svc = service
        svc.seed("staffNoOrg000000000000000", UserRole.ORGANIZATION_STAFF, organization_id=None)
        token = make_token("staffNoOrg000000000000000", UserRole.ORGANIZATION_STAFF)
        response = await client.get(
            "/test/same-org/orgA0000000000000000000000",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403


class TestTenantIsolationArchitecture:
    """Test that tenant isolation builds on get_current_user without duplicating auth logic."""

    def test_dependencies_use_get_current_user(self) -> None:
        import inspect

        from fastapi.params import Depends as DependsMarker

        from app.dependencies.auth import get_current_user
        from app.dependencies.tenant import (
            get_current_organization,
            require_organization_context,
            require_same_organization,
        )

        for dep_func in [get_current_organization, require_organization_context]:
            sig = inspect.signature(dep_func)
            params = list(sig.parameters.values())
            assert len(params) == 1
            param = params[0]
            assert param.default is not None
            assert isinstance(param.default, DependsMarker)
            assert param.default.dependency is get_current_user

        # require_same_organization has 2 params (resource_org_id + current_user)
        sig = inspect.signature(require_same_organization)
        params = list(sig.parameters.values())
        assert len(params) == 2
        # Second param should be current_user with Depends on get_current_user
        current_user_param = params[1]
        assert current_user_param.default is not None
        assert isinstance(current_user_param.default, DependsMarker)
        assert current_user_param.default.dependency is get_current_user
