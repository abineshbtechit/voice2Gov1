"""Rate-limit dependencies (Phase 1.3.4).

Reuses the Phase 1.2.6 in-memory :class:`RateLimiter`; it does **not** introduce
a second limiter or a Redis dependency.
"""

from fastapi import Depends, Request

from app.dependencies.auth import get_current_user
from app.middleware.rate_limit import check_image_upload_rate_limit
from app.schemas.user import UserResponse


async def image_upload_rate_limit(
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
) -> None:
    """Enforce the per-user image upload limit (10/minute)."""
    await check_image_upload_rate_limit(request, str(current_user.id))
