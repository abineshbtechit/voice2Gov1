"""Notification repository (Phase 1.6).

MongoDB access for `notifications` collection.
Authoritative source: docs/database-schema.md §9 and docs/database-indexes.md.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase


def to_object_id(value: object) -> ObjectId | None:
    """Safe conversion to ObjectId guarding against operator injection."""
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


class NotificationRepository:
    """MongoDB persistence layer for the `notifications` collection."""

    def __init__(self, database: AsyncDatabase[Any]) -> None:
        self._collection: AsyncCollection[Any] = database["notifications"]

    async def create_indexes(self) -> None:
        """Create authoritative indexes defined in database-indexes.md:

        - idx_notifs_user_id: user_id (ascending)
        - idx_notifs_user_unread: user_id + is_read (ascending)
        - idx_notifs_user_created: user_id (ascending) + created_at (descending)
        - idx_notifs_complaint_id: complaint_id (ascending)
        """
        await self._collection.create_index(
            [("user_id", ASCENDING)],
            name="idx_notifs_user_id",
        )
        await self._collection.create_index(
            [("user_id", ASCENDING), ("is_read", ASCENDING)],
            name="idx_notifs_user_unread",
        )
        await self._collection.create_index(
            [("user_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_notifs_user_created",
        )
        await self._collection.create_index(
            [("complaint_id", ASCENDING)],
            name="idx_notifs_complaint_id",
        )

    async def create(self, document: dict[str, Any]) -> str:
        """Insert a notification document into MongoDB and return its string ID."""
        doc = dict(document)
        if "user_id" in doc and not isinstance(doc["user_id"], ObjectId):
            oid = to_object_id(doc["user_id"])
            if oid:
                doc["user_id"] = oid
        if "complaint_id" in doc and doc["complaint_id"] is not None and not isinstance(doc["complaint_id"], ObjectId):
            cid = to_object_id(doc["complaint_id"])
            doc["complaint_id"] = cid

        if "created_at" not in doc:
            doc["created_at"] = datetime.now(UTC)
        if "is_read" not in doc:
            doc["is_read"] = False
        if "read_at" not in doc:
            doc["read_at"] = None

        result = await self._collection.insert_one(doc)
        return str(result.inserted_id)

    async def find_by_id(self, notification_id: object, user_id: object) -> dict[str, Any] | None:
        """Find a single notification ensuring strict user ownership isolation."""
        nid = to_object_id(notification_id)
        uid = to_object_id(user_id)
        if nid is None or uid is None:
            return None
        return await self._collection.find_one({"_id": nid, "user_id": uid})

    async def list_for_user(
        self,
        user_id: object,
        is_read: bool | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Sequence[dict[str, Any]]:
        """List notifications for a user, sorted descending by created_at."""
        uid = to_object_id(user_id)
        if uid is None:
            return []

        filter_doc: dict[str, Any] = {"user_id": uid}
        if is_read is not None:
            filter_doc["is_read"] = is_read

        cursor = (
            self._collection.find(filter_doc)
            .sort([("created_at", DESCENDING), ("_id", DESCENDING)])
            .skip(max(0, skip))
            .limit(max(1, limit))
        )
        return await cursor.to_list(length=limit)

    async def count_for_user(self, user_id: object, is_read: bool | None = None) -> int:
        """Count total notifications for a user, optionally filtered by read status."""
        uid = to_object_id(user_id)
        if uid is None:
            return 0

        filter_doc: dict[str, Any] = {"user_id": uid}
        if is_read is not None:
            filter_doc["is_read"] = is_read

        return await self._collection.count_documents(filter_doc)

    async def count_unread(self, user_id: object) -> int:
        """Count unread notifications for a user (backed by idx_notifs_user_unread)."""
        return await self.count_for_user(user_id, is_read=False)

    async def mark_read(
        self,
        notification_id: object,
        user_id: object,
        read_at: datetime | None = None,
    ) -> bool:
        """Mark a single notification as read if owned by user.

        Returns True if matched and updated (or already marked read).
        """
        nid = to_object_id(notification_id)
        uid = to_object_id(user_id)
        if nid is None or uid is None:
            return False

        now = read_at or datetime.now(UTC)
        result = await self._collection.update_one(
            {"_id": nid, "user_id": uid},
            {"$set": {"is_read": True, "read_at": now}},
        )
        return result.matched_count > 0

    async def mark_all_read(
        self,
        user_id: object,
        read_at: datetime | None = None,
    ) -> int:
        """Mark all unread notifications for a user as read.

        Returns number of notifications modified.
        """
        uid = to_object_id(user_id)
        if uid is None:
            return 0

        now = read_at or datetime.now(UTC)
        result = await self._collection.update_many(
            {"user_id": uid, "is_read": False},
            {"$set": {"is_read": True, "read_at": now}},
        )
        return result.modified_count
