from datetime import UTC, datetime
from typing import Any

from pymongo import ReturnDocument
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase

COLLECTION_NAME = "account_verification_otps"


class AccountVerificationOTPRepository:
    """Repository for user account registration OTP verification records."""

    def __init__(self, database: AsyncDatabase[Any]) -> None:
        self._collection: AsyncCollection[Any] = database[COLLECTION_NAME]

    async def create_otp(
        self,
        identifier: str,
        otp_hash: str,
        salt: str,
        channel: str,
        expires_at: datetime,
        user_id: str | None = None,
        max_attempts: int = 5,
    ) -> dict[str, Any]:
        """Invalidate previous unconsumed OTPs for identifier and persist fresh OTP."""
        now = datetime.now(UTC)
        await self._collection.update_many(
            {"identifier": identifier, "is_consumed": False},
            {"$set": {"is_consumed": True, "superseded_at": now}},
        )

        record = {
            "identifier": identifier,
            "user_id": user_id,
            "otp_hash": otp_hash,
            "salt": salt,
            "channel": channel,
            "attempts": 0,
            "max_attempts": max_attempts,
            "is_consumed": False,
            "created_at": now,
            "expires_at": expires_at,
            "verified_at": None,
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

    async def mark_consumed(self, record_id: Any) -> bool:
        """Atomically mark OTP as consumed upon successful verification."""
        res = await self._collection.find_one_and_update(
            {"_id": record_id, "is_consumed": False},
            {
                "$set": {
                    "is_consumed": True,
                    "verified_at": datetime.now(UTC),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return res is not None

