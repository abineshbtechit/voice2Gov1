"""Department repository (Phase 1.7).

Authoritative source: docs/database-schema.md §3, docs/database-indexes.md, docs/api-contract.md.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.exceptions.base import ConflictException


class DepartmentRepository:
    """MongoDB data access for the `departments` collection."""

    def __init__(self, database: AsyncDatabase[Any]) -> None:
        self._collection: AsyncCollection[Any] = database["departments"]

    async def create_indexes(self) -> None:
        """Create authoritative indexes defined in database-indexes.md:

        - idx_depts_org_id: organization_id (ascending)
        - idx_depts_org_code: (organization_id, code) unique
        - idx_depts_org_name: (organization_id, name) unique
        - idx_depts_org_active: (organization_id, is_active)
        """
        await self._collection.create_index("organization_id", name="idx_depts_org_id")
        await self._collection.create_index(
            [("organization_id", 1), ("code", 1)],
            unique=True,
            name="idx_depts_org_code",
        )
        await self._collection.create_index(
            [("organization_id", 1), ("name", 1)],
            unique=True,
            name="idx_depts_org_name",
        )
        await self._collection.create_index(
            [("organization_id", 1), ("is_active", 1)],
            name="idx_depts_org_active",
        )

    async def create(self, dept_data: dict[str, Any]) -> str:
        """Insert a new department document. Returns inserted ID."""
        try:
            result = await self._collection.insert_one(dept_data)
            return str(result.inserted_id)
        except DuplicateKeyError as e:
            error_msg = str(e)
            if "code" in error_msg:
                raise ConflictException("Department code already exists in this organization")
            elif "name" in error_msg:
                raise ConflictException("Department name already exists in this organization")
            raise ConflictException("Department with specified code or name already exists in this organization")

    async def find_by_id(self, department_id: str) -> dict[str, Any] | None:
        """Find a department by ObjectId string (unscoped / admin)."""
        try:
            object_id = ObjectId(department_id)
        except Exception:
            return None
        return await self._collection.find_one({"_id": object_id})

    async def find_by_ids(self, department_ids: Sequence[str]) -> list[dict[str, Any]]:
        """Find several departments in one query ($in).

        Prevents list endpoints from issuing one lookup per item (N+1).
        """
        oids: list[ObjectId] = []
        for did in department_ids:
            try:
                oids.append(ObjectId(did))
            except Exception:
                continue
        if not oids:
            return []
        cursor = self._collection.find({"_id": {"$in": oids}})
        return await cursor.to_list(length=len(oids))

    async def find_by_id_in_org(
        self, department_id: str, organization_id: str
    ) -> dict[str, Any] | None:
        """Find a department scoped to an organization."""
        try:
            object_id = ObjectId(department_id)
        except Exception:
            return None
        return await self._collection.find_one(
            {"_id": object_id, "organization_id": organization_id}
        )

    async def find_by_id_active_in_org(
        self, department_id: str, organization_id: str
    ) -> dict[str, Any] | None:
        """Find an active department by ID within an organization."""
        try:
            object_id = ObjectId(department_id)
        except Exception:
            return None
        return await self._collection.find_one(
            {"_id": object_id, "organization_id": organization_id, "is_active": True}
        )

    async def list_by_org(
        self,
        organization_id: str,
        is_active: bool | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        """List departments in an organization with optional active filter."""
        query: dict[str, Any] = {"organization_id": organization_id}
        if is_active is not None:
            query["is_active"] = is_active
        cursor = self._collection.find(query).sort("name", 1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_by_org(
        self, organization_id: str, is_active: bool | None = None
    ) -> int:
        """Count departments in an organization."""
        query: dict[str, Any] = {"organization_id": organization_id}
        if is_active is not None:
            query["is_active"] = is_active
        return await self._collection.count_documents(query)

    async def count_all(self, is_active: bool | None = None) -> int:
        """Count all departments across organizations (for admin stats)."""
        query: dict[str, Any] = {}
        if is_active is not None:
            query["is_active"] = is_active
        return await self._collection.count_documents(query)

    async def list_all(
        self,
        is_active: bool | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        """List all departments (admin only)."""
        query: dict[str, Any] = {}
        if is_active is not None:
            query["is_active"] = is_active
        cursor = self._collection.find(query).sort("name", 1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def update(
        self, department_id: str, organization_id: str, update_data: dict[str, Any]
    ) -> bool:
        """Update department scoped to organization."""
        try:
            object_id = ObjectId(department_id)
        except Exception:
            return False

        update_data["updated_at"] = datetime.now(UTC)
        try:
            result = await self._collection.update_one(
                {"_id": object_id, "organization_id": organization_id},
                {"$set": update_data},
            )
            return result.matched_count > 0
        except DuplicateKeyError as e:
            error_msg = str(e)
            if "code" in error_msg:
                raise ConflictException("Department code already exists in this organization")
            elif "name" in error_msg:
                raise ConflictException("Department name already exists in this organization")
            raise ConflictException("Duplicate key error")

    async def soft_delete(self, department_id: str, organization_id: str) -> bool:
        """Soft-deactivate a department (is_active = False)."""
        return await self.update(
            department_id, organization_id, {"is_active": False}
        )
