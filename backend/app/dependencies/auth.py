"""Authentication dependency (Phase 1.2.2 / Phase 1.8 hardening).

Resolves the current user from a ``Authorization: Bearer <access_token>``
header.  In addition to token signature/expiry validation this dependency now
enforces real-time account-status checks so that a suspended, inactive or
locked user cannot authenticate with a still-valid access token.
"""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.dependencies.services import get_user_service
from app.exceptions.base import UnauthorizedException
from app.schemas.user import UserResponse, UserStatus
from app.services.user_service import UserService

# Statuses that must be rejected at authentication time even if the token
# signature and expiry are otherwise valid.
_BLOCKED_STATUSES: frozenset[str] = frozenset({
    UserStatus.SUSPENDED.value,
    UserStatus.INACTIVE.value,
    UserStatus.LOCKED.value,
})

# auto_error=False so we control the failure response (consistent error
# contract) instead of FastAPI's default 403 for missing credentials.
bearer_scheme = HTTPBearer(
    auto_error=False,
    description="JWT access token (Authorization: Bearer <token>)",
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Resolve the authenticated user from the Bearer access token.

    Raises ``UnauthorizedException`` (401, safe message, stable error code) for
    missing, malformed, invalid, expired or tampered tokens, for tokens whose
    ``sub`` does not resolve to a user, and for a token missing ``sub``.
    """
    if credentials is None or not credentials.credentials:
        raise UnauthorizedException(
            "Authentication credentials were not provided",
            error_code="TOKEN_INVALID",
        )

    payload = decode_access_token(credentials.credentials)

    user = await service.get_user_by_id(payload.sub)
    if user is None:
        # Valid signature but the user no longer exists — never auto-create.
        raise UnauthorizedException(
            "Invalid access token",
            error_code="TOKEN_INVALID",
        )

    # Phase 1.8 hardening: reject suspended/inactive/locked accounts even
    # when the access token has not yet expired.  Generic 401 message so we
    # do not reveal *why* the account was deactivated.
    status_val = user.status.value if hasattr(user.status, "value") else str(user.status)
    if status_val in _BLOCKED_STATUSES:
        raise UnauthorizedException(
            "Account is not active",
            error_code="ACCOUNT_INACTIVE",
        )

    return user


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    service: UserService = Depends(get_user_service),
) -> UserResponse | None:
    """Resolve the authenticated user if credentials are provided, else None."""
    if credentials is None or not credentials.credentials:
        return None

    try:
        payload = decode_access_token(credentials.credentials)
        return await service.get_user_by_id(payload.sub)
    except Exception:
        return None

