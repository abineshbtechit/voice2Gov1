"""Organization and Department schemas (Phase 1.7).

Authoritative source: docs/database-schema.md §2, §3; docs/api-contract.md; docs/traceability-matrix.md.
"""

from datetime import datetime
from typing import Annotated, Any

from pydantic import ConfigDict, EmailStr, Field, field_validator
from pydantic.types import StringConstraints

from app.schemas.base import BaseSchema, ObjectIdStr


class OrganizationSettings(BaseSchema):
    """Organization-specific settings schema."""

    model_config = ConfigDict(extra="allow")

    priority_weights: dict[str, float] | None = Field(
        default=None, description="Custom priority weights (Phase 2)"
    )
    auto_assign: bool = Field(default=False, description="Auto-assign complaints")
    sla_hours: int | None = Field(
        default=None, ge=1, le=8760, description="Default SLA in hours"
    )


class OrganizationCreateRequest(BaseSchema):
    """Request payload for POST /api/v1/organizations (Admin only)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=200, description="Organization name")
    code: Annotated[
        str,
        StringConstraints(
            min_length=2, max_length=10, pattern=r"^[A-Z0-9_-]+$"
        ),
    ] = Field(..., description="Short code (e.g. MCD, DDA), unique, uppercase")
    description: str | None = Field(
        default=None, max_length=1000, description="Details about organization"
    )
    address: str | None = Field(default=None, max_length=500, description="Physical address")
    contact_email: EmailStr | None = Field(default=None, description="Official contact email")
    contact_phone: Annotated[
        str | None,
        StringConstraints(pattern=r"^\+[1-9]\d{1,14}$"),
    ] = Field(default=None, description="Official phone in E.164 format")
    logo_url: str | None = Field(default=None, description="Logo image reference")
    website: str | None = Field(default=None, max_length=500, description="Official website")
    is_active: bool = Field(default=True, description="Default active state")
    settings: OrganizationSettings | None = Field(
        default=None, description="Organization-specific settings"
    )

    @field_validator("code")
    @classmethod
    def validate_code_upper(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("name")
    @classmethod
    def validate_name_strip(cls, v: str) -> str:
        return v.strip()


class OrganizationUpdateRequest(BaseSchema):
    """Request payload for PUT /api/v1/organizations/{id}."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None, min_length=2, max_length=200, description="Organization name"
    )
    description: str | None = Field(
        default=None, max_length=1000, description="Details about organization"
    )
    address: str | None = Field(default=None, max_length=500, description="Physical address")
    contact_email: EmailStr | None = Field(default=None, description="Official contact email")
    contact_phone: Annotated[
        str | None,
        StringConstraints(pattern=r"^\+[1-9]\d{1,14}$"),
    ] = Field(default=None, description="Official phone in E.164 format")
    logo_url: str | None = Field(default=None, description="Logo image reference")
    website: str | None = Field(default=None, max_length=500, description="Official website")
    settings: OrganizationSettings | None = Field(
        default=None, description="Organization-specific settings"
    )

    @field_validator("name")
    @classmethod
    def validate_name_strip(cls, v: str | None) -> str | None:
        if v is not None:
            return v.strip()
        return v


class OrganizationStatusRequest(BaseSchema):
    """Request payload for PATCH /api/v1/organizations/{id}/status (Admin only)."""

    model_config = ConfigDict(extra="forbid")

    is_active: bool = Field(..., description="Active status to set")


class OrganizationResponse(BaseSchema):
    """Response schema for Organization entity."""

    id: str
    name: str
    code: str
    description: str | None = None
    address: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    logo_url: str | None = None
    website: str | None = None
    is_active: bool
    settings: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class OrganizationInDB(BaseSchema):
    """MongoDB representation of an organization."""

    id: ObjectIdStr = Field(..., alias="_id")
    name: str
    code: str
    description: str | None = None
    address: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    logo_url: str | None = None
    website: str | None = None
    is_active: bool = True
    settings: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
