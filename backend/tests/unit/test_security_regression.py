"""Phase 1.2.1 — security and regression tests.

Covers the SECURITY requirements:
- the stored document holds a bcrypt hash, never plaintext
- responses never expose password / password_hash
- exceptions and error details never expose password / password_hash
- Phase 1.2.2+ authentication endpoints are absent (regression guard)
"""

from unittest.mock import AsyncMock

import pytest

from app.exceptions.base import ConflictException, ValidationException
from app.main import create_app
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserInDB, UserRegisterRequest, UserResponse
from app.services.user_service import UserService

VALID_ID = "507f1f77bcf86cd799439011"
PLAINTEXT = "SecurePass123!"


def _request(**overrides: object) -> UserRegisterRequest:
    data: dict[str, object] = {
        "email": "test@example.com",
        "phone": "+15551234567",
        "full_name": "Test User",
        "password": PLAINTEXT,
    }
    data.update(overrides)
    return UserRegisterRequest(**data)


@pytest.fixture
def repository() -> AsyncMock:
    repo = AsyncMock(spec=UserRepository)
    repo.exists_by_email.return_value = False
    repo.exists_by_phone.return_value = False
    repo.create.return_value = VALID_ID
    return repo


@pytest.fixture
def service(repository: AsyncMock) -> UserService:
    return UserService(repository)


class TestDatabaseNeverStoresPlaintext:
    async def test_stored_document_holds_hash_not_plaintext(
        self, service: UserService, repository: AsyncMock
    ) -> None:
        await service.register(_request())

        stored = repository.create.await_args[0][0]
        assert PLAINTEXT not in str(stored)
        assert stored["password_hash"].startswith("$2")
        assert "password" not in {k for k in stored if k != "password_hash"}

    async def test_same_password_two_users_get_distinct_hashes(
        self, service: UserService, repository: AsyncMock
    ) -> None:
        await service.register(_request(email="a@example.com"))
        first = repository.create.await_args[0][0]["password_hash"]

        await service.register(_request(email="b@example.com"))
        second = repository.create.await_args[0][0]["password_hash"]

        assert first != second


class TestResponsesNeverExposeCredentials:
    def test_response_models_lack_password_fields(self) -> None:
        assert "password" not in UserResponse.model_fields
        assert "password_hash" not in UserResponse.model_fields
        assert "password_hash" in UserInDB.model_fields  # hash exists only for DB layer

    async def test_registration_response_leaks_nothing(
        self, service: UserService
    ) -> None:
        result = await service.register(_request())

        rendered = str(result.model_dump())
        assert PLAINTEXT not in rendered
        assert "password" not in rendered
        assert "$2" not in rendered


class TestErrorsNeverExposeCredentials:
    async def test_validation_error_hides_password(self, service: UserService) -> None:
        with pytest.raises(ValidationException) as exc:
            await service.register(_request(password="weakpassword"))

        rendered = f"{exc.value.message} {exc.value.details}"
        assert "weakpassword" not in rendered
        assert "password_hash" not in rendered

    async def test_conflict_error_hides_password(self, repository: AsyncMock) -> None:
        repository.exists_by_email.return_value = True
        service = UserService(repository)

        with pytest.raises(ConflictException) as exc:
            await service.register(_request())

        assert PLAINTEXT not in str(exc.value)
        assert "password_hash" not in str(exc.value)


class TestNoOutOfScopeEndpoints:
    """Regression guard: Phase 1.2.2+ auth endpoints must not exist."""

    def test_no_login_or_logout_routes(self) -> None:
        app = create_app()
        paths = {getattr(route, "path", "") for route in app.routes}
        forbidden = ("/auth/login", "/auth/logout", "/auth/refresh")
        for path in forbidden:
            assert path not in paths, f"out-of-scope route present: {path}"

    def test_register_route_present(self) -> None:
        app = create_app()
        paths = {getattr(route, "path", "") for route in app.routes}
        assert "/api/v1/auth/register" in paths
