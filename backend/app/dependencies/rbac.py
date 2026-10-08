"""Role-Based Access Control dependencies (Phase 1.2.4).

Provides reusable ``require_roles`` dependency that builds on top of
``get_current_user`` to enforce role-based authorization.

Authentication (``get_current_user``) answers: "Who is this user?"
Authorization (``require_roles``) answers: "Is this authenticated user allowed?"
"""

from collections.abc import Awaitable, Callable

from fastapi import Depends

from app.dependencies.auth import get_current_user
from app.exceptions.base import ForbiddenException
from app.schemas.user import UserResponse, UserRole


def _get_role_value(role: UserRole | str) -> str:
    """Extract string value from UserRole enum or string."""
    return role.value if isinstance(role, UserRole) else role


def require_roles(*allowed_roles: UserRole | str) -> Callable[[UserResponse], Awaitable[UserResponse]]:
    """Create a dependency that requires the current user to have one of the allowed roles.

    Args:
        *allowed_roles: One or more allowed roles (``UserRole`` enum or string values).

    Returns:
        A dependency function that returns the authenticated user on success,
        or raises ``ForbiddenException`` (HTTP 403) if the user's role is not allowed.

    Example:
        ```python
        # Admin-only endpoint
        @router.get("/admin/dashboard")
        async def admin_dashboard(user: UserResponse = Depends(require_roles(UserRole.ADMIN))):
            return {"message": "Admin dashboard"}

        # Organization admin or admin
        @router.get("/org/admin")
        async def org_admin_panel(user: UserResponse = Depends(require_roles(UserRole.ORGANIZATION_ADMIN, UserRole.ADMIN))):
            return {"message": "Org admin panel"}
        ```

    Note:
        - This dependency **must** be used after ``get_current_user`` has authenticated the user.
        - Unauthenticated requests (missing/invalid/expired token) are handled by ``get_current_user``
          and result in HTTP 401 (``UnauthorizedException``).
        - Authenticated users with insufficient role receive HTTP 403 (``ForbiddenException``).
        - Role values are matched exactly; no implicit hierarchy is assumed.
    """
    # Normalize to string values for comparison
    allowed_values = {_get_role_value(r) for r in allowed_roles}

    async def _checker(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
        user_role_value = _get_role_value(current_user.role)
        if user_role_value not in allowed_values:
            raise ForbiddenException(
                f"Required role(s): {', '.join(sorted(allowed_values))}",
                error_code="FORBIDDEN",
            )
        return current_user

    return _checker


# Convenience dependency functions for common role combinations
def require_admin(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    """Require ``admin`` role."""
    if _get_role_value(current_user.role) != UserRole.ADMIN.value:
        raise ForbiddenException("Required role: admin", error_code="FORBIDDEN")
    return current_user


def require_organization_admin(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    """Require ``organization_admin`` or ``admin`` role."""
    allowed = {UserRole.ORGANIZATION_ADMIN.value, UserRole.ADMIN.value}
    if _get_role_value(current_user.role) not in allowed:
        raise ForbiddenException("Required role: organization_admin or admin", error_code="FORBIDDEN")
    return current_user


def require_organization_staff(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    """Require ``organization_staff``, ``organization_admin``, or ``admin`` role."""
    allowed = {UserRole.ORGANIZATION_STAFF.value, UserRole.ORGANIZATION_ADMIN.value, UserRole.ADMIN.value}
    if _get_role_value(current_user.role) not in allowed:
        raise ForbiddenException("Required role: organization_staff, organization_admin, or admin", error_code="FORBIDDEN")
    return current_user


def require_any_authenticated(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    """Require any authenticated user (all four roles allowed)."""
    # All roles are allowed, so just return the user
    # This is essentially the same as get_current_user but explicit
    return current_user
