from datetime import UTC, datetime, timedelta
import hashlib
import re
import secrets
from typing import Any
import urllib.parse

from app.exceptions.base import BadRequestException, NotFoundException
from app.repositories.account_verification_otp_repository import AccountVerificationOTPRepository
from app.repositories.user_repository import UserRepository
from app.schemas.account_verification import (
    SendVerificationOTPRequest,
    SendVerificationOTPResponse,
    VerifyAccountOTPRequest,
    VerifyAccountOTPResponse,
)
from app.schemas.base import ObjectIdStr
from app.schemas.user import UserResponse, UserStatus
from app.services.email_service import EmailService
from app.services.token_service import RefreshTokenService


class AccountVerificationService:
    """Service handling multi-channel (Google SMTP email & WhatsApp URL query) account verification."""

    def __init__(
        self,
        user_repo: UserRepository,
        otp_repo: AccountVerificationOTPRepository,
        token_service: RefreshTokenService,
    ) -> None:
        self._user_repo = user_repo
        self._otp_repo = otp_repo
        self._token_service = token_service

    def _hash_otp(self, identifier: str, otp: str, salt: str) -> str:
        data = f"{salt}:{identifier}:{otp}".encode()
        return hashlib.sha256(data).hexdigest()

    async def _resolve_user(self, identifier: str) -> dict[str, Any]:
        """Resolve user document by email, phone, full_name, or ID."""
        identifier_clean = identifier.strip()
        user_doc = None
        if "@" in identifier_clean:
            user_doc = await self._user_repo.find_by_email(identifier_clean.lower())
        else:
            user_doc = await self._user_repo.find_by_phone(identifier_clean)
            if not user_doc and hasattr(self._user_repo, "find_by_full_name"):
                user_doc = await self._user_repo.find_by_full_name(identifier_clean)
            if not user_doc and len(identifier_clean) == 24:
                user_doc = await self._user_repo.find_by_id(identifier_clean)

        if not user_doc:
            raise NotFoundException("User account not found", error_code="USER_NOT_FOUND")
        return user_doc

    async def send_verification_otp(self, request: SendVerificationOTPRequest) -> SendVerificationOTPResponse:
        """Generate and dispatch 6-digit OTP via Google SMTP (email) or WhatsApp URL query (phone)."""
        user_doc = await self._resolve_user(request.identifier)
        user_id = str(user_doc["_id"])
        user_name = user_doc.get("full_name") or "Citizen"
        user_email = user_doc.get("email") or ""
        user_phone = user_doc.get("phone") or ""

        channel = request.channel.lower().strip()
        if channel not in ("email", "whatsapp"):
            channel = "email"

        # Generate cryptographic 6-digit OTP
        otp_code = f"{secrets.randbelow(900000) + 100000:06d}"
        salt = secrets.token_hex(16)
        expires_at = datetime.now(UTC) + timedelta(seconds=60)

        # Primary identifier used for validation lookup
        primary_identifier = user_email if channel == "email" else user_phone
        if not primary_identifier:
            primary_identifier = request.identifier.strip()

        otp_hash = self._hash_otp(primary_identifier, otp_code, salt)

        # Persist unconsumed OTP record
        await self._otp_repo.create_otp(
            identifier=primary_identifier,
            otp_hash=otp_hash,
            salt=salt,
            channel=channel,
            expires_at=expires_at,
            user_id=user_id,
            max_attempts=5,
        )

        whatsapp_url = None
        if channel == "whatsapp":
            clean_phone = re.sub(r"[^\d]", "", user_phone or request.identifier)
            msg_text = (
                f"Your Voice2Gov verification code is: {otp_code}\n\n"
                f"Valid for 1 minute. Please enter this code in the app to activate your account."
            )
            encoded_msg = urllib.parse.quote_plus(msg_text)
            whatsapp_url = f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_msg}"
            message = f"WhatsApp verification link created for {user_phone}"
        else:
            # Send via Google SMTP
            await EmailService.send_verification_otp(user_email, otp_code, user_name)
            message = f"Verification code sent to {user_email}"

        return SendVerificationOTPResponse(
            success=True,
            message=message,
            identifier=primary_identifier,
            channel=channel,
            whatsapp_url=whatsapp_url,
            expires_in_seconds=60,
            otp_code=otp_code,
        )

    async def verify_account_otp(self, request: VerifyAccountOTPRequest) -> VerifyAccountOTPResponse:
        """Validate 6-digit OTP, activate account, and issue session JWT tokens."""
        user_doc = await self._resolve_user(request.identifier)
        user_id = str(user_doc["_id"])
        user_email = user_doc.get("email") or ""
        user_phone = user_doc.get("phone") or ""
        submitted_otp = request.otp.strip()

        # Check latest active record for primary identifier, email, or phone
        record = await self._otp_repo.get_latest_active_otp(user_email)
        if not record and user_phone:
            record = await self._otp_repo.get_latest_active_otp(user_phone)
        if not record:
            record = await self._otp_repo.get_latest_active_otp(request.identifier.strip())

        if not record:
            raise BadRequestException(
                "Verification code has expired or is invalid. Please request a new one.",
                error_code="OTP_EXPIRED_OR_NOT_FOUND",
            )

        # Check maximum attempts
        attempts = await self._otp_repo.increment_attempts(record["_id"])
        if attempts > record.get("max_attempts", 5):
            raise BadRequestException(
                "Maximum verification attempts exceeded. Please request a new code.",
                error_code="OTP_MAX_ATTEMPTS_EXCEEDED",
            )

        # Verify cryptographic hash
        expected_hash = record["otp_hash"]
        salt = record["salt"]
        identifier_used = record["identifier"]
        actual_hash = self._hash_otp(identifier_used, submitted_otp, salt)

        if actual_hash != expected_hash:
            raise BadRequestException(
                "Invalid 6-digit verification code. Please check and try again.",
                error_code="INVALID_OTP",
            )

        # Consume OTP record
        await self._otp_repo.mark_consumed(record["_id"])

        # Activate user account
        now = datetime.now(UTC)
        await self._user_repo.update(
            user_id,
            {
                "status": UserStatus.ACTIVE.value,
                "is_verified": True,
                "failed_login_attempts": 0,
                "last_login_at": now,
                "updated_at": now,
            },
        )

        # Issue access and refresh tokens
        role = user_doc.get("role", "citizen")
        token_pair = await self._token_service.issue_token_pair(user_id, role)

        # Prepare safe user response
        user_response = UserResponse(
            id=ObjectIdStr(user_id),
            email=user_doc["email"],
            phone=user_doc.get("phone"),
            full_name=user_doc.get("full_name", "Citizen"),
            role=role,
            status=UserStatus.ACTIVE,
            is_verified=True,
            organization_id=ObjectIdStr(str(user_doc["organization_id"])) if user_doc.get("organization_id") else None,
            department_id=ObjectIdStr(str(user_doc["department_id"])) if user_doc.get("department_id") else None,
            created_at=user_doc.get("created_at") or now,
            updated_at=now,
        )

        return VerifyAccountOTPResponse(
            success=True,
            message="Account successfully verified and activated",
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type=token_pair.token_type,
            expires_in=token_pair.expires_in,
            user=user_response,
        )
