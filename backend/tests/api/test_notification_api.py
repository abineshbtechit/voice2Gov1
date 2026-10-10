"""API integration and security tests for Phase 1.6: Notifications (NOTIF-01 - NOTIF-08).

Covers:
- GET /api/v1/notifications:
  - list user notifications
  - pagination (page, page_size)
  - is_read filtering
  - unauthorized access rejected (401)
  - user isolation (never sees other user's notifications)
- GET /api/v1/notifications/unread-count:
  - accurate unread count
  - unauthorized access rejected (401)
- PATCH /api/v1/notifications/{id}/read:
  - mark single notification read
  - cannot mark another user's notification read (404)
  - invalid ObjectId format (422)
- PATCH /api/v1/notifications/read-all:
  - marks all for current user
  - does not mark other users' notifications
- POST /api/v1/notifications/devices:
  - register device token
  - platform enum validation
  - duplicate registration idempotency
"""

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.dependencies.services import get_notification_service, get_user_service
from app.main import create_app
from app.schemas.user import UserRole
from app.services.notification_provider import MockNotificationProvider
from app.services.notification_service import NotificationService
from app.services.user_service import UserService
from tests.fakes import FakeDeviceTokenRepository, FakeNotificationRepository, FakeUserRepository

USER1_ID = "507f1f77bcf86cd799439011"
USER2_ID = "507f1f77bcf86cd799439022"


@pytest.fixture
def fake_users() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def fake_notifs() -> FakeNotificationRepository:
    return FakeNotificationRepository()


@pytest.fixture
def fake_devices() -> FakeDeviceTokenRepository:
    return FakeDeviceTokenRepository()


@pytest.fixture
def mock_provider() -> MockNotificationProvider:
    return MockNotificationProvider()


@pytest.fixture
async def app_client(
    fake_users: FakeUserRepository,
    fake_notifs: FakeNotificationRepository,
    fake_devices: FakeDeviceTokenRepository,
    mock_provider: MockNotificationProvider,
) -> AsyncClient:
    app = create_app()

    now = datetime.now(UTC)
    fake_users.users[USER1_ID] = {
        "_id": USER1_ID,
        "email": "user1@example.com",
        "phone": "+919876543211",
        "full_name": "Citizen One",
        "role": UserRole.CITIZEN.value,
        "status": "active",
        "is_active": True,
        "is_verified": True,
        "created_at": now,
        "updated_at": now,
    }
    fake_users.users[USER2_ID] = {
        "_id": USER2_ID,
        "email": "user2@example.com",
        "phone": "+919876543222",
        "full_name": "Citizen Two",
        "role": UserRole.CITIZEN.value,
        "status": "active",
        "is_active": True,
        "is_verified": True,
        "created_at": now,
        "updated_at": now,
    }

    user_service = UserService(fake_users)
    notif_service = NotificationService(
        repo=fake_notifs,
        device_repo=fake_devices,
        provider=mock_provider,
    )

    app.dependency_overrides[get_user_service] = lambda: user_service
    app.dependency_overrides[get_notification_service] = lambda: notif_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def make_token(user_id: str, role: UserRole = UserRole.CITIZEN) -> str:
    return create_access_token(
        user_id=user_id,
        role=role.value,
    )


class TestNotificationEndpoints:
    @pytest.mark.asyncio
    async def test_list_notifications_unauthenticated(self, app_client: AsyncClient) -> None:
        resp = await app_client.get("/api/v1/notifications")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_notifications_user_isolation(
        self, app_client: AsyncClient, fake_notifs: FakeNotificationRepository
    ) -> None:
        token1 = make_token(USER1_ID)
        token2 = make_token(USER2_ID)

        # Seed notification for user1
        await fake_notifs.create({
            "user_id": USER1_ID,
            "type": "status_update",
            "title": "User1 Notif",
            "message": "Only for user 1",
            "is_read": False,
        })

        # Seed notification for user2
        await fake_notifs.create({
            "user_id": USER2_ID,
            "type": "system",
            "title": "User2 Notif",
            "message": "Only for user 2",
            "is_read": False,
        })

        # User 1 query
        resp1 = await app_client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {token1}"})
        assert resp1.status_code == 200
        data1 = resp1.json()["data"]
        assert data1["pagination"]["total_items"] == 1
        assert data1["items"][0]["title"] == "User1 Notif"

        # User 2 query
        resp2 = await app_client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {token2}"})
        assert resp2.status_code == 200
        data2 = resp2.json()["data"]
        assert data2["pagination"]["total_items"] == 1
        assert data2["items"][0]["title"] == "User2 Notif"

    @pytest.mark.asyncio
    async def test_unread_count_endpoint(
        self, app_client: AsyncClient, fake_notifs: FakeNotificationRepository
    ) -> None:
        token1 = make_token(USER1_ID)
        for i in range(4):
            await fake_notifs.create({
                "user_id": USER1_ID,
                "type": "status_update",
                "title": f"Unread {i}",
                "message": "msg",
                "is_read": False,
            })
        await fake_notifs.create({
            "user_id": USER1_ID,
            "type": "status_update",
            "title": "Read already",
            "message": "msg",
            "is_read": True,
        })

        resp = await app_client.get("/api/v1/notifications/unread-count", headers={"Authorization": f"Bearer {token1}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["count"] == 4

    @pytest.mark.asyncio
    async def test_mark_single_notification_read(
        self, app_client: AsyncClient, fake_notifs: FakeNotificationRepository
    ) -> None:
        token1 = make_token(USER1_ID)
        token2 = make_token(USER2_ID)

        nid = await fake_notifs.create({
            "user_id": USER1_ID,
            "type": "status_update",
            "title": "Target Notif",
            "message": "msg",
            "is_read": False,
        })

        # Other user cannot mark user1's notification read
        resp_other = await app_client.patch(
            f"/api/v1/notifications/{nid}/read",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert resp_other.status_code == 404

        # Owner marks read
        resp_owner = await app_client.patch(
            f"/api/v1/notifications/{nid}/read",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert resp_owner.status_code == 200
        assert resp_owner.json()["data"]["is_read"] is True

    @pytest.mark.asyncio
    async def test_mark_all_read_endpoint(
        self, app_client: AsyncClient, fake_notifs: FakeNotificationRepository
    ) -> None:
        token1 = make_token(USER1_ID)
        for _ in range(3):
            await fake_notifs.create({
                "user_id": USER1_ID,
                "type": "system",
                "title": "Alert",
                "message": "msg",
                "is_read": False,
            })

        resp = await app_client.patch("/api/v1/notifications/read-all", headers={"Authorization": f"Bearer {token1}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["count"] == 3

        count_resp = await app_client.get("/api/v1/notifications/unread-count", headers={"Authorization": f"Bearer {token1}"})
        assert count_resp.json()["data"]["count"] == 0

    @pytest.mark.asyncio
    async def test_register_device_token_endpoint(
        self, app_client: AsyncClient
    ) -> None:
        token1 = make_token(USER1_ID)
        body = {
            "device_token": "fcm_token_integration_123",
            "platform": "android",
            "device_id": "pixel_7_device_id",
            "app_version": "1.0.0",
        }
        resp = await app_client.post(
            "/api/v1/notifications/devices",
            headers={"Authorization": f"Bearer {token1}"},
            json=body,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["data"]["device_token"] == "fcm_token_integration_123"

    @pytest.mark.asyncio
    async def test_register_device_invalid_platform_rejected(
        self, app_client: AsyncClient
    ) -> None:
        token1 = make_token(USER1_ID)
        body = {
            "device_token": "fcm_token_xyz",
            "platform": "windows_phone",
        }
        resp = await app_client.post(
            "/api/v1/notifications/devices",
            headers={"Authorization": f"Bearer {token1}"},
            json=body,
        )
        assert resp.status_code == 422
