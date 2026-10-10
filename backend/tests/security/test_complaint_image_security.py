"""Phase 1.3.4 — Complaint image security tests.

Covers MongoDB-operator injection, path traversal, cross-user/cross-tenant
image access, mass assignment, response leakage and no-Motor regression.
"""

import re
from pathlib import Path
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

CID_A = "507f1f77bcf86cd799439013"
CID_B = "507f1f77bcf86cd799439099"
CITIZEN_A = "507f1f77bcf86cd799439011"
CITIZEN_B = "507f1f77bcf86cd799439012"
ORG_A = "507f1f77bcf86cd799439021"
ORG_B = "507f1f77bcf86cd799439022"
DEPT_A = "507f1f77bcf86cd799439031"
DEPT_B = "507f1f77bcf86cd799439032"
STAFF_B = "507f1f77bcf86cd799439043"
ORG_ADMIN_A = "507f1f77bcf86cd799439042"

POST_URL = f"/api/v1/complaints/{CID_A}/images"
GET_URL = f"/api/v1/complaints/{CID_A}/images"


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


def auth(role: UserRole, user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user_id, role=role.value)}"}


def files_payload(*entries: tuple[str, bytes, str]) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", entry) for entry in entries]


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def user_repository() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def complaint_lookup() -> FakeComplaintLookup:
    lookup = FakeComplaintLookup()
    lookup.seed(CID_A, user_id=CITIZEN_A, organization_id=ORG_A, department_id=DEPT_A, assigned_to=None)
    lookup.seed(CID_B, user_id=CITIZEN_B, organization_id=ORG_B, department_id=DEPT_B, assigned_to=None)
    return lookup


@pytest.fixture
def image_repository() -> FakeComplaintImageRepository:
    return FakeComplaintImageRepository()


@pytest.fixture
def storage() -> InMemoryStorageProvider:
    return InMemoryStorageProvider()


@pytest.fixture
async def client(
    app: Any,
    complaint_lookup: FakeComplaintLookup,
    image_repository: FakeComplaintImageRepository,
    storage: InMemoryStorageProvider,
    user_repository: FakeUserRepository,
):
    validator = FileValidator(
        max_file_sizes_mb={ImageType.EVIDENCE: 1, ImageType.PROGRESS: 1, ImageType.COMPLETION: 1}
    )
    service = ImageService(
        image_repository,  # type: ignore[arg-type]
        complaint_lookup,  # type: ignore[arg-type]
        storage,
        validator,
    )
    app.dependency_overrides[get_image_service] = lambda: service
    app.dependency_overrides[get_user_service] = lambda: UserService(user_repository)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestMongoInjection:
    @pytest.mark.parametrize(
        "complaint_id",
        ["%24ne", "%24gt", "%24regex", "%24where", "%24or", "not-an-objectid"],
    )
    async def test_operator_like_complaint_id_is_safe(
        self, client: AsyncClient, user_repository: FakeUserRepository, complaint_id: str
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            f"/api/v1/complaints/{complaint_id}/images",
            files=files_payload(("a.jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code in (404, 422)
        assert response.status_code != 500

    @pytest.mark.parametrize("image_id", ["%24ne", "%24where", "%24or", "not-an-id"])
    async def test_operator_like_image_id_is_safe(
        self, client: AsyncClient, user_repository: FakeUserRepository, image_id: str
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.delete(
            f"{POST_URL}/{image_id}", headers=auth(UserRole.CITIZEN, CITIZEN_A)
        )
        assert response.status_code in (404, 422)
        assert response.status_code != 500

    async def test_query_operator_does_not_crash(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.get(
            GET_URL, params={"complaint_id[$ne]": "x"}, headers=auth(UserRole.CITIZEN, CITIZEN_A)
        )
        assert response.status_code in (200, 404)


class TestMassAssignment:
    async def test_cannot_control_storage_key(
        self,
        client: AsyncClient,
        user_repository: FakeUserRepository,
        image_repository: FakeComplaintImageRepository,
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence", "storage_path": "../escape.jpg", "storage_key": "x/y"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 201
        record = next(iter(image_repository.images.values()))
        assert ".." not in record["storage_path"]
        assert record["storage_path"].startswith("evidence/")

    async def test_cannot_control_uploaded_by(
        self,
        client: AsyncClient,
        user_repository: FakeUserRepository,
        image_repository: FakeComplaintImageRepository,
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence", "uploaded_by": "507f1f77bcf86cd799439999"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 201
        record = next(iter(image_repository.images.values()))
        assert str(record["uploaded_by"]) != "507f1f77bcf86cd799439999"

    async def test_cannot_control_checksum_or_size(
        self,
        client: AsyncClient,
        user_repository: FakeUserRepository,
        image_repository: FakeComplaintImageRepository,
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence", "checksum": "f" * 64, "file_size": 1},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 201
        record = next(iter(image_repository.images.values()))
        assert record["checksum"] != "f" * 64
        assert record["file_size"] == len(JPEG)


class TestPathTraversal:
    # NOTE: Windows-drive and NUL-byte filenames are covered directly at the
    # validator level (test_file_validator.py); the HTTP client encodes/escapes
    # some of those characters before they reach the server, so they are not
    # reliable through the multipart API surface.
    @pytest.mark.parametrize(
        "filename",
        [
            "../../secret.jpg",
            "..\\..\\secret.jpg",
            "/etc/passwd",
            "dir/evil.jpg",
        ],
    )
    async def test_dangerous_filenames_rejected(
        self, client: AsyncClient, user_repository: FakeUserRepository, filename: str
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload((filename, JPEG, "image/jpeg")),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_FILENAME"

    async def test_script_extension_still_validated_by_content(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        """A .php/.py payload cannot pass as an image."""
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("evil.php", b"<?php system($_GET['c']); ?>", "image/jpeg")),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 400

    async def test_safe_filename_stored_sanitized(
        self,
        client: AsyncClient,
        user_repository: FakeUserRepository,
        image_repository: FakeComplaintImageRepository,
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("my photo (1).jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        assert response.status_code == 201
        record = next(iter(image_repository.images.values()))
        assert record["original_filename"] == "myphoto1.jpg"
        assert ".." not in record["storage_path"]
        assert record["storage_path"].endswith("_myphoto1.jpg")


class TestCrossUserAndTenantAccess:
    async def _upload_as_citizen_a(self, client: AsyncClient) -> str:
        response = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        return response.json()["data"]["images"][0]["id"]

    async def test_citizen_b_cannot_list_a_images(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        await self._upload_as_citizen_a(client)
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_B)
        response = await client.get(GET_URL, headers=auth(UserRole.CITIZEN, CITIZEN_B))
        assert response.status_code == 404

    async def test_other_org_staff_cannot_list_a_images(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        seed_user(user_repository, UserRole.ORGANIZATION_STAFF, STAFF_B, ORG_B, DEPT_B)
        await self._upload_as_citizen_a(client)
        response = await client.get(
            GET_URL, headers=auth(UserRole.ORGANIZATION_STAFF, STAFF_B)
        )
        assert response.status_code == 404

    async def test_other_user_cannot_delete_a_image(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        seed_user(user_repository, UserRole.ORGANIZATION_ADMIN, ORG_ADMIN_A, ORG_A)
        image_id = await self._upload_as_citizen_a(client)
        response = await client.delete(
            f"{POST_URL}/{image_id}", headers=auth(UserRole.ORGANIZATION_ADMIN, ORG_ADMIN_A)
        )
        assert response.status_code == 403


class TestResponseLeakage:
    async def test_error_body_has_no_stack_trace(
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
        assert "traceback" not in response.text.lower()
        assert "mongo" not in response.text.lower()

    async def test_success_body_exposes_only_contract_fields(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        response = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence"},
            headers=auth(UserRole.CITIZEN, CITIZEN_A),
        )
        image = response.json()["data"]["images"][0]
        assert set(image) == {"id", "image_type", "url", "file_size", "mime_type", "created_at"}


class TestRateLimitBoundary:
    async def test_under_limit_threshold_and_over_limit(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        seed_user(user_repository, UserRole.CITIZEN, CITIZEN_A)
        headers = auth(UserRole.CITIZEN, CITIZEN_A)
        for i in range(9):
            response = await client.post(
                POST_URL,
                files=files_payload(("a.jpg", JPEG, "image/jpeg")),
                data={"image_type": "evidence"},
                headers=headers,
            )
            assert response.status_code == 201, f"request {i + 1} unexpectedly blocked"
        # 10th request is the threshold (still allowed).
        tenth = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence"},
            headers=headers,
        )
        assert tenth.status_code == 201
        # 11th is over the limit.
        eleventh = await client.post(
            POST_URL,
            files=files_payload(("a.jpg", JPEG, "image/jpeg")),
            data={"image_type": "evidence"},
            headers=headers,
        )
        assert eleventh.status_code == 429
        assert eleventh.headers.get("X-RateLimit-Limit") == "10"
        assert "Retry-After" in eleventh.headers


class TestNoMotorRegression:
    def test_no_motor_imports_in_app_source(self) -> None:
        app_dir = Path(__file__).resolve().parents[2] / "app"
        motor_import = re.compile(r"^\s*(from|import)\s+motor\b", re.IGNORECASE)
        offenders: list[str] = []
        for path in app_dir.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                if motor_import.match(line) or "AsyncIOMotor" in line:
                    offenders.append(f"{path}: {line.strip()}")
        assert offenders == [], f"Motor usage detected: {offenders}"

    def test_image_service_uses_storage_abstraction(self) -> None:
        """Business logic must not import a concrete storage provider."""
        source = (
            Path(__file__).resolve().parents[2] / "app" / "services" / "image_service.py"
        ).read_text(encoding="utf-8")
        assert "LocalStorageProvider" not in source
        assert "InMemoryStorageProvider" not in source
        assert "import motor" not in source
