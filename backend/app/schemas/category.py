from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import ConfigDict, Field, field_validator
from pydantic.types import StringConstraints

from app.schemas.base import BaseSchema, ObjectIdStr


class CategoryStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class CategoryCreateRequest(BaseSchema):
    """Request payload for POST /api/v1/admin/categories (Admin only)."""

    model_config = ConfigDict(extra="forbid")

    organization_id: ObjectIdStr = Field(..., description="Organization ID for category")
    name: str = Field(..., min_length=2, max_length=100, description="Category name")
    description: str | None = Field(default=None, max_length=500, description="Category description")
    icon: str | None = Field(default=None, description="Icon identifier for UI")
    color: Annotated[str | None, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")] = Field(
        default=None, description="Hex color for UI"
    )
    default_department_id: ObjectIdStr = Field(
        ..., description="Default department for routing (must belong to same organization)"
    )
    severity_level: int = Field(default=1, ge=1, le=5, description="Severity 1-5 (1=Low, 5=Critical)")
    priority_weight: float = Field(default=1.0, ge=0.1, le=10.0, description="Priority weight multiplier")
    status: CategoryStatus = Field(default=CategoryStatus.ACTIVE, description="Category status")
    sort_order: int = Field(default=0, description="Display order")

    @field_validator("name")
    @classmethod
    def validate_name_strip(cls, v: str) -> str:
        return v.strip()


class CategoryUpdateRequest(BaseSchema):
    """Request payload for PUT /api/v1/admin/categories/{id} (Admin only)."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=100, description="Category name")
    description: str | None = Field(default=None, max_length=500, description="Category description")
    icon: str | None = Field(default=None, description="Icon identifier for UI")
    color: Annotated[str | None, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")] = Field(
        default=None, description="Hex color for UI"
    )
    default_department_id: ObjectIdStr | None = Field(
        default=None, description="Default department for routing (must belong to same organization)"
    )
    severity_level: int | None = Field(default=None, ge=1, le=5, description="Severity 1-5 (1=Low, 5=Critical)")
    priority_weight: float | None = Field(default=None, ge=0.1, le=10.0, description="Priority weight multiplier")
    status: CategoryStatus | None = Field(default=None, description="Category status")
    sort_order: int | None = Field(default=None, description="Display order")

    @field_validator("name")
    @classmethod
    def validate_name_strip(cls, v: str | None) -> str | None:
        if v is not None:
            return v.strip()
        return v


class CategoryInDB(BaseSchema):
    id: ObjectIdStr = Field(..., alias="_id")
    organization_id: ObjectIdStr = Field(..., description="Organization ID")
    name: str = Field(..., min_length=2, max_length=100, description="Category name")
    description: str | None = Field(default=None, max_length=500, description="Category description")
    icon: str | None = Field(default=None, description="Icon identifier for UI")
    color: Annotated[str | None, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")] = Field(
        default=None, description="Hex color for UI"
    )
    default_department_id: ObjectIdStr | None = Field(
        default=None, description="Default department for routing (must belong to same org)"
    )
    severity_level: int = Field(..., ge=1, le=5, description="Severity 1-5 (1=Low, 5=Critical)")
    priority_weight: float = Field(default=1.0, ge=0.1, le=10.0, description="Priority weight multiplier")
    status: CategoryStatus = Field(default=CategoryStatus.ACTIVE, description="Category status")
    sort_order: int = Field(default=0, description="Display order")
    created_at: datetime
    updated_at: datetime


class CategoryResponse(BaseSchema):
    id: str
    organization_id: str | None = None
    name: str
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    severity_level: int
    priority_weight: float
    default_department_id: str | None = None
    status: CategoryStatus | None = None
    sort_order: int | None = None
