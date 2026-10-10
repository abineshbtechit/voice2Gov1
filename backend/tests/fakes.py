"""Shared in-memory test doubles (no MongoDB required)."""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.repositories.complaint_image_repository import to_object_id
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

    async def find_users_in_organization_and_department(
        self,
        organization_id: str,
        department_id: str,
        role: str | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        results = []
        for user in self.users.values():
            if (
                user.get("organization_id") == organization_id
                and user.get("department_id") == department_id
            ):
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

    async def find_users(
        self,
        role: str | None = None,
        status: str | None = None,
        search: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        results = []
        for user in self.users.values():
            if role and user.get("role") != role:
                continue
            if status and user.get("status") != status:
                continue
            if search:
                term = search.lower().strip()
                if (
                    term not in user.get("email", "").lower()
                    and term not in user.get("full_name", "").lower()
                    and term not in user.get("phone", "")
                ):
                    continue
            results.append(user)
        results.sort(key=lambda u: u.get("created_at", datetime.min), reverse=True)
        return results[skip : skip + limit]

    async def count_users(
        self,
        role: str | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> int:
        return len(await self.find_users(role=role, status=status, search=search, limit=10000))

    async def count_all(self) -> int:
        return len(self.users)

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
        """Insert a fully-formed user document directly.

        If user_id is not a valid ObjectId, generate one.
        """
        try:
            ObjectId(user_id)
            valid_user_id = user_id
        except Exception:
            # Generate a deterministic ObjectId from the provided string
            import hashlib
            hash_bytes = hashlib.sha256(user_id.encode()).digest()[:12]
            valid_user_id = hash_bytes.hex()
        self.users[valid_user_id] = {
            "_id": valid_user_id,
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
        return valid_user_id


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

        status_val = user.status.value if hasattr(user.status, "value") else str(user.status)
        if status_val in ("suspended", "inactive", "locked"):
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


class FakeComplaintImageRepository:
    """In-memory stand-in for :class:`ComplaintImageRepository` (Phase 1.3.4)."""

    def __init__(self) -> None:
        self.images: dict[str, dict[str, Any]] = {}
        self._counter = 0

    @staticmethod
    def _norm(value: Any) -> str:
        return str(to_object_id(value) or value)

    async def create(self, metadata: dict[str, Any]) -> str:
        self._counter += 1
        image_id = f"{self._counter:024x}"
        self.images[image_id] = {"_id": image_id, **metadata}
        return image_id

    async def create_many(self, records: list[dict[str, Any]]) -> list[str]:
        return [await self.create(record) for record in records]

    async def find_by_id(
        self,
        image_id: Any,
        complaint_id: Any | None = None,
        *,
        include_deleted: bool = False,
    ) -> dict[str, Any] | None:
        record = self.images.get(str(image_id))
        if record is None:
            return None
        if complaint_id is not None and self._norm(record.get("complaint_id")) != self._norm(
            complaint_id
        ):
            return None
        if not include_deleted and record.get("is_deleted"):
            return None
        return record

    async def find_by_complaint(
        self,
        complaint_id: Any,
        *,
        image_type: Any | None = None,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        type_value = getattr(image_type, "value", image_type)
        results = [
            record
            for record in self.images.values()
            if self._norm(record.get("complaint_id")) == self._norm(complaint_id)
            and (type_value is None or record.get("image_type") == type_value)
            and (include_deleted or not record.get("is_deleted"))
        ]
        results.sort(key=lambda record: record.get("created_at"))
        return results

    async def count_by_complaint(
        self, complaint_id: Any, *, include_deleted: bool = False
    ) -> int:
        return len(
            await self.find_by_complaint(complaint_id, include_deleted=include_deleted)
        )

    async def count_by_complaints(self, complaint_ids: Any) -> dict[str, int]:
        counts: dict[str, int] = {}
        for cid in complaint_ids:
            key = self._norm(cid)
            counts[key] = sum(
                1
                for record in self.images.values()
                if self._norm(record.get("complaint_id")) == key
                and not record.get("is_deleted")
            )
        return counts

    async def soft_delete(self, image_id: Any, complaint_id: Any | None = None) -> bool:
        record = await self.find_by_id(image_id, complaint_id)
        if record is None:
            return False
        record["is_deleted"] = True
        return True

    async def create_indexes(self) -> None:  # pragma: no cover - no-op for fakes
        return None

    def seed(
        self,
        image_id: str,
        complaint_id: str,
        uploaded_by: str = "507f1f77bcf86cd799439011",
        image_type: str = "evidence",
        storage_path: str = "evidence/2024/01/15/c/abc_photo.jpg",
        mime_type: str = "image/jpeg",
        file_size: int = 1024,
        checksum: str = "0" * 64,
        is_deleted: bool = False,
    ) -> str:
        self.images[image_id] = {
            "_id": image_id,
            "complaint_id": complaint_id,
            "image_type": image_type,
            "storage_path": storage_path,
            "original_filename": "photo.jpg",
            "mime_type": mime_type,
            "file_size": file_size,
            "width": None,
            "height": None,
            "checksum": checksum,
            "uploaded_by": uploaded_by,
            "is_deleted": is_deleted,
            "created_at": datetime.now(UTC),
        }
        return image_id


class FakeComplaintLookup:
    """In-memory complaint reader used by :class:`ImageService` tests."""

    def __init__(self) -> None:
        self.complaints: dict[str, dict[str, Any]] = {}

    def seed(self, complaint_id: str, **data: Any) -> str:
        self.complaints[complaint_id] = {"_id": complaint_id, **data}
        return complaint_id

    async def create(self, complaint_data: dict[str, Any]) -> str:
        """Persist a complaint with a generated ObjectId (creation-path fake)."""
        oid = ObjectId()
        doc = dict(complaint_data)
        doc["_id"] = oid
        self.complaints[str(oid)] = doc
        return str(oid)

    async def count_complaints_by_year(self, year: int) -> int:
        prefix = f"CMP-{year}-"
        return sum(
            1
            for doc in self.complaints.values()
            if str(doc.get("complaint_number", "")).startswith(prefix)
        )

    async def find_by_id_for_admin(self, complaint_id: str) -> dict[str, Any] | None:
        return self.complaints.get(str(complaint_id))

    async def find_by_id_in_organization(
        self, complaint_id: str, organization_id: str
    ) -> dict[str, Any] | None:
        complaint = self.complaints.get(str(complaint_id))
        if complaint and str(complaint.get("organization_id")) == str(organization_id):
            return complaint
        return None

    async def find_by_id_for_organization_staff(
        self, complaint_id: str, organization_id: str, department_id: str | None = None
    ) -> dict[str, Any] | None:
        complaint = self.complaints.get(str(complaint_id))
        if not complaint:
            return None
        if str(complaint.get("organization_id")) != str(organization_id):
            return None
        if department_id and str(complaint.get("department_id")) != str(department_id):
            return None
        return complaint

    async def find_by_id(self, complaint_id: str) -> dict[str, Any] | None:
        return self.complaints.get(str(complaint_id))

    async def find_by_id_for_user(
        self, complaint_id: str, user_id: str
    ) -> dict[str, Any] | None:
        complaint = self.complaints.get(str(complaint_id))
        if complaint and str(complaint.get("user_id")) == str(user_id):
            return complaint
        return None

    async def transition_status(
        self,
        complaint_id: str,
        expected_status: str,
        new_status: str,
        update_fields: dict[str, Any],
        organization_id: str | None = None,
    ) -> bool:
        complaint = self.complaints.get(str(complaint_id))
        if not complaint:
            return False
        if complaint.get("status") != expected_status:
            return False
        if organization_id is not None and str(complaint.get("organization_id")) != str(organization_id):
            return False
        complaint.update(update_fields)
        complaint["status"] = new_status
        return True

    async def assign_complaint(
        self,
        complaint_id: str,
        expected_status: str,
        new_status: str,
        assigned_to: str,
        assigned_at: datetime,
        organization_id: str | None = None,
    ) -> bool:
        complaint = self.complaints.get(str(complaint_id))
        if not complaint:
            return False
        if complaint.get("status") != expected_status:
            return False
        if organization_id is not None and str(complaint.get("organization_id")) != str(organization_id):
            return False
        complaint["assigned_to"] = assigned_to
        complaint["assigned_at"] = assigned_at
        complaint["status"] = new_status
        complaint["updated_at"] = datetime.now(UTC)
        return True

    async def complete_complaint(
        self,
        complaint_id: str,
        completed_at: datetime,
        organization_id: str | None = None,
    ) -> bool:
        complaint = self.complaints.get(str(complaint_id))
        if not complaint:
            return False
        if complaint.get("status") != "PROCESSING":
            return False
        if organization_id is not None and str(complaint.get("organization_id")) != str(organization_id):
            return False
        complaint["status"] = "COMPLETED"
        complaint["completed_at"] = completed_at
        complaint["updated_at"] = datetime.now(UTC)
        return True

    async def update_likes_count_and_priority(
        self,
        complaint_id: str,
        likes_count: int,
        priority_score: float,
        community_engagement_score: int,
    ) -> bool:
        complaint = self.complaints.get(str(complaint_id))
        if not complaint:
            return False
        complaint["likes_count"] = likes_count
        complaint["priority_score"] = priority_score
        complaint["community_engagement_score"] = community_engagement_score
        complaint["updated_at"] = datetime.now(UTC)
        return True

    def _filter_feed_doc(
        self,
        doc: dict[str, Any],
        status: str | None,
        category_id: str | None,
        organization_id: str | None,
        q: str | None = None,
    ) -> bool:
        if doc.get("visibility") != "public":
            return False
        if status:
            if doc.get("status") != status:
                return False
        else:
            if doc.get("status") in ("REJECTED", "DUPLICATE", "CLOSED"):
                return False
        if category_id and str(doc.get("category_id")) != str(category_id):
            return False
        if organization_id and str(doc.get("organization_id")) != str(organization_id):
            return False
        if q and q.strip():
            needle = q.strip().lower()
            title = str(doc.get("title", "")).lower()
            description = str(doc.get("description", "")).lower()
            complaint_number = str(doc.get("complaint_number", "")).lower()
            if needle not in title and needle not in description and needle not in complaint_number:
                return False
        return True

    async def query_public_feed(
        self,
        status: str | None = None,
        category_id: str | None = None,
        organization_id: str | None = None,
        sort: str = "recent",
        page: int = 1,
        page_size: int = 20,
        lat: float | None = None,
        lng: float | None = None,
        radius_km: float = 10.0,
        q: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        import math

        results = []
        for doc in self.complaints.values():
            if not self._filter_feed_doc(doc, status, category_id, organization_id, q=q):
                continue

            item = dict(doc)
            if sort == "nearby" and lat is not None and lng is not None:
                loc = doc.get("location") or {}
                coords = loc.get("coordinates", [0.0, 0.0])
                doc_lng, doc_lat = coords[0], coords[1]
                dlat = math.radians(doc_lat - lat)
                dlng = math.radians(doc_lng - lng)
                a = (
                    math.sin(dlat / 2) ** 2
                    + math.cos(math.radians(lat))
                    * math.cos(math.radians(doc_lat))
                    * math.sin(dlng / 2) ** 2
                )
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                d_km = 6371.0 * c
                if d_km > radius_km:
                    continue
                item["distance_km"] = round(d_km, 2)
            results.append(item)

        sort_keys = {
            "popular": lambda x: (
                -int(x.get("likes_count", 0)),
                -x.get("created_at", datetime.min).timestamp() if isinstance(x.get("created_at"), datetime) else 0.0,
            ),
            "priority": lambda x: (
                -float(x.get("priority_score", 0.0)),
                -x.get("created_at", datetime.min).timestamp() if isinstance(x.get("created_at"), datetime) else 0.0,
            ),
            "nearby": lambda x: (
                x.get("distance_km", 0.0),
                -x.get("created_at", datetime.min).timestamp() if isinstance(x.get("created_at"), datetime) else 0.0,
            ),
        }
        key_fn = sort_keys.get(
            sort,
            lambda x: -x.get("created_at", datetime.min).timestamp() if isinstance(x.get("created_at"), datetime) else 0.0,
        )
        results.sort(key=key_fn)

        total = len(results)
        skip = (page - 1) * page_size
        return results[skip : skip + page_size], total

    async def find_organization_complaints(
        self,
        organization_id: str,
        status: str | None = None,
        department_id: str | None = None,
        assigned_to: str | None = None,
        sort_by: str = "priority",
        page: int = 1,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        results = []
        for doc in self.complaints.values():
            if str(doc.get("organization_id")) != str(organization_id):
                continue
            if status and doc.get("status") != status:
                continue
            if department_id and str(doc.get("department_id")) != str(department_id):
                continue
            if assigned_to and str(doc.get("assigned_to")) != str(assigned_to):
                continue
            results.append(doc)

        if sort_by == "priority":
            results.sort(
                key=lambda x: (
                    -float(x.get("priority_score", 0.0)),
                    -x.get("created_at", datetime.min).timestamp()
                    if isinstance(x.get("created_at"), datetime)
                    else 0.0,
                )
            )
        elif sort_by == "recent":
            results.sort(
                key=lambda x: -x.get("created_at", datetime.min).timestamp()
                if isinstance(x.get("created_at"), datetime)
                else 0.0
            )
        elif sort_by == "sla":
            results.sort(
                key=lambda x: x.get("sla_deadline", datetime.max).timestamp()
                if isinstance(x.get("sla_deadline"), datetime)
                else float("inf")
            )
        else:
            results.sort(
                key=lambda x: -x.get("created_at", datetime.min).timestamp()
                if isinstance(x.get("created_at"), datetime)
                else 0.0
            )

        skip = (page - 1) * page_size
        return results[skip : skip + page_size]

    async def count_organization_complaints(
        self,
        organization_id: str,
        status: str | None = None,
        department_id: str | None = None,
        assigned_to: str | None = None,
    ) -> int:
        count = 0
        for doc in self.complaints.values():
            if str(doc.get("organization_id")) != str(organization_id):
                continue
            if status and doc.get("status") != status:
                continue
            if department_id and str(doc.get("department_id")) != str(department_id):
                continue
            if assigned_to and str(doc.get("assigned_to")) != str(assigned_to):
                continue
            count += 1
        return count

    async def count_all(self) -> int:
        return len(self.complaints)

    async def get_dashboard_aggregates(self) -> tuple[dict[str, int], float, float]:
        status_counts: dict[str, int] = {}
        for doc in self.complaints.values():
            st = doc.get("status")
            if st:
                status_counts[st] = status_counts.get(st, 0) + 1

        completed = [
            c for c in self.complaints.values()
            if c.get("status") == "COMPLETED"
            and c.get("completed_at") is not None
            and c.get("created_at") is not None
        ]

        if not completed:
            return status_counts, 0.0, 1.0

        total_hours = 0.0
        compliant_count = 0
        for c in completed:
            cat = c["created_at"]
            comp = c["completed_at"]
            delta = (comp - cat).total_seconds() / 3600.0
            total_hours += max(0.0, delta)
            deadline = c.get("sla_deadline")
            if not deadline or comp <= deadline:
                compliant_count += 1

        avg_hours = round(total_hours / len(completed), 2)
        sla_rate = round(compliant_count / len(completed), 2)
        return status_counts, avg_hours, sla_rate



class FakeComplaintUpdateRepository:
    """In-memory stand-in for ComplaintUpdateRepository."""

    def __init__(self) -> None:
        self.updates: dict[str, dict[str, Any]] = {}
        self._counter = 0

    async def create(self, update_doc: dict[str, Any]) -> str:
        dept_id = update_doc.get("department_id")
        if not dept_id:
            raise ValueError("department_id is required for complaint_updates")
        self._counter += 1
        update_id = f"{self._counter:024x}"
        self.updates[update_id] = {"_id": update_id, **update_doc}
        return update_id

    async def find_by_id(self, update_id: object) -> dict[str, Any] | None:
        return self.updates.get(str(update_id))

    async def find_by_complaint(
        self,
        complaint_id: object,
        *,
        is_public_only: bool = False,
    ) -> list[dict[str, Any]]:
        results = []
        for doc in self.updates.values():
            if str(doc.get("complaint_id")) == str(complaint_id):
                if is_public_only and not doc.get("is_public", True):
                    continue
                results.append(doc)
        results.sort(key=lambda d: d.get("created_at", datetime.min))
        return results


class FakeComplaintLikeRepository:
    """In-memory stand-in for ComplaintLikeRepository."""

    def __init__(self) -> None:
        self.likes: set[tuple[str, str]] = set()

    def set_likes(self, complaint_id: str, user_ids: list[str]) -> None:
        self.likes = {
            (str(complaint_id), str(uid)) for uid in user_ids
        }

    async def count_by_complaint(self, complaint_id: object) -> int:
        return sum(1 for cid, _ in self.likes if cid == str(complaint_id))

    async def add_like(self, complaint_id: object, user_id: object) -> bool:
        pair = (str(complaint_id), str(user_id))
        if pair in self.likes:
            return False
        self.likes.add(pair)
        return True

    async def remove_like(self, complaint_id: object, user_id: object) -> bool:
        pair = (str(complaint_id), str(user_id))
        if pair in self.likes:
            self.likes.remove(pair)
            return True
        return False

    async def is_liked(self, complaint_id: object, user_id: object) -> bool:
        return (str(complaint_id), str(user_id)) in self.likes

    async def list_user_liked_complaint_ids(
        self, user_id: object, complaint_ids: list[object]
    ) -> set[str]:
        uid_str = str(user_id)
        cid_strs = {str(cid) for cid in complaint_ids}
        return {cid for cid, uid in self.likes if uid == uid_str and cid in cid_strs}



class FakeAdminSettingsRepository:
    """In-memory stand-in for AdminSettingsRepository."""

    def __init__(self) -> None:
        self.settings: dict[str, dict[str, Any]] = {}

    async def create_indexes(self) -> None:
        return None

    async def get_setting(self, key: str) -> Any | None:
        doc = self.settings.get(key)
        if doc is not None:
            return doc.get("value")
        return None

    async def get_settings_by_category(self, category: str) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for doc in self.settings.values():
            if doc.get("category") == category:
                results[doc["key"]] = doc.get("value")
        return results

    async def get_setting_doc(self, key: str) -> dict[str, Any] | None:
        return self.settings.get(key)

    async def list_all_settings(self) -> list[dict[str, Any]]:
        items = list(self.settings.values())
        items.sort(key=lambda d: (d.get("category", ""), d.get("key", "")))
        return items

    async def set_setting(
        self,
        key: str,
        value: Any,
        category: str = "priority",
        description: str | None = None,
        updated_by: str | None = None,
    ) -> None:
        doc = self.settings.get(key, {})
        doc.update({
            "key": key,
            "value": value,
            "category": category,
            "description": description or doc.get("description"),
            "updated_by": updated_by,
            "updated_at": datetime.now(UTC),
        })
        if "created_at" not in doc:
            doc["created_at"] = datetime.now(UTC)
            doc["is_public"] = False
        self.settings[key] = doc


class FakeCategoryRepository:
    """In-memory stand-in for CategoryRepository."""

    def __init__(self) -> None:
        self.categories: dict[str, dict[str, Any]] = {}
        self._counter = 0

    def seed(self, category_id: str, **data: Any) -> str:
        self.categories[str(category_id)] = {"_id": category_id, **data}
        return str(category_id)

    async def create_indexes(self) -> None:
        pass

    async def create(self, category_data: dict[str, Any]) -> str:
        name = category_data["name"]
        org_id = category_data.get("organization_id")
        for c in self.categories.values():
            if c.get("name") == name and str(c.get("organization_id")) == str(org_id):
                from app.exceptions.base import ConflictException
                raise ConflictException("Category with this name already exists in the organization")

        self._counter += 1
        cid = f"{self._counter:024x}"
        doc = dict(category_data)
        doc["_id"] = ObjectId(cid)
        doc.setdefault("created_at", datetime.now(UTC))
        doc.setdefault("updated_at", datetime.now(UTC))
        self.categories[cid] = doc
        return cid

    async def find_by_id(self, category_id: str) -> dict[str, Any] | None:
        return self.categories.get(str(category_id))

    async def find_by_id_active(self, category_id: str) -> dict[str, Any] | None:
        cat = self.categories.get(str(category_id))
        if cat and cat.get("status") in ("active", None):
            return cat
        return None

    async def find_by_ids(self, category_ids: list[object]) -> list[dict[str, Any]]:
        wanted = {str(cid) for cid in category_ids}
        return [
            cat for cid, cat in self.categories.items() if str(cid) in wanted
        ]

    async def list_active(
        self, organization_id: str | None = None, limit: int = 100, skip: int = 0
    ) -> list[dict[str, Any]]:
        results = [
            c for c in self.categories.values()
            if c.get("status") in ("active", None)
            and (organization_id is None or str(c.get("organization_id")) == str(organization_id))
        ]
        results.sort(key=lambda x: (x.get("sort_order", 0), x.get("name", "")))
        return results[skip : skip + limit]

    async def list_all(
        self, organization_id: str | None = None, limit: int = 100, skip: int = 0
    ) -> list[dict[str, Any]]:
        results = [
            c for c in self.categories.values()
            if organization_id is None or str(c.get("organization_id")) == str(organization_id)
        ]
        results.sort(key=lambda x: (x.get("sort_order", 0), x.get("name", "")))
        return results[skip : skip + limit]

    async def count_active(self, organization_id: str | None = None) -> int:
        return len(await self.list_active(organization_id=organization_id, limit=10000))

    async def update(self, category_id: str, update_data: dict[str, Any]) -> bool:
        cid = str(category_id)
        if cid not in self.categories:
            return False
        doc = self.categories[cid]
        if "name" in update_data:
            name = update_data["name"]
            org_id = doc.get("organization_id")
            for other_id, other in self.categories.items():
                if other_id != cid and other.get("name") == name and str(other.get("organization_id")) == str(org_id):
                    from app.exceptions.base import ConflictException
                    raise ConflictException("Category with this name already exists in the organization")
        doc.update(update_data)
        doc["updated_at"] = datetime.now(UTC)
        return True

    async def soft_delete(self, category_id: str) -> bool:
        return await self.update(category_id, {"status": "inactive"})


class FakeDepartmentRepository:
    """In-memory stand-in for DepartmentRepository."""

    def __init__(self) -> None:
        self.departments: dict[str, dict[str, Any]] = {}
        self._counter = 0

    def seed(self, department_id: str, **data: Any) -> str:
        self.departments[str(department_id)] = {"_id": department_id, **data}
        return str(department_id)

    async def create_indexes(self) -> None:
        pass

    async def create(self, dept_data: dict[str, Any]) -> str:
        code = dept_data["code"]
        name = dept_data["name"]
        org_id = str(dept_data["organization_id"])
        for d in self.departments.values():
            if str(d.get("organization_id")) == org_id:
                if d.get("code") == code:
                    from app.exceptions.base import ConflictException
                    raise ConflictException("Department code already exists in this organization")
                if d.get("name") == name:
                    from app.exceptions.base import ConflictException
                    raise ConflictException("Department name already exists in this organization")

        self._counter += 1
        did = f"{self._counter:024x}"
        doc = dict(dept_data)
        doc["_id"] = ObjectId(did)
        doc.setdefault("created_at", datetime.now(UTC))
        doc.setdefault("updated_at", datetime.now(UTC))
        self.departments[did] = doc
        return did

    async def find_by_id(self, department_id: str) -> dict[str, Any] | None:
        return self.departments.get(str(department_id))

    async def find_by_id_in_org(
        self, department_id: str, organization_id: str
    ) -> dict[str, Any] | None:
        dept = self.departments.get(str(department_id))
        if dept and str(dept.get("organization_id")) == str(organization_id):
            return dept
        return None

    async def find_by_id_in_organization(
        self, department_id: str, organization_id: str
    ) -> dict[str, Any] | None:
        return await self.find_by_id_in_org(department_id, organization_id)

    async def find_by_ids(self, department_ids: list[object]) -> list[dict[str, Any]]:
        wanted = {str(did) for did in department_ids}
        return [
            dept for did, dept in self.departments.items() if str(did) in wanted
        ]

    async def find_by_id_active_in_org(
        self, department_id: str, organization_id: str
    ) -> dict[str, Any] | None:
        dept = self.departments.get(str(department_id))
        if dept and str(dept.get("organization_id")) == str(organization_id) and dept.get("is_active", True):
            return dept
        return None

    async def list_by_org(
        self,
        organization_id: str,
        is_active: bool | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        results = [
            d for d in self.departments.values()
            if str(d.get("organization_id")) == str(organization_id)
            and (is_active is None or d.get("is_active", True) == is_active)
        ]
        results.sort(key=lambda x: x.get("name", ""))
        return results[skip : skip + limit]

    async def count_by_org(
        self, organization_id: str, is_active: bool | None = None
    ) -> int:
        return len(await self.list_by_org(organization_id, is_active=is_active, limit=10000))

    async def count_all(self, is_active: bool | None = None) -> int:
        return sum(
            1 for d in self.departments.values()
            if (is_active is None or d.get("is_active", True) == is_active)
        )

    async def list_all(
        self, is_active: bool | None = None, limit: int = 100, skip: int = 0
    ) -> list[dict[str, Any]]:
        results = [
            d for d in self.departments.values()
            if (is_active is None or d.get("is_active", True) == is_active)
        ]
        results.sort(key=lambda x: x.get("name", ""))
        return results[skip : skip + limit]

    async def update(
        self, department_id: str, organization_id: str, update_data: dict[str, Any]
    ) -> bool:
        did = str(department_id)
        if did not in self.departments:
            return False
        dept = self.departments[did]
        if str(dept.get("organization_id")) != str(organization_id):
            return False

        if "code" in update_data:
            code = update_data["code"]
            for other_id, other in self.departments.items():
                if other_id != did and str(other.get("organization_id")) == str(organization_id) and other.get("code") == code:
                    from app.exceptions.base import ConflictException
                    raise ConflictException("Department code already exists in this organization")

        if "name" in update_data:
            name = update_data["name"]
            for other_id, other in self.departments.items():
                if other_id != did and str(other.get("organization_id")) == str(organization_id) and other.get("name") == name:
                    from app.exceptions.base import ConflictException
                    raise ConflictException("Department name already exists in this organization")

        dept.update(update_data)
        dept["updated_at"] = datetime.now(UTC)
        return True

    async def soft_delete(self, department_id: str, organization_id: str) -> bool:
        return await self.update(department_id, organization_id, {"is_active": False})


class FakeOrganizationRepository:
    """In-memory stand-in for OrganizationRepository."""

    def __init__(self) -> None:
        self.organizations: dict[str, dict[str, Any]] = {}
        self._counter = 0

    async def create_indexes(self) -> None:
        pass

    def seed(self, org_id: str, **data: Any) -> str:
        doc = {"_id": org_id, **data}
        doc.setdefault("created_at", datetime.now(UTC))
        doc.setdefault("updated_at", datetime.now(UTC))
        self.organizations[str(org_id)] = doc
        return str(org_id)

    async def create(self, org_data: dict[str, Any]) -> str:
        code = org_data["code"]
        name = org_data["name"]
        for o in self.organizations.values():
            if o.get("code") == code:
                from app.exceptions.base import ConflictException
                raise ConflictException("Organization code already exists")
            if o.get("name") == name:
                from app.exceptions.base import ConflictException
                raise ConflictException("Organization name already exists")

        self._counter += 1
        oid = f"{self._counter:024x}"
        doc = dict(org_data)
        doc["_id"] = ObjectId(oid)
        doc.setdefault("created_at", datetime.now(UTC))
        doc.setdefault("updated_at", datetime.now(UTC))
        self.organizations[oid] = doc
        return oid

    async def find_by_id(self, org_id: str) -> dict[str, Any] | None:
        return self.organizations.get(str(org_id))

    async def find_by_code(self, code: str) -> dict[str, Any] | None:
        for o in self.organizations.values():
            if o.get("code") == code.upper():
                return o
        return None

    async def find_all(
        self, is_active: bool | None = None, limit: int = 100, skip: int = 0
    ) -> list[dict[str, Any]]:
        results = [
            o for o in self.organizations.values()
            if (is_active is None or o.get("is_active", True) == is_active)
        ]
        results.sort(key=lambda x: x.get("name", ""))
        return results[skip : skip + limit]

    async def count_all(self, is_active: bool | None = None) -> int:
        return sum(
            1 for o in self.organizations.values()
            if (is_active is None or o.get("is_active", True) == is_active)
        )

    async def update(self, org_id: str, update_data: dict[str, Any]) -> bool:
        oid = str(org_id)
        if oid not in self.organizations:
            return False
        org = self.organizations[oid]
        if "code" in update_data:
            code = update_data["code"]
            for other_id, other in self.organizations.items():
                if other_id != oid and other.get("code") == code:
                    from app.exceptions.base import ConflictException
                    raise ConflictException("Organization code already exists")
        if "name" in update_data:
            name = update_data["name"]
            for other_id, other in self.organizations.items():
                if other_id != oid and other.get("name") == name:
                    from app.exceptions.base import ConflictException
                    raise ConflictException("Organization name already exists")

        org.update(update_data)
        org["updated_at"] = datetime.now(UTC)
        return True

    async def set_status(self, org_id: str, is_active: bool) -> bool:
        return await self.update(org_id, {"is_active": is_active})


class FakeAuditLogRepository:
    """In-memory stand-in for AuditLogRepository."""

    def __init__(self) -> None:
        self.logs: list[dict[str, Any]] = []
        self._counter = 0

    async def create_indexes(self) -> None:
        pass

    async def log_event(
        self,
        actor_id: str,
        actor_role: str,
        action: str,
        entity_type: str,
        entity_id: str,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> str:
        self._counter += 1
        lid = f"{self._counter:024x}"
        doc = {
            "_id": ObjectId(lid),
            "actor_id": str(actor_id),
            "actor_role": str(actor_role),
            "action": str(action),
            "entity_type": str(entity_type),
            "entity_id": str(entity_id),
            "metadata": metadata or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime.now(UTC),
        }
        self.logs.append(doc)
        return lid

    async def find_logs(
        self,
        actor_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        action: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        results = [
            log_item for log_item in self.logs
            if (actor_id is None or log_item.get("actor_id") == str(actor_id))
            and (entity_type is None or log_item.get("entity_type") == entity_type)
            and (entity_id is None or log_item.get("entity_id") == str(entity_id))
            and (action is None or log_item.get("action") == action)
        ]
        results.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)
        return results[skip : skip + limit]

    async def count_logs(
        self,
        actor_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        action: str | None = None,
    ) -> int:
        return len(
            [
                log_item for log_item in self.logs
                if (actor_id is None or log_item.get("actor_id") == str(actor_id))
                and (entity_type is None or log_item.get("entity_type") == entity_type)
                and (entity_id is None or log_item.get("entity_id") == str(entity_id))
                and (action is None or log_item.get("action") == action)
            ]
        )


class FakeNotificationRepository:
    """In-memory stand-in for NotificationRepository."""

    def __init__(self) -> None:
        self.notifications: dict[str, dict[str, Any]] = {}
        self._counter = 0

    async def create_indexes(self) -> None:
        pass

    async def create(self, document: dict[str, Any]) -> str:
        self._counter += 1
        nid = f"{self._counter:024x}"
        doc = dict(document)
        doc["_id"] = ObjectId(nid)
        doc.setdefault("created_at", datetime.now(UTC))
        doc.setdefault("is_read", False)
        doc.setdefault("read_at", None)
        self.notifications[nid] = doc
        return nid

    async def find_by_id(self, notification_id: object, user_id: object) -> dict[str, Any] | None:
        nid_str = str(notification_id)
        uid_str = str(user_id)
        doc = self.notifications.get(nid_str)
        if doc and str(doc.get("user_id")) == uid_str:
            return doc
        return None

    async def list_for_user(
        self,
        user_id: object,
        is_read: bool | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        uid_str = str(user_id)
        filtered = [
            d for d in self.notifications.values()
            if str(d.get("user_id")) == uid_str and (is_read is None or d.get("is_read") == is_read)
        ]
        filtered.sort(key=lambda d: d.get("created_at", datetime.min), reverse=True)
        return filtered[skip : skip + limit]

    async def count_for_user(self, user_id: object, is_read: bool | None = None) -> int:
        uid_str = str(user_id)
        return sum(
            1 for d in self.notifications.values()
            if str(d.get("user_id")) == uid_str and (is_read is None or d.get("is_read") == is_read)
        )

    async def count_unread(self, user_id: object) -> int:
        return await self.count_for_user(user_id, is_read=False)

    async def mark_read(
        self,
        notification_id: object,
        user_id: object,
        read_at: datetime | None = None,
    ) -> bool:
        doc = await self.find_by_id(notification_id, user_id)
        if not doc:
            return False
        doc["is_read"] = True
        doc["read_at"] = read_at or datetime.now(UTC)
        return True

    async def mark_all_read(
        self,
        user_id: object,
        read_at: datetime | None = None,
    ) -> int:
        uid_str = str(user_id)
        now = read_at or datetime.now(UTC)
        count = 0
        for doc in self.notifications.values():
            if str(doc.get("user_id")) == uid_str and not doc.get("is_read"):
                doc["is_read"] = True
                doc["read_at"] = now
                count += 1
        return count


class FakeDeviceTokenRepository:
    """In-memory stand-in for DeviceTokenRepository."""

    def __init__(self) -> None:
        self.tokens: dict[str, dict[str, Any]] = {}

    async def create_indexes(self) -> None:
        pass

    async def upsert_token(
        self,
        user_id: object,
        device_token: str,
        platform: str,
        device_id: str | None = None,
        app_version: str | None = None,
    ) -> dict[str, Any]:
        key = f"{user_id}:{device_token}"
        now = datetime.now(UTC)
        doc = self.tokens.get(key, {})
        doc.update({
            "user_id": str(user_id),
            "device_token": device_token,
            "platform": platform,
            "device_id": device_id,
            "app_version": app_version,
            "is_active": True,
            "updated_at": now,
        })
        if "created_at" not in doc:
            doc["created_at"] = now
            doc["last_used_at"] = None
        self.tokens[key] = doc
        return doc

    async def get_active_tokens(self, user_id: object) -> list[dict[str, Any]]:
        uid_str = str(user_id)
        return [
            d for d in self.tokens.values()
            if str(d.get("user_id")) == uid_str and d.get("is_active")
        ]

    async def mark_token_inactive(self, device_token: str) -> int:
        now = datetime.now(UTC)
        count = 0
        for doc in self.tokens.values():
            if doc.get("device_token") == device_token and doc.get("is_active"):
                doc["is_active"] = False
                doc["updated_at"] = now
                count += 1
        return count

    async def update_last_used(self, device_token: str) -> None:
        now = datetime.now(UTC)
        for doc in self.tokens.values():
            if doc.get("device_token") == device_token:
                doc["last_used_at"] = now
                doc["updated_at"] = now





