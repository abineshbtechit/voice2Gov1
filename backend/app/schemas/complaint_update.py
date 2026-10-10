"""Complaint update schemas (Phase 1.3.6).

Defines data models for the complaint timeline / update history subsystem.
Authoritative source: docs/database-schema.md §8 and api-contract.md.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import ConfigDict, Field, StringConstraints

from app.schemas.base import BaseSchema, ObjectIdStr
from app.schemas.complaint import ComplaintStatus


class UpdateType(StrEnum):
    """Canonical complaint update type enum.

    Authoritative values:
    - status_change: automatic or staff-triggered lifecycle transition
    - progress_note: progress update written by organization staff
    - assignment: staff assignment update record
    - completion: resolution / work finished record
    - rejection: complaint rejected record
    """

    STATUS_CHANGE = "status_change"
    PROGRESS_NOTE = "progress_note"
    ASSIGNMENT = "assignment"
    COMPLETION = "completion"
    REJECTION = "rejection"


class ComplaintTimelineUpdateCreateRequest(BaseSchema):
    """Client request payload for POST /api/v1/complaints/{id}/updates.

    Only fields explicitly permitted for client input are present.
    Server-controlled fields (complaint_id, organization_id, department_id,
    updated_by, previous_status, new_status, created_at) cannot be injected.
    """

    model_config = ConfigDict(extra="forbid")

    update_type: UpdateType = Field(
        default=UpdateType.PROGRESS_NOTE,
        description="Type of update (default: progress_note for staff notes)",
    )
    message: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
    ] = Field(..., description="Description / progress note (1-2000 characters)")
    images: list[ObjectIdStr] = Field(
        default_factory=list,
        max_length=10,
        description="Optional list of complaint_images IDs attached to this update",
    )
    is_public: bool = Field(
        default=True,
        description="Whether this update is visible to citizens (default: true)",
    )


class ComplaintTimelineUpdateResponse(BaseSchema):
    """Public representation of a complaint update timeline entry."""

    id: ObjectIdStr = Field(..., alias="_id", description="Update record ID")
    complaint_id: ObjectIdStr = Field(..., description="Referenced complaint ID")
    organization_id: ObjectIdStr = Field(..., description="Organization ID")
    department_id: ObjectIdStr = Field(..., description="Department ID")
    updated_by: ObjectIdStr = Field(..., description="Author user ID")
    update_type: UpdateType = Field(..., description="Update classification")
    previous_status: ComplaintStatus | str | None = Field(
        default=None, description="Previous complaint status (for status_change)"
    )
    new_status: ComplaintStatus | str | None = Field(
        default=None, description="New complaint status (for status_change)"
    )
    message: str = Field(..., description="Update description")
    images: list[ObjectIdStr] = Field(default_factory=list, description="Referenced image IDs")
    is_public: bool = Field(default=True, description="Public visibility flag")
    created_at: datetime = Field(..., description="Creation timestamp")


class ComplaintTimelineUpdateCreateResponse(BaseSchema):
    """Response envelope for POST /api/v1/complaints/{id}/updates."""

    success: bool = True
    message: str = "Complaint update added successfully"
    data: ComplaintTimelineUpdateResponse


class ComplaintTimelineUpdateListResponse(BaseSchema):
    """Response envelope for GET /api/v1/complaints/{id}/updates."""

    success: bool = True
    message: str = "Complaint updates retrieved successfully"
    data: list[ComplaintTimelineUpdateResponse] = Field(default_factory=list)
