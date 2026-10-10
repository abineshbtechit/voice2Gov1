"""Admin service (Phase 1.7).

Authoritative source: docs/database-schema.md §11, §12; docs/api-contract.md; docs/traceability-matrix.md.
Implements:
- Admin dashboard summary statistics via aggregation
- User management (list, get, suspend, activate) with last-admin guard
- Audit log query
- System settings management with priority weight validation & PriorityService cache invalidation
"""

from typing import Any

from app.exceptions.base import (
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.repositories.admin_settings_repository import AdminSettingsRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.complaint_repository import ComplaintRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.admin import (
    AdminDashboardData,
    AdminUserListItem,
    AuditLogItem,
    SettingItem,
    SettingUpdateRequest,
)
from app.schemas.user import UserResponse, UserRole, UserStatus
from app.services.priority_service import PriorityService


class AdminService:
    """Service managing admin dashboard analytics, user status, settings, and audit logs."""

    # Strict key namespaces for updatable system settings: `general.*` and
    # `priority.*` (the priority-engine configuration, docs/priority-engine.md).
    # Keys outside these namespaces are rejected so an authenticated admin can
    # never inject arbitrary configuration (e.g. credential/secret keys) into
    # the settings store. Priority weight keys are additionally restricted to
    # the four canonical weights in update_setting.
    ALLOWED_SETTING_PREFIXES: tuple[str, ...] = ("general.", "priority.")

    def __init__(
        self,
        user_repo: UserRepository,
        org_repo: OrganizationRepository,
        dept_repo: DepartmentRepository,
        complaint_repo: ComplaintRepository,
        settings_repo: AdminSettingsRepository,
        audit_repo: AuditLogRepository,
        priority_service: PriorityService | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._org_repo = org_repo
        self._dept_repo = dept_repo
        self._complaint_repo = complaint_repo
        self._settings_repo = settings_repo
        self._audit_repo = audit_repo
        self._priority_service = priority_service

    async def _audit(
        self,
        actor: UserResponse,
        action: str,
        entity_type: str,
        entity_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self._audit_repo.log_event(
            actor_id=actor.id,
            actor_role=str(actor.role),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata,
        )

    # -------------------------------------------------------------------------
    # Dashboard Statistics
    # -------------------------------------------------------------------------

    async def get_dashboard_stats(self) -> AdminDashboardData:
        """Calculate system-wide statistics for the admin dashboard."""
        if (
            self._user_repo is None
            or self._org_repo is None
            or self._dept_repo is None
            or self._complaint_repo is None
        ):
            return AdminDashboardData()

        total_users = await self._user_repo.count_all()
        total_orgs = await self._org_repo.count_all()
        total_depts = await self._dept_repo.count_all()
        total_complaints = await self._complaint_repo.count_all()

        complaints_by_status, avg_resolution_hours, sla_compliance_rate = (
            await self._complaint_repo.get_dashboard_aggregates()
        )

        return AdminDashboardData(
            total_users=total_users,
            total_organizations=total_orgs,
            total_departments=total_depts,
            total_complaints=total_complaints,
            complaints_by_status=complaints_by_status,
            avg_resolution_hours=avg_resolution_hours,
            sla_compliance_rate=sla_compliance_rate,
        )

    # -------------------------------------------------------------------------
    # User Management
    # -------------------------------------------------------------------------

    async def list_users(
        self,
        role: UserRole | None = None,
        status: UserStatus | None = None,
        search: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[AdminUserListItem]:
        """List platform users with optional filters (Admin only)."""
        role_str = (
            role.value if hasattr(role, "value") else str(role)
        ) if role is not None else None
        status_str = (
            status.value if hasattr(status, "value") else str(status)
        ) if status is not None else None

        docs = await self._user_repo.find_users(
            role=role_str,
            status=status_str,
            search=search,
            limit=limit,
            skip=skip,
        )

        return [
            AdminUserListItem(
                id=str(d["_id"]),
                email=d["email"],
                phone=d["phone"],
                full_name=d["full_name"],
                role=UserRole(d["role"]),
                status=UserStatus(d.get("status", UserStatus.ACTIVE.value)),
                organization_id=str(d["organization_id"]) if d.get("organization_id") else None,
                department_id=str(d["department_id"]) if d.get("department_id") else None,
                is_verified=d.get("is_verified", False),
                created_at=d["created_at"],
                updated_at=d["updated_at"],
            )
            for d in docs
        ]

    async def count_users(
        self,
        role: UserRole | None = None,
        status: UserStatus | None = None,
        search: str | None = None,
    ) -> int:
        """Count users matching filters."""
        role_str = (
            role.value if hasattr(role, "value") else str(role)
        ) if role is not None else None
        status_str = (
            status.value if hasattr(status, "value") else str(status)
        ) if status is not None else None
        return await self._user_repo.count_users(role=role_str, status=status_str, search=search)

    async def get_user_detail(self, user_id: str) -> AdminUserListItem:
        """Get safe user details (Admin only)."""
        doc = await self._user_repo.find_by_id(user_id)
        if not doc:
            raise NotFoundException("User not found")

        return AdminUserListItem(
            id=str(doc["_id"]),
            email=doc["email"],
            phone=doc["phone"],
            full_name=doc["full_name"],
            role=UserRole(doc["role"]),
            status=UserStatus(doc.get("status", UserStatus.ACTIVE.value)),
            organization_id=str(doc["organization_id"]) if doc.get("organization_id") else None,
            department_id=str(doc["department_id"]) if doc.get("department_id") else None,
            is_verified=doc.get("is_verified", False),
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )

    async def suspend_user(
        self, user_id: str, reason: str | None, current_user: UserResponse
    ) -> AdminUserListItem:
        """Suspend a user account with self-suspension and last-admin protection."""
        target = await self._user_repo.find_by_id(user_id)
        if not target:
            raise NotFoundException("User not found")

        # Admin self-suspension guard
        if str(target["_id"]) == current_user.id:
            raise ForbiddenException("Administrators cannot suspend their own account")

        # Last active admin protection
        if target.get("role") == UserRole.ADMIN.value:
            admin_count = await self._user_repo.count_users(
                role=UserRole.ADMIN.value, status=UserStatus.ACTIVE.value
            )
            if admin_count <= 1:
                raise ForbiddenException("Cannot suspend the last active administrator on the platform")

        await self._user_repo.update(
            user_id,
            {"status": UserStatus.SUSPENDED.value, "is_active": False},
        )

        await self._audit(
            actor=current_user,
            action="user.suspend",
            entity_type="user",
            entity_id=user_id,
            metadata={"reason": reason, "previous_status": target.get("status")},
        )

        return await self.get_user_detail(user_id)

    async def activate_user(
        self, user_id: str, current_user: UserResponse
    ) -> AdminUserListItem:
        """Activate a suspended or inactive user."""
        target = await self._user_repo.find_by_id(user_id)
        if not target:
            raise NotFoundException("User not found")

        await self._user_repo.update(
            user_id,
            {"status": UserStatus.ACTIVE.value, "is_active": True},
        )

        await self._audit(
            actor=current_user,
            action="user.activate",
            entity_type="user",
            entity_id=user_id,
            metadata={"previous_status": target.get("status")},
        )

        return await self.get_user_detail(user_id)

    # -------------------------------------------------------------------------
    # Audit Logs
    # -------------------------------------------------------------------------

    async def get_audit_logs(
        self,
        actor_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        action: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[AuditLogItem]:
        """Query immutable audit log history (Admin only)."""
        logs = await self._audit_repo.find_logs(
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            limit=limit,
            skip=skip,
        )
        return [
            AuditLogItem(
                id=str(log["_id"]),
                actor_id=str(log["actor_id"]),
                actor_role=log["actor_role"],
                action=log["action"],
                entity_type=log["entity_type"],
                entity_id=str(log["entity_id"]),
                metadata=log.get("metadata"),
                ip_address=log.get("ip_address"),
                user_agent=log.get("user_agent"),
                created_at=log["created_at"],
            )
            for log in logs
        ]

    async def count_audit_logs(
        self,
        actor_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        action: str | None = None,
    ) -> int:
        return await self._audit_repo.count_logs(
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
        )

    # -------------------------------------------------------------------------
    # System Settings
    # -------------------------------------------------------------------------

    async def get_all_settings(self) -> list[SettingItem]:
        """Retrieve all system settings (Admin only). Excludes sensitive tokens/secrets."""
        docs = await self._settings_repo.list_all_settings()
        items: list[SettingItem] = []
        for doc in docs:
            key = doc.get("key", "")
            val = doc.get("value")
            # Mask any credentials/secret keys if any exist
            if any(secret_term in key.lower() for secret_term in ("secret", "password", "token", "private_key")):
                val = "******"
            items.append(
                SettingItem(
                    key=key,
                    value=val,
                    category=doc.get("category", "general"),
                    description=doc.get("description"),
                    is_public=doc.get("is_public", False),
                    created_at=doc.get("created_at"),
                    updated_at=doc.get("updated_at"),
                )
            )
        return items

    async def update_setting(
        self,
        key: str,
        request: SettingUpdateRequest,
        current_user: UserResponse,
    ) -> SettingItem:
        """Update system setting. Validates priority weight rules and invalidates priority cache."""
        # Strict key validation first: no arbitrary configuration injection.
        # Only the documented `general.*` / `priority.*` namespaces are updatable.
        if not key.startswith(self.ALLOWED_SETTING_PREFIXES):
            raise ValidationException(
                f"Unknown setting key '{key}'. Settings must live under one of: "
                f"{', '.join(self.ALLOWED_SETTING_PREFIXES)}",
                error_code="INVALID_SETTING_KEY",
            )

        existing = await self._settings_repo.get_setting_doc(key)
        default_category = "priority" if key.startswith("priority.") else "general"
        if request.category:
            category = (
                request.category.value
                if hasattr(request.category, "value")
                else str(request.category)
            )
        else:
            category = existing.get("category", default_category) if existing else default_category

        # Validate priority weight constraints if updating a priority weight
        if key.startswith("priority.weights."):
            canonical_weight_keys = {
                "priority.weights.community_engagement",
                "priority.weights.severity",
                "priority.weights.age",
                "priority.weights.organization_boost",
            }
            if key not in canonical_weight_keys:
                raise ValidationException(
                    f"Invalid priority weight setting key '{key}'. Must be one of: {sorted(canonical_weight_keys)}",
                    error_code="INVALID_WEIGHT_CONFIGURATION",
                )

            try:
                new_weight = float(request.value)
                if not (0.0 <= new_weight <= 1.0):
                    raise ValueError("Weight must be between 0.0 and 1.0")
            except (ValueError, TypeError):
                raise ValidationException(
                    f"Invalid weight value for {key}: must be a float between 0.0 and 1.0",
                    error_code="INVALID_WEIGHT_CONFIGURATION",
                )

            # Check hypothetical total weights sum == 1.0
            if self._priority_service is not None:
                current_weights = await self._priority_service.get_effective_config()
                test_weights = dict(current_weights)
                test_weights[key] = new_weight

                w_comm = float(test_weights.get("priority.weights.community_engagement", 0.3))
                w_sev = float(test_weights.get("priority.weights.severity", 0.4))
                w_age = float(test_weights.get("priority.weights.age", 0.2))
                w_org = float(test_weights.get("priority.weights.organization_boost", 0.1))

                total = w_comm + w_sev + w_age + w_org
                if abs(total - 1.0) > 1e-6:
                    raise ValidationException(
                        f"Priority weights must sum to exactly 1.0 (current sum would be {total:.4f})",
                        error_code="INVALID_WEIGHT_CONFIGURATION",
                    )

        await self._settings_repo.set_setting(
            key=key,
            value=request.value,
            category=category,
            description=request.description or (existing.get("description") if existing else None),
            updated_by=current_user.id,
        )

        # Invalidate PriorityService cache if priority setting changed
        if self._priority_service is not None:
            self._priority_service.invalidate_cache()

        await self._audit(
            actor=current_user,
            action="settings.update",
            entity_type="setting",
            entity_id=str(existing.get("_id")) if existing else key,
            metadata={"key": key, "new_value": request.value},
        )

        updated_doc = await self._settings_repo.get_setting_doc(key)
        assert updated_doc is not None

        return SettingItem(
            key=updated_doc["key"],
            value=updated_doc.get("value"),
            category=updated_doc.get("category", "general"),
            description=updated_doc.get("description"),
            is_public=updated_doc.get("is_public", False),
            created_at=updated_doc.get("created_at"),
            updated_at=updated_doc.get("updated_at"),
        )
