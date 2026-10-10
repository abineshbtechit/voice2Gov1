"""Unit tests for ComplaintTimelineUpdate schemas and ComplaintUpdateRepository (Phase 1.3.6)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId
from pydantic import ValidationError

from app.repositories.complaint_update_repository import ComplaintUpdateRepository, to_object_id
from app.schemas.complaint_update import (
    ComplaintTimelineUpdateCreateRequest,
    ComplaintTimelineUpdateResponse,
    UpdateType,
)


class TestComplaintTimelineUpdateSchema:
    def test_valid_progress_note(self) -> None:
        req = ComplaintTimelineUpdateCreateRequest(
            update_type=UpdateType.PROGRESS_NOTE,
            message="Repair crew has arrived on site.",
            images=["507f1f77bcf86cd799439016"],
            is_public=True,
        )
        assert req.update_type == UpdateType.PROGRESS_NOTE
        assert req.message == "Repair crew has arrived on site."
        assert req.images == ["507f1f77bcf86cd799439016"]
        assert req.is_public is True

    def test_default_values(self) -> None:
        req = ComplaintTimelineUpdateCreateRequest(
            message="Standard progress message"
        )
        assert req.update_type == UpdateType.PROGRESS_NOTE
        assert req.is_public is True
        assert req.images == []

    def test_blank_or_whitespace_message_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ComplaintTimelineUpdateCreateRequest(message="   ")

    def test_empty_message_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ComplaintTimelineUpdateCreateRequest(message="")

    def test_message_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ComplaintTimelineUpdateCreateRequest(message="a" * 2001)

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            ComplaintTimelineUpdateCreateRequest(
                message="Valid message",
                server_controlled_field="malicious_payload",  # type: ignore
            )

    def test_invalid_image_id_format_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ComplaintTimelineUpdateCreateRequest(
                message="Valid message",
                images=["invalid-non-hex-id"],
            )

    def test_response_schema_serialization(self) -> None:
        now = datetime.now(UTC)
        resp = ComplaintTimelineUpdateResponse(
            _id="507f1f77bcf86cd799439017",
            complaint_id="507f1f77bcf86cd799439013",
            organization_id="507f1f77bcf86cd799439012",
            department_id="507f1f77bcf86cd799439014",
            updated_by="507f1f77bcf86cd799439011",
            update_type=UpdateType.PROGRESS_NOTE,
            previous_status=None,
            new_status=None,
            message="Work in progress",
            images=["507f1f77bcf86cd799439016"],
            is_public=True,
            created_at=now,
        )
        assert resp.id == "507f1f77bcf86cd799439017"
        assert resp.complaint_id == "507f1f77bcf86cd799439013"
        assert resp.update_type == UpdateType.PROGRESS_NOTE


class TestComplaintUpdateRepository:
    def test_to_object_id_valid_and_invalid(self) -> None:
        valid_str = "507f1f77bcf86cd799439011"
        assert to_object_id(valid_str) == ObjectId(valid_str)
        assert to_object_id(ObjectId(valid_str)) == ObjectId(valid_str)
        assert to_object_id("invalid-id") is None
        assert to_object_id({"$ne": None}) is None

    @pytest.mark.asyncio
    async def test_create_update(self) -> None:
        db = MagicMock()
        coll = AsyncMock()
        db.__getitem__.return_value = coll
        coll.insert_one.return_value = MagicMock(inserted_id=ObjectId("507f1f77bcf86cd799439017"))

        repo = ComplaintUpdateRepository(db)
        doc = {
            "complaint_id": ObjectId("507f1f77bcf86cd799439013"),
            "department_id": ObjectId("507f1f77bcf86cd799439014"),
            "message": "Test",
        }
        uid = await repo.create(doc)
        assert uid == "507f1f77bcf86cd799439017"
        coll.insert_one.assert_awaited_once_with(doc)

    @pytest.mark.asyncio
    async def test_create_update_missing_department_id_rejected(self) -> None:
        db = MagicMock()
        repo = ComplaintUpdateRepository(db)
        doc = {"complaint_id": ObjectId("507f1f77bcf86cd799439013"), "message": "Test"}
        with pytest.raises(ValueError, match="department_id is required"):
            await repo.create(doc)

    @pytest.mark.asyncio
    async def test_find_by_id(self) -> None:
        db = MagicMock()
        coll = AsyncMock()
        db.__getitem__.return_value = coll
        coll.find_one.return_value = {"_id": ObjectId("507f1f77bcf86cd799439017"), "message": "Test"}

        repo = ComplaintUpdateRepository(db)
        found = await repo.find_by_id("507f1f77bcf86cd799439017")
        assert found is not None
        assert str(found["_id"]) == "507f1f77bcf86cd799439017"

    @pytest.mark.asyncio
    async def test_find_by_complaint(self) -> None:
        db = MagicMock()
        coll = MagicMock()
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.to_list = AsyncMock(return_value=[
            {"_id": ObjectId("507f1f77bcf86cd799439017"), "message": "Update 1"},
        ])
        coll.find.return_value = cursor
        db.__getitem__.return_value = coll

        repo = ComplaintUpdateRepository(db)
        res = await repo.find_by_complaint("507f1f77bcf86cd799439013", is_public_only=True)
        assert len(res) == 1
        coll.find.assert_called_once_with({
            "complaint_id": ObjectId("507f1f77bcf86cd799439013"),
            "is_public": True,
        })
