"""Complaint image metadata schemas (Phase 1.3.4).

Reconciliation notes (authoritative sources):

* ``image_type`` — the SRS conceptually refers to ``complaint_evidence``,
  ``progress_evidence`` and ``completion_evidence``. The authoritative database
  schema (``database-schema.md`` §6) and the file-storage/API contract both
  persist and expose the shorter canonical values below. There is a **single**
  enum: the external/API representation is identical to the internal/database
  representation (``evidence`` | ``progress`` | ``completion``).
* Field names follow the authoritative ``complaint_images`` collection schema:
  ``storage_path`` (the storage key) and ``original_filename`` (the sanitized
  original name). ``file_url`` is *not* persisted because image URLs are
  short-lived signed URLs generated on read; ``caption`` is not part of the
  authoritative schema and is therefore not persisted.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from app.schemas.base import BaseSchema, ObjectIdStr


class ImageType(StrEnum):
    """Canonical complaint image type values (API == database)."""

    EVIDENCE = "evidence"
    PROGRESS = "progress"
    COMPLETION = "completion"


class ComplaintImageInDB(BaseSchema):
    """A ``complaint_images`` document as persisted in MongoDB."""

    id: ObjectIdStr = Field(..., alias="_id", description="Image metadata ID")
    complaint_id: ObjectIdStr = Field(..., description="Owning complaint ID")
    image_type: ImageType = Field(..., description="Image classification")
    storage_path: str = Field(..., description="Storage key in the object store")
    original_filename: str = Field(..., description="Sanitized original filename")
    mime_type: str = Field(..., description="Validated MIME type")
    file_size: int = Field(..., ge=0, description="Size in bytes")
    width: int | None = Field(default=None, description="Image width (if known)")
    height: int | None = Field(default=None, description="Image height (if known)")
    checksum: str = Field(..., description="SHA-256 hex digest (integrity, internal)")
    uploaded_by: ObjectIdStr = Field(..., description="Uploader user ID")
    is_deleted: bool = Field(default=False, description="Soft-delete flag")
    created_at: datetime = Field(..., description="Upload timestamp")


class ComplaintImageResponse(BaseSchema):
    """Public API representation of an uploaded image (contract-defined fields only)."""

    id: ObjectIdStr
    image_type: ImageType
    url: str = Field(..., description="Time-limited signed access URL")
    file_size: int
    mime_type: str
    created_at: datetime


class ComplaintImageListData(BaseSchema):
    images: list[ComplaintImageResponse] = Field(default_factory=list)


class ComplaintImageUploadResponse(BaseSchema):
    success: bool = True
    message: str
    data: ComplaintImageListData


class ComplaintImageListResponse(BaseSchema):
    success: bool = True
    message: str
    data: ComplaintImageListData


class ComplaintImageDeleteResponse(BaseSchema):
    success: bool = True
    message: str
    data: dict[str, Any]
