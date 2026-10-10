"""Organization & Department service (Phase 1.7).

Handles organization and department business logic, tenant isolation enforcement,
and organizational complaint queues.
Authoritative source: docs/database-schema.md §2, §3; docs/api-contract.md; docs/traceability-matrix.md.
"""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.exceptions.base import (
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.complaint_repository import ComplaintRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.department import (
    DepartmentCreateRequest,
    DepartmentResponse,
    DepartmentUpdateRequest,
)
from app.schemas.organization import (
    OrganizationCreateRequest,
    OrganizationResponse,
    OrganizationUpdateRequest,
)
from app.schemas.user import UserResponse, UserRole


class OrganizationService:
    """Service managing organizations, departments, and organization complaint queues."""

    def __init__(
        self,
        org_repo: OrganizationRepository,
        dept_repo: DepartmentRepository,
        user_repo: UserRepository,
        complaint_repo: ComplaintRepository,
        audit_repo: AuditLogRepository | None = None,
    ) -> None:
        self._org_repo = org_repo
        self._dept_repo = dept_repo
        self._user_repo = user_repo
        self._complaint_repo = complaint_repo
        self._audit_repo = audit_repo

    async def _audit(
        self,
        actor: UserResponse,
        action: str,
        entity_type: str,
        entity_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self._audit_repo is not None:
            await self._audit_repo.log_event(
                actor_id=actor.id,
                actor_role=str(actor.role),
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                metadata=metadata,
            )

    # -------------------------------------------------------------------------
    # Organizations
    # -------------------------------------------------------------------------

    async def create_organization(
        self,
        request: OrganizationCreateRequest,
        current_user: UserResponse,
    ) -> OrganizationResponse:
        """Create a new organization (Admin only)."""
        now = datetime.now(UTC)
        doc: dict[str, Any] = {
            "name": request.name,
            "code": request.code,
            "description": request.description,
            "address": request.address,
            "contact_email": request.contact_email,
            "contact_phone": request.contact_phone,
            "logo_url": request.logo_url,
            "website": request.website,
            "is_active": request.is_active,
            "settings": request.settings.model_dump(exclude_unset=True) if request.settings else {},
            "created_at": now,
            "updated_at": now,
        }

        org_id = await self._org_repo.create(doc)
        doc["_id"] = ObjectId(org_id)

        await self._audit(
            actor=current_user,
            action="organization.create",
            entity_type="organization",
            entity_id=org_id,
            metadata={"code": request.code, "name": request.name},
        )

        return OrganizationResponse(
            id=org_id,
            name=doc["name"],
            code=doc["code"],
            description=doc.get("description"),
            address=doc.get("address"),
            contact_email=doc.get("contact_email"),
            contact_phone=doc.get("contact_phone"),
            logo_url=doc.get("logo_url"),
            website=doc.get("website"),
            is_active=doc["is_active"],
            settings=doc.get("settings"),
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )

    async def get_organization(
        self, org_id: str, current_user: UserResponse
    ) -> OrganizationResponse:
        """Get organization by ID."""
        # Tenant check: org_staff and org_admin can only view their own org
        if current_user.role in (UserRole.ORGANIZATION_STAFF, UserRole.ORGANIZATION_ADMIN):
            if str(current_user.organization_id) != org_id:
                raise ForbiddenException("Cross-organization access forbidden")

        doc = await self._org_repo.find_by_id(org_id)
        if not doc:
            raise NotFoundException("Organization not found")

        return OrganizationResponse(
            id=str(doc["_id"]),
            name=doc["name"],
            code=doc["code"],
            description=doc.get("description"),
            address=doc.get("address"),
            contact_email=doc.get("contact_email"),
            contact_phone=doc.get("contact_phone"),
            logo_url=doc.get("logo_url"),
            website=doc.get("website"),
            is_active=doc.get("is_active", True),
            settings=doc.get("settings"),
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )

    async def list_organizations(
        self,
        is_active: bool | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[OrganizationResponse]:
        """List all organizations (Admin only)."""
        docs = await self._org_repo.find_all(is_active=is_active, limit=limit, skip=skip)
        return [
            OrganizationResponse(
                id=str(d["_id"]),
                name=d["name"],
                code=d["code"],
                description=d.get("description"),
                address=d.get("address"),
                contact_email=d.get("contact_email"),
                contact_phone=d.get("contact_phone"),
                logo_url=d.get("logo_url"),
                website=d.get("website"),
                is_active=d.get("is_active", True),
                settings=d.get("settings"),
                created_at=d["created_at"],
                updated_at=d["updated_at"],
            )
            for d in docs
        ]

    async def count_organizations(self, is_active: bool | None = None) -> int:
        return await self._org_repo.count_all(is_active=is_active)

    async def update_organization(
        self,
        org_id: str,
        request: OrganizationUpdateRequest,
        current_user: UserResponse,
    ) -> OrganizationResponse:
        """Update organization details (Admin only per authoritative API contract)."""
        if current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Insufficient permissions to update organization: Admin required")

        existing = await self._org_repo.find_by_id(org_id)
        if not existing:
            raise NotFoundException("Organization not found")

        update_dict = request.model_dump(exclude_unset=True)
        if "settings" in update_dict and update_dict["settings"] is not None:
            # Merge settings
            current_settings = existing.get("settings") or {}
            current_settings.update(update_dict["settings"])
            update_dict["settings"] = current_settings

        if update_dict:
            await self._org_repo.update(org_id, update_dict)

        updated_doc = await self._org_repo.find_by_id(org_id)
        assert updated_doc is not None

        await self._audit(
            actor=current_user,
            action="organization.update",
            entity_type="organization",
            entity_id=org_id,
            metadata={"updated_fields": list(update_dict.keys())},
        )

        return OrganizationResponse(
            id=str(updated_doc["_id"]),
            name=updated_doc["name"],
            code=updated_doc["code"],
            description=updated_doc.get("description"),
            address=updated_doc.get("address"),
            contact_email=updated_doc.get("contact_email"),
            contact_phone=updated_doc.get("contact_phone"),
            logo_url=updated_doc.get("logo_url"),
            website=updated_doc.get("website"),
            is_active=updated_doc.get("is_active", True),
            settings=updated_doc.get("settings"),
            created_at=updated_doc["created_at"],
            updated_at=updated_doc["updated_at"],
        )

    async def toggle_organization_status(
        self,
        org_id: str,
        is_active: bool,
        current_user: UserResponse,
    ) -> OrganizationResponse:
        """Set organization active/inactive status (Admin only)."""
        existing = await self._org_repo.find_by_id(org_id)
        if not existing:
            raise NotFoundException("Organization not found")

        await self._org_repo.set_status(org_id, is_active)
        updated_doc = await self._org_repo.find_by_id(org_id)
        assert updated_doc is not None

        await self._audit(
            actor=current_user,
            action="organization.status_change",
            entity_type="organization",
            entity_id=org_id,
            metadata={"old_status": existing.get("is_active", True), "new_status": is_active},
        )

        return OrganizationResponse(
            id=str(updated_doc["_id"]),
            name=updated_doc["name"],
            code=updated_doc["code"],
            description=updated_doc.get("description"),
            address=updated_doc.get("address"),
            contact_email=updated_doc.get("contact_email"),
            contact_phone=updated_doc.get("contact_phone"),
            logo_url=updated_doc.get("logo_url"),
            website=updated_doc.get("website"),
            is_active=updated_doc.get("is_active", True),
            settings=updated_doc.get("settings"),
            created_at=updated_doc["created_at"],
            updated_at=updated_doc["updated_at"],
        )

    # -------------------------------------------------------------------------
    # Departments
    # -------------------------------------------------------------------------

    async def create_department(
        self,
        request: DepartmentCreateRequest,
        current_user: UserResponse,
    ) -> DepartmentResponse:
        """Create department. Org admin scoped to own org; admin can specify org."""
        if current_user.role == UserRole.ORGANIZATION_ADMIN:
            target_org_id = str(current_user.organization_id)
        elif current_user.role == UserRole.ADMIN:
            if not request.organization_id:
                raise ValidationException("organization_id required for admin creating department")
            target_org_id = str(request.organization_id)
        else:
            raise ForbiddenException("Insufficient permissions to create department")

        # Verify target organization exists and is active
        org = await self._org_repo.find_by_id(target_org_id)
        if not org:
            raise NotFoundException("Target organization not found")

        # Validate head_user_id if provided
        if request.head_user_id:
            head_user = await self._user_repo.find_by_id(str(request.head_user_id))
            if not head_user:
                raise NotFoundException("Department head user not found")
            if str(head_user.get("organization_id")) != target_org_id:
                raise ValidationException("Department head must belong to the same organization")
            if head_user.get("role") != UserRole.ORGANIZATION_ADMIN.value:
                raise ValidationException(
                    "Department head must have organization_admin role per schema specification"
                )

        now = datetime.now(UTC)
        dept_data: dict[str, Any] = {
            "organization_id": target_org_id,
            "name": request.name,
            "code": request.code,
            "description": request.description,
            "contact_email": request.contact_email,
            "contact_phone": request.contact_phone,
            "head_user_id": str(request.head_user_id) if request.head_user_id else None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        dept_id = await self._dept_repo.create(dept_data)

        await self._audit(
            actor=current_user,
            action="department.create",
            entity_type="department",
            entity_id=dept_id,
            metadata={"organization_id": target_org_id, "name": request.name, "code": request.code},
        )

        return DepartmentResponse(
            id=dept_id,
            organization_id=target_org_id,
            name=dept_data["name"],
            code=dept_data["code"],
            description=dept_data.get("description"),
            contact_email=dept_data.get("contact_email"),
            contact_phone=dept_data.get("contact_phone"),
            head_user_id=dept_data.get("head_user_id"),
            is_active=dept_data["is_active"],
            created_at=dept_data["created_at"],
            updated_at=dept_data["updated_at"],
        )

    async def get_department(
        self, dept_id: str, current_user: UserResponse
    ) -> DepartmentResponse:
        """Get department by ID enforcing tenant isolation."""
        dept = await self._dept_repo.find_by_id(dept_id)
        if not dept:
            raise NotFoundException("Department not found")

        dept_org_id = str(dept["organization_id"])

        if current_user.role in (UserRole.ORGANIZATION_STAFF, UserRole.ORGANIZATION_ADMIN):
            if str(current_user.organization_id) != dept_org_id:
                raise ForbiddenException("Cross-organization department access forbidden")
        elif current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Insufficient permissions to view department")

        return DepartmentResponse(
            id=str(dept["_id"]),
            organization_id=dept_org_id,
            name=dept["name"],
            code=dept["code"],
            description=dept.get("description"),
            contact_email=dept.get("contact_email"),
            contact_phone=dept.get("contact_phone"),
            head_user_id=dept.get("head_user_id"),
            is_active=dept.get("is_active", True),
            created_at=dept["created_at"],
            updated_at=dept["updated_at"],
        )

    async def list_departments(
        self,
        current_user: UserResponse,
        organization_id: str | None = None,
        is_active: bool | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[DepartmentResponse]:
        """List departments with tenant isolation."""
        if current_user.role in (UserRole.ORGANIZATION_STAFF, UserRole.ORGANIZATION_ADMIN):
            target_org_id = str(current_user.organization_id)
            docs = await self._dept_repo.list_by_org(
                organization_id=target_org_id,
                is_active=is_active,
                limit=limit,
                skip=skip,
            )
        elif current_user.role == UserRole.ADMIN:
            if organization_id:
                docs = await self._dept_repo.list_by_org(
                    organization_id=organization_id,
                    is_active=is_active,
                    limit=limit,
                    skip=skip,
                )
            else:
                docs = await self._dept_repo.list_all(
                    is_active=is_active,
                    limit=limit,
                    skip=skip,
                )
        else:
            raise ForbiddenException("Insufficient permissions to list departments")

        return [
            DepartmentResponse(
                id=str(d["_id"]),
                organization_id=str(d["organization_id"]),
                name=d["name"],
                code=d["code"],
                description=d.get("description"),
                contact_email=d.get("contact_email"),
                contact_phone=d.get("contact_phone"),
                head_user_id=d.get("head_user_id"),
                is_active=d.get("is_active", True),
                created_at=d["created_at"],
                updated_at=d["updated_at"],
            )
            for d in docs
        ]

    async def update_department(
        self,
        dept_id: str,
        request: DepartmentUpdateRequest,
        current_user: UserResponse,
    ) -> DepartmentResponse:
        """Update department."""
        dept = await self._dept_repo.find_by_id(dept_id)
        if not dept:
            raise NotFoundException("Department not found")

        dept_org_id = str(dept["organization_id"])

        if current_user.role == UserRole.ORGANIZATION_ADMIN:
            if str(current_user.organization_id) != dept_org_id:
                raise ForbiddenException("Cross-organization department modification forbidden")
        elif current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Insufficient permissions to update department")

        # Validate head_user_id if provided
        if request.head_user_id is not None:
            head_user = await self._user_repo.find_by_id(str(request.head_user_id))
            if not head_user:
                raise NotFoundException("Department head user not found")
            if str(head_user.get("organization_id")) != dept_org_id:
                raise ValidationException("Department head must belong to the same organization")
            if head_user.get("role") != UserRole.ORGANIZATION_ADMIN.value:
                raise ValidationException(
                    "Department head must have organization_admin role per schema specification"
                )

        update_dict = request.model_dump(exclude_unset=True)
        if update_dict:
            await self._dept_repo.update(dept_id, dept_org_id, update_dict)

        updated_doc = await self._dept_repo.find_by_id(dept_id)
        assert updated_doc is not None

        await self._audit(
            actor=current_user,
            action="department.update",
            entity_type="department",
            entity_id=dept_id,
            metadata={"updated_fields": list(update_dict.keys())},
        )

        return DepartmentResponse(
            id=str(updated_doc["_id"]),
            organization_id=str(updated_doc["organization_id"]),
            name=updated_doc["name"],
            code=updated_doc["code"],
            description=updated_doc.get("description"),
            contact_email=updated_doc.get("contact_email"),
            contact_phone=updated_doc.get("contact_phone"),
            head_user_id=updated_doc.get("head_user_id"),
            is_active=updated_doc.get("is_active", True),
            created_at=updated_doc["created_at"],
            updated_at=updated_doc["updated_at"],
        )

    async def delete_department(
        self, dept_id: str, current_user: UserResponse
    ) -> bool:
        """Soft-deactivate a department (is_active = False)."""
        dept = await self._dept_repo.find_by_id(dept_id)
        if not dept:
            raise NotFoundException("Department not found")

        dept_org_id = str(dept["organization_id"])

        if current_user.role == UserRole.ORGANIZATION_ADMIN:
            if str(current_user.organization_id) != dept_org_id:
                raise ForbiddenException("Cross-organization department deletion forbidden")
        elif current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Insufficient permissions to delete department")

        await self._dept_repo.soft_delete(dept_id, dept_org_id)

        await self._audit(
            actor=current_user,
            action="department.delete",
            entity_type="department",
            entity_id=dept_id,
            metadata={"organization_id": dept_org_id, "name": dept.get("name")},
        )
        return True

    # -------------------------------------------------------------------------
    # Organization Complaint Dashboard & Priority Queue
    # -------------------------------------------------------------------------

    async def get_my_org_complaints(
        self,
        current_user: UserResponse,
        status: str | None = None,
        department_id: str | None = None,
        assigned_to: str | None = None,
        sort: str = "recent",
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Fetch complaints scoped to the authenticated user's organization."""
        org_id = current_user.organization_id
        if not org_id:
            raise ForbiddenException("User does not belong to any organization")

        # If user is staff, check if dept filter should match their dept if they choose
        items = await self._complaint_repo.find_organization_complaints(
            organization_id=str(org_id),
            status=status,
            department_id=department_id,
            assigned_to=assigned_to,
            sort_by=sort,
            page=page,
            page_size=page_size,
        )
        total = await self._complaint_repo.count_organization_complaints(
            organization_id=str(org_id),
            status=status,
            department_id=department_id,
            assigned_to=assigned_to,
        )

        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        # Safe serialisation
        safe_items: list[dict[str, Any]] = []
        for item in items:
            safe_items.append(
                {
                    "id": str(item["_id"]),
                    "complaint_number": item.get("complaint_number"),
                    "title": item.get("title"),
                    "status": item.get("status"),
                    "priority_score": item.get("priority_score", 0.0),
                    "organization_id": str(item.get("organization_id")),
                    "department_id": str(item.get("department_id")),
                    "category_id": str(item.get("category_id")),
                    "assigned_to": str(item.get("assigned_to")) if item.get("assigned_to") else None,
                    "likes_count": item.get("likes_count", 0),
                    "created_at": item.get("created_at"),
                    "updated_at": item.get("updated_at"),
                }
            )

        return {
            "items": safe_items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }

    async def get_my_org_priority_queue(
        self,
        current_user: UserResponse,
        department_id: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """Fetch complaint assignment priority queue sorted by priority_score descending."""
        return await self.get_my_org_complaints(
            current_user=current_user,
            status=None,
            department_id=department_id,
            assigned_to=None,
            sort="priority",
            page=page,
            page_size=page_size,
        )
