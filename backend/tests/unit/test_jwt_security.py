"""Phase 1.2.2 — JWT access-token creation/validation unit tests.

Covers: valid token creation, JWT structure, claims (sub/exp/iat/type/role),
configured algorithm + secret, expiration from configuration, and rejection of
wrong-secret, tampered, malformed, expired, and missing-claim tokens.
"""

import base64
import json
import time
from datetime import timedelta

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token
from app.exceptions.base import UnauthorizedException
from app.schemas.token import TokenPayload, TokenType
from tests.fakes import tamper_token

USER_ID = "507f1f77bcf86cd799439011"


class TestCreateAccessToken:
    def test_creates_a_valid_jwt(self) -> None:
        token = create_access_token(USER_ID, role="citizen")
        assert isinstance(token, str)
        assert token.count(".") == 2  # header.payload.signature

    def test_contains_sub_exp_and_iat(self) -> None:
        claims = jwt.get_unverified_claims(create_access_token(USER_ID, role="citizen"))
        assert claims["sub"] == USER_ID
        assert "exp" in claims
        assert "iat" in claims

    def test_type_claim_is_access(self) -> None:
        claims = jwt.get_unverified_claims(create_access_token(USER_ID))
        assert claims["type"] == TokenType.ACCESS.value == "access"

    def test_role_claim_included_when_supplied(self) -> None:
        claims = jwt.get_unverified_claims(create_access_token(USER_ID, role="citizen"))
        assert claims["role"] == "citizen"

    def test_uses_configured_algorithm(self) -> None:
        header = jwt.get_unverified_header(create_access_token(USER_ID))
        assert header["alg"] == settings.algorithm

    def test_expiration_is_calculated_from_configuration(self) -> None:
        claims = jwt.get_unverified_claims(create_access_token(USER_ID))
        expected = settings.access_token_expire_minutes * 60
        assert claims["exp"] - claims["iat"] == expected

    def test_expiration_respects_explicit_delta(self) -> None:
        claims = jwt.get_unverified_claims(
            create_access_token(USER_ID, expires_delta=timedelta(minutes=5))
        )
        assert claims["exp"] - claims["iat"] == 300

    def test_token_does_not_contain_password_or_hash(self) -> None:
        claims = jwt.get_unverified_claims(create_access_token(USER_ID, role="citizen"))
        assert "password" not in claims
        assert "password_hash" not in claims

    def test_token_contains_no_unnecessary_personal_information(self) -> None:
        claims = jwt.get_unverified_claims(create_access_token(USER_ID, role="citizen"))
        assert "phone" not in claims
        assert "email" not in claims
        assert set(claims) <= {"sub", "type", "iat", "exp", "role"}

    def test_emits_the_minimal_srs_subset_exactly(self) -> None:
        """SRS reconciliation: Phase 1.2.2 emits only the minimal subset."""
        claims = jwt.get_unverified_claims(create_access_token(USER_ID, role="citizen"))

        assert set(claims) == {"sub", "type", "iat", "exp", "role"}
        for deferred in ("email", "organization_id", "department_id", "jti"):
            assert deferred not in claims

    def test_role_omitted_when_not_supplied(self) -> None:
        claims = jwt.get_unverified_claims(create_access_token(USER_ID))
        assert set(claims) == {"sub", "type", "iat", "exp"}


class TestDecodeAccessToken:
    def test_decodes_with_correct_secret(self) -> None:
        payload = decode_access_token(create_access_token(USER_ID, role="citizen"))

        assert isinstance(payload, TokenPayload)
        assert payload.sub == USER_ID
        assert payload.type == TokenType.ACCESS
        assert payload.role == "citizen"
        assert payload.exp > payload.iat

    def test_wrong_secret_fails(self) -> None:
        now = int(time.time())
        token = jwt.encode(
            {"sub": USER_ID, "type": "access", "iat": now, "exp": now + 60},
            "a-different-secret",
            algorithm=settings.algorithm,
        )

        with pytest.raises(UnauthorizedException) as exc:
            decode_access_token(token)

        assert exc.value.error_code == "TOKEN_INVALID"

    def test_tampered_token_fails(self) -> None:
        tampered = tamper_token(create_access_token(USER_ID))

        with pytest.raises(UnauthorizedException) as exc:
            decode_access_token(tampered)

        assert exc.value.error_code == "TOKEN_INVALID"

    def test_malformed_token_fails(self) -> None:
        with pytest.raises(UnauthorizedException) as exc:
            decode_access_token("this-is-not-a-jwt")

        assert exc.value.error_code == "TOKEN_INVALID"

    def test_empty_token_fails(self) -> None:
        with pytest.raises(UnauthorizedException) as exc:
            decode_access_token("")

        assert exc.value.error_code == "TOKEN_INVALID"

    def test_expired_token_fails(self) -> None:
        token = create_access_token(USER_ID, expires_delta=timedelta(seconds=-10))

        with pytest.raises(UnauthorizedException) as exc:
            decode_access_token(token)

        assert exc.value.error_code == "TOKEN_EXPIRED"

    def test_token_missing_sub_fails(self) -> None:
        now = int(time.time())
        token = jwt.encode(
            {"type": "access", "iat": now, "exp": now + 60},
            settings.secret_key,
            algorithm=settings.algorithm,
        )

        with pytest.raises(UnauthorizedException) as exc:
            decode_access_token(token)

        assert exc.value.error_code == "TOKEN_INVALID"

    def test_token_missing_exp_fails(self) -> None:
        now = int(time.time())
        token = jwt.encode(
            {"sub": USER_ID, "type": "access", "iat": now},
            settings.secret_key,
            algorithm=settings.algorithm,
        )

        with pytest.raises(UnauthorizedException) as exc:
            decode_access_token(token)

        assert exc.value.error_code == "TOKEN_INVALID"

    def test_token_missing_type_fails(self) -> None:
        now = int(time.time())
        token = jwt.encode(
            {"sub": USER_ID, "iat": now, "exp": now + 60},
            settings.secret_key,
            algorithm=settings.algorithm,
        )

        with pytest.raises(UnauthorizedException):
            decode_access_token(token)

    def test_decode_never_returns_unverified_payload(self) -> None:
        """A hand-crafted unsigned (``alg=none``) token must not be accepted."""

        def _b64(obj: dict[str, object]) -> str:
            raw = json.dumps(obj, separators=(",", ":")).encode()
            return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

        claims = {"sub": USER_ID, "type": "access", "iat": 1, "exp": 9999999999}
        unsigned = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(claims)}."

        with pytest.raises(UnauthorizedException) as exc:
            decode_access_token(unsigned)

        assert exc.value.error_code == "TOKEN_INVALID"
