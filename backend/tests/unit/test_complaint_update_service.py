"""Phase 1.3.3 — Complaint update service tests.

Covers SERVICE requirements:
- successful update
- authenticated user becomes user_id
- complaint number generated server-side
- initial status is SUBMITTED
- routing is resolved server-side
- invalid category rejected
- invalid routing rejected
- inactive category rejected
- client organization_id cannot override routing
- client department_id cannot override routing
- privileged fields cannot be mass-assigned
- safe response
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

from app.exceptions.base import NotFoundException, ValidationException
from app.schemas.base import ObjectIdStr
from app.schemas.category import CategoryStatus
from app.schemas.complaint import (
    ComplaintStatus,
    ComplaintUpdateRequest,
    ComplaintVisibility,
)
from app.schemas.user import UserResponse, UserRole, UserStatus
from app.services.complaint_service import ComplaintService


@pytest.fixture
def mock_complaint_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_category_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_department_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(
    mock_complaint_repo: AsyncMock,
    mock_category_repo: AsyncMock,
    mock_department_repo: AsyncMock,
) -> ComplaintService:
    return ComplaintService(mock_complaint_repo, mock_category_repo, mock_department_repo)


VALID_USER_ID = "507f1f77bcf86cd799439011"
VALID_ORG_ID = "507f1f77bcf86cd799439012"
VALID_DEPT_ID = "507f1f77bcf86cd799439014"
VALID_CAT_ID = "507f1f77bcf86cd799439015"
VALID_COMPLAINT_ID = "507f1f77bcf86cd799439013"


def make_current_user(**overrides):
    base = {
        "id": VALID_USER_ID,
        "email": "citizen@example.com",
        "phone": "+15551234567",
        "full_name": "Jane Citizen",
        "role": UserRole.CITIZEN,
        "status": UserStatus.ACTIVE,
        "organization_id": None,
        "department_id": None,
        "avatar_url": None,
        "is_verified": True,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return UserResponse(**base)


def make_valid_category(**overrides):
    base = {
        "_id": ObjectId(VALID_CAT_ID),
        "organization_id": VALID_ORG_ID,
        "name": "Pothole",
        "description": "Road surface issues",
        "icon": "pothole",
        "color": "#FF6B35",
        "default_department_id": VALID_DEPT_ID,
        "severity_level": 3,
        "priority_weight": 1.0,
        "status": CategoryStatus.ACTIVE.value,
        "sort_order": 0,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return base


def make_valid_department(**overrides):
    base = {
        "_id": ObjectId(VALID_DEPT_ID),
        "organization_id": VALID_ORG_ID,
        "name": "Road Maintenance",
        "code": "ROADS",
        "description": "Handles road issues",
        "contact_email": "roads@example.com",
        "contact_phone": "+15551234568",
        "head_user_id": None,
        "is_active": True,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return base


def make_complaint_doc(**overrides):
    base = {
        "_id": ObjectId(VALID_COMPLAINT_ID),
        "complaint_number": "CMP-2024-000001",
        "user_id": VALID_USER_ID,
        "organization_id": VALID_ORG_ID,
        "department_id": VALID_DEPT_ID,
        "category_id": VALID_CAT_ID,
        "title": "Large pothole on Main Street",
        "description": "Deep pothole causing vehicle damage near intersection",
        "status": ComplaintStatus.SUBMITTED.value,
        "visibility": ComplaintVisibility.PUBLIC.value,
        "location": {"type": "Point", "coordinates": [-73.9857, 40.7484]},
        "address": "Main St & 1st Ave",
        "assigned_to": None,
        "assigned_at": None,
        "completed_at": None,
        "rejected_at": None,
        "rejection_reason": None,
        "duplicate_of": None,
        "likes_count": 0,
        "community_engagement_score": 0,
        "age_score": 0.0,
        "organization_priority_boost": 0.0,
        "sla_deadline": None,
        "priority_score": 0.0,
        "severity_score": 3,
        "metadata": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return base


def make_request(**overrides):
    base = {
        "title": "Large pothole on Main Street",
        "description": "Deep pothole causing vehicle damage near intersection",
        "location": {"type": "Point", "coordinates": [-73.9857, 40.7484]},
        "address": "Main St & 1st Ave",
    }
    base.update(overrides)
    return ComplaintUpdateRequest(**base)


class TestComplaintServiceUpdateByCitizen:
    async def test_successful_update(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
        mock_category_repo: AsyncMock,
        mock_department_repo: AsyncMock,
    ) -> None:
        current_user = make_current_user()
        # First call returns original complaint, second call returns updated complaint
        original_complaint = make_complaint_doc()
        updated_complaint = make_complaint_doc(title="Updated title")
        mock_complaint_repo.find_by_id_for_user.side_effect = [original_complaint, updated_complaint]
        mock_complaint_repo.update_by_user.return_value = True
        mock_category_repo.find_by_id.return_value = make_valid_category()
        mock_department_repo.find_by_id.return_value = make_valid_department()

        result = await service.update_by_citizen(
            VALID_COMPLAINT_ID, current_user, make_request(title="Updated title")
        )

        assert result.success is True
        assert "Complaint updated successfully" in result.message
        assert result.data.title == "Updated title"
        assert result.data.status == ComplaintStatus.SUBMITTED
        assert result.data.visibility == ComplaintVisibility.PUBLIC
        assert result.data.complaint_number == "CMP-2024-000001"
        assert result.data.category["id"] == VALID_CAT_ID
        assert result.data.category["name"] == "Pothole"
        assert result.data.department["id"] == VALID_DEPT_ID
        assert result.data.department["name"] == "Road Maintenance"

    async def test_user_id_from_authenticated_user(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
        mock_category_repo: AsyncMock,
        mock_department_repo: AsyncMock,
    ) -> None:
        current_user = make_current_user()
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()
        mock_complaint_repo.update_by_user.return_value = True
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()
        mock_category_repo.find_by_id.return_value = make_valid_category()
        mock_department_repo.find_by_id.return_value = make_valid_department()

        await service.update_by_citizen(VALID_COMPLAINT_ID, current_user, make_request())

        call_args = mock_complaint_repo.update_by_user.await_args[0]
        assert call_args[1] == VALID_USER_ID

    async def test_complaint_number_not_changed(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
        mock_category_repo: AsyncMock,
        mock_department_repo: AsyncMock,
    ) -> None:
        current_user = make_current_user()
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()
        mock_complaint_repo.update_by_user.return_value = True
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()
        mock_category_repo.find_by_id.return_value = make_valid_category()
        mock_department_repo.find_by_id.return_value = make_valid_department()

        await service.update_by_citizen(VALID_COMPLAINT_ID, current_user, make_request())

        call_args = mock_complaint_repo.update_by_user.await_args[0][2]
        assert "complaint_number" not in call_args

    async def test_organization_id_not_changed(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
        mock_category_repo: AsyncMock,
        mock_department_repo: AsyncMock,
    ) -> None:
        current_user = make_current_user()
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()
        mock_complaint_repo.update_by_user.return_value = True
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()
        mock_category_repo.find_by_id.return_value = make_valid_category()
        mock_department_repo.find_by_id.return_value = make_valid_department()

        await service.update_by_citizen(VALID_COMPLAINT_ID, current_user, make_request())

        call_args = mock_complaint_repo.update_by_user.await_args[0][2]
        assert "organization_id" not in call_args

    async def test_department_id_not_changed(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
        mock_category_repo: AsyncMock,
        mock_department_repo: AsyncMock,
    ) -> None:
        current_user = make_current_user()
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()
        mock_complaint_repo.update_by_user.return_value = True
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()
        mock_category_repo.find_by_id.return_value = make_valid_category()
        mock_department_repo.find_by_id.return_value = make_valid_department()

        await service.update_by_citizen(VALID_COMPLAINT_ID, current_user, make_request())

        call_args = mock_complaint_repo.update_by_user.await_args[0][2]
        assert "department_id" not in call_args

    async def test_status_not_changed(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
        mock_category_repo: AsyncMock,
        mock_department_repo: AsyncMock,
    ) -> None:
        current_user = make_current_user()
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()
        mock_complaint_repo.update_by_user.return_value = True
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()
        mock_category_repo.find_by_id.return_value = make_valid_category()
        mock_department_repo.find_by_id.return_value = make_valid_department()

        await service.update_by_citizen(VALID_COMPLAINT_ID, current_user, make_request())

        call_args = mock_complaint_repo.update_by_user.await_args[0][2]
        assert "status" not in call_args

    async def test_routing_resolved_server_side(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
        mock_category_repo: AsyncMock,
        mock_department_repo: AsyncMock,
    ) -> None:
        current_user = make_current_user()
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()
        mock_category_repo.find_by_id.return_value = make_valid_category()
        mock_department_repo.find_by_id.return_value = make_valid_department()
        mock_complaint_repo.update_by_user.return_value = True
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()

        await service.update_by_citizen(VALID_COMPLAINT_ID, current_user, make_request())

        call_args = mock_complaint_repo.update_by_user.await_args[0][2]
        # organization_id and department_id are resolved server-side, not in update_data
        assert "organization_id" not in call_args
        assert "department_id" not in call_args
        # But the update should still include the fields that were provided
        assert "title" in call_args

    async def test_invalid_category_rejected(
        self,
        service: ComplaintService,
        mock_category_repo: AsyncMock,
    ) -> None:
        # _validate_category calls find_by_id_active, so we need to mock that
        mock_category_repo.find_by_id_active.return_value = None

        with pytest.raises(NotFoundException) as exc:
            await service.update_by_citizen(
                VALID_COMPLAINT_ID,
                make_current_user(),
                make_request(),
            )

        assert "Category not found or inactive" in str(exc.value)

    async def test_inactive_category_rejected(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
        mock_category_repo: AsyncMock,
    ) -> None:
        # Category exists but is inactive (find_by_id_active returns None)
        category = make_valid_category(status="inactive")
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()
        mock_category_repo.find_by_id_active.return_value = None
        mock_category_repo.find_by_id.return_value = category

        with pytest.raises(NotFoundException):
            await service.update_by_citizen(
                VALID_COMPLAINT_ID,
                make_current_user(),
                make_request(),
            )

    async def test_category_without_default_department_rejected(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
        mock_category_repo: AsyncMock,
    ) -> None:
        # Category is active but has no default_department_id
        category = make_valid_category(default_department_id=None)
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()
        mock_category_repo.find_by_id_active.return_value = category

        with pytest.raises(ValidationException) as exc:
            await service.update_by_citizen(
                VALID_COMPLAINT_ID,
                make_current_user(),
                make_request(),
            )

        assert "Category has no default department configured for routing" in str(exc.value)
        assert exc.value.details["errors"][0]["code"] == "ROUTING_CONFIGURATION_ERROR"

    async def test_department_not_found_rejected(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
        mock_category_repo: AsyncMock,
        mock_department_repo: AsyncMock,
    ) -> None:
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()
        mock_category_repo.find_by_id.return_value = make_valid_category()
        mock_department_repo.find_by_id.return_value = None

        with pytest.raises(NotFoundException):
            await service.update_by_citizen(
                VALID_COMPLAINT_ID,
                make_current_user(),
                make_request(),
            )

    async def test_invalid_status_rejected(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
    ) -> None:
        complaint = make_complaint_doc(status=ComplaintStatus.ONGOING.value)
        mock_complaint_repo.find_by_id_for_user.return_value = complaint

        with pytest.raises(ValidationException) as exc:
            await service.update_by_citizen(
                VALID_COMPLAINT_ID,
                make_current_user(),
                make_request(),
            )

        assert "Complaint can only be updated while in SUBMITTED status" in str(exc.value)

    async def test_empty_update_rejected(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
    ) -> None:
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()

        with pytest.raises(ValidationException) as exc:
            await service.update_by_citizen(
                VALID_COMPLAINT_ID,
                make_current_user(),
                ComplaintUpdateRequest(),  # No fields provided
            )

        assert "At least one field must be provided for update" in str(exc.value)

    async def test_privileged_fields_not_accepted(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
        mock_category_repo: AsyncMock,
        mock_department_repo: AsyncMock,
    ) -> None:
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()
        mock_complaint_repo.update_by_user.return_value = True
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()
        mock_category_repo.find_by_id.return_value = make_valid_category()
        mock_department_repo.find_by_id.return_value = make_valid_department()

        # Verify that the schema rejects extra fields
        from pydantic import ValidationError

        from app.schemas.complaint import ComplaintUpdateRequest

        # Verify that the schema rejects extra fields
        with pytest.raises(ValidationError):
            ComplaintUpdateRequest(
                title="Updated title",
                category_id=ObjectIdStr("507f1f77bcf86cd799439999"),
                status="COMPLETED",
                user_id="507f1f77bcf86cd799439999",
                organization_id="507f1f77bcf86cd799439999",
                department_id="507f1f77bcf86cd799439999",
                complaint_number="CMP-FAKE-000001",
                likes_count=100,
                priority_score=100.0,
            )

    async def test_safe_response_excludes_internal_fields(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
        mock_category_repo: AsyncMock,
        mock_department_repo: AsyncMock,
    ) -> None:
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()
        mock_complaint_repo.update_by_user.return_value = True
        mock_complaint_repo.find_by_id_for_user.return_value = make_complaint_doc()
        mock_category_repo.find_by_id.return_value = make_valid_category()
        mock_department_repo.find_by_id.return_value = make_valid_department()

        result = await service.update_by_citizen(
            VALID_COMPLAINT_ID, make_current_user(), make_request()
        )

        dumped = result.data.model_dump()
        assert "password" not in dumped
        assert "password_hash" not in dumped
        assert "rejection_reason" not in dumped
        assert "duplicate_of" not in dumped
        assert "metadata" not in dumped
        assert "organization_priority_boost" not in dumped
        assert "sla_deadline" not in dumped
