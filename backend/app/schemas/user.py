from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import ConfigDict, EmailStr, Field, model_validator
from pydantic.types import StringConstraints

from app.schemas.base import BaseSchema, ObjectIdStr


class UserRole(StrEnum):
    CITIZEN = "citizen"
    ORGANIZATION_STAFF = "organization_staff"
    ORGANIZATION_ADMIN = "organization_admin"
    ADMIN = "admin"


class UserStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"
    LOCKED = "locked"


class UserBase(BaseSchema):
    email: EmailStr = Field(..., description="User email address")
    phone: Annotated[str, StringConstraints(pattern=r"^\+[1-9]\d{1,14}$")] = Field(
        ..., description="User phone number in E.164 format"
    )
    full_name: str = Field(..., min_length=1, max_length=255, description="User full name")
    role: UserRole = Field(default=UserRole.CITIZEN, description="User role")
    status: UserStatus = Field(default=UserStatus.PENDING_VERIFICATION, description="User account status")
    organization_id: ObjectIdStr | None = Field(default=None, description="Organization ID for org users")
    department_id: ObjectIdStr | None = Field(default=None, description="Department ID for staff users")
    avatar_url: str | None = Field(default=None, description="Profile image URL")
    is_verified: bool = Field(default=False, description="Whether user has verified their contact")
    failed_login_attempts: int = Field(default=0, ge=0, description="Number of failed login attempts")
    locked_until: datetime | None = Field(default=None, description="Account lockout timestamp")

    @model_validator(mode="after")
    def _validate_organization_scope(self) -> "UserBase":
        """Enforce authoritative SRS role/scope rules.

        - ``organization_id`` is required for every non-citizen role.
        - ``department_id`` is required for ``organization_staff``.
        """
        # ``use_enum_values=True`` means role is stored as its string value, but
        # ``UserRole`` is a ``StrEnum`` so equality against the value still holds.
        if self.role != UserRole.CITIZEN and self.organization_id is None:
            raise ValueError("organization_id is required for non-citizen roles")
        if self.role == UserRole.ORGANIZATION_STAFF and self.department_id is None:
            raise ValueError("department_id is required for organization_staff role")
        return self


class UserCreate(BaseSchema):
    email: EmailStr = Field(..., description="User email address")
    phone: Annotated[str, StringConstraints(pattern=r"^\+[1-9]\d{1,14}$")] = Field(
        ..., description="User phone number in E.164 format"
    )
    full_name: str = Field(..., min_length=1, max_length=255, description="User full name")
    password: str = Field(..., min_length=8, max_length=128, description="User password")


class UserUpdate(BaseSchema):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    avatar_url: str | None = Field(default=None)
    role: UserRole | None = Field(default=None)
    status: UserStatus | None = Field(default=None)
    organization_id: ObjectIdStr | None = Field(default=None)
    department_id: ObjectIdStr | None = Field(default=None)


class UserInDB(UserBase):
    id: ObjectIdStr = Field(..., alias="_id")
    password_hash: str = Field(..., description="Bcrypt password hash")
    last_login_at: datetime | None = Field(default=None, description="Last login timestamp")
    created_at: datetime
    updated_at: datetime


class UserResponse(BaseSchema):
    id: ObjectIdStr
    email: EmailStr
    phone: str
    full_name: str
    role: UserRole
    status: UserStatus
    organization_id: ObjectIdStr | None = None
    department_id: ObjectIdStr | None = None
    avatar_url: str | None = None
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class UserRegisterRequest(BaseSchema):
    """Request payload for POST /auth/register.

    ``extra="forbid"``: registration is the most security-sensitive
    mass-assignment surface — a privilege field such as ``role`` or ``status``
    in the payload must be rejected (422), never silently ignored.
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(..., description="User email address")
    phone: Annotated[str, StringConstraints(pattern=r"^\+[1-9]\d{1,14}$")] = Field(
        ..., description="User phone number in E.164 format"
    )
    full_name: str = Field(..., min_length=1, max_length=255, description="User full name")
    password: str = Field(..., min_length=8, max_length=128, description="User password")


class UserRegisterResponse(BaseSchema):
    id: ObjectIdStr
    email: EmailStr
    phone: str
    full_name: str
    role: UserRole
    status: UserStatus
    is_verified: bool
    message: str


class UserLoginRequest(BaseSchema):
    identifier: str = Field(..., min_length=1, max_length=256, description="Email or phone number")
    # Do NOT enforce min_length on the login password field: a password that is
    # too short is still an invalid credential and must produce a 401 (not 422).
    # An attacker must not be able to infer policy violations vs wrong creds.
    password: str = Field(..., max_length=256, description="User password")


class UserLoginResponse(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
