"""Organization API endpoints (Phase 1.2.5 & Phase 1.7).

Protected endpoints that enforce organization-scoped tenant isolation.
Authoritative source: docs/api-contract.md; docs/traceability-matrix.md.
"""

from typing import Any

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import (
    require_admin,
    require_organization_admin,
    require_organization_staff,
)
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_organization_service, get_user_service
from app.schemas.common import PaginatedResponse, PaginationMeta, SuccessResponse
from app.schemas.organization import (
    OrganizationCreateRequest,
    OrganizationStatusRequest,
    OrganizationUpdateRequest,
)
from app.schemas.user import UserResponse, UserRole
from app.services.organization_service import OrganizationService
from app.services.user_service import UserService

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _role_str(user: UserResponse) -> str:
    """Get role as string (handles both UserRole enum and str)."""
    return str(user.role)


def _status_str(user: UserResponse) -> str:
    """Get status as string (handles both UserStatus enum and str)."""
    return user.status.value if hasattr(user.status, "value") else str(user.status)


# =============================================================================
# ORG-05: Org Complaint Dashboard
# =============================================================================


@router.get(
    "/me/complaints",
    summary="Get organization complaints dashboard",
    description="Fetch complaints scoped to the authenticated user's organization.",
    response_model=PaginatedResponse,
)
async def get_my_org_complaints(
    current_user: UserResponse = Depends(require_organization_staff),
    service: OrganizationService = Depends(get_organization_service),
    status: str | None = Query(default=None, description="Filter by status"),
    department_id: str | None = Query(default=None, description="Filter by department"),
    assigned_to: str | None = Query(default=None, description="Filter by assigned staff"),
    sort: str = Query(default="recent", description="Sort by: priority, recent, sla"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse:
    res = await service.get_my_org_complaints(
        current_user=current_user,
        status=status,
        department_id=department_id,
        assigned_to=assigned_to,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    p = res["pagination"]
    return PaginatedResponse(
        success=True,
        message="Organization complaints retrieved",
        data={"items": res["items"]},
        pagination=PaginationMeta(
            page=p["page"],
            page_size=p["page_size"],
            total_items=p["total_items"],
            total_pages=p["total_pages"],
            has_next=p["has_next"],
            has_prev=p["has_prev"],
        ),
    )


# =============================================================================
# ORG-06: Org Priority Queue
# =============================================================================


@router.get(
    "/me/complaints/priority",
    summary="Get organization priority queue",
    description="Fetch organization complaints sorted by priority_score descending.",
    response_model=PaginatedResponse,
)
async def get_my_org_priority_queue(
    current_user: UserResponse = Depends(require_organization_staff),
    service: OrganizationService = Depends(get_organization_service),
    department_id: str | None = Query(default=None, description="Filter by department"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> PaginatedResponse:
    res = await service.get_my_org_priority_queue(
        current_user=current_user,
        department_id=department_id,
        page=page,
        page_size=page_size,
    )
    p = res["pagination"]
    return PaginatedResponse(
        success=True,
        message="Organization priority queue retrieved",
        data={"items": res["items"]},
        pagination=PaginationMeta(
            page=p["page"],
            page_size=p["page_size"],
            total_items=p["total_items"],
            total_pages=p["total_pages"],
            has_next=p["has_next"],
            has_prev=p["has_prev"],
        ),
    )


# =============================================================================
# Existing Phase 1.2.5 Organization Admin Endpoints
# =============================================================================


@router.get(
    "/me/dashboard",
    summary="Organization admin dashboard",
    description="Organization administrative dashboard. Requires ``organization_admin`` or ``admin`` role.",
)
async def org_admin_dashboard(
    current_user: UserResponse = Depends(require_organization_admin),
) -> dict[str, str]:
    """Return organization admin dashboard data."""
    return {
        "message": "Organization admin dashboard",
        "user_id": current_user.id,
        "role": _role_str(current_user),
    }


@router.get(
    "/me/staff",
    summary="List organization staff",
    description="List staff members in the authenticated user's organization.",
)
async def list_org_staff(
    current_user: UserResponse = Depends(require_organization_admin),
    service: UserService = Depends(get_user_service),
    role: UserRole | None = Query(default=None, description="Filter by role (defaults to organization_staff)"),
    limit: int = Query(default=100, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    if role is None:
        role = UserRole.ORGANIZATION_STAFF

    org_id = current_user.organization_id

    if org_id is None:
        return {
            "message": "Organization staff list",
            "users": [],
            "total": 0,
        }

    users = await service.get_users_in_organization(
        str(org_id), role=role, limit=limit, skip=skip
    )
    total = await service.count_users_in_organization(str(org_id), role=role)

    return {
        "message": "Organization staff list",
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "role": _role_str(u),
                "status": _status_str(u),
            }
            for u in users
        ],
        "total": total,
        "limit": limit,
        "skip": skip,
    }


@router.get(
    "/me/users/{user_id}",
    summary="Get organization user by ID",
    description="Get a user in the authenticated user's organization.",
)
async def get_org_user(
    user_id: str,
    current_user: UserResponse = Depends(require_organization_admin),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    if current_user.role == UserRole.ADMIN:
        user = await service.get_user_by_id(user_id)
        if not user:
            from app.exceptions.base import NotFoundException
            raise NotFoundException("User not found")
        return user

    org_id = current_user.organization_id
    if org_id is None:
        from app.exceptions.base import ForbiddenException
        raise ForbiddenException("Organization context required", error_code="FORBIDDEN")

    user = await service.get_user_by_id_in_organization(user_id, str(org_id))
    if not user:
        from app.exceptions.base import NotFoundException
        raise NotFoundException("User not found in your organization")
    return user


@router.get(
    "/me/department/{department_id}/staff",
    summary="List department staff",
    description="List staff members in a specific department (tenant-isolated).",
)
async def list_department_staff(
    department_id: str,
    current_user: UserResponse = Depends(require_organization_admin),
    service: OrganizationService = Depends(get_organization_service),
    user_service: UserService = Depends(get_user_service),
    role: UserRole | None = Query(default=None, description="Filter by role"),
    limit: int = Query(default=100, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    # Phase 1.8 hardening: the department must first be resolved through the
    # tenant-isolated service path. Without this, an org admin could list the
    # staff of another organization's department by changing the department_id
    # in the URL (cross-tenant IDOR). Admin retains global authority.
    await service.get_department(department_id, current_user)

    # Scope the staff query by the caller's organization in addition to the
    # department id (defense in depth for the tenant boundary). Global admins
    # keep the department-wide lookup.
    if current_user.role == UserRole.ADMIN:
        user_docs = await user_service._repository.find_users_in_department(
            department_id, role=role.value if role else None, limit=limit, skip=skip
        )
    else:
        user_org_id = current_user.organization_id
        if user_org_id is None:
            from app.exceptions.base import ForbiddenException
            raise ForbiddenException("Organization context required", error_code="FORBIDDEN")
        user_docs = await user_service._repository.find_users_in_organization_and_department(
            str(user_org_id), department_id, role=role.value if role else None, limit=limit, skip=skip
        )
    users = [user_service._to_user_response(doc) for doc in user_docs]

    return {
        "message": "Department staff list",
        "department_id": department_id,
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "role": _role_str(u),
                "status": _status_str(u),
            }
            for u in users
        ],
        "limit": limit,
        "skip": skip,
    }


# =============================================================================
# ORG-01 → ORG-04: Organization CRUD
# =============================================================================


@router.get(
    "",
    summary="List organizations",
    description="List organizations (Admin only per ORG-01).",
    response_model=PaginatedResponse,
)
async def list_organizations(
    current_user: UserResponse = Depends(require_admin),
    service: OrganizationService = Depends(get_organization_service),
    is_active: bool | None = Query(default=None, description="Filter by active status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> PaginatedResponse:
    skip = (page - 1) * page_size
    items = await service.list_organizations(is_active=is_active, limit=page_size, skip=skip)
    total = await service.count_organizations(is_active=is_active)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedResponse(
        success=True,
        message="Organizations retrieved",
        data={"items": [item.model_dump() for item in items]},
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        ),
    )


@router.post(
    "",
    summary="Create organization",
    description="Create a new organization (Admin only per ORG-02).",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization(
    request: OrganizationCreateRequest,
    current_user: UserResponse = Depends(require_admin),
    service: OrganizationService = Depends(get_organization_service),
) -> SuccessResponse:
    org = await service.create_organization(request, current_user)
    return SuccessResponse(
        success=True,
        message="Organization created successfully",
        data=org.model_dump(),
    )


@router.get(
    "/{id}",
    summary="Get organization details",
    description="Get organization by ID.",
    response_model=SuccessResponse,
)
async def get_organization(
    id: str,
    current_user: UserResponse = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
) -> SuccessResponse:
    org = await service.get_organization(id, current_user)
    return SuccessResponse(
        success=True,
        message="Organization retrieved",
        data=org.model_dump(),
    )


@router.put(
    "/{id}",
    summary="Update organization",
    description="Update organization details (Admin only per authoritative API contract).",
    response_model=SuccessResponse,
)
async def update_organization(
    id: str,
    request: OrganizationUpdateRequest,
    current_user: UserResponse = Depends(require_admin),
    service: OrganizationService = Depends(get_organization_service),
) -> SuccessResponse:
    org = await service.update_organization(id, request, current_user)
    return SuccessResponse(
        success=True,
        message="Organization updated successfully",
        data=org.model_dump(),
    )


@router.patch(
    "/{id}/status",
    summary="Toggle organization status",
    description="Activate or deactivate organization (Admin only per ORG-04).",
    response_model=SuccessResponse,
)
async def toggle_organization_status(
    id: str,
    request: OrganizationStatusRequest,
    current_user: UserResponse = Depends(require_admin),
    service: OrganizationService = Depends(get_organization_service),
) -> SuccessResponse:
    org = await service.toggle_organization_status(id, request.is_active, current_user)
    return SuccessResponse(
        success=True,
        message="Organization status updated successfully",
        data=org.model_dump(),
    )
