"""Notification service implementation (Phase 1.6).

Authoritative source: docs/notification-architecture.md, docs/api-contract.md, docs/database-schema.md.
Handles in-app notification persistence, push dispatch via provider abstraction,
unread counts, read transitions, and complaint lifecycle triggers.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.exceptions.base import (
    NotFoundException,
    ValidationException,
)
from app.repositories.device_token_repository import DeviceTokenRepository
from app.repositories.notification_repository import NotificationRepository
from app.schemas.base import ObjectIdStr
from app.schemas.notification import (
    DevicePlatform,
    DeviceTokenRequest,
    DeviceTokenResponse,
    DeviceTokenResponseData,
    MarkAllReadData,
    MarkAllReadResponse,
    MarkReadData,
    MarkReadResponse,
    NotificationItem,
    NotificationListData,
    NotificationListResponse,
    NotificationPagination,
    NotificationType,
    UnreadCountData,
    UnreadCountResponse,
)
from app.schemas.user import UserResponse
from app.services.notification_provider import MockNotificationProvider, NotificationProvider

logger = logging.getLogger(__name__)


NOTIFICATION_TEMPLATES: dict[str, dict[str, str]] = {
    "status_update": {
        "title": "Complaint Status Updated",
        "message": "Your complaint '{title}' is now {new_status}",
    },
    "assignment": {
        "title": "New Complaint Assigned",
        "message": "You have been assigned: '{title}'",
    },
    "completion": {
        "title": "Complaint Resolved",
        "message": "Your complaint '{title}' has been completed",
    },
    "rejection": {
        "title": "Complaint Rejected",
        "message": "Your complaint '{title}' was rejected: {reason}",
    },
    "duplicate": {
        "title": "Duplicate Complaint",
        "message": "Your complaint '{title}' is a duplicate of #{ref_number}",
    },
    "comment": {
        "title": "New Update on Your Complaint",
        "message": "{author} added an update to '{title}'",
    },
    "like": {
        "title": "New Like",
        "message": "Someone liked your complaint '{title}'",
    },
    "system": {
        "title": "{custom_title}",
        "message": "{custom_message}",
    },
}


@dataclass
class NotificationPayload:
    user_id: ObjectId | str
    type: NotificationType | str
    title: str
    message: str
    complaint_id: ObjectId | str | None = None
    metadata: dict[str, Any] | None = None
    push: bool = True


class NotificationService:
    """Core domain service for user notifications and push notification dispatch."""

    def __init__(
        self,
        repo: NotificationRepository,
        device_repo: DeviceTokenRepository,
        provider: NotificationProvider | None = None,
    ) -> None:
        self.repo = repo
        self.device_repo = device_repo
        self.provider = provider or MockNotificationProvider()

    async def create_notification(self, payload: NotificationPayload) -> dict[str, Any]:
        """Create an in-app notification and initiate push delivery.

        Guarantees that push failure will never cause the notification or
        caller transaction to fail.
        """
        # Validate notification type
        raw_type = payload.type.value if isinstance(payload.type, NotificationType) else str(payload.type)
        try:
            notif_type = NotificationType(raw_type)
        except ValueError as err:
            raise ValidationException(
                f"Invalid notification type: {raw_type}",
                error_code="INVALID_NOTIFICATION_TYPE",
            ) from err

        user_oid = ObjectId(str(payload.user_id)) if ObjectId.is_valid(str(payload.user_id)) else None
        if not user_oid:
            raise ValidationException("Invalid recipient user_id", error_code="INVALID_USER_ID")

        complaint_oid = (
            ObjectId(str(payload.complaint_id))
            if payload.complaint_id and ObjectId.is_valid(str(payload.complaint_id))
            else None
        )

        now = datetime.now(UTC)
        doc: dict[str, Any] = {
            "user_id": user_oid,
            "complaint_id": complaint_oid,
            "type": notif_type.value,
            "title": payload.title,
            "message": payload.message,
            "is_read": False,
            "read_at": None,
            "metadata": payload.metadata or {},
            "created_at": now,
        }

        notif_id = await self.repo.create(doc)
        doc["_id"] = ObjectId(notif_id)

        # Dispatch push notification if enabled
        if payload.push:
            await self._dispatch_push(doc, payload)

        return doc

    async def _dispatch_push(
        self, notif_doc: dict[str, Any], payload: NotificationPayload
    ) -> None:
        """Fetch recipient device tokens and initiate push sending with retry."""
        try:
            tokens_data = await self.device_repo.get_active_tokens(payload.user_id)
            if not tokens_data:
                return

            token_strings = [str(t["device_token"]) for t in tokens_data if t.get("device_token")]
            if not token_strings:
                return

            push_data = {
                "notification_id": str(notif_doc["_id"]),
                "type": str(notif_doc["type"]),
                "complaint_id": str(notif_doc["complaint_id"]) if notif_doc.get("complaint_id") else "",
                "deep_link": (
                    payload.metadata.get("deep_link", "")
                    if payload.metadata and isinstance(payload.metadata, dict)
                    else ""
                ),
            }

            # Attempt delivery asynchronously with retry
            asyncio.create_task(
                self._send_push_with_retry(
                    tokens=token_strings,
                    title=payload.title,
                    body=payload.message,
                    data=push_data,
                )
            )
        except Exception as exc:
            logger.warning("Error initiating push notification dispatch: %s", exc)

    async def _send_push_with_retry(
        self,
        tokens: list[str],
        title: str,
        body: str,
        data: dict[str, Any],
        max_retries: int = 3,
    ) -> None:
        """Send push notifications with exponential backoff and invalid token deactivation."""
        for attempt in range(max_retries):
            try:
                res: dict[str, Any]
                if len(tokens) == 1:
                    res = await self.provider.send_push(tokens, title, body, data)
                else:
                    res = await self.provider.send_multicast(tokens, title, body, data)

                # Check if provider returned invalid tokens
                if isinstance(res, dict) and "invalid_tokens" in res:
                    for inv_tok in res["invalid_tokens"]:
                        await self.device_repo.mark_token_inactive(str(inv_tok))

                # Update last used timestamp on active tokens
                for tok in tokens:
                    await self.device_repo.update_last_used(tok)
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error("Push notification failed after %d attempts: %s", max_retries, e)
                else:
                    await asyncio.sleep(0.01 * (2**attempt))

    async def list_notifications(
        self,
        current_user: UserResponse,
        page: int = 1,
        page_size: int = 20,
        is_read: bool | None = None,
    ) -> NotificationListResponse:
        """Retrieve paginated in-app notifications for the authenticated user."""
        if page < 1:
            raise ValidationException("Page must be >= 1", error_code="INVALID_PAGE")
        if page_size < 1 or page_size > 50:
            raise ValidationException("Page size must be between 1 and 50", error_code="INVALID_PAGE_SIZE")

        skip = (page - 1) * page_size
        items = await self.repo.list_for_user(
            user_id=str(current_user.id),
            is_read=is_read,
            skip=skip,
            limit=page_size,
        )
        total_items = await self.repo.count_for_user(user_id=str(current_user.id), is_read=is_read)
        total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 0

        parsed_items: list[NotificationItem] = []
        for raw in items:
            parsed_items.append(
                NotificationItem(
                    _id=ObjectIdStr(str(raw["_id"])),
                    user_id=ObjectIdStr(str(raw["user_id"])),
                    complaint_id=ObjectIdStr(str(raw["complaint_id"])) if raw.get("complaint_id") else None,
                    type=NotificationType(raw["type"]),
                    title=str(raw["title"]),
                    message=str(raw["message"]),
                    is_read=bool(raw.get("is_read", False)),
                    read_at=raw.get("read_at"),
                    metadata=raw.get("metadata"),
                    created_at=raw["created_at"],
                )
            )

        return NotificationListResponse(
            success=True,
            message="Notifications retrieved",
            data=NotificationListData(
                items=parsed_items,
                pagination=NotificationPagination(
                    page=page,
                    page_size=page_size,
                    total_items=total_items,
                    total_pages=total_pages,
                    has_next=page < total_pages,
                    has_prev=page > 1 and total_pages > 0,
                ),
            ),
        )

    async def get_unread_count(self, current_user: UserResponse) -> UnreadCountResponse:
        """Calculate unread notifications count for the authenticated user."""
        count = await self.repo.count_unread(str(current_user.id))
        return UnreadCountResponse(
            success=True,
            message="Unread count",
            data=UnreadCountData(count=count),
        )

    async def mark_read(
        self, notification_id: str, current_user: UserResponse
    ) -> MarkReadResponse:
        """Mark a single notification as read, ensuring strict user ownership isolation."""
        if not ObjectId.is_valid(notification_id):
            raise ValidationException("Invalid notification ID format", error_code="INVALID_ID")

        # Verify notification exists and belongs to current user
        existing = await self.repo.find_by_id(notification_id, str(current_user.id))
        if existing is None:
            raise NotFoundException("Notification not found", error_code="NOTIFICATION_NOT_FOUND")

        now = datetime.now(UTC)
        await self.repo.mark_read(notification_id, str(current_user.id), read_at=now)

        return MarkReadResponse(
            success=True,
            message="Notification marked as read",
            data=MarkReadData(
                id=ObjectIdStr(notification_id),
                is_read=True,
                read_at=now,
            ),
        )

    async def mark_all_read(self, current_user: UserResponse) -> MarkAllReadResponse:
        """Mark all unread notifications for current user as read."""
        now = datetime.now(UTC)
        modified_count = await self.repo.mark_all_read(str(current_user.id), read_at=now)
        return MarkAllReadResponse(
            success=True,
            message="All notifications marked as read",
            data=MarkAllReadData(count=modified_count),
        )

    async def register_device(
        self, request: DeviceTokenRequest, current_user: UserResponse
    ) -> DeviceTokenResponse:
        """Register or update device push token for authenticated user."""
        platform_str = (
            request.platform.value
            if hasattr(request.platform, "value")
            else str(request.platform)
        )
        await self.device_repo.upsert_token(
            user_id=str(current_user.id),
            device_token=request.device_token,
            platform=platform_str,
            device_id=request.device_id,
            app_version=request.app_version,
        )
        return DeviceTokenResponse(
            success=True,
            message="Device registered",
            data=DeviceTokenResponseData(
                device_token=request.device_token,
                platform=DevicePlatform(platform_str),
                is_active=True,
            ),
        )
