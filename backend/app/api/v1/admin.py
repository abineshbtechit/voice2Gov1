"""Admin API endpoints (Phase 1.2.4).

Protected endpoints that demonstrate RBAC enforcement for the ``admin`` role.
"""

from fastapi import APIRouter, Depends

from app.dependencies import require_admin
from app.schemas.user import UserResponse

router = APIRouter(prefix="/admin", tags=["admin"])


def _role_str(role: UserResponse) -> str:
    """Get role as string (handles both UserRole enum and str)."""
    return str(role.role)


@router.get(
    "/dashboard",
    summary="Admin dashboard",
    description="System-wide administrative dashboard. Requires ``admin`` role.",
)
async def admin_dashboard(
    current_user: UserResponse = Depends(require_admin),
) -> dict[str, str]:
    """Return admin dashboard data."""
    return {"message": "Admin dashboard", "user_id": current_user.id, "role": _role_str(current_user)}


@router.get(
    "/stats",
    summary="System statistics",
    description="System-wide statistics. Requires ``admin`` role.",
)
async def admin_stats(
    current_user: UserResponse = Depends(require_admin),
) -> dict[str, str]:
    """Return system statistics."""
    return {"message": "System statistics", "user_id": current_user.id, "role": _role_str(current_user)}
