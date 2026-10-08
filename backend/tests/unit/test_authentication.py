"""Phase 1.2.2 — authentication dependency unit tests.

Exercises :func:`app.dependencies.auth.get_current_user` directly with bearer
credentials and an in-memory repository.
"""

import time
from datetime import timedelta

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.core.config import settings
from app.core.security import create_access_token
from app.dependencies.auth import get_current_user
from app.exceptions.base import UnauthorizedException
from app.services.user_service import UserService
from tests.fakes import FakeUserRepository, tamper_token

USER_ID = "507f1f77bcf86cd799439011"


def bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.fixture
def repository() -> FakeUserRepository:
    repo = FakeUserRepository()
    repo.seed(USER_ID, role="citizen")
    return repo


@pytest.fixture
def service(repository: FakeUserRepository) -> UserService:
    return UserService(repository)  # type: ignore[arg-type]


class TestSuccessfulAuthentication:
    async def test_valid_bearer_token_authenticates(self, service: UserService) -> None:
        token = create_access_token(USER_ID, role="citizen")

        user = await get_current_user(credentials=bearer(token), service=service)

        assert user.id == USER_ID
        assert user.email == "citizen@example.com"
        assert user.role == "citizen"

    async def test_returns_safe_user_without_credentials(self, service: UserService) -> None:
        token = create_access_token(USER_ID)

        user = await get_current_user(credentials=bearer(token), service=service)

        dumped = user.model_dump()
        assert "password" not in dumped
        assert "password_hash" not in dumped


class TestAuthenticationFailures:
    async def test_missing_authorization_header_fails(self, service: UserService) -> None:
        with pytest.raises(UnauthorizedException) as exc:
            await get_current_user(credentials=None, service=service)

        assert exc.value.status_code == 401
        assert exc.value.error_code == "TOKEN_INVALID"

    async def test_empty_bearer_token_fails(self, service: UserService) -> None:
        with pytest.raises(UnauthorizedException) as exc:
            await get_current_user(credentials=bearer(""), service=service)

        assert exc.value.status_code == 401

    async def test_invalid_jwt_fails(self, service: UserService) -> None:
        with pytest.raises(UnauthorizedException) as exc:
            await get_current_user(credentials=bearer("not-a-jwt"), service=service)

        assert exc.value.error_code == "TOKEN_INVALID"

    async def test_expired_jwt_fails(self, service: UserService) -> None:
        token = create_access_token(USER_ID, expires_delta=timedelta(seconds=-5))

        with pytest.raises(UnauthorizedException) as exc:
            await get_current_user(credentials=bearer(token), service=service)

        assert exc.value.error_code == "TOKEN_EXPIRED"

    async def test_tampered_jwt_fails(self, service: UserService) -> None:
        tampered = tamper_token(create_access_token(USER_ID))

        with pytest.raises(UnauthorizedException) as exc:
            await get_current_user(credentials=bearer(tampered), service=service)

        assert exc.value.error_code == "TOKEN_INVALID"

    async def test_token_without_sub_fails(self, service: UserService) -> None:
        now = int(time.time())
        token = jwt.encode(
            {"type": "access", "iat": now, "exp": now + 60},
            settings.secret_key,
            algorithm=settings.algorithm,
        )

        with pytest.raises(UnauthorizedException) as exc:
            await get_current_user(credentials=bearer(token), service=service)

        assert exc.value.error_code == "TOKEN_INVALID"

    async def test_valid_token_for_nonexistent_user_fails(self, service: UserService) -> None:
        token = create_access_token("0000000000000000000000ff")

        with pytest.raises(UnauthorizedException) as exc:
            await get_current_user(credentials=bearer(token), service=service)

        assert exc.value.error_code == "TOKEN_INVALID"


class TestFailureSafety:
    async def test_failure_never_exposes_secret_or_password(self, service: UserService) -> None:
        token = create_access_token(USER_ID, expires_delta=timedelta(seconds=-5))

        with pytest.raises(UnauthorizedException) as exc:
            await get_current_user(credentials=bearer(token), service=service)

        rendered = f"{exc.value.message} {exc.value.details} {exc.value.error_code}"
        assert settings.secret_key not in rendered
        assert "password" not in rendered.lower()
        assert "password_hash" not in rendered
        assert "$2b$" not in rendered
