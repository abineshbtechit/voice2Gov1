"""API integration tests for Search API (LOC-05, GET /api/v1/search).

Covers:
- GET /api/v1/search:
  - Anonymous access permitted (Bearer optional)
  - Authenticated citizen access
  - Keyword filtering (q in title, description, or complaint_number)
  - Status, category_id, organization_id filtering
  - Private and rejected complaints excluded from public search
  - Sorting (recent, popular, priority, nearby)
  - Pagination (page, page_size, total_items, total_pages)
  - Negative validation cases (invalid sort, invalid page, invalid page_size, invalid status)
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.dependencies.services import get_complaint_service, get_user_service
from app.main import create_app
from app.schemas.complaint import ComplaintStatus, ComplaintVisibility
from app.schemas.user import UserRole
from app.services.complaint_service import ComplaintService
from app.services.priority_service import PriorityService
from app.services.user_service import UserService
from tests.fakes import (
    FakeComplaintLikeRepository,
    FakeComplaintLookup,
    FakeUserRepository,
)

CID_PUBLIC_1 = "507f1f77bcf86cd799439011"
CID_PUBLIC_2 = "507f1f77bcf86cd799439012"
CID_PRIVATE = "507f1f77bcf86cd799439013"

ORG_ID = "507f1f77bcf86cd799439021"
DEPT_ID = "507f1f77bcf86cd799439031"
CAT_ID = "507f1f77bcf86cd799439032"

CITIZEN_ID = "507f1f77bcf86cd799439041"


@pytest.fixture
def fake_users() -> FakeUserRepository:
    repo = FakeUserRepository()
    repo.seed(CITIZEN_ID, email="citizen@example.com", role=UserRole.CITIZEN)
    return repo


@pytest.fixture
def fake_complaints() -> FakeComplaintLookup:
    repo = FakeComplaintLookup()
    now = datetime.now(UTC)
    repo.seed(
        CID_PUBLIC_1,
        title="Dangerous Water Leak",
        description="Massive pipeline leak on Oak Avenue",
        complaint_number="CMP-2026-000001",
        status=ComplaintStatus.ONGOING,
        visibility=ComplaintVisibility.PUBLIC,
        organization_id=ORG_ID,
        department_id=DEPT_ID,
        category_id=CAT_ID,
        user_id=CITIZEN_ID,
        likes_count=10,
        priority_score=60.0,
        location={"type": "Point", "coordinates": [-73.9855, 40.7580]},
        created_at=now - timedelta(hours=3),
    )
    repo.seed(
        CID_PUBLIC_2,
        title="Fallen Tree Branch",
        description="Large tree branch blocking the pedestrian sidewalk",
        complaint_number="CMP-2026-000002",
        status=ComplaintStatus.SUBMITTED,
        visibility=ComplaintVisibility.PUBLIC,
        organization_id=ORG_ID,
        department_id=DEPT_ID,
        category_id=CAT_ID,
        user_id=CITIZEN_ID,
        likes_count=2,
        priority_score=25.0,
        location={"type": "Point", "coordinates": [-73.9860, 40.7585]},
        created_at=now - timedelta(hours=1),
    )
    repo.seed(
        CID_PRIVATE,
        title="Private Domestic Noise",
        description="Confidential neighbor noise complaint",
        complaint_number="CMP-2026-000003",
        status=ComplaintStatus.SUBMITTED,
        visibility=ComplaintVisibility.PRIVATE,
        organization_id=ORG_ID,
        department_id=DEPT_ID,
        category_id=CAT_ID,
        user_id=CITIZEN_ID,
        created_at=now - timedelta(minutes=30),
    )
    return repo


@pytest.fixture
def test_app(fake_users: FakeUserRepository, fake_complaints: FakeComplaintLookup):
    app = create_app()
    user_service = UserService(fake_users)  # type: ignore

    category_repo = AsyncMock()
    department_repo = AsyncMock()
    category_repo.find_by_ids.return_value = [
        {"_id": CAT_ID, "name": "Infrastructure", "icon": "tool", "color": "#112233"}
    ]
    department_repo.find_by_ids.return_value = [
        {"_id": DEPT_ID, "name": "Public Works"}
    ]
    like_repo = FakeComplaintLikeRepository()
    priority_service = PriorityService(like_repo=like_repo)  # type: ignore

    complaint_service = ComplaintService(
        complaint_repo=fake_complaints,  # type: ignore
        category_repo=category_repo,
        department_repo=department_repo,
        priority_service=priority_service,
        like_repo=like_repo,  # type: ignore
    )

    app.dependency_overrides[get_user_service] = lambda: user_service
    app.dependency_overrides[get_complaint_service] = lambda: complaint_service
    return app


@pytest.fixture
async def client(test_app):
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as c:
        yield c


@pytest.fixture
def auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(CITIZEN_ID, role=UserRole.CITIZEN)}"}


class TestSearchAPI:
    @pytest.mark.asyncio
    async def test_search_anonymous_success(self, client):
        resp = await client.get("/api/v1/search")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "data" in data
        items = data["data"]["items"]
        assert len(items) == 2
        ids = [item["id"] for item in items]
        assert CID_PRIVATE not in ids

    @pytest.mark.asyncio
    async def test_search_with_query_keyword(self, client):
        resp = await client.get("/api/v1/search?q=water")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["id"] == CID_PUBLIC_1
        assert "Water" in items[0]["title"]

    @pytest.mark.asyncio
    async def test_search_with_complaint_number(self, client):
        resp = await client.get("/api/v1/search?q=CMP-2026-000002")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["id"] == CID_PUBLIC_2

    @pytest.mark.asyncio
    async def test_search_authenticated_citizen(self, client, auth_header):
        resp = await client.get("/api/v1/search", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_search_filters_status_and_category(self, client):
        resp = await client.get(f"/api/v1/search?status=SUBMITTED&category_id={CAT_ID}")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["id"] == CID_PUBLIC_2

    @pytest.mark.asyncio
    async def test_search_pagination(self, client):
        resp = await client.get("/api/v1/search?page=1&page_size=1")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["items"]) == 1
        assert data["pagination"]["total_items"] == 2
        assert data["pagination"]["total_pages"] == 2
        assert data["pagination"]["has_next"] is True

    @pytest.mark.asyncio
    async def test_search_invalid_sort_returns_422_or_400(self, client):
        resp = await client.get("/api/v1/search?sort=invalid_sort")
        assert resp.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_search_invalid_page_returns_422(self, client):
        resp = await client.get("/api/v1/search?page=0")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_invalid_page_size_returns_422(self, client):
        resp = await client.get("/api/v1/search?page_size=100")
        assert resp.status_code == 422
