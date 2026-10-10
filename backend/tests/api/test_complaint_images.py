"""Phase 1.3.4 — Complaint image API tests (multipart upload, list, delete)."""

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.dependencies.services import get_image_service, get_user_service
from app.main import create_app
from app.schemas.complaint_image import ImageType
from app.schemas.user import UserRole
from app.services.image_service import ImageService
from app.services.user_service import UserService
from app.storage.memory import InMemoryStorageProvider
from app.utils.file_validation import FileValidator
from tests.fakes import FakeComplaintImageRepository, FakeComplaintLookup, FakeUserRepository

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


def seed_user(
    repository: FakeUserRepository,
    role: UserRole,
    user_id: str,
    organization_id: str | None = None,
    department_id: str | None = None,
) -> str:
    return repository.seed(
        user_id=user_id,
        email=f"{user_id}@example.com",
        phone="+15550000000",
        role=role.value,
        status="active",
        organization_id=organization_id,
        department_id=department_id,
    )


def make_token(user_id: str, role: UserRole) -> str:
    return create_access_token(user_id=user_id, role=role.value)


def auth(role: UserRole, user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user_id, role)}"}


def files_payload(*entries: tuple[str, bytes, str]) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", entry) for entry in entries]


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def user_repository() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def user_service(user_repository: FakeUserRepository) -> UserService:
    return UserService(user_repository)


@pytest.fixture
def complaint_lookup() -> FakeComplaintLookup:
    lookup = FakeComplaintLookup()
    lookup.seed(
        CID_A,
        user_id=CITIZEN_A,
        organization_id=ORG_A,
        department_id=DEPT_A,
        assigned_to=None,
        status="SUBMITTED",
    )
    lookup.seed(
        CID_B,
        user_id=CITIZEN_B,
        organization_id=ORG_B,
        department_id=DEPT_B,
        assigned_to=None,
        status="SUBMITTED",
    )
    return lookup


@pytest.fixture
def image_repository() -> FakeComplaintImageRepository:
    return FakeComplaintImageRepository()


@pytest.fixture
def storage() -> InMemoryStorageProvider:
    return InMemoryStorageProvider()


@pytest.fixture
def image_service(
    image_repository: FakeComplaintImageRepository,
    complaint_lookup: FakeComplaintLookup,
    storage: InMemoryStorageProvider,
) -> ImageService:
    validator = FileValidator(
        max_file_sizes_mb={
            ImageType.EVIDENCE: 1,
            ImageType.PROGRESS: 1,
            ImageType.COMPLETION: 1,
        }
    )
    return ImageService(
        image_repository,  # type: ignore[arg-type]
        complaint_lookup,  # type: ignore[arg-type]
        storage,
        validator,
        max_images_per_request=5,
    )


@pytest.fixture
async def client(app, image_service: ImageService, user_service: UserService):
    app.dependency_overrides[get_image_service] = lambda: image_service
    app.dependency_overrides[get_user_service] = lambda: user_service
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


POST_URL = f"/api/v1/complaints/{CID_A}/images"
GET_URL = f"/api/v1/complaints/{CID_A}/images"


class TestUploadAuth:
    async def test_unauthenticated_returns_401(self, client: AsyncClient) -> None:
        response = await client.post(
            POST_URL, files=files_payload(("a.jpg", JPEG, "image/jpeg")), data={"image_type": "evidence"}
        )
        assert response.status_code == 401

    async def test_invalid_token_returns_401(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence"},
            headers={"Authorization": "Bearer not.a.token"},
        )
        assert response.status_code == 401


class TestUploadSuccess:
    async def test_citizen_owner_uploads_evidence(
        self,
        client: AsyncClient,
        user_repository: FakeUserRepository,
        image_repository: FakeComplaintImageRepository,
        storage: InMemoryStorageProvider,
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("pothole.jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["message"] == "Images uploaded"
        assert len(body["data"]["images"]) == 1
        assert len(image_repository.images) == 1
        assert len(storage.objects) == 1

    async def test_response_contract_fields(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("pothole.jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 201
        image = response.json()["data"]["images"][0]
        assert set(image) == {"id", "image_type", "url", "file_size", "mime_type", "created_at"}
        assert image["image_type"] == "evidence"
        assert image["mime_type"] == "image/jpeg"
        assert image["file_size"] == len(JPEG)

    async def test_response_exposes_no_internal_or_secret_data(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("pothole.jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        text = response.text.lower()
        for forbidden in ("checksum", "storage_path", "storage_key", "secret", "password", "bucket"):
            assert forbidden not in text

    async def test_multiple_valid_files(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(
                ("a.jpg", JPEG, "image/jpeg"), ("b.png", PNG, "image/png")
            ),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 201
        assert len(response.json()["data"]["images"]) == 2

    async def test_exactly_five_files(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        entries = tuple((f"f{i}.jpg", JPEG, "image/jpeg") for i in range(5))
        response = await client.post(
            POST_URL,
            files=files_payload(*entries),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 201
        assert len(response.json()["data"]["images"]) == 5

    @pytest.mark.parametrize(
        ("filename", "content", "mime"),
        [
            ("a.jpg", JPEG, "image/jpeg"),
            ("a.png", PNG, "image/png"),
            ("a.webp", WEBP, "image/webp"),
            ("a.heic", HEIC, "image/heic"),
        ],
    )
    async def test_supported_evidence_types(
        self,
        client: AsyncClient,
        user_repository: FakeUserRepository,
        filename: str,
        content: bytes,
        mime: str,
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload((filename, content, mime)),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 201

    async def test_extra_form_fields_ignored(
        self,
        client: AsyncClient,
        user_repository: FakeUserRepository,
        image_repository: FakeComplaintImageRepository,
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", JPEG, "image/jpeg")),
            data={
                "image_type": "evidence",
                "uploaded_by": "507f1f77bcf86cd799439999",
                "storage_key": "hacked/path.jpg",
                "complaint_id": CID_B,
            },
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 201
        record = next(iter(image_repository.images.values()))
        assert record["storage_path"] != "hacked/path.jpg"
        assert str(record["complaint_id"]) != CID_B


class TestUploadAuthorization:
    async def test_citizen_cannot_upload_to_other_complaint(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_B)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_B),
        )
        assert response.status_code == 404

    async def test_org_admin_cannot_upload_evidence(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.ORGANIZATION_ADMIN, ORG_ADMIN_A, ORG_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence"},
            headers=auth(UserRole.ORGANIZATION_ADMIN, ORG_ADMIN_A),
        )
        assert response.status_code == 403

    async def test_org_admin_can_upload_progress(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.ORGANIZATION_ADMIN, ORG_ADMIN_A, ORG_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.png", PNG, "image/png")),
            data={"image_type": "progress"},
            headers=auth(UserRole.ORGANIZATION_ADMIN, ORG_ADMIN_A),
        )
        assert response.status_code == 201
        assert response.json()["data"]["images"][0]["image_type"] == "progress"

    async def test_unassigned_staff_cannot_upload_progress(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.ORGANIZATION_STAFF, STAFF_A, ORG_A, DEPT_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.png", PNG, "image/png")),
            data={"image_type": "progress"},
            headers=auth(UserRole.ORGANIZATION_STAFF, STAFF_A),
        )
        assert response.status_code == 403

    async def test_assigned_staff_can_upload_completion(
        self,
        client: AsyncClient,
        user_repository: FakeUserRepository,
        complaint_lookup: FakeComplaintLookup,
    ) -> None:
        complaint_lookup.seed(
            CID_A,
            user_id=CITIZEN_A,
            organization_id=ORG_A,
            department_id=DEPT_A,
            assigned_to=STAFF_A,
            status="ONGOING",
        )
        seed_user(user_repository, UserRole.ORGANIZATION_STAFF, STAFF_A, ORG_A, DEPT_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.png", PNG, "image/png")),
            data={"image_type": "completion"},
            headers=auth(UserRole.ORGANIZATION_STAFF, STAFF_A),
        )
        assert response.status_code == 201

    async def test_citizen_cannot_upload_progress_to_own_complaint(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.png", PNG, "image/png")),
            data={"image_type": "progress"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 403

    async def test_cross_org_staff_denied(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.ORGANIZATION_STAFF, STAFF_B, ORG_B, DEPT_B)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.png", PNG, "image/png")),
            data={"image_type": "progress"},
            headers=auth(UserRole.ORGANIZATION_STAFF, STAFF_B),
        )
        assert response.status_code == 404

    async def test_platform_admin_can_upload_progress(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.ADMIN, PLATFORM_ADMIN)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.png", PNG, "image/png")),
            data={"image_type": "progress"},
            headers=auth(UserRole.ADMIN, PLATFORM_ADMIN),
        )
        assert response.status_code == 201


class TestUploadValidation:
    async def test_invalid_mime_returns_400(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.gif", b"GIF89a", "image/gif")),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_FILE_TYPE"

    async def test_magic_byte_mismatch_returns_400(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", PNG, "image/jpeg")),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_FILE_TYPE"

    async def test_random_binary_returns_400(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", b"\x00\x01\x02random", "image/jpeg")),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 400

    async def test_empty_file_returns_400(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", b"", "image/jpeg")),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 400

    async def test_oversized_file_returns_400(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        oversized = b"\xff\xd8\xff" + b"x" * (1024 * 1024 + 1)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", oversized, "image/jpeg")),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == "FILE_TOO_LARGE"

    async def test_malicious_filename_returns_400(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("../../secret.jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_FILENAME"

    async def test_more_than_five_files_returns_422(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        entries = tuple((f"f{i}.jpg", JPEG, "image/jpeg") for i in range(6))
        response = await client.post(
            POST_URL,
            files=files_payload(*entries),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 422

    async def test_missing_image_type_returns_422(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", JPEG, "image/jpeg")),
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 422

    async def test_invalid_image_type_returns_422(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", JPEG, "image/jpeg")),
            data={"image_type": "avatar"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 422

    async def test_mixed_valid_invalid_is_atomic(
        self,
        client: AsyncClient,
        user_repository: FakeUserRepository,
        image_repository: FakeComplaintImageRepository,
        storage: InMemoryStorageProvider,
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(
                ("a.jpg", JPEG, "image/jpeg"), ("b.jpg", b"bad", "image/jpeg")
            ),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 400
        assert image_repository.images == {}
        assert storage.objects == {}


class TestListImages:
    async def test_unauthenticated_returns_401(self, client: AsyncClient) -> None:
        assert (await client.get(GET_URL)).status_code == 401

    async def test_owner_lists_uploaded_images(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        headers = auth(UserRole.CITIZEN, CITIZEN_A)
        await client.post(
            POST_URL,
            files=files_payload(("a.jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence"},
            headers=headers,
        )
        response = await client.get(GET_URL, headers=headers)
        assert response.status_code == 200
        images = response.json()["data"]["images"]
        assert len(images) == 1
        assert "expires=" in images[0]["url"]

    async def test_other_citizen_denied(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_B)
        response = await client.get(GET_URL, headers=auth(UserRole.CITIZEN, CITIZEN_B))
        assert response.status_code == 404

    async def test_cross_org_staff_denied(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.ORGANIZATION_STAFF, STAFF_B, ORG_B, DEPT_B)
        response = await client.get(
            GET_URL, headers=auth(UserRole.ORGANIZATION_STAFF, STAFF_B)
        )
        assert response.status_code == 404


class TestDeleteImage:
    async def _upload(self, client: AsyncClient) -> str:
        response = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 201
        return response.json()["data"]["images"][0]["id"]

    async def test_uploader_soft_deletes(
        self,
        client: AsyncClient,
        user_repository: FakeUserRepository,
        image_repository: FakeComplaintImageRepository,
        storage: InMemoryStorageProvider,
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        image_id = await self._upload(client)
        headers = auth(UserRole.CITIZEN, CITIZEN_A)
        response = await client.delete(f"{POST_URL}/{image_id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["data"]["is_deleted"] is True
        assert image_repository.images[image_id]["is_deleted"] is True
        # Storage object remains (deferred physical deletion).
        assert len(storage.objects) == 1
        # Excluded from listing afterwards.
        listing = await client.get(GET_URL, headers=headers)
        assert listing.json()["data"]["images"] == []

    async def test_non_uploader_denied(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        seed_user(user_repository, UserRole.ORGANIZATION_ADMIN, ORG_ADMIN_A, ORG_A)
        image_id = await self._upload(client)
        response = await client.delete(
            f"{POST_URL}/{image_id}",
            headers=auth(UserRole.ORGANIZATION_ADMIN, ORG_ADMIN_A),
        )
        assert response.status_code == 403

    async def test_unknown_image_returns_404(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.delete(
            f"{POST_URL}/507f1f77bcf86cd7994390ff",
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 404

    async def test_unauthenticated_returns_401(self, client: AsyncClient) -> None:
        response = await client.delete(f"{POST_URL}/507f1f77bcf86cd7994390ff")
        assert response.status_code == 401


class TestUploadRateLimit:
    async def test_eleventh_upload_is_rate_limited(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        headers = auth(UserRole.CITIZEN, CITIZEN_A)
        for _ in range(10):
            response = await client.post(
                POST_URL,
                files=files_payload(("a.jpg", JPEG, "image/jpeg")),
                data={"image_type": "evidence"},
                headers=headers,
            )
            assert response.status_code == 201
        blocked = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence"},
            headers=headers,
        )
        assert blocked.status_code == 429
        assert blocked.json()["error_code"] == "RATE_LIMIT_EXCEEDED"
        assert blocked.headers.get("X-RateLimit-Limit") == "10"
        assert blocked.headers.get("X-RateLimit-Remaining") == "0"

    async def test_limit_is_per_user(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_B)
        headers_a = auth(UserRole.CITIZEN, CITIZEN_A)
        headers_b = auth(UserRole.CITIZEN, CITIZEN_B)
        for _ in range(10):
            await client.post(
                POST_URL,
                files=files_payload(("a.jpg", JPEG, "image/jpeg")),
                data={"image_type": "evidence"},
                headers=headers_a,
            )
        # A different user is unaffected by A's consumption.
        response = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence"},
            headers=headers_b,
        )
        assert response.status_code == 404  # B cannot access A's complaint


class TestOpenAPI:
    def test_paths_documented(self, app: Any) -> None:
        schema = app.openapi()
        assert "/api/v1/complaints/{complaint_id}/images" in schema["paths"]
        assert "/api/v1/complaints/{complaint_id}/images/{image_id}" in schema["paths"]

    def test_post_is_multipart(self, app: Any) -> None:
        schema = app.openapi()
        post = schema["paths"]["/api/v1/complaints/{complaint_id}/images"]["post"]
        content = post["requestBody"]["content"]
        assert "multipart/form-data" in content

    def test_post_has_bearer_security(self, app: Any) -> None:
        schema = app.openapi()
        post = schema["paths"]["/api/v1/complaints/{complaint_id}/images"]["post"]
        assert "security" in post
        assert any("Bearer" in str(req) for req in post["security"])

    def test_image_type_enum_documented(self, app: Any) -> None:
        schema = app.openapi()
        components = schema["components"]["schemas"]
        assert components["ImageType"]["enum"] == ["evidence", "progress", "completion"]
