import asyncio

import pytest

from app.repositories.password_reset_otp_repository import PasswordResetOTPRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.password_recovery import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyOTPRequest,
)
from app.services.otp_provider import MockOTPDeliveryProvider
from app.services.password_recovery_service import PasswordRecoveryService


@pytest.mark.asyncio
async def test_concurrent_otp_verification_single_use(db) -> None:
    """Ensure two concurrent verify requests for the same OTP cannot both succeed."""
    user_repo = UserRepository(db)
    otp_repo = PasswordResetOTPRepository(db)
    provider = MockOTPDeliveryProvider()
    token_repo = RefreshTokenRepository(db)
    service = PasswordRecoveryService(otp_repo, user_repo, provider, token_repo)

    await user_repo.create({
        "email": "race@example.com",
        "phone": "+919876500000",
        "full_name": "Race User",
        "password_hash": "dummy_hash",
        "role": "citizen",
        "status": "active",
        "is_verified": True,
    })

    await service.initiate_password_recovery(ForgotPasswordRequest(identifier="race@example.com"))
    sent_otp = provider.sent_messages[0]["otp_code"]

    req1 = VerifyOTPRequest(identifier="race@example.com", otp=sent_otp)
    req2 = VerifyOTPRequest(identifier="race@example.com", otp=sent_otp)

    # Execute both simultaneously
    results = await asyncio.gather(
        service.verify_otp(req1),
        service.verify_otp(req2),
        return_exceptions=True,
    )

    # Exactly one must succeed, and the other must raise an exception
    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(failures) == 1, f"Expected exactly 1 failure, got {len(failures)}"


@pytest.mark.asyncio
async def test_concurrent_password_reset_single_use(db) -> None:
    """Ensure two concurrent reset requests with the same reset token cannot both succeed."""
    user_repo = UserRepository(db)
    otp_repo = PasswordResetOTPRepository(db)
    provider = MockOTPDeliveryProvider()
    token_repo = RefreshTokenRepository(db)
    service = PasswordRecoveryService(otp_repo, user_repo, provider, token_repo)

    await user_repo.create({
        "email": "reset.race@example.com",
        "phone": "+919876500001",
        "full_name": "Reset Race User",
        "password_hash": "dummy_hash",
        "role": "citizen",
        "status": "active",
        "is_verified": True,
    })

    await service.initiate_password_recovery(ForgotPasswordRequest(identifier="reset.race@example.com"))
    sent_otp = provider.sent_messages[0]["otp_code"]
    verify_resp = await service.verify_otp(VerifyOTPRequest(identifier="reset.race@example.com", otp=sent_otp))

    reset_token = verify_resp.reset_token

    req1 = ResetPasswordRequest(reset_token=reset_token, new_password="NewSecurePass1@")
    req2 = ResetPasswordRequest(reset_token=reset_token, new_password="AnotherSecurePass2@")

    results = await asyncio.gather(
        service.reset_password(req1),
        service.reset_password(req2),
        return_exceptions=True,
    )

    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(failures) == 1, f"Expected exactly 1 failure, got {len(failures)}"


@pytest.mark.asyncio
async def test_password_reset_revokes_active_sessions(db) -> None:
    """Resetting password must revoke all existing active refresh tokens for the user."""
    user_repo = UserRepository(db)
    otp_repo = PasswordResetOTPRepository(db)
    token_repo = RefreshTokenRepository(db)
    provider = MockOTPDeliveryProvider()
    service = PasswordRecoveryService(otp_repo, user_repo, provider, token_repo)

    user_id = await user_repo.create({
        "email": "sessions@example.com",
        "phone": "+919876500002",
        "full_name": "Session User",
        "password_hash": "dummy_hash",
        "role": "citizen",
        "status": "active",
        "is_verified": True,
    })

    # Insert an active refresh token
    await token_repo.insert_token({
        "user_id": str(user_id),
        "family_id": "family-123",
        "jti": "jti-123",
        "token_hash": "dummy_token_hash_value",
        "expires_at": None,
        "created_at": None,
        "revoked_at": None,
        "replaced_by": None,
        "reuse_detected": False,
    })

    # Perform password reset
    await service.initiate_password_recovery(ForgotPasswordRequest(identifier="sessions@example.com"))
    sent_otp = provider.sent_messages[0]["otp_code"]
    v_resp = await service.verify_otp(VerifyOTPRequest(identifier="sessions@example.com", otp=sent_otp))

    await service.reset_password(ResetPasswordRequest(reset_token=v_resp.reset_token, new_password="BrandNewPass@123"))

    # Verify that the refresh token was revoked
    doc = await token_repo.find_by_token_hash("dummy_token_hash_value")
    assert doc is not None
    assert doc["revoked_at"] is not None
    assert doc["reason"] == "password_reset"
