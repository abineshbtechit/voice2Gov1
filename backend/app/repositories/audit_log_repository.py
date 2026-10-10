"""Audit log repository (Phase 1.7).

Authoritative source: docs/database-schema.md §11, docs/database-indexes.md, docs/api-contract.md.
"""

from datetime import UTC, datetime
from typing import Any

from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase


class AuditLogRepository:
    """MongoDB data access for the immutable `audit_logs` collection.

    Append-only: No update or delete operations are exposed.
    """

    def __init__(self, database: AsyncDatabase[Any]) -> None:
        self._collection: AsyncCollection[Any] = database["audit_logs"]

    async def create_indexes(self) -> None:
        """Create authoritative indexes defined in database-indexes.md:

        - idx_audit_actor_id: actor_id (ascending)
        - idx_audit_entity_type: entity_type (ascending)
        - idx_audit_entity_id: entity_id (ascending)
        - idx_audit_action: action (ascending)
        - idx_audit_created_at: created_at (descending)
        - idx_audit_entity_timeline: (entity_type, entity_id, created_at)
        """
        await self._collection.create_index("actor_id", name="idx_audit_actor_id")
        await self._collection.create_index("entity_type", name="idx_audit_entity_type")
        await self._collection.create_index("entity_id", name="idx_audit_entity_id")
        await self._collection.create_index("action", name="idx_audit_action")
        await self._collection.create_index([("created_at", -1)], name="idx_audit_created_at")
        await self._collection.create_index(
            [("entity_type", 1), ("entity_id", 1), ("created_at", -1)],
            name="idx_audit_entity_timeline",
        )

    async def log_event(
        self,
        actor_id: str,
        actor_role: str,
        action: str,
        entity_type: str,
        entity_id: str,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> str:
        """Record an immutable audit log entry."""
        entry: dict[str, Any] = {
            "actor_id": actor_id,
            "actor_role": actor_role,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "metadata": metadata or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime.now(UTC),
        }
        result = await self._collection.insert_one(entry)
        return str(result.inserted_id)

    async def find_logs(
        self,
        actor_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        action: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        """List audit records ordered newest first (admin only)."""
        query: dict[str, Any] = {}
        if actor_id:
            query["actor_id"] = actor_id
        if entity_type:
            query["entity_type"] = entity_type
        if entity_id:
            query["entity_id"] = entity_id
        if action:
            query["action"] = action

        cursor = self._collection.find(query).sort([("created_at", -1)]).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_logs(
        self,
        actor_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        action: str | None = None,
    ) -> int:
        """Count matching audit records."""
        query: dict[str, Any] = {}
        if actor_id:
            query["actor_id"] = actor_id
        if entity_type:
            query["entity_type"] = entity_type
        if entity_id:
            query["entity_id"] = entity_id
        if action:
            query["action"] = action
        return await self._collection.count_documents(query)
