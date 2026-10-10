from abc import ABC, abstractmethod
from typing import Any


class OTPDeliveryProvider(ABC):
    """Abstract base class for delivering one-time passwords (SMS/Email)."""

    @abstractmethod
    async def send_otp(
        self,
        identifier: str,
        otp_code: str,
        purpose: str = "password_reset",
    ) -> dict[str, Any]:
        """Send OTP code to identifier (email or phone)."""
        raise NotImplementedError


class MockOTPDeliveryProvider(OTPDeliveryProvider):
    """Deterministic in-memory mock OTP delivery provider for testing and development."""

    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []
        self.send_called: bool = False
        self.fail_mode: bool = False

    async def send_otp(
        self,
        identifier: str,
        otp_code: str,
        purpose: str = "password_reset",
    ) -> dict[str, Any]:
        self.send_called = True
        if self.fail_mode:
            raise RuntimeError("Mock OTP delivery provider failure simulation")

        record = {
            "identifier": identifier,
            "otp_code": otp_code,
            "purpose": purpose,
        }
        self.sent_messages.append(record)
        return {"success": True, "delivered_to": identifier}
