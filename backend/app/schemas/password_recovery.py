from pydantic import Field

from app.schemas.base import BaseSchema


class ForgotPasswordRequest(BaseSchema):
    identifier: str = Field(..., min_length=3, max_length=256, description="User email or phone number")


class ForgotPasswordResponse(BaseSchema):
    message: str = Field(..., description="Status message")
    cooldown_seconds: int = Field(default=60, description="Minimum seconds before requesting another OTP")


class VerifyOTPRequest(BaseSchema):
    identifier: str = Field(..., min_length=3, max_length=256, description="User email or phone number")
    otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$", description="6-digit numeric OTP")


class VerifyOTPResponse(BaseSchema):
    reset_token: str = Field(..., description="Short-lived reset token for completing password reset")
    expires_in: int = Field(default=900, description="Token validity in seconds (15 minutes)")
    message: str = Field(..., description="Verification status message")


class ResetPasswordRequest(BaseSchema):
    reset_token: str = Field(..., min_length=16, description="Cryptographic reset token received from verify-otp")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password adhering to security policy")


class ResetPasswordResponse(BaseSchema):
    message: str = Field(..., description="Success message")
