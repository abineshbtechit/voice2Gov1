"""Category repository (Phase 1.7).

Authoritative source: docs/database-schema.md §4, docs/database-indexes.md, docs/api-contract.md.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.exceptions.base import ConflictException


class CategoryRepository:
    """MongoDB data access for the `categories` collection."""

    def __init__(self, database: AsyncDatabase[Any]) -> None:
        self._collection: AsyncCollection[Any] = database["categories"]

    async def create_indexes(self) -> None:
        """Create authoritative indexes defined in database-indexes.md:

        - idx_cats_org_name: (organization_id, name) unique
        - idx_cats_org_id: organization_id (ascending)
        - idx_cats_org_status: (organization_id, status)
        - idx_cats_default_dept: default_department_id (ascending)
        - idx_cats_sort: sort_order (ascending)
        """
        await self._collection.create_index(
            [("organization_id", 1), ("name", 1)],
            unique=True,
            name="idx_cats_org_name",
        )
        await self._collection.create_index("organization_id", name="idx_cats_org_id")
        await self._collection.create_index(
            [("organization_id", 1), ("status", 1)],
            name="idx_cats_org_status",
        )
        await self._collection.create_index("default_department_id", name="idx_cats_default_dept")
        await self._collection.create_index("sort_order", name="idx_cats_sort")

    async def create(self, category_data: dict[str, Any]) -> str:
        """Insert a new category document. Returns inserted ID."""
        try:
            result = await self._collection.insert_one(category_data)
            return str(result.inserted_id)
        except DuplicateKeyError:
            raise ConflictException("Category with this name already exists in the organization")

    async def find_by_id(self, category_id: str) -> dict[str, Any] | None:
        """Find a category by ObjectId string."""
        try:
            object_id = ObjectId(category_id)
        except Exception:
            return None
        return await self._collection.find_one({"_id": object_id})

    async def find_by_ids(self, category_ids: Sequence[str]) -> list[dict[str, Any]]:
        """Find several categories in one query ($in).

        Prevents list endpoints from issuing one lookup per item (N+1).
        """
        oids: list[ObjectId] = []
        for cid in category_ids:
            try:
                oids.append(ObjectId(cid))
            except Exception:
                continue
        if not oids:
            return []
        cursor = self._collection.find({"_id": {"$in": oids}})
        return await cursor.to_list(length=len(oids))

    async def find_by_id_active(self, category_id: str) -> dict[str, Any] | None:
        """Find an active category by ObjectId string."""
        try:
            object_id = ObjectId(category_id)
        except Exception:
            return None
        return await self._collection.find_one({"_id": object_id, "status": "active"})

    async def list_active(
        self,
        organization_id: str | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        """List active categories ordered deterministically by sort_order, then name."""
        query: dict[str, Any] = {"status": "active"}
        if organization_id:
            query["organization_id"] = organization_id
        cursor = self._collection.find(query).sort([("sort_order", 1), ("name", 1)]).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def list_all(
        self,
        organization_id: str | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        """List all categories (admin use)."""
        query: dict[str, Any] = {}
        if organization_id:
            query["organization_id"] = organization_id
        cursor = self._collection.find(query).sort([("sort_order", 1), ("name", 1)]).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_active(self, organization_id: str | None = None) -> int:
        query: dict[str, Any] = {"status": "active"}
        if organization_id:
            query["organization_id"] = organization_id
        return await self._collection.count_documents(query)

    async def update(self, category_id: str, update_data: dict[str, Any]) -> bool:
        """Update category by ID."""
        try:
            object_id = ObjectId(category_id)
        except Exception:
            return False

        update_data["updated_at"] = datetime.now(UTC)
        try:
            result = await self._collection.update_one({"_id": object_id}, {"$set": update_data})
            return result.matched_count > 0
        except DuplicateKeyError:
            raise ConflictException("Category with this name already exists in the organization")

    async def soft_delete(self, category_id: str) -> bool:
        """Deactivate category by setting status to inactive."""
        return await self.update(category_id, {"status": "inactive"})
