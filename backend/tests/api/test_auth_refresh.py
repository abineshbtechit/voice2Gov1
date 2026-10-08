"""Phase 1.2.3 — POST /api/v1/auth/refresh API tests."""

from datetime import timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token, create_refresh_token
from app.dependencies.services import get_refresh_token_service, get_user_service
from app.main import create_app
from app.services.token_service import RefreshTokenService
from app.services.user_service import UserService
from tests.fakes import FakeRefreshTokenRepository, FakeUserRepository, tamper_token

USER_ID = "507f1f77bcf86cd799439011"


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def user_repository() -> FakeUserRepository:
    repo = FakeUserRepository()
    repo.seed(USER_ID, role="citizen")
    return repo


@pytest.fixture
def token_repository() -> FakeRefreshTokenRepository:
    return FakeRefreshTokenRepository()


@pytest.fixture
def token_service(
    token_repository: FakeRefreshTokenRepository, user_repository: FakeUserRepository
) -> RefreshTokenService:
    return RefreshTokenService(token_repository, UserService(user_repository))  # type: ignore[arg-type]


@pytest_asyncio.fixture
async def client(app, token_service: RefreshTokenService, user_repository: FakeUserRepository):
    app.dependency_overrides[get_refresh_token_service] = lambda: token_service
    app.dependency_overrides[get_user_service] = lambda: UserService(user_repository)  # type: ignore[arg-type]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestRefreshSuccess:
    async def test_valid_refresh_returns_token_pair(
        self, client: AsyncClient, token_service: RefreshTokenService
    ) -> None:
        issued = await token_service.issue_token_pair(USER_ID, role="citizen")

        response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": issued.refresh_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["refresh_token"] != issued.refresh_token

    async def test_new_access_token_authenticates(
        self, client: AsyncClient, token_service: RefreshTokenService
    ) -> None:
        issued = await token_service.issue_token_pair(USER_ID, role="citizen")

        refreshed = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": issued.refresh_token}
        )
        new_access = refreshed.json()["access_token"]

        me = await client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {new_access}"}
        )

        assert me.status_code == 200
        assert me.json()["id"] == USER_ID

    async def test_response_leaks_nothing(
        self, client: AsyncClient, token_service: RefreshTokenService
    ) -> None:
        issued = await token_service.issue_token_pair(USER_ID)

        response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": issued.refresh_token}
        )

        body = response.text.lower()
        assert "password" not in body
        assert "$2b$" not in body
        assert "token_hash" not in body
        assert "family_id" not in body
        assert "revoked_at" not in body


class TestRefreshFailures:
    async def test_missing_body_field_returns_422(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/auth/refresh", json={})

        assert response.status_code == 422
        assert response.json()["success"] is False

    async def test_malformed_token_returns_401(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": "not-a-jwt"}
        )

        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_INVALID"

    async def test_tampered_token_returns_401(
        self, client: AsyncClient, token_service: RefreshTokenService
    ) -> None:
        issued = await token_service.issue_token_pair(USER_ID)

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tamper_token(issued.refresh_token)},
        )

        assert response.status_code == 401

    async def test_expired_token_returns_401(self, client: AsyncClient) -> None:
        expired = create_refresh_token(USER_ID, jti="a" * 32, expires_delta=timedelta(seconds=-5))

        response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": expired}
        )

        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_EXPIRED"

    async def test_access_token_returns_401(self, client: AsyncClient) -> None:
        access = create_access_token(USER_ID, role="citizen")

        response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": access}
        )

        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_INVALID"

    async def test_nonexistent_user_returns_401(
        self, client: AsyncClient, token_service: RefreshTokenService
    ) -> None:
        issued = await token_service.issue_token_pair("0000000000000000000000ff")

        response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": issued.refresh_token}
        )

        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_INVALID"

    async def test_unknown_token_returns_401(self, client: AsyncClient) -> None:
        # Valid signature, but never issued/stored.
        stray = create_refresh_token(USER_ID, jti="b" * 32)

        response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": stray}
        )

        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_INVALID"

    async def test_reused_token_returns_401_revoked(
        self, client: AsyncClient, token_service: RefreshTokenService
    ) -> None:
        issued = await token_service.issue_token_pair(USER_ID)
        await client.post("/api/v1/auth/refresh", json={"refresh_token": issued.refresh_token})

        replay = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": issued.refresh_token}
        )

        assert replay.status_code == 401
        assert replay.json()["error_code"] == "TOKEN_REVOKED"
