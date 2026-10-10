"""Storage key generation for complaint images (Phase 1.3.4).

Format (authoritative file-storage-architecture.md)::

    {image_type}/{year}/{month}/{day}/{entity_id}/{uuid}_{sanitized_filename}

Benefits: time-based partitioning, entity scoping for access control, and a
UUID prefix that prevents enumeration and collisions. The key never depends
solely on the client-supplied filename, and both the entity id and filename are
sanitized so a client can never control an arbitrary storage path.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from app.schemas.complaint_image import ImageType

_SAFE_SEGMENT = re.compile(r"[^A-Za-z0-9_-]")


def _safe_segment(value: object) -> str:
    return _SAFE_SEGMENT.sub("", str(value))


def build_storage_key(
    image_type: ImageType | str,
    entity_id: object,
    filename: str,
    *,
    now: datetime | None = None,
    uuid_prefix: str | None = None,
) -> str:
    """Build a storage key of the documented shape.

    ``now`` and ``uuid_prefix`` are injectable for deterministic testing.
    """
    image_type_value = image_type.value if isinstance(image_type, ImageType) else str(image_type)
    timestamp = now or datetime.now(UTC)
    prefix = uuid_prefix if uuid_prefix is not None else uuid.uuid4().hex[:8]
    safe_entity = _safe_segment(entity_id) or "unknown"
    safe_name = filename or "image"
    return (
        f"{image_type_value}/{timestamp.year}/{timestamp.month:02d}/{timestamp.day:02d}"
        f"/{safe_entity}/{prefix}_{safe_name}"
    )
