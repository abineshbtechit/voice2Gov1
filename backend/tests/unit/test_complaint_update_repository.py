"""Phase 1.3.3 — Complaint update repository tests.

Covers REPOSITORY requirements:
- update by user (citizen owner)
- update in organization (org staff/admin)
- missing complaint returns False
- ownership scope enforced
- organization scope enforced
- updated_at is set
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection

from app.repositories.complaint_repository import ComplaintRepository
from app.schemas.complaint import ComplaintStatus


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


def make_complaint_data(**overrides) -> dict[str, Any]:
    base = {
        "_id": ObjectId(VALID_COMPLAINT_ID),
        "complaint_number": "CMP-2024-000001",
        "user_id": VALID_USER_ID,
        "organization_id": VALID_ORG_ID,
        "department_id": VALID_DEPT_ID,
        "category_id": "507f1f77bcf86cd799439015",
        "title": "Large pothole on Main Street",
        "description": "Deep pothole causing vehicle damage near intersection",
        "status": ComplaintStatus.SUBMITTED.value,
        "visibility": "public",
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


class TestComplaintRepositoryUpdateByUser:
    async def test_update_by_user_success(
        self, repository: ComplaintRepository, mock_collection: AsyncMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_collection.update_one.return_value = mock_result

        complaint_data = make_complaint_data()
        mock_collection.find_one.return_value = complaint_data

        updated = await repository.update_by_user(
            VALID_COMPLAINT_ID, VALID_USER_ID, {"title": "Updated title"}
        )

        assert updated is True
        mock_collection.update_one.assert_awaited_once()
        call_args = mock_collection.update_one.await_args
        query = call_args[0][0]
        update_doc = call_args[0][1]

        assert query["_id"] == ObjectId(VALID_COMPLAINT_ID)
        assert query["user_id"] == VALID_USER_ID
        assert query["status"] == "SUBMITTED"
        assert update_doc["$set"]["title"] == "Updated title"
        assert "updated_at" in update_doc["$set"]

    async def test_update_by_user_not_found_wrong_user(
        self, repository: ComplaintRepository, mock_collection: AsyncMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.modified_count = 0
        mock_collection.update_one.return_value = mock_result

        updated = await repository.update_by_user(
            VALID_COMPLAINT_ID, "different_user_id", {"title": "Updated title"}
        )

        assert updated is False

    async def test_update_by_user_not_found_wrong_status(
        self, repository: ComplaintRepository, mock_collection: AsyncMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.modified_count = 0
        mock_collection.update_one.return_value = mock_result

        updated = await repository.update_by_user(
            VALID_COMPLAINT_ID, VALID_USER_ID, {"title": "Updated title"}
        )

        assert updated is False

    async def test_update_by_user_invalid_id(
        self, repository: ComplaintRepository, mock_collection: AsyncMock
    ) -> None:
        updated = await repository.update_by_user(
            "invalid-id", VALID_USER_ID, {"title": "Updated title"}
        )

        assert updated is False
        mock_collection.update_one.assert_not_awaited()


class TestComplaintRepositoryUpdateInOrganization:
    async def test_update_in_organization_success(
        self, repository: ComplaintRepository, mock_collection: AsyncMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_collection.update_one.return_value = mock_result

        complaint_data = make_complaint_data()
        mock_collection.find_one.return_value = complaint_data

        updated = await repository.update_in_organization(
            VALID_COMPLAINT_ID, VALID_ORG_ID, {"title": "Updated title"}
        )

        assert updated is True
        mock_collection.update_one.assert_awaited_once()
        call_args = mock_collection.update_one.await_args
        query = call_args[0][0]
        update_doc = call_args[0][1]

        assert query["_id"] == ObjectId(VALID_COMPLAINT_ID)
        assert query["organization_id"] == VALID_ORG_ID
        assert update_doc["$set"]["title"] == "Updated title"
        assert "updated_at" in update_doc["$set"]

    async def test_update_in_organization_not_found_wrong_org(
        self, repository: ComplaintRepository, mock_collection: AsyncMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.modified_count = 0
        mock_collection.update_one.return_value = mock_result

        updated = await repository.update_in_organization(
            VALID_COMPLAINT_ID, "different_org_id", {"title": "Updated title"}
        )

        assert updated is False

    async def test_update_in_organization_invalid_id(
        self, repository: ComplaintRepository, mock_collection: AsyncMock
    ) -> None:
        updated = await repository.update_in_organization(
            "invalid-id", VALID_ORG_ID, {"title": "Updated title"}
        )

        assert updated is False
        mock_collection.update_one.assert_not_awaited()
