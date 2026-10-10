"""Storage provider factory (Phase 1.3.4).

Selects a concrete :class:`~app.storage.base.StorageProvider` from configuration.

Implemented in this phase:

* ``local``  — filesystem provider for local development/test.
* ``memory`` — in-memory provider for the test suite.

``s3``/``minio`` and ``gridfs`` are documented future providers: the
abstraction supports them, but a production provider is **not** implemented in
Phase 1.3.4 and is rejected explicitly rather than silently falling back.
"""

from __future__ import annotations

from app.core.config import Settings
from app.exceptions.base import StorageException
from app.storage.base import StorageProvider
from app.storage.local import LocalStorageProvider
from app.storage.memory import InMemoryStorageProvider

_IMPLEMENTED_PROVIDERS = ("local", "memory")


def create_storage_provider(settings: Settings) -> StorageProvider:
    """Build the configured storage provider."""
    provider = (settings.storage_provider or "").strip().lower()
    if provider == "local":
        return LocalStorageProvider(
            settings.storage_local_path,
            settings.storage_local_url,
            secret_key=settings.secret_key,
            default_expiry_seconds=settings.storage_signed_url_expiry_seconds,
        )
    if provider == "memory":
        return InMemoryStorageProvider(
            secret_key=settings.secret_key,
            default_expiry_seconds=settings.storage_signed_url_expiry_seconds,
        )
    raise StorageException(
        f"Unsupported storage provider '{settings.storage_provider}'. "
        f"Implemented providers: {', '.join(_IMPLEMENTED_PROVIDERS)}. "
        "S3/MinIO and GridFS providers are documented future integrations."
    )
