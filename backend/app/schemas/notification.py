from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import ConfigDict, Field

from app.schemas.base import BaseSchema, ObjectIdStr


class NotificationType(StrEnum):
    STATUS_UPDATE = "status_update"
    ASSIGNMENT = "assignment"
    COMPLETION = "completion"
    REJECTION = "rejection"
    DUPLICATE = "duplicate"
    COMMENT = "comment"
    LIKE = "like"
    SYSTEM = "system"


class DevicePlatform(StrEnum):
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


# -------------------------------------------------------------------------
# Notification Schemas
# -------------------------------------------------------------------------

class NotificationItem(BaseSchema):
    id: ObjectIdStr = Field(..., alias="_id")
    user_id: ObjectIdStr
    complaint_id: ObjectIdStr | None = None
    type: NotificationType
    title: str
    message: str
    is_read: bool = False
    read_at: datetime | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime


class NotificationPagination(BaseSchema):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool


class NotificationListData(BaseSchema):
    items: list[NotificationItem]
    pagination: NotificationPagination


class NotificationListResponse(BaseSchema):
    success: bool = True
    message: str = "Notifications retrieved"
    data: NotificationListData


class UnreadCountData(BaseSchema):
    count: int = Field(..., ge=0)


class UnreadCountResponse(BaseSchema):
    success: bool = True
    message: str = "Unread count"
    data: UnreadCountData


class MarkReadData(BaseSchema):
    id: ObjectIdStr
    is_read: bool = True
    read_at: datetime | None = None


class MarkReadResponse(BaseSchema):
    success: bool = True
    message: str = "Notification marked as read"
    data: MarkReadData


class MarkAllReadData(BaseSchema):
    count: int = Field(..., ge=0)


class MarkAllReadResponse(BaseSchema):
    success: bool = True
    message: str = "All notifications marked as read"
    data: MarkAllReadData


# -------------------------------------------------------------------------
# Device Token Schemas
# -------------------------------------------------------------------------

class DeviceTokenRequest(BaseSchema):
    model_config = ConfigDict(extra="forbid")

    device_token: str = Field(..., min_length=1, max_length=500, description="FCM / APNs device token")
    platform: DevicePlatform = Field(..., description="Platform: ios, android, web")
    device_id: str | None = Field(default=None, max_length=200, description="Unique device identifier")
    app_version: str | None = Field(default=None, max_length=50, description="App version")


class DeviceTokenResponseData(BaseSchema):
    device_token: str
    platform: DevicePlatform
    is_active: bool = True


class DeviceTokenResponse(BaseSchema):
    success: bool = True
    message: str = "Device registered"
    data: DeviceTokenResponseData | None = None
