"""API and integration tests for Phase 1.3.7 - Complaint Assignment."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.dependencies.services import get_complaint_service, get_user_service
from app.main import create_app
from app.schemas.complaint import ComplaintStatus
from app.schemas.user import UserRole
from app.services.complaint_service import ComplaintService
from app.services.user_service import UserService
from tests.fakes import (
    FakeComplaintImageRepository,
    FakeComplaintLookup,
    FakeComplaintUpdateRepository,
    FakeUserRepository,
)

ORG_A_ID = "507f1f77bcf86cd799439012"
ORG_B_ID = "507f1f77bcf86cd799439099"
DEPT_A1_ID = "507f1f77bcf86cd799439014"
DEPT_A2_ID = "507f1f77bcf86cd799439088"

ORG_ADMIN_A_ID = "507f1f77bcf86cd799439020"
ORG_ADMIN_B_ID = "507f1f77bcf86cd799439021"
GLOBAL_ADMIN_ID = "507f1f77bcf86cd799439022"
STAFF_A1_ID = "507f1f77bcf86cd799439023"
STAFF_A1_SECOND_ID = "507f1f77bcf86cd799439024"
STAFF_A2_ID = "507f1f77bcf86cd799439025"
STAFF_B_ID = "507f1f77bcf86cd799439026"
STAFF_INACTIVE_ID = "507f1f77bcf86cd799439027"
CITIZEN_ID = "507f1f77bcf86cd799439030"

COMPLAINT_SUBMITTED_ID = "507f1f77bcf86cd799439050"
COMPLAINT_ONGOING_ID = "507f1f77bcf86cd799439051"
COMPLAINT_PROCESSING_ID = "507f1f77bcf86cd799439052"
COMPLAINT_COMPLETED_ID = "507f1f77bcf86cd799439053"
COMPLAINT_ORG_B_ID = "507f1f77bcf86cd799439054"


def auth_header(user_id: str, role: UserRole) -> dict[str, str]:
    token = create_access_token(user_id=user_id, role=role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def fake_users() -> FakeUserRepository:
    repo = FakeUserRepository()
    repo.seed(
        ORG_ADMIN_A_ID,
        email="admin_a@org.gov",
        phone="+15550000001",
        role=UserRole.ORGANIZATION_ADMIN.value,
        organization_id=ORG_A_ID,
        status="active",
    )
    repo.seed(
        ORG_ADMIN_B_ID,
        email="admin_b@org.gov",
        phone="+15550000002",
        role=UserRole.ORGANIZATION_ADMIN.value,
        organization_id=ORG_B_ID,
        status="active",
    )
    repo.seed(
        GLOBAL_ADMIN_ID,
        email="global_admin@gov.in",
        phone="+15550000003",
        role=UserRole.ADMIN.value,
        status="active",
    )
    repo.seed(
        STAFF_A1_ID,
        email="staff_a1@org.gov",
        phone="+15550000004",
        role=UserRole.ORGANIZATION_STAFF.value,
        organization_id=ORG_A_ID,
        department_id=DEPT_A1_ID,
        status="active",
    )
    repo.seed(
        STAFF_A1_SECOND_ID,
        email="staff_a1_2@org.gov",
        phone="+15550000005",
        role=UserRole.ORGANIZATION_STAFF.value,
        organization_id=ORG_A_ID,
        department_id=DEPT_A1_ID,
        status="active",
    )
    repo.seed(
        STAFF_A2_ID,
        email="staff_a2@org.gov",
        phone="+15550000006",
        role=UserRole.ORGANIZATION_STAFF.value,
        organization_id=ORG_A_ID,
        department_id=DEPT_A2_ID,
        status="active",
    )
    repo.seed(
        STAFF_B_ID,
        email="staff_b@org.gov",
        phone="+15550000007",
        role=UserRole.ORGANIZATION_STAFF.value,
        organization_id=ORG_B_ID,
        department_id=DEPT_A1_ID,
        status="active",
    )
    repo.seed(
        STAFF_INACTIVE_ID,
        email="staff_inactive@org.gov",
        phone="+15550000008",
        role=UserRole.ORGANIZATION_STAFF.value,
        organization_id=ORG_A_ID,
        department_id=DEPT_A1_ID,
        status="suspended",
    )
    repo.seed(
        CITIZEN_ID,
        email="citizen@example.com",
        phone="+15550000009",
        role=UserRole.CITIZEN.value,
        status="active",
    )
    return repo


@pytest.fixture
def fake_complaints() -> FakeComplaintLookup:
    repo = FakeComplaintLookup()
    repo.seed(
        COMPLAINT_SUBMITTED_ID,
        user_id=CITIZEN_ID,
        organization_id=ORG_A_ID,
        department_id=DEPT_A1_ID,
        status=ComplaintStatus.SUBMITTED.value,
        complaint_number="CMP-2024-000001",
    )
    repo.seed(
        COMPLAINT_ONGOING_ID,
        user_id=CITIZEN_ID,
        organization_id=ORG_A_ID,
        department_id=DEPT_A1_ID,
        status=ComplaintStatus.ONGOING.value,
        assigned_to=STAFF_A1_ID,
        complaint_number="CMP-2024-000002",
    )
    repo.seed(
        COMPLAINT_PROCESSING_ID,
        user_id=CITIZEN_ID,
        organization_id=ORG_A_ID,
        department_id=DEPT_A1_ID,
        status=ComplaintStatus.PROCESSING.value,
        assigned_to=STAFF_A1_ID,
        complaint_number="CMP-2024-000003",
    )
    repo.seed(
        COMPLAINT_COMPLETED_ID,
        user_id=CITIZEN_ID,
        organization_id=ORG_A_ID,
        department_id=DEPT_A1_ID,
        status=ComplaintStatus.COMPLETED.value,
        assigned_to=STAFF_A1_ID,
        complaint_number="CMP-2024-000004",
    )
    repo.seed(
        COMPLAINT_ORG_B_ID,
        user_id=CITIZEN_ID,
        organization_id=ORG_B_ID,
        department_id=DEPT_A1_ID,
        status=ComplaintStatus.SUBMITTED.value,
        complaint_number="CMP-2024-000005",
    )
    return repo


@pytest.fixture
def fake_updates() -> FakeComplaintUpdateRepository:
    return FakeComplaintUpdateRepository()


@pytest.fixture
def fake_images() -> FakeComplaintImageRepository:
    return FakeComplaintImageRepository()


@pytest.fixture
def app(
    fake_users: FakeUserRepository,
    fake_complaints: FakeComplaintLookup,
    fake_updates: FakeComplaintUpdateRepository,
    fake_images: FakeComplaintImageRepository,
):
    app_instance = create_app()
    user_service = UserService(fake_users)
    complaint_service = ComplaintService(
        complaint_repo=fake_complaints,  # type: ignore[arg-type]
        category_repo=AsyncMock(),
        department_repo=AsyncMock(),
        complaint_update_repo=fake_updates,  # type: ignore[arg-type]
        complaint_image_repo=fake_images,  # type: ignore[arg-type]
        user_repo=fake_users,  # type: ignore[arg-type]
    )

    app_instance.dependency_overrides[get_complaint_service] = lambda: complaint_service
    app_instance.dependency_overrides[get_user_service] = lambda: user_service
    return app_instance


class TestComplaintAssignmentAPI:
    @pytest.mark.asyncio
    async def test_citizen_cannot_assign(self, app) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/api/v1/complaints/{COMPLAINT_SUBMITTED_ID}/assign",
                json={"assigned_to": STAFF_A1_ID},
                headers=auth_header(CITIZEN_ID, UserRole.CITIZEN),
            )
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_staff_cannot_assign(self, app) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/api/v1/complaints/{COMPLAINT_SUBMITTED_ID}/assign",
                json={"assigned_to": STAFF_A1_SECOND_ID},
                headers=auth_header(STAFF_A1_ID, UserRole.ORGANIZATION_STAFF),
            )
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_initial_assignment_submitted_to_ongoing(
        self, app, fake_complaints: FakeComplaintLookup, fake_updates: FakeComplaintUpdateRepository
    ) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/api/v1/complaints/{COMPLAINT_SUBMITTED_ID}/assign",
                json={"assigned_to": STAFF_A1_ID},
                headers=auth_header(ORG_ADMIN_A_ID, UserRole.ORGANIZATION_ADMIN),
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            assert body["data"]["id"] == COMPLAINT_SUBMITTED_ID
            assert body["data"]["assigned_to"]["id"] == STAFF_A1_ID
            assert body["data"]["status"] == "ONGOING"
            assert "assigned_at" in body["data"]

            # Verify complaint record mutated
            c = fake_complaints.complaints[COMPLAINT_SUBMITTED_ID]
            assert c["status"] == "ONGOING"
            assert c["assigned_to"] == STAFF_A1_ID

            # Verify timeline update created with required department_id
            updates = await fake_updates.find_by_complaint(COMPLAINT_SUBMITTED_ID)
            assert len(updates) == 1
            up = updates[0]
            assert up["update_type"] == "assignment"
            assert up["department_id"] is not None
            assert str(up["department_id"]) == DEPT_A1_ID
            assert str(up["organization_id"]) == ORG_A_ID

    @pytest.mark.asyncio
    async def test_reassignment_ongoing_to_ongoing(
        self, app, fake_complaints: FakeComplaintLookup, fake_updates: FakeComplaintUpdateRepository
    ) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/api/v1/complaints/{COMPLAINT_ONGOING_ID}/assign",
                json={"assigned_to": STAFF_A1_SECOND_ID},
                headers=auth_header(ORG_ADMIN_A_ID, UserRole.ORGANIZATION_ADMIN),
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            assert body["data"]["assigned_to"]["id"] == STAFF_A1_SECOND_ID
            assert body["data"]["status"] == "ONGOING"

            # Check reassignment timeline
            updates = await fake_updates.find_by_complaint(COMPLAINT_ONGOING_ID)
            assert len(updates) == 1
            assert updates[0]["update_type"] == "assignment"
            assert "reassigned" in updates[0]["message"]

    @pytest.mark.asyncio
    async def test_global_admin_can_assign(self, app) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/api/v1/complaints/{COMPLAINT_SUBMITTED_ID}/assign",
                json={"assigned_to": STAFF_A1_ID},
                headers=auth_header(GLOBAL_ADMIN_ID, UserRole.ADMIN),
            )
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_cross_tenant_complaint_hidden(self, app) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Org A Admin cannot access Org B Complaint
            resp = await client.patch(
                f"/api/v1/complaints/{COMPLAINT_ORG_B_ID}/assign",
                json={"assigned_to": STAFF_A1_ID},
                headers=auth_header(ORG_ADMIN_A_ID, UserRole.ORGANIZATION_ADMIN),
            )
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cross_tenant_target_staff_rejected(self, app) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Org A Admin attempts to assign Staff from Org B
            resp = await client.patch(
                f"/api/v1/complaints/{COMPLAINT_SUBMITTED_ID}/assign",
                json={"assigned_to": STAFF_B_ID},
                headers=auth_header(ORG_ADMIN_A_ID, UserRole.ORGANIZATION_ADMIN),
            )
            assert resp.status_code == 422
            assert resp.json()["error_code"] == "ORG_MISMATCH"

    @pytest.mark.asyncio
    async def test_department_mismatch_rejected(self, app) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Staff from Dept A2 cannot be assigned to Dept A1 complaint
            resp = await client.patch(
                f"/api/v1/complaints/{COMPLAINT_SUBMITTED_ID}/assign",
                json={"assigned_to": STAFF_A2_ID},
                headers=auth_header(ORG_ADMIN_A_ID, UserRole.ORGANIZATION_ADMIN),
            )
            assert resp.status_code == 422
            assert resp.json()["error_code"] == "DEPARTMENT_MISMATCH"

    @pytest.mark.asyncio
    async def test_nonexistent_target_user_rejected(self, app) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/api/v1/complaints/{COMPLAINT_SUBMITTED_ID}/assign",
                json={"assigned_to": "507f1f77bcf86cd799439999"},
                headers=auth_header(ORG_ADMIN_A_ID, UserRole.ORGANIZATION_ADMIN),
            )
            assert resp.status_code == 422
            assert resp.json()["error_code"] == "USER_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_inactive_target_user_rejected(self, app) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/api/v1/complaints/{COMPLAINT_SUBMITTED_ID}/assign",
                json={"assigned_to": STAFF_INACTIVE_ID},
                headers=auth_header(ORG_ADMIN_A_ID, UserRole.ORGANIZATION_ADMIN),
            )
            assert resp.status_code == 422
            assert resp.json()["error_code"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_terminal_complaint_rejected(self, app) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/api/v1/complaints/{COMPLAINT_COMPLETED_ID}/assign",
                json={"assigned_to": STAFF_A1_ID},
                headers=auth_header(ORG_ADMIN_A_ID, UserRole.ORGANIZATION_ADMIN),
            )
            assert resp.status_code == 422
            assert resp.json()["error_code"] == "INVALID_STATUS_TRANSITION"

    @pytest.mark.asyncio
    async def test_invalid_status_processing_rejected(self, app) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/api/v1/complaints/{COMPLAINT_PROCESSING_ID}/assign",
                json={"assigned_to": STAFF_A1_ID},
                headers=auth_header(ORG_ADMIN_A_ID, UserRole.ORGANIZATION_ADMIN),
            )
            assert resp.status_code == 422
            assert resp.json()["error_code"] == "INVALID_STATUS_TRANSITION"
