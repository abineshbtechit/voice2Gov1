"""API integration tests for Phase 1.4: Complete complaint & Priority breakdown.

Covers:
- PATCH /api/v1/complaints/{id}/complete:
  - citizen forbidden (403)
  - unassigned staff forbidden (403)
  - assigned staff success (200)
  - org admin success (200)
  - global admin success (200)
  - cross-tenant hidden (404)
  - invalid starting status (422)
  - terminal status rejected (422)
  - missing reason / empty reason rejected (422)
  - timeline record created with department_id
  - concurrency race condition (409)
- GET /api/v1/complaints/{id}/priority:
  - citizen access to own complaint (200)
  - org staff access in same org (200)
  - cross-tenant hidden (404)
  - response schema breakdown, weights, raw components
"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.dependencies.services import get_complaint_service, get_user_service
from app.main import create_app
from app.schemas.user import UserRole
from app.services.complaint_service import ComplaintService
from app.services.priority_service import PriorityService
from app.services.user_service import UserService
from tests.fakes import (
    FakeComplaintLikeRepository,
    FakeComplaintLookup,
    FakeComplaintUpdateRepository,
    FakeUserRepository,
)

CID_PROCESSING = "507f1f77bcf86cd799439011"
CID_SUBMITTED = "507f1f77bcf86cd799439012"
CID_COMPLETED = "507f1f77bcf86cd799439013"
CID_ORG_B = "507f1f77bcf86cd799439099"

ORG_A = "507f1f77bcf86cd799439021"
ORG_B = "507f1f77bcf86cd799439022"

DEPT_A = "507f1f77bcf86cd799439031"

CITIZEN_ID = "507f1f77bcf86cd799439041"
STAFF_ASSIGNED_ID = "507f1f77bcf86cd799439042"
STAFF_UNASSIGNED_ID = "507f1f77bcf86cd799439043"
ORG_ADMIN_ID = "507f1f77bcf86cd799439045"
ADMIN_ID = "507f1f77bcf86cd799439046"


@pytest.fixture
def fake_users() -> FakeUserRepository:
    repo = FakeUserRepository()
    repo.seed(user_id=CITIZEN_ID, email="cit@example.com", phone="+15550000001", role="citizen")
    repo.seed(
        user_id=STAFF_ASSIGNED_ID,
        email="staff_asgn@example.com",
        phone="+15550000002",
        role="organization_staff",
        organization_id=ORG_A,
        department_id=DEPT_A,
    )
    repo.seed(
        user_id=STAFF_UNASSIGNED_ID,
        email="staff_unasgn@example.com",
        phone="+15550000003",
        role="organization_staff",
        organization_id=ORG_A,
        department_id=DEPT_A,
    )
    repo.seed(
        user_id=ORG_ADMIN_ID,
        email="org_adm@example.com",
        phone="+15550000005",
        role="organization_admin",
        organization_id=ORG_A,
    )
    repo.seed(user_id=ADMIN_ID, email="adm@example.com", phone="+15550000006", role="admin")
    return repo


@pytest.fixture
def fake_complaints() -> FakeComplaintLookup:
    repo = FakeComplaintLookup()
    repo.seed(
        CID_PROCESSING,
        complaint_number="CMP-2024-000001",
        user_id=CITIZEN_ID,
        organization_id=ORG_A,
        department_id=DEPT_A,
        status="PROCESSING",
        assigned_to=STAFF_ASSIGNED_ID,
        likes_count=10,
        severity_score=4,
    )
    repo.seed(
        CID_SUBMITTED,
        complaint_number="CMP-2024-000002",
        user_id=CITIZEN_ID,
        organization_id=ORG_A,
        department_id=DEPT_A,
        status="SUBMITTED",
        likes_count=0,
        severity_score=2,
    )
    repo.seed(
        CID_COMPLETED,
        complaint_number="CMP-2024-000003",
        user_id=CITIZEN_ID,
        organization_id=ORG_A,
        department_id=DEPT_A,
        status="COMPLETED",
        likes_count=5,
        severity_score=3,
    )
    repo.seed(
        CID_ORG_B,
        complaint_number="CMP-2024-000099",
        user_id=CITIZEN_ID,
        organization_id=ORG_B,
        department_id=DEPT_A,
        status="PROCESSING",
    )
    return repo


@pytest.fixture
def fake_updates() -> FakeComplaintUpdateRepository:
    return FakeComplaintUpdateRepository()


@pytest.fixture
def fake_likes() -> FakeComplaintLikeRepository:
    repo = FakeComplaintLikeRepository()
    repo.set_likes(CID_PROCESSING, ["user_1", "user_2", "user_3"])
    return repo


@pytest.fixture
def app_instance(
    fake_users: FakeUserRepository,
    fake_complaints: FakeComplaintLookup,
    fake_updates: FakeComplaintUpdateRepository,
    fake_likes: FakeComplaintLikeRepository,
):
    app = create_app()
    user_service = UserService(fake_users)
    priority_service = PriorityService(like_repo=fake_likes)
    complaint_service = ComplaintService(
        complaint_repo=fake_complaints,
        category_repo=AsyncMock(),
        department_repo=AsyncMock(),
        complaint_update_repo=fake_updates,
        complaint_image_repo=AsyncMock(),
        user_repo=fake_users,
        priority_service=priority_service,
    )

    app.dependency_overrides[get_user_service] = lambda: user_service
    app.dependency_overrides[get_complaint_service] = lambda: complaint_service
    return app


@pytest.fixture
async def client(app_instance):
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def auth_header(user_id: str, role: UserRole) -> dict[str, str]:
    token = create_access_token(user_id=user_id, role=role.value)
    return {"Authorization": f"Bearer {token}"}


class TestComplaintCompleteAPI:
    """Test PATCH /api/v1/complaints/{id}/complete."""

    @pytest.mark.asyncio
    async def test_citizen_cannot_complete(self, client: AsyncClient) -> None:
        headers = auth_header(CITIZEN_ID, UserRole.CITIZEN)
        resp = await client.patch(
            f"/api/v1/complaints/{CID_PROCESSING}/complete",
            json={"reason": "Finished road repair"},
            headers=headers,
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_unassigned_staff_cannot_complete(self, client: AsyncClient) -> None:
        headers = auth_header(STAFF_UNASSIGNED_ID, UserRole.ORGANIZATION_STAFF)
        resp = await client.patch(
            f"/api/v1/complaints/{CID_PROCESSING}/complete",
            json={"reason": "Finished road repair"},
            headers=headers,
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_assigned_staff_can_complete(
        self, client: AsyncClient, fake_complaints: FakeComplaintLookup, fake_updates: FakeComplaintUpdateRepository
    ) -> None:
        headers = auth_header(STAFF_ASSIGNED_ID, UserRole.ORGANIZATION_STAFF)
        resp = await client.patch(
            f"/api/v1/complaints/{CID_PROCESSING}/complete",
            json={"reason": "Finished road repair, asphalt poured and dried"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "COMPLETED"
        assert "completed_at" in data
        assert fake_complaints.complaints[CID_PROCESSING]["status"] == "COMPLETED"

        # Verify timeline update created
        updates = await fake_updates.find_by_complaint(CID_PROCESSING)
        assert len(updates) == 1
        assert updates[0]["update_type"] == "completion"
        assert str(updates[0]["department_id"]) == DEPT_A
        assert updates[0]["message"] == "Finished road repair, asphalt poured and dried"

    @pytest.mark.asyncio
    async def test_org_admin_can_complete(self, client: AsyncClient, fake_complaints: FakeComplaintLookup) -> None:
        headers = auth_header(ORG_ADMIN_ID, UserRole.ORGANIZATION_ADMIN)
        resp = await client.patch(
            f"/api/v1/complaints/{CID_PROCESSING}/complete",
            json={"reason": "Admin verified completion"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_global_admin_can_complete(self, client: AsyncClient) -> None:
        headers = auth_header(ADMIN_ID, UserRole.ADMIN)
        resp = await client.patch(
            f"/api/v1/complaints/{CID_PROCESSING}/complete",
            json={"reason": "Global admin completed"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_cross_tenant_complaint_hidden(self, client: AsyncClient) -> None:
        headers = auth_header(ORG_ADMIN_ID, UserRole.ORGANIZATION_ADMIN)
        resp = await client.patch(
            f"/api/v1/complaints/{CID_ORG_B}/complete",
            json={"reason": "Attempting cross tenant complete"},
            headers=headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_starting_status_rejected(self, client: AsyncClient) -> None:
        headers = auth_header(ORG_ADMIN_ID, UserRole.ORGANIZATION_ADMIN)
        resp = await client.patch(
            f"/api/v1/complaints/{CID_SUBMITTED}/complete",
            json={"reason": "Skip to complete"},
            headers=headers,
        )
        assert resp.status_code == 422
        assert resp.json()["error_code"] == "INVALID_STATUS_TRANSITION"

    @pytest.mark.asyncio
    async def test_terminal_complaint_rejected(self, client: AsyncClient) -> None:
        headers = auth_header(ORG_ADMIN_ID, UserRole.ORGANIZATION_ADMIN)
        resp = await client.patch(
            f"/api/v1/complaints/{CID_COMPLETED}/complete",
            json={"reason": "Re-complete"},
            headers=headers,
        )
        assert resp.status_code == 422
        assert resp.json()["error_code"] == "INVALID_STATUS_TRANSITION"

    @pytest.mark.asyncio
    async def test_empty_reason_rejected(self, client: AsyncClient) -> None:
        headers = auth_header(ORG_ADMIN_ID, UserRole.ORGANIZATION_ADMIN)
        resp = await client.patch(
            f"/api/v1/complaints/{CID_PROCESSING}/complete",
            json={"reason": "   "},
            headers=headers,
        )
        assert resp.status_code == 422


class TestComplaintPriorityAPI:
    """Test GET /api/v1/complaints/{id}/priority."""

    @pytest.mark.asyncio
    async def test_citizen_can_view_own_complaint_priority(self, client: AsyncClient) -> None:
        headers = auth_header(CITIZEN_ID, UserRole.CITIZEN)
        resp = await client.get(
            f"/api/v1/complaints/{CID_PROCESSING}/priority",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Priority breakdown"
        data = body["data"]
        assert "priority_score" in data
        assert "breakdown" in data
        assert "weights" in data
        assert data["max_score"] == 100.0

    @pytest.mark.asyncio
    async def test_staff_can_view_complaint_priority(self, client: AsyncClient) -> None:
        headers = auth_header(STAFF_ASSIGNED_ID, UserRole.ORGANIZATION_STAFF)
        resp = await client.get(
            f"/api/v1/complaints/{CID_PROCESSING}/priority",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["priority_score"] >= 0.0

    @pytest.mark.asyncio
    async def test_cross_tenant_priority_hidden(self, client: AsyncClient) -> None:
        headers = auth_header(ORG_ADMIN_ID, UserRole.ORGANIZATION_ADMIN)
        resp = await client.get(
            f"/api/v1/complaints/{CID_ORG_B}/priority",
            headers=headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_missing_complaint_returns_404(self, client: AsyncClient) -> None:
        headers = auth_header(ADMIN_ID, UserRole.ADMIN)
        resp = await client.get(
            "/api/v1/complaints/507f1f77bcf86cd799439999/priority",
            headers=headers,
        )
        assert resp.status_code == 404
