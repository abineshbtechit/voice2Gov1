"""Complaint image service (Phase 1.3.4).

Orchestrates the image-upload foundation: authorization, validation, storage
upload and metadata persistence. Business logic depends only on the storage
*abstraction*, never on a concrete backend.

Flow for an upload (all-or-nothing):

1. resolve the complaint under the caller's tenant/role scope (404 if not accessible)
2. authorize the image type against the complaint (403 if forbidden)
3. validate *every* file before any side effect (declared MIME, filename, size,
   magic bytes)
4. upload storage objects, compensating (deleting) on failure
5. persist metadata; if persistence fails, delete the uploaded objects

Progress/completion uploads depend on assignment semantics that are **not**
implemented in Phase 1.3.4. The service therefore uses the existing
``complaint.assigned_to`` field exactly as the authoritative storage
architecture prescribes: an organization staff member may only upload
progress/completion images when the complaint is assigned to them, while
organization admins are "authorized organization personnel". Until assignment
exists, staff uploads of such images fail closed with 403.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from io import BytesIO

from fastapi import UploadFile

from app.core.config import Settings
from app.exceptions.base import (
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.repositories.complaint_image_repository import (
    ComplaintImageRepository,
    to_object_id,
)
from app.repositories.complaint_repository import ComplaintRepository
from app.schemas.base import ObjectIdStr
from app.schemas.complaint_image import (
    ComplaintImageDeleteResponse,
    ComplaintImageListData,
    ComplaintImageListResponse,
    ComplaintImageResponse,
    ComplaintImageUploadResponse,
    ImageType,
)
from app.schemas.user import UserResponse
from app.storage.base import StorageProvider
from app.storage.keys import build_storage_key
from app.utils.file_validation import FileValidator, read_bounded

logger = logging.getLogger(__name__)

_COMPLAINT_NOT_FOUND = "Complaint not found"

_STAFF_ROLES = ("organization_staff", "organization_admin")


class ImageService:
    """Upload, list and soft-delete complaint image metadata."""

    def __init__(
        self,
        image_repo: ComplaintImageRepository,
        complaint_repo: ComplaintRepository,
        storage: StorageProvider,
        validator: FileValidator,
        *,
        max_images_per_request: int = 5,
        signed_url_expiry_seconds: int = 3600,
    ) -> None:
        self._image_repo = image_repo
        self._complaint_repo = complaint_repo
        self._storage = storage
        self._validator = validator
        self._max_images_per_request = max_images_per_request
        self._signed_url_expiry = signed_url_expiry_seconds

    def _role_of(self, user: UserResponse) -> str:
        return getattr(user.role, "value", None) or str(user.role)

    # ------------------------------------------------------------------ upload

    async def upload_images(
        self,
        complaint_id: str,
        current_user: UserResponse,
        files: list[UploadFile],
        image_type: ImageType,
    ) -> ComplaintImageUploadResponse:
        """Validate and store one or more images for a complaint."""
        if not files:
            raise ValidationException(
                "At least one image file is required",
                errors=[
                    {
                        "field": "files",
                        "message": "No image files were provided",
                        "code": "VALIDATION_ERROR",
                    }
                ],
            )
        if len(files) > self._max_images_per_request:
            raise ValidationException(
                f"At most {self._max_images_per_request} images may be uploaded per request",
                errors=[
                    {
                        "field": "files",
                        "message": (
                            f"Received {len(files)} files; the maximum is "
                            f"{self._max_images_per_request}"
                        ),
                        "code": "VALIDATION_ERROR",
                    }
                ],
            )

        # 1. Resolve + authorize the complaint before touching any file content.
        complaint = await self._get_accessible_complaint(complaint_id, current_user)
        self._authorize_upload(complaint, current_user, image_type)

        # 2. Validate every file up-front (no side effects) — atomic reject.
        prepared: list[tuple[str, str, bytes]] = []
        for upload in files:
            declared_mime = self._validator.validate_declared_mime(
                upload.content_type, image_type
            )
            safe_name = self._validator.validate_filename(upload.filename)
            content = await read_bounded(upload, self._validator.max_file_size(image_type))
            self._validator.validate_content(content, declared_mime)
            prepared.append((safe_name, declared_mime, content))

        # 3. Upload storage objects with compensating cleanup on failure.
        uploads = []
        try:
            for safe_name, mime, content in prepared:
                key = build_storage_key(image_type, complaint_id, safe_name)
                result = await self._storage.upload(
                    BytesIO(content),
                    key,
                    mime,
                    metadata={
                        "complaint_id": str(complaint_id),
                        "uploaded_by": str(current_user.id),
                        "image_type": image_type.value,
                    },
                )
                uploads.append(result)
        except Exception:
            await self._cleanup_storage([result.storage_key for result in uploads])
            raise

        # 4. Persist metadata; roll back storage objects if persistence fails.
        now = datetime.now(UTC)
        complaint_object_id = to_object_id(complaint_id)
        uploaded_by = to_object_id(current_user.id)
        records = [
            {
                "complaint_id": complaint_object_id if complaint_object_id is not None
                else complaint_id,
                "image_type": image_type.value,
                "storage_path": result.storage_key,
                "original_filename": safe_name,
                "mime_type": mime,
                "file_size": result.file_size,
                "width": None,
                "height": None,
                "checksum": result.checksum,
                "uploaded_by": uploaded_by if uploaded_by is not None else str(current_user.id),
                "is_deleted": False,
                "created_at": now,
            }
            for (safe_name, mime, _content), result in zip(prepared, uploads, strict=True)
        ]
        try:
            image_ids = await self._image_repo.create_many(records)
        except Exception:
            await self._cleanup_storage([result.storage_key for result in uploads])
            raise

        # 5. Build the safe response (signed URLs only).
        images = [
            ComplaintImageResponse(
                id=ObjectIdStr(image_id),
                image_type=image_type,
                url=await self._storage.generate_presigned_url(
                    result.storage_key, self._signed_url_expiry
                ),
                file_size=result.file_size,
                mime_type=mime,
                created_at=now,
            )
            for image_id, (_safe_name, mime, _content), result in zip(
                image_ids, prepared, uploads, strict=True
            )
        ]
        return ComplaintImageUploadResponse(
            success=True, message="Images uploaded", data=ComplaintImageListData(images=images)
        )

    # -------------------------------------------------------------------- list

    async def list_images(
        self, complaint_id: str, current_user: UserResponse
    ) -> ComplaintImageListResponse:
        """List a complaint's visible images with signed URLs."""
        await self._get_accessible_complaint(complaint_id, current_user)
        records = await self._image_repo.find_by_complaint(complaint_id)
        images = [
            ComplaintImageResponse(
                id=ObjectIdStr(str(record["_id"])),
                image_type=ImageType(str(record["image_type"])),
                url=await self._storage.generate_presigned_url(
                    record["storage_path"], self._signed_url_expiry
                ),
                file_size=int(record["file_size"]),
                mime_type=str(record["mime_type"]),
                created_at=record["created_at"],
            )
            for record in records
        ]
        return ComplaintImageListResponse(
            success=True, message="Images retrieved", data=ComplaintImageListData(images=images)
        )

    # ------------------------------------------------------------------ delete

    async def delete_image(
        self, complaint_id: str, image_id: str, current_user: UserResponse
    ) -> ComplaintImageDeleteResponse:
        """Soft-delete an image. Only the uploader may delete their image."""
        await self._get_accessible_complaint(complaint_id, current_user)
        image = await self._image_repo.find_by_id(image_id, complaint_id)
        if image is None:
            raise NotFoundException("Image not found")
        if str(image.get("uploaded_by")) != str(current_user.id):
            raise ForbiddenException(
                "Only the uploader can delete this image", error_code="FORBIDDEN"
            )
        # Soft delete only — physical deletion follows the documented retention
        # policy via a future cleanup job (not implemented in this phase).
        deleted = await self._image_repo.soft_delete(image_id, complaint_id)
        if not deleted:
            raise NotFoundException("Image not found")
        return ComplaintImageDeleteResponse(
            success=True,
            message="Image deleted",
            data={"id": str(image_id), "is_deleted": True},
        )

    # ----------------------------------------------------------------- helpers

    async def _get_accessible_complaint(
        self, complaint_id: str, current_user: UserResponse
    ) -> dict[str, object]:
        """Resolve a complaint under the caller's role/tenant scope.

        Mirrors the complaint read authorization so image access inherits it.
        Raises ``NotFoundException`` (404) when the complaint does not exist or
        is not accessible, so cross-tenant probes do not leak existence.
        """
        role = self._role_of(current_user)
        complaint: dict[str, object] | None = None
        if role == "admin":
            complaint = await self._complaint_repo.find_by_id_for_admin(complaint_id)
        elif role in _STAFF_ROLES:
            if not current_user.organization_id:
                raise NotFoundException(_COMPLAINT_NOT_FOUND, error_code="COMPLAINT_NOT_FOUND")
            organization_id = str(current_user.organization_id)
            if role == "organization_admin":
                complaint = await self._complaint_repo.find_by_id_in_organization(
                    complaint_id, organization_id
                )
            else:
                if not current_user.department_id:
                    raise NotFoundException(
                        _COMPLAINT_NOT_FOUND, error_code="COMPLAINT_NOT_FOUND"
                    )
                complaint = await self._complaint_repo.find_by_id_for_organization_staff(
                    complaint_id, organization_id, str(current_user.department_id)
                )
        else:
            complaint = await self._complaint_repo.find_by_id_for_user(
                complaint_id, str(current_user.id)
            )

        if complaint is None:
            raise NotFoundException(_COMPLAINT_NOT_FOUND, error_code="COMPLAINT_NOT_FOUND")
        return complaint

    def _authorize_upload(
        self, complaint: dict[str, object], current_user: UserResponse, image_type: ImageType
    ) -> None:
        """Authorize an upload for ``image_type`` against ``complaint``."""
        role = self._role_of(current_user)

        if image_type == ImageType.EVIDENCE:
            # Evidence is citizen-owned: only the complaint owner may upload.
            if str(complaint.get("user_id")) != str(current_user.id):
                raise ForbiddenException(
                    "Only the complaint owner can upload evidence images",
                    error_code="FORBIDDEN",
                )
            return

        # progress / completion evidence — organization personnel only.
        if role not in (*_STAFF_ROLES, "admin"):
            raise ForbiddenException(
                "Only authorized organization personnel can upload "
                "progress/completion images",
                error_code="FORBIDDEN",
            )

        # Tenant boundary (defense in depth; repository scoping also applies).
        if role != "admin" and str(complaint.get("organization_id")) != str(
            current_user.organization_id
        ):
            raise ForbiddenException(
                "Access denied: complaint belongs to another organization",
                error_code="ORG_ISOLATION_VIOLATION",
            )

        # Assignment dependency (Phase 1.3.4 does not implement assignment):
        # staff must be the assignee; org admins are authorized personnel.
        assigned_to = complaint.get("assigned_to")
        if role not in ("organization_admin", "admin") and str(assigned_to) != str(
            current_user.id
        ):
            raise ForbiddenException(
                "Complaint is not assigned to this user",
                error_code="FORBIDDEN",
            )

    async def _cleanup_storage(self, keys: list[str]) -> None:
        """Best-effort removal of already-uploaded objects (compensation)."""
        for key in keys:
            try:
                await self._storage.delete(key)
            except Exception:  # pragma: no cover - cleanup is best-effort
                logger.warning("Failed to clean up storage object after error", extra={"key": key})


def build_image_service(
    image_repo: ComplaintImageRepository,
    complaint_repo: ComplaintRepository,
    storage: StorageProvider,
    settings: Settings,
) -> ImageService:
    """Construct an :class:`ImageService` from application settings."""
    return ImageService(
        image_repo,
        complaint_repo,
        storage,
        FileValidator.from_settings(settings),
        max_images_per_request=settings.max_images_per_request,
        signed_url_expiry_seconds=settings.storage_signed_url_expiry_seconds,
    )
