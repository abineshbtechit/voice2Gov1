"""Phase 1.3.4 — Complaint image service unit tests."""

from datetime import UTC, datetime
from io import BytesIO

import pytest
from starlette.datastructures import Headers, UploadFile

from app.exceptions.base import (
    FileTooLargeException,
    ForbiddenException,
    InvalidFilenameException,
    InvalidFileTypeException,
    NotFoundException,
    StorageException,
    ValidationException,
)
from app.schemas.complaint_image import ImageType
from app.schemas.user import UserResponse
from app.services.image_service import ImageService
from app.storage.base import StorageProvider, UploadResult
from app.storage.memory import InMemoryStorageProvider
from app.utils.file_validation import FileValidator
from tests.fakes import FakeComplaintImageRepository, FakeComplaintLookup

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 32
HEIC = b"\x00\x00\x00\x20ftypheic" + b"\x00" * 32

CID_A = "507f1f77bcf86cd799439013"
CID_B = "507f1f77bcf86cd799439099"
CITIZEN_A = "507f1f77bcf86cd799439011"
CITIZEN_B = "507f1f77bcf86cd799439012"
ORG_A = "507f1f77bcf86cd799439021"
ORG_B = "507f1f77bcf86cd799439022"
DEPT_A = "507f1f77bcf86cd799439031"
DEPT_B = "507f1f77bcf86cd799439032"
STAFF_A = "507f1f77bcf86cd799439041"
ORG_ADMIN_A = "507f1f77bcf86cd799439042"
STAFF_B = "507f1f77bcf86cd799439043"
PLATFORM_ADMIN = "507f1f77bcf86cd799439044"


def make_user(
    user_id: str,
    role: str,
    organization_id: str | None = None,
    department_id: str | None = None,
) -> UserResponse:
    now = datetime.now(UTC)
    return UserResponse(
        id=user_id,
        email="user@example.com",
        phone="+15551234567",
        full_name="Test User",
        role=role,
        status="active",
        organization_id=organization_id,
        department_id=department_id,
        avatar_url=None,
        is_verified=True,
        created_at=now,
        updated_at=now,
    )


def upload_file(data: bytes, filename: str = "photo.jpg", mime: str = "image/jpeg") -> UploadFile:
    return UploadFile(
        file=BytesIO(data),
        filename=filename,
        headers=Headers({"content-type": mime}),
    )


def make_validator(*, max_mb: int = 1) -> FileValidator:
    return FileValidator(
        max_file_sizes_mb={
            ImageType.EVIDENCE: max_mb,
            ImageType.PROGRESS: max_mb,
            ImageType.COMPLETION: max_mb,
        }
    )


class FailingStorage(StorageProvider):
    """Storage provider whose upload always fails."""

    def __init__(self, fail_on_call: int = 0) -> None:
        self._mem = InMemoryStorageProvider()
        self._fail_on_call = fail_on_call
        self._calls = 0
        self.deleted: list[str] = []

    async def upload(
        self,
        file: BytesIO,
        key: str,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        if self._calls >= self._fail_on_call:
            self._calls += 1
            raise StorageException("boom")
        self._calls += 1
        return await self._mem.upload(file, key, content_type, metadata)

    async def download(self, key: str) -> BytesIO:
        return await self._mem.download(key)

    async def delete(self, key: str) -> bool:
        self.deleted.append(key)
        return await self._mem.delete(key)

    async def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        return await self._mem.generate_presigned_url(key, expires_in)

    async def exists(self, key: str) -> bool:
        return await self._mem.exists(key)


class FailingRepository(FakeComplaintImageRepository):
    """Fake repository whose ``create_many`` always fails."""

    async def create_many(self, records):  # type: ignore[override]
        raise StorageException("metadata write failed")


def build_service(
    *,
    storage: StorageProvider | None = None,
    image_repo: FakeComplaintImageRepository | None = None,
    validator: FileValidator | None = None,
) -> tuple[ImageService, FakeComplaintLookup, FakeComplaintImageRepository, InMemoryStorageProvider]:
    lookup = FakeComplaintLookup()
    repo = image_repo or FakeComplaintImageRepository()
    store = storage or InMemoryStorageProvider()
    service = ImageService(
        repo,  # type: ignore[arg-type]
        lookup,  # type: ignore[arg-type]
        store,
        validator or make_validator(),
        max_images_per_request=5,
    )
    return service, lookup, repo, store  # type: ignore[return-value]


def seed_complaint(
    lookup: FakeComplaintLookup,
    complaint_id: str = CID_A,
    user_id: str = CITIZEN_A,
    organization_id: str = ORG_A,
    department_id: str = DEPT_A,
    assigned_to: str | None = None,
) -> str:
    return lookup.seed(
        complaint_id,
        user_id=user_id,
        organization_id=organization_id,
        department_id=department_id,
        assigned_to=assigned_to,
        status="SUBMITTED",
    )


class TestEvidenceAuthorization:
    async def test_owner_can_upload_evidence(self) -> None:
        service, lookup, repo, _ = build_service()
        seed_complaint(lookup)
        user = make_user(CITIZEN_A, "citizen")
        response = await service.upload_images(
            CID_A, user, [upload_file(JPEG)], ImageType.EVIDENCE
        )
        assert response.success is True
        assert len(response.data.images) == 1
        assert response.data.images[0].image_type == ImageType.EVIDENCE
        assert len(repo.images) == 1

    async def test_non_owner_citizen_denied(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup)
        user = make_user(CITIZEN_B, "citizen")
        with pytest.raises(NotFoundException):
            await service.upload_images(CID_A, user, [upload_file(JPEG)], ImageType.EVIDENCE)

    async def test_org_admin_cannot_upload_evidence_to_citizen_complaint(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup)
        user = make_user(ORG_ADMIN_A, "organization_admin", ORG_A)
        with pytest.raises(ForbiddenException):
            await service.upload_images(CID_A, user, [upload_file(JPEG)], ImageType.EVIDENCE)

    async def test_platform_admin_cannot_upload_evidence_to_other_complaint(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup)
        user = make_user(PLATFORM_ADMIN, "admin")
        with pytest.raises(ForbiddenException):
            await service.upload_images(CID_A, user, [upload_file(JPEG)], ImageType.EVIDENCE)

    async def test_missing_complaint_returns_404(self) -> None:
        service, _, _, _ = build_service()
        user = make_user(CITIZEN_A, "citizen")
        with pytest.raises(NotFoundException) as exc:
            await service.upload_images("507f1f77bcf86cd7994390ff", user, [upload_file(JPEG)], ImageType.EVIDENCE)
        assert exc.value.error_code == "COMPLAINT_NOT_FOUND"


class TestProgressCompletionAuthorization:
    async def test_assigned_staff_can_upload_progress(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup, assigned_to=STAFF_A)
        user = make_user(STAFF_A, "organization_staff", ORG_A, DEPT_A)
        response = await service.upload_images(
            CID_A, user, [upload_file(PNG, mime="image/png")], ImageType.PROGRESS
        )
        assert response.data.images[0].image_type == ImageType.PROGRESS

    async def test_unassigned_staff_denied_progress(self) -> None:
        """Assignment is not implemented in Phase 1.3.4, so this fails closed."""
        service, lookup, _, _ = build_service()
        seed_complaint(lookup, assigned_to=None)
        user = make_user(STAFF_A, "organization_staff", ORG_A, DEPT_A)
        with pytest.raises(ForbiddenException):
            await service.upload_images(CID_A, user, [upload_file(PNG)], ImageType.PROGRESS)

    async def test_org_admin_can_upload_completion(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup, assigned_to=None)
        user = make_user(ORG_ADMIN_A, "organization_admin", ORG_A)
        response = await service.upload_images(
            CID_A, user, [upload_file(PNG, mime="image/png")], ImageType.COMPLETION
        )
        assert response.data.images[0].image_type == ImageType.COMPLETION

    async def test_platform_admin_can_upload_completion(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup)
        user = make_user(PLATFORM_ADMIN, "admin")
        response = await service.upload_images(
            CID_A, user, [upload_file(PNG, mime="image/png")], ImageType.COMPLETION
        )
        assert len(response.data.images) == 1

    async def test_citizen_cannot_upload_progress_to_own_complaint(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup)
        user = make_user(CITIZEN_A, "citizen")
        with pytest.raises(ForbiddenException):
            await service.upload_images(CID_A, user, [upload_file(PNG)], ImageType.PROGRESS)

    async def test_org_admin_from_other_org_denied(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup)
        user = make_user(ORG_ADMIN_A, "organization_admin", ORG_B)
        with pytest.raises(NotFoundException):
            await service.upload_images(CID_A, user, [upload_file(PNG)], ImageType.COMPLETION)

    async def test_staff_from_other_department_denied(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup, assigned_to=STAFF_A)
        user = make_user(STAFF_A, "organization_staff", ORG_A, DEPT_B)
        with pytest.raises(NotFoundException):
            await service.upload_images(CID_A, user, [upload_file(PNG)], ImageType.PROGRESS)


class TestValidation:
    async def test_no_files_rejected(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup)
        with pytest.raises(ValidationException):
            await service.upload_images(CID_A, make_user(CITIZEN_A, "citizen"), [], ImageType.EVIDENCE)

    async def test_more_than_five_files_rejected(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup)
        files = [upload_file(JPEG) for _ in range(6)]
        with pytest.raises(ValidationException):
            await service.upload_images(CID_A, make_user(CITIZEN_A, "citizen"), files, ImageType.EVIDENCE)

    async def test_exactly_five_files_allowed(self) -> None:
        service, lookup, repo, _ = build_service()
        seed_complaint(lookup)
        files = [upload_file(JPEG) for _ in range(5)]
        response = await service.upload_images(
            CID_A, make_user(CITIZEN_A, "citizen"), files, ImageType.EVIDENCE
        )
        assert len(response.data.images) == 5
        assert len(repo.images) == 5

    async def test_invalid_mime_rejected(self) -> None:
        service, lookup, repo, store = build_service()
        seed_complaint(lookup)
        with pytest.raises(InvalidFileTypeException):
            await service.upload_images(
                CID_A,
                make_user(CITIZEN_A, "citizen"),
                [upload_file(JPEG, mime="image/gif")],
                ImageType.EVIDENCE,
            )
        assert repo.images == {}
        assert store.objects == {}

    async def test_content_mismatch_rejected(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup)
        with pytest.raises(InvalidFileTypeException):
            await service.upload_images(
                CID_A,
                make_user(CITIZEN_A, "citizen"),
                [upload_file(b"not a jpeg", mime="image/jpeg")],
                ImageType.EVIDENCE,
            )

    async def test_empty_file_rejected(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup)
        with pytest.raises(InvalidFileTypeException):
            await service.upload_images(
                CID_A, make_user(CITIZEN_A, "citizen"), [upload_file(b"")], ImageType.EVIDENCE
            )

    async def test_oversized_file_rejected(self) -> None:
        service, lookup, repo, store = build_service()
        seed_complaint(lookup)
        oversized = b"\xff\xd8\xff" + b"x" * (1024 * 1024 + 1)
        with pytest.raises(FileTooLargeException):
            await service.upload_images(
                CID_A,
                make_user(CITIZEN_A, "citizen"),
                [upload_file(oversized)],
                ImageType.EVIDENCE,
            )
        assert repo.images == {}
        assert store.objects == {}

    async def test_heic_rejected_for_progress(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup, assigned_to=STAFF_A)
        user = make_user(STAFF_A, "organization_staff", ORG_A, DEPT_A)
        with pytest.raises(InvalidFileTypeException):
            await service.upload_images(
                CID_A, user, [upload_file(HEIC, filename="x.heic", mime="image/heic")], ImageType.PROGRESS
            )

    async def test_heic_allowed_for_evidence(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup)
        response = await service.upload_images(
            CID_A,
            make_user(CITIZEN_A, "citizen"),
            [upload_file(HEIC, filename="x.heic", mime="image/heic")],
            ImageType.EVIDENCE,
        )
        assert len(response.data.images) == 1

    async def test_malicious_filename_rejected(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup)
        with pytest.raises(InvalidFilenameException):
            await service.upload_images(
                CID_A,
                make_user(CITIZEN_A, "citizen"),
                [upload_file(JPEG, filename="../../secret.jpg")],
                ImageType.EVIDENCE,
            )

    async def test_mixed_valid_invalid_is_atomic(self) -> None:
        service, lookup, repo, store = build_service()
        seed_complaint(lookup)
        files = [upload_file(JPEG), upload_file(b"bad", mime="image/jpeg")]
        with pytest.raises(InvalidFileTypeException):
            await service.upload_images(
                CID_A, make_user(CITIZEN_A, "citizen"), files, ImageType.EVIDENCE
            )
        assert repo.images == {}
        assert store.objects == {}


class TestStorageAndMetadata:
    async def test_multiple_files_get_distinct_keys(self) -> None:
        service, lookup, repo, store = build_service()
        seed_complaint(lookup)
        files = [upload_file(JPEG, filename="a.jpg"), upload_file(JPEG, filename="b.jpg")]
        await service.upload_images(CID_A, make_user(CITIZEN_A, "citizen"), files, ImageType.EVIDENCE)
        keys = list(store.objects)
        assert len(keys) == 2
        assert keys[0] != keys[1]
        assert len(repo.images) == 2

    async def test_metadata_contains_internal_fields(self) -> None:
        service, lookup, repo, _ = build_service()
        seed_complaint(lookup)
        await service.upload_images(CID_A, make_user(CITIZEN_A, "citizen"), [upload_file(JPEG)], ImageType.EVIDENCE)
        record = next(iter(repo.images.values()))
        assert record["checksum"]
        assert record["storage_path"].startswith("evidence/")
        assert record["original_filename"] == "photo.jpg"
        assert record["is_deleted"] is False
        assert record["uploaded_by"] is not None

    async def test_response_uses_signed_url(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup)
        response = await service.upload_images(
            CID_A, make_user(CITIZEN_A, "citizen"), [upload_file(JPEG)], ImageType.EVIDENCE
        )
        url = response.data.images[0].url
        assert "expires=" in url and "signature=" in url

    async def test_upload_failure_leaves_no_metadata(self) -> None:
        failing = FailingStorage(fail_on_call=0)
        service, lookup, repo, _ = build_service(storage=failing)
        seed_complaint(lookup)
        with pytest.raises(StorageException):
            await service.upload_images(
                CID_A, make_user(CITIZEN_A, "citizen"), [upload_file(JPEG)], ImageType.EVIDENCE
            )
        assert repo.images == {}

    async def test_partial_upload_failure_compensates(self) -> None:
        failing = FailingStorage(fail_on_call=1)
        service, lookup, repo, _ = build_service(storage=failing)
        seed_complaint(lookup)
        files = [upload_file(JPEG, filename="a.jpg"), upload_file(JPEG, filename="b.jpg")]
        with pytest.raises(StorageException):
            await service.upload_images(
                CID_A, make_user(CITIZEN_A, "citizen"), files, ImageType.EVIDENCE
            )
        assert repo.images == {}
        # The first successfully uploaded object must have been cleaned up.
        assert len(failing.deleted) == 1

    async def test_metadata_failure_cleans_storage(self) -> None:
        repo = FailingRepository()
        service, lookup, _, store = build_service(image_repo=repo)
        seed_complaint(lookup)
        with pytest.raises(StorageException):
            await service.upload_images(
                CID_A, make_user(CITIZEN_A, "citizen"), [upload_file(JPEG)], ImageType.EVIDENCE
            )
        assert store.objects == {}


class TestListImages:
    async def test_owner_lists_images(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup)
        await service.upload_images(CID_A, make_user(CITIZEN_A, "citizen"), [upload_file(JPEG)], ImageType.EVIDENCE)
        response = await service.list_images(CID_A, make_user(CITIZEN_A, "citizen"))
        assert len(response.data.images) == 1
        assert "expires=" in response.data.images[0].url

    async def test_other_citizen_denied(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup)
        with pytest.raises(NotFoundException):
            await service.list_images(CID_A, make_user(CITIZEN_B, "citizen"))

    async def test_staff_other_org_denied(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup)
        with pytest.raises(NotFoundException):
            await service.list_images(CID_A, make_user(STAFF_B, "organization_staff", ORG_B, DEPT_B))

    async def test_deleted_images_excluded(self) -> None:
        service, lookup, repo, _ = build_service()
        seed_complaint(lookup)
        user = make_user(CITIZEN_A, "citizen")
        await service.upload_images(CID_A, user, [upload_file(JPEG)], ImageType.EVIDENCE)
        image_id = next(iter(repo.images))
        await service.delete_image(CID_A, image_id, user)
        response = await service.list_images(CID_A, user)
        assert response.data.images == []


class TestDeleteImage:
    async def test_uploader_can_soft_delete(self) -> None:
        service, lookup, repo, store = build_service()
        seed_complaint(lookup)
        user = make_user(CITIZEN_A, "citizen")
        await service.upload_images(CID_A, user, [upload_file(JPEG)], ImageType.EVIDENCE)
        image_id = next(iter(repo.images))
        storage_key = repo.images[image_id]["storage_path"]
        response = await service.delete_image(CID_A, image_id, user)
        assert response.data["is_deleted"] is True
        assert repo.images[image_id]["is_deleted"] is True
        # Physical deletion is deferred: the object remains in storage.
        assert storage_key in store.objects

    async def test_non_uploader_denied(self) -> None:
        service, lookup, repo, _ = build_service()
        seed_complaint(lookup)
        await service.upload_images(CID_A, make_user(CITIZEN_A, "citizen"), [upload_file(JPEG)], ImageType.EVIDENCE)
        image_id = next(iter(repo.images))
        # An org admin can access the complaint but is not the uploader.
        with pytest.raises(ForbiddenException):
            await service.delete_image(CID_A, image_id, make_user(ORG_ADMIN_A, "organization_admin", ORG_A))

    async def test_unknown_image_returns_404(self) -> None:
        service, lookup, _, _ = build_service()
        seed_complaint(lookup)
        with pytest.raises(NotFoundException):
            await service.delete_image(CID_A, "507f1f77bcf86cd7994390ff", make_user(CITIZEN_A, "citizen"))

    async def test_cross_tenant_denied(self) -> None:
        service, lookup, repo, _ = build_service()
        seed_complaint(lookup)
        await service.upload_images(CID_A, make_user(CITIZEN_A, "citizen"), [upload_file(JPEG)], ImageType.EVIDENCE)
        image_id = next(iter(repo.images))
        with pytest.raises(NotFoundException):
            await service.delete_image(CID_A, image_id, make_user(STAFF_B, "organization_staff", ORG_B, DEPT_B))
