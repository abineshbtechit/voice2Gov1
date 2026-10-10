"""Search API router (LOC-05, SRS Area: Search / GET /api/v1/search).

Provides GET /api/v1/search for searching public complaints with keyword,
filtering, geolocation, sorting, and pagination.
Supports optional Bearer token authentication per api-contract.md.
"""

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_optional_current_user
from app.dependencies.services import get_complaint_service
from app.schemas.complaint import FeedResponse
from app.schemas.user import UserResponse
from app.services.complaint_service import ComplaintService

router = APIRouter(prefix="/search", tags=["Search"])


@router.get(
    "",
    response_model=FeedResponse,
    summary="Search public complaints",
    description=(
        "Search complaints by keyword query, status, category, organization, or location. "
        "Open to anonymous and authenticated users (optional Bearer token)."
    ),
)
async def search_complaints(
    q: str | None = Query(default=None, description="Search keyword in title, description, or complaint number"),
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
    """Search public complaints.

    - **Authentication**: Optional Bearer token.
    - **Query**: Searches title, description, and complaint number.
    - **Visibility**: Exposes only public complaints; excludes private complaints and deleted complaints.
    - **Pagination**: page >= 1, 1 <= page_size <= 50.
    - **Sorting**: recent, popular, priority, nearby.
    - **Filtering**: status, category_id, organization_id.
    """
    search_data = await complaint_service.get_public_feed(
        page=page,
        page_size=page_size,
        sort=sort,
        status=status,
        category_id=category_id,
        organization_id=organization_id,
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        q=q,
        current_user=current_user,
    )
    return FeedResponse(
        success=True,
        message="Search results retrieved",
        data=search_data,
    )
