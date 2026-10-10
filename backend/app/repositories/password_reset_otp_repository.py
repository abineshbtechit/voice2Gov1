from datetime import UTC, datetime
from typing import Any

from pymongo import ReturnDocument
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase

COLLECTION_NAME = "password_reset_otps"


class PasswordResetOTPRepository:
    """Repository for password reset OTP records with hash security and expiration."""

    def __init__(self, database: AsyncDatabase[Any]) -> None:
        self._collection: AsyncCollection[Any] = database[COLLECTION_NAME]

    async def create_otp(
        self,
        identifier: str,
        otp_hash: str,
        salt: str,
        expires_at: datetime,
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        """Invalidate previous unconsumed OTPs for identifier and store fresh OTP."""
        # Mark previous active records as consumed/superseded
        now = datetime.now(UTC)
        await self._collection.update_many(
            {"identifier": identifier, "is_consumed": False},
            {"$set": {"is_consumed": True, "superseded_at": now}},
        )

        record = {
            "identifier": identifier,
            "otp_hash": otp_hash,
            "salt": salt,
            "attempts": 0,
            "max_attempts": max_attempts,
            "is_consumed": False,
            "created_at": now,
            "expires_at": expires_at,
            "reset_token_hash": None,
            "reset_token_expires_at": None,
        }
        res = await self._collection.insert_one(record)
        record["_id"] = res.inserted_id
        return record

    async def get_latest_active_otp(self, identifier: str) -> dict[str, Any] | None:
        """Find the latest active unconsumed OTP for identifier."""
        now = datetime.now(UTC)
        return await self._collection.find_one(
            {
                "identifier": identifier,
                "is_consumed": False,
                "expires_at": {"$gt": now},
            },
            sort=[("created_at", -1)],
        )

    async def increment_attempts(self, record_id: Any) -> int:
        """Increment attempt count and return new attempts count."""
        res = await self._collection.find_one_and_update(
            {"_id": record_id},
            {"$inc": {"attempts": 1}},
            return_document=ReturnDocument.AFTER,
        )
        return res["attempts"] if res else 999

    async def mark_verified_and_set_reset_token(
        self,
        record_id: Any,
        reset_token_hash: str,
        reset_token_expires_at: datetime,
    ) -> bool:
        """Atomically mark OTP as consumed and associate reset token hash."""
        res = await self._collection.find_one_and_update(
            {"_id": record_id, "is_consumed": False},
            {
                "$set": {
                    "is_consumed": True,
                    "reset_token_hash": reset_token_hash,
                    "reset_token_expires_at": reset_token_expires_at,
                    "verified_at": datetime.now(UTC),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return res is not None

    async def find_by_reset_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        """Find record by valid, unconsumed reset token hash."""
        now = datetime.now(UTC)
        return await self._collection.find_one({
            "reset_token_hash": token_hash,
            "reset_token_expires_at": {"$gt": now},
            "token_consumed": {"$ne": True},
        })

    async def consume_reset_token(self, record_id: Any) -> bool:
        """Atomically consume the reset token preventing replay."""
        res = await self._collection.find_one_and_update(
            {"_id": record_id, "token_consumed": {"$ne": True}},
            {
                "$set": {
                    "token_consumed": True,
                    "consumed_at": datetime.now(UTC),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return res is not None
