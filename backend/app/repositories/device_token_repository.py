"""Device token repository (Phase 1.6).

MongoDB access for `device_tokens` collection.
Authoritative source: docs/database-schema.md §10 and docs/database-indexes.md.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError


def to_object_id(value: object) -> ObjectId | None:
    """Safe conversion to ObjectId guarding against operator injection."""
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


class DeviceTokenRepository:
    """MongoDB persistence layer for `device_tokens`."""

    def __init__(self, database: AsyncDatabase[Any]) -> None:
        self._collection: AsyncCollection[Any] = database["device_tokens"]

    async def create_indexes(self) -> None:
        """Create authoritative indexes defined in database-indexes.md:

        - idx_device_user_id: user_id (ascending)
        - idx_device_token: device_token (ascending)
        - idx_device_user_active: user_id + is_active (ascending)
        - idx_device_user_token: user_id + device_token (unique, ascending)
        """
        await self._collection.create_index(
            [("user_id", ASCENDING)],
            name="idx_device_user_id",
        )
        await self._collection.create_index(
            [("device_token", ASCENDING)],
            name="idx_device_token",
        )
        await self._collection.create_index(
            [("user_id", ASCENDING), ("is_active", ASCENDING)],
            name="idx_device_user_active",
        )
        await self._collection.create_index(
            [("user_id", ASCENDING), ("device_token", ASCENDING)],
            unique=True,
            name="idx_device_user_token",
        )

    async def upsert_token(
        self,
        user_id: object,
        device_token: str,
        platform: str,
        device_id: str | None = None,
        app_version: str | None = None,
    ) -> dict[str, Any]:
        """Register or update a device token for a user.

        Ensures active status is refreshed and timestamps are maintained.
        """
        uid = to_object_id(user_id)
        if uid is None:
            raise ValueError(f"Invalid user_id: {user_id}")

        now = datetime.now(UTC)
        filter_doc = {
            "user_id": uid,
            "device_token": device_token,
        }

        update_doc = {
            "$set": {
                "platform": platform,
                "device_id": device_id,
                "app_version": app_version,
                "is_active": True,
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
                "last_used_at": None,
            },
        }

        try:
            await self._collection.update_one(filter_doc, update_doc, upsert=True)
        except DuplicateKeyError:
            # Race-safety boundary: two concurrent registrations of the same
            # (user_id, device_token) can both pass the upsert check; the unique
            # index rejects the loser. The record exists, so re-apply the update
            # without the insert branch.
            update_doc.pop("$setOnInsert", None)
            await self._collection.update_one(filter_doc, update_doc)
        doc = await self._collection.find_one(filter_doc)
        return doc or {}

    async def get_active_tokens(self, user_id: object) -> Sequence[dict[str, Any]]:
        """Retrieve all active device tokens registered to a given user."""
        uid = to_object_id(user_id)
        if uid is None:
            return []

        cursor = self._collection.find({"user_id": uid, "is_active": True})
        return await cursor.to_list(length=100)

    async def mark_token_inactive(self, device_token: str) -> int:
        """Mark a device token as inactive (e.g. upon push provider invalid token feedback)."""
        now = datetime.now(UTC)
        result = await self._collection.update_many(
            {"device_token": device_token},
            {"$set": {"is_active": False, "updated_at": now}},
        )
        return result.modified_count

    async def update_last_used(self, device_token: str) -> None:
        """Update last_used_at timestamp on successful push notification."""
        now = datetime.now(UTC)
        await self._collection.update_many(
            {"device_token": device_token},
            {"$set": {"last_used_at": now, "updated_at": now}},
        )
