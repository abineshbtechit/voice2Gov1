"""FastAPI dependencies (Phase 1.2.5)."""

from app.dependencies.rbac import (  # noqa: F401
    require_admin,
    require_any_authenticated,
    require_organization_admin,
    require_organization_staff,
    require_roles,
)
from app.dependencies.tenant import (  # noqa: F401
    get_current_organization,
    require_organization_context,
    require_same_organization,
    validate_department_belongs_to_organization,
)

__all__ = [
    "require_roles",
    "require_admin",
    "require_organization_admin",
    "require_organization_staff",
    "require_any_authenticated",
    "get_current_organization",
    "require_organization_context",
    "require_same_organization",
    "validate_department_belongs_to_organization",
]
