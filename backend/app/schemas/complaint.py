from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import ConfigDict, Field, model_validator
from pydantic.types import StringConstraints

from app.schemas.base import BaseSchema, ObjectIdStr


class ComplaintStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    ONGOING = "ONGOING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"
    CLOSED = "CLOSED"


class ComplaintVisibility(StrEnum):
    PUBLIC = "public"
    ORGANIZATION = "organization"
    PRIVATE = "private"


class GeoJSONPoint(BaseSchema):
    type: Annotated[str, StringConstraints(pattern=r"^Point$")] = Field(
        default="Point", description="GeoJSON type, must be 'Point'"
    )
    coordinates: Annotated[
        list[float], Field(min_length=2, max_length=2, description="[longitude, latitude]")
    ] = Field(..., description="GeoJSON coordinates: [longitude, latitude]")

    @model_validator(mode="after")
    def _validate_coordinates(self) -> "GeoJSONPoint":
        lng, lat = self.coordinates
        if not (-180 <= lng <= 180):
            raise ValueError(f"Longitude must be in [-180, 180], got {lng}")
        if not (-90 <= lat <= 90):
            raise ValueError(f"Latitude must be in [-90, 90], got {lat}")
        return self


class ComplaintBase(BaseSchema):
    title: str = Field(..., min_length=5, max_length=200, description="Complaint title")
    description: str = Field(..., min_length=10, max_length=5000, description="Complaint description")
    category_id: ObjectIdStr = Field(..., description="Category ID")
    location: GeoJSONPoint = Field(..., description="GeoJSON Point location")
    address: str | None = Field(default=None, max_length=500, description="Reverse-geocoded address")


class ComplaintCreateRequest(ComplaintBase):
    pass


class ComplaintUpdateRequest(BaseSchema):
    """Update request for citizen complaint updates (SUBMITTED only).

    Only fields explicitly permitted for citizen updates are included.
    Server-controlled fields (category_id, status, user_id, organization_id, etc.)
    are intentionally excluded.
    """
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=5, max_length=200, description="Complaint title")
    description: str | None = Field(default=None, min_length=10, max_length=5000, description="Complaint description")
    location: GeoJSONPoint | None = Field(default=None, description="GeoJSON Point location")
    address: str | None = Field(default=None, max_length=500, description="Reverse-geocoded address")


class ComplaintInDB(BaseSchema):
    id: ObjectIdStr = Field(..., alias="_id")
    complaint_number: str = Field(..., description="Human-readable complaint number (e.g., CMP-2024-001234)")
    user_id: ObjectIdStr = Field(..., description="Citizen user ID")
    organization_id: ObjectIdStr = Field(..., description="Organization ID")
    department_id: ObjectIdStr = Field(..., description="Department ID")
    category_id: ObjectIdStr = Field(..., description="Category ID")
    title: str
    description: str
    status: ComplaintStatus = Field(default=ComplaintStatus.SUBMITTED, description="Complaint status")
    visibility: ComplaintVisibility = Field(default=ComplaintVisibility.PUBLIC, description="Visibility level")
    location: GeoJSONPoint
    address: str | None = None
    assigned_to: ObjectIdStr | None = Field(default=None, description="Assigned staff user ID")
    assigned_at: datetime | None = Field(default=None, description="Assignment timestamp")
    completed_at: datetime | None = Field(default=None, description="Completion timestamp")
    rejected_at: datetime | None = Field(default=None, description="Rejection timestamp")
    rejection_reason: str | None = Field(default=None, description="Rejection reason")
    duplicate_of: ObjectIdStr | None = Field(default=None, description="Original complaint ID if duplicate")
    likes_count: int = Field(default=0, ge=0, description="Denormalized like count")
    community_engagement_score: int = Field(default=0, ge=0, description="Normalized engagement score")
    age_score: float = Field(default=0.0, ge=0.0, description="Time-based age score")
    organization_priority_boost: float = Field(default=0.0, ge=0.0, description="Org priority boost")
    sla_deadline: datetime | None = Field(default=None, description="SLA deadline")
    priority_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Computed priority (0-100)")
    severity_score: int = Field(default=1, ge=1, le=5, description="Severity from category (1-5)")
    metadata: dict[str, Any] | None = Field(default=None, description="Flexible extra data")
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _validate_severity_priority(self) -> "ComplaintInDB":
        if not (0 <= self.priority_score <= 100):
            raise ValueError("priority_score must be in [0, 100]")
        if not (1 <= self.severity_score <= 5):
            raise ValueError("severity_score must be in [1, 5]")
        return self


class ComplaintResponse(BaseSchema):
    id: ObjectIdStr
    complaint_number: str
    title: str
    description: str
    status: ComplaintStatus
    visibility: ComplaintVisibility
    priority_score: float
    severity_score: int
    location: GeoJSONPoint
    address: str | None = None
    category: dict[str, Any] | None = Field(default=None, description="Category summary")
    department: dict[str, Any] | None = Field(default=None, description="Department summary")
    assigned_to: dict[str, Any] | None = Field(default=None, description="Assigned staff summary")
    created_at: datetime
    updated_at: datetime


class ComplaintCreateResponse(BaseSchema):
    success: bool = True
    message: str
    data: ComplaintResponse


class ComplaintDetailResponse(BaseSchema):
    """Full complaint detail response for GET /complaints/{id}"""
    id: ObjectIdStr
    complaint_number: str
    title: str
    description: str
    status: ComplaintStatus
    visibility: ComplaintVisibility
    priority_score: float
    severity_score: int
    community_engagement_score: int
    age_score: float
    organization_priority_boost: float = Field(default=0.0, exclude=True)
    location: GeoJSONPoint
    address: str | None = None
    user: dict[str, Any] | None = Field(default=None, description="Citizen user summary")
    category: dict[str, Any] | None = Field(default=None, description="Category summary")
    department: dict[str, Any] | None = Field(default=None, description="Department summary")
    assigned_to: dict[str, Any] | None = Field(default=None, description="Assigned staff summary")
    images: list[dict[str, Any]] = Field(default_factory=list, description="Complaint images")
    sla_deadline: datetime | None = Field(default=None, exclude=True)
    created_at: datetime
    updated_at: datetime


class ComplaintDetailResponseWrapper(BaseSchema):
    success: bool = True
    message: str
    data: ComplaintDetailResponse


class ComplaintListItem(BaseSchema):
    """Complaint summary for list views"""
    id: ObjectIdStr
    complaint_number: str
    title: str
    status: ComplaintStatus
    priority_score: float
    category: dict[str, Any] | None = Field(default=None, description="Category summary")
    department: dict[str, Any] | None = Field(default=None, description="Department summary")
    assigned_to: dict[str, Any] | None = Field(default=None, description="Assigned staff summary")
    created_at: datetime
    updated_at: datetime


class MyComplaintsResponse(BaseSchema):
    success: bool = True
    message: str
    data: dict[str, Any]


class ComplaintStatusUpdateRequest(BaseSchema):
    """Request payload for PATCH /api/v1/complaints/{id}/status"""

    model_config = ConfigDict(extra="forbid")

    status: ComplaintStatus = Field(..., description="Target complaint status")
    reason: str | None = Field(
        default=None,
        min_length=1,
        max_length=2000,
        description="Reason or completion summary for the status change",
    )
    duplicate_of: ObjectIdStr | None = Field(
        default=None,
        description="Original complaint ID if target status is DUPLICATE",
    )


class ComplaintStatusUpdateData(BaseSchema):
    """Data envelope for status update response per API contract."""

    id: ObjectIdStr
    status: ComplaintStatus
    updated_at: datetime


class ComplaintStatusUpdateResponse(BaseSchema):
    """Response envelope for PATCH /api/v1/complaints/{id}/status"""

    success: bool = True
    message: str
    data: ComplaintStatusUpdateData


class ComplaintAssignRequest(BaseSchema):
    """Request payload for PATCH /api/v1/complaints/{id}/assign."""

    model_config = ConfigDict(extra="forbid")

    assigned_to: ObjectIdStr = Field(
        ..., description="User ID of the organization staff member to assign"
    )


class ComplaintAssignData(BaseSchema):
    """Data envelope for assignment response per docs/api-contract.md."""

    id: ObjectIdStr
    assigned_to: dict[str, Any] = Field(
        ..., description="Assigned staff summary ({id, name})"
    )
    assigned_at: datetime = Field(
        ..., description="Timestamp when complaint was assigned"
    )
    status: ComplaintStatus = Field(
        ..., description="Current complaint status (e.g. ONGOING)"
    )


class ComplaintAssignResponse(BaseSchema):
    """Response envelope for PATCH /api/v1/complaints/{id}/assign."""

    success: bool = True
    message: str
    data: ComplaintAssignData


class ComplaintCompleteRequest(BaseSchema):
    """Request payload for PATCH /api/v1/complaints/{id}/complete."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Completion summary / resolution notes",
    )
    completion_images: list[ObjectIdStr] = Field(
        default_factory=list,
        max_length=10,
        description="Optional list of complaint completion image IDs",
    )


class ComplaintCompleteData(BaseSchema):
    """Data envelope for completion response per API contract."""

    id: ObjectIdStr
    status: ComplaintStatus = Field(default=ComplaintStatus.COMPLETED)
    completed_at: datetime
    updated_at: datetime


class ComplaintCompleteResponse(BaseSchema):
    """Response envelope for PATCH /api/v1/complaints/{id}/complete."""

    success: bool = True
    message: str
    data: ComplaintCompleteData


class PriorityBreakdownWeights(BaseSchema):
    """Weights used in priority score calculation."""

    community_engagement: float = Field(..., description="Weight for community engagement")
    severity: float = Field(..., description="Weight for severity")
    age: float = Field(..., description="Weight for age")
    organization_boost: float = Field(..., description="Weight for organization boost")


class PriorityBreakdownComponents(BaseSchema):
    """Component scores in priority breakdown."""

    community_engagement_score: float = Field(..., description="Normalized weighted engagement score")
    severity_score: float = Field(..., description="Normalized weighted severity score")
    age_score: float = Field(..., description="Normalized weighted age score")
    organization_priority_boost: float = Field(..., description="Normalized weighted organization boost")


class PriorityRawComponents(BaseSchema):
    """Raw unweighted components used in calculation."""

    likes_count: int = Field(..., ge=0)
    severity_level: int = Field(..., ge=1, le=5)
    hours_since_creation: float = Field(..., ge=0.0)
    org_boost_value: float = Field(..., ge=0.0)


class PriorityBreakdownData(BaseSchema):
    """Data envelope for priority score breakdown per docs/api-contract.md and priority-engine.md."""

    priority_score: float = Field(..., ge=0.0, le=100.0)
    breakdown: PriorityBreakdownComponents
    weights: PriorityBreakdownWeights
    raw_components: PriorityRawComponents | None = None
    max_score: float = 100.0


class PriorityBreakdownResponse(BaseSchema):
    """Response envelope for GET /api/v1/complaints/{id}/priority."""

    success: bool = True
    message: str
    data: PriorityBreakdownData


class FeedCategorySummary(BaseSchema):
    id: ObjectIdStr
    name: str
    icon: str | None = None
    color: str | None = None


class FeedDepartmentSummary(BaseSchema):
    id: ObjectIdStr
    name: str


class FeedItem(BaseSchema):
    """Feed complaint item per docs/api-contract.md GET /feed."""

    id: ObjectIdStr
    title: str
    status: ComplaintStatus
    priority_score: float
    like_count: int
    user_liked: bool = False
    category: FeedCategorySummary | None = None
    department: FeedDepartmentSummary | None = None
    location: GeoJSONPoint
    address: str | None = None
    distance_km: float | None = None
    created_at: datetime
    image_count: int = 0


class FeedPagination(BaseSchema):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool


class FeedData(BaseSchema):
    items: list[FeedItem]
    pagination: FeedPagination


class FeedResponse(BaseSchema):
    """Response envelope for GET /api/v1/feed."""

    success: bool = True
    message: str = "Feed retrieved"
    data: FeedData


class ComplaintLikeData(BaseSchema):
    like_count: int
    user_liked: bool


class ComplaintLikeResponse(BaseSchema):
    """Response envelope for POST and DELETE /api/v1/complaints/{id}/like."""

    success: bool = True
    message: str
    data: ComplaintLikeData


class ComplaintLikeStatusResponse(BaseSchema):
    """Response envelope for GET /api/v1/complaints/{id}/like-status."""

    success: bool = True
    message: str = "Like status"
    data: ComplaintLikeData


class ComplaintLikesListData(BaseSchema):
    like_count: int
    user_liked: bool = False


class ComplaintLikesListResponse(BaseSchema):
    """Response envelope for GET /api/v1/complaints/{id}/likes."""

    success: bool = True
    message: str = "Likes retrieved"
    data: ComplaintLikesListData | ComplaintLikeData


