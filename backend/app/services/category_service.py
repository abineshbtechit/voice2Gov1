"""Category service (Phase 1.7).

Authoritative source: docs/database-schema.md §4; docs/api-contract.md; docs/traceability-matrix.md.
"""

from datetime import UTC, datetime
from typing import Any

from app.exceptions.base import (
    NotFoundException,
    ValidationException,
)
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.organization_repository import OrganizationRepository
from app.schemas.category import (
    CategoryCreateRequest,
    CategoryResponse,
    CategoryStatus,
    CategoryUpdateRequest,
)
from app.schemas.user import UserResponse


class CategoryService:
    """Service managing categories for complaint classification and routing."""

    def __init__(
        self,
        category_repo: CategoryRepository,
        dept_repo: DepartmentRepository,
        org_repo: OrganizationRepository,
        audit_repo: AuditLogRepository | None = None,
    ) -> None:
        self._category_repo = category_repo
        self._dept_repo = dept_repo
        self._org_repo = org_repo
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

    async def list_active_categories(
        self, organization_id: str | None = None
    ) -> list[CategoryResponse]:
        """List active categories (public/all users)."""
        docs = await self._category_repo.list_active(organization_id=organization_id)
        return [
            CategoryResponse(
                id=str(d["_id"]),
                organization_id=str(d["organization_id"]) if d.get("organization_id") else None,
                name=d["name"],
                description=d.get("description"),
                icon=d.get("icon"),
                color=d.get("color"),
                severity_level=d.get("severity_level", 1),
                priority_weight=d.get("priority_weight", 1.0),
                default_department_id=str(d["default_department_id"]) if d.get("default_department_id") else None,
                status=d.get("status", CategoryStatus.ACTIVE),
                sort_order=d.get("sort_order", 0),
            )
            for d in docs
        ]

    async def create_category(
        self, request: CategoryCreateRequest, current_user: UserResponse
    ) -> CategoryResponse:
        """Create category (Admin only)."""
        org_id = str(request.organization_id)
        org = await self._org_repo.find_by_id(org_id)
        if not org:
            raise NotFoundException("Organization not found")

        # Validate default_department_id belongs to same org and is active
        dept_id = str(request.default_department_id)
        dept = await self._dept_repo.find_by_id_active_in_org(dept_id, org_id)
        if not dept:
            raise ValidationException(
                "Default department does not exist, is inactive, or belongs to a different organization"
            )

        now = datetime.now(UTC)
        cat_data: dict[str, Any] = {
            "organization_id": org_id,
            "name": request.name,
            "description": request.description,
            "icon": request.icon,
            "color": request.color,
            "default_department_id": dept_id,
            "severity_level": request.severity_level,
            "priority_weight": request.priority_weight,
            "status": request.status.value,
            "sort_order": request.sort_order,
            "created_at": now,
            "updated_at": now,
        }

        category_id = await self._category_repo.create(cat_data)

        await self._audit(
            actor=current_user,
            action="category.create",
            entity_type="category",
            entity_id=category_id,
            metadata={"organization_id": org_id, "name": request.name},
        )

        return CategoryResponse(
            id=category_id,
            organization_id=org_id,
            name=cat_data["name"],
            description=cat_data.get("description"),
            icon=cat_data.get("icon"),
            color=cat_data.get("color"),
            severity_level=cat_data["severity_level"],
            priority_weight=cat_data["priority_weight"],
            default_department_id=dept_id,
            status=CategoryStatus(cat_data["status"]),
            sort_order=cat_data["sort_order"],
        )

    async def update_category(
        self, category_id: str, request: CategoryUpdateRequest, current_user: UserResponse
    ) -> CategoryResponse:
        """Update category (Admin only)."""
        existing = await self._category_repo.find_by_id(category_id)
        if not existing:
            raise NotFoundException("Category not found")

        org_id = str(existing.get("organization_id")) if existing.get("organization_id") else None

        # If default_department_id is changed, validate it
        if request.default_department_id is not None:
            dept_id = str(request.default_department_id)
            if org_id:
                dept = await self._dept_repo.find_by_id_active_in_org(dept_id, org_id)
            else:
                dept = await self._dept_repo.find_by_id(dept_id)
            if not dept:
                raise ValidationException(
                    "Default department does not exist, is inactive, or belongs to a different organization"
                )

        update_dict = request.model_dump(exclude_unset=True)
        if "status" in update_dict and update_dict["status"] is not None:
            update_dict["status"] = (
                update_dict["status"].value
                if hasattr(update_dict["status"], "value")
                else str(update_dict["status"])
            )

        if update_dict:
            await self._category_repo.update(category_id, update_dict)

        updated_doc = await self._category_repo.find_by_id(category_id)
        assert updated_doc is not None

        await self._audit(
            actor=current_user,
            action="category.update",
            entity_type="category",
            entity_id=category_id,
            metadata={"updated_fields": list(update_dict.keys())},
        )

        return CategoryResponse(
            id=str(updated_doc["_id"]),
            organization_id=str(updated_doc.get("organization_id")),
            name=updated_doc["name"],
            description=updated_doc.get("description"),
            icon=updated_doc.get("icon"),
            color=updated_doc.get("color"),
            severity_level=updated_doc.get("severity_level", 1),
            priority_weight=updated_doc.get("priority_weight", 1.0),
            default_department_id=str(updated_doc.get("default_department_id"))
            if updated_doc.get("default_department_id")
            else None,
            status=CategoryStatus(updated_doc.get("status", "active")),
            sort_order=updated_doc.get("sort_order", 0),
        )

    async def delete_category(
        self, category_id: str, current_user: UserResponse
    ) -> bool:
        """Soft-delete category by setting status to inactive (Admin only)."""
        existing = await self._category_repo.find_by_id(category_id)
        if not existing:
            raise NotFoundException("Category not found")

        await self._category_repo.soft_delete(category_id)

        await self._audit(
            actor=current_user,
            action="category.delete",
            entity_type="category",
            entity_id=category_id,
            metadata={"name": existing.get("name")},
        )
        return True
