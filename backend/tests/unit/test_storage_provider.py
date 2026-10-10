"""Phase 1.3.4 — Storage provider + storage key unit tests."""

import hashlib
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest

from app.core.config import Settings
from app.exceptions.base import StorageException
from app.schemas.complaint_image import ImageType
from app.storage import (
    InMemoryStorageProvider,
    LocalStorageProvider,
    StorageProvider,
    build_storage_key,
    create_storage_provider,
)

CONTENT = b"\xff\xd8\xff" + b"payload" * 4


class TestInMemoryProvider:
    async def test_implements_interface(self) -> None:
        assert isinstance(InMemoryStorageProvider(), StorageProvider)

    async def test_upload_returns_metadata(self) -> None:
        provider = InMemoryStorageProvider()
        result = await provider.upload(BytesIO(CONTENT), "evidence/a.jpg", "image/jpeg")
        assert result.storage_key == "evidence/a.jpg"
        assert result.file_size == len(CONTENT)
        assert result.checksum == hashlib.sha256(CONTENT).hexdigest()

    async def test_download_roundtrip(self) -> None:
        provider = InMemoryStorageProvider()
        await provider.upload(BytesIO(CONTENT), "k", "image/png")
        stream = await provider.download("k")
        assert stream.read() == CONTENT

    async def test_exists(self) -> None:
        provider = InMemoryStorageProvider()
        assert await provider.exists("missing") is False
        await provider.upload(BytesIO(CONTENT), "k", "image/jpeg")
        assert await provider.exists("k") is True

    async def test_delete(self) -> None:
        provider = InMemoryStorageProvider()
        await provider.upload(BytesIO(CONTENT), "k", "image/jpeg")
        assert await provider.delete("k") is True
        assert await provider.exists("k") is False

    async def test_delete_missing_returns_false(self) -> None:
        provider = InMemoryStorageProvider()
        assert await provider.delete("missing") is False

    async def test_presigned_url_is_time_limited(self) -> None:
        provider = InMemoryStorageProvider()
        url = await provider.generate_presigned_url("k", expires_in=120)
        assert "expires=" in url
        assert "signature=" in url


class TestLocalProvider:
    async def test_upload_writes_object(self, tmp_path: Path) -> None:
        provider = LocalStorageProvider(str(tmp_path), "http://localhost/uploads")
        result = await provider.upload(BytesIO(CONTENT), "evidence/2024/a.jpg", "image/jpeg")
        assert (tmp_path / "evidence/2024/a.jpg").read_bytes() == CONTENT
        assert result.checksum == hashlib.sha256(CONTENT).hexdigest()
        assert result.file_size == len(CONTENT)

    async def test_exists_download_delete(self, tmp_path: Path) -> None:
        provider = LocalStorageProvider(str(tmp_path), "http://localhost/uploads")
        await provider.upload(BytesIO(CONTENT), "a/b.jpg", "image/jpeg")
        assert await provider.exists("a/b.jpg") is True
        assert (await provider.download("a/b.jpg")).read() == CONTENT
        assert await provider.delete("a/b.jpg") is True
        assert await provider.exists("a/b.jpg") is False

    async def test_delete_missing_returns_false(self, tmp_path: Path) -> None:
        provider = LocalStorageProvider(str(tmp_path), "http://localhost/uploads")
        assert await provider.delete("nope.jpg") is False

    async def test_presigned_url_hides_filesystem_path(self, tmp_path: Path) -> None:
        provider = LocalStorageProvider(str(tmp_path), "http://localhost/uploads")
        url = await provider.generate_presigned_url("evidence/a.jpg", expires_in=60)
        assert str(tmp_path) not in url
        assert url.startswith("http://localhost/uploads/")
        assert "expires=" in url and "signature=" in url

    @pytest.mark.parametrize("key", ["../escape.jpg", "a/../../escape.jpg", "/abs.jpg"])
    async def test_traversal_key_rejected(self, tmp_path: Path, key: str) -> None:
        provider = LocalStorageProvider(str(tmp_path), "http://localhost/uploads")
        with pytest.raises(StorageException):
            await provider.upload(BytesIO(CONTENT), key, "image/jpeg")

    async def test_upload_reports_checksum(self, tmp_path: Path) -> None:
        provider = LocalStorageProvider(str(tmp_path), "http://localhost/uploads")
        result = await provider.upload(BytesIO(CONTENT), "x.jpg", "image/jpeg")
        assert result.checksum == hashlib.sha256(CONTENT).hexdigest()


class TestStorageKey:
    def test_expected_structure(self) -> None:
        key = build_storage_key(
            ImageType.EVIDENCE,
            "507f1f77bcf86cd799439013",
            "pothole.jpg",
            now=datetime(2024, 1, 15, tzinfo=UTC),
            uuid_prefix="a1b2c3d4",
        )
        assert key == (
            "evidence/2024/01/15/507f1f77bcf86cd799439013/a1b2c3d4_pothole.jpg"
        )

    def test_month_and_day_are_zero_padded(self) -> None:
        key = build_storage_key(
            "progress", "entity", "x.png", now=datetime(2024, 3, 5, tzinfo=UTC), uuid_prefix="deadbeef"
        )
        assert "/2024/03/05/" in key

    def test_keys_are_unique(self) -> None:
        first = build_storage_key("evidence", "c", "a.jpg")
        second = build_storage_key("evidence", "c", "a.jpg")
        assert first != second

    def test_scoped_by_complaint_id(self) -> None:
        key = build_storage_key("evidence", "complaint-abc", "a.jpg", uuid_prefix="ffffffff")
        assert "complaint-abc" in key

    def test_uses_sanitized_filename_only(self) -> None:
        key = build_storage_key("evidence", "c", "safe_photo.jpg", uuid_prefix="ffffffff")
        assert key.endswith("ffffffff_safe_photo.jpg")
        assert ".." not in key

    def test_entity_id_is_sanitized(self) -> None:
        key = build_storage_key("evidence", "../../etc", "a.jpg", uuid_prefix="ffffffff")
        assert ".." not in key
        assert "/etc" not in key.split("/")[-2]

    def test_string_image_type_supported(self) -> None:
        key = build_storage_key("completion", "c", "done.jpg", uuid_prefix="ffffffff")
        assert key.startswith("completion/")


class TestFactory:
    def test_local_provider(self) -> None:
        provider = create_storage_provider(Settings(storage_provider="local"))
        assert isinstance(provider, LocalStorageProvider)

    def test_memory_provider(self) -> None:
        provider = create_storage_provider(Settings(storage_provider="memory"))
        assert isinstance(provider, InMemoryStorageProvider)

    def test_provider_is_case_insensitive(self) -> None:
        provider = create_storage_provider(Settings(storage_provider="LOCAL"))
        assert isinstance(provider, LocalStorageProvider)

    @pytest.mark.parametrize("name", ["s3", "minio", "gridfs", "mystery"])
    def test_unimplemented_provider_rejected(self, name: str) -> None:
        with pytest.raises(StorageException):
            create_storage_provider(Settings(storage_provider=name))
