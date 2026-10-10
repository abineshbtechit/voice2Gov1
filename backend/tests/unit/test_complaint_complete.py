"""Unit tests for complaint completion (Phase 1.4, CMP-11)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.exceptions.base import (
    BusinessLogicException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.repositories.complaint_image_repository import ComplaintImageRepository
from app.repositories.complaint_repository import ComplaintRepository
from app.schemas.complaint import (
    ComplaintCompleteRequest,
)
from app.schemas.user import UserResponse, UserRole
from app.services.complaint_service import ComplaintService


class TestComplaintCompleteSchema:
    """Test ComplaintCompleteRequest validation."""

    def test_valid_request(self) -> None:
        req = ComplaintCompleteRequest(reason="Pothole filled and road repaved")
        assert req.reason == "Pothole filled and road repaved"
        assert req.completion_images == []

    def test_valid_request_with_images(self) -> None:
        req = ComplaintCompleteRequest(
            reason="Work finished",
            completion_images=["507f1f77bcf86cd799439011"],
        )
        assert len(req.completion_images) == 1

    def test_empty_reason_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ComplaintCompleteRequest(reason="")

    def test_whitespace_reason_rejected_at_service_or_schema(self) -> None:
        req = ComplaintCompleteRequest(reason="   ")
        assert req.reason.strip() == ""

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            ComplaintCompleteRequest(
                reason="Done",
                status="COMPLETED",  # Client cannot pass status
            )

    def test_server_owned_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            ComplaintCompleteRequest(
                reason="Done",
                completed_at=datetime.now(UTC),  # type: ignore[call-arg]
            )


class TestComplaintCompleteRepository:
    """Test ComplaintRepository.complete_complaint atomic query behavior."""

    @pytest.mark.asyncio
    async def test_complete_complaint_atomic(self) -> None:
        collection = MagicMock()
        update_result = MagicMock()
        update_result.modified_count = 1
        collection.update_one = AsyncMock(return_value=update_result)

        db = MagicMock()
        db.__getitem__.return_value = collection

        repo = ComplaintRepository(db)
        cid = "507f1f77bcf86cd799439011"
        org_id = "507f1f77bcf86cd799439012"
        now = datetime.now(UTC)

        res = await repo.complete_complaint(cid, completed_at=now, organization_id=org_id)
        assert res is True
        collection.update_one.assert_called_once()
        query = collection.update_one.call_args[0][0]
        assert query["status"] == "PROCESSING"

    @pytest.mark.asyncio
    async def test_complete_complaint_invalid_id_returns_false(self) -> None:
        db = MagicMock()
        repo = ComplaintRepository(db)
        res = await repo.complete_complaint("invalid_id", completed_at=datetime.now(UTC))
        assert res is False


class TestComplaintCompleteServiceUnit:
    """Test service-layer complete logic and security."""

    @pytest.fixture
    def mock_repos(self):
        complaint_repo = AsyncMock(spec=ComplaintRepository)
        category_repo = AsyncMock()
        department_repo = AsyncMock()
        update_repo = AsyncMock()
        image_repo = AsyncMock(spec=ComplaintImageRepository)
        user_repo = AsyncMock()
        service = ComplaintService(
            complaint_repo=complaint_repo,
            category_repo=category_repo,
            department_repo=department_repo,
            complaint_update_repo=update_repo,
            complaint_image_repo=image_repo,
            user_repo=user_repo,
        )
        return service, complaint_repo, update_repo, image_repo

    @pytest.mark.asyncio
    async def test_citizen_forbidden(self, mock_repos) -> None:
        service, _, _, _ = mock_repos
        citizen = UserResponse(
            id="507f1f77bcf86cd799439099",
            email="citizen@example.com",
            phone="+15550000001",
            full_name="Citizen",
            role=UserRole.CITIZEN,
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        req = ComplaintCompleteRequest(reason="Done")
        with pytest.raises(ForbiddenException) as exc:
            await service.complete("507f1f77bcf86cd799439011", citizen, req)
        assert exc.value.error_code == "FORBIDDEN"

    @pytest.mark.asyncio
    async def test_complaint_not_found(self, mock_repos) -> None:
        service, complaint_repo, _, _ = mock_repos
        complaint_repo.find_by_id_in_organization.return_value = None
        admin = UserResponse(
            id="507f1f77bcf86cd799439099",
            email="admin@example.com",
            phone="+15550000002",
            full_name="Org Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id="507f1f77bcf86cd799439012",
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        req = ComplaintCompleteRequest(reason="Done")
        with pytest.raises(NotFoundException) as exc:
            await service.complete("507f1f77bcf86cd799439011", admin, req)
        assert exc.value.error_code == "COMPLAINT_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_wrong_starting_status_rejected(self, mock_repos) -> None:
        service, complaint_repo, _, _ = mock_repos
        complaint_repo.find_by_id_in_organization.return_value = {
            "_id": "507f1f77bcf86cd799439011",
            "status": "ONGOING",
            "organization_id": "507f1f77bcf86cd799439012",
            "department_id": "507f1f77bcf86cd799439013",
        }
        admin = UserResponse(
            id="507f1f77bcf86cd799439099",
            email="admin@example.com",
            phone="+15550000002",
            full_name="Org Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id="507f1f77bcf86cd799439012",
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        req = ComplaintCompleteRequest(reason="Done")
        with pytest.raises(BusinessLogicException) as exc:
            await service.complete("507f1f77bcf86cd799439011", admin, req)
        assert exc.value.error_code == "INVALID_STATUS_TRANSITION"

    @pytest.mark.asyncio
    async def test_terminal_status_rejected(self, mock_repos) -> None:
        service, complaint_repo, _, _ = mock_repos
        complaint_repo.find_by_id_in_organization.return_value = {
            "_id": "507f1f77bcf86cd799439011",
            "status": "COMPLETED",
            "organization_id": "507f1f77bcf86cd799439012",
            "department_id": "507f1f77bcf86cd799439013",
        }
        admin = UserResponse(
            id="507f1f77bcf86cd799439099",
            email="admin@example.com",
            phone="+15550000002",
            full_name="Org Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id="507f1f77bcf86cd799439012",
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        req = ComplaintCompleteRequest(reason="Done")
        with pytest.raises(BusinessLogicException) as exc:
            await service.complete("507f1f77bcf86cd799439011", admin, req)
        assert exc.value.error_code == "INVALID_STATUS_TRANSITION"

    @pytest.mark.asyncio
    async def test_whitespace_reason_rejected(self, mock_repos) -> None:
        service, complaint_repo, _, _ = mock_repos
        complaint_repo.find_by_id_in_organization.return_value = {
            "_id": "507f1f77bcf86cd799439011",
            "status": "PROCESSING",
            "organization_id": "507f1f77bcf86cd799439012",
            "department_id": "507f1f77bcf86cd799439013",
        }
        admin = UserResponse(
            id="507f1f77bcf86cd799439099",
            email="admin@example.com",
            phone="+15550000002",
            full_name="Org Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id="507f1f77bcf86cd799439012",
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        req = ComplaintCompleteRequest(reason="   ")
        with pytest.raises(ValidationException) as exc:
            await service.complete("507f1f77bcf86cd799439011", admin, req)
        assert exc.value.error_code == "REASON_REQUIRED"

    @pytest.mark.asyncio
    async def test_unassigned_staff_rejected(self, mock_repos) -> None:
        service, complaint_repo, _, _ = mock_repos
        complaint_repo.find_by_id_in_organization.return_value = {
            "_id": "507f1f77bcf86cd799439011",
            "status": "PROCESSING",
            "organization_id": "507f1f77bcf86cd799439012",
            "department_id": "507f1f77bcf86cd799439013",
            "assigned_to": "507f1f77bcf86cd799439014",
        }
        other_staff = UserResponse(
            id="507f1f77bcf86cd799439099",  # different staff id
            email="staff@example.com",
            phone="+15550000003",
            full_name="Other Staff",
            role=UserRole.ORGANIZATION_STAFF,
            organization_id="507f1f77bcf86cd799439012",
            department_id="507f1f77bcf86cd799439013",
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        req = ComplaintCompleteRequest(reason="Done")
        with pytest.raises(ForbiddenException) as exc:
            await service.complete("507f1f77bcf86cd799439011", other_staff, req)
        assert exc.value.error_code == "FORBIDDEN"

    @pytest.mark.asyncio
    async def test_cross_complaint_image_rejected(self, mock_repos) -> None:
        service, complaint_repo, _, image_repo = mock_repos
        complaint_repo.find_by_id_in_organization.return_value = {
            "_id": "507f1f77bcf86cd799439011",
            "status": "PROCESSING",
            "organization_id": "507f1f77bcf86cd799439012",
            "department_id": "507f1f77bcf86cd799439013",
        }
        image_repo.find_by_id.return_value = None  # Image not found on complaint
        admin = UserResponse(
            id="507f1f77bcf86cd799439099",
            email="admin@example.com",
            phone="+15550000002",
            full_name="Org Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id="507f1f77bcf86cd799439012",
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        req = ComplaintCompleteRequest(
            reason="Done",
            completion_images=["507f1f77bcf86cd799439088"],
        )
        with pytest.raises(ValidationException) as exc:
            await service.complete("507f1f77bcf86cd799439011", admin, req)
        assert exc.value.error_code == "INVALID_IMAGE_REFERENCE"

    @pytest.mark.asyncio
    async def test_wrong_image_type_rejected(self, mock_repos) -> None:
        service, complaint_repo, _, image_repo = mock_repos
        complaint_repo.find_by_id_in_organization.return_value = {
            "_id": "507f1f77bcf86cd799439011",
            "status": "PROCESSING",
            "organization_id": "507f1f77bcf86cd799439012",
            "department_id": "507f1f77bcf86cd799439013",
        }
        image_repo.find_by_id.return_value = {
            "_id": "507f1f77bcf86cd799439088",
            "image_type": "evidence",  # Evidence images cannot be completion images
        }
        admin = UserResponse(
            id="507f1f77bcf86cd799439099",
            email="admin@example.com",
            phone="+15550000002",
            full_name="Org Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id="507f1f77bcf86cd799439012",
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        req = ComplaintCompleteRequest(
            reason="Done",
            completion_images=["507f1f77bcf86cd799439088"],
        )
        with pytest.raises(ValidationException) as exc:
            await service.complete("507f1f77bcf86cd799439011", admin, req)
        assert exc.value.error_code == "INVALID_IMAGE_TYPE"

