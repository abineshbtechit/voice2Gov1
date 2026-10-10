import pytest

from app.exceptions.base import BadRequestException
from app.repositories.password_reset_otp_repository import PasswordResetOTPRepository
from app.repositories.user_repository import UserRepository
from app.schemas.password_recovery import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyOTPRequest,
)
from app.services.otp_provider import MockOTPDeliveryProvider
from app.services.password_recovery_service import PasswordRecoveryService


@pytest.mark.asyncio
async def test_full_otp_and_reset_flow(db) -> None:
    user_repo = UserRepository(db)
    otp_repo = PasswordResetOTPRepository(db)
    provider = MockOTPDeliveryProvider()
    service = PasswordRecoveryService(otp_repo, user_repo, provider)

    # 1. Create a user
    user_id = await user_repo.create({
        "email": "test.user@example.com",
        "phone": "+919988776655",
        "full_name": "Test User",
        "password_hash": "dummy_hash",
        "role": "citizen",
        "status": "active",
        "is_verified": True,
    })
    assert user_id is not None

    # 2. Request OTP
    forgot_req = ForgotPasswordRequest(identifier="test.user@example.com")
    resp = await service.initiate_password_recovery(forgot_req)
    assert resp.cooldown_seconds == 60
    assert provider.send_called is True
    assert len(provider.sent_messages) == 1
    sent_otp = provider.sent_messages[0]["otp_code"]

    # 3. Verify OTP
    verify_req = VerifyOTPRequest(identifier="test.user@example.com", otp=sent_otp)
    verify_resp = await service.verify_otp(verify_req)
    assert verify_resp.reset_token is not None

    # 4. Replay OTP -> should fail because OTP was marked consumed
    with pytest.raises(BadRequestException):
        await service.verify_otp(verify_req)

    # 5. Reset Password
    reset_req = ResetPasswordRequest(
        reset_token=verify_resp.reset_token,
        new_password="BrandNewPassword@123",
    )
    reset_resp = await service.reset_password(reset_req)
    assert "successfully" in reset_resp.message

    # 6. Replay Reset Token -> should fail
    with pytest.raises(BadRequestException):
        await service.reset_password(reset_req)


@pytest.mark.asyncio
async def test_otp_attempt_limits(db) -> None:
    user_repo = UserRepository(db)
    otp_repo = PasswordResetOTPRepository(db)
    provider = MockOTPDeliveryProvider()
    service = PasswordRecoveryService(otp_repo, user_repo, provider)

    await user_repo.create({
        "email": "brute@example.com",
        "phone": "+919988776600",
        "full_name": "Brute Force User",
        "password_hash": "dummy_hash",
        "role": "citizen",
        "status": "active",
        "is_verified": True,
    })

    await service.initiate_password_recovery(ForgotPasswordRequest(identifier="brute@example.com"))

    # Fail 3 times
    for _ in range(3):
        with pytest.raises(BadRequestException):
            await service.verify_otp(VerifyOTPRequest(identifier="brute@example.com", otp="999999"))

    # 4th time -> attempts exceeded
    with pytest.raises(BadRequestException) as exc_info:
        await service.verify_otp(VerifyOTPRequest(identifier="brute@example.com", otp="999999"))
    assert "exceeded" in str(exc_info.value.message).lower()
