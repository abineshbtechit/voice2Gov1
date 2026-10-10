"""Category API endpoints (Phase 1.7).

Authoritative source: docs/api-contract.md §Categories; docs/traceability-matrix.md CAT-01 → CAT-04.
"""

from fastapi import APIRouter, Depends, Query

from app.dependencies.services import get_category_service
from app.schemas.common import SuccessResponse
from app.services.category_service import CategoryService

# Public / general categories router
router = APIRouter(prefix="/categories", tags=["categories"])


@router.get(
    "",
    summary="List active categories",
    description="List active categories for complaint classification and routing (public/optional auth).",
    response_model=SuccessResponse,
)
async def list_active_categories(
    organization_id: str | None = Query(default=None, description="Filter by organization"),
    service: CategoryService = Depends(get_category_service),
) -> SuccessResponse:
    categories = await service.list_active_categories(organization_id=organization_id)
    return SuccessResponse(
        success=True,
        message="Active categories retrieved",
        data=[c.model_dump() for c in categories],
    )
