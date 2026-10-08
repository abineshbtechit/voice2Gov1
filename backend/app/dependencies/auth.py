"""Authentication dependency (Phase 1.2.2).

Resolves the current user from a ``Authorization: Bearer <access_token>``
header. This phase answers only *"is this token valid, and which user does it
represent?"* — no authorization/RBAC is performed here.
"""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.dependencies.services import get_user_service
from app.exceptions.base import UnauthorizedException
from app.schemas.user import UserResponse
from app.services.user_service import UserService

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

    return user
