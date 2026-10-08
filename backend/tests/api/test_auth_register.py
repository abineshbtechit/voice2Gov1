"""Phase 1.2.1 — POST /api/v1/auth/register API tests.

Uses a real ``UserService`` backed by an in-memory fake repository, so the
request travels through pydantic validation, the service, bcrypt hashing and
response serialization. Only MongoDB is faked.

Covers the API requirements:
- 201 on success
- invalid payload rejected (422)
- weak password rejected (422)
- duplicate email / phone rejected (409)
- response never contains password / hash
- ``/login`` does NOT exist in Phase 1.2.1
"""

from datetime import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.v1.auth import get_refresh_token_service, get_user_service
from app.core.security import hash_password, verify_password
from app.main import create_app
from app.services.user_service import UserService
from tests.fakes import FakeRefreshTokenService

VALID_PASSWORD = "SecurePass123!"


class FakeUserRepository:
    """Minimal in-memory stand-in for :class:`UserRepository` (no MongoDB)."""

    def __init__(self) -> None:
        self.users: dict[str, dict[str, object]] = {}
        self._counter = 0

    async def exists_by_email(self, email: str) -> bool:
        return any(doc["email"] == email for doc in self.users.values())

    async def exists_by_phone(self, phone: str) -> bool:
        return any(doc["phone"] == phone for doc in self.users.values())

    async def create(self, user_data: dict[str, object]) -> str:
        self._counter += 1
        user_id = f"{self._counter:024x}"
        self.users[user_id] = {"_id": user_id, **user_data}
        return user_id

    async def find_by_id(self, user_id: str) -> dict[str, object] | None:
        return self.users.get(user_id)

    async def find_by_email(self, email: str) -> dict[str, object] | None:
        return next((d for d in self.users.values() if d["email"] == email.lower()), None)

    async def find_by_phone(self, phone: str) -> dict[str, object] | None:
        return next((d for d in self.users.values() if d["phone"] == phone), None)

    async def update(self, user_id: str, update_data: dict[str, object]) -> bool:
        if user_id in self.users:
            self.users[user_id].update(update_data)
            self.users[user_id]["updated_at"] = datetime.utcnow()
            return True
        return False

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
        from datetime import datetime
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


def payload(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "email": "citizen@example.com",
        "phone": "+15551234567",
        "full_name": "Jane Citizen",
        "password": VALID_PASSWORD,
    }
    data.update(overrides)
    return data


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def repository() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def service(repository: FakeUserRepository) -> UserService:
    return UserService(repository)  # type: ignore[arg-type]


@pytest.fixture
def refresh_token_service(repository: FakeUserRepository, service: UserService):
    from tests.fakes import FakeRefreshTokenRepository
    repo = FakeRefreshTokenRepository()
    return FakeRefreshTokenService(repo, service)


@pytest_asyncio.fixture
async def client(app, service: UserService, refresh_token_service):
    app.dependency_overrides[get_user_service] = lambda: service
    app.dependency_overrides[get_refresh_token_service] = lambda: refresh_token_service
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestRegisterSuccess:
    async def test_register_returns_201(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/auth/register", json=payload())

        assert response.status_code == 201
        data = response.json()
        assert data["id"]
        assert data["email"] == "citizen@example.com"
        assert data["phone"] == "+15551234567"
        assert data["full_name"] == "Jane Citizen"
        assert data["role"] == "citizen"
        assert data["status"] == "pending_verification"
        assert data["is_verified"] is False
        assert "Registration successful" in data["message"]

    async def test_register_stores_hashed_password_never_plaintext(
        self, client: AsyncClient, repository: FakeUserRepository
    ) -> None:
        await client.post("/api/v1/auth/register", json=payload())

        stored = next(iter(repository.users.values()))
        assert stored["password_hash"] != VALID_PASSWORD
        assert stored["password_hash"].startswith("$2")
        assert verify_password(VALID_PASSWORD, str(stored["password_hash"])) is True
        assert "password" not in stored  # no plaintext field stored

    async def test_register_normalizes_email(
        self, client: AsyncClient, repository: FakeUserRepository
    ) -> None:
        response = await client.post(
            "/api/v1/auth/register", json=payload(email="  MIXED@Example.COM  ")
        )

        assert response.status_code == 201
        stored = next(iter(repository.users.values()))
        assert stored["email"] == "mixed@example.com"


class TestRegisterValidation:
    async def test_invalid_email_rejected(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/auth/register", json=payload(email="bad-email"))

        assert response.status_code == 422
        assert response.json()["success"] is False

    async def test_invalid_phone_rejected(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/auth/register", json=payload(phone="12345"))

        assert response.status_code == 422
        assert response.json()["success"] is False

    async def test_missing_field_rejected(self, client: AsyncClient) -> None:
        body = payload()
        del body["full_name"]

        response = await client.post("/api/v1/auth/register", json=body)

        assert response.status_code == 422

    async def test_weak_password_rejected(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/register", json=payload(password="weakpassword")
        )

        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "VALIDATION_ERROR"
        codes = [e.get("code") for e in data.get("errors", [])]
        assert "PASSWORD_POLICY" in codes

    async def test_too_short_password_rejected(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/auth/register", json=payload(password="Ab1!"))

        assert response.status_code == 422


class TestRegisterDuplicates:
    async def test_duplicate_email_rejected(
        self, client: AsyncClient, repository: FakeUserRepository
    ) -> None:
        repository.seed("exists00000000000000000000", email="exists@example.com", phone="+15550000000")

        response = await client.post(
            "/api/v1/auth/register", json=payload(email="exists@example.com")
        )

        assert response.status_code == 409
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "CONFLICT"
        assert "Email already registered" in data["message"]

    async def test_duplicate_phone_rejected(
        self, client: AsyncClient, repository: FakeUserRepository
    ) -> None:
        repository.seed("phone00000000000000000000", email="other@example.com", phone="+15551234567")

        response = await client.post(
            "/api/v1/auth/register", json=payload(phone="+15551234567")
        )

        assert response.status_code == 409
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "CONFLICT"
        assert "Phone number already registered" in data["message"]


class TestNoCredentialLeakage:
    async def test_success_response_has_no_password_or_hash(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/auth/register", json=payload())

        body = response.text
        assert VALID_PASSWORD not in body
        assert "$2b$" not in body
        assert "password" not in body.lower()

    async def test_error_response_has_no_password_or_hash(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/register", json=payload(password="weakpassword")
        )

        body = response.text
        assert "$2b$" not in body
        assert "password_hash" not in body


class TestLoginEndpoint:
    async def test_login_get_method_not_allowed(self, client: AsyncClient) -> None:
        """GET /login should return 405 Method Not Allowed."""
        response = await client.get("/api/v1/auth/login")
        assert response.status_code == 405

    async def test_login_post_returns_invalid_credentials_for_wrong_password(
        self, client: AsyncClient, repository: FakeUserRepository
    ) -> None:
        """POST /login with wrong password should return 401 INVALID_CREDENTIALS."""
        # Seed a user with known credentials
        user_id = "userlogin00000000000000000"
        repository.seed(
            user_id,
            email="login@example.com",
            phone="+15551234567",
            role="citizen",
            status="active",
            password_hash=hash_password(VALID_PASSWORD),
        )
        # Note: password hash would need to match "SecurePass123!" for this to work
        # For now, test that endpoint exists and returns proper error for invalid credentials
        response = await client.post(
            "/api/v1/auth/login", json={"identifier": "login@example.com", "password": "WrongPassword123!"}
        )
        assert response.status_code == 401
        assert response.json()["error_code"] == "INVALID_CREDENTIALS"

    async def test_openapi_has_login_path(self, app) -> None:
        schema = app.openapi()
        assert "/api/v1/auth/login" in schema["paths"]
        assert "/api/v1/auth/register" in schema["paths"]
