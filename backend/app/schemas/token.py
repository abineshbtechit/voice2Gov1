"""JWT token claim contracts and token-pair API schemas.

Access-token contract (Phase 1.2.2 — unchanged)
------------------------------------------------
``docs/authentication-rbac.md`` illustrates the full-system access payload as
``{sub, email, role, organization_id, department_id, type, iat, exp, jti}``.
Phase 1.2.2 deliberately emits a **minimal subset** (``sub``, ``type``,
``role``, ``iat``, ``exp``); ``email``, ``organization_id``,
``department_id`` and ``jti`` are deferred to later phases (RBAC AUTH-07,
tenant isolation AUTH-08; PII avoidance).

Refresh-token contract (Phase 1.2.3)
------------------------------------
The SRS refresh payload is ``{sub, type: "refresh", iat, exp, jti,
device_id}``. This phase emits the security-relevant subset:

- ``sub``  — user id; required.
- ``type`` — always ``"refresh"``; distinguishes refresh from access tokens.
- ``iat``  — issued-at (Unix seconds).
- ``exp``  — expiry (Unix seconds from ``refresh_token_expire_days``); required.
- ``jti``  — opaque unique token id (``uuid4().hex``); required. It carries no
  sensitive data and is the server-side handle used for revocation/reuse
  detection.

Deferred: ``device_id`` (push/device management, later phase).
The token-family id is **not** a claim — it is stored server-side only, so a
leaked token does not reveal the family; the family is looked up from the
stored record during rotation/reuse handling.
"""

from enum import StrEnum

from app.schemas.base import BaseSchema
from app.schemas.user import UserRole


class TokenType(StrEnum):
    """Supported token types. Access and refresh tokens are not interchangeable."""

    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(BaseSchema):
    """Validated JWT **access**-token claims (Phase 1.2.2 minimal subset)."""

    sub: str
    type: TokenType
    iat: int
    exp: int
    role: UserRole | None = None


class RefreshTokenPayload(BaseSchema):
    """Validated JWT **refresh**-token claims (Phase 1.2.3)."""

    sub: str
    type: TokenType
    iat: int
    exp: int
    jti: str


class TokenPairResponse(BaseSchema):
    """Access + refresh token pair returned by refresh/issuance.

    Field names follow ``docs/api-contract.md`` (``access_token``,
    ``refresh_token``, ``token_type``, ``expires_in``). Consistent with the
    implemented convention (register / ``/me``), the model is returned directly
    rather than wrapped in the SRS ``{success, message, data}`` envelope.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseSchema):
    """Body for ``POST /auth/refresh``."""

    refresh_token: str


class LogoutRequest(BaseSchema):
    """Body for ``POST /auth/logout``."""

    refresh_token: str


class LogoutResponse(BaseSchema):
    """Body returned by ``POST /auth/logout``."""

    message: str = "Logged out"
