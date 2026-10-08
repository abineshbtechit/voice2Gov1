"""Phase 1.2.3 — refresh-token repository tests (atomic guarded revoke, family)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from pymongo import ReturnDocument

from app.repositories.refresh_token_repository import (
    TOKEN_COLLECTION,
    RefreshTokenRepository,
)


@pytest.fixture
def collection() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def repository(collection: AsyncMock) -> RefreshTokenRepository:
    database = MagicMock()
    database.__getitem__.return_value = collection
    return RefreshTokenRepository(database)


class TestStorageLocation:
    def test_uses_the_srs_token_blacklist_collection(self) -> None:
        database = MagicMock()
        RefreshTokenRepository(database)
        database.__getitem__.assert_called_once_with(TOKEN_COLLECTION)
        assert TOKEN_COLLECTION == "token_blacklist"


class TestInsert:
    async def test_insert_returns_id(
        self, repository: RefreshTokenRepository, collection: AsyncMock
    ) -> None:
        collection.insert_one.return_value = MagicMock(inserted_id="abc123")

        result = await repository.insert_token({"token_hash": "h"})

        assert result == "abc123"
        collection.insert_one.assert_awaited_once_with({"token_hash": "h"})


class TestLookup:
    async def test_find_by_token_hash(
        self, repository: RefreshTokenRepository, collection: AsyncMock
    ) -> None:
        collection.find_one.return_value = {"token_hash": "h", "revoked_at": None}

        record = await repository.find_by_token_hash("h")

        assert record == {"token_hash": "h", "revoked_at": None}
        collection.find_one.assert_awaited_once_with({"token_hash": "h"})


class TestAtomicRevoke:
    async def test_revoke_is_guarded_on_active_only(
        self, repository: RefreshTokenRepository, collection: AsyncMock
    ) -> None:
        now = datetime.now(UTC)
        collection.find_one_and_update.return_value = {"token_hash": "h", "revoked_at": now}

        record = await repository.revoke_if_active("h", revoked_at=now, replaced_by="new-jti")

        assert record is not None
        args, kwargs = collection.find_one_and_update.await_args
        # The filter requires revoked_at is None -> only active tokens can be revoked.
        assert args[0] == {"token_hash": "h", "revoked_at": None}
        assert args[1]["$set"]["replaced_by"] == "new-jti"
        assert kwargs["return_document"] == ReturnDocument.AFTER

    async def test_revoke_already_revoked_returns_none(
        self, repository: RefreshTokenRepository, collection: AsyncMock
    ) -> None:
        collection.find_one_and_update.return_value = None

        record = await repository.revoke_if_active("h", revoked_at=datetime.now(UTC))

        assert record is None


class TestFamilyRevocation:
    async def test_revoke_family_targets_active_records(
        self, repository: RefreshTokenRepository, collection: AsyncMock
    ) -> None:
        collection.update_many.return_value = MagicMock(modified_count=2)

        count = await repository.revoke_family(
            "fam-1", revoked_at=datetime.now(UTC), reuse_detected=True
        )

        assert count == 2
        args, _ = collection.update_many.await_args
        assert args[0] == {"family_id": "fam-1", "revoked_at": None}
        assert args[1]["$set"]["reuse_detected"] is True

    async def test_revoke_family_without_reuse_flag(
        self, repository: RefreshTokenRepository, collection: AsyncMock
    ) -> None:
        collection.update_many.return_value = MagicMock(modified_count=1)

        await repository.revoke_family("fam-1", revoked_at=datetime.now(UTC))

        args, _ = collection.update_many.await_args
        assert args[1]["$set"]["reuse_detected"] is False
