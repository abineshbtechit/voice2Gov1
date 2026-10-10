"""In-memory storage provider (tests).

Deterministic, dependency-free provider used by the test suite so image tests
never require a live object store or cloud credentials. It implements the same
``StorageProvider`` contract as production providers.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
from typing import BinaryIO

from app.storage.base import StorageProvider, UploadResult


class InMemoryStorageProvider(StorageProvider):
    """Dict-backed provider implementing the full storage contract."""

    def __init__(self, *, secret_key: str = "test", default_expiry_seconds: int = 3600) -> None:
        self._objects: dict[str, bytes] = {}
        self._metadata: dict[str, dict[str, str]] = {}
        self._secret_key = secret_key
        self._default_expiry = default_expiry_seconds

    @property
    def objects(self) -> dict[str, bytes]:
        """Expose stored objects for test assertions."""
        return self._objects

    async def upload(
        self,
        file: BinaryIO,
        key: str,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        content = file.read()
        if isinstance(content, str):  # pragma: no cover - defensive
            content = content.encode()
        self._objects[key] = content
        self._metadata[key] = {"content_type": content_type, **(metadata or {})}
        checksum = hashlib.sha256(content).hexdigest()
        url = await self.generate_presigned_url(key, self._default_expiry)
        return UploadResult(
            storage_key=key, public_url=url, file_size=len(content), checksum=checksum
        )

    async def download(self, key: str) -> BinaryIO:
        return BytesIO(self._objects[key])

    async def delete(self, key: str) -> bool:
        self._metadata.pop(key, None)
        return self._objects.pop(key, None) is not None

    async def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        import hmac
        import time

        expires_at = int(time.time()) + max(expires_in, 1)
        signature = hmac.new(
            self._secret_key.encode(), f"{key}:{expires_at}".encode(), hashlib.sha256
        ).hexdigest()
        return f"memory://{key}?expires={expires_at}&signature={signature}"

    async def exists(self, key: str) -> bool:
        return key in self._objects
