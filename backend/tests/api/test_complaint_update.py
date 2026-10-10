"""Phase 1.3.3 — Complaint update API tests.

Covers API requirements:
- unauthenticated request → 401
- citizen → 200 (when SUBMITTED)
- citizen → 403 (when not SUBMITTED)
- organization_staff → 403
- organization_admin → 403
- admin → 403
- invalid payload → 422
- invalid title → 422
- invalid description → 422
- invalid category_id → 422 (not allowed)
- invalid location → 422
- cross-organization manipulation rejected
- server-controlled fields cannot be injected
- response contains no credentials/secrets
- complaint is actually persisted
"""

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.dependencies.services import get_complaint_service
from app.main import create_app
from app.schemas.category import CategoryStatus
from app.schemas.complaint import ComplaintStatus
from app.schemas.user import UserRole
from app.services.complaint_service import ComplaintService
from tests.fakes import FakeUserRepository

VALID_PASSWORD = "SecurePass123!"

VALID_CATEGORY_ID = "507f1f77bcf86cd799439015"
VALID_ORG_ID = "507f1f77bcf86cd799439012"
VALID_DEPT_ID = "507f1f77bcf86cd799439014"
VALID_USER_ID = "507f1f77bcf86cd799439011"
VALID_COMPLAINT_ID = "507f1f77bcf86cd799439013"
VALID_LOCATION = {"type": "Point", "coordinates": [-73.9857, 40.7484]}
VALID_PAYLOAD = {
    "title": "Large pothole on Main Street",
    "description": "Deep pothole causing vehicle damage near intersection",
    "category_id": VALID_CATEGORY_ID,
    "location": VALID_LOCATION,
    "address": "Main St & 1st Ave",
}


class FakeComplaintRepository:
    """In-memory stand-in for ComplaintRepository."""

    def __init__(self) -> None:
        self.complaints: dict[str, dict] = {}
        self._counter = 0

    async def create(self, complaint_data: dict) -> str:
        self._counter += 1
        complaint_id = f"{self._counter:024x}"
        # Generate complaint number server-side
        year = datetime.now(UTC).year
        complaint_number = f"CMP-{year}-{self._counter:06d}"
        self.complaints[complaint_id] = {"_id": complaint_id, "complaint_number": complaint_number, **complaint_data}
        return complaint_id

    async def find_by_id(self, complaint_id: str) -> dict | None:
        return self.complaints.get(complaint_id)

    async def find_by_id_for_user(self, complaint_id: str, user_id: str) -> dict | None:
        complaint = self.complaints.get(complaint_id)
        if complaint and complaint.get("user_id") == user_id:
            return complaint
        return None

    async def find_by_id_for_admin(self, complaint_id: str) -> dict | None:
        return self.complaints.get(complaint_id)

    async def find_by_id_in_organization(self, complaint_id: str, organization_id: str) -> dict | None:
        complaint = self.complaints.get(complaint_id)
        if complaint and complaint.get("organization_id") == organization_id:
            return complaint
        return None

    async def find_by_id_for_organization_staff(
        self, complaint_id: str, organization_id: str, department_id: str | None
    ) -> dict | None:
        complaint = self.complaints.get(complaint_id)
        if complaint and complaint.get("organization_id") == organization_id:
            if department_id is None or complaint.get("department_id") == department_id:
                return complaint
        return None

    async def find_by_id_with_user(self, user_id: str) -> dict | None:
        for complaint in self.complaints.values():
            if complaint.get("user_id") == user_id:
                return complaint
        return None

    async def update_by_user(self, complaint_id: str, user_id: str, update_data: dict) -> bool:
        complaint = self.complaints.get(complaint_id)
        if complaint and complaint.get("user_id") == user_id and complaint.get("status") == ComplaintStatus.SUBMITTED.value:
            complaint.update(update_data)
            complaint["updated_at"] = datetime.now(UTC)
            return True
        return False

    async def update_in_organization(self, complaint_id: str, organization_id: str, update_data: dict) -> bool:
        complaint = self.complaints.get(complaint_id)
        if complaint and complaint.get("organization_id") == organization_id:
            complaint.update(update_data)
            complaint["updated_at"] = datetime.now(UTC)
            return True
        return False


class FakeCategoryRepository:
    """In-memory stand-in for CategoryRepository."""

    def __init__(self) -> None:
        self.categories: dict[str, dict] = {}

    def seed(self, category_id: str, **data) -> str:
        self.categories[category_id] = {"_id": category_id, **data}
        return category_id

    async def find_by_id(self, category_id: str) -> dict | None:
        return self.categories.get(category_id)

    async def find_by_id_active(self, category_id: str) -> dict | None:
        cat = self.categories.get(category_id)
        if cat and cat.get("status") == CategoryStatus.ACTIVE.value:
            return cat
        return None


class FakeDepartmentRepository:
    """In-memory stand-in for DepartmentRepository."""

    def __init__(self) -> None:
        self.departments: dict[str, dict] = {}

    def seed(self, department_id: str, **data) -> str:
        self.departments[department_id] = {"_id": department_id, **data}
        return department_id

    async def find_by_id(self, department_id: str) -> dict | None:
        return self.departments.get(department_id)

    async def find_by_id_active_in_org(self, department_id: str, organization_id: str) -> dict | None:
        dept = self.departments.get(department_id)
        if dept and dept.get("organization_id") == organization_id and dept.get("is_active"):
            return dept
        return None


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def user_repository():
    return FakeUserRepository()


@pytest.fixture
def complaint_repository():
    return FakeComplaintRepository()


@pytest.fixture
def category_repository():
    repo = FakeCategoryRepository()
    # Seed a valid active category with default department
    repo.seed(
        VALID_CATEGORY_ID,
        organization_id=VALID_ORG_ID,
        name="Pothole",
        description="Road surface issues",
        icon="pothole",
        color="#FF6B35",
        default_department_id=VALID_DEPT_ID,
        severity_level=3,
        priority_weight=1.0,
        status=CategoryStatus.ACTIVE.value,
        sort_order=0,
    )
    return repo


@pytest.fixture
def department_repository():
    repo = FakeDepartmentRepository()
    # Seed a valid active department
    repo.seed(
        VALID_DEPT_ID,
        organization_id=VALID_ORG_ID,
        name="Road Maintenance",
        code="ROADS",
        description="Handles road issues",
        contact_email="roads@example.com",
        contact_phone="+15551234568",
        head_user_id=None,
        is_active=True,
    )
    return repo


@pytest.fixture
def complaint_service(
    complaint_repository: FakeComplaintRepository,
    category_repository: FakeCategoryRepository,
    department_repository: FakeDepartmentRepository,
) -> ComplaintService:
    return ComplaintService(complaint_repository, category_repository, department_repository)


@pytest.fixture
def user_service(user_repository: FakeUserRepository):
    from app.services.user_service import UserService
    return UserService(user_repository)


@pytest.fixture
def refresh_token_service():
    from tests.fakes import FakeRefreshTokenService
    return FakeRefreshTokenService()


@pytest.fixture
async def client(app, complaint_service: ComplaintService, user_service, user_repository: FakeUserRepository):
    app.dependency_overrides[get_complaint_service] = lambda: complaint_service
    from app.api.v1.auth import get_user_service as auth_get_user_service
    app.dependency_overrides[auth_get_user_service] = lambda: user_service
    from app.api.v1.auth import get_refresh_token_service
    app.dependency_overrides[get_refresh_token_service] = lambda: refresh_token_service
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class FakeRefreshTokenService:
    """In-memory stand-in for RefreshTokenService."""

    async def issue_token_pair(self, user_id: str, role: str | None = None):
        from app.schemas.token import TokenPairResponse
        return TokenPairResponse(
            access_token="fake_access_token",
            refresh_token="fake_refresh_token",
            token_type="bearer",
            expires_in=900,
        )

    async def rotate(self, refresh_token: str):
        from app.schemas.token import TokenPairResponse
        return TokenPairResponse(
            access_token="fake_access_token",
            refresh_token="fake_refresh_token",
            token_type="bearer",
            expires_in=900,
        )

    async def revoke(self, refresh_token: str) -> None:
        pass


def make_token(user_id: str, role: UserRole) -> str:
    return create_access_token(user_id=user_id, role=role.value)


def seed_user(repo: FakeUserRepository, role: UserRole, user_id: str | None = None) -> str:
    if user_id is None:
        if role == UserRole.CITIZEN:
            user_id = "507f1f77bcf86cd799439011"
        elif role == UserRole.ORGANIZATION_STAFF:
            user_id = "507f1f77bcf86cd799439021"
        elif role == UserRole.ORGANIZATION_ADMIN:
            user_id = "507f1f77bcf86cd799439022"
        elif role == UserRole.ADMIN:
            user_id = "507f1f77bcf86cd799439023"
        else:
            user_id = "507f1f77bcf86cd799439030"
    repo.seed(
        user_id=user_id,
        email=f"{role.value}@example.com",
        phone="+15550000000",
        role=role.value,
        status="active",
    )
    return user_id


class TestComplaintUpdateAPI:
    VALID_CATEGORY_ID = "507f1f77bcf86cd799439015"
    VALID_ORG_ID = "507f1f77bcf86cd799439012"
    VALID_DEPT_ID = "507f1f77bcf86cd799439014"
    VALID_USER_ID = "507f1f77bcf86cd799439011"
    VALID_COMPLAINT_ID = "507f1f77bcf86cd799439013"
    VALID_LOCATION = {"type": "Point", "coordinates": [-73.9857, 40.7484]}
    VALID_PAYLOAD = {
        "title": "Large pothole on Main Street",
        "description": "Deep pothole causing vehicle damage near intersection",
        "category_id": VALID_CATEGORY_ID,
        "location": VALID_LOCATION,
        "address": "Main St & 1st Ave",
    }

    async def test_unauthenticated_request_returns_401(
        self, client: AsyncClient
    ) -> None:
        response = await client.put(f"/api/v1/complaints/{self.VALID_COMPLAINT_ID}", json=self.VALID_PAYLOAD)
        assert response.status_code == 401

    async def test_citizen_can_update_submitted_complaint(
        self, client: AsyncClient, user_repository: FakeUserRepository, complaint_repository: FakeComplaintRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN, VALID_USER_ID)
        token = make_token(user_id, UserRole.CITIZEN)

        # Seed a SUBMITTED complaint owned by this user
        complaint_repository.complaints[VALID_COMPLAINT_ID] = {
            "_id": VALID_COMPLAINT_ID,
            "complaint_number": "CMP-2024-000001",
            "user_id": VALID_USER_ID,
            "organization_id": VALID_ORG_ID,
            "department_id": VALID_DEPT_ID,
            "category_id": VALID_CATEGORY_ID,
            "title": "Large pothole on Main Street",
            "description": "Deep pothole causing vehicle damage near intersection",
            "status": "SUBMITTED",
            "visibility": "public",
            "location": {"type": "Point", "coordinates": [-73.9857, 40.7484]},
            "address": "Main St & 1st Ave",
            "assigned_to": None,
            "assigned_at": None,
            "completed_at": None,
            "rejected_at": None,
            "rejection_reason": None,
            "duplicate_of": None,
            "likes_count": 0,
            "community_engagement_score": 0,
            "age_score": 0.0,
            "organization_priority_boost": 0.0,
            "sla_deadline": None,
            "priority_score": 0.0,
            "severity_score": 3,
            "metadata": None,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "title": "Updated pothole title",
            "description": "Updated description",
        }
        response = await client.put(
            f"/api/v1/complaints/{VALID_COMPLAINT_ID}", json=payload, headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["title"] == "Updated pothole title"
        assert data["data"]["description"] == "Updated description"
        assert data["data"]["status"] == "SUBMITTED"
        assert data["data"]["complaint_number"].startswith("CMP-")

    async def test_citizen_cannot_update_non_submitted_complaint(
        self, client: AsyncClient, user_repository: FakeUserRepository, complaint_repository: FakeComplaintRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN, VALID_USER_ID)
        token = make_token(user_id, UserRole.CITIZEN)

        # Seed an ONGOING complaint owned by this user
        complaint_repository.complaints[VALID_COMPLAINT_ID] = {
            "_id": VALID_COMPLAINT_ID,
            "complaint_number": "CMP-2024-000001",
            "user_id": VALID_USER_ID,
            "organization_id": VALID_ORG_ID,
            "department_id": VALID_DEPT_ID,
            "category_id": VALID_CATEGORY_ID,
            "title": "Large pothole on Main Street",
            "description": "Deep pothole causing vehicle damage near intersection",
            "status": "ONGOING",
            "visibility": "public",
            "location": {"type": "Point", "coordinates": [-73.9857, 40.7484]},
            "address": "Main St & 1st Ave",
            "assigned_to": "507f1f77bcf86cd799439015",
            "assigned_at": datetime.now(UTC),
            "completed_at": None,
            "rejected_at": None,
            "rejection_reason": None,
            "duplicate_of": None,
            "likes_count": 0,
            "community_engagement_score": 0,
            "age_score": 0.0,
            "organization_priority_boost": 0.0,
            "sla_deadline": None,
            "priority_score": 0.0,
            "severity_score": 3,
            "metadata": None,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

        headers = {"Authorization": f"Bearer {token}"}
        payload = {"title": "Updated title"}
        response = await client.put(
            f"/api/v1/complaints/{VALID_COMPLAINT_ID}", json=payload, headers=headers
        )
        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "VALIDATION_ERROR"
        assert "INVALID_STATUS_TRANSITION" in str(data["details"]["errors"])

    async def test_organization_staff_denied(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.ORGANIZATION_STAFF)
        token = make_token(user_id, UserRole.ORGANIZATION_STAFF)
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.put(
            "/api/v1/complaints/507f1f77bcf86cd799439013", json={"title": "Test"}, headers=headers
        )
        assert response.status_code == 403

    async def test_organization_admin_denied(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.ORGANIZATION_ADMIN)
        token = make_token(user_id, UserRole.ORGANIZATION_ADMIN)
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.put(
            "/api/v1/complaints/507f1f77bcf86cd799439013", json={"title": "Test"}, headers=headers
        )
        assert response.status_code == 403

    async def test_admin_denied_per_srs(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        """Admin should be denied per SRS - complaint update is citizen-only."""
        user_id = seed_user(user_repository, UserRole.ADMIN)
        token = make_token(user_id, UserRole.ADMIN)
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.put(
            "/api/v1/complaints/507f1f77bcf86cd799439013", json={"title": "Test"}, headers=headers
        )
        assert response.status_code == 403

    async def test_invalid_payload_returns_422(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}
        invalid_payload = {"title": "Hi"}  # too short
        response = await client.put(
            "/api/v1/complaints/507f1f77bcf86cd799439013", json=invalid_payload, headers=headers
        )
        assert response.status_code == 422

    async def test_invalid_title_too_short(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}
        payload = {**self.VALID_PAYLOAD, "title": "Hi"}
        response = await client.put(
            "/api/v1/complaints/507f1f77bcf86cd799439013", json=payload, headers=headers
        )
        assert response.status_code == 422

    async def test_invalid_title_too_long(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}
        payload = {**self.VALID_PAYLOAD, "title": "x" * 201}
        response = await client.put(
            "/api/v1/complaints/507f1f77bcf86cd799439013", json=payload, headers=headers
        )
        assert response.status_code == 422

    async def test_invalid_description_too_short(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}
        payload = {**self.VALID_PAYLOAD, "description": "Short"}
        response = await client.put(
            "/api/v1/complaints/507f1f77bcf86cd799439013", json=payload, headers=headers
        )
        assert response.status_code == 422

    async def test_invalid_description_too_long(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}
        payload = {**self.VALID_PAYLOAD, "description": "x" * 5001}
        response = await client.put(
            "/api/v1/complaints/507f1f77bcf86cd799439013", json=payload, headers=headers
        )
        assert response.status_code == 422

    async def test_invalid_location_missing_type(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}
        payload = {**self.VALID_PAYLOAD, "location": {"coordinates": [-73.9857, 40.7484]}}
        response = await client.put(
            "/api/v1/complaints/507f1f77bcf86cd799439013", json=payload, headers=headers
        )
        assert response.status_code == 422

    async def test_invalid_location_wrong_type(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}
        payload = {**self.VALID_PAYLOAD, "location": {"type": "Polygon", "coordinates": [[[0, 0]]]}}
        response = await client.put(
            "/api/v1/complaints/507f1f77bcf86cd799439013", json=payload, headers=headers
        )
        assert response.status_code == 422

    async def test_invalid_longitude_out_of_range(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}
        payload = {**self.VALID_PAYLOAD, "location": {"type": "Point", "coordinates": [181.0, 40.7484]}}
        response = await client.put(
            "/api/v1/complaints/507f1f77bcf86cd799439013", json=payload, headers=headers
        )
        assert response.status_code == 422

    async def test_invalid_latitude_out_of_range(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}
        payload = {**self.VALID_PAYLOAD, "location": {"type": "Point", "coordinates": [-73.9857, 91.0]}}
        response = await client.put(
            "/api/v1/complaints/507f1f77bcf86cd799439013", json=payload, headers=headers
        )
        assert response.status_code == 422

    async def test_malformed_coordinates(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}
        payload = {**self.VALID_PAYLOAD, "location": {"type": "Point", "coordinates": [-73.9857]}}
        response = await client.put(
            "/api/v1/complaints/507f1f77bcf86cd799439013", json=payload, headers=headers
        )
        assert response.status_code == 422

    async def test_mongo_operator_injection_rejected(
        self, client: AsyncClient, user_repository: FakeUserRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "title": "Test",
            "description": "Test",
            "category_id": "507f1f77bcf86cd799439015",
            "location": {"$near": {"$geometry": {"type": "Point", "coordinates": [0, 0]}}},
        }
        response = await client.put(
            "/api/v1/complaints/507f1f77bcf86cd799439013", json=payload, headers=headers
        )
        assert response.status_code == 422

    async def test_client_cannot_inject_category_id(
        self, client: AsyncClient, user_repository: FakeUserRepository, complaint_repository: FakeComplaintRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN, VALID_USER_ID)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}

        # Seed a SUBMITTED complaint
        complaint_repository.complaints[VALID_COMPLAINT_ID] = {
            "_id": VALID_COMPLAINT_ID,
            "user_id": VALID_USER_ID,
            "organization_id": VALID_ORG_ID,
            "department_id": VALID_DEPT_ID,
            "category_id": VALID_CATEGORY_ID,
            "title": "Test",
            "description": "Test",
            "status": "SUBMITTED",
            "visibility": "public",
            "location": VALID_LOCATION,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

        payload = {"title": "Test", "category_id": "507f1f77bcf86cd799439999"}
        response = await client.put(
            f"/api/v1/complaints/{VALID_COMPLAINT_ID}", json=payload, headers=headers
        )
        # Should reject category_id as it's not in the update schema
        assert response.status_code == 422

    async def test_client_cannot_inject_organization_id(
        self, client: AsyncClient, user_repository: FakeUserRepository, complaint_repository: FakeComplaintRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN, VALID_USER_ID)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}

        complaint_repository.complaints[VALID_COMPLAINT_ID] = {
            "_id": VALID_COMPLAINT_ID,
            "user_id": VALID_USER_ID,
            "organization_id": VALID_ORG_ID,
            "department_id": VALID_DEPT_ID,
            "category_id": VALID_CATEGORY_ID,
            "title": "Test",
            "description": "Test",
            "status": "SUBMITTED",
            "visibility": "public",
            "location": VALID_LOCATION,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

        payload = {"title": "Test", "organization_id": "507f1f77bcf86cd799439999"}
        response = await client.put(
            f"/api/v1/complaints/{VALID_COMPLAINT_ID}", json=payload, headers=headers
        )
        assert response.status_code == 422

    async def test_client_cannot_inject_department_id(
        self, client: AsyncClient, user_repository: FakeUserRepository, complaint_repository: FakeComplaintRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN, VALID_USER_ID)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}

        complaint_repository.complaints[VALID_COMPLAINT_ID] = {
            "_id": VALID_COMPLAINT_ID,
            "user_id": VALID_USER_ID,
            "organization_id": VALID_ORG_ID,
            "department_id": VALID_DEPT_ID,
            "category_id": VALID_CATEGORY_ID,
            "title": "Test",
            "description": "Test",
            "status": "SUBMITTED",
            "visibility": "public",
            "location": VALID_LOCATION,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

        payload = {"title": "Test", "department_id": "507f1f77bcf86cd799439999"}
        response = await client.put(
            f"/api/v1/complaints/{VALID_COMPLAINT_ID}", json=payload, headers=headers
        )
        assert response.status_code == 422

    async def test_client_cannot_inject_status(
        self, client: AsyncClient, user_repository: FakeUserRepository, complaint_repository: FakeComplaintRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN, VALID_USER_ID)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}

        complaint_repository.complaints[VALID_COMPLAINT_ID] = {
            "_id": VALID_COMPLAINT_ID,
            "user_id": VALID_USER_ID,
            "organization_id": VALID_ORG_ID,
            "department_id": VALID_DEPT_ID,
            "category_id": VALID_CATEGORY_ID,
            "title": "Test",
            "description": "Test",
            "status": "SUBMITTED",
            "visibility": "public",
            "location": VALID_LOCATION,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

        payload = {"title": "Test", "status": "COMPLETED"}
        response = await client.put(
            f"/api/v1/complaints/{VALID_COMPLAINT_ID}", json=payload, headers=headers
        )
        assert response.status_code == 422

    async def test_client_cannot_inject_complaint_number(
        self, client: AsyncClient, user_repository: FakeUserRepository, complaint_repository: FakeComplaintRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN, VALID_USER_ID)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}

        complaint_repository.complaints[VALID_COMPLAINT_ID] = {
            "_id": VALID_COMPLAINT_ID,
            "user_id": VALID_USER_ID,
            "organization_id": VALID_ORG_ID,
            "department_id": VALID_DEPT_ID,
            "category_id": VALID_CATEGORY_ID,
            "title": "Test",
            "description": "Test",
            "status": "SUBMITTED",
            "visibility": "public",
            "location": VALID_LOCATION,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

        payload = {"title": "Test", "complaint_number": "CMP-FAKE-000001"}
        response = await client.put(
            f"/api/v1/complaints/{VALID_COMPLAINT_ID}", json=payload, headers=headers
        )
        assert response.status_code == 422

    async def test_client_cannot_inject_likes_count(
        self, client: AsyncClient, user_repository: FakeUserRepository, complaint_repository: FakeComplaintRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN, VALID_USER_ID)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}

        complaint_repository.complaints[VALID_COMPLAINT_ID] = {
            "_id": VALID_COMPLAINT_ID,
            "user_id": VALID_USER_ID,
            "organization_id": VALID_ORG_ID,
            "department_id": VALID_DEPT_ID,
            "category_id": VALID_CATEGORY_ID,
            "title": "Test",
            "description": "Test",
            "status": "SUBMITTED",
            "visibility": "public",
            "location": VALID_LOCATION,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

        payload = {"title": "Test", "likes_count": 100}
        response = await client.put(
            f"/api/v1/complaints/{VALID_COMPLAINT_ID}", json=payload, headers=headers
        )
        assert response.status_code == 422

    async def test_client_cannot_inject_priority_score(
        self, client: AsyncClient, user_repository: FakeUserRepository, complaint_repository: FakeComplaintRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN, VALID_USER_ID)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}

        complaint_repository.complaints[VALID_COMPLAINT_ID] = {
            "_id": VALID_COMPLAINT_ID,
            "user_id": VALID_USER_ID,
            "organization_id": VALID_ORG_ID,
            "department_id": VALID_DEPT_ID,
            "category_id": VALID_CATEGORY_ID,
            "title": "Test",
            "description": "Test",
            "status": "SUBMITTED",
            "visibility": "public",
            "location": VALID_LOCATION,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

        payload = {"title": "Test", "priority_score": 100.0}
        response = await client.put(
            f"/api/v1/complaints/{VALID_COMPLAINT_ID}", json=payload, headers=headers
        )
        assert response.status_code == 422

    async def test_response_contains_no_credentials(
        self, client: AsyncClient, user_repository: FakeUserRepository, complaint_repository: FakeComplaintRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN, VALID_USER_ID)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}

        complaint_repository.complaints[VALID_COMPLAINT_ID] = {
            "_id": VALID_COMPLAINT_ID,
            "complaint_number": "CMP-2024-000001",
            "user_id": VALID_USER_ID,
            "organization_id": VALID_ORG_ID,
            "department_id": VALID_DEPT_ID,
            "category_id": VALID_CATEGORY_ID,
            "title": "Test",
            "description": "Test",
            "status": "SUBMITTED",
            "visibility": "public",
            "location": VALID_LOCATION,
            "address": "Test Address",
            "assigned_to": None,
            "assigned_at": None,
            "completed_at": None,
            "rejected_at": None,
            "rejection_reason": None,
            "duplicate_of": None,
            "likes_count": 0,
            "community_engagement_score": 0,
            "age_score": 0.0,
            "organization_priority_boost": 0.0,
            "sla_deadline": None,
            "priority_score": 0.0,
            "severity_score": 3,
            "metadata": None,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

        response = await client.put(
            f"/api/v1/complaints/{VALID_COMPLAINT_ID}", json={"title": "Test Title", "description": "Test Description"}, headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "password" not in str(data)
        assert "password_hash" not in str(data)
        assert "token" not in str(data).lower()

    async def test_complaint_actually_updated(
        self, client: AsyncClient, user_repository: FakeUserRepository, complaint_repository: FakeComplaintRepository
    ) -> None:
        user_id = seed_user(user_repository, UserRole.CITIZEN, VALID_USER_ID)
        token = make_token(user_id, UserRole.CITIZEN)
        headers = {"Authorization": f"Bearer {token}"}

        complaint_repository.complaints[VALID_COMPLAINT_ID] = {
            "_id": VALID_COMPLAINT_ID,
            "complaint_number": "CMP-2024-000001",
            "user_id": VALID_USER_ID,
            "organization_id": VALID_ORG_ID,
            "department_id": VALID_DEPT_ID,
            "category_id": VALID_CATEGORY_ID,
            "title": "Original Title",
            "description": "Original Description",
            "status": "SUBMITTED",
            "visibility": "public",
            "location": VALID_LOCATION,
            "address": "Main St & 1st Ave",
            "assigned_to": None,
            "assigned_at": None,
            "completed_at": None,
            "rejected_at": None,
            "rejection_reason": None,
            "duplicate_of": None,
            "likes_count": 0,
            "community_engagement_score": 0,
            "age_score": 0.0,
            "organization_priority_boost": 0.0,
            "sla_deadline": None,
            "priority_score": 0.0,
            "severity_score": 3,
            "metadata": None,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

        response = await client.put(
            f"/api/v1/complaints/{VALID_COMPLAINT_ID}",
            json={"title": "Updated Title", "description": "Updated Description"},
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["title"] == "Updated Title"
        assert data["data"]["description"] == "Updated Description"
        assert data["data"]["updated_at"] is not None

        # Verify it's actually persisted
        assert complaint_repository.complaints[VALID_COMPLAINT_ID]["title"] == "Updated Title"
        assert complaint_repository.complaints[VALID_COMPLAINT_ID]["description"] == "Updated Description"
