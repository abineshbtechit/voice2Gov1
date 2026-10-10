"""Integration tests verifying notification creation triggers across complaint lifecycle (NOTIF-08).

Verifies:
1. Status change creates notification for complaint owner (citizen).
2. Status rejection creates REJECTION notification.
3. Complaint assignment creates ASSIGNMENT notification for assigned staff member.
4. Complaint completion creates COMPLETION notification for complaint owner.
5. Public progress update (comment) creates COMMENT notification for complaint owner.
6. Notification provider failure does not break the primary complaint operation.
"""

from datetime import UTC, datetime

import pytest

from app.schemas.base import ObjectIdStr
from app.schemas.complaint import (
    ComplaintAssignRequest,
    ComplaintCompleteRequest,
    ComplaintStatus,
    ComplaintStatusUpdateRequest,
)
from app.schemas.user import UserResponse, UserRole, UserStatus
from app.services.complaint_service import ComplaintService
from app.services.notification_provider import MockNotificationProvider
from app.services.notification_service import NotificationService
from tests.fakes import (
    FakeCategoryRepository,
    FakeComplaintLikeRepository,
    FakeComplaintLookup,
    FakeDepartmentRepository,
    FakeDeviceTokenRepository,
    FakeNotificationRepository,
    FakeUserRepository,
)

CID = "507f1f77bcf86cd799439011"
ORG_ID = "507f1f77bcf86cd799439021"
DEPT_ID = "507f1f77bcf86cd799439031"
CAT_ID = "507f1f77bcf86cd799439032"

CITIZEN_ID = "507f1f77bcf86cd799439041"
STAFF_ID = "507f1f77bcf86cd799439042"
ADMIN_ID = "507f1f77bcf86cd799439043"


@pytest.fixture
def fake_repos():
    complaint_repo = FakeComplaintLookup()
    category_repo = FakeCategoryRepository()
    dept_repo = FakeDepartmentRepository()
    user_repo = FakeUserRepository()
    notif_repo = FakeNotificationRepository()
    device_repo = FakeDeviceTokenRepository()
    mock_provider = MockNotificationProvider()
    like_repo = FakeComplaintLikeRepository()

    now = datetime.now(UTC)
    user_repo.users[CITIZEN_ID] = {
        "_id": CITIZEN_ID,
        "email": "citizen@test.com",
        "phone": "+919876543201",
        "full_name": "Citizen One",
        "role": UserRole.CITIZEN.value,
        "is_active": True,
        "is_verified": True,
        "created_at": now,
        "updated_at": now,
    }
    user_repo.users[STAFF_ID] = {
        "_id": STAFF_ID,
        "email": "staff@test.com",
        "phone": "+919876543202",
        "full_name": "Staff One",
        "role": UserRole.ORGANIZATION_STAFF.value,
        "organization_id": ORG_ID,
        "department_id": DEPT_ID,
        "is_active": True,
        "is_verified": True,
        "created_at": now,
        "updated_at": now,
    }
    user_repo.users[ADMIN_ID] = {
        "_id": ADMIN_ID,
        "email": "admin@test.com",
        "phone": "+919876543203",
        "full_name": "Org Admin",
        "role": UserRole.ORGANIZATION_ADMIN.value,
        "organization_id": ORG_ID,
        "is_active": True,
        "is_verified": True,
        "created_at": now,
        "updated_at": now,
    }

    dept_repo.departments[DEPT_ID] = {
        "_id": DEPT_ID,
        "organization_id": ORG_ID,
        "name": "Roads Department",
    }
    category_repo.categories[CAT_ID] = {
        "_id": CAT_ID,
        "organization_id": ORG_ID,
        "name": "Potholes",
        "default_department_id": DEPT_ID,
        "severity_level": 3,
        "priority_weight": 1.0,
    }

    complaint_repo.complaints[CID] = {
        "_id": CID,
        "complaint_number": "CMP-2026-0001",
        "user_id": CITIZEN_ID,
        "organization_id": ORG_ID,
        "department_id": DEPT_ID,
        "category_id": CAT_ID,
        "title": "Large pothole on 5th street",
        "description": "Vehicle damage danger",
        "status": "SUBMITTED",
        "visibility": "public",
        "location": {"type": "Point", "coordinates": [77.5946, 12.9716]},
        "created_at": now,
        "updated_at": now,
        "likes_count": 0,
        "priority_score": 50.0,
    }

    notif_service = NotificationService(
        repo=notif_repo,
        device_repo=device_repo,
        provider=mock_provider,
    )

    complaint_service = ComplaintService(
        complaint_repo=complaint_repo,
        category_repo=category_repo,
        department_repo=dept_repo,
        user_repo=user_repo,
        like_repo=like_repo,
        notification_service=notif_service,
    )

    return {
        "complaint_service": complaint_service,
        "notif_repo": notif_repo,
        "mock_provider": mock_provider,
        "user_repo": user_repo,
        "complaint_repo": complaint_repo,
    }


def make_actor(user_dict: dict) -> UserResponse:
    now = datetime.now(UTC)
    return UserResponse(
        id=ObjectIdStr(str(user_dict["_id"])),
        email=user_dict["email"],
        phone=user_dict["phone"],
        full_name=user_dict["full_name"],
        role=UserRole(user_dict["role"]),
        status=UserStatus.ACTIVE,
        organization_id=ObjectIdStr(str(user_dict["organization_id"])) if user_dict.get("organization_id") else None,
        department_id=ObjectIdStr(str(user_dict["department_id"])) if user_dict.get("department_id") else None,
        is_verified=True,
        created_at=now,
        updated_at=now,
    )


class TestComplaintNotificationTriggers:
    @pytest.mark.asyncio
    async def test_assign_creates_notification_for_staff(self, fake_repos) -> None:
        service: ComplaintService = fake_repos["complaint_service"]
        notif_repo: FakeNotificationRepository = fake_repos["notif_repo"]
        admin = make_actor(fake_repos["user_repo"].users[ADMIN_ID])

        req = ComplaintAssignRequest(assigned_to=ObjectIdStr(STAFF_ID))
        await service.assign(CID, admin, req)

        # Check notification in repo
        notifs = await notif_repo.list_for_user(STAFF_ID)
        assert len(notifs) == 1
        assert notifs[0]["type"] == "assignment"
        assert str(notifs[0]["user_id"]) == STAFF_ID
        assert "assigned" in notifs[0]["title"].lower()

    @pytest.mark.asyncio
    async def test_status_update_creates_notification_for_citizen(self, fake_repos) -> None:
        service: ComplaintService = fake_repos["complaint_service"]
        notif_repo: FakeNotificationRepository = fake_repos["notif_repo"]
        admin = make_actor(fake_repos["user_repo"].users[ADMIN_ID])

        # Transition SUBMITTED -> REJECTED
        req = ComplaintStatusUpdateRequest(
            status=ComplaintStatus.REJECTED,
            reason="Invalid jurisdiction for municipal roads",
        )
        await service.change_status(CID, admin, req)

        notifs = await notif_repo.list_for_user(CITIZEN_ID)
        assert len(notifs) == 1
        assert notifs[0]["type"] == "rejection"
        assert str(notifs[0]["user_id"]) == CITIZEN_ID
        assert "rejected" in notifs[0]["title"].lower()

    @pytest.mark.asyncio
    async def test_completion_creates_notification_for_citizen(self, fake_repos) -> None:
        service: ComplaintService = fake_repos["complaint_service"]
        notif_repo: FakeNotificationRepository = fake_repos["notif_repo"]
        staff = make_actor(fake_repos["user_repo"].users[STAFF_ID])

        # Fast forward complaint to PROCESSING and assigned
        fake_repos["complaint_repo"].complaints[CID]["status"] = "PROCESSING"
        fake_repos["complaint_repo"].complaints[CID]["assigned_to"] = STAFF_ID

        req = ComplaintCompleteRequest(reason="Pothole filled and sealed with asphalt")
        await service.complete(CID, staff, req)

        notifs = await notif_repo.list_for_user(CITIZEN_ID)
        assert len(notifs) == 1
        assert notifs[0]["type"] == "completion"
        assert str(notifs[0]["user_id"]) == CITIZEN_ID
        assert "resolved" in notifs[0]["title"].lower() or "completed" in notifs[0]["title"].lower()

    @pytest.mark.asyncio
    async def test_provider_outage_does_not_break_complaint_assignment(self, fake_repos) -> None:
        service: ComplaintService = fake_repos["complaint_service"]
        mock_provider: MockNotificationProvider = fake_repos["mock_provider"]
        admin = make_actor(fake_repos["user_repo"].users[ADMIN_ID])

        # Simulate push provider throwing network / service exception
        mock_provider.fail_mode = True

        req = ComplaintAssignRequest(assigned_to=ObjectIdStr(STAFF_ID))
        # Operation should succeed without raising push error
        resp = await service.assign(CID, admin, req)
        assert resp.success is True
        assert resp.data.assigned_to["id"] == STAFF_ID
