"""Unit tests for Phase 1.5 Community Public Feed (FEED-01 - FEED-04, FEED-09)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.exceptions.base import ValidationException
from app.schemas.complaint import ComplaintStatus, ComplaintVisibility
from app.schemas.user import UserResponse, UserRole
from app.services.complaint_service import ComplaintService
from app.services.priority_service import PriorityService
from tests.fakes import (
    FakeAdminSettingsRepository,
    FakeComplaintLikeRepository,
    FakeComplaintLookup,
)


class TestPublicFeedUnit:
    """Test feed visibility, sorting, filtering, and pagination logic."""

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
    def complaint_service(self) -> ComplaintService:
        complaint_repo = FakeComplaintLookup()
        like_repo = FakeComplaintLikeRepository()
        settings_repo = FakeAdminSettingsRepository()
        priority_service = PriorityService(like_repo=like_repo, settings_repo=settings_repo)

        from unittest.mock import AsyncMock
        category_repo = AsyncMock()
        department_repo = AsyncMock()

        CAT_1 = "507f1f77bcf86cd799439051"
        CAT_2 = "507f1f77bcf86cd799439052"
        DEPT_1 = "507f1f77bcf86cd799439061"
        DEPT_2 = "507f1f77bcf86cd799439062"
        DEPT_3 = "507f1f77bcf86cd799439063"
        ORG_1 = "507f1f77bcf86cd799439071"
        ORG_2 = "507f1f77bcf86cd799439072"

        # Seed categories and departments
        category_repo.find_by_id.side_effect = lambda cid: {
            "_id": cid,
            "name": f"Category {cid}",
            "icon": "icon",
            "color": "#123456",
        }
        category_repo.find_by_ids.side_effect = lambda ids: [
            {
                "_id": cid,
                "name": f"Category {cid}",
                "icon": "icon",
                "color": "#123456",
            }
            for cid in ids
        ]
        department_repo.find_by_id.side_effect = lambda did: {
            "_id": did,
            "name": f"Dept {did}",
        }
        department_repo.find_by_ids.side_effect = lambda dids: [
            {
                "_id": did,
                "name": f"Dept {did}",
            }
            for did in dids
        ]

        now = datetime.now(UTC)

        # 1. Public SUBMITTED (NYC Times Square ~ 40.7580, -73.9855)
        complaint_repo.seed(
            "507f1f77bcf86cd799439001",
            title="Public Road Hole 1",
            status=ComplaintStatus.SUBMITTED,
            visibility=ComplaintVisibility.PUBLIC,
            organization_id=ORG_1,
            department_id=DEPT_1,
            category_id=CAT_1,
            user_id="507f1f77bcf86cd799439081",
            likes_count=10,
            priority_score=40.0,
            location={"type": "Point", "coordinates": [-73.9855, 40.7580]},
            created_at=now - timedelta(hours=10),
        )
        # 2. Public ONGOING (Empire State ~ 40.7484, -73.9857)
        complaint_repo.seed(
            "507f1f77bcf86cd799439002",
            title="Public Street Light 2",
            status=ComplaintStatus.ONGOING,
            visibility=ComplaintVisibility.PUBLIC,
            organization_id=ORG_1,
            department_id=DEPT_2,
            category_id=CAT_2,
            user_id="507f1f77bcf86cd799439082",
            likes_count=50,
            priority_score=85.0,
            location={"type": "Point", "coordinates": [-73.9857, 40.7484]},
            created_at=now - timedelta(hours=5),
        )
        # 3. Public COMPLETED
        complaint_repo.seed(
            "507f1f77bcf86cd799439003",
            title="Public Resolved 3",
            status=ComplaintStatus.COMPLETED,
            visibility=ComplaintVisibility.PUBLIC,
            organization_id=ORG_2,
            department_id=DEPT_3,
            category_id=CAT_1,
            user_id="507f1f77bcf86cd799439083",
            likes_count=5,
            priority_score=20.0,
            location={"type": "Point", "coordinates": [-73.9800, 40.7500]},
            created_at=now - timedelta(hours=1),
        )
        # 4. Private complaint (Must be hidden)
        complaint_repo.seed(
            "507f1f77bcf86cd799439004",
            title="Private Confidential Complaint",
            status=ComplaintStatus.ONGOING,
            visibility=ComplaintVisibility.PRIVATE,
            organization_id=ORG_1,
            department_id=DEPT_1,
            category_id=CAT_1,
            user_id="507f1f77bcf86cd799439081",
            likes_count=100,
            priority_score=99.0,
            created_at=now,
        )
        # 5. Public REJECTED (Must be hidden in default feed)
        complaint_repo.seed(
            "507f1f77bcf86cd799439005",
            title="Public Rejected Complaint",
            status=ComplaintStatus.REJECTED,
            visibility=ComplaintVisibility.PUBLIC,
            organization_id=ORG_1,
            department_id=DEPT_1,
            category_id=CAT_1,
            user_id="507f1f77bcf86cd799439081",
            likes_count=0,
            priority_score=0.0,
            created_at=now,
        )


        return ComplaintService(
            complaint_repo=complaint_repo,  # type: ignore
            category_repo=category_repo,
            department_repo=department_repo,
            priority_service=priority_service,
            like_repo=like_repo,  # type: ignore
        )

    @pytest.mark.asyncio
    async def test_feed_excludes_private_and_rejected_by_default(
        self, complaint_service: ComplaintService
    ) -> None:
        feed = await complaint_service.get_public_feed()
        ids = [item.id for item in feed.items]
        # Should include items 1, 2, 3
        assert "507f1f77bcf86cd799439001" in ids
        assert "507f1f77bcf86cd799439002" in ids
        assert "507f1f77bcf86cd799439003" in ids
        # Must exclude private and rejected
        assert "507f1f77bcf86cd799439004" not in ids
        assert "507f1f77bcf86cd799439005" not in ids
        assert feed.pagination.total_items == 3

    @pytest.mark.asyncio
    async def test_feed_sorting_recent(self, complaint_service: ComplaintService) -> None:
        feed = await complaint_service.get_public_feed(sort="recent")
        # Most recent first: 3 (1h ago), then 2 (5h ago), then 1 (10h ago)
        assert [item.id for item in feed.items] == [
            "507f1f77bcf86cd799439003",
            "507f1f77bcf86cd799439002",
            "507f1f77bcf86cd799439001",
        ]

    @pytest.mark.asyncio
    async def test_feed_sorting_popular(self, complaint_service: ComplaintService) -> None:
        feed = await complaint_service.get_public_feed(sort="popular")
        # Most liked first: 2 (50 likes), then 1 (10 likes), then 3 (5 likes)
        assert [item.id for item in feed.items] == [
            "507f1f77bcf86cd799439002",
            "507f1f77bcf86cd799439001",
            "507f1f77bcf86cd799439003",
        ]

    @pytest.mark.asyncio
    async def test_feed_sorting_priority(self, complaint_service: ComplaintService) -> None:
        feed = await complaint_service.get_public_feed(sort="priority")
        # Highest priority first: 2 (85.0), then 1 (40.0), then 3 (20.0)
        assert [item.id for item in feed.items] == [
            "507f1f77bcf86cd799439002",
            "507f1f77bcf86cd799439001",
            "507f1f77bcf86cd799439003",
        ]

    @pytest.mark.asyncio
    async def test_feed_sorting_nearby(self, complaint_service: ComplaintService) -> None:
        # Search from Empire State coordinates (40.7484, -73.9857)
        feed = await complaint_service.get_public_feed(
            sort="nearby",
            lat=40.7484,
            lng=-73.9857,
            radius_km=10.0,
        )
        # Closest item should be 2 (distance ~ 0 km), then others
        assert feed.items[0].id == "507f1f77bcf86cd799439002"
        assert feed.items[0].distance_km is not None
        assert feed.items[0].distance_km < 0.1

    @pytest.mark.asyncio
    async def test_feed_filtering_by_status(self, complaint_service: ComplaintService) -> None:
        feed = await complaint_service.get_public_feed(status="ONGOING")
        assert len(feed.items) == 1
        assert feed.items[0].id == "507f1f77bcf86cd799439002"

    @pytest.mark.asyncio
    async def test_feed_filtering_by_organization(self, complaint_service: ComplaintService) -> None:
        feed = await complaint_service.get_public_feed(organization_id="507f1f77bcf86cd799439072")
        assert len(feed.items) == 1
        assert feed.items[0].id == "507f1f77bcf86cd799439003"


    @pytest.mark.asyncio
    async def test_feed_pagination(self, complaint_service: ComplaintService) -> None:
        feed_p1 = await complaint_service.get_public_feed(page=1, page_size=2)
        assert len(feed_p1.items) == 2
        assert feed_p1.pagination.total_items == 3
        assert feed_p1.pagination.total_pages == 2
        assert feed_p1.pagination.has_next is True
        assert feed_p1.pagination.has_prev is False

        feed_p2 = await complaint_service.get_public_feed(page=2, page_size=2)
        assert len(feed_p2.items) == 1
        assert feed_p2.pagination.has_next is False
        assert feed_p2.pagination.has_prev is True

    @pytest.mark.asyncio
    async def test_invalid_parameters_raise_validation_error(
        self, complaint_service: ComplaintService
    ) -> None:
        with pytest.raises(ValidationException):
            await complaint_service.get_public_feed(page=0)

        with pytest.raises(ValidationException):
            await complaint_service.get_public_feed(page_size=100)

        with pytest.raises(ValidationException):
            await complaint_service.get_public_feed(sort="invalid_sort")

        with pytest.raises(ValidationException):
            # nearby without lat/lng
            await complaint_service.get_public_feed(sort="nearby")

    @pytest.mark.asyncio
    async def test_user_liked_flag_for_authenticated_caller(
        self, complaint_service: ComplaintService, current_citizen: UserResponse
    ) -> None:
        cid = "507f1f77bcf86cd799439002"
        await complaint_service.like_complaint(cid, current_citizen)

        # Feed with current_citizen
        feed = await complaint_service.get_public_feed(current_user=current_citizen)
        item2 = next(i for i in feed.items if i.id == cid)
        item1 = next(i for i in feed.items if i.id == "507f1f77bcf86cd799439001")
        assert item2.user_liked is True
        assert item1.user_liked is False

        # Anonymous feed has user_liked=False everywhere
        anon_feed = await complaint_service.get_public_feed(current_user=None)
        item2_anon = next(i for i in anon_feed.items if i.id == cid)
        assert item2_anon.user_liked is False
