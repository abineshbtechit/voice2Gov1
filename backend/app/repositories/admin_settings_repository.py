"""Admin settings repository (Phase 1.4 & 1.7).

Persists and queries system settings and priority engine configuration in the `admin_settings` collection.
Authoritative source: docs/database-schema.md §12, docs/database-indexes.md, docs/priority-engine.md.
"""

from datetime import UTC, datetime
from typing import Any

from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase


class AdminSettingsRepository:
    """MongoDB access for `admin_settings` documents."""

    def __init__(self, database: AsyncDatabase[Any]) -> None:
        self._collection: AsyncCollection[Any] = database["admin_settings"]

    async def create_indexes(self) -> None:
        """Create authoritative indexes defined in database-indexes.md:

        - idx_settings_key: key (unique, ascending)
        - idx_settings_category: category (ascending)
        """
        await self._collection.create_index(
            "key",
            unique=True,
            name="idx_settings_key",
        )
        await self._collection.create_index(
            "category",
            name="idx_settings_category",
        )

    async def get_setting(self, key: str) -> Any | None:
        """Find a setting document by its unique key and return its value."""
        doc = await self._collection.find_one({"key": key})
        if doc is not None:
            return doc.get("value")
        return None

    async def get_setting_doc(self, key: str) -> dict[str, Any] | None:
        """Find the full setting document by key."""
        return await self._collection.find_one({"key": key})

    async def get_settings_by_category(self, category: str) -> dict[str, Any]:
        """Retrieve all settings for a category as a key -> value mapping."""
        cursor = self._collection.find({"category": category})
        results: dict[str, Any] = {}
        async for doc in cursor:
            results[doc["key"]] = doc.get("value")
        return results

    async def list_all_settings(self) -> list[dict[str, Any]]:
        """Retrieve all setting documents ordered by category, then key."""
        cursor = self._collection.find().sort([("category", 1), ("key", 1)])
        return await cursor.to_list(length=200)

    async def set_setting(
        self,
        key: str,
        value: Any,
        category: str = "priority",
        description: str | None = None,
        updated_by: str | None = None,
    ) -> None:
        """Upsert a setting value."""
        now = datetime.now(UTC)
        update_fields: dict[str, Any] = {
            "value": value,
            "category": category,
            "updated_at": now,
        }
        if description is not None:
            update_fields["description"] = description
        if updated_by is not None:
            update_fields["updated_by"] = updated_by

        await self._collection.update_one(
            {"key": key},
            {
                "$set": update_fields,
                "$setOnInsert": {
                    "created_at": now,
                    "is_public": False,
                },
            },
            upsert=True,
        )
