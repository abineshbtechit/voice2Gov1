"""File validation for complaint image uploads (Phase 1.3.4).

Implements the authoritative file-storage rules:

* per-image-type MIME allow-list (``evidence`` also permits ``image/heic``),
* per-image-type size limits (10 MB evidence, 5 MB progress/completion),
* filename sanitization + path-traversal rejection,
* magic-byte / content validation (never trust the client-declared MIME type).

The client-declared MIME type is validated *and* the actual file signature is
checked, so a file claiming ``image/jpeg`` that contains arbitrary text is
rejected rather than stored.
"""

from __future__ import annotations

import re
from typing import Protocol

from app.core.config import Settings
from app.exceptions.base import (
    FileTooLargeException,
    InvalidFilenameException,
    InvalidFileTypeException,
)
from app.schemas.complaint_image import ImageType

#: Chunk size used when reading an upload while enforcing the size limit.
READ_CHUNK_SIZE = 64 * 1024

#: Per-image-type allow-lists (authoritative file-storage-architecture.md).
EVIDENCE_MIME_TYPES: tuple[str, ...] = (
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
)
PROGRESS_MIME_TYPES: tuple[str, ...] = ("image/jpeg", "image/png", "image/webp")
COMPLETION_MIME_TYPES: tuple[str, ...] = ("image/jpeg", "image/png", "image/webp")

ALLOWED_MIME_TYPES: dict[ImageType, tuple[str, ...]] = {
    ImageType.EVIDENCE: EVIDENCE_MIME_TYPES,
    ImageType.PROGRESS: PROGRESS_MIME_TYPES,
    ImageType.COMPLETION: COMPLETION_MIME_TYPES,
}

#: Default size limits in megabytes (authoritative file-storage-architecture.md).
DEFAULT_MAX_FILE_SIZES_MB: dict[ImageType, int] = {
    ImageType.EVIDENCE: 10,
    ImageType.PROGRESS: 5,
    ImageType.COMPLETION: 5,
}

#: HEIC/HEIF ISO-BMFF brands accepted for ``image/heic``.
_HEIC_BRANDS = frozenset(
    {b"heic", b"heix", b"hevc", b"hevx", b"heif", b"mif1", b"msf1", b"avif"}
)

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")
_MULTI_DOT = re.compile(r"\.{2,}")


class AsyncByteReader(Protocol):
    """Minimal async file-like reader (e.g. ``starlette.UploadFile``)."""

    async def read(self, size: int = -1) -> bytes: ...


async def read_bounded(reader: AsyncByteReader, max_bytes: int) -> bytes:
    """Read an upload in bounded chunks, aborting as soon as it exceeds ``max_bytes``.

    Keeps peak memory to roughly ``max_bytes`` plus one chunk, so a hostile
    multi-gigabyte upload is rejected without being fully buffered.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await reader.read(READ_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise FileTooLargeException(
                f"File exceeds the maximum allowed size of {max_bytes // (1024 * 1024)}MB"
            )
        chunks.append(chunk)
    return b"".join(chunks)


def validate_magic_bytes(content: bytes, mime_type: str) -> bool:
    """Return ``True`` if ``content`` matches the expected signature for ``mime_type``.

    Unknown MIME types return ``False`` (the allow-list already constrains the
    accepted set, so an unknown type must never be trusted).
    """
    if not content:
        return False
    if mime_type == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")
    if mime_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/webp":
        return len(content) >= 12 and content[0:4] == b"RIFF" and content[8:12] == b"WEBP"
    if mime_type == "image/heic":
        return len(content) >= 12 and content[4:8] == b"ftyp" and content[8:12] in _HEIC_BRANDS
    return False


def is_unsafe_filename(filename: str | None) -> bool:
    """Detect path-traversal / absolute / control-character filenames.

    Rejects names such as ``../../secret.txt``, ``..\\..\\secret.txt``,
    ``/etc/passwd`` and ``C:\\Windows\\system32\\file``.
    """
    if filename is None:
        return True
    if not filename.strip():
        return True
    if filename in {".", ".."}:
        return True
    if _CONTROL_CHARS.search(filename) is not None:
        return True
    if "/" in filename or "\\" in filename:
        return True
    if filename.startswith(".."):
        return True
    if _DRIVE_PREFIX.match(filename) is not None:
        return True
    return False


def sanitize_filename(filename: str | None, max_stem_length: int = 100) -> str:
    """Return a safe, storage-friendly filename.

    The result never contains path separators, traversal sequences or shell /
    control characters. If nothing usable remains, ``"image"`` is used.
    """
    raw = (filename or "").replace("\\", "/")
    base = raw.split("/")[-1]
    base = _CONTROL_CHARS.sub("", base)
    base = base.lstrip(".")
    base = _UNSAFE_CHARS.sub("", base)
    base = _MULTI_DOT.sub(".", base)
    base = base.strip(".")
    if not base:
        return "image"

    stem, dot, ext = base.rpartition(".")
    if not dot:
        stem, ext = base, ""
    stem = stem[:max_stem_length] or "image"
    ext = _UNSAFE_CHARS.sub("", ext)[:10]
    return f"{stem}.{ext}" if ext else stem


class FileValidator:
    """Validates declared MIME type, filename, size and content signature."""

    def __init__(
        self,
        *,
        allowed_mime_types: dict[ImageType, tuple[str, ...]] | None = None,
        max_file_sizes_mb: dict[ImageType, int] | None = None,
        max_filename_length: int = 100,
    ) -> None:
        self._allowed_mime_types = {
            image_type: tuple(types)
            for image_type, types in (allowed_mime_types or ALLOWED_MIME_TYPES).items()
        }
        sizes_mb = max_file_sizes_mb or DEFAULT_MAX_FILE_SIZES_MB
        self._max_file_sizes = {
            image_type: mb * 1024 * 1024 for image_type, mb in sizes_mb.items()
        }
        self._max_filename_length = max_filename_length

    @classmethod
    def from_settings(cls, settings: Settings) -> FileValidator:
        return cls(
            max_file_sizes_mb={
                ImageType.EVIDENCE: settings.max_evidence_size_mb,
                ImageType.PROGRESS: settings.max_progress_size_mb,
                ImageType.COMPLETION: settings.max_completion_size_mb,
            },
            max_filename_length=settings.max_image_filename_length,
        )

    def allowed_mime_types(self, image_type: ImageType) -> tuple[str, ...]:
        return self._allowed_mime_types.get(image_type, ())

    def max_file_size(self, image_type: ImageType) -> int:
        return self._max_file_sizes.get(image_type, 0)

    def sanitize_filename(self, filename: str | None) -> str:
        return sanitize_filename(filename, self._max_filename_length)

    def validate_declared_mime(self, declared_mime: str | None, image_type: ImageType) -> str:
        """Validate the client-declared MIME type is allowed for ``image_type``."""
        allowed = self.allowed_mime_types(image_type)
        if declared_mime is None or declared_mime.strip() == "":
            raise InvalidFileTypeException("Missing file content type")
        normalized = declared_mime.strip().lower()
        if normalized not in allowed:
            raise InvalidFileTypeException(
                f"MIME type '{declared_mime}' is not allowed for image_type '{image_type.value}'"
            )
        return normalized

    def validate_filename(self, filename: str | None) -> str:
        """Return the sanitized filename, rejecting unsafe names."""
        if is_unsafe_filename(filename):
            raise InvalidFilenameException("Filename contains invalid or unsafe characters")
        return self.sanitize_filename(filename)

    def validate_content(self, content: bytes, declared_mime: str) -> None:
        """Validate the actual file content matches the declared MIME type."""
        if not content:
            raise InvalidFileTypeException("Empty file")
        if not validate_magic_bytes(content, declared_mime):
            raise InvalidFileTypeException(
                "File content does not match the declared content type"
            )
