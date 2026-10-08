"""Phase 1.2.3 — refresh-token service: issuance, rotation, reuse, logout."""

import asyncio
from datetime import UTC, datetime

import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    decode_refresh_token,
    hash_refresh_token,
)
from app.exceptions.base import UnauthorizedException
from app.schemas.token import TokenType
from app.services.token_service import RefreshTokenService
from app.services.user_service import UserService
from tests.fakes import FakeRefreshTokenRepository, FakeUserRepository

USER_ID = "507f1f77bcf86cd799439011"


@pytest.fixture
def user_repository() -> FakeUserRepository:
    repo = FakeUserRepository()
    repo.seed(USER_ID, role="citizen")
    return repo


@pytest.fixture
def token_repository() -> FakeRefreshTokenRepository:
    return FakeRefreshTokenRepository()


@pytest.fixture
def service(
    token_repository: FakeRefreshTokenRepository, user_repository: FakeUserRepository
) -> RefreshTokenService:
    return RefreshTokenService(token_repository, UserService(user_repository))  # type: ignore[arg-type]


class TestIssuance:
    async def test_issues_access_and_refresh_pair(self, service: RefreshTokenService) -> None:
        pair = await service.issue_token_pair(USER_ID, role="citizen")

        assert decode_access_token(pair.access_token).sub == USER_ID
        assert decode_refresh_token(pair.refresh_token).sub == USER_ID
        assert pair.token_type == "bearer"
        assert pair.expires_in > 0

    async def test_stores_hash_not_raw_token(
        self, service: RefreshTokenService, token_repository: FakeRefreshTokenRepository
    ) -> None:
        pair = await service.issue_token_pair(USER_ID)

        assert len(token_repository.records) == 1
        record = next(iter(token_repository.records.values()))
        assert record["token_hash"] == hash_refresh_token(pair.refresh_token)
        assert record["token_hash"] != pair.refresh_token
        assert pair.refresh_token not in str(record)

    async def test_record_has_family_jti_and_expiry(
        self, service: RefreshTokenService, token_repository: FakeRefreshTokenRepository
    ) -> None:
        pair = await service.issue_token_pair(USER_ID)
        record = next(iter(token_repository.records.values()))

        payload = decode_refresh_token(pair.refresh_token)
        assert record["family_id"]
        assert record["jti"] == payload.jti
        assert record["revoked_at"] is None
        assert record["reuse_detected"] is False
        assert record["expires_at"] > datetime.now(UTC)


class TestRotation:
    async def test_valid_refresh_succeeds_and_issues_new_pair(
        self, service: RefreshTokenService
    ) -> None:
        first = await service.issue_token_pair(USER_ID, role="citizen")

        rotated = await service.rotate(first.refresh_token)

        # A new, valid access token is issued for the same user.
        new_access = decode_access_token(rotated.access_token)
        assert new_access.sub == USER_ID
        assert new_access.type == TokenType.ACCESS
        # The refresh token is rotated: new token, new jti.
        assert rotated.refresh_token != first.refresh_token
        assert decode_refresh_token(rotated.refresh_token).jti != decode_refresh_token(
            first.refresh_token
        ).jti

    async def test_rotation_preserves_family_and_revokes_old(
        self, service: RefreshTokenService, token_repository: FakeRefreshTokenRepository
    ) -> None:
        first = await service.issue_token_pair(USER_ID)
        rotated = await service.rotate(first.refresh_token)

        families = {r["family_id"] for r in token_repository.records.values()}
        assert len(families) == 1

        old = await token_repository.find_by_token_hash(hash_refresh_token(first.refresh_token))
        assert old is not None
        assert old["revoked_at"] is not None
        assert old["replaced_by"] == decode_refresh_token(rotated.refresh_token).jti

    async def test_old_token_becomes_unusable(self, service: RefreshTokenService) -> None:
        first = await service.issue_token_pair(USER_ID)
        await service.rotate(first.refresh_token)

        with pytest.raises(UnauthorizedException) as exc:
            await service.rotate(first.refresh_token)

        assert exc.value.error_code == "TOKEN_REVOKED"

    async def test_nonexistent_user_rejected(
        self, token_repository: FakeRefreshTokenRepository
    ) -> None:
        empty_users = FakeUserRepository()  # no users seeded
        service = RefreshTokenService(token_repository, UserService(empty_users))  # type: ignore[arg-type]
        issued = await service.issue_token_pair(USER_ID)

        with pytest.raises(UnauthorizedException) as exc:
            await service.rotate(issued.refresh_token)

        assert exc.value.error_code == "TOKEN_INVALID"

    async def test_access_token_rejected_by_refresh(
        self, service: RefreshTokenService
    ) -> None:
        with pytest.raises(UnauthorizedException) as exc:
            await service.rotate(create_access_token(USER_ID, role="citizen"))

        assert exc.value.error_code == "TOKEN_INVALID"

    async def test_concurrent_rotation_only_one_succeeds(
        self, service: RefreshTokenService
    ) -> None:
        """Two simultaneous uses of the same token must not both rotate it.

        The guarded ``revoke_if_active`` predicate guarantees only one caller
        can revoke an active token (enforced by a single MongoDB
        ``find_one_and_update``); the loser sees the token as already revoked.
        """
        issued = await service.issue_token_pair(USER_ID)

        results = await asyncio.gather(
            service.rotate(issued.refresh_token),
            service.rotate(issued.refresh_token),
            return_exceptions=True,
        )
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]

        assert len(successes) == 1
        assert len(failures) == 1
        assert isinstance(failures[0], UnauthorizedException)
        assert failures[0].error_code == "TOKEN_REVOKED"


class TestReuseDetection:
    async def test_reuse_revokes_whole_family(
        self, service: RefreshTokenService, token_repository: FakeRefreshTokenRepository
    ) -> None:
        first = await service.issue_token_pair(USER_ID)
        rotated = await service.rotate(first.refresh_token)

        # Replay the already-rotated token.
        with pytest.raises(UnauthorizedException) as exc:
            await service.rotate(first.refresh_token)
        assert exc.value.error_code == "TOKEN_REVOKED"

        # The legitimately-issued successor is now dead too (family compromised).
        assert all(r["revoked_at"] is not None for r in token_repository.records.values())
        assert any(r["reuse_detected"] for r in token_repository.records.values())

        with pytest.raises(UnauthorizedException) as exc2:
            await service.rotate(rotated.refresh_token)
        assert exc2.value.error_code == "TOKEN_REVOKED"


class TestRevocationAndLogout:
    async def test_logout_revokes_family(self, service: RefreshTokenService) -> None:
        issued = await service.issue_token_pair(USER_ID)

        await service.revoke(issued.refresh_token)

        with pytest.raises(UnauthorizedException) as exc:
            await service.rotate(issued.refresh_token)
        assert exc.value.error_code == "TOKEN_REVOKED"

    async def test_logout_is_idempotent_for_invalid_token(
        self, service: RefreshTokenService
    ) -> None:
        # Must not raise and must not leak whether the token existed.
        await service.revoke("not-a-jwt")
        await service.revoke("")

    async def test_logout_for_unknown_signed_token_does_not_raise(
        self, service: RefreshTokenService
    ) -> None:
        from app.core.security import create_refresh_token

        stray = create_refresh_token(USER_ID, jti="f" * 32)
        await service.revoke(stray)  # valid signature, no stored record
