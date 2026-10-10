"""Notification API endpoints (Phase 1.6).

Authoritative source: docs/api-contract.md §Notifications, docs/notification-architecture.md.
Endpoints:
- GET   /api/v1/notifications
- GET   /api/v1/notifications/unread-count
- PATCH /api/v1/notifications/{notification_id}/read
- PATCH /api/v1/notifications/read-all
- POST  /api/v1/notifications/devices
"""

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_notification_service
from app.schemas.notification import (
    DeviceTokenRequest,
    DeviceTokenResponse,
    MarkAllReadResponse,
    MarkReadResponse,
    NotificationListResponse,
    UnreadCountResponse,
)
from app.schemas.user import UserResponse
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="List notifications",
    description="Retrieve paginated in-app notifications for the authenticated user.",
)
async def list_notifications(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=50, description="Items per page (max 50)"),
    is_read: bool | None = Query(default=None, description="Optional read status filter"),
    current_user: UserResponse = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationListResponse:
    return await service.list_notifications(
        current_user=current_user,
        page=page,
        page_size=page_size,
        is_read=is_read,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Get unread notifications count",
    description="Return the number of unread in-app notifications for the authenticated user.",
)
async def get_unread_count(
    current_user: UserResponse = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> UnreadCountResponse:
    return await service.get_unread_count(current_user=current_user)


@router.patch(
    "/read-all",
    response_model=MarkAllReadResponse,
    summary="Mark all notifications as read",
    description="Mark all unread in-app notifications as read for the authenticated user.",
)
async def mark_all_read(
    current_user: UserResponse = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> MarkAllReadResponse:
    return await service.mark_all_read(current_user=current_user)


@router.patch(
    "/{notification_id}/read",
    response_model=MarkReadResponse,
    summary="Mark notification as read",
    description="Mark a specific notification as read for the authenticated user.",
)
async def mark_read(
    notification_id: str,
    current_user: UserResponse = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> MarkReadResponse:
    return await service.mark_read(
        notification_id=notification_id,
        current_user=current_user,
    )


@router.post(
    "/devices",
    response_model=DeviceTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Register device token",
    description="Register or upsert a push device token for the authenticated user.",
)
async def register_device(
    request: DeviceTokenRequest,
    current_user: UserResponse = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> DeviceTokenResponse:
    return await service.register_device(
        request=request,
        current_user=current_user,
    )
