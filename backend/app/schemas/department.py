from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import ConfigDict, EmailStr, Field, field_validator
from pydantic.types import StringConstraints

from app.schemas.base import BaseSchema, ObjectIdStr


class DepartmentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class DepartmentCreateRequest(BaseSchema):
    """Request payload for POST /api/v1/departments."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=200, description="Department name")
    code: Annotated[
        str,
        StringConstraints(
            min_length=2, max_length=10, pattern=r"^[A-Z0-9_-]+$"
        ),
    ] = Field(..., description="Short code, unique within org")
    description: str | None = Field(default=None, max_length=500, description="Department description")
    contact_email: EmailStr | None = Field(default=None, description="Department contact email")
    contact_phone: Annotated[
        str | None,
        StringConstraints(pattern=r"^\+[1-9]\d{1,14}$"),
    ] = Field(default=None, description="Department contact phone")
    head_user_id: ObjectIdStr | None = Field(
        default=None, description="Department head user ID (organization_admin)"
    )
    organization_id: ObjectIdStr | None = Field(
        default=None, description="Organization ID (required if admin, ignored/derived if org_admin)"
    )

    @field_validator("code")
    @classmethod
    def validate_code_upper(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("name")
    @classmethod
    def validate_name_strip(cls, v: str) -> str:
        return v.strip()


class DepartmentUpdateRequest(BaseSchema):
    """Request payload for PUT /api/v1/departments/{id}."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=200, description="Department name")
    description: str | None = Field(default=None, max_length=500, description="Department description")
    contact_email: EmailStr | None = Field(default=None, description="Department contact email")
    contact_phone: Annotated[
        str | None,
        StringConstraints(pattern=r"^\+[1-9]\d{1,14}$"),
    ] = Field(default=None, description="Department contact phone")
    head_user_id: ObjectIdStr | None = Field(
        default=None, description="Department head user ID (organization_admin)"
    )
    is_active: bool | None = Field(default=None, description="Department active flag")

    @field_validator("name")
    @classmethod
    def validate_name_strip(cls, v: str | None) -> str | None:
        if v is not None:
            return v.strip()
        return v


class DepartmentInDB(BaseSchema):
    id: ObjectIdStr = Field(..., alias="_id")
    organization_id: ObjectIdStr = Field(..., description="Organization ID")
    name: str = Field(..., min_length=2, max_length=200, description="Department name")
    code: str = Field(..., min_length=2, max_length=10, description="Short code, unique within org")
    description: str | None = Field(default=None, max_length=500, description="Department description")
    contact_email: str | None = Field(default=None, description="Department contact email")
    contact_phone: str | None = Field(default=None, description="Department contact phone")
    head_user_id: ObjectIdStr | None = Field(
        default=None, description="Department head user ID (organization_admin)"
    )
    is_active: bool = Field(default=True, description="Whether department is active")
    created_at: datetime
    updated_at: datetime


class DepartmentResponse(BaseSchema):
    id: str
    organization_id: str
    name: str
    code: str
    description: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    head_user_id: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
