"""Complaint creation and retrieval service (Phase 1.3.1, 1.3.2).

Handles the complete complaint lifecycle:
- Creation
- Retrieval
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from bson import ObjectId
from pymongo import ReturnDocument

from app.exceptions.base import (
    BusinessLogicException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.repositories.category_repository import CategoryRepository
from app.repositories.complaint_image_repository import ComplaintImageRepository
from app.repositories.complaint_like_repository import ComplaintLikeRepository
from app.repositories.complaint_repository import ComplaintRepository
from app.repositories.complaint_update_repository import ComplaintUpdateRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.user_repository import UserRepository
from app.schemas.base import ObjectIdStr
from app.schemas.complaint import (
    ComplaintAssignData,
    ComplaintAssignRequest,
    ComplaintAssignResponse,
    ComplaintCompleteData,
    ComplaintCompleteRequest,
    ComplaintCompleteResponse,
    ComplaintCreateRequest,
    ComplaintCreateResponse,
    ComplaintDetailResponse,
    ComplaintDetailResponseWrapper,
    ComplaintLikeData,
    ComplaintListItem,
    ComplaintResponse,
    ComplaintStatus,
    ComplaintStatusUpdateData,
    ComplaintStatusUpdateRequest,
    ComplaintStatusUpdateResponse,
    ComplaintUpdateRequest,
    ComplaintVisibility,
    FeedCategorySummary,
    FeedData,
    FeedDepartmentSummary,
    FeedItem,
    FeedPagination,
    GeoJSONPoint,
    MyComplaintsResponse,
    PriorityBreakdownData,
)
from app.schemas.complaint_update import (
    ComplaintTimelineUpdateCreateRequest,
    ComplaintTimelineUpdateCreateResponse,
    ComplaintTimelineUpdateListResponse,
    ComplaintTimelineUpdateResponse,
    UpdateType,
)
from app.schemas.user import UserResponse, UserRole
from app.services.complaint_state_machine import ComplaintStateMachine
from app.services.priority_service import PriorityService

if TYPE_CHECKING:
    pass


class ComplaintService:
    def __init__(
        self,
        complaint_repo: ComplaintRepository,
        category_repo: CategoryRepository,
        department_repo: DepartmentRepository,
        complaint_update_repo: ComplaintUpdateRepository | None = None,
        complaint_image_repo: ComplaintImageRepository | None = None,
        user_repo: UserRepository | None = None,
        priority_service: PriorityService | None = None,
        like_repo: ComplaintLikeRepository | None = None,
        notification_service: Any | None = None,
    ) -> None:
        self._complaint_repo = complaint_repo
        self._category_repo = category_repo
        self._department_repo = department_repo
        self._complaint_update_repo = complaint_update_repo
        self._complaint_image_repo = complaint_image_repo
        self._user_repo = user_repo
        self._priority_service = priority_service
        self._like_repo = like_repo
        self._notification_service = notification_service


    async def create_complaint(
        self, request: ComplaintCreateRequest, current_user: UserResponse
    ) -> ComplaintCreateResponse:
        """Create a new complaint for an authenticated citizen.

        Server-controlled fields (client cannot set):
        - user_id (from authenticated user)
        - complaint_number (generated server-side)
        - organization_id (resolved from category)
        - department_id (resolved from category.default_department_id)
        - status (always SUBMITTED on creation)
        - visibility (default PUBLIC)
        - likes_count (default 0)
        - priority_score (default 0, computed later)
        - severity_score (copied from category)
        - community_engagement_score (default 0)
        - age_score (default 0)
        - assigned_to (None on creation)
        - assigned_at (None on creation)
        - timestamps (server-generated)
        """
        # 1. Validate category exists and is active
        category = await self._validate_category(request.category_id)
        if not category:
            raise NotFoundException("Category not found or inactive")

        # 2. Resolve organization from category
        organization_id = category["organization_id"]

        # 3. Resolve department from category's default_department_id
        if not category.get("default_department_id"):
            raise ValidationException(
                "Category has no default department configured for routing",
                errors=[
                    {
                        "field": "category_id",
                        "message": "Category is not routable: missing default_department_id",
                        "code": "ROUTING_CONFIGURATION_ERROR",
                    }
                ],
            )

        department = await self._validate_department(
            category["default_department_id"], organization_id
        )
        if not department:
            raise NotFoundException(
                "Default department not found or inactive in the category's organization"
            )

        # Store FK ids as strings (the representation every complaint query in
        # ComplaintRepository uses). department["_id"] is an ObjectId from the
        # driver, so it must be normalized here — otherwise org-staff complaint
        # retrieval, which filters `department_id` as a string, would never match.
        department_id = str(department["_id"])

        # 4. Generate complaint number (server-side, collision-safe)
        complaint_number = await self._generate_complaint_number()

        # 5. Build server-controlled complaint document
        now = datetime.now(UTC)
        complaint_data = {
            "complaint_number": complaint_number,
            "user_id": current_user.id,
            "organization_id": organization_id,
            "department_id": department_id,
            "category_id": request.category_id,
            "title": request.title.strip(),
            "description": request.description.strip(),
            "status": ComplaintStatus.SUBMITTED.value,
            "visibility": ComplaintVisibility.PUBLIC.value,
            "location": request.location.model_dump(),
            "address": request.address.strip() if request.address else None,
            "assigned_to": None,
            "assigned_at": None,
            "completed_at": None,
            "rejected_at": None,
            "rejection_reason": None,
            "duplicate_of": None,
            "likes_count": 0,
            "community_engagement_score": 0,
            "age_score": 0.0,
            "organization_priority_boost": 0.0,
            "sla_deadline": None,
            "priority_score": 0.0,
            "severity_score": category.get("severity_level", 1),
            "metadata": None,
            "created_at": now,
            "updated_at": now,
        }

        # 6. Persist
        complaint_id = await self._complaint_repo.create(complaint_data)

        # 7. Fetch the created complaint for response
        created_complaint = await self._complaint_repo.find_by_id(complaint_id)
        if not created_complaint:
            raise ValidationException("Failed to retrieve created complaint")

        # 8. Return safe response
        response_data = self._to_complaint_response(created_complaint, category, department)

        return ComplaintCreateResponse(
            success=True,
            message="Complaint submitted successfully",
            data=response_data,
        )

    async def _validate_category(self, category_id: str) -> dict[str, Any] | None:
        """Validate category exists and is active."""
        category = await self._category_repo.find_by_id_active(category_id)
        return category

    async def _validate_department(
        self, department_id: str, organization_id: str
    ) -> dict[str, Any] | None:
        """Validate department exists, is active, and belongs to the organization."""
        department = await self._department_repo.find_by_id_active_in_org(
            department_id, organization_id
        )
        return department

    async def _generate_complaint_number(self) -> str:
        """Generate a collision-safe complaint number.

        Format: CMP-YYYY-NNNNNN (year + 6-digit sequential).

        Implemented as a single atomic ``find_one_and_update`` on a per-year
        counter document, so two concurrent creations can never produce the
        same sequence — the unique ``idx_complaints_complaint_number`` index
        would otherwise reject the loser with a spurious 409. The counter is
        lazily seeded from the number of existing complaints for the year, so
        it stays correct for databases that already contain complaints.
        """
        now = datetime.now(UTC)
        year = now.year

        collection = getattr(self._complaint_repo, "_collection", None)
        database = getattr(collection, "database", None)
        if database is None:
            # Non-Mongo repository (test double): fall back to count-based.
            count = await self._complaint_repo.count_complaints_by_year(year)
            return f"CMP-{year}-{count + 1:06d}"

        base = await self._complaint_repo.count_complaints_by_year(year)
        counters = database["counters"]
        doc = await counters.find_one_and_update(
            {"_id": f"complaint_number_{year}"},
            [{"$set": {"seq": {"$add": [{"$ifNull": ["$seq", base]}, 1]}}}],
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        sequence = int(doc["seq"])
        return f"CMP-{year}-{sequence:06d}"

    def _to_complaint_response(
        self,
        complaint: dict[str, Any],
        category: dict[str, Any],
        department: dict[str, Any],
    ) -> ComplaintResponse:
        """Convert complaint document to safe response model."""
        return ComplaintResponse(
            id=ObjectIdStr(complaint["_id"]),
            complaint_number=complaint["complaint_number"],
            title=complaint["title"],
            description=complaint["description"],
            status=ComplaintStatus(complaint["status"]),
            visibility=ComplaintVisibility(complaint["visibility"]),
            priority_score=complaint["priority_score"],
            severity_score=complaint["severity_score"],
            location=complaint["location"],
            address=complaint.get("address"),
            category={
                "id": str(category["_id"]),
                "name": category["name"],
                "severity_level": category["severity_level"],
            },
            department={
                "id": str(department["_id"]),
                "name": department["name"],
            },
            assigned_to=None,
            created_at=complaint["created_at"],
            updated_at=complaint["updated_at"],
        )

    async def get_complaint_by_id(
        self, complaint_id: str, current_user: UserResponse
    ) -> ComplaintDetailResponseWrapper:
        """Get a complaint by ID with authorization checks.

        Authorization rules:
        - Admin: can access any complaint
        - Organization staff/admin: can access complaints in their organization
        - Citizen: can only access their own complaints
        """
        # Try to find the complaint based on user's role
        complaint = None

        if current_user.role == "admin":
            complaint = await self._complaint_repo.find_by_id_for_admin(complaint_id)
        elif current_user.role in ("organization_staff", "organization_admin"):
            if not current_user.organization_id:
                raise NotFoundException("Complaint not found")
            org_id = str(current_user.organization_id)
            if current_user.role == "organization_admin":
                complaint = await self._complaint_repo.find_by_id_in_organization(
                    complaint_id, org_id
                )
            else:
                # Organization staff - scope by department
                if not current_user.department_id:
                    raise NotFoundException("Complaint not found")
                dept_id = str(current_user.department_id)
                complaint = await self._complaint_repo.find_by_id_for_organization_staff(
                    complaint_id, org_id, dept_id
                )
        else:
            # Citizen - can only access their own complaints
            complaint = await self._complaint_repo.find_by_id_for_user(
                complaint_id, str(current_user.id)
            )

        if not complaint:
            raise NotFoundException("Complaint not found")

        # Check visibility rules
        if not self._can_view_complaint(complaint, current_user):
            raise NotFoundException("Complaint not found")

        # Fetch related data for response
        category = await self._category_repo.find_by_id(complaint["category_id"])
        department = await self._department_repo.find_by_id(complaint["department_id"])

        if not category or not department:
            raise NotFoundException("Related category or department not found")

        return await self._to_complaint_detail_response(complaint, category, department)

    def _can_view_complaint(self, complaint: dict[str, Any], current_user: UserResponse) -> bool:
        """Check if user can view the complaint based on visibility rules."""
        # Admin can see everything
        if current_user.role == "admin":
            return True

        # Organization staff/admin can see complaints in their org
        if current_user.role in ("organization_staff", "organization_admin"):
            if complaint.get("organization_id") == current_user.organization_id:
                return True
            return False

        # Citizen can see:
        # - Their own complaints
        # - Public complaints (if API contract allows)
        if current_user.role == "citizen":
            if complaint.get("user_id") == current_user.id:
                return True
            # For now, citizens can only see their own complaints
            # Public visibility in feed is handled separately
            return False

        return False

    async def get_my_complaints(
        self,
        current_user: UserResponse,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> MyComplaintsResponse:
        """Get current user's complaints with pagination."""
        if current_user.role != "citizen":
            raise ValidationException(
                "Only citizens can access their own complaints",
                errors=[
                    {
                        "field": "role",
                        "message": "Only citizens can access this endpoint",
                        "code": "FORBIDDEN",
                    }
                ],
            )

        if page_size > 100:
            page_size = 100

        complaints = await self._complaint_repo.find_user_complaints(
            current_user.id, status, page, page_size
        )
        total = await self._complaint_repo.count_user_complaints(current_user.id, status)

        # Batch fetches (one query each) instead of a per-item lookup (N+1).
        cat_ids = {str(c["category_id"]) for c in complaints if c.get("category_id")}
        dept_ids = {str(d["department_id"]) for d in complaints if d.get("department_id")}
        categories_map = {
            str(c["_id"]): c for c in await self._category_repo.find_by_ids(list(cat_ids))
        }
        departments_map = {
            str(d["_id"]): d for d in await self._department_repo.find_by_ids(list(dept_ids))
        }

        items = []
        for complaint in complaints:
            category = categories_map.get(str(complaint["category_id"]))
            department = departments_map.get(str(complaint["department_id"]))
            items.append(
                ComplaintListItem(
                    id=ObjectIdStr(complaint["_id"]),
                    complaint_number=complaint["complaint_number"],
                    title=complaint["title"],
                    status=ComplaintStatus(complaint["status"]),
                    priority_score=complaint["priority_score"],
                    category={"id": str(category["_id"]), "name": category["name"]} if category else None,
                    department={"id": str(department["_id"]), "name": department["name"]} if department else None,
                    assigned_to=None,
                    created_at=complaint["created_at"],
                    updated_at=complaint["updated_at"],
                )
            )

        total_pages = (total + page_size - 1) // page_size
        return MyComplaintsResponse(
            success=True,
            message="Complaints retrieved",
            data={
                "items": items,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_items": total,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1,
                },
            },
        )

    async def update_by_citizen(
        self,
        complaint_id: str,
        current_user: UserResponse,
        request: ComplaintUpdateRequest,
    ) -> ComplaintDetailResponseWrapper:
        """Update a complaint by its owning citizen.

        Only allows updates when:
        - The complaint belongs to the authenticated citizen
        - The complaint is in SUBMITTED status (before assignment)
        - Only permitted fields are provided (title, description, location, address)

        Raises:
            NotFoundException: If complaint doesn't exist or user doesn't own it
            ValidationException: If complaint is not in SUBMITTED status or invalid fields
        """
        # Verify complaint exists and belongs to user
        complaint = await self._complaint_repo.find_by_id_for_user(
            complaint_id, current_user.id
        )
        if not complaint:
            raise NotFoundException("Complaint not found or access denied")

        # Validate category exists and is active
        category = await self._validate_category(complaint["category_id"])
        if not category:
            raise NotFoundException("Category not found or inactive")

        # Validate department exists and belongs to the same organization
        if not category.get("default_department_id"):
            raise ValidationException(
                "Category has no default department configured for routing",
                errors=[
                    {
                        "field": "category_id",
                        "message": "Category is not routable: missing default_department_id",
                        "code": "ROUTING_CONFIGURATION_ERROR",
                    }
                ],
            )

        department = await self._validate_department(
            category["default_department_id"], complaint["organization_id"]
        )
        if not department:
            raise NotFoundException(
                "Default department not found or inactive in the category's organization"
            )

        # Only allow updates when complaint is SUBMITTED (before assignment)
        if complaint.get("status") != ComplaintStatus.SUBMITTED.value:
            raise ValidationException(
                "Complaint can only be updated while in SUBMITTED status",
                errors=[
                    {
                        "field": "status",
                        "message": f"Cannot update complaint in {complaint.get('status')} status",
                        "code": "INVALID_STATUS_TRANSITION",
                    }
                ],
            )

        # Build update data from request (only non-None fields)
        update_data = request.model_dump(exclude_unset=True, exclude_none=True)
        if not update_data:
            raise ValidationException(
                "At least one field must be provided for update",
                errors=[{"field": "body", "message": "No fields provided for update", "code": "VALIDATION_ERROR"}],
            )

        # Update the complaint
        updated = await self._complaint_repo.update_by_user(
            complaint_id, current_user.id, update_data
        )
        if not updated:
            raise NotFoundException("Complaint not found or update failed")

        # Fetch updated complaint for response
        updated_complaint = await self._complaint_repo.find_by_id_for_user(
            complaint_id, current_user.id
        )
        if not updated_complaint:
            raise NotFoundException("Complaint not found after update")

        # Fetch related data for response
        category = await self._category_repo.find_by_id(updated_complaint["category_id"])
        department = await self._department_repo.find_by_id(updated_complaint["department_id"])

        if not category or not department:
            raise NotFoundException("Related category or department not found")

        return ComplaintDetailResponseWrapper(
            success=True,
            message="Complaint updated successfully",
            data=await self._build_complaint_detail_response(
                updated_complaint, category, department, include_internal_fields=False
            ),
        )

    async def _build_complaint_detail_response(
        self,
        complaint: dict[str, Any],
        category: dict[str, Any],
        department: dict[str, Any],
        include_internal_fields: bool = False,
    ) -> ComplaintDetailResponse:
        """Convert complaint document to detailed response model (for updates)."""
        data = {
            "id": ObjectIdStr(complaint["_id"]),
            "complaint_number": complaint["complaint_number"],
            "title": complaint["title"],
            "description": complaint["description"],
            "status": ComplaintStatus(complaint["status"]),
            "visibility": ComplaintVisibility(complaint["visibility"]),
            "priority_score": complaint["priority_score"],
            "severity_score": complaint["severity_score"],
            "community_engagement_score": complaint.get("community_engagement_score", 0),
            "age_score": complaint.get("age_score", 0.0),
            "location": complaint["location"],
            "address": complaint.get("address"),
            "user": None,
            "category": {
                "id": str(category["_id"]),
                "name": category["name"],
                "severity_level": category["severity_level"],
            },
            "department": {
                "id": str(department["_id"]),
                "name": department["name"],
            },
            "assigned_to": None,
            "images": [],
            "created_at": complaint["created_at"],
            "updated_at": complaint["updated_at"],
        }

        if include_internal_fields:
            data["organization_priority_boost"] = complaint.get("organization_priority_boost", 0.0)
            data["sla_deadline"] = complaint.get("sla_deadline")

        # Fetch user info for the citizen who created the complaint
        user_summary = await self._get_complaint_owner_summary(complaint)
        data["user"] = user_summary

        # Fetch category and department info
        data["category"] = {
            "id": str(category["_id"]),
            "name": category["name"],
            "severity_level": category["severity_level"],
        }
        data["department"] = {
            "id": str(department["_id"]),
            "name": department["name"],
        }
        data["assigned_to"] = None
        data["images"] = []
        data["sla_deadline"] = complaint.get("sla_deadline")
        data["created_at"] = complaint["created_at"]
        data["updated_at"] = complaint["updated_at"]

        return ComplaintDetailResponse(**data)

    async def _get_complaint_owner_summary(self, complaint: dict[str, Any]) -> dict[str, Any] | None:
        """Resolve the complaint creator's safe summary via the user repository."""
        if self._user_repo is None:
            return None
        user = await self._user_repo.find_by_id(str(complaint["user_id"]))
        if not user:
            return None
        return {
            "id": str(user["_id"]),
            "name": user.get("full_name"),
        }

    async def _to_complaint_detail_response(
        self,
        complaint: dict[str, Any],
        category: dict[str, Any],
        department: dict[str, Any],
    ) -> ComplaintDetailResponseWrapper:
        """Convert complaint document to detailed response model."""
        user_summary = await self._get_complaint_owner_summary(complaint)

        return ComplaintDetailResponseWrapper(
            success=True,
            message="Complaint retrieved",
            data=ComplaintDetailResponse(
                id=ObjectIdStr(complaint["_id"]),
                complaint_number=complaint["complaint_number"],
                title=complaint["title"],
                description=complaint["description"],
                status=ComplaintStatus(complaint["status"]),
                visibility=ComplaintVisibility(complaint["visibility"]),
                priority_score=complaint["priority_score"],
                severity_score=complaint["severity_score"],
                community_engagement_score=complaint.get("community_engagement_score", 0),
                age_score=complaint.get("age_score", 0.0),
                organization_priority_boost=complaint.get("organization_priority_boost", 0.0),
                location=complaint["location"],
                address=complaint.get("address"),
                user=user_summary,
                category={
                    "id": str(category["_id"]),
                    "name": category["name"],
                    "severity_level": category["severity_level"],
                },
                department={
                    "id": str(department["_id"]),
                    "name": department["name"],
                },
                assigned_to=None,
                images=[],
                sla_deadline=complaint.get("sla_deadline"),
                created_at=complaint["created_at"],
                updated_at=complaint["updated_at"],
            ),
        )

    async def change_status(
        self,
        complaint_id: str,
        current_user: UserResponse,
        request: ComplaintStatusUpdateRequest,
    ) -> ComplaintStatusUpdateResponse:
        """Execute a complaint status transition enforcing the formal state machine.

        Validates:
        1. Access under actor role and tenant boundary (404/403).
        2. Role authorization for requested transition (403).
        3. Allowed state transitions (422 INVALID_STATUS_TRANSITION).
        4. Terminal state immutability (422 INVALID_STATUS_TRANSITION).
        5. Department scoping for organization staff (403 FORBIDDEN).
        6. Assignment scoping for organization staff (fails closed with 403 FORBIDDEN if unassigned).
        7. Required reason for terminal/completion transitions (422 REASON_REQUIRED).
        8. Duplicate reference validation (422 DUPLICATE_REF_REQUIRED, DUPLICATE_SELF_REFERENCE, etc.).
        9. Atomic update against concurrent status races (409 STATUS_CONFLICT).
        10. Side effects: audit log entry and deterministic notification event dispatch.
        """
        actor_role = current_user.role if isinstance(current_user.role, UserRole) else UserRole(str(current_user.role))

        # Citizens are never permitted to transition complaint status
        if actor_role == UserRole.CITIZEN:
            raise ForbiddenException(
                "Citizens cannot change complaint status",
                error_code="FORBIDDEN",
            )

        # 1. Fetch complaint with tenant scoping
        complaint = await self._get_complaint_for_status_change(complaint_id, current_user, actor_role)
        if complaint is None:
            raise NotFoundException("Complaint not found", error_code="COMPLAINT_NOT_FOUND")

        current_status = ComplaintStatus(complaint["status"])
        target_status = ComplaintStatus(request.status)

        # 2. Check if current status is terminal
        if ComplaintStateMachine.is_terminal(current_status):
            raise BusinessLogicException(
                f"Cannot change status: complaint is in terminal state '{current_status.value}'",
                error_code="INVALID_STATUS_TRANSITION",
            )

        # 3. Check transition rule
        rule = ComplaintStateMachine.get_rule(current_status, target_status)
        if rule is None:
            raise BusinessLogicException(
                f"Invalid status transition from {current_status.value} to {target_status.value}",
                error_code="INVALID_STATUS_TRANSITION",
            )

        clean_reason = request.reason.strip() if request.reason else None

        self._validate_status_transition(
            current_status=current_status,
            target_status=target_status,
            rule=rule,
            actor_role=actor_role,
            current_user=current_user,
            complaint=complaint,
            clean_reason=clean_reason,
        )

        # 8. Duplicate reference validation
        if rule.requires_duplicate_of:
            await self._validate_duplicate_reference(request.duplicate_of, complaint)

        # 9. Build atomic update fields
        now = datetime.now(UTC)
        update_fields = self._build_status_update_fields(target_status, clean_reason, request.duplicate_of, now)

        # Atomic transition with optimistic lock on expected_status and tenant scoping
        org_id_scope = str(current_user.organization_id) if actor_role != UserRole.ADMIN else None
        applied = await self._complaint_repo.transition_status(
            complaint_id=str(complaint["_id"]),
            expected_status=current_status.value,
            new_status=target_status.value,
            update_fields=update_fields,
            organization_id=org_id_scope,
        )

        if not applied:
            # Re-fetch to distinguish between concurrent modification and not found
            fresh = await self._complaint_repo.find_by_id(str(complaint["_id"]))
            if fresh is None:
                raise NotFoundException("Complaint not found", error_code="COMPLAINT_NOT_FOUND")
            raise ConflictException(
                f"Complaint status was concurrently modified from {current_status.value} to {fresh.get('status')}",
                error_code="STATUS_CONFLICT",
            )

        # 10. Side effects: Audit log record & deterministic notification event trigger
        await self._record_status_change_audit(
            complaint=complaint,
            current_user=current_user,
            actor_role=actor_role,
            previous_status=current_status.value,
            new_status=target_status.value,
            reason=clean_reason,
            timestamp=now,
        )

        return ComplaintStatusUpdateResponse(
            success=True,
            message=f"Status updated to {target_status.value}",
            data=ComplaintStatusUpdateData(
                id=ObjectIdStr(str(complaint["_id"])),
                status=target_status,
                updated_at=now,
            ),
        )

    async def _get_complaint_for_status_change(
        self,
        complaint_id: str,
        current_user: UserResponse,
        actor_role: UserRole,
    ) -> dict[str, Any] | None:
        """Retrieve complaint ensuring tenant isolation boundary."""
        if actor_role == UserRole.ADMIN:
            return await self._complaint_repo.find_by_id_for_admin(complaint_id)

        if not current_user.organization_id:
            return None

        org_id = str(current_user.organization_id)
        if actor_role == UserRole.ORGANIZATION_ADMIN:
            return await self._complaint_repo.find_by_id_in_organization(complaint_id, org_id)

        if actor_role == UserRole.ORGANIZATION_STAFF:
            # Staff can only retrieve complaints within their organization
            return await self._complaint_repo.find_by_id_in_organization(complaint_id, org_id)

        return None

    def _validate_status_transition(
        self,
        current_status: ComplaintStatus,
        target_status: ComplaintStatus,
        rule: Any,
        actor_role: UserRole,
        current_user: UserResponse,
        complaint: dict[str, Any],
        clean_reason: str | None,
    ) -> None:
        """Enforce role, department, assignment, and reason rules."""
        # 4. Check actor role permission
        if actor_role not in rule.allowed_roles:
            raise ForbiddenException(
                f"Role '{actor_role.value}' is not authorized to transition from "
                f"{current_status.value} to {target_status.value}",
                error_code="FORBIDDEN",
            )

        # 5. Department match requirement for organization staff
        if rule.requires_department_match and actor_role == UserRole.ORGANIZATION_STAFF:
            user_dept = str(current_user.department_id) if current_user.department_id else None
            complaint_dept = str(complaint.get("department_id")) if complaint.get("department_id") else None
            if not user_dept or user_dept != complaint_dept:
                raise ForbiddenException(
                    "Staff member must belong to the department assigned to this complaint",
                    error_code="FORBIDDEN",
                )

        # 6. Assignment requirement for organization staff (fail closed if not assigned)
        if rule.requires_assigned_staff and actor_role == UserRole.ORGANIZATION_STAFF:
            assigned_to = str(complaint.get("assigned_to")) if complaint.get("assigned_to") else None
            user_id = str(current_user.id)
            if not assigned_to or assigned_to != user_id:
                raise ForbiddenException(
                    "Only the assigned staff member can transition this complaint",
                    error_code="FORBIDDEN",
                )

        # 7. Reason validation
        if rule.requires_reason and not clean_reason:
            raise ValidationException(
                f"Reason is required for transition to {target_status.value}",
                error_code="REASON_REQUIRED",
            )

    async def _validate_duplicate_reference(
        self,
        duplicate_of: Any,
        complaint: dict[str, Any],
    ) -> None:
        """Validate duplicate reference existence, self-reference, and tenant scope."""
        if not duplicate_of:
            raise ValidationException(
                "duplicate_of is required when marking a complaint as DUPLICATE",
                error_code="DUPLICATE_REF_REQUIRED",
            )
        if str(duplicate_of) == str(complaint["_id"]):
            raise ValidationException(
                "Complaint cannot be marked as a duplicate of itself",
                error_code="DUPLICATE_SELF_REFERENCE",
            )
        original_complaint = await self._complaint_repo.find_by_id(str(duplicate_of))
        if original_complaint is None:
            raise ValidationException(
                "Referenced duplicate complaint does not exist",
                error_code="DUPLICATE_REF_NOT_FOUND",
            )
        if str(original_complaint.get("organization_id")) != str(complaint.get("organization_id")):
            raise ValidationException(
                "Referenced duplicate complaint must belong to the same organization",
                error_code="CROSS_TENANT_DUPLICATE_REF",
            )

    def _build_status_update_fields(
        self,
        target_status: ComplaintStatus,
        clean_reason: str | None,
        duplicate_of: Any,
        now: datetime,
    ) -> dict[str, Any]:
        """Build status-specific update fields."""
        fields: dict[str, Any] = {"updated_at": now}
        if target_status == ComplaintStatus.REJECTED:
            fields["rejected_at"] = now
            fields["rejection_reason"] = clean_reason
        elif target_status == ComplaintStatus.COMPLETED:
            fields["completed_at"] = now
        elif target_status == ComplaintStatus.DUPLICATE:
            fields["duplicate_of"] = str(duplicate_of)
        return fields

    async def _record_status_change_audit(
        self,
        complaint: dict[str, Any],
        current_user: UserResponse,
        actor_role: UserRole,
        previous_status: str,
        new_status: str,
        reason: str | None,
        timestamp: datetime,
    ) -> None:
        """Best-effort audit logging and event dispatch for complaint status change."""
        audit_doc = {
            "actor_id": str(current_user.id),
            "actor_role": actor_role.value,
            "action": "complaint.status_changed",
            "entity_type": "complaint",
            "entity_id": str(complaint["_id"]),
            "metadata": {
                "complaint_number": complaint.get("complaint_number"),
                "previous_status": previous_status,
                "new_status": new_status,
                "reason": reason,
            },
            "created_at": timestamp,
        }
        try:
            # Access database collection directly for audit log insertion if collection exists
            db = getattr(self._complaint_repo._collection, "database", None)
            if db is not None:
                await db["audit_logs"].insert_one(audit_doc)
        except Exception:
            # Audit logging failure must never fail the committed transition
            pass

        # Also create a complaint_updates timeline entry of update_type status_change
        if self._complaint_update_repo is not None:
            try:
                dept_id = complaint.get("department_id")
                if not dept_id:
                    # Invariant: valid complaints must have department_id (docs/database-schema.md §5)
                    raise ValueError(f"Complaint {complaint.get('_id')} is missing department_id")

                update_doc: dict[str, Any] = {
                    "complaint_id": ObjectId(str(complaint["_id"])),
                    "organization_id": ObjectId(str(complaint["organization_id"])),
                    "department_id": ObjectId(str(dept_id)),
                    "updated_by": ObjectId(str(current_user.id)),
                    "update_type": UpdateType.STATUS_CHANGE.value,
                    "previous_status": previous_status,
                    "new_status": new_status,
                    "message": reason or f"Complaint status updated to {new_status}",
                    "images": [],
                    "is_public": True,
                    "created_at": timestamp,
                }
                await self._complaint_update_repo.create(update_doc)
            except Exception:
                # Timeline persistence failure must never fail the committed status transition
                pass

        # Trigger in-app notification (NOTIF-08)
        if self._notification_service is not None:
            try:
                from app.schemas.notification import NotificationType
                from app.services.notification_service import NotificationPayload

                cid = str(complaint["_id"])
                ctitle = complaint.get("title", "Complaint")
                owner_id = str(complaint.get("user_id"))

                notif_type = NotificationType.STATUS_UPDATE
                title = "Complaint Status Updated"
                message = f"Your complaint '{ctitle}' is now {new_status}"
                metadata = {
                    "previous_status": previous_status,
                    "new_status": new_status,
                    "deep_link": f"app://complaint/{cid}",
                }

                if new_status == ComplaintStatus.REJECTED.value:
                    notif_type = NotificationType.REJECTION
                    title = "Complaint Rejected"
                    message = f"Your complaint '{ctitle}' was rejected: {reason or 'No reason provided'}"
                    metadata["reason"] = reason or ""
                elif new_status == ComplaintStatus.DUPLICATE.value:
                    notif_type = NotificationType.DUPLICATE
                    title = "Duplicate Complaint"
                    dup_ref = complaint.get("duplicate_of")
                    message = f"Your complaint '{ctitle}' is a duplicate of #{dup_ref or ''}"
                    metadata["duplicate_of"] = str(dup_ref) if dup_ref else ""

                payload = NotificationPayload(
                    user_id=owner_id,
                    type=notif_type,
                    title=title,
                    message=message,
                    complaint_id=cid,
                    metadata=metadata,
                )
                await self._notification_service.create_notification(payload)
            except Exception:
                # Notification dispatch failure must never abort the primary complaint flow
                pass

    def _validate_timeline_actor_scope(
        self,
        complaint: dict[str, Any],
        current_user: UserResponse,
        actor_role: UserRole,
    ) -> None:
        if actor_role == UserRole.CITIZEN:
            raise ForbiddenException(
                "Citizens cannot add complaint progress updates",
                error_code="FORBIDDEN",
            )
        if actor_role == UserRole.ORGANIZATION_STAFF:
            complaint_dept = str(complaint.get("department_id")) if complaint.get("department_id") else None
            user_dept = str(current_user.department_id) if current_user.department_id else None
            if complaint_dept and user_dept != complaint_dept:
                raise ForbiddenException(
                    "Staff member must belong to the department assigned to this complaint",
                    error_code="FORBIDDEN",
                )

    async def _validate_timeline_images(
        self,
        complaint_id: str,
        image_ids_str: Sequence[str] | None,
    ) -> list[ObjectId]:
        if not image_ids_str:
            return []
        if self._complaint_image_repo is None:
            raise ValidationException("Image repository not available", error_code="IMAGE_REPO_UNAVAILABLE")

        validated: list[ObjectId] = []
        for img_id_str in image_ids_str:
            img_doc = await self._complaint_image_repo.find_by_id(
                image_id=str(img_id_str),
                complaint_id=str(complaint_id),
            )
            if img_doc is None:
                raise ValidationException(
                    f"Image {img_id_str} not found or does not belong to this complaint",
                    error_code="INVALID_IMAGE_REFERENCE",
                )
            img_type = img_doc.get("image_type")
            if img_type not in ("progress", "completion"):
                raise ValidationException(
                    f"Image {img_id_str} is of type '{img_type}'. Only 'progress' or 'completion' images may be attached.",
                    error_code="INVALID_IMAGE_TYPE",
                )
            validated.append(ObjectId(str(img_doc["_id"])))
        return validated

    async def add_timeline_update(
        self,
        complaint_id: str,
        current_user: UserResponse,
        request: ComplaintTimelineUpdateCreateRequest,
    ) -> ComplaintTimelineUpdateCreateResponse:
        """Create a progress note or timeline update for a complaint."""
        actor_role = (
            current_user.role
            if isinstance(current_user.role, UserRole)
            else UserRole(str(current_user.role))
        )
        # 1. Fetch complaint with tenant scoping
        complaint = await self._get_complaint_for_status_change(complaint_id, current_user, actor_role)
        if complaint is None:
            raise NotFoundException("Complaint not found", error_code="COMPLAINT_NOT_FOUND")

        # 2. Scope checks
        self._validate_timeline_actor_scope(complaint, current_user, actor_role)

        # 3. Disallow client injecting status_change via POST updates
        update_type = UpdateType(request.update_type)
        if update_type == UpdateType.STATUS_CHANGE:
            raise ValidationException(
                "status_change updates are created automatically via status transitions",
                error_code="INVALID_UPDATE_TYPE",
            )

        # 4. Image validation
        image_ids = await self._validate_timeline_images(str(complaint["_id"]), request.images)

        # 5. Build timeline update record
        dept_id = complaint.get("department_id")
        if not dept_id:
            raise ValidationException("Complaint is missing required department_id", error_code="MISSING_DEPARTMENT")

        now = datetime.now(UTC)
        update_doc = {
            "complaint_id": ObjectId(str(complaint["_id"])),
            "organization_id": ObjectId(str(complaint["organization_id"])),
            "department_id": ObjectId(str(dept_id)),
            "updated_by": ObjectId(str(current_user.id)),
            "update_type": update_type.value,
            "previous_status": None,
            "new_status": None,
            "message": request.message,
            "images": image_ids,
            "is_public": request.is_public,
            "created_at": now,
        }

        if self._complaint_update_repo is None:
            raise ValidationException("Complaint update repository not configured", error_code="SERVER_ERROR")

        update_id = await self._complaint_update_repo.create(update_doc)

        # 6. Best-effort audit logging
        try:
            db = getattr(self._complaint_repo._collection, "database", None)
            if db is not None:
                await db["audit_logs"].insert_one({
                    "actor_id": str(current_user.id),
                    "actor_role": actor_role.value,
                    "action": "complaint.update_added",
                    "entity_type": "complaint_update",
                    "entity_id": update_id,
                    "metadata": {
                        "complaint_id": str(complaint["_id"]),
                        "update_type": update_type.value,
                        "is_public": request.is_public,
                        "image_count": len(image_ids),
                    },
                    "created_at": now,
                })
        except Exception:
            pass

        # Trigger citizen comment notification if update is public (NOTIF-02, NOTIF-08)
        if request.is_public and self._notification_service is not None:
            try:
                from app.schemas.notification import NotificationType
                from app.services.notification_service import NotificationPayload

                cid = str(complaint["_id"])
                ctitle = complaint.get("title", "Complaint")
                owner_id = str(complaint.get("user_id"))
                author_name = current_user.full_name or "Staff"
                payload = NotificationPayload(
                    user_id=owner_id,
                    type=NotificationType.COMMENT,
                    title="New Update on Your Complaint",
                    message=f"{author_name} added an update to '{ctitle}'",
                    complaint_id=cid,
                    metadata={
                        "complaint_number": complaint.get("complaint_number"),
                        "update_id": str(update_id),
                        "deep_link": f"app://complaint/{cid}",
                    },
                )
                await self._notification_service.create_notification(payload)
            except Exception:
                pass

        return ComplaintTimelineUpdateCreateResponse(
            success=True,
            message="Complaint update added successfully",
            data=ComplaintTimelineUpdateResponse(
                _id=ObjectIdStr(update_id),
                complaint_id=ObjectIdStr(str(complaint["_id"])),
                organization_id=ObjectIdStr(str(complaint["organization_id"])),
                department_id=ObjectIdStr(str(dept_id)),
                updated_by=ObjectIdStr(str(current_user.id)),
                update_type=update_type,
                previous_status=None,
                new_status=None,
                message=request.message,
                images=[ObjectIdStr(str(oid)) for oid in image_ids],
                is_public=request.is_public,
                created_at=now,
            ),
        )

    async def get_timeline_updates(
        self,
        complaint_id: str,
        current_user: UserResponse,
    ) -> ComplaintTimelineUpdateListResponse:
        """Get timeline updates for a complaint.

        Authorization:
        - Admin: sees all updates (public + internal).
        - Org Admin / Org Staff (same organization): sees all updates (public + internal).
        - Citizen (owner): sees only is_public == True updates.
        - Other callers / cross-tenant: 404 COMPLAINT_NOT_FOUND.
        """
        actor_role = (
            current_user.role
            if isinstance(current_user.role, UserRole)
            else UserRole(str(current_user.role))
        )

        complaint: dict[str, Any] | None = None
        is_public_only = False

        if actor_role == UserRole.ADMIN:
            complaint = await self._complaint_repo.find_by_id_for_admin(complaint_id)
        elif actor_role in (UserRole.ORGANIZATION_ADMIN, UserRole.ORGANIZATION_STAFF):
            if not current_user.organization_id:
                raise NotFoundException("Complaint not found", error_code="COMPLAINT_NOT_FOUND")
            org_id = str(current_user.organization_id)
            complaint = await self._complaint_repo.find_by_id_in_organization(complaint_id, org_id)
        else:
            # Citizen - only if owner
            complaint = await self._complaint_repo.find_by_id_for_user(complaint_id, str(current_user.id))
            is_public_only = True

        if complaint is None:
            raise NotFoundException("Complaint not found", error_code="COMPLAINT_NOT_FOUND")

        if self._complaint_update_repo is None:
            return ComplaintTimelineUpdateListResponse(
                success=True,
                message="Complaint updates retrieved successfully",
                data=[],
            )

        raw_updates = await self._complaint_update_repo.find_by_complaint(
            complaint_id=str(complaint["_id"]),
            is_public_only=is_public_only,
        )

        items: list[ComplaintTimelineUpdateResponse] = []
        for doc in raw_updates:
            items.append(
                ComplaintTimelineUpdateResponse(
                    _id=ObjectIdStr(str(doc["_id"])),
                    complaint_id=ObjectIdStr(str(doc["complaint_id"])),
                    organization_id=ObjectIdStr(str(doc["organization_id"])),
                    department_id=ObjectIdStr(str(doc["department_id"])),
                    updated_by=ObjectIdStr(str(doc["updated_by"])),
                    update_type=UpdateType(doc["update_type"]),
                    previous_status=doc.get("previous_status"),
                    new_status=doc.get("new_status"),
                    message=doc.get("message", ""),
                    images=[ObjectIdStr(str(img)) for img in doc.get("images", [])],
                    is_public=doc.get("is_public", True),
                    created_at=doc["created_at"],
                )
            )

        return ComplaintTimelineUpdateListResponse(
            success=True,
            message="Complaint updates retrieved successfully",
            data=items,
        )

    def _validate_assign_status(self, current_status: ComplaintStatus) -> ComplaintStatus:
        if ComplaintStateMachine.is_terminal(current_status):
            raise BusinessLogicException(
                f"Cannot assign complaint in terminal state '{current_status.value}'",
                error_code="INVALID_STATUS_TRANSITION",
            )
        if current_status in (ComplaintStatus.SUBMITTED, ComplaintStatus.ONGOING):
            return ComplaintStatus.ONGOING
        raise BusinessLogicException(
            f"Cannot assign complaint in status '{current_status.value}'. Assignment is only permitted for SUBMITTED or ONGOING complaints.",
            error_code="INVALID_STATUS_TRANSITION",
        )

    async def _record_assignment_timeline(
        self,
        complaint: dict[str, Any],
        actor_id: str,
        current_status: ComplaintStatus,
        new_status: ComplaintStatus,
        staff_name: str,
        action_verb: str,
        now: datetime,
    ) -> None:
        if self._complaint_update_repo is None:
            return
        try:
            dept_id = complaint.get("department_id")
            if not dept_id:
                raise ValueError(f"Complaint {complaint.get('_id')} missing department_id")

            timeline_doc: dict[str, Any] = {
                "complaint_id": ObjectId(str(complaint["_id"])),
                "organization_id": ObjectId(str(complaint["organization_id"])),
                "department_id": ObjectId(str(dept_id)),
                "updated_by": ObjectId(str(actor_id)),
                "update_type": UpdateType.ASSIGNMENT.value,
                "previous_status": current_status.value,
                "new_status": new_status.value,
                "message": f"Complaint {action_verb} to {staff_name}",
                "images": [],
                "is_public": True,
                "created_at": now,
            }
            await self._complaint_update_repo.create(timeline_doc)
        except Exception:
            pass

    async def assign(
        self,
        complaint_id: str,
        current_user: UserResponse,
        request: ComplaintAssignRequest,
    ) -> ComplaintAssignResponse:
        """Assign or reassign a complaint to an organization staff member."""
        actor_role = (
            current_user.role
            if isinstance(current_user.role, UserRole)
            else UserRole(str(current_user.role))
        )
        if actor_role not in (UserRole.ORGANIZATION_ADMIN, UserRole.ADMIN):
            raise ForbiddenException(
                "Only organization admins and platform admins can assign complaints",
                error_code="FORBIDDEN",
            )

        # 1. Fetch complaint with tenant scoping
        complaint = await self._get_complaint_for_status_change(complaint_id, current_user, actor_role)
        if complaint is None:
            raise NotFoundException("Complaint not found", error_code="COMPLAINT_NOT_FOUND")

        current_status = ComplaintStatus(complaint["status"])

        # 2. Status validation: initial assignment or reassignment
        new_status = self._validate_assign_status(current_status)

        # 3. Validate target staff user
        target_staff = await self._validate_target_staff(
            target_user_id=request.assigned_to,
            complaint=complaint,
        )

        now = datetime.now(UTC)
        org_id_scope = str(current_user.organization_id) if actor_role != UserRole.ADMIN else None

        # 4. Atomic assignment with optimistic concurrency on current_status
        success = await self._complaint_repo.assign_complaint(
            complaint_id=str(complaint["_id"]),
            expected_status=current_status.value,
            new_status=new_status.value,
            assigned_to=str(target_staff["_id"]),
            assigned_at=now,
            organization_id=org_id_scope,
        )
        if not success:
            raise ConflictException(
                "Complaint state changed concurrently. Please refresh and retry.",
                error_code="STATUS_CONFLICT",
            )

        staff_name = target_staff.get("full_name") or "staff member"
        action_verb = "assigned" if current_status == ComplaintStatus.SUBMITTED else "reassigned"

        # 5. Timeline update record (update_type="assignment")
        await self._record_assignment_timeline(
            complaint=complaint,
            actor_id=str(current_user.id),
            current_status=current_status,
            new_status=new_status,
            staff_name=staff_name,
            action_verb=action_verb,
            now=now,
        )

        # 6. Best-effort audit logging
        try:
            db = getattr(self._complaint_repo._collection, "database", None)
            if db is not None:
                await db["audit_logs"].insert_one({
                    "actor_id": str(current_user.id),
                    "actor_role": actor_role.value,
                    "action": "complaint.assigned",
                    "entity_type": "complaint",
                    "entity_id": str(complaint["_id"]),
                    "metadata": {
                        "complaint_number": complaint.get("complaint_number"),
                        "previous_status": current_status.value,
                        "new_status": new_status.value,
                        "previous_assigned_to": str(complaint.get("assigned_to")) if complaint.get("assigned_to") else None,
                        "assigned_to": str(target_staff["_id"]),
                        "assigned_to_name": staff_name,
                        "organization_id": str(complaint["organization_id"]),
                        "department_id": str(complaint.get("department_id")),
                    },
                    "created_at": now,
                })
        except Exception:
            pass

        # Trigger staff in-app notification (NOTIF-08)
        if self._notification_service is not None:
            try:
                from app.schemas.notification import NotificationType
                from app.services.notification_service import NotificationPayload

                cid = str(complaint["_id"])
                ctitle = complaint.get("title", "Complaint")
                payload = NotificationPayload(
                    user_id=str(target_staff["_id"]),
                    type=NotificationType.ASSIGNMENT,
                    title="New Complaint Assigned",
                    message=f"You have been assigned: '{ctitle}'",
                    complaint_id=cid,
                    metadata={
                        "complaint_number": complaint.get("complaint_number"),
                        "deep_link": f"app://complaint/{cid}",
                    },
                )
                await self._notification_service.create_notification(payload)
            except Exception:
                # Notification dispatch failure must never abort complaint assignment
                pass

        return ComplaintAssignResponse(
            success=True,
            message=f"Complaint assigned to {staff_name}",
            data=ComplaintAssignData(
                id=ObjectIdStr(str(complaint["_id"])),
                assigned_to={
                    "id": str(target_staff["_id"]),
                    "name": staff_name,
                },
                assigned_at=now,
                status=new_status,
            ),
        )

    async def _validate_target_staff(
        self,
        target_user_id: str,
        complaint: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate that target user exists, is organization staff, active, and matches tenant & department."""
        if self._user_repo is None:
            raise ValidationException("User repository not configured", error_code="SERVER_ERROR")

        target_user = await self._user_repo.find_by_id(target_user_id)
        if target_user is None:
            raise ValidationException("Target staff user not found", error_code="USER_NOT_FOUND")

        # Must have role organization_staff
        if target_user.get("role") != UserRole.ORGANIZATION_STAFF.value:
            raise ValidationException(
                "Target user is not an organization staff member",
                error_code="INVALID_ASSIGNEE_ROLE",
            )

        # Must be active
        if target_user.get("status") not in ("active", None):
            raise ValidationException(
                "Target staff user is not active",
                error_code="USER_INACTIVE",
            )

        # Must belong to the same organization as the complaint
        complaint_org = str(complaint.get("organization_id"))
        staff_org = str(target_user.get("organization_id")) if target_user.get("organization_id") else None
        if staff_org != complaint_org:
            raise ValidationException(
                "Target staff member belongs to a different organization",
                error_code="ORG_MISMATCH",
            )

        # Must belong to the same department as the complaint
        complaint_dept = str(complaint.get("department_id")) if complaint.get("department_id") else None
        staff_dept = str(target_user.get("department_id")) if target_user.get("department_id") else None
        if not complaint_dept or staff_dept != complaint_dept:
            raise ValidationException(
                "Target staff member does not belong to the complaint's department",
                error_code="DEPARTMENT_MISMATCH",
            )

        return target_user

    async def complete(
        self,
        complaint_id: str,
        current_user: UserResponse,
        request: ComplaintCompleteRequest,
    ) -> ComplaintCompleteResponse:
        """Complete a complaint (PROCESSING -> COMPLETED).

        Business Rules:
        - Only ORGANIZATION_STAFF (assigned to complaint), ORGANIZATION_ADMIN, or ADMIN can complete.
        - Citizens forbidden (403).
        - Tenant isolation enforced (404 for cross-tenant org admin / staff).
        - Status must be PROCESSING (422 INVALID_STATUS_TRANSITION for terminal or other statuses).
        - Reason/summary is required and non-empty.
        - Completion images (if provided) validated against target complaint, tenant, and type.
        - Concurrency: optimistic locking against concurrent status modification (409).
        - Creates timeline record with update_type='completion' and required department_id.
        - Emits best-effort audit event 'complaint.completed'.
        """
        actor_role = (
            current_user.role
            if isinstance(current_user.role, UserRole)
            else UserRole(str(current_user.role))
        )
        if actor_role == UserRole.CITIZEN:
            raise ForbiddenException("Citizens cannot complete complaints", error_code="FORBIDDEN")

        complaint = await self._get_complaint_for_status_change(complaint_id, current_user, actor_role)
        if complaint is None:
            raise NotFoundException("Complaint not found", error_code="COMPLAINT_NOT_FOUND")

        current_status = ComplaintStatus(complaint["status"])
        target_status = ComplaintStatus.COMPLETED

        if ComplaintStateMachine.is_terminal(current_status):
            raise BusinessLogicException(
                f"Cannot change status: complaint is in terminal state '{current_status.value}'",
                error_code="INVALID_STATUS_TRANSITION",
            )

        rule = ComplaintStateMachine.get_rule(current_status, target_status)
        if rule is None:
            raise BusinessLogicException(
                f"Invalid status transition from {current_status.value} to {target_status.value}",
                error_code="INVALID_STATUS_TRANSITION",
            )

        clean_reason = request.reason.strip()
        self._validate_status_transition(
            current_status=current_status,
            target_status=target_status,
            rule=rule,
            actor_role=actor_role,
            current_user=current_user,
            complaint=complaint,
            clean_reason=clean_reason,
        )

        # Validate completion images if provided
        image_ids: list[ObjectId] = []
        if request.completion_images and self._complaint_image_repo is not None:
            image_ids = await self._validate_completion_images(str(complaint["_id"]), request.completion_images)

        now = datetime.now(UTC)
        org_id_scope = str(current_user.organization_id) if actor_role != UserRole.ADMIN else None
        applied = await self._complaint_repo.complete_complaint(
            complaint_id=str(complaint["_id"]),
            completed_at=now,
            organization_id=org_id_scope,
        )
        if not applied:
            fresh = await self._complaint_repo.find_by_id(str(complaint["_id"]))
            if fresh is None:
                raise NotFoundException("Complaint not found", error_code="COMPLAINT_NOT_FOUND")
            raise ConflictException(
                f"Complaint status was concurrently modified from {current_status.value} to {fresh.get('status')}",
                error_code="STATUS_CONFLICT",
            )

        # Record timeline & audit
        await self._record_completion_timeline(complaint, current_user, clean_reason, image_ids, now)
        await self._record_completion_audit(complaint, current_user, actor_role, clean_reason, now)

        # Trigger citizen completion notification (NOTIF-08)
        if self._notification_service is not None:
            try:
                from app.schemas.notification import NotificationType
                from app.services.notification_service import NotificationPayload

                cid = str(complaint["_id"])
                ctitle = complaint.get("title", "Complaint")
                owner_id = str(complaint.get("user_id"))
                payload = NotificationPayload(
                    user_id=owner_id,
                    type=NotificationType.COMPLETION,
                    title="Complaint Resolved",
                    message=f"Your complaint '{ctitle}' has been completed",
                    complaint_id=cid,
                    metadata={
                        "complaint_number": complaint.get("complaint_number"),
                        "reason": clean_reason,
                        "deep_link": f"app://complaint/{cid}",
                    },
                )
                await self._notification_service.create_notification(payload)
            except Exception:
                # Notification dispatch failure must never abort completion
                pass

        return ComplaintCompleteResponse(
            success=True,
            message="Complaint completed successfully",
            data=ComplaintCompleteData(
                id=ObjectIdStr(str(complaint["_id"])),
                status=ComplaintStatus.COMPLETED,
                completed_at=now,
                updated_at=now,
            ),
        )

    async def _validate_completion_images(
        self, complaint_id: str, image_ids_str: list[ObjectIdStr]
    ) -> list[ObjectId]:
        if not image_ids_str or self._complaint_image_repo is None:
            return []
        validated: list[ObjectId] = []
        for img_id_str in image_ids_str:
            img_doc = await self._complaint_image_repo.find_by_id(
                image_id=str(img_id_str),
                complaint_id=str(complaint_id),
            )
            if img_doc is None:
                raise ValidationException(
                    f"Image {img_id_str} not found or does not belong to this complaint",
                    error_code="INVALID_IMAGE_REFERENCE",
                )
            img_type = img_doc.get("image_type")
            if img_type not in ("completion", "progress"):
                raise ValidationException(
                    f"Image {img_id_str} is of type '{img_type}'. Only 'completion' or 'progress' images may be attached.",
                    error_code="INVALID_IMAGE_TYPE",
                )
            validated.append(ObjectId(str(img_doc["_id"])))
        return validated

    async def _record_completion_timeline(
        self,
        complaint: dict[str, Any],
        current_user: UserResponse,
        clean_reason: str,
        image_ids: list[ObjectId],
        now: datetime,
    ) -> None:
        if self._complaint_update_repo is None:
            return
        try:
            dept_id = complaint.get("department_id")
            if not dept_id:
                raise ValueError(f"Complaint {complaint.get('_id')} missing department_id")
            timeline_doc = {
                "complaint_id": ObjectId(str(complaint["_id"])),
                "organization_id": ObjectId(str(complaint["organization_id"])),
                "department_id": ObjectId(str(dept_id)),
                "updated_by": ObjectId(str(current_user.id)),
                "update_type": UpdateType.COMPLETION.value,
                "previous_status": ComplaintStatus.PROCESSING.value,
                "new_status": ComplaintStatus.COMPLETED.value,
                "message": clean_reason,
                "images": image_ids,
                "is_public": True,
                "created_at": now,
            }
            await self._complaint_update_repo.create(timeline_doc)
        except Exception:
            pass

    async def _record_completion_audit(
        self,
        complaint: dict[str, Any],
        current_user: UserResponse,
        actor_role: UserRole,
        clean_reason: str,
        now: datetime,
    ) -> None:
        audit_doc = {
            "actor_id": str(current_user.id),
            "actor_role": actor_role.value,
            "action": "complaint.completed",
            "entity_type": "complaint",
            "entity_id": str(complaint["_id"]),
            "metadata": {
                "complaint_number": complaint.get("complaint_number"),
                "previous_status": ComplaintStatus.PROCESSING.value,
                "new_status": ComplaintStatus.COMPLETED.value,
                "reason": clean_reason,
                "organization_id": str(complaint["organization_id"]),
                "department_id": str(complaint.get("department_id")),
            },
            "created_at": now,
        }
        try:
            db = getattr(self._complaint_repo._collection, "database", None)
            if db is not None:
                await db["audit_logs"].insert_one(audit_doc)
        except Exception:
            pass

    async def _get_complaint_for_view(
        self, complaint_id: str, current_user: UserResponse
    ) -> dict[str, Any] | None:
        """Retrieve complaint matching the authorization rules in get_complaint_by_id."""
        if current_user.role == "admin":
            complaint = await self._complaint_repo.find_by_id_for_admin(complaint_id)
        elif current_user.role in ("organization_staff", "organization_admin"):
            if not current_user.organization_id:
                return None
            org_id = str(current_user.organization_id)
            if current_user.role == "organization_admin":
                complaint = await self._complaint_repo.find_by_id_in_organization(
                    complaint_id, org_id
                )
            else:
                if not current_user.department_id:
                    return None
                dept_id = str(current_user.department_id)
                complaint = await self._complaint_repo.find_by_id_for_organization_staff(
                    complaint_id, org_id, dept_id
                )
        else:
            complaint = await self._complaint_repo.find_by_id_for_user(
                complaint_id, str(current_user.id)
            )

        if not complaint or not self._can_view_complaint(complaint, current_user):
            return None
        return complaint

    async def get_priority(
        self,
        complaint_id: str,
        current_user: UserResponse,
    ) -> PriorityBreakdownData:
        """Retrieve priority breakdown for a complaint.

        Authorizes access using the standard complaint retrieval tenant isolation.
        """
        complaint = await self._get_complaint_for_view(complaint_id, current_user)
        if complaint is None:
            raise NotFoundException("Complaint not found", error_code="COMPLAINT_NOT_FOUND")

        service = self._priority_service or PriorityService()
        return await service.calculate_priority(complaint)

    async def like_complaint(
        self,
        complaint_id: str,
        current_user: UserResponse,
    ) -> ComplaintLikeData:
        """Like a complaint as an authenticated citizen (FEED-05, FEED-08).

        Rules:
        - Authenticated citizen only (enforced by RBAC at route)
        - Complaint must exist
        - Complaint must have visibility == 'public'
        - Complaint status must not be in ['REJECTED', 'DUPLICATE', 'CLOSED']
        - Uniqueness enforced at DB level via idx_likes_complaint_user
        - If already liked, raise ConflictException(DUPLICATE_LIKE)
        - Updates denormalized likes_count, priority_score, and community_engagement_score
        """
        complaint = await self._complaint_repo.find_by_id(complaint_id)
        if complaint is None:
            raise NotFoundException("Complaint not found", error_code="COMPLAINT_NOT_FOUND")

        if complaint.get("visibility") != "public":
            raise ForbiddenException(
                "Cannot like non-public complaint", error_code="FORBIDDEN"
            )

        if complaint.get("status") in ("REJECTED", "DUPLICATE", "CLOSED"):
            raise ValidationException(
                f"Cannot like complaint in {complaint.get('status')} status",
                error_code="INVALID_STATUS_TRANSITION",
            )

        if self._like_repo is None:
            raise BusinessLogicException("Like repository unavailable")

        inserted = await self._like_repo.add_like(complaint_id, str(current_user.id))
        if not inserted:
            raise ConflictException(
                "You have already liked this complaint",
                error_code="DUPLICATE_LIKE",
            )

        new_likes_count = await self._like_repo.count_by_complaint(complaint_id)

        # Recalculate priority
        complaint["likes_count"] = new_likes_count
        priority_service = self._priority_service or PriorityService()
        breakdown = await priority_service.calculate_priority(complaint)

        await self._complaint_repo.update_likes_count_and_priority(
            complaint_id=complaint_id,
            likes_count=new_likes_count,
            priority_score=breakdown.priority_score,
            community_engagement_score=int(round(breakdown.breakdown.community_engagement_score)),
        )

        return ComplaintLikeData(
            like_count=new_likes_count,
            user_liked=True,
        )

    async def unlike_complaint(
        self,
        complaint_id: str,
        current_user: UserResponse,
    ) -> ComplaintLikeData:
        """Unlike a complaint as an authenticated citizen (FEED-06).

        Rules:
        - Authenticated citizen only
        - Safe if like does not exist: returns current like_count, user_liked=False
        - Recalculates priority and updates denormalized fields
        """
        complaint = await self._complaint_repo.find_by_id(complaint_id)
        if complaint is None:
            raise NotFoundException("Complaint not found", error_code="COMPLAINT_NOT_FOUND")

        if self._like_repo is None:
            raise BusinessLogicException("Like repository unavailable")

        deleted = await self._like_repo.remove_like(complaint_id, str(current_user.id))
        new_likes_count = await self._like_repo.count_by_complaint(complaint_id)

        if deleted:
            complaint["likes_count"] = new_likes_count
            priority_service = self._priority_service or PriorityService()
            breakdown = await priority_service.calculate_priority(complaint)

            await self._complaint_repo.update_likes_count_and_priority(
                complaint_id=complaint_id,
                likes_count=new_likes_count,
                priority_score=breakdown.priority_score,
                community_engagement_score=int(round(breakdown.breakdown.community_engagement_score)),
            )

        return ComplaintLikeData(
            like_count=new_likes_count,
            user_liked=False,
        )

    async def get_like_status(
        self,
        complaint_id: str,
        current_user: UserResponse,
    ) -> ComplaintLikeData:
        """Get like status for current user on complaint (FEED-07)."""
        complaint = await self._complaint_repo.find_by_id(complaint_id)
        if complaint is None:
            raise NotFoundException("Complaint not found", error_code="COMPLAINT_NOT_FOUND")

        # Non-public complaints check
        if complaint.get("visibility") != "public":
            # If not public, must be visible to user
            if not self._can_view_complaint(complaint, current_user):
                raise NotFoundException("Complaint not found", error_code="COMPLAINT_NOT_FOUND")

        if self._like_repo is None:
            like_count = int(complaint.get("likes_count", 0))
            return ComplaintLikeData(like_count=like_count, user_liked=False)

        user_liked = await self._like_repo.is_liked(complaint_id, str(current_user.id))
        like_count = await self._like_repo.count_by_complaint(complaint_id)

        return ComplaintLikeData(
            like_count=like_count,
            user_liked=user_liked,
        )

    async def get_likes_summary(
        self,
        complaint_id: str,
        current_user: UserResponse | None = None,
    ) -> ComplaintLikeData:
        """Get likes count and optional user_liked for public inspection (GET /complaints/{id}/likes)."""
        complaint = await self._complaint_repo.find_by_id(complaint_id)
        if complaint is None:
            raise NotFoundException("Complaint not found", error_code="COMPLAINT_NOT_FOUND")

        if complaint.get("visibility") != "public":
            if current_user is None or not self._can_view_complaint(complaint, current_user):
                raise NotFoundException("Complaint not found", error_code="COMPLAINT_NOT_FOUND")

        if self._like_repo is None:
            like_count = int(complaint.get("likes_count", 0))
            return ComplaintLikeData(like_count=like_count, user_liked=False)

        like_count = await self._like_repo.count_by_complaint(complaint_id)
        user_liked = False
        if current_user is not None:
            user_liked = await self._like_repo.is_liked(complaint_id, str(current_user.id))

        return ComplaintLikeData(
            like_count=like_count,
            user_liked=user_liked,
        )

    @staticmethod
    def _validate_feed_parameters(
        sort: str,
        page: int,
        page_size: int,
        status: str | None,
        lat: float | None,
        lng: float | None,
        radius_km: float,
    ) -> None:
        allowed_sorts = {"recent", "popular", "priority", "nearby"}
        if sort not in allowed_sorts:
            raise ValidationException(
                f"Invalid sort option: {sort}. Must be one of: {', '.join(sorted(allowed_sorts))}",
                error_code="VALIDATION_ERROR",
            )
        if sort == "nearby":
            if lat is None or lng is None:
                raise ValidationException(
                    "lat and lng parameters are required for nearby sort",
                    error_code="VALIDATION_ERROR",
                )
            if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0) or radius_km <= 0:
                raise ValidationException(
                    "Coordinates or search radius invalid for nearby sort",
                    error_code="VALIDATION_ERROR",
                )
        if page < 1:
            raise ValidationException("page must be >= 1", error_code="VALIDATION_ERROR")
        if page_size < 1 or page_size > 50:
            raise ValidationException("page_size must be between 1 and 50", error_code="VALIDATION_ERROR")
        if status and status not in {s.value for s in ComplaintStatus}:
            raise ValidationException(
                f"Invalid status filter: {status}", error_code="VALIDATION_ERROR"
            )

    async     def _build_feed_item(
        self,
        doc: dict[str, Any],
        categories_map: dict[str, Any],
        departments_map: dict[str, Any],
        liked_cids: set[str],
        image_counts: dict[str, int],
    ) -> FeedItem:
        cid_str = str(doc["_id"])
        cat_doc = categories_map.get(str(doc.get("category_id")))
        dept_doc = departments_map.get(str(doc.get("department_id")))

        category_summary = None
        if cat_doc:
            category_summary = FeedCategorySummary(
                id=ObjectIdStr(str(cat_doc["_id"])),
                name=cat_doc["name"],
                icon=cat_doc.get("icon"),
                color=cat_doc.get("color"),
            )

        department_summary = None
        if dept_doc:
            department_summary = FeedDepartmentSummary(
                id=ObjectIdStr(str(dept_doc["_id"])),
                name=dept_doc["name"],
            )

        loc_data = doc.get("location") or {"type": "Point", "coordinates": [0.0, 0.0]}
        location = GeoJSONPoint(
            type=loc_data.get("type", "Point"),
            coordinates=loc_data.get("coordinates", [0.0, 0.0]),
        )

        image_count = image_counts.get(cid_str, 0)

        created_at = doc.get("created_at")
        if isinstance(created_at, datetime) and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        return FeedItem(
            id=ObjectIdStr(cid_str),
            title=doc.get("title", ""),
            status=ComplaintStatus(doc.get("status", "SUBMITTED")),
            priority_score=round(float(doc.get("priority_score", 0.0)), 1),
            like_count=int(doc.get("likes_count", 0)),
            user_liked=cid_str in liked_cids,
            category=category_summary,
            department=department_summary,
            location=location,
            address=doc.get("address"),
            distance_km=doc.get("distance_km"),
            created_at=created_at or datetime.now(UTC),
            image_count=image_count,
        )


    async def get_public_feed(
        self,
        page: int = 1,
        page_size: int = 20,
        sort: str = "recent",
        status: str | None = None,
        category_id: str | None = None,
        organization_id: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
        radius_km: float = 10.0,
        q: str | None = None,
        current_user: UserResponse | None = None,
    ) -> FeedData:
        """Retrieve paginated public feed (FEED-01 through FEED-04, FEED-09)."""
        self._validate_feed_parameters(
            sort=sort,
            page=page,
            page_size=page_size,
            status=status,
            lat=lat,
            lng=lng,
            radius_km=radius_km,
        )

        items_raw, total_items = await self._complaint_repo.query_public_feed(
            status=status,
            category_id=category_id,
            organization_id=organization_id,
            sort=sort,
            page=page,
            page_size=page_size,
            lat=lat,
            lng=lng,
            radius_km=radius_km,
            q=q,
        )

        total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 0
        has_next = page < total_pages
        has_prev = page > 1

        liked_cids: set[str] = set()
        if current_user is not None and self._like_repo is not None and items_raw:
            cids = [str(item["_id"]) for item in items_raw]
            liked_cids = await self._like_repo.list_user_liked_complaint_ids(
                str(current_user.id), cids
            )

        cat_ids = {str(item["category_id"]) for item in items_raw if item.get("category_id")}
        dept_ids = {str(item["department_id"]) for item in items_raw if item.get("department_id")}

        # Batch fetches (one query each) instead of a per-item lookup (N+1).
        categories_map: dict[str, Any] = {
            str(c["_id"]): c for c in await self._category_repo.find_by_ids(list(cat_ids))
        }
        departments_map: dict[str, Any] = {
            str(d["_id"]): d for d in await self._department_repo.find_by_ids(list(dept_ids))
        }

        # Batch image counts (one aggregate) instead of a per-item count (N+1).
        image_counts: dict[str, int] = {}
        if self._complaint_image_repo is not None and items_raw:
            image_counts = await self._complaint_image_repo.count_by_complaints(
                [str(item["_id"]) for item in items_raw]
            )

        feed_items = [
            await self._build_feed_item(doc, categories_map, departments_map, liked_cids, image_counts)
            for doc in items_raw
        ]

        return FeedData(
            items=feed_items,
            pagination=FeedPagination(
                page=page,
                page_size=page_size,
                total_items=total_items,
                total_pages=total_pages,
                has_next=has_next,
                has_prev=has_prev,
            ),
        )






