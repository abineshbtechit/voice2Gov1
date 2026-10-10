"""Admin schemas for dashboard, users, audit logs, and settings (Phase 1.7).

Authoritative source: docs/database-schema.md §11, §12; docs/api-contract.md; docs/traceability-matrix.md.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import ConfigDict, Field

from app.schemas.base import BaseSchema
from app.schemas.user import UserRole, UserStatus


class SettingCategory(StrEnum):
    PRIORITY = "priority"
    GENERAL = "general"
    NOTIFICATION = "notification"
    SECURITY = "security"
    SLA = "sla"


class AdminDashboardData(BaseSchema):
    """Data payload for GET /api/v1/admin/dashboard."""

    total_users: int = Field(default=0, description="Total registered users")
    total_organizations: int = Field(default=0, description="Total organizations")
    total_departments: int = Field(default=0, description="Total departments")
    total_complaints: int = Field(default=0, description="Total complaints")
    complaints_by_status: dict[str, int] = Field(
        default_factory=dict, description="Complaint counts grouped by status"
    )
    avg_resolution_hours: float = Field(
        default=0.0, description="Average time to resolution in hours"
    )
    sla_compliance_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="SLA compliance fraction between 0.0 and 1.0"
    )


class AdminDashboardResponse(BaseSchema):
    """Response envelope for GET /api/v1/admin/dashboard."""

    success: bool = True
    message: str = "Dashboard stats"
    data: AdminDashboardData
    user_id: str | None = None
    role: str | None = None


class UserSuspendRequest(BaseSchema):
    """Request payload for PATCH /api/v1/admin/users/{id}/suspend."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500, description="Reason for suspension")


class AdminUserListItem(BaseSchema):
    """Safe representation of user in admin user listing."""

    id: str
    email: str
    phone: str
    full_name: str
    role: UserRole
    status: UserStatus
    organization_id: str | None = None
    department_id: str | None = None
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class AuditLogItem(BaseSchema):
    """Representation of an immutable audit record."""

    id: str
    actor_id: str
    actor_role: str
    action: str
    entity_type: str
    entity_id: str
    metadata: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime


class SettingItem(BaseSchema):
    """System setting response item."""

    key: str
    value: Any
    category: str
    description: str | None = None
    is_public: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SettingUpdateRequest(BaseSchema):
    """Request payload for PUT /api/v1/admin/settings/{key}."""

    model_config = ConfigDict(extra="forbid")

    value: Any = Field(..., description="New setting value")
    category: SettingCategory | None = Field(
        default=None, description="Category (defaults to current category or general)"
    )
    description: str | None = Field(default=None, max_length=500, description="Optional description")
