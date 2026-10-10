"""Unit tests for NotificationService, NotificationRepository, and MockNotificationProvider (Phase 1.6)."""

from datetime import UTC, datetime

import pytest

from app.exceptions.base import NotFoundException, ValidationException
from app.schemas.base import ObjectIdStr
from app.schemas.notification import DevicePlatform, DeviceTokenRequest, NotificationType
from app.schemas.user import UserResponse, UserRole, UserStatus
from app.services.notification_provider import MockNotificationProvider
from app.services.notification_service import NotificationPayload, NotificationService
from tests.fakes import FakeDeviceTokenRepository, FakeNotificationRepository


def make_user(
    user_id: str = "507f1f77bcf86cd799439011",
    role: UserRole = UserRole.CITIZEN,
) -> UserResponse:
    now = datetime.now(UTC)
    return UserResponse(
        id=ObjectIdStr(user_id),
        email="citizen@example.com",
        phone="+919876543210",
        full_name="Citizen User",
        role=role,
        status=UserStatus.ACTIVE,
        is_verified=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def fake_notif_repo() -> FakeNotificationRepository:
    return FakeNotificationRepository()


@pytest.fixture
def fake_device_repo() -> FakeDeviceTokenRepository:
    return FakeDeviceTokenRepository()


@pytest.fixture
def mock_provider() -> MockNotificationProvider:
    return MockNotificationProvider()


@pytest.fixture
def notification_service(
    fake_notif_repo: FakeNotificationRepository,
    fake_device_repo: FakeDeviceTokenRepository,
    mock_provider: MockNotificationProvider,
) -> NotificationService:
    return NotificationService(
        repo=fake_notif_repo,
        device_repo=fake_device_repo,
        provider=mock_provider,
    )


class TestNotificationServiceLifecycle:
    @pytest.mark.asyncio
    async def test_create_in_app_notification_succeeds(
        self, notification_service: NotificationService, fake_notif_repo: FakeNotificationRepository
    ) -> None:
        user_id = "507f1f77bcf86cd799439011"
        payload = NotificationPayload(
            user_id=user_id,
            type=NotificationType.STATUS_UPDATE,
            title="Status Changed",
            message="Your complaint is ongoing",
            complaint_id="507f1f77bcf86cd799439012",
            metadata={"new_status": "ONGOING"},
            push=False,
        )
        notif = await notification_service.create_notification(payload)
        assert notif["title"] == "Status Changed"
        assert notif["type"] == "status_update"
        assert notif["is_read"] is False
        assert await fake_notif_repo.count_unread(user_id) == 1

    @pytest.mark.asyncio
    async def test_invalid_notification_type_rejected(
        self, notification_service: NotificationService
    ) -> None:
        payload = NotificationPayload(
            user_id="507f1f77bcf86cd799439011",
            type="invalid_custom_type",
            title="Invalid",
            message="Message",
        )
        with pytest.raises(ValidationException) as exc:
            await notification_service.create_notification(payload)
        assert exc.value.error_code == "INVALID_NOTIFICATION_TYPE"

    @pytest.mark.asyncio
    async def test_invalid_user_id_rejected(
        self, notification_service: NotificationService
    ) -> None:
        payload = NotificationPayload(
            user_id="not-an-objectid",
            type=NotificationType.SYSTEM,
            title="System Alert",
            message="Maintenance tonight",
        )
        with pytest.raises(ValidationException) as exc:
            await notification_service.create_notification(payload)
        assert exc.value.error_code == "INVALID_USER_ID"

    @pytest.mark.asyncio
    async def test_push_dispatch_to_registered_device(
        self,
        notification_service: NotificationService,
        fake_device_repo: FakeDeviceTokenRepository,
        mock_provider: MockNotificationProvider,
    ) -> None:
        user_id = "507f1f77bcf86cd799439011"
        # Register a device token for user
        await fake_device_repo.upsert_token(
            user_id=user_id,
            device_token="fcm_valid_token_123",
            platform="android",
        )

        payload = NotificationPayload(
            user_id=user_id,
            type=NotificationType.ASSIGNMENT,
            title="Complaint Assigned",
            message="You have been assigned to road repair",
            complaint_id="507f1f77bcf86cd799439013",
            push=True,
        )
        await notification_service.create_notification(payload)

        # Allow background task to execute
        import asyncio
        await asyncio.sleep(0.05)

        assert mock_provider.send_called is True
        assert mock_provider.last_tokens == ["fcm_valid_token_123"]
        assert mock_provider.last_notification["title"] == "Complaint Assigned"

    @pytest.mark.asyncio
    async def test_push_failure_does_not_abort_in_app_notification(
        self,
        notification_service: NotificationService,
        fake_device_repo: FakeDeviceTokenRepository,
        fake_notif_repo: FakeNotificationRepository,
        mock_provider: MockNotificationProvider,
    ) -> None:
        user_id = "507f1f77bcf86cd799439011"
        await fake_device_repo.upsert_token(
            user_id=user_id,
            device_token="fcm_failing_token",
            platform="ios",
        )
        mock_provider.fail_mode = True

        payload = NotificationPayload(
            user_id=user_id,
            type=NotificationType.STATUS_UPDATE,
            title="Status update",
            message="Your complaint updated",
            push=True,
        )
        # Should not raise exception
        notif = await notification_service.create_notification(payload)
        assert notif is not None
        assert await fake_notif_repo.count_unread(user_id) == 1

    @pytest.mark.asyncio
    async def test_invalid_token_marked_inactive(
        self,
        notification_service: NotificationService,
        fake_device_repo: FakeDeviceTokenRepository,
        mock_provider: MockNotificationProvider,
    ) -> None:
        user_id = "507f1f77bcf86cd799439011"
        bad_token = "fcm_dead_token"
        await fake_device_repo.upsert_token(
            user_id=user_id,
            device_token=bad_token,
            platform="android",
        )
        mock_provider.invalid_tokens.add(bad_token)

        payload = NotificationPayload(
            user_id=user_id,
            type=NotificationType.SYSTEM,
            title="System Alert",
            message="Hello",
            push=True,
        )
        await notification_service.create_notification(payload)
        import asyncio
        await asyncio.sleep(0.05)

        # Token should be marked inactive
        active_tokens = await fake_device_repo.get_active_tokens(user_id)
        assert len(active_tokens) == 0


class TestNotificationReadOperations:
    @pytest.mark.asyncio
    async def test_unread_count_calculation(
        self, notification_service: NotificationService, fake_notif_repo: FakeNotificationRepository
    ) -> None:
        user = make_user()
        for i in range(3):
            await fake_notif_repo.create({
                "user_id": str(user.id),
                "type": "status_update",
                "title": f"Update {i}",
                "message": f"Message {i}",
                "is_read": False,
            })
        resp = await notification_service.get_unread_count(user)
        assert resp.data.count == 3

    @pytest.mark.asyncio
    async def test_mark_read_single_notification(
        self, notification_service: NotificationService, fake_notif_repo: FakeNotificationRepository
    ) -> None:
        user = make_user()
        nid = await fake_notif_repo.create({
            "user_id": str(user.id),
            "type": "status_update",
            "title": "Title",
            "message": "Body",
            "is_read": False,
        })
        resp = await notification_service.mark_read(nid, user)
        assert resp.data.is_read is True
        assert await fake_notif_repo.count_unread(str(user.id)) == 0

    @pytest.mark.asyncio
    async def test_mark_read_other_user_notification_fails(
        self, notification_service: NotificationService, fake_notif_repo: FakeNotificationRepository
    ) -> None:
        owner_id = "507f1f77bcf86cd799439011"
        attacker = make_user(user_id="507f1f77bcf86cd799439022")
        nid = await fake_notif_repo.create({
            "user_id": owner_id,
            "type": "status_update",
            "title": "Private notification",
            "message": "Private body",
            "is_read": False,
        })

        with pytest.raises(NotFoundException) as exc:
            await notification_service.mark_read(nid, attacker)
        assert exc.value.error_code == "NOTIFICATION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_mark_all_read_affects_only_current_user(
        self, notification_service: NotificationService, fake_notif_repo: FakeNotificationRepository
    ) -> None:
        user1 = make_user(user_id="507f1f77bcf86cd799439011")
        user2 = make_user(user_id="507f1f77bcf86cd799439022")

        # user1 has 2 unread
        await fake_notif_repo.create({"user_id": str(user1.id), "type": "system", "title": "U1-A", "message": "msg", "is_read": False})
        await fake_notif_repo.create({"user_id": str(user1.id), "type": "system", "title": "U1-B", "message": "msg", "is_read": False})

        # user2 has 1 unread
        await fake_notif_repo.create({"user_id": str(user2.id), "type": "system", "title": "U2-A", "message": "msg", "is_read": False})

        resp = await notification_service.mark_all_read(user1)
        assert resp.data.count == 2
        assert await fake_notif_repo.count_unread(str(user1.id)) == 0
        assert await fake_notif_repo.count_unread(str(user2.id)) == 1


class TestDeviceTokenRegistration:
    @pytest.mark.asyncio
    async def test_register_device_token_upsert(
        self, notification_service: NotificationService, fake_device_repo: FakeDeviceTokenRepository
    ) -> None:
        user = make_user()
        req = DeviceTokenRequest(
            device_token="fcm_token_xyz",
            platform=DevicePlatform.ANDROID,
            device_id="device_uuid_999",
            app_version="1.2.0",
        )
        resp = await notification_service.register_device(req, user)
        assert resp.success is True
        assert resp.data.device_token == "fcm_token_xyz"

        tokens = await fake_device_repo.get_active_tokens(str(user.id))
        assert len(tokens) == 1
        assert tokens[0]["device_id"] == "device_uuid_999"

        # Re-registering the same token updates it without duplicate
        req2 = DeviceTokenRequest(
            device_token="fcm_token_xyz",
            platform=DevicePlatform.ANDROID,
            device_id="device_uuid_999",
            app_version="1.2.1",
        )
        await notification_service.register_device(req2, user)
        tokens_after = await fake_device_repo.get_active_tokens(str(user.id))
        assert len(tokens_after) == 1
        assert tokens_after[0]["app_version"] == "1.2.1"
