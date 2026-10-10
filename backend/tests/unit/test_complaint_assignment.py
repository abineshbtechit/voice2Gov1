"""Unit tests for Phase 1.3.7 - Complaint Assignment."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId
from pydantic import ValidationError

from app.exceptions.base import (
    BusinessLogicException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.repositories.complaint_repository import ComplaintRepository
from app.schemas.complaint import ComplaintAssignRequest
from app.schemas.user import UserResponse, UserRole
from app.services.complaint_service import ComplaintService


class TestComplaintAssignSchema:
    def test_valid_request(self) -> None:
        req = ComplaintAssignRequest(assigned_to="507f1f77bcf86cd799439011")
        assert req.assigned_to == "507f1f77bcf86cd799439011"

    def test_invalid_object_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ComplaintAssignRequest(assigned_to="not-a-valid-hex-id")

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            ComplaintAssignRequest(
                assigned_to="507f1f77bcf86cd799439011",
                organization_id="507f1f77bcf86cd799439012",  # type: ignore[call-arg]
            )

    def test_client_cannot_pass_status_or_timestamp(self) -> None:
        with pytest.raises(ValidationError):
            ComplaintAssignRequest(
                assigned_to="507f1f77bcf86cd799439011",
                status="ONGOING",  # type: ignore[call-arg]
            )
        with pytest.raises(ValidationError):
            ComplaintAssignRequest(
                assigned_to="507f1f77bcf86cd799439011",
                assigned_at=datetime.now(UTC),  # type: ignore[call-arg]
            )


class TestComplaintAssignRepository:
    @pytest.mark.asyncio
    async def test_assign_complaint_atomic(self) -> None:
        db = MagicMock()
        coll = AsyncMock()
        db.__getitem__.return_value = coll
        coll.update_one.return_value = MagicMock(modified_count=1)

        repo = ComplaintRepository(db)
        now = datetime.now(UTC)
        res = await repo.assign_complaint(
            complaint_id="507f1f77bcf86cd799439013",
            expected_status="SUBMITTED",
            new_status="ONGOING",
            assigned_to="507f1f77bcf86cd799439015",
            assigned_at=now,
            organization_id="507f1f77bcf86cd799439012",
        )
        assert res is True
        coll.update_one.assert_awaited_once()
        args, _ = coll.update_one.await_args
        query, update = args
        assert query["_id"] == ObjectId("507f1f77bcf86cd799439013")
        assert query["status"] == "SUBMITTED"
        # Complaint documents store `organization_id`/`assigned_to` as strings;
        # an ObjectId in the query would never match real stored documents
        # (verified against live MongoDB in Phase 1.8) and every org-scoped
        # assignment would fail with a spurious 409.
        assert query["organization_id"] == "507f1f77bcf86cd799439012"
        assert update["$set"]["assigned_to"] == "507f1f77bcf86cd799439015"
        assert update["$set"]["status"] == "ONGOING"
        assert update["$set"]["assigned_at"] == now

    @pytest.mark.asyncio
    async def test_assign_complaint_invalid_id_returns_false(self) -> None:
        db = MagicMock()
        repo = ComplaintRepository(db)
        res = await repo.assign_complaint(
            complaint_id="invalid-hex",
            expected_status="SUBMITTED",
            new_status="ONGOING",
            assigned_to="507f1f77bcf86cd799439015",
            assigned_at=datetime.now(UTC),
        )
        assert res is False


class TestComplaintAssignServiceUnit:
    @pytest.fixture
    def mock_repos(self):
        complaint_repo = AsyncMock()
        category_repo = AsyncMock()
        department_repo = AsyncMock()
        update_repo = AsyncMock()
        image_repo = AsyncMock()
        user_repo = AsyncMock()
        service = ComplaintService(
            complaint_repo=complaint_repo,
            category_repo=category_repo,
            department_repo=department_repo,
            complaint_update_repo=update_repo,
            complaint_image_repo=image_repo,
            user_repo=user_repo,
        )
        return service, complaint_repo, user_repo, update_repo

    @pytest.mark.asyncio
    async def test_citizen_forbidden(self, mock_repos) -> None:
        service, _, _, _ = mock_repos
        user = UserResponse(
            id="507f1f77bcf86cd799439010",
            email="citizen@example.com",
            phone="+15551234567",
            full_name="Citizen",
            role=UserRole.CITIZEN,
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        req = ComplaintAssignRequest(assigned_to="507f1f77bcf86cd799439015")
        with pytest.raises(ForbiddenException):
            await service.assign("507f1f77bcf86cd799439013", user, req)

    @pytest.mark.asyncio
    async def test_staff_forbidden(self, mock_repos) -> None:
        service, _, _, _ = mock_repos
        user = UserResponse(
            id="507f1f77bcf86cd799439010",
            email="staff@example.com",
            phone="+15551234567",
            full_name="Staff",
            role=UserRole.ORGANIZATION_STAFF,
            organization_id="507f1f77bcf86cd799439012",
            department_id="507f1f77bcf86cd799439014",
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        req = ComplaintAssignRequest(assigned_to="507f1f77bcf86cd799439015")
        with pytest.raises(ForbiddenException):
            await service.assign("507f1f77bcf86cd799439013", user, req)

    @pytest.mark.asyncio
    async def test_complaint_not_found(self, mock_repos) -> None:
        service, complaint_repo, _, _ = mock_repos
        complaint_repo.find_by_id_in_organization.return_value = None
        user = UserResponse(
            id="507f1f77bcf86cd799439010",
            email="orgadmin@example.com",
            phone="+15551234567",
            full_name="Org Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id="507f1f77bcf86cd799439012",
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        req = ComplaintAssignRequest(assigned_to="507f1f77bcf86cd799439015")
        with pytest.raises(NotFoundException):
            await service.assign("507f1f77bcf86cd799439013", user, req)

    @pytest.mark.asyncio
    async def test_terminal_complaint_rejected(self, mock_repos) -> None:
        service, complaint_repo, _, _ = mock_repos
        complaint_repo.find_by_id_in_organization.return_value = {
            "_id": ObjectId("507f1f77bcf86cd799439013"),
            "organization_id": ObjectId("507f1f77bcf86cd799439012"),
            "department_id": ObjectId("507f1f77bcf86cd799439014"),
            "status": "COMPLETED",
        }
        user = UserResponse(
            id="507f1f77bcf86cd799439010",
            email="orgadmin@example.com",
            phone="+15551234567",
            full_name="Org Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id="507f1f77bcf86cd799439012",
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        req = ComplaintAssignRequest(assigned_to="507f1f77bcf86cd799439015")
        with pytest.raises(BusinessLogicException, match="terminal"):
            await service.assign("507f1f77bcf86cd799439013", user, req)

    @pytest.mark.asyncio
    async def test_non_assignable_status_rejected(self, mock_repos) -> None:
        service, complaint_repo, _, _ = mock_repos
        complaint_repo.find_by_id_in_organization.return_value = {
            "_id": ObjectId("507f1f77bcf86cd799439013"),
            "organization_id": ObjectId("507f1f77bcf86cd799439012"),
            "department_id": ObjectId("507f1f77bcf86cd799439014"),
            "status": "PROCESSING",
        }
        user = UserResponse(
            id="507f1f77bcf86cd799439010",
            email="orgadmin@example.com",
            phone="+15551234567",
            full_name="Org Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id="507f1f77bcf86cd799439012",
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        req = ComplaintAssignRequest(assigned_to="507f1f77bcf86cd799439015")
        with pytest.raises(BusinessLogicException, match="PROCESSING"):
            await service.assign("507f1f77bcf86cd799439013", user, req)

    @pytest.mark.asyncio
    async def test_target_user_not_found(self, mock_repos) -> None:
        service, complaint_repo, user_repo, _ = mock_repos
        complaint_repo.find_by_id_in_organization.return_value = {
            "_id": ObjectId("507f1f77bcf86cd799439013"),
            "organization_id": ObjectId("507f1f77bcf86cd799439012"),
            "department_id": ObjectId("507f1f77bcf86cd799439014"),
            "status": "SUBMITTED",
        }
        user_repo.find_by_id.return_value = None
        user = UserResponse(
            id="507f1f77bcf86cd799439010",
            email="orgadmin@example.com",
            phone="+15551234567",
            full_name="Org Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id="507f1f77bcf86cd799439012",
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        req = ComplaintAssignRequest(assigned_to="507f1f77bcf86cd799439015")
        with pytest.raises(ValidationException, match="not found"):
            await service.assign("507f1f77bcf86cd799439013", user, req)

    @pytest.mark.asyncio
    async def test_target_user_not_org_staff(self, mock_repos) -> None:
        service, complaint_repo, user_repo, _ = mock_repos
        complaint_repo.find_by_id_in_organization.return_value = {
            "_id": ObjectId("507f1f77bcf86cd799439013"),
            "organization_id": ObjectId("507f1f77bcf86cd799439012"),
            "department_id": ObjectId("507f1f77bcf86cd799439014"),
            "status": "SUBMITTED",
        }
        user_repo.find_by_id.return_value = {
            "_id": ObjectId("507f1f77bcf86cd799439015"),
            "role": "citizen",
            "status": "active",
        }
        user = UserResponse(
            id="507f1f77bcf86cd799439010",
            email="orgadmin@example.com",
            phone="+15551234567",
            full_name="Org Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id="507f1f77bcf86cd799439012",
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        req = ComplaintAssignRequest(assigned_to="507f1f77bcf86cd799439015")
        with pytest.raises(ValidationException, match="not an organization staff"):
            await service.assign("507f1f77bcf86cd799439013", user, req)

    @pytest.mark.asyncio
    async def test_target_user_inactive(self, mock_repos) -> None:
        service, complaint_repo, user_repo, _ = mock_repos
        complaint_repo.find_by_id_in_organization.return_value = {
            "_id": ObjectId("507f1f77bcf86cd799439013"),
            "organization_id": ObjectId("507f1f77bcf86cd799439012"),
            "department_id": ObjectId("507f1f77bcf86cd799439014"),
            "status": "SUBMITTED",
        }
        user_repo.find_by_id.return_value = {
            "_id": ObjectId("507f1f77bcf86cd799439015"),
            "role": "organization_staff",
            "status": "suspended",
        }
        user = UserResponse(
            id="507f1f77bcf86cd799439010",
            email="orgadmin@example.com",
            phone="+15551234567",
            full_name="Org Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id="507f1f77bcf86cd799439012",
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        req = ComplaintAssignRequest(assigned_to="507f1f77bcf86cd799439015")
        with pytest.raises(ValidationException, match="not active"):
            await service.assign("507f1f77bcf86cd799439013", user, req)

    @pytest.mark.asyncio
    async def test_target_user_org_mismatch(self, mock_repos) -> None:
        service, complaint_repo, user_repo, _ = mock_repos
        complaint_repo.find_by_id_in_organization.return_value = {
            "_id": ObjectId("507f1f77bcf86cd799439013"),
            "organization_id": ObjectId("507f1f77bcf86cd799439012"),
            "department_id": ObjectId("507f1f77bcf86cd799439014"),
            "status": "SUBMITTED",
        }
        user_repo.find_by_id.return_value = {
            "_id": ObjectId("507f1f77bcf86cd799439015"),
            "role": "organization_staff",
            "status": "active",
            "organization_id": "507f1f77bcf86cd799439099",  # different org
            "department_id": "507f1f77bcf86cd799439014",
        }
        user = UserResponse(
            id="507f1f77bcf86cd799439010",
            email="orgadmin@example.com",
            phone="+15551234567",
            full_name="Org Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id="507f1f77bcf86cd799439012",
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        req = ComplaintAssignRequest(assigned_to="507f1f77bcf86cd799439015")
        with pytest.raises(ValidationException, match="different organization"):
            await service.assign("507f1f77bcf86cd799439013", user, req)

    @pytest.mark.asyncio
    async def test_target_user_dept_mismatch(self, mock_repos) -> None:
        service, complaint_repo, user_repo, _ = mock_repos
        complaint_repo.find_by_id_in_organization.return_value = {
            "_id": ObjectId("507f1f77bcf86cd799439013"),
            "organization_id": ObjectId("507f1f77bcf86cd799439012"),
            "department_id": ObjectId("507f1f77bcf86cd799439014"),
            "status": "SUBMITTED",
        }
        user_repo.find_by_id.return_value = {
            "_id": ObjectId("507f1f77bcf86cd799439015"),
            "role": "organization_staff",
            "status": "active",
            "organization_id": "507f1f77bcf86cd799439012",
            "department_id": "507f1f77bcf86cd799439088",  # different dept
        }
        user = UserResponse(
            id="507f1f77bcf86cd799439010",
            email="orgadmin@example.com",
            phone="+15551234567",
            full_name="Org Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id="507f1f77bcf86cd799439012",
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        req = ComplaintAssignRequest(assigned_to="507f1f77bcf86cd799439015")
        with pytest.raises(ValidationException, match="department"):
            await service.assign("507f1f77bcf86cd799439013", user, req)
