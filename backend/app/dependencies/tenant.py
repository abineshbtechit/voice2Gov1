"""Tenant isolation dependencies (Phase 1.2.5).

Provides dependencies for enforcing organization-scoped access control.
The authenticated user's organization_id serves as the authoritative tenant boundary.

Key principles:
- Never trust client-supplied organization_id for authorization
- Admin role bypasses tenant restrictions (global access)
- Organization-scoped roles (staff, org_admin) restricted to their own organization
- Citizen role not organization-scoped (own data + public feed only)
"""

from fastapi import Depends

from app.dependencies.auth import get_current_user
from app.exceptions.base import ForbiddenException
from app.schemas.user import UserResponse, UserRole


def get_current_organization(current_user: UserResponse = Depends(get_current_user)) -> str | None:
    """Extract the authenticated user's organization_id as the trusted tenant scope.

    Returns the user's organization_id for organization-scoped roles.
    Returns None for citizens (who are not organization members).
    Returns None for admin (who has global access).

    This is the authoritative tenant boundary - client-supplied organization IDs
    must never override this value for authorization decisions.
    """
    if current_user.role in (UserRole.ORGANIZATION_STAFF, UserRole.ORGANIZATION_ADMIN):
        return current_user.organization_id
    return None


def require_organization_context(
    current_user: UserResponse = Depends(get_current_user),
) -> str:
    """Require the current user to have an organization context.

    Raises ForbiddenException if the user is a citizen or has no organization_id.
    Returns the organization_id for use in tenant-scoped queries.
    """
    if current_user.role == UserRole.ADMIN:
        # Admin has global access - no organization context required
        raise ForbiddenException(
            "Admin users have global access; use get_current_organization for cross-org queries",
            error_code="FORBIDDEN",
        )

    org_id = current_user.organization_id
    if org_id is None:
        raise ForbiddenException(
            "Organization context required for this operation",
            error_code="FORBIDDEN",
        )
    return str(org_id)


def require_same_organization(
    resource_org_id: str,
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """Verify the resource belongs to the user's organization.

    For organization-scoped roles (staff, org_admin), the resource's organization_id
    must match the user's organization_id.
    Admin bypasses this check (global access).
    Citizens cannot access organization resources via this dependency.

    Args:
        resource_org_id: The organization_id of the resource being accessed.

    Returns:
        The authenticated user if access is allowed.

    Raises:
        ForbiddenException: If the user lacks organization context or
            the resource belongs to a different organization.
    """
    # Admin has global access
    if current_user.role == UserRole.ADMIN:
        return current_user

    # Citizens don't have organization context for resource access
    if current_user.role == UserRole.CITIZEN:
        raise ForbiddenException(
            "Organization context required",
            error_code="FORBIDDEN",
        )

    user_org_id = current_user.organization_id
    if user_org_id is None:
        raise ForbiddenException(
            "User has no organization assignment",
            error_code="FORBIDDEN",
        )

    if str(user_org_id) != str(resource_org_id):
        raise ForbiddenException(
            "Access denied: resource belongs to another organization",
            error_code="FORBIDDEN",
        )

    return current_user


def validate_department_belongs_to_organization(
    department_id: str,
    organization_id: str,
    current_user: UserResponse = Depends(get_current_user),
) -> None:
    """Validate that a department belongs to the specified organization.

    This prevents users from using department_ids from other organizations
    to bypass tenant isolation.

    Note: Actual database validation should be done in the repository/service layer.
    This dependency provides the authorization check pattern.
    """
    # Admin can access any department
    if current_user.role == UserRole.ADMIN:
        return

    # For org-scoped users, their organization must match
    if current_user.role in (UserRole.ORGANIZATION_STAFF, UserRole.ORGANIZATION_ADMIN):
        user_org_id = current_user.organization_id
        if user_org_id is None:
            raise ForbiddenException(
                "User has no organization assignment",
                error_code="FORBIDDEN",
            )
        if str(user_org_id) != str(organization_id):
            raise ForbiddenException(
                "Department belongs to another organization",
                error_code="FORBIDDEN",
            )
        return

    # Citizens cannot access department-scoped resources
    raise ForbiddenException(
        "Organization context required",
        error_code="FORBIDDEN",
    )
