"""Phase 1.3.4 — Complaint image schema unit tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.complaint_image import (
    ComplaintImageDeleteResponse,
    ComplaintImageInDB,
    ComplaintImageListData,
    ComplaintImageListResponse,
    ComplaintImageResponse,
    ComplaintImageUploadResponse,
    ImageType,
)

VALID_IMAGE = {
    "_id": "507f1f77bcf86cd799439016",
    "complaint_id": "507f1f77bcf86cd799439013",
    "image_type": "evidence",
    "storage_path": "evidence/2024/01/15/507f1f77bcf86cd799439013/abc_photo.jpg",
    "original_filename": "photo.jpg",
    "mime_type": "image/jpeg",
    "file_size": 2048,
    "width": None,
    "height": None,
    "checksum": "a" * 64,
    "uploaded_by": "507f1f77bcf86cd799439011",
    "is_deleted": False,
    "created_at": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
}


class TestImageType:
    def test_canonical_values(self) -> None:
        assert ImageType.EVIDENCE.value == "evidence"
        assert ImageType.PROGRESS.value == "progress"
        assert ImageType.COMPLETION.value == "completion"

    def test_external_and_internal_representation_match(self) -> None:
        # The API value is the DB value (single enum, no divergence).
        for image_type in ImageType:
            assert ImageType(image_type.value) == image_type

    def test_rejects_unknown_value(self) -> None:
        with pytest.raises(ValueError):
            ImageType("complaint_evidence")


class TestComplaintImageInDB:
    def test_valid_document(self) -> None:
        model = ComplaintImageInDB(**VALID_IMAGE)
        assert model.id == VALID_IMAGE["_id"]
        assert model.image_type == ImageType.EVIDENCE
        assert model.storage_path == VALID_IMAGE["storage_path"]
        assert model.original_filename == "photo.jpg"
        assert model.is_deleted is False

    def test_required_fields_enforced(self) -> None:
        with pytest.raises(ValidationError):
            ComplaintImageInDB(_id=VALID_IMAGE["_id"])

    def test_invalid_object_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ComplaintImageInDB(**{**VALID_IMAGE, "complaint_id": "not-an-object-id"})

    def test_invalid_image_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ComplaintImageInDB(**{**VALID_IMAGE, "image_type": "avatar"})

    def test_negative_file_size_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ComplaintImageInDB(**{**VALID_IMAGE, "file_size": -1})

    def test_is_deleted_defaults_false(self) -> None:
        payload = {k: v for k, v in VALID_IMAGE.items() if k != "is_deleted"}
        assert ComplaintImageInDB(**payload).is_deleted is False

    def test_timestamps_required(self) -> None:
        payload = {k: v for k, v in VALID_IMAGE.items() if k != "created_at"}
        with pytest.raises(ValidationError):
            ComplaintImageInDB(**payload)


class TestComplaintImageResponse:
    def _response(self) -> ComplaintImageResponse:
        return ComplaintImageResponse(
            id=VALID_IMAGE["_id"],
            image_type=ImageType.EVIDENCE,
            url="https://storage/evidence/a.jpg?expires=1&signature=abc",
            file_size=2048,
            mime_type="image/jpeg",
            created_at=datetime(2024, 1, 15, tzinfo=UTC),
        )

    def test_contract_fields_present(self) -> None:
        data = self._response().model_dump()
        assert set(data) == {"id", "image_type", "url", "file_size", "mime_type", "created_at"}

    def test_internal_fields_not_exposed(self) -> None:
        data = self._response().model_dump()
        for internal in ("checksum", "storage_path", "width", "height", "is_deleted", "uploaded_by"):
            assert internal not in data

    def test_url_required(self) -> None:
        with pytest.raises(ValidationError):
            ComplaintImageResponse(
                id=VALID_IMAGE["_id"],
                image_type=ImageType.EVIDENCE,
                file_size=1,
                mime_type="image/jpeg",
                created_at=datetime(2024, 1, 15, tzinfo=UTC),
            )


class TestResponseWrappers:
    def test_upload_response_envelope(self) -> None:
        response = ComplaintImageUploadResponse(
            success=True,
            message="Images uploaded",
            data=ComplaintImageListData(
                images=[
                    ComplaintImageResponse(
                        id=VALID_IMAGE["_id"],
                        image_type=ImageType.EVIDENCE,
                        url="memory://k",
                        file_size=1,
                        mime_type="image/jpeg",
                        created_at=datetime(2024, 1, 15, tzinfo=UTC),
                    )
                ]
            ),
        )
        dumped = response.model_dump()
        assert dumped["success"] is True
        assert dumped["data"]["images"][0]["image_type"] == "evidence"

    def test_list_response_envelope(self) -> None:
        response = ComplaintImageListResponse(
            success=True, message="Images retrieved", data=ComplaintImageListData(images=[])
        )
        assert response.data.images == []

    def test_delete_response_envelope(self) -> None:
        response = ComplaintImageDeleteResponse(
            success=True, message="Image deleted", data={"id": VALID_IMAGE["_id"], "is_deleted": True}
        )
        assert response.data["is_deleted"] is True
