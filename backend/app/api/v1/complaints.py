"""Complaint creation, retrieval, and update API endpoints (Phase 1.3.1, 1.3.2, 1.3.3).

POST /api/v1/complaints - Create a new complaint (citizen only)
GET /api/v1/complaints/{id} - Get complaint details
GET /api/v1/complaints/my - Get current user's complaints
PUT /api/v1/complaints/{id} - Update complaint (citizen, SUBMITTED only)
"""

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.dependencies.auth import get_current_user, get_optional_current_user
from app.dependencies.rate_limit import image_upload_rate_limit
from app.dependencies.rbac import require_roles
from app.dependencies.services import get_complaint_service, get_image_service
from app.schemas.complaint import (
    ComplaintAssignRequest,
    ComplaintAssignResponse,
    ComplaintCompleteRequest,
    ComplaintCompleteResponse,
    ComplaintCreateRequest,
    ComplaintCreateResponse,
    ComplaintDetailResponseWrapper,
    ComplaintLikeResponse,
    ComplaintLikesListResponse,
    ComplaintLikeStatusResponse,
    ComplaintStatusUpdateRequest,
    ComplaintStatusUpdateResponse,
    ComplaintUpdateRequest,
    MyComplaintsResponse,
    PriorityBreakdownResponse,
)
from app.schemas.complaint_image import (
    ComplaintImageDeleteResponse,
    ComplaintImageListResponse,
    ComplaintImageUploadResponse,
    ImageType,
)
from app.schemas.complaint_update import (
    ComplaintTimelineUpdateCreateRequest,
    ComplaintTimelineUpdateCreateResponse,
    ComplaintTimelineUpdateListResponse,
)
from app.schemas.user import UserResponse, UserRole
from app.services.complaint_service import ComplaintService
from app.services.image_service import ImageService

router = APIRouter(prefix="/complaints", tags=["Complaints"])


@router.post(
    "",
    response_model=ComplaintCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new complaint",
    description="Submit a new civic complaint. Requires citizen authentication.",
)
async def create_complaint(
    request: ComplaintCreateRequest,
    current_user: UserResponse = Depends(require_roles(UserRole.CITIZEN)),
    complaint_service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintCreateResponse:
    """Create a new complaint.

    - **Authentication**: Required (Bearer token)
    - **Authorization**: Citizen role only
    - **Request body**: title, description, category_id, location, address (optional)
    - **Server-controlled**: user_id, complaint_number, organization_id, department_id, status, visibility, timestamps
    - **Response**: 201 Created with complaint details
    """
    return await complaint_service.create_complaint(request, current_user)


@router.get(
    "/{complaint_id}",
    response_model=ComplaintDetailResponseWrapper,
    summary="Get complaint details",
    description="Retrieve a complaint by ID. Authorization based on user role and complaint visibility.",
)
async def get_complaint(
    complaint_id: str,
    current_user: UserResponse = Depends(get_current_user),
    complaint_service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintDetailResponseWrapper:
    """Get a complaint by ID.

    - **Authentication**: Required (Bearer token)
    - **Authorization**:
        - Admin: can access any complaint
        - Organization admin: complaints in their organization
        - Organization staff: complaints in their department
        - Citizen: own complaints only
    - **Response**: 200 with complaint details, 404 if not found/accessible
    """
    return await complaint_service.get_complaint_by_id(complaint_id, current_user)


@router.get(
    "/my",
    response_model=MyComplaintsResponse,
    summary="Get current user's complaints",
    description="Retrieve paginated list of current citizen's complaints. Supports status filtering.",
)
async def get_my_complaints(
    status: str | None = Query(None, description="Filter by complaint status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: UserResponse = Depends(get_current_user),
    complaint_service: ComplaintService = Depends(get_complaint_service),
) -> MyComplaintsResponse:
    """Get current user's complaints.

    - **Authentication**: Required (Bearer token)
    - **Authorization**: Citizen role only
    - **Query parameters**:
        - status: optional filter by status
        - page: page number (default 1)
        - page_size: items per page (default 20, max 100)
    - **Response**: 200 with paginated complaints
    """
    return await complaint_service.get_my_complaints(current_user, status, page, page_size)


@router.put(
    "/{complaint_id}",
    response_model=ComplaintDetailResponseWrapper,
    summary="Update complaint (citizen, SUBMITTED only)",
    description="Update a complaint owned by the authenticated citizen. Only allowed while complaint is in SUBMITTED status.",
)
async def update_complaint(
    complaint_id: str,
    request: ComplaintUpdateRequest,
    current_user: UserResponse = Depends(require_roles(UserRole.CITIZEN)),
    complaint_service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintDetailResponseWrapper:
    """Update a complaint by the owning citizen.

    - **Authentication**: Required (Bearer token)
    - **Authorization**: Citizen role only
    - **Conditions**: Complaint must be in SUBMITTED status (before assignment)
    - **Updatable fields**: title, description, location, address
    - **Server-controlled (ignored if provided)**: category_id, status, user_id, organization_id, department_id, complaint_number, status, visibility, timestamps
    - **Response**: 200 with updated complaint details
    - **Errors**: 401 (unauthenticated), 403 (forbidden), 404 (not found/access denied), 422 (validation error, invalid status)
    """
    return await complaint_service.update_by_citizen(complaint_id, current_user, request)


@router.patch(
    "/{complaint_id}/status",
    response_model=ComplaintStatusUpdateResponse,
    summary="Update complaint status",
    description=(
        "Transition complaint status through the authoritative state machine. "
        "Enforces strict role permissions, department scoping, assignment rules, "
        "required reasons, duplicate checks, and tenant isolation."
    ),
)
async def update_complaint_status(
    complaint_id: str,
    request: ComplaintStatusUpdateRequest,
    current_user: UserResponse = Depends(
        require_roles(
            UserRole.ORGANIZATION_STAFF,
            UserRole.ORGANIZATION_ADMIN,
            UserRole.ADMIN,
        )
    ),
    complaint_service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintStatusUpdateResponse:
    """Transition a complaint's status.

    - **Authentication**: Required (Bearer token)
    - **Authorization**: organization_staff, organization_admin, admin (citizens forbidden)
    - **State machine**: Enforces valid transitions and terminal state protection
    - **Response**: 200 with updated status and timestamp
    """
    return await complaint_service.change_status(complaint_id, current_user, request)


@router.patch(
    "/{complaint_id}/assign",
    response_model=ComplaintAssignResponse,
    summary="Assign complaint to department staff",
    description=(
        "Assign or reassign a complaint to an organization staff member. "
        "Authorized strictly for organization_admin and global admin."
    ),
)
async def assign_complaint(
    complaint_id: str,
    request: ComplaintAssignRequest,
    current_user: UserResponse = Depends(
        require_roles(
            UserRole.ORGANIZATION_ADMIN,
            UserRole.ADMIN,
        )
    ),
    complaint_service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintAssignResponse:
    """Assign or reassign a complaint to staff.

    - **Authentication**: Required (Bearer token)
    - **Authorization**: organization_admin, admin only (citizens and staff forbidden: 403)
    - **Tenant Scoping**: Must belong to the caller's organization (cross-tenant: 404)
    - **Validation**: Staff member must belong to the complaint's organization and department
    - **Lifecycle**: SUBMITTED -> ONGOING, ONGOING -> ONGOING (reassignment)
    - **Timeline**: Emits an 'assignment' update record
    - **Response**: 200 with assignment summary ({id, assigned_to, assigned_at, status})
    """
    return await complaint_service.assign(complaint_id, current_user, request)


@router.post(
    "/{complaint_id}/images",
    response_model=ComplaintImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload complaint images",
    description=(
        "Upload up to 5 complaint images (multipart/form-data). "
        "Image type authorization depends on the caller's role and ownership."
    ),
)
async def upload_complaint_images(
    complaint_id: str,
    files: list[UploadFile] = File(..., description="Image files (maximum 5 per request)"),
    image_type: ImageType = Form(
        ..., description="Image classification: evidence | progress | completion"
    ),
    current_user: UserResponse = Depends(get_current_user),
    _rate_limit: None = Depends(image_upload_rate_limit),
    image_service: ImageService = Depends(get_image_service),
) -> ComplaintImageUploadResponse:
    """Upload one or more images for a complaint.

    - **Authentication**: Required (Bearer token)
    - **Rate limit**: 10 uploads/minute/user
    - **Authorization**:
        - ``evidence``: complaint owner (citizen) only
        - ``progress``/``completion``: assigned organization staff or an
          organization admin in the complaint's organization
    - **Validation**: declared MIME + magic bytes, per-type size limits,
      sanitized filename, max 5 files
    - **Response**: 201 with ``{id, image_type, url, file_size, mime_type, created_at}``
    """
    return await image_service.upload_images(complaint_id, current_user, files, image_type)


@router.get(
    "/{complaint_id}/images",
    response_model=ComplaintImageListResponse,
    summary="List complaint images",
    description="List a complaint's images with time-limited signed URLs.",
)
async def list_complaint_images(
    complaint_id: str,
    current_user: UserResponse = Depends(get_current_user),
    image_service: ImageService = Depends(get_image_service),
) -> ComplaintImageListResponse:
    """List images for a complaint.

    - **Authentication**: Required (Bearer token)
    - **Authorization**: inherits complaint access (owner / staff / org admin / admin)
    - **Response**: 200 with image metadata and signed URLs
    """
    return await image_service.list_images(complaint_id, current_user)


@router.delete(
    "/{complaint_id}/images/{image_id}",
    response_model=ComplaintImageDeleteResponse,
    summary="Delete a complaint image",
    description="Soft-delete a complaint image. Only the uploader may delete their image.",
)
async def delete_complaint_image(
    complaint_id: str,
    image_id: str,
    current_user: UserResponse = Depends(get_current_user),
    image_service: ImageService = Depends(get_image_service),
) -> ComplaintImageDeleteResponse:
    """Soft-delete an image.

    - **Authentication**: Required (Bearer token)
    - **Authorization**: complaint access and image ownership (uploader only)
    - **Response**: 200 with the image id and soft-delete flag
    """
    return await image_service.delete_image(complaint_id, image_id, current_user)


@router.post(
    "/{complaint_id}/updates",
    response_model=ComplaintTimelineUpdateCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add complaint update",
    description="Add a progress update/note to a complaint. Authorized for organization staff, org admin, and global admin.",
)
async def add_complaint_update(
    complaint_id: str,
    request: ComplaintTimelineUpdateCreateRequest,
    current_user: UserResponse = Depends(
        require_roles(
            UserRole.ORGANIZATION_STAFF,
            UserRole.ORGANIZATION_ADMIN,
            UserRole.ADMIN,
        )
    ),
    complaint_service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintTimelineUpdateCreateResponse:
    """Add a progress note or timeline update to a complaint.

    - **Authentication**: Required (Bearer token)
    - **Authorization**: organization_staff, organization_admin, admin (citizens forbidden)
    - **Tenant Scoping**: Must belong to the caller's organization and department
    - **Response**: 201 with created update record
    """
    return await complaint_service.add_timeline_update(complaint_id, current_user, request)


@router.get(
    "/{complaint_id}/updates",
    response_model=ComplaintTimelineUpdateListResponse,
    summary="Get complaint updates",
    description="Retrieve all updates and timeline history for a complaint in chronological order.",
)
async def get_complaint_updates(
    complaint_id: str,
    current_user: UserResponse = Depends(get_current_user),
    complaint_service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintTimelineUpdateListResponse:
    """Retrieve timeline updates for a complaint.

    - **Authentication**: Required (Bearer token)
    - **Authorization**: owner (citizen sees public updates), org staff/admin (sees all), admin (sees all)
    - **Tenant Scoping**: Cross-tenant requests return 404
    - **Response**: 200 with list of timeline updates
    """
    return await complaint_service.get_timeline_updates(complaint_id, current_user)


@router.patch(
    "/{complaint_id}/complete",
    response_model=ComplaintCompleteResponse,
    summary="Complete a complaint",
    description=(
        "Mark a complaint as COMPLETED from PROCESSING. "
        "Authorized for assigned organization staff, organization admin, and global admin."
    ),
)
async def complete_complaint(
    complaint_id: str,
    request: ComplaintCompleteRequest,
    current_user: UserResponse = Depends(
        require_roles(
            UserRole.ORGANIZATION_STAFF,
            UserRole.ORGANIZATION_ADMIN,
            UserRole.ADMIN,
        )
    ),
    complaint_service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintCompleteResponse:
    """Complete a complaint.

    - **Authentication**: Required (Bearer token)
    - **Authorization**: assigned staff, org admin, admin (citizens forbidden: 403)
    - **Tenant Scoping**: Must belong to caller's organization (cross-tenant: 404)
    - **Validation**: Current status must be PROCESSING (422)
    - **Timeline**: Creates a 'completion' update record with non-null department_id
    - **Response**: 200 with completion summary
    """
    return await complaint_service.complete(complaint_id, current_user, request)


@router.get(
    "/{complaint_id}/priority",
    response_model=PriorityBreakdownResponse,
    summary="Get complaint priority breakdown",
    description="Retrieve detailed priority score calculation breakdown for a complaint.",
)
async def get_complaint_priority(
    complaint_id: str,
    current_user: UserResponse = Depends(get_current_user),
    complaint_service: ComplaintService = Depends(get_complaint_service),
) -> PriorityBreakdownResponse:
    """Get priority score calculation breakdown.

    - **Authentication**: Required (Bearer token)
    - **Authorization**: inherits standard complaint retrieval access
    - **Tenant Scoping**: Cross-tenant requests return 404
    - **Response**: 200 with priority score, breakdown, weights, and raw components
    """
    breakdown_data = await complaint_service.get_priority(complaint_id, current_user)
    return PriorityBreakdownResponse(
        success=True,
        message="Priority breakdown",
        data=breakdown_data,
    )


@router.post(
    "/{complaint_id}/like",
    response_model=ComplaintLikeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Like a complaint",
    description="Add a community like to a public complaint. Citizen only (FEED-05, FEED-08).",
)
async def like_complaint(
    complaint_id: str,
    current_user: UserResponse = Depends(require_roles(UserRole.CITIZEN)),
    complaint_service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintLikeResponse:
    """Like a complaint.

    - **Authentication**: Required (Bearer token)
    - **Authorization**: Citizen role only (403 for staff/admins)
    - **Validation**: Complaint must exist (404) and be public / non-terminal (422/403)
    - **Uniqueness**: Prevents duplicate likes (409 DUPLICATE_LIKE)
    - **Response**: 201 with updated like_count and user_liked=True
    """
    data = await complaint_service.like_complaint(complaint_id, current_user)
    return ComplaintLikeResponse(
        success=True,
        message="Complaint liked",
        data=data,
    )


@router.delete(
    "/{complaint_id}/like",
    response_model=ComplaintLikeResponse,
    summary="Unlike a complaint",
    description="Remove a community like from a complaint. Citizen only (FEED-06).",
)
async def unlike_complaint(
    complaint_id: str,
    current_user: UserResponse = Depends(require_roles(UserRole.CITIZEN)),
    complaint_service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintLikeResponse:
    """Unlike a complaint.

    - **Authentication**: Required (Bearer token)
    - **Authorization**: Citizen role only (403 for staff/admins)
    - **Safety**: Safe if like does not exist; returns current count
    - **Response**: 200 with updated like_count and user_liked=False
    """
    data = await complaint_service.unlike_complaint(complaint_id, current_user)
    return ComplaintLikeResponse(
        success=True,
        message="Complaint unliked",
        data=data,
    )


@router.get(
    "/{complaint_id}/like-status",
    response_model=ComplaintLikeStatusResponse,
    summary="Get complaint like status",
    description="Check whether current citizen user has liked the complaint (FEED-07).",
)
async def get_like_status(
    complaint_id: str,
    current_user: UserResponse = Depends(require_roles(UserRole.CITIZEN)),
    complaint_service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintLikeStatusResponse:
    """Check like status for authenticated citizen."""
    data = await complaint_service.get_like_status(complaint_id, current_user)
    return ComplaintLikeStatusResponse(
        success=True,
        message="Like status",
        data=data,
    )


@router.get(
    "/{complaint_id}/likes",
    response_model=ComplaintLikesListResponse,
    summary="Get complaint like count and list",
    description="Public endpoint to view like count and caller's like status if authenticated.",
)
async def get_complaint_likes(
    complaint_id: str,
    current_user: UserResponse | None = Depends(get_optional_current_user),
    complaint_service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintLikesListResponse:
    """Get complaint like count and status."""
    data = await complaint_service.get_likes_summary(complaint_id, current_user)
    return ComplaintLikesListResponse(
        success=True,
        message="Likes retrieved",
        data=data,
    )



