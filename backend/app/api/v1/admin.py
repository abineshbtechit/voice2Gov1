"""Admin API endpoints (Phase 1.2.4 & Phase 1.7).

Protected endpoints that enforce system-wide administrative access (Admin role only).
Authoritative source: docs/api-contract.md §Admin, §Categories; docs/traceability-matrix.md ADM-01 → ADM-05, CAT-02.
"""


from fastapi import APIRouter, Depends, Query, status

from app.dependencies import require_admin
from app.dependencies.services import get_admin_service, get_category_service
from app.schemas.admin import (
    AdminDashboardResponse,
    SettingUpdateRequest,
    UserSuspendRequest,
)
from app.schemas.category import (
    CategoryCreateRequest,
    CategoryUpdateRequest,
)
from app.schemas.common import PaginatedResponse, PaginationMeta, SuccessResponse
from app.schemas.user import UserResponse, UserRole, UserStatus
from app.services.admin_service import AdminService
from app.services.category_service import CategoryService

router = APIRouter(prefix="/admin", tags=["admin"])


# =============================================================================
# ADM-01: Admin Dashboard & Stats
# =============================================================================


@router.get(
    "/dashboard",
    summary="Admin dashboard",
    description="System-wide administrative dashboard statistics. Requires ``admin`` role.",
    response_model=AdminDashboardResponse,
)
async def admin_dashboard(
    current_user: UserResponse = Depends(require_admin),
    service: AdminService = Depends(get_admin_service),
) -> AdminDashboardResponse:
    stats = await service.get_dashboard_stats()
    role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    return AdminDashboardResponse(
        success=True,
        message="Dashboard stats",
        data=stats,
        user_id=str(current_user.id),
        role=role_str,
    )


@router.get(
    "/stats",
    summary="System statistics",
    description="System-wide statistics. Requires ``admin`` role.",
    response_model=AdminDashboardResponse,
)
async def admin_stats(
    current_user: UserResponse = Depends(require_admin),
    service: AdminService = Depends(get_admin_service),
) -> AdminDashboardResponse:
    stats = await service.get_dashboard_stats()
    role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    return AdminDashboardResponse(
        success=True,
        message="System statistics",
        data=stats,
        user_id=str(current_user.id),
        role=role_str,
    )


# =============================================================================
# ADM-02: Admin User Management
# =============================================================================


@router.get(
    "/users",
    summary="List all users",
    description="List system users with filtering and search. Requires ``admin`` role.",
    response_model=PaginatedResponse,
)
async def list_users(
    current_user: UserResponse = Depends(require_admin),
    service: AdminService = Depends(get_admin_service),
    role: UserRole | None = Query(default=None, description="Filter by role"),
    status: UserStatus | None = Query(default=None, description="Filter by status"),
    search: str | None = Query(default=None, description="Search by name, email, or phone"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> PaginatedResponse:
    skip = (page - 1) * page_size
    users = await service.list_users(role=role, status=status, search=search, limit=page_size, skip=skip)
    total = await service.count_users(role=role, status=status, search=search)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedResponse(
        success=True,
        message="Users retrieved",
        data={"items": [u.model_dump() for u in users]},
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        ),
    )


@router.get(
    "/users/{id}",
    summary="Get user details",
    description="Get user details by ID. Requires ``admin`` role.",
    response_model=SuccessResponse,
)
async def get_user_detail(
    id: str,
    current_user: UserResponse = Depends(require_admin),
    service: AdminService = Depends(get_admin_service),
) -> SuccessResponse:
    user = await service.get_user_detail(id)
    return SuccessResponse(
        success=True,
        message="User details retrieved",
        data=user.model_dump(),
    )


@router.patch(
    "/users/{id}/suspend",
    summary="Suspend user",
    description="Suspend a user account. Requires ``admin`` role.",
    response_model=SuccessResponse,
)
async def suspend_user(
    id: str,
    request: UserSuspendRequest | None = None,
    current_user: UserResponse = Depends(require_admin),
    service: AdminService = Depends(get_admin_service),
) -> SuccessResponse:
    reason = request.reason if request else None
    user = await service.suspend_user(id, reason=reason, current_user=current_user)
    return SuccessResponse(
        success=True,
        message="User suspended successfully",
        data=user.model_dump(),
    )


@router.patch(
    "/users/{id}/activate",
    summary="Activate user",
    description="Activate a user account. Requires ``admin`` role.",
    response_model=SuccessResponse,
)
async def activate_user(
    id: str,
    current_user: UserResponse = Depends(require_admin),
    service: AdminService = Depends(get_admin_service),
) -> SuccessResponse:
    user = await service.activate_user(id, current_user=current_user)
    return SuccessResponse(
        success=True,
        message="User activated successfully",
        data=user.model_dump(),
    )


# =============================================================================
# CAT-02: Admin Category Management
# =============================================================================


@router.post(
    "/categories",
    summary="Create category",
    description="Create a new complaint category (Admin only per CAT-02).",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    request: CategoryCreateRequest,
    current_user: UserResponse = Depends(require_admin),
    service: CategoryService = Depends(get_category_service),
) -> SuccessResponse:
    cat = await service.create_category(request, current_user)
    return SuccessResponse(
        success=True,
        message="Category created successfully",
        data=cat.model_dump(),
    )


@router.put(
    "/categories/{id}",
    summary="Update category",
    description="Update a complaint category (Admin only per CAT-02).",
    response_model=SuccessResponse,
)
async def update_category(
    id: str,
    request: CategoryUpdateRequest,
    current_user: UserResponse = Depends(require_admin),
    service: CategoryService = Depends(get_category_service),
) -> SuccessResponse:
    cat = await service.update_category(id, request, current_user)
    return SuccessResponse(
        success=True,
        message="Category updated successfully",
        data=cat.model_dump(),
    )


@router.delete(
    "/categories/{id}",
    summary="Delete category",
    description="Soft-deactivate category (Admin only per CAT-02).",
    response_model=SuccessResponse,
)
async def delete_category(
    id: str,
    current_user: UserResponse = Depends(require_admin),
    service: CategoryService = Depends(get_category_service),
) -> SuccessResponse:
    await service.delete_category(id, current_user)
    return SuccessResponse(
        success=True,
        message="Category deleted successfully",
        data=None,
    )


# =============================================================================
# ADM-03 & ADM-04: Immutable Audit Logs
# =============================================================================


@router.get(
    "/audit-logs",
    summary="Get audit logs",
    description="Query immutable audit log history. Requires ``admin`` role.",
    response_model=PaginatedResponse,
)
async def get_audit_logs(
    current_user: UserResponse = Depends(require_admin),
    service: AdminService = Depends(get_admin_service),
    actor_id: str | None = Query(default=None, description="Filter by actor ID"),
    entity_type: str | None = Query(default=None, description="Filter by entity type"),
    entity_id: str | None = Query(default=None, description="Filter by entity ID"),
    action: str | None = Query(default=None, description="Filter by action name"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> PaginatedResponse:
    skip = (page - 1) * page_size
    logs = await service.get_audit_logs(
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        limit=page_size,
        skip=skip,
    )
    total = await service.count_audit_logs(
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedResponse(
        success=True,
        message="Audit logs retrieved",
        data={"items": [log.model_dump() for log in logs]},
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        ),
    )


# =============================================================================
# ADM-05: System Settings
# =============================================================================


@router.get(
    "/settings",
    summary="Get all system settings",
    description="Retrieve system settings. Requires ``admin`` role.",
    response_model=SuccessResponse,
)
async def get_settings(
    current_user: UserResponse = Depends(require_admin),
    service: AdminService = Depends(get_admin_service),
) -> SuccessResponse:
    items = await service.get_all_settings()
    return SuccessResponse(
        success=True,
        message="Settings retrieved",
        data=[item.model_dump() for item in items],
    )


@router.put(
    "/settings/{key:path}",
    summary="Update system setting",
    description="Update system setting value. Requires ``admin`` role.",
    response_model=SuccessResponse,
)
async def update_setting(
    key: str,
    request: SettingUpdateRequest,
    current_user: UserResponse = Depends(require_admin),
    service: AdminService = Depends(get_admin_service),
) -> SuccessResponse:
    setting = await service.update_setting(key, request, current_user)
    return SuccessResponse(
        success=True,
        message="Setting updated successfully",
        data=setting.model_dump(),
    )
