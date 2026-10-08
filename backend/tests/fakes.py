"""Shared in-memory test doubles (no MongoDB required)."""

from datetime import UTC, datetime
from typing import Any

from app.schemas.token import TokenPairResponse


def tamper_token(token: str) -> str:
    """Return a copy of ``token`` with an altered payload segment.

    Changing a payload character guarantees the signed bytes differ, so
    signature verification must fail. (Flipping the *last* base64 char of the
    signature is unreliable: those low bits are padding and can decode to the
    same bytes.)
    """
    header, payload, signature = token.split(".")
    mid = len(payload) // 2
    original = payload[mid]
    replacement = "A" if original != "A" else "B"
    tampered_payload = f"{payload[:mid]}{replacement}{payload[mid + 1:]}"
    return f"{header}.{tampered_payload}.{signature}"


class FakeUserRepository:
    """Minimal in-memory stand-in for :class:`UserRepository`."""

    def __init__(self) -> None:
        self.users: dict[str, dict[str, Any]] = {}
        self._counter = 0

    async def exists_by_email(self, email: str) -> bool:
        return any(doc["email"] == email for doc in self.users.values())

    async def exists_by_phone(self, phone: str) -> bool:
        return any(doc["phone"] == phone for doc in self.users.values())

    async def create(self, user_data: dict[str, Any]) -> str:
        self._counter += 1
        user_id = f"{self._counter:024x}"
        self.users[user_id] = {"_id": user_id, **user_data}
        return user_id

    async def find_by_id(self, user_id: str) -> dict[str, Any] | None:
        return self.users.get(user_id)

    async def find_by_id_in_organization(self, user_id: str, organization_id: str) -> dict[str, Any] | None:
        user = self.users.get(user_id)
        if user and user.get("organization_id") == organization_id:
            return user
        return None

    async def find_by_id_in_department(self, user_id: str, department_id: str) -> dict[str, Any] | None:
        user = self.users.get(user_id)
        if user and user.get("department_id") == department_id:
            return user
        return None

    async def find_by_email(self, email: str) -> dict[str, Any] | None:
        return next((d for d in self.users.values() if d["email"] == email.lower()), None)

    async def find_by_phone(self, phone: str) -> dict[str, Any] | None:
        return next((d for d in self.users.values() if d["phone"] == phone), None)

    async def find_by_email_or_phone(self, email: str, phone: str) -> dict[str, Any] | None:
        return next((d for d in self.users.values() if d["email"] == email.lower() or d["phone"] == phone), None)

    async def find_users_in_organization(
        self,
        organization_id: str,
        role: str | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        results = []
        for user in self.users.values():
            if user.get("organization_id") == organization_id:
                if role is None or user.get("role") == role:
                    results.append(user)
        return results[skip : skip + limit]

    async def find_users_in_department(
        self,
        department_id: str,
        role: str | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        results = []
        for user in self.users.values():
            if user.get("department_id") == department_id:
                if role is None or user.get("role") == role:
                    results.append(user)
        return results[skip : skip + limit]

    async def count_users_in_organization(self, organization_id: str, role: str | None = None) -> int:
        count = 0
        for user in self.users.values():
            if user.get("organization_id") == organization_id:
                if role is None or user.get("role") == role:
                    count += 1
        return count

    async def update(self, user_id: str, update_data: dict[str, Any]) -> bool:
        if user_id in self.users:
            self.users[user_id].update(update_data)
            self.users[user_id]["updated_at"] = datetime.utcnow()
            return True
        return False

    async def update_in_organization(
        self,
        user_id: str,
        organization_id: str,
        update_data: dict[str, Any],
    ) -> bool:
        user = self.users.get(user_id)
        if user and user.get("organization_id") == organization_id:
            user.update(update_data)
            user["updated_at"] = datetime.utcnow()
            return True
        return False

    async def exists_by_email_in_organization(self, email: str, organization_id: str) -> bool:
        return any(
            doc["email"] == email.lower() and doc.get("organization_id") == organization_id
            for doc in self.users.values()
        )

    def seed(
        self,
        user_id: str,
        email: str = "citizen@example.com",
        phone: str = "+15551234567",
        role: str = "citizen",
        status: str = "active",
        password_hash: str | None = None,
        organization_id: str | None = None,
        department_id: str | None = None,
    ) -> str:
        """Insert a fully-formed user document directly."""
        self.users[user_id] = {
            "_id": user_id,
            "email": email,
            "phone": phone,
            "full_name": "Jane Citizen",
            "role": role,
            "status": status,
            "is_verified": True,
            "password_hash": password_hash,
            "organization_id": organization_id,
            "department_id": department_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        return user_id


class FakeRefreshTokenRepository:
    """In-memory stand-in for :class:`RefreshTokenRepository`.

    Mirrors the real repository's semantics, including the guarded
    ``revoke_if_active`` predicate (only an active record can be revoked) so
    double-use / replay behaviour can be exercised without MongoDB.
    """

    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}
        self._counter = 0

    async def insert_token(self, record: dict[str, Any]) -> str:
        self._counter += 1
        record_id = f"tok{self._counter:04d}"
        self.records[record_id] = dict(record)
        return record_id

    async def find_by_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        for record in self.records.values():
            if record["token_hash"] == token_hash:
                return record
        return None

    async def revoke_if_active(
        self,
        token_hash: str,
        revoked_at: datetime,
        replaced_by: str | None = None,
    ) -> dict[str, Any] | None:
        record = await self.find_by_token_hash(token_hash)
        if record is None or record["revoked_at"] is not None:
            return None
        record["revoked_at"] = revoked_at
        record["replaced_by"] = replaced_by
        return record

    async def revoke_family(
        self,
        family_id: str,
        revoked_at: datetime,
        reuse_detected: bool = False,
    ) -> int:
        count = 0
        for record in self.records.values():
            if record["family_id"] == family_id and record["revoked_at"] is None:
                record["revoked_at"] = revoked_at
                record["reuse_detected"] = reuse_detected
                count += 1
        return count


class FakeRefreshTokenService:
    """In-memory stand-in for :class:`RefreshTokenService`."""

    def __init__(self, repository: "FakeRefreshTokenRepository", user_service) -> None:
        self._repository = repository
        self._user_service = user_service

    async def issue_token_pair(
        self, user_id: str, role: str | None = None
    ) -> TokenPairResponse:
        """Issue a fresh access + refresh pair, starting a new token family."""
        from datetime import timedelta
        from uuid import uuid4

        from app.core.security import create_access_token, create_refresh_token, hash_refresh_token

        now = datetime.now(UTC)
        family_id = uuid4().hex
        jti = uuid4().hex
        expires_delta = timedelta(days=30)

        raw = create_refresh_token(user_id, jti=jti, now=now, expires_delta=expires_delta)
        await self._repository.insert_token(
            {
                "user_id": str(user_id),
                "family_id": family_id,
                "jti": jti,
                "token_hash": hash_refresh_token(raw),
                "expires_at": now + expires_delta,
                "created_at": now,
                "revoked_at": None,
                "replaced_by": None,
                "reuse_detected": False,
            }
        )
        access_token = create_access_token(user_id, role=role)
        return TokenPairResponse(
            access_token=access_token,
            refresh_token=raw,
            token_type="bearer",
            expires_in=15 * 60,
        )

    async def rotate(self, refresh_token: str) -> TokenPairResponse:
        """Rotate a valid refresh token into a new access + refresh pair."""
        from datetime import timedelta
        from uuid import uuid4

        from app.core.security import (
            create_access_token,
            create_refresh_token,
            decode_refresh_token,
            hash_refresh_token,
        )
        from app.exceptions.base import UnauthorizedException

        payload = decode_refresh_token(refresh_token)

        user = await self._user_service.get_user_by_id(payload.sub)
        if user is None:
            raise UnauthorizedException("Invalid refresh token", error_code="TOKEN_INVALID")

        token_hash = hash_refresh_token(refresh_token)
        now = datetime.now(UTC)
        new_jti = uuid4().hex

        record = await self._repository.revoke_if_active(
            token_hash, revoked_at=now, replaced_by=new_jti
        )
        if record is None:
            existing = await self._repository.find_by_token_hash(token_hash)
            if existing is not None:
                await self._repository.revoke_family(
                    str(existing["family_id"]),
                    revoked_at=now,
                    reuse_detected=True,
                )
            raise UnauthorizedException("Invalid refresh token", error_code="TOKEN_INVALID")

        family_id = str(record["family_id"])
        expires_delta = timedelta(days=30)
        raw = create_refresh_token(
            payload.sub, jti=new_jti, now=now, expires_delta=expires_delta
        )
        await self._repository.insert_token(
            {
                "user_id": str(payload.sub),
                "family_id": family_id,
                "jti": new_jti,
                "token_hash": hash_refresh_token(raw),
                "expires_at": now + expires_delta,
                "created_at": now,
                "revoked_at": None,
                "replaced_by": None,
                "reuse_detected": False,
            }
        )
        return TokenPairResponse(
            access_token=create_access_token(payload.sub, role=user.role),
            refresh_token=raw,
            token_type="bearer",
            expires_in=15 * 60,
        )

    async def revoke(self, refresh_token: str) -> None:
        """Logout: revoke the family of the presented refresh token."""
        from app.core.security import decode_refresh_token, hash_refresh_token
        from app.exceptions.base import UnauthorizedException

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
