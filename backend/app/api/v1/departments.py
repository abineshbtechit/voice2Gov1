"""Department API endpoints (Phase 1.7).

Authoritative source: docs/api-contract.md §Departments; docs/traceability-matrix.md ORG-07, ORG-08.
"""

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import (
    require_organization_admin,
    require_organization_staff,
)
from app.dependencies.services import get_organization_service
from app.schemas.common import SuccessResponse
from app.schemas.department import (
    DepartmentCreateRequest,
    DepartmentUpdateRequest,
)
from app.schemas.user import UserResponse
from app.services.organization_service import OrganizationService

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get(
    "",
    summary="List departments",
    description="List departments scoped to user's organization.",
    response_model=SuccessResponse,
)
async def list_departments(
    current_user: UserResponse = Depends(require_organization_staff),
    service: OrganizationService = Depends(get_organization_service),
    is_active: bool | None = Query(default=None, description="Filter active status"),
    organization_id: str | None = Query(default=None, description="Filter by org (Admin only)"),
    limit: int = Query(default=100, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
) -> SuccessResponse:
    depts = await service.list_departments(
        current_user=current_user,
        organization_id=organization_id,
        is_active=is_active,
        limit=limit,
        skip=skip,
    )
    return SuccessResponse(
        success=True,
        message="Departments retrieved",
        data=[d.model_dump() for d in depts],
    )


@router.post(
    "",
    summary="Create department",
    description="Create department within organization (Org Admin or Admin).",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_department(
    request: DepartmentCreateRequest,
    current_user: UserResponse = Depends(require_organization_admin),
    service: OrganizationService = Depends(get_organization_service),
) -> SuccessResponse:
    dept = await service.create_department(request, current_user)
    return SuccessResponse(
        success=True,
        message="Department created successfully",
        data=dept.model_dump(),
    )


@router.get(
    "/{id}",
    summary="Get department details",
    description="Get department by ID with tenant isolation.",
    response_model=SuccessResponse,
)
async def get_department(
    id: str,
    current_user: UserResponse = Depends(require_organization_staff),
    service: OrganizationService = Depends(get_organization_service),
) -> SuccessResponse:
    dept = await service.get_department(id, current_user)
    return SuccessResponse(
        success=True,
        message="Department retrieved",
        data=dept.model_dump(),
    )


@router.put(
    "/{id}",
    summary="Update department",
    description="Update department details (Org Admin or Admin).",
    response_model=SuccessResponse,
)
async def update_department(
    id: str,
    request: DepartmentUpdateRequest,
    current_user: UserResponse = Depends(require_organization_admin),
    service: OrganizationService = Depends(get_organization_service),
) -> SuccessResponse:
    dept = await service.update_department(id, request, current_user)
    return SuccessResponse(
        success=True,
        message="Department updated successfully",
        data=dept.model_dump(),
    )


@router.delete(
    "/{id}",
    summary="Delete department",
    description="Soft-deactivate department (Org Admin or Admin).",
    response_model=SuccessResponse,
)
async def delete_department(
    id: str,
    current_user: UserResponse = Depends(require_organization_admin),
    service: OrganizationService = Depends(get_organization_service),
) -> SuccessResponse:
    await service.delete_department(id, current_user)
    return SuccessResponse(
        success=True,
        message="Department deleted successfully",
        data=None,
    )
