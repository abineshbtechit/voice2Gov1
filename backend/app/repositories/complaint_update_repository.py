"""Complaint updates repository (Phase 1.3.6).

Persists and queries complaint timeline updates in the `complaint_updates` collection.
Authoritative source: docs/database-schema.md §8 and database-indexes.md.
"""

from typing import Any

from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase


def to_object_id(value: object) -> ObjectId | None:
    """Safe conversion to ObjectId guarding against operator injection."""
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


#: Safety ceiling for a single timeline retrieval. The API contract returns all
#: updates for a complaint (no pagination); the cap prevents unbounded memory
#: use from a pathological complaint while never being hit by realistic data.
MAX_UPDATES_PER_RETRIEVAL = 1000


class ComplaintUpdateRepository:
    """MongoDB access for `complaint_updates` documents."""

    def __init__(self, database: AsyncDatabase[Any]) -> None:
        self._collection: AsyncCollection[Any] = database["complaint_updates"]

    async def create_indexes(self) -> None:
        """Create the 5 authoritative indexes defined in database-indexes.md:

        - idx_updates_complaint_id: complaint_id (ascending)
        - idx_updates_complaint_created: complaint_id (1), created_at (-1)
        - idx_updates_org_id: organization_id (ascending)
        - idx_updates_dept_id: department_id (ascending)
        - idx_updates_updated_by: updated_by (ascending)
        """
        await self._collection.create_index(
            "complaint_id", name="idx_updates_complaint_id"
        )
        await self._collection.create_index(
            [("complaint_id", 1), ("created_at", -1)],
            name="idx_updates_complaint_created",
        )
        await self._collection.create_index(
            "organization_id", name="idx_updates_org_id"
        )
        await self._collection.create_index(
            "department_id", name="idx_updates_dept_id"
        )
        await self._collection.create_index(
            "updated_by", name="idx_updates_updated_by"
        )

    async def create(self, update_doc: dict[str, Any]) -> str:
        """Insert a complaint update document. Returns inserted _id as string.

        department_id is required per docs/database-schema.md §8.
        """
        dept_id = update_doc.get("department_id")
        if not dept_id:
            raise ValueError("department_id is required for complaint_updates")
        result = await self._collection.insert_one(update_doc)
        return str(result.inserted_id)

    async def find_by_id(self, update_id: object) -> dict[str, Any] | None:
        """Find a single update by id."""
        oid = to_object_id(update_id)
        if oid is None:
            return None
        return await self._collection.find_one({"_id": oid})

    async def find_by_complaint(
        self,
        complaint_id: object,
        *,
        is_public_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Retrieve updates for a complaint ordered chronologically.

        Uses the compound index (complaint_id: 1, created_at: -1) or sort asc (created_at: 1).
        By timeline convention, updates are sorted oldest first (created_at: 1).
        """
        cid = to_object_id(complaint_id)
        if cid is None:
            return []

        query: dict[str, Any] = {"complaint_id": cid}
        if is_public_only:
            query["is_public"] = True

        cursor = self._collection.find(query).sort("created_at", 1)
        return await cursor.to_list(length=MAX_UPDATES_PER_RETRIEVAL)
