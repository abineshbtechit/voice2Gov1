from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from app.core.security import hash_password, validate_password_policy
from app.exceptions.base import (
    ConflictException,
    UnauthorizedException,
    ValidationException,
)
from app.repositories.user_repository import UserRepository
from app.schemas.base import ObjectIdStr
from app.schemas.token import TokenPairResponse
from app.schemas.user import (
    UserLoginRequest,
    UserLoginResponse,
    UserRegisterRequest,
    UserRegisterResponse,
    UserResponse,
    UserRole,
    UserStatus,
)

if TYPE_CHECKING:
    from app.services.token_service import RefreshTokenService


# Lockout policy constants
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


class UserService:
    def __init__(self, repository: UserRepository):
        self._repository = repository

    async def register(self, request: UserRegisterRequest) -> UserRegisterResponse:
        """Register a new user.

        Flow (Phase 1.2.1):
            validate input (pydantic) -> validate password policy ->
            normalize email/phone -> check duplicate email/phone ->
            hash password -> create user -> return safe response.
        """
        # 1. Validate password policy before any persistence work.
        is_valid, errors = validate_password_policy(request.password)
        if not is_valid:
            raise ValidationException(
                "Password does not meet policy requirements",
                errors=[
                    {"field": "password", "message": e, "code": "PASSWORD_POLICY"}
                    for e in errors
                ],
            )

        # 2. Normalize email and phone.
        normalized_email = request.email.lower().strip()
        normalized_phone = request.phone.strip()
        normalized_full_name = request.full_name.strip()

        # 3. Check for duplicates.
        if await self._repository.exists_by_email(normalized_email):
            raise ConflictException("Email already registered")

        if await self._repository.exists_by_phone(normalized_phone):
            raise ConflictException("Phone number already registered")

        # 4. Hash the password and build the user document.
        user_data = {
            "email": normalized_email,
            "phone": normalized_phone,
            "full_name": normalized_full_name,
            "password_hash": hash_password(request.password),
            "role": UserRole.CITIZEN.value,
            "status": UserStatus.PENDING_VERIFICATION.value,
            "is_verified": False,
            "failed_login_attempts": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        # 5. Persist and return a safe response.
        user_id = await self._repository.create(user_data)

        return UserRegisterResponse(
            id=ObjectIdStr(user_id),
            email=normalized_email,
            phone=normalized_phone,
            full_name=normalized_full_name,
            role=UserRole.CITIZEN,
            status=UserStatus.PENDING_VERIFICATION,
            is_verified=False,
            message="Registration successful. Please verify your account.",
        )

    async def login(
        self,
        request: UserLoginRequest,
        token_service: "RefreshTokenService",
    ) -> UserLoginResponse:
        """Authenticate a user and issue token pair.

        Security requirements:
        - Generic error message to prevent user enumeration
        - Track failed login attempts
        - Lock account after MAX_FAILED_LOGIN_ATTEMPTS
        - Lock duration: LOCKOUT_DURATION_MINUTES
        - Reset failed attempts on successful login
        """
        from app.core.security import verify_password

        identifier = request.identifier.strip()
        password = request.password

        # Find user by email or phone (normalized), with full_name fallback
        if "@" in identifier:
            user_doc = await self._repository.find_by_email(identifier.lower())
        else:
            user_doc = await self._repository.find_by_phone(identifier)
            if not user_doc and hasattr(self._repository, "find_by_full_name"):
                user_doc = await self._repository.find_by_full_name(identifier)

        # Check if user exists
        if not user_doc:
            # Generic error to prevent user enumeration
            raise UnauthorizedException("Invalid credentials", error_code="INVALID_CREDENTIALS")

        # Check if account is locked FIRST (before status check)
        locked_until = user_doc.get("locked_until")
        if locked_until and locked_until > datetime.now(UTC):
            raise UnauthorizedException(
                "Account temporarily locked due to failed login attempts",
                error_code="ACCOUNT_LOCKED",
            )

        # Check if account is locked via status
        if user_doc.get("status") == UserStatus.LOCKED.value:
            raise UnauthorizedException(
                "Account temporarily locked due to failed login attempts",
                error_code="ACCOUNT_LOCKED",
            )

        # Check account status (reject inactive or suspended users)
        if user_doc.get("status") in (UserStatus.INACTIVE.value, UserStatus.SUSPENDED.value):
            raise UnauthorizedException("Account is not active", error_code="ACCOUNT_INACTIVE")

        # Verify password
        if not verify_password(password, user_doc["password_hash"]):
            # Increment failed login attempts
            await self._handle_failed_login(user_doc)
            raise UnauthorizedException("Invalid credentials", error_code="INVALID_CREDENTIALS")

        # Password verified - reset failed attempts and update last_login_at
        await self._reset_failed_login_attempts(user_doc["_id"])

        # Issue token pair
        token_pair = await self._issue_token_pair(user_doc, token_service)

        return UserLoginResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type=token_pair.token_type,
            expires_in=token_pair.expires_in,
        )

    async def _handle_failed_login(self, user_doc: dict[str, Any]) -> None:
        """Increment failed login attempts and lock account if threshold exceeded."""
        failed_attempts = user_doc.get("failed_login_attempts", 0) + 1
        update_data = {
            "failed_login_attempts": failed_attempts,
            "updated_at": datetime.now(UTC),
        }

        if failed_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
            update_data["locked_until"] = datetime.now(UTC) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            update_data["status"] = UserStatus.LOCKED.value

        await self._repository.update(str(user_doc["_id"]), update_data)

    async def _reset_failed_login_attempts(self, user_id: str) -> None:
        """Reset failed login attempts on successful login."""
        # First get the current user to check status
        user_doc = await self._repository.find_by_id(user_id)
        update_data = {
            "failed_login_attempts": 0,
            "locked_until": None,
            "status": UserStatus.ACTIVE.value,
            "is_verified": True,
            "last_login_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
        await self._repository.update(user_id, update_data)

    async def _issue_token_pair(self, user_doc: dict[str, Any], token_service: "RefreshTokenService") -> TokenPairResponse:
        """Issue access and refresh token pair for authenticated user."""
        user_id = str(user_doc["_id"])
        role = user_doc.get("role")
        token_pair = await token_service.issue_token_pair(user_id, role)
        return token_pair

    async def get_user_by_id(self, user_id: str) -> UserResponse | None:
        """Get user by ID (safe response) - no tenant scoping, for admin/global use."""
        user_doc = await self._repository.find_by_id(user_id)
        if not user_doc:
            return None
        return self._to_user_response(user_doc)

    async def get_user_by_id_in_organization(
        self, user_id: str, organization_id: str
    ) -> UserResponse | None:
        """Get user by ID scoped to an organization (tenant isolation)."""
        user_doc = await self._repository.find_by_id_in_organization(user_id, organization_id)
        if not user_doc:
            return None
        return self._to_user_response(user_doc)

    async def get_users_in_organization(
        self,
        organization_id: str,
        role: UserRole | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[UserResponse]:
        """Get users in an organization (tenant-scoped)."""
        role_value = role.value if role else None
        user_docs = await self._repository.find_users_in_organization(
            organization_id, role=role_value, limit=limit, skip=skip
        )
        return [self._to_user_response(doc) for doc in user_docs]

    async def count_users_in_organization(
        self, organization_id: str, role: UserRole | None = None
    ) -> int:
        """Count users in an organization (tenant-scoped)."""
        role_value = role.value if role else None
        return await self._repository.count_users_in_organization(organization_id, role=role_value)

    async def update_user_in_organization(
        self,
        user_id: str,
        organization_id: str,
        update_data: dict[str, Any],
    ) -> bool:
        """Update a user in an organization (tenant-scoped)."""
        return await self._repository.update_in_organization(user_id, organization_id, update_data)

    def _to_user_response(self, user_doc: dict[str, Any]) -> UserResponse:
        """Convert user document to safe response model."""
        return UserResponse(
            id=ObjectIdStr(user_doc["_id"]),
            email=user_doc["email"],
            phone=user_doc["phone"],
            full_name=user_doc["full_name"],
            role=UserRole(user_doc["role"]),
            status=UserStatus(user_doc["status"]),
            organization_id=ObjectIdStr(user_doc["organization_id"]) if user_doc.get("organization_id") else None,
            department_id=ObjectIdStr(user_doc["department_id"]) if user_doc.get("department_id") else None,
            avatar_url=user_doc.get("avatar_url"),
            is_verified=user_doc.get("is_verified", False),
            created_at=user_doc["created_at"],
            updated_at=user_doc["updated_at"],
        )
