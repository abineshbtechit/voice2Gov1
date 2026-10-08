"""Phase 1.2.1 — user registration service tests.

Covers the SERVICE requirements:
- successful registration
- email/phone normalization
- password hashing (bcrypt, never plaintext)
- duplicate email / phone rejection
- flow ordering (password policy validated before duplicate lookups)
- safe response (no password / password_hash)
"""

import re
from unittest.mock import AsyncMock

import pytest

from app.core.security import verify_password
from app.exceptions.base import ConflictException, ValidationException
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserRegisterRequest
from app.services.user_service import UserService

BCRYPT_PATTERN = re.compile(r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$")

VALID_ID = "507f1f77bcf86cd799439011"
VALID_PASSWORD = "SecurePass123!"


def make_request(
    email: str = "test@example.com",
    phone: str = "+15551234567",
    full_name: str = "Test User",
    password: str = VALID_PASSWORD,
) -> UserRegisterRequest:
    return UserRegisterRequest(
        email=email, phone=phone, full_name=full_name, password=password
    )


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


class TestSuccessfulRegistration:
    async def test_register_creates_user(self, service: UserService, repository: AsyncMock) -> None:
        result = await service.register(make_request())

        assert result.id == VALID_ID
        assert result.email == "test@example.com"
        assert result.phone == "+15551234567"
        assert result.full_name == "Test User"
        assert result.role == "citizen"
        assert result.status == "pending_verification"
        assert result.is_verified is False
        assert "Registration successful" in result.message
        repository.create.assert_awaited_once()

    async def test_email_is_normalized(self, service: UserService, repository: AsyncMock) -> None:
        await service.register(make_request(email="  TEST@EXAMPLE.COM  "))

        repository.exists_by_email.assert_awaited_once_with("test@example.com")
        stored = repository.create.await_args[0][0]
        assert stored["email"] == "test@example.com"

    async def test_phone_is_preserved_as_e164(self, service: UserService, repository: AsyncMock) -> None:
        await service.register(make_request(phone="+15551234567"))

        repository.exists_by_phone.assert_awaited_once_with("+15551234567")
        stored = repository.create.await_args[0][0]
        assert stored["phone"] == "+15551234567"

    async def test_full_name_is_trimmed(self, service: UserService, repository: AsyncMock) -> None:
        await service.register(make_request(full_name="  Test User  "))

        stored = repository.create.await_args[0][0]
        assert stored["full_name"] == "Test User"

    async def test_password_is_hashed_with_bcrypt(
        self, service: UserService, repository: AsyncMock
    ) -> None:
        await service.register(make_request())

        stored = repository.create.await_args[0][0]
        password_hash = stored["password_hash"]

        assert password_hash != VALID_PASSWORD
        assert BCRYPT_PATTERN.match(password_hash)
        assert verify_password(VALID_PASSWORD, password_hash) is True
        assert "password" not in stored or stored.get("password") is None


class TestDuplicateHandling:
    async def test_duplicate_email_rejected(
        self, service: UserService, repository: AsyncMock
    ) -> None:
        repository.exists_by_email.return_value = True

        with pytest.raises(ConflictException) as exc:
            await service.register(make_request(email="exists@example.com"))

        assert exc.value.error_code == "CONFLICT"
        assert "Email already registered" in str(exc.value.message)
        repository.create.assert_not_awaited()

    async def test_duplicate_phone_rejected(
        self, service: UserService, repository: AsyncMock
    ) -> None:
        repository.exists_by_phone.return_value = True

        with pytest.raises(ConflictException) as exc:
            await service.register(make_request())

        assert exc.value.error_code == "CONFLICT"
        assert "Phone number already registered" in str(exc.value.message)
        repository.create.assert_not_awaited()

    async def test_duplicate_key_race_is_converted_to_conflict(
        self, service: UserService, repository: AsyncMock
    ) -> None:
        repository.create.side_effect = ConflictException("Email already registered")

        with pytest.raises(ConflictException):
            await service.register(make_request())


class TestPasswordPolicyEnforcement:
    async def test_weak_password_rejected(self, service: UserService, repository: AsyncMock) -> None:
        with pytest.raises(ValidationException) as exc:
            await service.register(make_request(password="weakpassword"))

        assert exc.value.error_code == "VALIDATION_ERROR"
        codes = [e.get("code") for e in exc.value.details.get("errors", [])]
        assert "PASSWORD_POLICY" in codes
        repository.create.assert_not_awaited()

    async def test_policy_validated_before_duplicate_lookup(
        self, service: UserService, repository: AsyncMock
    ) -> None:
        """Flow order: password policy must be checked before duplicate lookups."""
        repository.exists_by_email.return_value = True  # would be a 409 if reached

        with pytest.raises(ValidationException):
            await service.register(
                make_request(email="exists@example.com", password="weakpassword")
            )

        repository.exists_by_email.assert_not_awaited()


class TestSafeResponse:
    async def test_response_excludes_password(self, service: UserService) -> None:
        result = await service.register(make_request())

        dumped = result.model_dump()
        assert "password" not in dumped
        assert "password_hash" not in dumped
        assert not hasattr(result, "password")
        assert not hasattr(result, "password_hash")

    async def test_get_user_by_id_excludes_credentials(self, repository: AsyncMock) -> None:
        from datetime import datetime

        repository.find_by_id.return_value = {
            "_id": VALID_ID,
            "email": "a@b.com",
            "phone": "+15551234567",
            "full_name": "A",
            "role": "citizen",
            "status": "active",
            "is_verified": True,
            "password_hash": "$2b$12$abcdefghijklmnopqrstuv",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        service = UserService(repository)

        user = await service.get_user_by_id(VALID_ID)

        assert user is not None
        dumped = user.model_dump()
        assert "password_hash" not in dumped
        assert "password" not in dumped

    async def test_get_user_by_id_missing_returns_none(self, repository: AsyncMock) -> None:
        repository.find_by_id.return_value = None
        service = UserService(repository)

        assert await service.get_user_by_id(VALID_ID) is None
