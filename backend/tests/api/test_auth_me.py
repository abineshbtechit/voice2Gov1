"""Phase 1.2.2 — protected ``/me`` endpoint API tests.

The authoritative API SRS (``docs/api-contract.md``) documents both
``GET /auth/me`` and ``GET /users/me`` as "current user profile" behind a
Bearer token, so both routes are implemented and exercised here. The real
``get_current_user`` dependency runs; only the user service is faked.
"""

from datetime import timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.dependencies.services import get_user_service
from app.main import create_app
from app.services.user_service import UserService
from tests.fakes import FakeUserRepository, tamper_token

USER_ID = "507f1f77bcf86cd799439011"
ME_PATHS = ("/api/v1/users/me", "/api/v1/auth/me")


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def repository() -> FakeUserRepository:
    repo = FakeUserRepository()
    repo.seed(USER_ID, role="citizen")
    return repo


@pytest_asyncio.fixture
async def client(app, repository: FakeUserRepository):
    app.dependency_overrides[get_user_service] = lambda: UserService(repository)  # type: ignore[arg-type]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.parametrize("path", ME_PATHS)
class TestProtectedMe:
    async def test_valid_token_succeeds(self, client: AsyncClient, path: str) -> None:
        token = create_access_token(USER_ID, role="citizen")

        response = await client.get(path, headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == USER_ID
        assert data["email"] == "citizen@example.com"
        assert data["role"] == "citizen"

    async def test_response_excludes_credentials(self, client: AsyncClient, path: str) -> None:
        token = create_access_token(USER_ID)

        response = await client.get(path, headers={"Authorization": f"Bearer {token}"})

        body = response.text.lower()
        assert "password" not in body
        assert "$2b$" not in body

    async def test_missing_token_returns_401(self, client: AsyncClient, path: str) -> None:
        response = await client.get(path)

        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_INVALID"

    async def test_invalid_token_returns_401(self, client: AsyncClient, path: str) -> None:
        response = await client.get(path, headers={"Authorization": "Bearer not-a-jwt"})

        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_INVALID"

    async def test_expired_token_returns_401(self, client: AsyncClient, path: str) -> None:
        token = create_access_token(USER_ID, expires_delta=timedelta(seconds=-5))

        response = await client.get(path, headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_EXPIRED"

    async def test_tampered_token_returns_401(self, client: AsyncClient, path: str) -> None:
        tampered = tamper_token(create_access_token(USER_ID))

        response = await client.get(path, headers={"Authorization": f"Bearer {tampered}"})

        assert response.status_code == 401

    async def test_nonexistent_user_returns_401(self, client: AsyncClient, path: str) -> None:
        token = create_access_token("0000000000000000000000ff")

        response = await client.get(path, headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 401


class TestMalformedAuthorization:
    @pytest.mark.parametrize(
        "header",
        [
            "NotBearer abc.def.ghi",
            "Basic dXNlcjpwYXNz",
            "Bearer",
            "Bearer ",
            "bearer",
            "abc.def.ghi",
        ],
    )
    async def test_malformed_header_returns_401(self, client: AsyncClient, header: str) -> None:
        response = await client.get("/api/v1/users/me", headers={"Authorization": header})

        assert response.status_code == 401
        body = response.json()
        assert body["success"] is False
        assert body["error_code"] in {"TOKEN_INVALID", "TOKEN_EXPIRED"}

    async def test_error_body_has_no_secrets(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer not-a-jwt"}
        )

        body = response.text
        assert "$2b$" not in body
        assert "password_hash" not in body
        assert "secret" not in body.lower()


class TestPhase121RegistrationStillWorks:
    async def test_register_still_returns_201(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "new-citizen@example.com",
                "phone": "+15559998888",
                "full_name": "New Citizen",
                "password": "SecurePass123!",
            },
        )

        assert response.status_code == 201
        assert response.json()["email"] == "new-citizen@example.com"


class TestScope:
    def test_login_endpoint_exists(self, app) -> None:
        paths = set(app.openapi()["paths"])
        assert "/api/v1/auth/login" in paths
        assert "/api/v1/auth/me" in paths
        assert "/api/v1/users/me" in paths
