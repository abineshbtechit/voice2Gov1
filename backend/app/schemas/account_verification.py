from typing import Any
from pydantic import Field

from app.schemas.base import BaseSchema
from app.schemas.user import UserResponse


class SendVerificationOTPRequest(BaseSchema):
    """Payload to request an account verification OTP."""

    identifier: str = Field(..., min_length=1, description="Registered email, phone, or user identifier")
    channel: str = Field(default="email", description="Channel choice: 'email' or 'whatsapp'")


class SendVerificationOTPResponse(BaseSchema):
    """Response returned after generating verification OTP."""

    success: bool = True
    message: str = "Verification code generated"
    identifier: str
    channel: str
    whatsapp_url: str | None = None
    expires_in_seconds: int = 600
    otp_code: str | None = None  # Available for easy verification in mobile app & dev


class VerifyAccountOTPRequest(BaseSchema):
    """Payload to verify the 6-digit OTP and activate account."""

    identifier: str = Field(..., min_length=1, description="Registered email or phone")
    otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$", description="6-digit numeric OTP")


class VerifyAccountOTPResponse(BaseSchema):
    """Response on successful account verification containing JWT tokens."""

    success: bool = True
    message: str = "Account successfully verified"
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

