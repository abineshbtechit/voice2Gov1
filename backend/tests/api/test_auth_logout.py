"""Phase 1.2.3 — POST /api/v1/auth/logout API tests."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.dependencies.services import get_refresh_token_service, get_user_service
from app.main import create_app
from app.services.token_service import RefreshTokenService
from app.services.user_service import UserService
from tests.fakes import FakeRefreshTokenRepository, FakeUserRepository

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


class TestLogout:
    async def test_logout_returns_200_without_bearer(
        self, client: AsyncClient, token_service: RefreshTokenService
    ) -> None:
        issued = await token_service.issue_token_pair(USER_ID)

        response = await client.post(
            "/api/v1/auth/logout", json={"refresh_token": issued.refresh_token}
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Logged out"

    async def test_logout_invalidates_refresh_token(
        self, client: AsyncClient, token_service: RefreshTokenService
    ) -> None:
        issued = await token_service.issue_token_pair(USER_ID)
        await client.post("/api/v1/auth/logout", json={"refresh_token": issued.refresh_token})

        refresh = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": issued.refresh_token}
        )

        assert refresh.status_code == 401
        assert refresh.json()["error_code"] == "TOKEN_REVOKED"

    async def test_logout_revokes_whole_family(
        self,
        client: AsyncClient,
        token_service: RefreshTokenService,
        token_repository: FakeRefreshTokenRepository,
    ) -> None:
        issued = await token_service.issue_token_pair(USER_ID)
        rotated = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": issued.refresh_token}
        )
        latest = rotated.json()["refresh_token"]

        await client.post("/api/v1/auth/logout", json={"refresh_token": latest})

        assert all(r["revoked_at"] is not None for r in token_repository.records.values())

        refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": latest})
        assert refresh.status_code == 401
        assert refresh.json()["error_code"] == "TOKEN_REVOKED"

    async def test_logout_is_idempotent_for_invalid_token(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/logout", json={"refresh_token": "not-a-jwt"}
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Logged out"

    async def test_logout_missing_body_returns_422(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/auth/logout", json={})

        assert response.status_code == 422

    async def test_logout_response_leaks_nothing(
        self, client: AsyncClient, token_service: RefreshTokenService
    ) -> None:
        issued = await token_service.issue_token_pair(USER_ID)

        response = await client.post(
            "/api/v1/auth/logout", json={"refresh_token": issued.refresh_token}
        )

        body = response.text.lower()
        assert "password" not in body
        assert "token_hash" not in body
        assert "family_id" not in body
