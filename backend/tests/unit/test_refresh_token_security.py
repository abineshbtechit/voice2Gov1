"""Phase 1.2.3 — refresh-token creation / hashing / claim-contract tests."""

import base64
import json
import time
from datetime import timedelta

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_refresh_token,
)
from app.exceptions.base import UnauthorizedException
from app.schemas.token import RefreshTokenPayload, TokenType
from tests.fakes import tamper_token

USER_ID = "507f1f77bcf86cd799439011"
JTI = "1f0e2d3c4b5a69788796a5b4c3d2e1f0"


class TestCreateRefreshToken:
    def test_creates_a_valid_jwt(self) -> None:
        token = create_refresh_token(USER_ID, jti=JTI)
        assert isinstance(token, str)
        assert token.count(".") == 2

    def test_type_claim_is_refresh(self) -> None:
        claims = jwt.get_unverified_claims(create_refresh_token(USER_ID, jti=JTI))
        assert claims["type"] == TokenType.REFRESH.value == "refresh"

    def test_contains_required_claims(self) -> None:
        claims = jwt.get_unverified_claims(create_refresh_token(USER_ID, jti=JTI))
        assert claims["sub"] == USER_ID
        assert claims["jti"] == JTI
        assert "iat" in claims
        assert "exp" in claims

    def test_expiry_comes_from_configuration(self) -> None:
        claims = jwt.get_unverified_claims(create_refresh_token(USER_ID, jti=JTI))
        assert claims["exp"] - claims["iat"] == settings.refresh_token_expire_days * 86400

    def test_jti_is_unique_per_token(self) -> None:
        first = jwt.get_unverified_claims(create_refresh_token(USER_ID, jti="a" * 32))
        second = jwt.get_unverified_claims(create_refresh_token(USER_ID, jti="b" * 32))
        assert first["jti"] != second["jti"]

    def test_contains_no_password_or_sensitive_data(self) -> None:
        claims = jwt.get_unverified_claims(create_refresh_token(USER_ID, jti=JTI))
        assert "password" not in claims
        assert "password_hash" not in claims
        assert "phone" not in claims
        assert "email" not in claims
        assert set(claims) == {"sub", "type", "iat", "exp", "jti"}

    def test_family_id_is_not_a_claim(self) -> None:
        claims = jwt.get_unverified_claims(create_refresh_token(USER_ID, jti=JTI))
        assert "family_id" not in claims


class TestDecodeRefreshToken:
    def test_valid_token_decodes(self) -> None:
        payload = decode_refresh_token(create_refresh_token(USER_ID, jti=JTI))
        assert isinstance(payload, RefreshTokenPayload)
        assert payload.sub == USER_ID
        assert payload.jti == JTI
        assert payload.type == TokenType.REFRESH
        assert payload.exp > payload.iat

    def test_wrong_secret_fails(self) -> None:
        now = int(time.time())
        token = jwt.encode(
            {"sub": USER_ID, "type": "refresh", "iat": now, "exp": now + 60, "jti": JTI},
            "a-different-secret",
            algorithm=settings.algorithm,
        )
        with pytest.raises(UnauthorizedException) as exc:
            decode_refresh_token(token)
        assert exc.value.error_code == "TOKEN_INVALID"

    def test_malformed_fails(self) -> None:
        with pytest.raises(UnauthorizedException) as exc:
            decode_refresh_token("not-a-jwt")
        assert exc.value.error_code == "TOKEN_INVALID"

    def test_empty_fails(self) -> None:
        with pytest.raises(UnauthorizedException):
            decode_refresh_token("")

    def test_tampered_fails(self) -> None:
        with pytest.raises(UnauthorizedException) as exc:
            decode_refresh_token(tamper_token(create_refresh_token(USER_ID, jti=JTI)))
        assert exc.value.error_code == "TOKEN_INVALID"

    def test_expired_fails(self) -> None:
        token = create_refresh_token(
            USER_ID, jti=JTI, expires_delta=timedelta(seconds=-5)
        )
        with pytest.raises(UnauthorizedException) as exc:
            decode_refresh_token(token)
        assert exc.value.error_code == "TOKEN_EXPIRED"

    def test_missing_jti_fails(self) -> None:
        now = int(time.time())
        token = jwt.encode(
            {"sub": USER_ID, "type": "refresh", "iat": now, "exp": now + 60},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        with pytest.raises(UnauthorizedException):
            decode_refresh_token(token)

    def test_missing_sub_fails(self) -> None:
        now = int(time.time())
        token = jwt.encode(
            {"type": "refresh", "iat": now, "exp": now + 60, "jti": JTI},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        with pytest.raises(UnauthorizedException):
            decode_refresh_token(token)

    def test_unsigned_token_fails(self) -> None:
        def _b64(obj: dict[str, object]) -> str:
            raw = json.dumps(obj, separators=(",", ":")).encode()
            return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

        claims = {"sub": USER_ID, "type": "refresh", "iat": 1, "exp": 9999999999, "jti": JTI}
        unsigned = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(claims)}."
        with pytest.raises(UnauthorizedException):
            decode_refresh_token(unsigned)


class TestTokenTypeSeparation:
    """Access and refresh tokens are not interchangeable."""

    def test_access_token_rejected_by_refresh_decoder(self) -> None:
        with pytest.raises(UnauthorizedException) as exc:
            decode_refresh_token(create_access_token(USER_ID, role="citizen"))
        assert exc.value.error_code == "TOKEN_INVALID"

    def test_refresh_token_rejected_by_access_decoder(self) -> None:
        with pytest.raises(UnauthorizedException) as exc:
            decode_access_token(create_refresh_token(USER_ID, jti=JTI))
        assert exc.value.error_code == "TOKEN_INVALID"


class TestHashRefreshToken:
    def test_is_deterministic_for_lookup(self) -> None:
        token = create_refresh_token(USER_ID, jti=JTI)
        assert hash_refresh_token(token) == hash_refresh_token(token)

    def test_is_sha256_hex(self) -> None:
        digest = hash_refresh_token(create_refresh_token(USER_ID, jti=JTI))
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_differs_per_token(self) -> None:
        first = hash_refresh_token(create_refresh_token(USER_ID, jti="a" * 32))
        second = hash_refresh_token(create_refresh_token(USER_ID, jti="b" * 32))
        assert first != second

    def test_raw_token_is_not_recoverable_from_hash(self) -> None:
        token = create_refresh_token(USER_ID, jti=JTI)
        digest = hash_refresh_token(token)
        assert digest != token
        assert token not in digest
        assert not digest.startswith("$2")  # not bcrypt (password hashing)
