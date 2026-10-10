"""Refresh-token lifecycle: issuance, rotation, reuse detection, revocation.

Security model (Phase 1.2.3):
- Raw refresh tokens are never persisted — the repository stores a SHA-256 hash.
- Every token chain belongs to a *family* (server-side id, not a claim).
- Rotation atomically revokes the presented token before issuing a successor in
  the same family; the old token becomes unusable immediately.
- Presenting an already-revoked token is treated as replay: the whole family is
  revoked and the request is rejected (``TOKEN_REVOKED``).
- Logout revokes the presented token's whole family and is idempotent.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_refresh_token,
)
from app.exceptions.base import UnauthorizedException
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.schemas.token import TokenPairResponse
from app.schemas.user import UserStatus
from app.services.user_service import UserService

# Statuses that must never be able to mint a fresh access token, even with a
# valid refresh token (Phase 1.8 hardening — defense in depth on top of the
# access-time account-status check in the authentication dependency).
_BLOCKED_STATUSES: frozenset[str] = frozenset({
    UserStatus.SUSPENDED.value,
    UserStatus.INACTIVE.value,
    UserStatus.LOCKED.value,
})


class RefreshTokenService:
    def __init__(
        self,
        repository: RefreshTokenRepository,
        user_service: UserService,
    ) -> None:
        self._repository = repository
        self._user_service = user_service

    async def issue_token_pair(
        self, user_id: str, role: str | None = None
    ) -> TokenPairResponse:
        """Issue a fresh access + refresh pair, starting a new token family.

        Not exposed by a Phase 1.2.3 endpoint (login is out of scope); the
        (later) login flow and the test-suite use it to obtain an initial
        refresh token.
        """
        now = datetime.now(UTC)
        family_id = uuid4().hex
        jti = uuid4().hex
        expires_delta = self._refresh_lifetime()

        raw = create_refresh_token(user_id, jti=jti, now=now, expires_delta=expires_delta)
        await self._repository.insert_token(
            self._build_record(raw, user_id, family_id, jti, now, now + expires_delta)
        )
        return self._pair(create_access_token(user_id, role=role), raw)

    async def rotate(self, refresh_token: str) -> TokenPairResponse:
        """Rotate a valid refresh token into a new access + refresh pair."""
        payload = decode_refresh_token(refresh_token)

        user = await self._user_service.get_user_by_id(payload.sub)
        if user is None:
            raise UnauthorizedException("Invalid refresh token", error_code="TOKEN_INVALID")

        # Phase 1.8 hardening: a suspended, inactive or locked account must not
        # be able to rotate a refresh token into a fresh access token. Generic
        # message so the response does not reveal the account state.
        status_val = user.status.value if hasattr(user.status, "value") else str(user.status)
        if status_val in _BLOCKED_STATUSES:
            raise UnauthorizedException("Account is not active", error_code="ACCOUNT_INACTIVE")

        token_hash = hash_refresh_token(refresh_token)
        now = datetime.now(UTC)
        new_jti = uuid4().hex

        record = await self._repository.revoke_if_active(
            token_hash, revoked_at=now, replaced_by=new_jti
        )
        if record is None:
            existing = await self._repository.find_by_token_hash(token_hash)
            if existing is not None:
                # Replay of an already-revoked token -> the family is compromised.
                await self._repository.revoke_family(
                    str(existing["family_id"]),
                    revoked_at=now,
                    reuse_detected=True,
                )
                raise UnauthorizedException(
                    "Refresh token has been revoked", error_code="TOKEN_REVOKED"
                )
            raise UnauthorizedException("Invalid refresh token", error_code="TOKEN_INVALID")

        family_id = str(record["family_id"])
        expires_delta = self._refresh_lifetime()
        raw = create_refresh_token(
            payload.sub, jti=new_jti, now=now, expires_delta=expires_delta
        )
        await self._repository.insert_token(
            self._build_record(raw, payload.sub, family_id, new_jti, now, now + expires_delta)
        )
        return self._pair(create_access_token(payload.sub, role=user.role), raw)

    async def revoke(self, refresh_token: str) -> None:
        """Logout: revoke the family of the presented refresh token.

        Idempotent and never raises for invalid/expired/unknown tokens, so
        logout cannot be used as a token oracle and works even after the token
        has expired.
        """
        try:
            decode_refresh_token(refresh_token)
        except UnauthorizedException:
            return

        record = await self._repository.find_by_token_hash(hash_refresh_token(refresh_token))
        if record is None:
            return

        await self._repository.revoke_family(
            str(record["family_id"]), revoked_at=datetime.now(UTC)
        )

    @staticmethod
    def _refresh_lifetime() -> timedelta:
        return timedelta(days=settings.refresh_token_expire_days)

    @staticmethod
    def _build_record(
        raw: str,
        user_id: str,
        family_id: str,
        jti: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> dict[str, Any]:
        return {
            "user_id": str(user_id),
            "family_id": family_id,
            "jti": jti,
            "token_hash": hash_refresh_token(raw),
            "expires_at": expires_at,
            "created_at": created_at,
            "revoked_at": None,
            "replaced_by": None,
            "reuse_detected": False,
        }

    @staticmethod
    def _pair(access_token: str, refresh_token: str) -> TokenPairResponse:
        return TokenPairResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60,
        )
