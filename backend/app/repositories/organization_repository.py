"""Organization repository (Phase 1.7).

Authoritative source: docs/database-schema.md §2, docs/database-indexes.md, docs/api-contract.md.
"""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.exceptions.base import ConflictException


class OrganizationRepository:
    """MongoDB data access for the `organizations` collection."""

    def __init__(self, database: AsyncDatabase[Any]) -> None:
        self._collection: AsyncCollection[Any] = database["organizations"]

    async def create_indexes(self) -> None:
        """Create authoritative indexes defined in database-indexes.md:

        - idx_orgs_code: code (unique, ascending)
        - idx_orgs_name: name (unique, ascending)
        - idx_orgs_is_active: is_active (ascending)
        """
        await self._collection.create_index("code", unique=True, name="idx_orgs_code")
        await self._collection.create_index("name", unique=True, name="idx_orgs_name")
        await self._collection.create_index("is_active", name="idx_orgs_is_active")

    async def create(self, org_data: dict[str, Any]) -> str:
        """Insert a new organization document. Returns the inserted ID."""
        try:
            result = await self._collection.insert_one(org_data)
            return str(result.inserted_id)
        except DuplicateKeyError as e:
            error_msg = str(e)
            if "code" in error_msg:
                raise ConflictException("Organization code already exists")
            elif "name" in error_msg:
                raise ConflictException("Organization name already exists")
            raise ConflictException("Organization with specified code or name already exists")

    async def find_by_id(self, org_id: str) -> dict[str, Any] | None:
        """Find an organization by ObjectId string."""
        try:
            object_id = ObjectId(org_id)
        except Exception:
            return None
        return await self._collection.find_one({"_id": object_id})

    async def find_by_code(self, code: str) -> dict[str, Any] | None:
        """Find an organization by code (case-insensitive)."""
        return await self._collection.find_one({"code": code.upper()})

    async def find_all(
        self,
        is_active: bool | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        """List organizations with optional active filter and pagination."""
        query: dict[str, Any] = {}
        if is_active is not None:
            query["is_active"] = is_active
        cursor = self._collection.find(query).sort("name", 1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_all(self, is_active: bool | None = None) -> int:
        """Count total organizations."""
        query: dict[str, Any] = {}
        if is_active is not None:
            query["is_active"] = is_active
        return await self._collection.count_documents(query)

    async def update(self, org_id: str, update_data: dict[str, Any]) -> bool:
        """Update organization by ID."""
        try:
            object_id = ObjectId(org_id)
        except Exception:
            return False

        update_data["updated_at"] = datetime.now(UTC)
        try:
            result = await self._collection.update_one({"_id": object_id}, {"$set": update_data})
            return result.matched_count > 0
        except DuplicateKeyError as e:
            error_msg = str(e)
            if "code" in error_msg:
                raise ConflictException("Organization code already exists")
            elif "name" in error_msg:
                raise ConflictException("Organization name already exists")
            raise ConflictException("Duplicate key error")

    async def set_status(self, org_id: str, is_active: bool) -> bool:
        """Toggle organization status."""
        return await self.update(org_id, {"is_active": is_active})
