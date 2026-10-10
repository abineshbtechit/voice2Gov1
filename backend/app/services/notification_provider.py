"""Push notification provider abstraction and implementations (Phase 1.6).

Authoritative source: docs/notification-architecture.md §Service Abstraction.
Decouples notification dispatch from concrete push services (FCM/APNS/Mock).
"""

from abc import ABC, abstractmethod
from typing import Any


class NotificationProvider(ABC):
    """Abstract base class for push notification delivery providers."""

    @abstractmethod
    async def send_push(
        self, tokens: list[str], title: str, body: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Send push notification to device tokens."""
        raise NotImplementedError

    @abstractmethod
    async def send_multicast(
        self, tokens: list[str], title: str, body: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Send multicast push notification to multiple device tokens."""
        raise NotImplementedError


class MockNotificationProvider(NotificationProvider):
    """Deterministic in-memory mock provider for testing and development."""

    def __init__(self) -> None:
        self.sent_notifications: list[dict[str, Any]] = []
        self.send_called: bool = False
        self.fail_mode: bool = False
        self.invalid_tokens: set[str] = set()

    async def send_push(
        self, tokens: list[str], title: str, body: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        self.send_called = True
        if self.fail_mode:
            raise RuntimeError("Mock push provider delivery failure simulation")

        record = {
            "tokens": list(tokens),
            "title": title,
            "body": body,
            "data": dict(data),
        }
        self.sent_notifications.append(record)

        # Report invalid tokens if any matched
        invalid_encountered = [t for t in tokens if t in self.invalid_tokens]
        return {
            "success": True,
            "sent": len(tokens) - len(invalid_encountered),
            "invalid_tokens": invalid_encountered,
        }

    async def send_multicast(
        self, tokens: list[str], title: str, body: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        return await self.send_push(tokens, title, body, data)

    @property
    def last_notification(self) -> dict[str, Any] | None:
        return self.sent_notifications[-1] if self.sent_notifications else None

    @property
    def last_tokens(self) -> list[str]:
        return self.sent_notifications[-1]["tokens"] if self.sent_notifications else []

    def reset(self) -> None:
        self.sent_notifications.clear()
        self.send_called = False
        self.fail_mode = False
        self.invalid_tokens.clear()
