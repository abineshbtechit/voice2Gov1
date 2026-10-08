"""Phase 1.2.1 — password hashing and password policy tests.

Covers the PASSWORD requirements:
- plaintext is never stored / returned
- bcrypt is used and produces a valid bcrypt hash
- bcrypt uses a random salt (same password -> different hashes)
- correct password verifies, incorrect fails
- password policy: min/max length, upper, lower, digit, special
"""

import re

import pytest

from app.core.security import (
    hash_password,
    validate_password_policy,
    verify_password,
)

# bcrypt modular crypt format: $2<variant>$<cost>$<22 char salt><31 char digest>
BCRYPT_PATTERN = re.compile(r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$")

VALID_PASSWORD = "SecurePass123!"


class TestPasswordHashing:
    """bcrypt hashing behaviour."""

    def test_hash_is_never_plaintext(self) -> None:
        hashed = hash_password(VALID_PASSWORD)
        assert hashed != VALID_PASSWORD
        assert VALID_PASSWORD not in hashed

    def test_bcrypt_is_used(self) -> None:
        hashed = hash_password(VALID_PASSWORD)
        assert hashed.startswith("$2b$")
        assert hashed.startswith("$2")

    def test_hash_is_valid_bcrypt_format(self) -> None:
        hashed = hash_password(VALID_PASSWORD)
        assert BCRYPT_PATTERN.match(hashed), f"not a valid bcrypt hash: {hashed!r}"
        assert len(hashed) == 60

    def test_same_password_produces_different_hashes(self) -> None:
        """bcrypt salts randomly: hashes must differ but both must verify."""
        hash1 = hash_password(VALID_PASSWORD)
        hash2 = hash_password(VALID_PASSWORD)

        assert hash1 != hash2
        assert verify_password(VALID_PASSWORD, hash1) is True
        assert verify_password(VALID_PASSWORD, hash2) is True

    def test_hash_password_rejects_empty(self) -> None:
        with pytest.raises(ValueError):
            hash_password("")


class TestPasswordVerification:
    def test_correct_password_verifies(self) -> None:
        hashed = hash_password(VALID_PASSWORD)
        assert verify_password(VALID_PASSWORD, hashed) is True

    def test_incorrect_password_fails(self) -> None:
        hashed = hash_password(VALID_PASSWORD)
        assert verify_password("WrongPassword123!", hashed) is False

    def test_verification_is_case_sensitive(self) -> None:
        hashed = hash_password(VALID_PASSWORD)
        assert verify_password(VALID_PASSWORD.lower(), hashed) is False

    def test_invalid_hash_returns_false(self) -> None:
        assert verify_password(VALID_PASSWORD, "not-a-bcrypt-hash") is False

    def test_empty_inputs_return_false(self) -> None:
        assert verify_password("", "hash") is False
        assert verify_password(VALID_PASSWORD, "") is False


class TestPasswordPolicy:
    def test_valid_password_passes(self) -> None:
        is_valid, errors = validate_password_policy(VALID_PASSWORD)
        assert is_valid is True
        assert errors == []

    def test_minimum_length_enforced(self) -> None:
        is_valid, errors = validate_password_policy("Ab1!xyz")  # 7 chars
        assert is_valid is False
        assert any("8" in e for e in errors)

    def test_exactly_eight_characters_passes(self) -> None:
        is_valid, errors = validate_password_policy("Abcdef1!")
        assert is_valid is True

    def test_maximum_length_enforced(self) -> None:
        long_password = "A" * 126 + "a1!"  # 129 characters
        assert len(long_password) == 129
        is_valid, errors = validate_password_policy(long_password)
        assert is_valid is False
        assert any("128" in e for e in errors)

    def test_one_hundred_28_characters_passes(self) -> None:
        ok_password = "A" * 125 + "a1!"
        assert len(ok_password) == 128
        is_valid, errors = validate_password_policy(ok_password)
        assert is_valid is True

    def test_uppercase_required(self) -> None:
        is_valid, errors = validate_password_policy("lowercase1!")
        assert is_valid is False
        assert any("uppercase" in e for e in errors)

    def test_lowercase_required(self) -> None:
        is_valid, errors = validate_password_policy("UPPERCASE1!")
        assert is_valid is False
        assert any("lowercase" in e for e in errors)

    def test_digit_required(self) -> None:
        is_valid, errors = validate_password_policy("NoDigits!!")
        assert is_valid is False
        assert any("digit" in e for e in errors)

    def test_special_character_required(self) -> None:
        is_valid, errors = validate_password_policy("NoSpecial123")
        assert is_valid is False
        assert any("special" in e.lower() for e in errors)

    def test_empty_password_fails(self) -> None:
        is_valid, errors = validate_password_policy("")
        assert is_valid is False
        assert any("empty" in e.lower() for e in errors)

    @pytest.mark.parametrize(
        "weak",
        [
            "password",  # no upper, digit, special
            "12345678",  # no letters, special
            "PASSWORD",  # no lower, digit, special
            "Password",  # no digit, special
            "Password1",  # no special
            "Password!",  # no digit
            "Sh0rt!",  # too short (6 chars)
        ],
    )
    def test_weak_passwords_are_rejected(self, weak: str) -> None:
        is_valid, _ = validate_password_policy(weak)
        assert is_valid is False
