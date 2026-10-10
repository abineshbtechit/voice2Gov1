import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.core.security import hash_password, validate_password_policy
from app.exceptions.base import (
    BadRequestException,
    ValidationException,
)
from app.repositories.password_reset_otp_repository import PasswordResetOTPRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.password_recovery import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    VerifyOTPRequest,
    VerifyOTPResponse,
)
from app.services.otp_provider import OTPDeliveryProvider


class PasswordRecoveryService:
    """Service handling OTP password recovery workflow with timing-safe hash verification,

    rate limiting, account enumeration resistance, session invalidation, and single-use token lifecycle.
    """

    OTP_TTL_MINUTES = 10
    RESET_TOKEN_TTL_MINUTES = 15
    MAX_ATTEMPTS = 3

    def __init__(
        self,
        otp_repo: PasswordResetOTPRepository,
        user_repo: UserRepository,
        delivery_provider: OTPDeliveryProvider,
        token_repo: RefreshTokenRepository | None = None,
    ) -> None:
        self._otp_repo = otp_repo
        self._user_repo = user_repo
        self._delivery_provider = delivery_provider
        self._token_repo = token_repo

    def _hash_otp(self, identifier: str, otp: str, salt: str) -> str:
        """Create HMAC-SHA-256 hash using secret_key as pepper combined with per-record salt."""
        pepper = settings.secret_key.encode()
        data = f"{salt}:{identifier}:{otp}".encode()
        return hmac.new(pepper, data, hashlib.sha256).hexdigest()

    def _hash_token(self, token: str) -> str:
        """Create SHA-256 hash of reset token."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def initiate_password_recovery(
        self, request: ForgotPasswordRequest
    ) -> ForgotPasswordResponse:
        """Initiate password recovery flow.

        Returns generic success message regardless of user existence to prevent account enumeration.
        """
        identifier = request.identifier.strip().lower()

        # Check if user exists (by email or phone)
        user = await self._user_repo.find_by_email(identifier)
        if not user:
            user = await self._user_repo.find_by_phone(request.identifier.strip())

        # If user exists, generate cryptographically secure 6-digit OTP
        if user:
            # 6-digit numeric OTP (100000 - 999999)
            otp_code = f"{secrets.randbelow(900000) + 100000:06d}"
            salt = secrets.token_hex(16)
            otp_hash = self._hash_otp(identifier, otp_code, salt)
            expires_at = datetime.now(UTC) + timedelta(minutes=self.OTP_TTL_MINUTES)

            await self._otp_repo.create_otp(
                identifier=identifier,
                otp_hash=otp_hash,
                salt=salt,
                expires_at=expires_at,
                max_attempts=self.MAX_ATTEMPTS,
            )

            # Dispatch via delivery provider abstraction (safe mock / decoupled)
            try:
                await self._delivery_provider.send_otp(
                    identifier=identifier,
                    otp_code=otp_code,
                    purpose="password_reset",
                )
            except Exception:
                # Log provider failure but do not leak or break recovery flow
                pass

        return ForgotPasswordResponse(
            message="If an account exists with the provided information, a verification code has been sent.",
            cooldown_seconds=60,
        )

    async def verify_otp(self, request: VerifyOTPRequest) -> VerifyOTPResponse:
        """Verify submitted OTP code and return short-lived password reset token."""
        identifier = request.identifier.strip().lower()
        submitted_otp = request.otp.strip()

        record = await self._otp_repo.get_latest_active_otp(identifier)
        if not record:
            raise BadRequestException("Invalid or expired verification code", error_code="OTP_INVALID")

        # Check attempt limits
        if record.get("attempts", 0) >= record.get("max_attempts", self.MAX_ATTEMPTS):
            raise BadRequestException(
                "Maximum verification attempts exceeded. Please request a new code.",
                error_code="OTP_ATTEMPTS_EXCEEDED",
            )

        # Increment attempts counter
        new_attempts = await self._otp_repo.increment_attempts(record["_id"])

        # Constant-time comparison using record salt and server pepper
        salt = record.get("salt", "")
        expected_hash = record["otp_hash"]
        actual_hash = self._hash_otp(identifier, submitted_otp, salt)
        if not hmac.compare_digest(expected_hash, actual_hash):
            remaining = max(0, record.get("max_attempts", self.MAX_ATTEMPTS) - new_attempts)
            raise BadRequestException(
                f"Invalid verification code. {remaining} attempt(s) remaining.",
                error_code="OTP_INVALID",
            )

        # Generate single-use reset token
        reset_token = secrets.token_urlsafe(32)
        reset_token_hash = self._hash_token(reset_token)
        reset_token_expires = datetime.now(UTC) + timedelta(minutes=self.RESET_TOKEN_TTL_MINUTES)

        marked = await self._otp_repo.mark_verified_and_set_reset_token(
            record_id=record["_id"],
            reset_token_hash=reset_token_hash,
            reset_token_expires_at=reset_token_expires,
        )
        if not marked:
            raise BadRequestException(
                "Verification code has already been consumed. Please request a new code.",
                error_code="OTP_ALREADY_CONSUMED",
            )

        return VerifyOTPResponse(
            reset_token=reset_token,
            expires_in=self.RESET_TOKEN_TTL_MINUTES * 60,
            message="Verification successful. Use the reset token to complete password update.",
        )

    async def reset_password(self, request: ResetPasswordRequest) -> ResetPasswordResponse:
        """Reset user password using single-use reset token with full password policy enforcement

        and revocation of all active sessions/refresh tokens.
        """
        # 1. Validate password policy
        is_valid, errors = validate_password_policy(request.new_password)
        if not is_valid:
            raise ValidationException(
                "New password does not meet complexity requirements",
                errors=[
                    {"field": "new_password", "message": err, "code": "PASSWORD_POLICY"}
                    for err in errors
                ],
            )

        # 2. Find and validate reset token record
        token_hash = self._hash_token(request.reset_token)
        record = await self._otp_repo.find_by_reset_token_hash(token_hash)
        if not record:
            raise BadRequestException("Invalid or expired password reset token", error_code="TOKEN_INVALID")

        # 3. Atomically consume token
        consumed = await self._otp_repo.consume_reset_token(record["_id"])
        if not consumed:
            raise BadRequestException("Password reset token has already been used", error_code="TOKEN_ALREADY_USED")

        # 4. Find user by record identifier and update password
        identifier = record["identifier"]
        user = await self._user_repo.find_by_email(identifier)
        if not user:
            user = await self._user_repo.find_by_phone(identifier)

        if not user:
            raise BadRequestException("User associated with reset token not found", error_code="USER_NOT_FOUND")

        new_password_hash = hash_password(request.new_password)
        user_id = str(user["_id"])
        await self._user_repo.update(
            user_id,
            {
                "password_hash": new_password_hash,
                "failed_login_attempts": 0,
                "locked_until": None,
                "updated_at": datetime.now(UTC),
            },
        )

        # 5. Security requirement: Invalidate all outstanding refresh tokens / sessions for user
        if self._token_repo is not None:
            await self._token_repo.revoke_all_for_user(user_id, revoked_at=datetime.now(UTC))

        return ResetPasswordResponse(message="Password has been reset successfully. You may now log in.")

