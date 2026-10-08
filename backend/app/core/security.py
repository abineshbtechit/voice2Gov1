
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import ExpiredSignatureError, JWTError, jwt
from pydantic import ValidationError

from app.core.config import settings
from app.exceptions.base import UnauthorizedException
from app.schemas.token import RefreshTokenPayload, TokenPayload, TokenType


def hash_password(password: str) -> str:
    """Hash a password using bcrypt with configured rounds."""
    if not password:
        raise ValueError("Password cannot be empty")
    salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a bcrypt hash."""
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def validate_password_policy(password: str) -> tuple[bool, list[str]]:
    """
    Validate password against policy.
    Returns (is_valid, list_of_errors).
    """
    errors = []

    if not password:
        errors.append("Password cannot be empty")
        return False, errors

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")

    if len(password) > 128:
        errors.append("Password must not exceed 128 characters")

    # Check for at least one uppercase letter
    if not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")

    # Check for at least one lowercase letter
    if not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")

    # Check for at least one digit
    if not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit")

    # Check for at least one special character
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(c in special_chars for c in password):
        errors.append("Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)")

    return len(errors) == 0, errors


def create_access_token(
    user_id: str,
    role: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token for ``user_id``.

    Claims: ``sub``, ``type``, ``iat``, ``exp`` and (optionally) ``role``.
    The secret, algorithm and default lifetime all come from settings; the
    lifetime is only overridable for tests. No refresh token is created.
    """
    now = datetime.now(UTC)
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    claims: dict[str, Any] = {
        "sub": str(user_id),
        "type": TokenType.ACCESS.value,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    if role is not None:
        claims["role"] = role

    token: str = jwt.encode(claims, settings.secret_key, algorithm=settings.algorithm)
    return token


def decode_access_token(token: str) -> TokenPayload:
    """Decode and fully validate a JWT access token.

    Verifies the signature and expiry, then enforces the required claim
    contract. Raises ``UnauthorizedException`` with a stable, safe error code
    (``TOKEN_EXPIRED`` / ``TOKEN_INVALID``) — it never returns an unverified
    payload and never leaks secrets.
    """
    if not token:
        raise UnauthorizedException("Invalid access token", error_code="TOKEN_INVALID")

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except ExpiredSignatureError as exc:
        raise UnauthorizedException(
            "Access token has expired", error_code="TOKEN_EXPIRED"
        ) from exc
    except JWTError as exc:
        raise UnauthorizedException(
            "Invalid access token", error_code="TOKEN_INVALID"
        ) from exc

    try:
        model = TokenPayload.model_validate(payload)
    except ValidationError as exc:
        raise UnauthorizedException(
            "Invalid access token", error_code="TOKEN_INVALID"
        ) from exc

    # A refresh token must never be accepted as an access token.
    if model.type != TokenType.ACCESS:
        raise UnauthorizedException("Invalid access token", error_code="TOKEN_INVALID")

    return model


def create_refresh_token(
    user_id: str,
    jti: str,
    now: datetime | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT refresh token for ``user_id``.

    Claims: ``sub``, ``type``, ``iat``, ``exp``, ``jti``. The family id is a
    server-side concept and is deliberately **not** a claim. Lifetime comes
    from ``settings.refresh_token_expire_days`` unless overridden (tests).
    """
    if now is None:
        now = datetime.now(UTC)
    if expires_delta is None:
        expires_delta = timedelta(days=settings.refresh_token_expire_days)

    claims: dict[str, Any] = {
        "sub": str(user_id),
        "type": TokenType.REFRESH.value,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": str(jti),
    }
    token: str = jwt.encode(claims, settings.secret_key, algorithm=settings.algorithm)
    return token


def decode_refresh_token(token: str) -> RefreshTokenPayload:
    """Decode and fully validate a JWT refresh token.

    Verifies the signature and expiry, then enforces the refresh claim
    contract (``sub``, ``type``, ``jti``, ``exp``). An access token is rejected
    here because its ``type`` is not ``refresh``.
    """
    if not token:
        raise UnauthorizedException("Invalid refresh token", error_code="TOKEN_INVALID")

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except ExpiredSignatureError as exc:
        raise UnauthorizedException(
            "Refresh token has expired", error_code="TOKEN_EXPIRED"
        ) from exc
    except JWTError as exc:
        raise UnauthorizedException(
            "Invalid refresh token", error_code="TOKEN_INVALID"
        ) from exc

    try:
        model = RefreshTokenPayload.model_validate(payload)
    except ValidationError as exc:
        raise UnauthorizedException(
            "Invalid refresh token", error_code="TOKEN_INVALID"
        ) from exc

    if model.type != TokenType.REFRESH:
        raise UnauthorizedException("Invalid refresh token", error_code="TOKEN_INVALID")

    return model


def hash_refresh_token(token: str) -> str:
    """Return the deterministic SHA-256 hex digest used to store a refresh token.

    Refresh tokens are high-entropy signed JWTs, so a fast unsalted hash is
    appropriate and — unlike bcrypt — deterministic, which is required to look
    the record up by hash. Password hashing (bcrypt) is a separate concern.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
