"""Unit tests for Phase 1.5 Community Likes and Engagement (FEED-05 - FEED-08)."""

from datetime import UTC, datetime

import pytest

from app.exceptions.base import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.schemas.complaint import ComplaintStatus, ComplaintVisibility
from app.schemas.user import UserResponse, UserRole
from app.services.complaint_service import ComplaintService
from app.services.priority_service import PriorityService
from tests.fakes import (
    FakeAdminSettingsRepository,
    FakeComplaintLikeRepository,
    FakeComplaintLookup,
)


class TestComplaintLikeServiceUnit:
    """Test unit business logic for like, unlike, duplicate like protection, and priority recalculation."""

    @pytest.fixture
    def current_citizen(self) -> UserResponse:
        return UserResponse(
            id="507f1f77bcf86cd799439011",
            email="citizen@example.com",
            phone="+15551234567",
            full_name="Citizen One",
            role=UserRole.CITIZEN,
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @pytest.fixture
    def other_citizen(self) -> UserResponse:
        return UserResponse(
            id="507f1f77bcf86cd799439022",
            email="citizen2@example.com",
            phone="+15559876543",
            full_name="Citizen Two",
            role=UserRole.CITIZEN,
            status="active",
            is_verified=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @pytest.fixture
    def staff_user(self) -> UserResponse:
        return UserResponse(
            id="507f1f77bcf86cd799439033",
            email="staff@example.com",
            phone="+15550000000",
            full_name="Staff Member",
            role=UserRole.ORGANIZATION_STAFF,
            status="active",
            is_verified=True,
            organization_id="507f1f77bcf86cd799439001",
            department_id="507f1f77bcf86cd799439002",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @pytest.fixture
    def complaint_service(self) -> ComplaintService:
        complaint_repo = FakeComplaintLookup()
        like_repo = FakeComplaintLikeRepository()
        settings_repo = FakeAdminSettingsRepository()
        priority_service = PriorityService(like_repo=like_repo, settings_repo=settings_repo)

        # Seed test public complaint
        complaint_repo.seed(
            "507f1f77bcf86cd799439099",
            title="Public Road Damage",
            description="Massive pothole needs repair immediately",
            status=ComplaintStatus.ONGOING,
            visibility=ComplaintVisibility.PUBLIC,
            organization_id="507f1f77bcf86cd799439001",
            department_id="507f1f77bcf86cd799439002",
            category_id="507f1f77bcf86cd799439003",
            user_id="507f1f77bcf86cd799439011",
            likes_count=0,
            priority_score=10.0,
            severity_score=3,
            created_at=datetime.now(UTC),
        )

        from unittest.mock import AsyncMock
        category_repo = AsyncMock()
        department_repo = AsyncMock()

        service = ComplaintService(
            complaint_repo=complaint_repo,  # type: ignore
            category_repo=category_repo,
            department_repo=department_repo,
            priority_service=priority_service,
            like_repo=like_repo,  # type: ignore
        )
        return service

    @pytest.mark.asyncio
    async def test_citizen_can_like_public_complaint(
        self, complaint_service: ComplaintService, current_citizen: UserResponse
    ) -> None:
        cid = "507f1f77bcf86cd799439099"
        res = await complaint_service.like_complaint(cid, current_citizen)
        assert res.like_count == 1
        assert res.user_liked is True

        # Check repository updated
        complaint = await complaint_service._complaint_repo.find_by_id(cid)
        assert complaint["likes_count"] == 1
        # Priority score should be recalculated
        assert complaint["priority_score"] > 0

    @pytest.mark.asyncio
    async def test_duplicate_like_rejected_with_conflict(
        self, complaint_service: ComplaintService, current_citizen: UserResponse
    ) -> None:
        cid = "507f1f77bcf86cd799439099"
        await complaint_service.like_complaint(cid, current_citizen)

        # Second like must raise ConflictException(DUPLICATE_LIKE)
        with pytest.raises(ConflictException) as exc:
            await complaint_service.like_complaint(cid, current_citizen)
        assert exc.value.error_code == "DUPLICATE_LIKE"

    @pytest.mark.asyncio
    async def test_two_different_citizens_can_both_like(
        self,
        complaint_service: ComplaintService,
        current_citizen: UserResponse,
        other_citizen: UserResponse,
    ) -> None:
        cid = "507f1f77bcf86cd799439099"
        r1 = await complaint_service.like_complaint(cid, current_citizen)
        assert r1.like_count == 1

        r2 = await complaint_service.like_complaint(cid, other_citizen)
        assert r2.like_count == 2

    @pytest.mark.asyncio
    async def test_like_nonexistent_complaint_raises_not_found(
        self, complaint_service: ComplaintService, current_citizen: UserResponse
    ) -> None:
        with pytest.raises(NotFoundException) as exc:
            await complaint_service.like_complaint("507f1f77bcf86cd799439000", current_citizen)
        assert exc.value.error_code == "COMPLAINT_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_like_private_complaint_forbidden(
        self, complaint_service: ComplaintService, current_citizen: UserResponse
    ) -> None:
        cid = "507f1f77bcf86cd799439088"
        complaint_service._complaint_repo.seed(  # type: ignore
            cid,
            title="Private Internal Leak",
            description="Should not be liked by public citizens",
            status=ComplaintStatus.ONGOING,
            visibility=ComplaintVisibility.PRIVATE,
            user_id="507f1f77bcf86cd799439011",
        )
        with pytest.raises(ForbiddenException) as exc:
            await complaint_service.like_complaint(cid, current_citizen)
        assert exc.value.error_code == "FORBIDDEN"

    @pytest.mark.asyncio
    async def test_like_terminal_complaint_rejected(
        self, complaint_service: ComplaintService, current_citizen: UserResponse
    ) -> None:
        cid = "507f1f77bcf86cd799439077"
        complaint_service._complaint_repo.seed(  # type: ignore
            cid,
            title="Rejected Complaint",
            description="Already rejected",
            status=ComplaintStatus.REJECTED,
            visibility=ComplaintVisibility.PUBLIC,
            user_id="507f1f77bcf86cd799439011",
        )
        with pytest.raises(ValidationException) as exc:
            await complaint_service.like_complaint(cid, current_citizen)
        assert exc.value.error_code == "INVALID_STATUS_TRANSITION"

    @pytest.mark.asyncio
    async def test_unlike_complaint_decrements_count_and_recalculates(
        self, complaint_service: ComplaintService, current_citizen: UserResponse
    ) -> None:
        cid = "507f1f77bcf86cd799439099"
        await complaint_service.like_complaint(cid, current_citizen)
        complaint_before = await complaint_service._complaint_repo.find_by_id(cid)
        score_with_like = complaint_before["priority_score"]

        # Unlike
        res = await complaint_service.unlike_complaint(cid, current_citizen)
        assert res.like_count == 0
        assert res.user_liked is False

        complaint_after = await complaint_service._complaint_repo.find_by_id(cid)
        assert complaint_after["likes_count"] == 0
        assert complaint_after["priority_score"] < score_with_like

    @pytest.mark.asyncio
    async def test_unlike_when_not_liked_is_safe(
        self, complaint_service: ComplaintService, current_citizen: UserResponse
    ) -> None:
        cid = "507f1f77bcf86cd799439099"
        res = await complaint_service.unlike_complaint(cid, current_citizen)
        assert res.like_count == 0
        assert res.user_liked is False

    @pytest.mark.asyncio
    async def test_get_like_status(
        self,
        complaint_service: ComplaintService,
        current_citizen: UserResponse,
        other_citizen: UserResponse,
    ) -> None:
        cid = "507f1f77bcf86cd799439099"
        # Check before like
        s1 = await complaint_service.get_like_status(cid, current_citizen)
        assert s1.user_liked is False
        assert s1.like_count == 0

        # Citizen 1 likes
        await complaint_service.like_complaint(cid, current_citizen)

        s2 = await complaint_service.get_like_status(cid, current_citizen)
        assert s2.user_liked is True
        assert s2.like_count == 1

        # Other citizen inspects status
        s3 = await complaint_service.get_like_status(cid, other_citizen)
        assert s3.user_liked is False
        assert s3.like_count == 1
