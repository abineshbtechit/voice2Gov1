"""Complaint image metadata repository (Phase 1.3.4).

Persists image *metadata* in the ``complaint_images`` collection; binary
content lives in the pluggable storage backend. Client-supplied identifiers are
converted to ``ObjectId`` before use, so raw MongoDB operators can never reach
a query.
"""

from collections.abc import Sequence
from typing import Any

from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase

from app.schemas.complaint_image import ImageType


def to_object_id(value: object) -> ObjectId | None:
    """Return an ``ObjectId`` for a valid id, else ``None``.

    Guards every query boundary against MongoDB operator injection: a dict such
    as ``{"$ne": None}`` is neither an ``ObjectId`` nor a valid id string, so it
    can never be used as a query value.
    """
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


class ComplaintImageRepository:
    """MongoDB access for ``complaint_images`` documents."""

    def __init__(self, database: AsyncDatabase[Any]) -> None:
        self._collection: AsyncCollection[Any] = database["complaint_images"]

    async def create_indexes(self) -> None:
        """Create the four ``complaint_images`` indexes from database-indexes.md.

        - ``complaint_id`` — all images for a complaint
        - ``complaint_id + image_type`` — images by type
        - ``uploaded_by`` — a user's uploaded images
        - ``created_at`` (descending) — recent uploads
        """
        await self._collection.create_index("complaint_id", name="idx_images_complaint_id")
        await self._collection.create_index(
            [("complaint_id", 1), ("image_type", 1)], name="idx_images_complaint_type"
        )
        await self._collection.create_index("uploaded_by", name="idx_images_uploaded_by")
        await self._collection.create_index(
            "created_at", name="idx_images_created_at"
        )

    async def create(self, metadata: dict[str, Any]) -> str:
        """Insert one image metadata document. Returns the inserted id."""
        result = await self._collection.insert_one(metadata)
        return str(result.inserted_id)

    async def create_many(self, records: list[dict[str, Any]]) -> list[str]:
        """Insert several metadata documents in one call. Returns the inserted ids."""
        result = await self._collection.insert_many(records)
        return [str(inserted_id) for inserted_id in result.inserted_ids]

    async def find_by_id(
        self,
        image_id: object,
        complaint_id: object | None = None,
        *,
        include_deleted: bool = False,
    ) -> dict[str, Any] | None:
        """Find an image by id, optionally scoped to a complaint."""
        object_id = to_object_id(image_id)
        if object_id is None:
            return None
        query: dict[str, Any] = {"_id": object_id}
        if complaint_id is not None:
            complaint_object_id = to_object_id(complaint_id)
            if complaint_object_id is None:
                return None
            query["complaint_id"] = complaint_object_id
        if not include_deleted:
            query["is_deleted"] = False
        return await self._collection.find_one(query)

    async def find_by_complaint(
        self,
        complaint_id: object,
        *,
        image_type: ImageType | str | None = None,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        """List a complaint's images, oldest first."""
        complaint_object_id = to_object_id(complaint_id)
        if complaint_object_id is None:
            return []
        query: dict[str, Any] = {"complaint_id": complaint_object_id}
        if image_type is not None:
            query["image_type"] = (
                image_type.value if isinstance(image_type, ImageType) else str(image_type)
            )
        if not include_deleted:
            query["is_deleted"] = False
        cursor = self._collection.find(query).sort("created_at", 1)
        # Images are bounded by upload limits, but a ceiling keeps the
        # retrieval bounded even for pathological data.
        return await cursor.to_list(length=1000)

    async def count_by_complaint(
        self, complaint_id: object, *, include_deleted: bool = False
    ) -> int:
        """Count images attached to a complaint."""
        complaint_object_id = to_object_id(complaint_id)
        if complaint_object_id is None:
            return 0
        query: dict[str, Any] = {"complaint_id": complaint_object_id}
        if not include_deleted:
            query["is_deleted"] = False
        return await self._collection.count_documents(query)

    async def count_by_complaints(self, complaint_ids: Sequence[object]) -> dict[str, int]:
        """Count non-deleted images for several complaints in one aggregate query.

        Prevents the feed from issuing one count query per item (N+1).
        """
        oids = [oid for oid in (to_object_id(c) for c in complaint_ids) if oid is not None]
        if not oids:
            return {}
        pipeline: list[dict[str, Any]] = [
            {"$match": {"complaint_id": {"$in": oids}, "is_deleted": False}},
            {"$group": {"_id": "$complaint_id", "count": {"$sum": 1}}},
        ]
        cursor = await self._collection.aggregate(pipeline)
        counts: dict[str, int] = {}
        async for doc in cursor:
            counts[str(doc["_id"])] = int(doc["count"])
        return counts

    async def soft_delete(self, image_id: object, complaint_id: object | None = None) -> bool:
        """Mark an image as deleted (physical deletion is deferred)."""
        object_id = to_object_id(image_id)
        if object_id is None:
            return False
        query: dict[str, Any] = {"_id": object_id, "is_deleted": False}
        if complaint_id is not None:
            complaint_object_id = to_object_id(complaint_id)
            if complaint_object_id is None:
                return False
            query["complaint_id"] = complaint_object_id
        result = await self._collection.update_one(query, {"$set": {"is_deleted": True}})
        return result.modified_count > 0
