"""Phase 1.2.1 — user repository tests.

Covers the REPOSITORY requirements:
- create user
- find by id / email / phone
- duplicate email / phone handling (unique index -> ConflictException)
- index definitions match the authoritative Database Design SRS
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.exceptions.base import ConflictException
from app.repositories.user_repository import UserRepository

VALID_ID = "507f1f77bcf86cd799439011"


@pytest.fixture
def collection() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def repository(collection: AsyncMock) -> UserRepository:
    database = MagicMock()
    database.__getitem__.return_value = collection
    return UserRepository(database)


class TestCreate:
    async def test_create_user_returns_id(self, repository: UserRepository, collection: AsyncMock) -> None:
        inserted = ObjectId(VALID_ID)
        collection.insert_one.return_value = MagicMock(inserted_id=inserted)

        user_id = await repository.create({"email": "a@b.com", "phone": "+15551234567"})

        assert user_id == VALID_ID
        collection.insert_one.assert_awaited_once()

    async def test_duplicate_email_raises_conflict(
        self, repository: UserRepository, collection: AsyncMock
    ) -> None:
        collection.insert_one.side_effect = DuplicateKeyError(
            'E11000 duplicate key error collection: voice2gov.users '
            'index: idx_users_email dup key: { email: "a@b.com" }'
        )

        with pytest.raises(ConflictException) as exc:
            await repository.create({"email": "a@b.com"})

        assert "Email already registered" in str(exc.value.message)

    async def test_duplicate_phone_raises_conflict(
        self, repository: UserRepository, collection: AsyncMock
    ) -> None:
        collection.insert_one.side_effect = DuplicateKeyError(
            'E11000 duplicate key error collection: voice2gov.users '
            'index: idx_users_phone dup key: { phone: "+15551234567" }'
        )

        with pytest.raises(ConflictException) as exc:
            await repository.create({"phone": "+15551234567"})

        assert "Phone number already registered" in str(exc.value.message)

    async def test_unknown_duplicate_key_raises_generic_conflict(
        self, repository: UserRepository, collection: AsyncMock
    ) -> None:
        collection.insert_one.side_effect = DuplicateKeyError("duplicate key error")

        with pytest.raises(ConflictException) as exc:
            await repository.create({})

        assert "Duplicate key error" in str(exc.value.message)


class TestFind:
    async def test_find_by_id(self, repository: UserRepository, collection: AsyncMock) -> None:
        document = {"_id": ObjectId(VALID_ID), "email": "a@b.com"}
        collection.find_one.return_value = document

        result = await repository.find_by_id(VALID_ID)

        assert result == document
        collection.find_one.assert_awaited_once_with({"_id": ObjectId(VALID_ID)})

    async def test_find_by_id_invalid_returns_none(
        self, repository: UserRepository, collection: AsyncMock
    ) -> None:
        result = await repository.find_by_id("not-an-object-id")

        assert result is None
        collection.find_one.assert_not_awaited()

    async def test_find_by_email_is_case_insensitive(
        self, repository: UserRepository, collection: AsyncMock
    ) -> None:
        collection.find_one.return_value = {"email": "a@b.com"}

        result = await repository.find_by_email("A@B.COM")

        assert result == {"email": "a@b.com"}
        collection.find_one.assert_awaited_once_with({"email": "a@b.com"})

    async def test_find_by_phone(self, repository: UserRepository, collection: AsyncMock) -> None:
        collection.find_one.return_value = {"phone": "+15551234567"}

        result = await repository.find_by_phone("+15551234567")

        assert result == {"phone": "+15551234567"}
        collection.find_one.assert_awaited_once_with({"phone": "+15551234567"})


class TestExists:
    async def test_exists_by_email_true(
        self, repository: UserRepository, collection: AsyncMock
    ) -> None:
        collection.count_documents.return_value = 1

        assert await repository.exists_by_email("A@B.com") is True
        collection.count_documents.assert_awaited_once_with({"email": "a@b.com"}, limit=1)

    async def test_exists_by_email_false(
        self, repository: UserRepository, collection: AsyncMock
    ) -> None:
        collection.count_documents.return_value = 0

        assert await repository.exists_by_email("a@b.com") is False

    async def test_exists_by_phone(
        self, repository: UserRepository, collection: AsyncMock
    ) -> None:
        collection.count_documents.return_value = 1

        assert await repository.exists_by_phone("+15551234567") is True
        collection.count_documents.assert_awaited_once_with({"phone": "+15551234567"}, limit=1)


class TestIndexDefinitions:
    """The repository must define exactly the SRS users indexes."""

    async def test_indexes_match_srs(
        self, repository: UserRepository, collection: AsyncMock
    ) -> None:
        await repository.create_indexes()

        names = {c.kwargs["name"] for c in collection.create_index.await_args_list}
        assert names == {
            "idx_users_email",
            "idx_users_phone",
            "idx_users_organization_id",
            "idx_users_department_id",
            "idx_users_role",
            "idx_users_org_role",
        }

    async def test_email_and_phone_are_unique_sparse(
        self, repository: UserRepository, collection: AsyncMock
    ) -> None:
        await repository.create_indexes()

        by_name = {c.kwargs["name"]: c for c in collection.create_index.await_args_list}
        for index_name in ("idx_users_email", "idx_users_phone"):
            assert by_name[index_name].kwargs["unique"] is True
            assert by_name[index_name].kwargs["sparse"] is True

    async def test_status_index_is_not_defined(
        self, repository: UserRepository, collection: AsyncMock
    ) -> None:
        """``status`` is not an SRS users index and must not be invented."""
        await repository.create_indexes()

        names = {c.kwargs["name"] for c in collection.create_index.await_args_list}
        assert "idx_users_status" not in names
