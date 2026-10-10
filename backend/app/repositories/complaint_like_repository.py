"""Complaint like repository (Phase 1.4).

Persists and queries unique citizen likes on complaints in the `complaint_likes` collection.
Authoritative source: docs/database-schema.md §7 and database-indexes.md.
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


class ComplaintLikeRepository:
    """MongoDB access for `complaint_likes` documents."""

    def __init__(self, database: AsyncDatabase[Any]) -> None:
        self._collection: AsyncCollection[Any] = database["complaint_likes"]

    async def create_indexes(self) -> None:
        """Create authoritative indexes defined in database-indexes.md:

        - idx_likes_complaint_user: complaint_id + user_id (unique, ascending)
        - idx_likes_user_id: user_id (ascending)
        - idx_likes_created_at: created_at (descending)
        """
        await self._collection.create_index(
            [("complaint_id", 1), ("user_id", 1)],
            unique=True,
            name="idx_likes_complaint_user",
        )
        await self._collection.create_index(
            "user_id", name="idx_likes_user_id"
        )
        await self._collection.create_index(
            "created_at", name="idx_likes_created_at"
        )

    async def count_by_complaint(self, complaint_id: object) -> int:
        """Count unique likes on a complaint."""
        cid_oid = to_object_id(complaint_id)
        if cid_oid is None:
            return 0
        return await self._collection.count_documents({"complaint_id": cid_oid})

    async def add_like(self, complaint_id: object, user_id: object) -> bool:
        """Add a like from user to complaint.

        Enforces uniqueness at database level via `idx_likes_complaint_user`.
        Returns True if inserted, False if already exists (DuplicateKeyError).
        """
        from datetime import UTC, datetime

        from pymongo.errors import DuplicateKeyError

        cid_oid = to_object_id(complaint_id)
        uid_oid = to_object_id(user_id)
        if cid_oid is None or uid_oid is None:
            return False

        doc = {
            "complaint_id": cid_oid,
            "user_id": uid_oid,
            "created_at": datetime.now(UTC),
        }
        try:
            await self._collection.insert_one(doc)
            return True
        except DuplicateKeyError:
            return False

    async def remove_like(self, complaint_id: object, user_id: object) -> bool:
        """Remove a like from user on a complaint.

        Returns True if deleted, False if no such like existed.
        """
        cid_oid = to_object_id(complaint_id)
        uid_oid = to_object_id(user_id)
        if cid_oid is None or uid_oid is None:
            return False

        result = await self._collection.delete_one(
            {"complaint_id": cid_oid, "user_id": uid_oid}
        )
        return result.deleted_count > 0

    async def is_liked(self, complaint_id: object, user_id: object) -> bool:
        """Check if user has liked the complaint."""
        cid_oid = to_object_id(complaint_id)
        uid_oid = to_object_id(user_id)
        if cid_oid is None or uid_oid is None:
            return False

        doc = await self._collection.find_one(
            {"complaint_id": cid_oid, "user_id": uid_oid},
            projection={"_id": 1},
        )
        return doc is not None

    async def list_user_liked_complaint_ids(
        self, user_id: object, complaint_ids: Any
    ) -> set[str]:
        """Find which complaint IDs in the given set the user has liked."""
        uid_oid = to_object_id(user_id)
        if uid_oid is None or not complaint_ids:
            return set()


        oids = [to_object_id(cid) for cid in complaint_ids]
        valid_oids = [oid for oid in oids if oid is not None]
        if not valid_oids:
            return set()

        cursor = self._collection.find(
            {"user_id": uid_oid, "complaint_id": {"$in": valid_oids}},
            projection={"complaint_id": 1},
        )
        liked_set: set[str] = set()
        async for doc in cursor:
            liked_set.add(str(doc["complaint_id"]))
        return liked_set

