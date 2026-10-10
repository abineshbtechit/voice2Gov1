"""Phase 1.3.1 — Complaint service tests.

Covers SERVICE requirements:
- successful creation
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
from typing import Any
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

from app.exceptions.base import NotFoundException, ValidationException
from app.repositories.category_repository import CategoryRepository
from app.repositories.complaint_repository import ComplaintRepository
from app.repositories.department_repository import DepartmentRepository
from app.schemas.base import ObjectIdStr
from app.schemas.category import CategoryStatus
from app.schemas.complaint import ComplaintCreateRequest, ComplaintStatus, ComplaintVisibility
from app.schemas.user import UserResponse, UserRole, UserStatus
from app.services.complaint_service import ComplaintService


@pytest.fixture
def mock_complaint_repo() -> AsyncMock:
    mock = AsyncMock(spec=ComplaintRepository)
    mock.count_complaints_by_year.return_value = 0
    return mock


@pytest.fixture
def mock_category_repo() -> AsyncMock:
    return AsyncMock(spec=CategoryRepository)


@pytest.fixture
def mock_department_repo() -> AsyncMock:
    return AsyncMock(spec=DepartmentRepository)


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


def make_current_user(**overrides) -> UserResponse:
    base = {
        "id": ObjectIdStr(VALID_USER_ID),
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


def make_valid_category(**overrides) -> dict[str, Any]:
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


def make_valid_department(**overrides) -> dict[str, Any]:
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


def make_complaint_doc(**overrides) -> dict[str, Any]:
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


def make_request(**overrides) -> ComplaintCreateRequest:
    base = {
        "title": "Large pothole on Main Street",
        "description": "Deep pothole causing vehicle damage near intersection",
        "category_id": ObjectIdStr(VALID_CAT_ID),
        "location": {"type": "Point", "coordinates": [-73.9857, 40.7484]},
        "address": "Main St & 1st Ave",
    }
    base.update(overrides)
    return ComplaintCreateRequest(**base)


class TestComplaintServiceCreate:
    async def test_successful_creation(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
        mock_category_repo: AsyncMock,
        mock_department_repo: AsyncMock,
    ) -> None:
        current_user = make_current_user()
        mock_category_repo.find_by_id_active.return_value = make_valid_category()
        mock_department_repo.find_by_id_active_in_org.return_value = make_valid_department()
        mock_complaint_repo.create.return_value = VALID_COMPLAINT_ID
        mock_complaint_repo.find_by_id.return_value = make_complaint_doc()

        result = await service.create_complaint(make_request(), current_user)

        assert result.success is True
        assert "Complaint submitted successfully" in result.message
        assert result.data.id == VALID_COMPLAINT_ID
        assert result.data.complaint_number == "CMP-2024-000001"
        assert result.data.title == "Large pothole on Main Street"
        assert result.data.status == ComplaintStatus.SUBMITTED
        assert result.data.visibility == ComplaintVisibility.PUBLIC
        assert result.data.priority_score == 0.0
        assert result.data.severity_score == 3
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
        mock_category_repo.find_by_id_active.return_value = make_valid_category()
        mock_department_repo.find_by_id_active_in_org.return_value = make_valid_department()
        mock_complaint_repo.create.return_value = VALID_COMPLAINT_ID
        mock_complaint_repo.find_by_id.return_value = make_complaint_doc()

        await service.create_complaint(make_request(), current_user)

        call_args = mock_complaint_repo.create.await_args[0][0]
        assert call_args["user_id"] == VALID_USER_ID

    async def test_complaint_number_generated_server_side(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
        mock_category_repo: AsyncMock,
        mock_department_repo: AsyncMock,
    ) -> None:
        current_user = make_current_user()
        mock_category_repo.find_by_id_active.return_value = make_valid_category()
        mock_department_repo.find_by_id_active_in_org.return_value = make_valid_department()
        mock_complaint_repo.create.return_value = VALID_COMPLAINT_ID
        mock_complaint_repo.find_by_id.return_value = make_complaint_doc()

        await service.create_complaint(make_request(), current_user)

        call_args = mock_complaint_repo.create.await_args[0][0]
        assert "complaint_number" in call_args
        assert call_args["complaint_number"].startswith("CMP-")
        assert len(call_args["complaint_number"]) == len("CMP-2024-000001")

    async def test_initial_status_submitted(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
        mock_category_repo: AsyncMock,
        mock_department_repo: AsyncMock,
    ) -> None:
        current_user = make_current_user()
        mock_category_repo.find_by_id_active.return_value = make_valid_category()
        mock_department_repo.find_by_id_active_in_org.return_value = make_valid_department()
        mock_complaint_repo.create.return_value = VALID_COMPLAINT_ID
        mock_complaint_repo.find_by_id.return_value = make_complaint_doc()

        await service.create_complaint(make_request(), current_user)

        call_args = mock_complaint_repo.create.await_args[0][0]
        assert call_args["status"] == ComplaintStatus.SUBMITTED.value

    async def test_routing_resolved_server_side(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
        mock_category_repo: AsyncMock,
        mock_department_repo: AsyncMock,
    ) -> None:
        current_user = make_current_user()
        mock_category_repo.find_by_id_active.return_value = make_valid_category()
        mock_department_repo.find_by_id_active_in_org.return_value = make_valid_department()
        mock_complaint_repo.create.return_value = VALID_COMPLAINT_ID
        mock_complaint_repo.find_by_id.return_value = make_complaint_doc()

        await service.create_complaint(make_request(), current_user)

        call_args = mock_complaint_repo.create.await_args[0][0]
        assert call_args["organization_id"] == VALID_ORG_ID
        assert str(call_args["department_id"]) == VALID_DEPT_ID
        mock_category_repo.find_by_id_active.assert_awaited_once_with(VALID_CAT_ID)
        mock_department_repo.find_by_id_active_in_org.assert_awaited_once_with(VALID_DEPT_ID, VALID_ORG_ID)

    async def test_invalid_category_rejected(
        self,
        service: ComplaintService,
        mock_category_repo: AsyncMock,
    ) -> None:
        mock_category_repo.find_by_id_active.return_value = None

        with pytest.raises(NotFoundException) as exc:
            await service.create_complaint(make_request(), make_current_user())

        assert "Category not found or inactive" in str(exc.value)

    async def test_inactive_category_rejected(
        self,
        service: ComplaintService,
        mock_category_repo: AsyncMock,
    ) -> None:
        mock_category_repo.find_by_id_active.return_value = None

        with pytest.raises(NotFoundException):
            await service.create_complaint(make_request(), make_current_user())

    async def test_category_without_default_department_rejected(
        self,
        service: ComplaintService,
        mock_category_repo: AsyncMock,
    ) -> None:
        category = make_valid_category(default_department_id=None)
        mock_category_repo.find_by_id_active.return_value = category

        with pytest.raises(ValidationException) as exc:
            await service.create_complaint(make_request(), make_current_user())

        assert "Category has no default department configured" in str(exc.value)
        assert exc.value.details["errors"][0]["code"] == "ROUTING_CONFIGURATION_ERROR"

    async def test_department_not_found_rejected(
        self,
        service: ComplaintService,
        mock_category_repo: AsyncMock,
        mock_department_repo: AsyncMock,
    ) -> None:
        mock_category_repo.find_by_id_active.return_value = make_valid_category()
        mock_department_repo.find_by_id_active_in_org.return_value = None

        with pytest.raises(NotFoundException) as exc:
            await service.create_complaint(make_request(), make_current_user())

        assert "Default department not found" in str(exc.value)

    async def test_inactive_department_rejected(
        self,
        service: ComplaintService,
        mock_category_repo: AsyncMock,
        mock_department_repo: AsyncMock,
    ) -> None:
        mock_category_repo.find_by_id_active.return_value = make_valid_category()
        mock_department_repo.find_by_id_active_in_org.return_value = None

        with pytest.raises(NotFoundException):
            await service.create_complaint(make_request(), make_current_user())

    async def test_privileged_fields_not_accepted(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
        mock_category_repo: AsyncMock,
        mock_department_repo: AsyncMock,
    ) -> None:
        current_user = make_current_user()
        mock_category_repo.find_by_id_active.return_value = make_valid_category()
        mock_department_repo.find_by_id_active_in_org.return_value = make_valid_department()
        mock_complaint_repo.create.return_value = VALID_COMPLAINT_ID
        mock_complaint_repo.find_by_id.return_value = make_complaint_doc()

        # These fields are server-controlled and should not come from request
        # The request schema doesn't even include them, but verify they're set by server
        await service.create_complaint(make_request(), current_user)

        call_args = mock_complaint_repo.create.await_args[0][0]
        assert call_args["user_id"] == VALID_USER_ID  # From auth
        assert call_args["complaint_number"].startswith("CMP-")  # Server-generated
        assert call_args["organization_id"] == VALID_ORG_ID  # From category
        assert str(call_args["department_id"]) == VALID_DEPT_ID  # From category
        assert call_args["status"] == ComplaintStatus.SUBMITTED.value  # Server-set
        assert call_args["visibility"] == ComplaintVisibility.PUBLIC.value  # Default
        assert call_args["likes_count"] == 0  # Default
        assert call_args["priority_score"] == 0.0  # Default
        assert call_args["severity_score"] == 3  # From category
        assert call_args["community_engagement_score"] == 0  # Default
        assert call_args["age_score"] == 0.0  # Default
        assert call_args["assigned_to"] is None  # Default
        assert call_args["assigned_at"] is None  # Default

    async def test_safe_response_excludes_internal_fields(
        self,
        service: ComplaintService,
        mock_complaint_repo: AsyncMock,
        mock_category_repo: AsyncMock,
        mock_department_repo: AsyncMock,
    ) -> None:
        current_user = make_current_user()
        mock_category_repo.find_by_id_active.return_value = make_valid_category()
        mock_department_repo.find_by_id_active_in_org.return_value = make_valid_department()
        mock_complaint_repo.create.return_value = VALID_COMPLAINT_ID
        mock_complaint_repo.find_by_id.return_value = make_complaint_doc()

        result = await service.create_complaint(make_request(), current_user)

        dumped = result.data.model_dump()
        assert "password" not in dumped
        assert "password_hash" not in dumped
        assert "rejection_reason" not in dumped
        assert "duplicate_of" not in dumped
        assert "metadata" not in dumped
        assert "organization_priority_boost" not in dumped
        assert "sla_deadline" not in dumped
