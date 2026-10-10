"""Feed API router (Phase 1.5, FEED-01 - FEED-04, FEED-09).

GET /api/v1/feed - Public complaint feed with pagination, filtering, and sorting.
"""

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_optional_current_user
from app.dependencies.services import get_complaint_service
from app.schemas.complaint import FeedResponse
from app.schemas.user import UserResponse
from app.services.complaint_service import ComplaintService

router = APIRouter(prefix="/feed", tags=["Feed"])


@router.get(
    "",
    response_model=FeedResponse,
    summary="Get public community feed",
    description="Retrieve public complaint feed with pagination, filtering, and sorting. Open to anonymous and authenticated users.",
)
async def get_public_feed(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=50, description="Items per page (max 50)"),
    sort: str = Query(default="recent", description="Sort order: recent, popular, priority, nearby"),
    status: str | None = Query(default=None, description="Filter by complaint status"),
    category_id: str | None = Query(default=None, description="Filter by category ID"),
    organization_id: str | None = Query(default=None, description="Filter by organization ID"),
    lat: float | None = Query(default=None, ge=-90.0, le=90.0, description="Latitude for nearby sort"),
    lng: float | None = Query(default=None, ge=-180.0, le=180.0, description="Longitude for nearby sort"),
    radius_km: float = Query(default=10.0, gt=0, description="Search radius in kilometers for nearby sort"),
    current_user: UserResponse | None = Depends(get_optional_current_user),
    complaint_service: ComplaintService = Depends(get_complaint_service),
) -> FeedResponse:
    """Retrieve public feed.

    - **Authentication**: Optional Bearer token.
    - **Visibility**: Exposes only public complaints; excludes private complaints and deleted complaints.
    - **Pagination**: page >= 1, 1 <= page_size <= 50.
    - **Sorting**: recent (created_at DESC), popular (likes DESC), priority (priority_score DESC), nearby ($geoNear).
    - **Filtering**: status, category_id, organization_id.
    - **Personalization**: If caller is authenticated, `user_liked` field reflects whether current user liked each complaint.
    """
    feed_data = await complaint_service.get_public_feed(
        page=page,
        page_size=page_size,
        sort=sort,
        status=status,
        category_id=category_id,
        organization_id=organization_id,
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        current_user=current_user,
    )
    return FeedResponse(
        success=True,
        message="Feed retrieved",
        data=feed_data,
    )
