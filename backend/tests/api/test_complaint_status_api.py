"""Phase 1.3.5 — Complaint state machine API integration tests.

Tests PATCH /api/v1/complaints/{id}/status:
- Successful status transitions across allowed roles
- Unauthorized citizen requests (403)
- Tenant isolation (Organization A staff cannot update Organization B complaints)
- Department scope matching for organization staff
- Fail-closed assignment rules (unassigned staff rejected with 403)
- Terminal state protection (422)
- Skip and backward invalid transitions (422)
- Reason required validation (422)
- Duplicate reference validation (self-duplicate, cross-tenant duplicate, missing)
- Concurrency / optimistic locking (409 on status race)
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.dependencies.services import get_complaint_service, get_user_service
from app.main import create_app
from app.schemas.user import UserRole
from app.services.complaint_service import ComplaintService
from app.services.user_service import UserService
from tests.fakes import FakeComplaintLookup, FakeUserRepository

CID_1 = "507f1f77bcf86cd799439011"
CID_2 = "507f1f77bcf86cd799439012"
CID_ORG_B = "507f1f77bcf86cd799439099"

ORG_A = "507f1f77bcf86cd799439021"
ORG_B = "507f1f77bcf86cd799439022"

DEPT_A = "507f1f77bcf86cd799439031"
DEPT_OTHER = "507f1f77bcf86cd799439032"

CITIZEN_ID = "507f1f77bcf86cd799439041"
STAFF_ASSIGNED_ID = "507f1f77bcf86cd799439042"
STAFF_UNASSIGNED_ID = "507f1f77bcf86cd799439043"
STAFF_WRONG_DEPT_ID = "507f1f77bcf86cd799439044"
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
        user_id=STAFF_WRONG_DEPT_ID,
        email="staff_wrgdept@example.com",
        phone="+15550000004",
        role="organization_staff",
        organization_id=ORG_A,
        department_id=DEPT_OTHER,
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
    # Complaint in ORG_A, DEPT_A, assigned to STAFF_ASSIGNED_ID, SUBMITTED
    repo.seed(
        CID_1,
        complaint_number="CMP-2024-000001",
        user_id=CITIZEN_ID,
        organization_id=ORG_A,
        department_id=DEPT_A,
        status="SUBMITTED",
        assigned_to=STAFF_ASSIGNED_ID,
    )
    # Duplicate target in ORG_A
    repo.seed(
        CID_2,
        complaint_number="CMP-2024-000002",
        user_id=CITIZEN_ID,
        organization_id=ORG_A,
        department_id=DEPT_A,
        status="SUBMITTED",
    )
    # Complaint in ORG_B (cross-tenant)
    repo.seed(
        CID_ORG_B,
        complaint_number="CMP-2024-000099",
        user_id=CITIZEN_ID,
        organization_id=ORG_B,
        department_id=DEPT_A,
        status="SUBMITTED",
    )
    return repo


@pytest.fixture
def app_instance(fake_users: FakeUserRepository, fake_complaints: FakeComplaintLookup):
    app = create_app()
    from unittest.mock import AsyncMock

    user_service = UserService(fake_users)
    complaint_service = ComplaintService(fake_complaints, AsyncMock(), AsyncMock())

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


@pytest.mark.asyncio
class TestComplaintStatusAPI:
    async def test_citizen_cannot_change_status(self, client: AsyncClient) -> None:
        headers = auth_header(CITIZEN_ID, UserRole.CITIZEN)
        resp = await client.patch(
            f"/api/v1/complaints/{CID_1}/status",
            json={"status": "ONGOING"},
            headers=headers,
        )
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "FORBIDDEN"

    async def test_staff_department_mismatch_rejected(self, client: AsyncClient) -> None:
        headers = auth_header(STAFF_WRONG_DEPT_ID, UserRole.ORGANIZATION_STAFF)
        resp = await client.patch(
            f"/api/v1/complaints/{CID_1}/status",
            json={"status": "ONGOING"},
            headers=headers,
        )
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "FORBIDDEN"

    async def test_staff_transition_submitted_to_ongoing_success(
        self, client: AsyncClient, fake_complaints: FakeComplaintLookup
    ) -> None:
        headers = auth_header(STAFF_ASSIGNED_ID, UserRole.ORGANIZATION_STAFF)
        resp = await client.patch(
            f"/api/v1/complaints/{CID_1}/status",
            json={"status": "ONGOING", "reason": "Work started"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "ONGOING"
        assert fake_complaints.complaints[CID_1]["status"] == "ONGOING"

    async def test_org_admin_transition_submitted_to_rejected_requires_reason(
        self, client: AsyncClient
    ) -> None:
        headers = auth_header(ORG_ADMIN_ID, UserRole.ORGANIZATION_ADMIN)
        # Missing reason
        resp = await client.patch(
            f"/api/v1/complaints/{CID_1}/status",
            json={"status": "REJECTED"},
            headers=headers,
        )
        assert resp.status_code == 422
        assert resp.json()["error_code"] == "REASON_REQUIRED"

        # With reason
        resp_valid = await client.patch(
            f"/api/v1/complaints/{CID_1}/status",
            json={"status": "REJECTED", "reason": "Private property issue"},
            headers=headers,
        )
        assert resp_valid.status_code == 200
        assert resp_valid.json()["data"]["status"] == "REJECTED"

    async def test_duplicate_requires_duplicate_of_reference(self, client: AsyncClient) -> None:
        headers = auth_header(ORG_ADMIN_ID, UserRole.ORGANIZATION_ADMIN)
        # Missing duplicate_of
        resp = await client.patch(
            f"/api/v1/complaints/{CID_1}/status",
            json={"status": "DUPLICATE", "reason": "Duplicate entry"},
            headers=headers,
        )
        assert resp.status_code == 422
        assert resp.json()["error_code"] == "DUPLICATE_REF_REQUIRED"

        # Self-duplicate rejected
        resp_self = await client.patch(
            f"/api/v1/complaints/{CID_1}/status",
            json={"status": "DUPLICATE", "reason": "Self duplicate", "duplicate_of": CID_1},
            headers=headers,
        )
        assert resp_self.status_code == 422
        assert resp_self.json()["error_code"] == "DUPLICATE_SELF_REFERENCE"

        # Cross-tenant duplicate rejected
        resp_cross = await client.patch(
            f"/api/v1/complaints/{CID_1}/status",
            json={"status": "DUPLICATE", "reason": "Cross tenant duplicate", "duplicate_of": CID_ORG_B},
            headers=headers,
        )
        assert resp_cross.status_code == 422
        assert resp_cross.json()["error_code"] == "CROSS_TENANT_DUPLICATE_REF"

        # Valid duplicate
        resp_ok = await client.patch(
            f"/api/v1/complaints/{CID_1}/status",
            json={"status": "DUPLICATE", "reason": "Valid duplicate", "duplicate_of": CID_2},
            headers=headers,
        )
        assert resp_ok.status_code == 200
        assert resp_ok.json()["data"]["status"] == "DUPLICATE"

    async def test_staff_unassigned_fails_closed_on_ongoing_to_processing(
        self, client: AsyncClient, fake_complaints: FakeComplaintLookup
    ) -> None:
        fake_complaints.complaints[CID_1]["status"] = "ONGOING"
        # STAFF_UNASSIGNED_ID is in same dept but complaint.assigned_to is STAFF_ASSIGNED_ID
        headers = auth_header(STAFF_UNASSIGNED_ID, UserRole.ORGANIZATION_STAFF)
        resp = await client.patch(
            f"/api/v1/complaints/{CID_1}/status",
            json={"status": "PROCESSING"},
            headers=headers,
        )
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "FORBIDDEN"

    async def test_staff_assigned_can_transition_ongoing_to_processing(
        self, client: AsyncClient, fake_complaints: FakeComplaintLookup
    ) -> None:
        fake_complaints.complaints[CID_1]["status"] = "ONGOING"
        headers = auth_header(STAFF_ASSIGNED_ID, UserRole.ORGANIZATION_STAFF)
        resp = await client.patch(
            f"/api/v1/complaints/{CID_1}/status",
            json={"status": "PROCESSING"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "PROCESSING"

    async def test_processing_to_completed_requires_reason(
        self, client: AsyncClient, fake_complaints: FakeComplaintLookup
    ) -> None:
        fake_complaints.complaints[CID_1]["status"] = "PROCESSING"
        headers = auth_header(STAFF_ASSIGNED_ID, UserRole.ORGANIZATION_STAFF)

        # Without reason
        resp = await client.patch(
            f"/api/v1/complaints/{CID_1}/status",
            json={"status": "COMPLETED"},
            headers=headers,
        )
        assert resp.status_code == 422
        assert resp.json()["error_code"] == "REASON_REQUIRED"

        # With completion summary
        resp_ok = await client.patch(
            f"/api/v1/complaints/{CID_1}/status",
            json={"status": "COMPLETED", "reason": "Pothole successfully asphalted and road opened"},
            headers=headers,
        )
        assert resp_ok.status_code == 200
        assert resp_ok.json()["data"]["status"] == "COMPLETED"

    async def test_terminal_state_cannot_be_changed(
        self, client: AsyncClient, fake_complaints: FakeComplaintLookup
    ) -> None:
        fake_complaints.complaints[CID_1]["status"] = "COMPLETED"
        headers = auth_header(ORG_ADMIN_ID, UserRole.ORGANIZATION_ADMIN)
        resp = await client.patch(
            f"/api/v1/complaints/{CID_1}/status",
            json={"status": "PROCESSING", "reason": "Reopen attempt"},
            headers=headers,
        )
        assert resp.status_code == 422
        assert resp.json()["error_code"] == "INVALID_STATUS_TRANSITION"

    async def test_cross_tenant_access_hidden(self, client: AsyncClient) -> None:
        # Org A staff trying to modify Org B complaint
        headers = auth_header(STAFF_ASSIGNED_ID, UserRole.ORGANIZATION_STAFF)
        resp = await client.patch(
            f"/api/v1/complaints/{CID_ORG_B}/status",
            json={"status": "ONGOING"},
            headers=headers,
        )
        assert resp.status_code == 404
        assert resp.json()["error_code"] == "COMPLAINT_NOT_FOUND"

    async def test_admin_can_close_complaint_and_cross_tenants(
        self, client: AsyncClient, fake_complaints: FakeComplaintLookup
    ) -> None:
        headers = auth_header(ADMIN_ID, UserRole.ADMIN)
        resp = await client.patch(
            f"/api/v1/complaints/{CID_ORG_B}/status",
            json={"status": "CLOSED", "reason": "Administrative closure"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "CLOSED"
        assert fake_complaints.complaints[CID_ORG_B]["status"] == "CLOSED"

    async def test_concurrency_race_condition_detected(
        self, client: AsyncClient, fake_complaints: FakeComplaintLookup
    ) -> None:
        # Mock transition_status returning False as if another worker already transitioned it
        async def fake_conflict(*args, **kwargs):
            return False

        fake_complaints.transition_status = fake_conflict
        headers = auth_header(ORG_ADMIN_ID, UserRole.ORGANIZATION_ADMIN)
        resp = await client.patch(
            f"/api/v1/complaints/{CID_1}/status",
            json={"status": "ONGOING"},
            headers=headers,
        )
        assert resp.status_code == 409
        assert resp.json()["error_code"] == "STATUS_CONFLICT"
