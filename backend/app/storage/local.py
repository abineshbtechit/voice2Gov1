"""Local filesystem storage provider (development/test only).

Stores objects under a configured root directory. Keys are validated and
resolved so they can never escape the configured root (path-traversal safe),
and generated URLs are signed and time-limited rather than raw file paths.

This provider is intended for local development and tests. Production should
use an object-store provider (S3/MinIO) or GridFS.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from urllib.parse import quote

from app.exceptions.base import StorageException
from app.storage.base import StorageProvider, UploadResult


class LocalStorageProvider(StorageProvider):
    """Filesystem-backed provider rooted at ``base_path``."""

    def __init__(
        self,
        base_path: str,
        base_url: str,
        *,
        secret_key: str = "",
        default_expiry_seconds: int = 3600,
    ) -> None:
        self._base_path = Path(base_path)
        self._base_url = base_url.rstrip("/")
        self._secret_key = secret_key
        self._default_expiry = default_expiry_seconds

    @property
    def base_path(self) -> Path:
        return self._base_path

    def _resolve(self, key: str) -> Path:
        rel = PurePosixPath(key)
        if rel.is_absolute() or ".." in rel.parts or not key:
            raise StorageException("Invalid storage key")
        candidate = (self._base_path / rel).resolve()
        root = self._base_path.resolve()
        if candidate != root and root not in candidate.parents:
            raise StorageException("Invalid storage key")
        return candidate

    def _sign(self, key: str, expires_at: int) -> str:
        message = f"{key}:{expires_at}".encode()
        return hmac.new(self._secret_key.encode(), message, hashlib.sha256).hexdigest()

    async def upload(
        self,
        file: BinaryIO,
        key: str,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        path = self._resolve(key)
        content = file.read()
        if isinstance(content, str):  # pragma: no cover - defensive
            content = content.encode()
        checksum = hashlib.sha256(content).hexdigest()

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

        try:
            await asyncio.to_thread(_write)
        except OSError as exc:  # pragma: no cover - filesystem failure
            raise StorageException("Failed to write object to local storage") from exc

        url = await self.generate_presigned_url(key, self._default_expiry)
        return UploadResult(
            storage_key=key, public_url=url, file_size=len(content), checksum=checksum
        )

    async def download(self, key: str) -> BinaryIO:
        path = self._resolve(key)

        def _read() -> bytes:
            return path.read_bytes()

        try:
            content = await asyncio.to_thread(_read)
        except OSError as exc:
            raise StorageException("Failed to read object from local storage") from exc
        return BytesIO(content)

    async def delete(self, key: str) -> bool:
        path = self._resolve(key)

        def _delete() -> bool:
            try:
                path.unlink()
                return True
            except FileNotFoundError:
                return False

        return await asyncio.to_thread(_delete)

    async def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        import time

        expires_at = int(time.time()) + max(expires_in, 1)
        signature = self._sign(key, expires_at)
        return (
            f"{self._base_url}/{quote(key, safe='/')}"
            f"?expires={expires_at}&signature={signature}"
        )

    async def exists(self, key: str) -> bool:
        path = self._resolve(key)
        return await asyncio.to_thread(path.is_file)
