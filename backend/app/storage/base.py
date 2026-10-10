"""Storage provider abstraction (Phase 1.3.4).

Business logic depends only on this interface, never on a concrete backend, so
the application can run against local/test storage in development and an
object-store provider (S3/MinIO) or GridFS in production without changes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import BinaryIO


@dataclass(frozen=True)
class UploadResult:
    """Outcome of a successful storage upload."""

    storage_key: str
    public_url: str
    file_size: int
    checksum: str


@dataclass(frozen=True)
class StorageConfig:
    """Non-secret storage configuration."""

    bucket: str
    region: str
    base_url: str
    default_expiry_seconds: int = 3600


class StorageProvider(ABC):
    """Abstract object-storage backend."""

    @abstractmethod
    async def upload(
        self,
        file: BinaryIO,
        key: str,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        """Store ``file`` under ``key`` and return its upload result."""

    @abstractmethod
    async def download(self, key: str) -> BinaryIO:
        """Return a readable stream for the object stored at ``key``."""

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete the object at ``key``. Returns ``True`` if it was removed."""

    @abstractmethod
    async def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a time-limited access URL for a private object."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return ``True`` if an object exists at ``key``."""
