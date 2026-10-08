from fastapi import APIRouter, Depends, status

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_refresh_token_service, get_user_service
from app.middleware.rate_limit import rate_limit_auth
from app.schemas.token import (
    LogoutRequest,
    LogoutResponse,
    RefreshTokenRequest,
    TokenPairResponse,
)
from app.schemas.user import (
    UserLoginRequest,
    UserLoginResponse,
    UserRegisterRequest,
    UserRegisterResponse,
    UserResponse,
)
from app.services.token_service import RefreshTokenService
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["authentication"])

# Re-exported so existing consumers (and Phase 1.2.1 tests) can keep importing
# ``get_user_service`` from this module; it is the same dependency object.
__all__ = ["router", "get_user_service"]


@router.post(
    "/register",
    response_model=UserRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Register a new citizen user with email, phone, and password.",
    dependencies=[Depends(rate_limit_auth)],
)
async def register(
    request: UserRegisterRequest,
    service: UserService = Depends(get_user_service),
) -> UserRegisterResponse:
    """Register a new citizen user.

    Domain failures raise :class:`AppException` subclasses
    (``ConflictException`` / ``ValidationException``) which the globally
    registered ``app_exception_handler`` renders as a structured error body
    with the correct status code.
    """
    return await service.register(request)


@router.post(
    "/login",
    response_model=UserLoginResponse,
    summary="User login",
    description="Authenticate user with email/phone and password. Returns access and refresh token pair.",
    dependencies=[Depends(rate_limit_auth)],
)
async def login(
    request: UserLoginRequest,
    user_service: UserService = Depends(get_user_service),
    token_service: RefreshTokenService = Depends(get_refresh_token_service),
) -> UserLoginResponse:
    """Authenticate user and issue access + refresh token pair.

    Returns generic error message to prevent user enumeration.
    Implements account lockout after failed attempts.
    """
    return await user_service.login(request, token_service)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="Return the authenticated user's safe profile (Bearer access token).",
)
async def read_current_user(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """Return the authenticated user's safe profile."""
    return current_user


@router.post(
    "/refresh",
    response_model=TokenPairResponse,
    summary="Rotate refresh token",
    description=(
        "Exchange a valid refresh token (request body) for a new access + "
        "refresh token pair. The presented token is rotated and cannot be reused."
    ),
)
async def refresh_tokens(
    request: RefreshTokenRequest,
    service: RefreshTokenService = Depends(get_refresh_token_service),
) -> TokenPairResponse:
    """Rotate a refresh token into a new access + refresh pair."""
    return await service.rotate(request.refresh_token)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Logout",
    description=(
        "Revoke the refresh-token family associated with the presented refresh "
        "token. Idempotent; does not require a password or an access token."
    ),
)
async def logout(
    request: LogoutRequest,
    service: RefreshTokenService = Depends(get_refresh_token_service),
) -> LogoutResponse:
    """Revoke the refresh-token family for the presented refresh token."""
    await service.revoke(request.refresh_token)
    return LogoutResponse(message="Logged out")
