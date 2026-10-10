"""Phase 1.3.1 — Complaint repository tests.

Covers REPOSITORY requirements:
- create complaint
- stored complaint has expected fields
- complaint number persisted
- generated ID returned
- find by ID
- missing complaint returns None
- indexes match project requirements
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection

from app.repositories.complaint_repository import ComplaintRepository
from app.schemas.complaint import ComplaintStatus, ComplaintVisibility


@pytest.fixture
def mock_collection() -> AsyncMock:
    collection = AsyncMock(spec=AsyncCollection)
    return collection


@pytest.fixture
def mock_database(mock_collection: AsyncMock) -> AsyncMock:
    database = AsyncMock()
    database.__getitem__.return_value = mock_collection
    return database


@pytest.fixture
def repository(mock_database: AsyncMock) -> ComplaintRepository:
    return ComplaintRepository(mock_database)


VALID_COMPLAINT_ID = "507f1f77bcf86cd799439013"
VALID_USER_ID = "507f1f77bcf86cd799439011"
VALID_ORG_ID = "507f1f77bcf86cd799439012"
VALID_DEPT_ID = "507f1f77bcf86cd799439014"
VALID_CAT_ID = "507f1f77bcf86cd799439015"


def make_complaint_data(**overrides) -> dict[str, Any]:
    base = {
        "complaint_number": "CMP-2024-000001",
        "user_id": VALID_USER_ID,
        "organization_id": VALID_ORG_ID,
        "department_id": VALID_DEPT_ID,
        "category_id": VALID_CAT_ID,
        "title": "Large pothole on Main Street",
        "description": "Deep pothole causing vehicle damage near intersection",
        "status": ComplaintStatus.SUBMITTED.value,
        "visibility": ComplaintVisibility.PUBLIC.value,
        "location": {"type": "Point", "coordinates": [-73.9857, 40.7484]},
        "address": "Main St & 1st Ave",
        "assigned_to": None,
        "assigned_at": None,
        "completed_at": None,
        "rejected_at": None,
        "rejection_reason": None,
        "duplicate_of": None,
        "likes_count": 0,
        "community_engagement_score": 0,
        "age_score": 0.0,
        "organization_priority_boost": 0.0,
        "sla_deadline": None,
        "priority_score": 0.0,
        "severity_score": 3,
        "metadata": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return base


class TestComplaintRepositoryCreate:
    async def test_create_complaint_returns_id(
        self, repository: ComplaintRepository, mock_collection: AsyncMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.inserted_id = ObjectId(VALID_COMPLAINT_ID)
        mock_collection.insert_one.return_value = mock_result

        complaint_id = await repository.create(make_complaint_data())

        assert complaint_id == VALID_COMPLAINT_ID
        mock_collection.insert_one.assert_awaited_once()
        call_args = mock_collection.insert_one.await_args[0][0]
        assert call_args["complaint_number"] == "CMP-2024-000001"
        assert call_args["user_id"] == VALID_USER_ID
        assert call_args["status"] == ComplaintStatus.SUBMITTED.value

    async def test_create_duplicate_complaint_number_raises_conflict(
        self, repository: ComplaintRepository, mock_collection: AsyncMock
    ) -> None:
        from pymongo.errors import DuplicateKeyError

        mock_collection.insert_one.side_effect = DuplicateKeyError("E11000 duplicate key error complaint_number")

        with pytest.raises(Exception) as exc:
            await repository.create(make_complaint_data())

        assert "Complaint number already exists" in str(exc.value) or "Duplicate key error" in str(exc.value)


class TestComplaintRepositoryFindById:
    async def test_find_by_id_returns_complaint(
        self, repository: ComplaintRepository, mock_collection: AsyncMock
    ) -> None:
        complaint_data = make_complaint_data()
        complaint_data["_id"] = ObjectId(VALID_COMPLAINT_ID)
        mock_collection.find_one.return_value = complaint_data

        result = await repository.find_by_id(VALID_COMPLAINT_ID)

        assert result is not None
        assert result["_id"] == ObjectId(VALID_COMPLAINT_ID)
        assert result["complaint_number"] == "CMP-2024-000001"
        mock_collection.find_one.assert_awaited_once_with({"_id": ObjectId(VALID_COMPLAINT_ID)})

    async def test_find_by_id_invalid_id_returns_none(
        self, repository: ComplaintRepository, mock_collection: AsyncMock
    ) -> None:
        result = await repository.find_by_id("invalid-id")
        assert result is None
        mock_collection.find_one.assert_not_awaited()

    async def test_find_by_id_not_found_returns_none(
        self, repository: ComplaintRepository, mock_collection: AsyncMock
    ) -> None:
        mock_collection.find_one.return_value = None

        result = await repository.find_by_id(VALID_COMPLAINT_ID)

        assert result is None


class TestComplaintRepositoryFindByIdInOrganization:
    async def test_find_by_id_in_org_returns_complaint(
        self, repository: ComplaintRepository, mock_collection: AsyncMock
    ) -> None:
        complaint_data = make_complaint_data()
        complaint_data["_id"] = ObjectId(VALID_COMPLAINT_ID)
        mock_collection.find_one.return_value = complaint_data

        result = await repository.find_by_id_in_organization(VALID_COMPLAINT_ID, VALID_ORG_ID)

        assert result is not None
        assert result["_id"] == ObjectId(VALID_COMPLAINT_ID)
        mock_collection.find_one.assert_awaited_once_with(
            {"_id": ObjectId(VALID_COMPLAINT_ID), "organization_id": VALID_ORG_ID}
        )

    async def test_find_by_id_in_org_not_found_returns_none(
        self, repository: ComplaintRepository, mock_collection: AsyncMock
    ) -> None:
        mock_collection.find_one.return_value = None

        result = await repository.find_by_id_in_organization(VALID_COMPLAINT_ID, VALID_ORG_ID)

        assert result is None


class TestComplaintRepositoryFindByComplaintNumber:
    async def test_find_by_complaint_number_returns_complaint(
        self, repository: ComplaintRepository, mock_collection: AsyncMock
    ) -> None:
        complaint_data = make_complaint_data()
        complaint_data["_id"] = ObjectId(VALID_COMPLAINT_ID)
        mock_collection.find_one.return_value = complaint_data

        result = await repository.find_by_complaint_number("CMP-2024-000001")

        assert result is not None
        assert result["complaint_number"] == "CMP-2024-000001"
        mock_collection.find_one.assert_awaited_once_with({"complaint_number": "CMP-2024-000001"})

    async def test_find_by_complaint_number_not_found_returns_none(
        self, repository: ComplaintRepository, mock_collection: AsyncMock
    ) -> None:
        mock_collection.find_one.return_value = None

        result = await repository.find_by_complaint_number("CMP-2024-999999")

        assert result is None
