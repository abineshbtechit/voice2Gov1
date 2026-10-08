"""Refresh-token registry / revocation repository.

Storage decision (SRS-driven): ``scripts/create_indexes.py`` already defines a
``token_blacklist`` collection with a unique ``token_hash``, ``family_id``,
``user_id``, ``user_id+revoked_at`` and a TTL on ``expires_at``. We store one
record per *issued* refresh token in that collection — **hash only, never the
raw token** — and mark ``revoked_at`` on rotation / logout / family
revocation. The record therefore doubles as the SRS "blacklist" while enabling
reuse detection. No new collection or index is introduced.
"""

from datetime import datetime
from typing import Any

from pymongo import ReturnDocument
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase

TOKEN_COLLECTION = "token_blacklist"


class RefreshTokenRepository:
    def __init__(self, database: AsyncDatabase[Any]) -> None:
        self._collection: AsyncCollection[Any] = database[TOKEN_COLLECTION]

    async def insert_token(self, record: dict[str, Any]) -> str:
        """Persist a refresh-token record. Returns the inserted id."""
        result = await self._collection.insert_one(record)
        return str(result.inserted_id)

    async def find_by_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        """Look a record up by its deterministic token hash."""
        return await self._collection.find_one({"token_hash": token_hash})

    async def revoke_if_active(
        self,
        token_hash: str,
        revoked_at: datetime,
        replaced_by: str | None = None,
    ) -> dict[str, Any] | None:
        """Atomically revoke a token iff it is still active.

        Returns the updated document on success, or ``None`` if the token was
        already revoked or is absent. Implemented as a single guarded
        ``find_one_and_update`` on ``revoked_at: None``, so two concurrent
        rotations of the same token cannot both succeed.
        """
        return await self._collection.find_one_and_update(
            {"token_hash": token_hash, "revoked_at": None},
            {"$set": {"revoked_at": revoked_at, "replaced_by": replaced_by}},
            return_document=ReturnDocument.AFTER,
        )

    async def revoke_family(
        self,
        family_id: str,
        revoked_at: datetime,
        reuse_detected: bool = False,
    ) -> int:
        """Revoke every currently-active token in a family. Returns count revoked."""
        result = await self._collection.update_many(
            {"family_id": family_id, "revoked_at": None},
            {"$set": {"revoked_at": revoked_at, "reuse_detected": reuse_detected}},
        )
        return int(result.modified_count)
