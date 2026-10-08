# Voice2Gov Testing Strategy

## Overview
Comprehensive testing approach covering unit, integration, API, security, and performance tests for the Voice2Gov backend.

---

## Test Pyramid

```
                    ┌─────────────┐
                    │  E2E/UI     │  ← Few, critical paths
                    └─────────────┘
              ┌───────────────────┐
              │   Integration     │  ← API + DB, Auth flows
              └───────────────────┘
        ┌─────────────────────────────┐
        │         Unit Tests          │  ← Many, fast, isolated
        └─────────────────────────────┘
```

### Target Coverage
| Layer | Coverage Target | Tools |
|-------|----------------|-------|
| Unit | 85%+ | pytest, pytest-asyncio, faker |
| Integration | 70%+ | pytest, httpx, testcontainers |
| Security | 100% critical paths | bandit, custom tests |
| Performance | Key endpoints | locust, pytest-benchmark |

---

## Test Structure

```
tests/
├── conftest.py                 # Shared fixtures, test DB setup
├── unit/
│   ├── test_auth_service.py
│   ├── test_complaint_service.py
│   ├── test_priority_service.py
│   ├── test_routing_service.py
│   ├── test_notification_service.py
│   ├── test_image_service.py
│   ├── test_repositories/
│   │   ├── test_user_repo.py
│   │   ├── test_complaint_repo.py
│   │   └── ...
│   ├── test_validators/
│   │   ├── test_file_validator.py
│   │   └── test_input_sanitization.py
│   └── test_utils/
│       ├── test_pagination.py
│       ├── test_geojson.py
│       └── test_error_codes.py
├── integration/
│   ├── test_auth_api.py
│   ├── test_complaint_api.py
│   ├── test_feed_api.py
│   ├── test_organization_api.py
│   ├── test_admin_api.py
│   └── test_notification_api.py
├── security/
│   ├── test_rbac.py
│   ├── test_token_security.py
│   ├── test_file_upload.py
│   ├── test_injection.py
│   ├── test_rate_limiting.py
│   └── test_org_isolation.py
├── performance/
│   ├── test_feed_performance.py
│   ├── test_complaint_creation.py
│   └── test_concurrent_users.py
└── fixtures/
    ├── users.json
    ├── complaints.json
    └── organizations.json
```

---

## Test Database Strategy

### Testcontainers (Integration Tests)
```python
# conftest.py
import pytest
from testcontainers.mongodb import MongoDbContainer
from pymongo.asynchronous import AsyncMongoClient

@pytest.fixture(scope="session")
def mongodb_container():
    with MongoDbContainer("mongo:7.0") as mongo:
        yield mongo

@pytest.fixture(scope="session")
async def mongo_client(mongodb_container):
    client = AsyncMongoClient(mongodb_container.get_connection_url())
    yield client
    await client.close()

@pytest.fixture(scope="function")
async def test_db(mongo_client):
    db = mongo_client["voice2gov_test"]
    # Create indexes
    await create_indexes(db)
    yield db
    # Cleanup
    await mongo_client.drop_database("voice2gov_test")

@pytest.fixture
async def clean_db(test_db):
    """Function-scoped clean database"""
    yield test_db
    # Drop all collections after test
    for coll in await test_db.list_collection_names():
        await test_db[coll].delete_many({})
```

### Unit Test Mocking
```python
# Unit tests use mocked repositories
@pytest.fixture
def mock_user_repo():
    return AsyncMock(spec=UserRepository)

@pytest.fixture
def auth_service(mock_user_repo, mock_settings_repo):
    return AuthService(mock_user_repo, mock_settings_repo)
```

---

## Unit Test Examples

### Auth Service
```python
# tests/unit/test_auth_service.py
class TestAuthService:
    @pytest.mark.asyncio
    async def test_register_creates_user(self, auth_service, mock_user_repo):
        mock_user_repo.find_by_email.return_value = None
        mock_user_repo.find_by_phone.return_value = None
        mock_user_repo.create.return_value = User(id=ObjectId(), ...)
        
        result = await auth_service.register(RegisterRequest(
            email="test@example.com",
            phone="+15551234567",
            password="SecurePass123!",
            full_name="Test User"
        ))
        
        assert result.user_id is not None
        mock_user_repo.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_register_duplicate_email_raises(self, auth_service, mock_user_repo):
        mock_user_repo.find_by_email.return_value = User(...)
        
        with pytest.raises(ConflictException) as exc:
            await auth_service.register(RegisterRequest(email="exists@example.com", ...))
        
        assert exc.value.error_code == "EMAIL_EXISTS"
    
    @pytest.mark.asyncio
    async def test_login_valid_credentials(self, auth_service, mock_user_repo):
        user = User(password_hash=bcrypt.hash("SecurePass123!"), ...)
        mock_user_repo.find_by_identifier.return_value = user
        
        result = await auth_service.login(LoginRequest(
            identifier="test@example.com",
            password="SecurePass123!"
        ))
        
        assert result.access_token is not None
        assert result.refresh_token is not None
    
    @pytest.mark.asyncio
    async def test_login_invalid_password(self, auth_service, mock_user_repo):
        user = User(password_hash=bcrypt.hash("WrongPass"), ...)
        mock_user_repo.find_by_identifier.return_value = user
        
        with pytest.raises(UnauthorizedException) as exc:
            await auth_service.login(LoginRequest(
                identifier="test@example.com",
                password="SecurePass123!"
            ))
        
        assert exc.value.error_code == "INVALID_CREDENTIALS"
```

### Complaint Service - State Machine
```python
# tests/unit/test_complaint_service.py
class TestComplaintStateMachine:
    @pytest.mark.asyncio
    async def test_submitted_to_ongoing_allowed(self, complaint_service, sample_complaint):
        sample_complaint.status = "SUBMITTED"
        
        result = await complaint_service.change_status(
            sample_complaint, "ONGOING", staff_user, "Assigned to team"
        )
        
        assert result.status == "ONGOING"
        assert result.assigned_to == staff_user.id
    
    @pytest.mark.asyncio
    async def test_submitted_to_completed_forbidden(self, complaint_service, sample_complaint):
        sample_complaint.status = "SUBMITTED"
        
        with pytest.raises(BusinessLogicException) as exc:
            await complaint_service.change_status(
                sample_complaint, "COMPLETED", staff_user, "Skip steps"
            )
        
        assert exc.value.error_code == "INVALID_STATUS_TRANSITION"
    
    @pytest.mark.asyncio
    async def test_citizen_cannot_change_status(self, complaint_service, sample_complaint, citizen_user):
        sample_complaint.status = "SUBMITTED"
        sample_complaint.user_id = citizen_user.id
        
        with pytest.raises(ForbiddenException):
            await complaint_service.change_status(
                sample_complaint, "ONGOING", citizen_user, "Trying to hack"
            )
    
    @pytest.mark.asyncio
    async def test_rejected_requires_reason(self, complaint_service, sample_complaint, staff_user):
        sample_complaint.status = "SUBMITTED"
        
        with pytest.raises(ValidationException) as exc:
            await complaint_service.change_status(
                sample_complaint, "REJECTED", staff_user, ""  # Empty reason
            )
        
        assert exc.value.error_code == "REASON_REQUIRED"
```

### Priority Service
```python
# tests/unit/test_priority_service.py
class TestPriorityService:
    @pytest.mark.asyncio
    async def test_calculates_priority_with_defaults(self, priority_service, sample_complaint):
        sample_complaint.severity_score = 4
        sample_complaint.created_at = datetime.utcnow() - timedelta(hours=72)
        
        # Mock like count
        priority_service.like_repo.count_by_complaint.return_value = 25
        
        result = await priority_service.calculate_priority(sample_complaint)
        
        # severity: (4/5)*40*0.4 = 12.8
        # engagement: min(25*1, 30)*0.3 = 7.5
        # age: min(72/168*20, 20)*0.2 = 1.71
        # org_boost: 0
        # total = 22.0
        assert 21.5 <= result.priority_score <= 22.5
    
    @pytest.mark.asyncio
    async def test_engagement_capped_at_max(self, priority_service, sample_complaint):
        priority_service.like_repo.count_by_complaint.return_value = 100
        
        result = await priority_service.calculate_priority(sample_complaint)
        
        # engagement capped at 30 * 0.3 = 9
        assert result.breakdown.community_engagement_score == 9.0
    
    @pytest.mark.asyncio
    async def test_org_override_weights(self, priority_service, sample_complaint):
        # Organization has custom weights - DEFERRED TO PHASE 2
        # This test is explicitly skipped in Phase 1
        pytest.skip("Phase 2 feature: organization priority weight overrides")
        
        # sample_complaint.organization_id = org_with_custom_weights.id
        # result = await priority_service.calculate_priority(sample_complaint)
        # assert result.weights.community_engagement == 0.25  # org custom
```

### Routing Service
```python
# tests/unit/test_routing_service.py
class TestRoutingService:
    @pytest.mark.asyncio
    async def test_routes_to_category_default_department(self, routing_service):
        category = Category(default_department_id=dept_id)
        
        result = await routing_service.route_complaint(category, organization)
        
        assert result.department_id == dept_id
    
    @pytest.mark.asyncio
    async def test_raises_when_category_has_no_default_department(self, routing_service):
        category = Category(default_department_id=None)
        organization = Organization()  # No default_department_id
        
        with pytest.raises(RoutingConfigurationError):
            await routing_service.route_complaint(category, organization)
    
    @pytest.mark.asyncio
    async def test_rejects_cross_org_department(self, routing_service):
        # Category belongs to org A, but default_department_id references org B's department
        category = Category(
            organization_id=org_a_id,
            default_department_id=dept_b_id  # dept_b belongs to org B
        )
        
        with pytest.raises(RoutingConfigurationError):
            await routing_service.route_complaint(category, org_a)
```

---

## Integration Test Examples

### Auth API
```python
# tests/integration/test_auth_api.py
class TestAuthAPI:
    @pytest.mark.asyncio
    async def test_register_success(self, client, clean_db):
        response = await client.post("/api/v1/auth/register", json={
            "email": "newuser@example.com",
            "phone": "+15551112222",
            "password": "SecurePass123!",
            "full_name": "New User"
        })
        
        assert response.status_code == 201
        assert response.json()["success"] is True
        assert "user_id" in response.json()["data"]
    
    @pytest.mark.asyncio
    async def test_login_returns_tokens(self, client, clean_db, sample_user):
        response = await client.post("/api/v1/auth/login", json={
            "identifier": sample_user.email,
            "password": "SecurePass123!"
        })
        
        assert response.status_code == 200
        data = response.json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_refresh_token_rotation(self, client, clean_db, sample_user):
        # Login
        login_resp = await client.post("/api/v1/auth/login", json={...})
        refresh_token = login_resp.cookies.get("refresh_token")
        
        # Refresh
        response = await client.post("/api/v1/auth/refresh", cookies={"refresh_token": refresh_token})
        
        assert response.status_code == 200
        new_access = response.json()["data"]["access_token"]
        new_refresh = response.cookies.get("refresh_token")
        
        # Old refresh token should be revoked
        assert new_refresh != refresh_token
    
    @pytest.mark.asyncio
    async def test_revoked_refresh_token_rejected(self, client, clean_db, sample_user):
        login_resp = await client.post("/api/v1/auth/login", json={...})
        refresh_token = login_resp.cookies.get("refresh_token")
        
        # Logout (revokes token)
        await client.post("/api/v1/auth/logout", cookies={"refresh_token": refresh_token})
        
        # Try to use revoked token
        response = await client.post("/api/v1/auth/refresh", cookies={"refresh_token": refresh_token})
        
        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_REVOKED"
```

### Complaint API
```python
# tests/integration/test_complaint_api.py
class TestComplaintAPI:
    @pytest.mark.asyncio
    async def test_create_complaint_citizen(self, auth_client, category, department):
        response = await auth_client.post("/api/v1/complaints", json={
            "title": "Test Complaint",
            "description": "This is a test complaint description",
            "category_id": str(category.id),
            "location": {"type": "Point", "coordinates": [-73.9857, 40.7484]},
            "address": "Test Address"
        })
        
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["status"] == "SUBMITTED"
        assert data["priority_score"] > 0
    
    @pytest.mark.asyncio
    async def test_get_my_complaints(self, auth_client, sample_complaints):
        response = await auth_client.get("/api/v1/complaints/my")
        
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["items"]) == len(sample_complaints)
    
    @pytest.mark.asyncio
    async def test_org_staff_sees_only_org_complaints(self, org_staff_client, other_org_complaint):
        response = await org_staff_client.get("/api/v1/complaints")
        
        assert response.status_code == 200
        data = response.json()["data"]
        # Should not see other org's complaint
        assert all(c["organization_id"] == org_staff_client.org_id for c in data["items"])
```

### Feed API
```python
# tests/integration/test_feed_api.py
class TestFeedAPI:
    @pytest.mark.asyncio
    async def test_feed_pagination(self, client, many_complaints):
        response = await client.get("/api/v1/feed?page=1&page_size=10")
        
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["items"]) == 10
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["has_next"] is True
    
    @pytest.mark.asyncio
    async def test_feed_sort_priority(self, client, complaints_with_priority):
        response = await client.get("/api/v1/feed?sort=priority")
        
        assert response.status_code == 200
        data = response.json()["data"]
        scores = [c["priority_score"] for c in data["items"]]
        assert scores == sorted(scores, reverse=True)
    
    @pytest.mark.asyncio
    async def test_feed_nearby(self, client, geo_complaints):
        response = await client.get("/api/v1/feed?sort=nearby&lat=40.7484&lng=-73.9857&radius_km=5")
        
        assert response.status_code == 200
        data = response.json()["data"]
        # All should be within 5km
        for complaint in data["items"]:
            assert complaint["distance_km"] <= 5
    
    @pytest.mark.asyncio
    async def test_like_duplicate_prevented(self, auth_client, sample_complaint):
        # First like
        await auth_client.post(f"/api/v1/complaints/{sample_complaint.id}/like")
        
        # Second like should fail
        response = await auth_client.post(f"/api/v1/complaints/{sample_complaint.id}/like")
        
        assert response.status_code == 409
        assert response.json()["error_code"] == "DUPLICATE_LIKE"
```

---

## Security Tests

### RBAC Tests
```python
# tests/security/test_rbac.py
class TestRBAC:
    @pytest.mark.asyncio
    async def test_citizen_cannot_access_org_complaints(self, citizen_client, org_complaint):
        response = await citizen_client.get(f"/api/v1/complaints/{org_complaint.id}")
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_org_staff_cannot_access_other_org(self, org_staff_client, other_org_complaint):
        response = await org_staff_client.get(f"/api/v1/complaints/{other_org_complaint.id}")
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_org_staff_can_access_assigned(self, org_staff_client, assigned_complaint):
        response = await org_staff_client.get(f"/api/v1/complaints/{assigned_complaint.id}")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_admin_can_access_all(self, admin_client, any_complaint):
        response = await admin_client.get(f"/api/v1/complaints/{any_complaint.id}")
        assert response.status_code == 200
```

### Token Security
```python
# tests/security/test_token_security.py
class TestTokenSecurity:
    @pytest.mark.asyncio
    async def test_expired_access_token_rejected(self, client, expired_token):
        response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_EXPIRED"
    
    @pytest.mark.asyncio
    async def test_tampered_token_rejected(self, client, tampered_token):
        response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
        assert response.status_code == 401
        assert response.json()["error_code"] == "TOKEN_INVALID"
    
    @pytest.mark.asyncio
    async def test_access_token_not_in_url(self, client, valid_token):
        # Tokens should not be accepted in query params
        response = await client.get(f"/api/v1/auth/me?token={valid_token}")
        assert response.status_code == 401
```

### File Upload Security
```python
# tests/security/test_file_upload.py
class TestFileUploadSecurity:
    @pytest.mark.asyncio
    async def test_rejects_executable_disguised_as_image(self, auth_client):
        fake_image = b"<?php system($_GET['cmd']); ?>"
        files = {"files": ("shell.php", fake_image, "image/jpeg")}
        
        response = await auth_client.post("/api/v1/complaints/123/images", files=files, data={"image_type": "evidence"})
        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_FILE_TYPE"
    
    @pytest.mark.asyncio
    async def test_rejects_oversized_file(self, auth_client):
        large_file = b"x" * (11 * 1024 * 1024)  # 11MB > 10MB limit
        files = {"files": ("large.jpg", large_file, "image/jpeg")}
        
        response = await auth_client.post("/api/v1/complaints/123/images", files=files, data={"image_type": "evidence"})
        assert response.status_code == 400
        assert response.json()["error_code"] == "FILE_TOO_LARGE"
    
    @pytest.mark.asyncio
    async def test_filename_path_traversal_blocked(self, auth_client):
        files = {"files": ("../../../etc/passwd", b"content", "image/jpeg")}
        
        response = await auth_client.post("/api/v1/complaints/123/images", files=files, data={"image_type": "evidence"})
        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_FILENAME"
```

### Injection Tests
```python
# tests/security/test_injection.py
class TestInjection:
    @pytest.mark.asyncio
    async def test_nosql_injection_in_query_params(self, client):
        # Attempt to inject MongoDB operators
        response = await client.get("/api/v1/complaints?status[$ne]=REJECTED")
        assert response.status_code == 400  # Validation rejects
    
    @pytest.mark.asyncio
    async def test_nosql_injection_in_body(self, auth_client):
        response = await auth_client.post("/api/v1/complaints", json={
            "title": {"$gt": ""},  # MongoDB operator
            "description": "test",
            "category_id": "valid_id",
            "location": {"type": "Point", "coordinates": [0, 0]}
        })
        assert response.status_code == 422  # Pydantic rejects
```

### Organization Isolation
```python
# tests/security/test_org_isolation.py
class TestOrgIsolation:
    @pytest.mark.asyncio
    async def test_staff_cannot_list_other_org_users(self, org_staff_client, other_org_user):
        response = await org_staff_client.get("/api/v1/admin/users")  # If endpoint exists
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_staff_cannot_see_other_org_departments(self, org_staff_client):
        response = await org_staff_client.get("/api/v1/departments")
        assert response.status_code == 200
        data = response.json()["data"]
        assert all(d["organization_id"] == org_staff_client.org_id for d in data["items"])
    
    @pytest.mark.asyncio
    async def test_admin_can_see_all_orgs(self, admin_client, multiple_orgs):
        response = await admin_client.get("/api/v1/organizations")
        assert response.status_code == 200
        data = response.json()["data"]
        org_ids = {o["id"] for o in data["items"]}
        assert len(org_ids) == len(multiple_orgs)
```

---

## Performance Tests

### Feed Performance
```python
# tests/performance/test_feed_performance.py
class TestFeedPerformance:
    @pytest.mark.asyncio
    async def test_feed_load_under_2_seconds(self, client, large_dataset):
        import time
        start = time.perf_counter()
        response = await client.get("/api/v1/feed?page_size=20")
        elapsed = time.perf_counter() - start
        
        assert response.status_code == 200
        assert elapsed < 2.0  # SRS requirement
    
    @pytest.mark.asyncio
    async def test_priority_calculation_performance(self, priority_service, many_complaints):
        import time
        start = time.perf_counter()
        
        for complaint in many_complaints[:100]:
            await priority_service.calculate_priority(complaint)
        
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0  # 100 calculations under 1 second
```

### Locust Load Test
```python
# tests/performance/locustfile.py
from locust import HttpUser, task, between

class Voice2GovUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        # Login
        response = self.client.post("/api/v1/auth/login", json={
            "identifier": "test@example.com",
            "password": "SecurePass123!"
        })
        self.token = response.json()["data"]["access_token"]
        self.client.headers["Authorization"] = f"Bearer {self.token}"
    
    @task(10)
    def view_feed(self):
        self.client.get("/api/v1/feed?page_size=20")
    
    @task(3)
    def view_complaint(self):
        self.client.get("/api/v1/complaints/507f1f77bcf86cd799439013")
    
    @task(1)
    def create_complaint(self):
        self.client.post("/api/v1/complaints", json={
            "title": "Load test complaint",
            "description": "Description for load testing",
            "category_id": "507f1f77bcf86cd799439012",
            "location": {"type": "Point", "coordinates": [-73.9857, 40.7484]}
        })
```

---

## CI/CD Integration

### GitHub Actions Workflow
```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/unit -v --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v3
  
  integration:
    runs-on: ubuntu-latest
    services:
      mongodb:
        image: mongo:7.0
        ports: [27017:27017]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/integration -v
  
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -r requirements-dev.txt
      - run: bandit -r app/ -f json -o bandit-report.json
      - run: pytest tests/security -v
  
  performance:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule' || github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - run: pip install locust
      - run: locust -f tests/performance/locustfile.py --headless -u 50 -t 60s
```

---

## Test Data Management

### Fixtures
```python
# tests/conftest.py
@pytest.fixture
def sample_user():
    return User(
        id=ObjectId(),
        email="test@example.com",
        phone="+15551234567",
        full_name="Test User",
        role="citizen",
        password_hash=bcrypt.hash("SecurePass123!"),
        is_active=True,
        is_verified=True
    )

@pytest.fixture
def sample_complaint(sample_user, sample_category, sample_department):
    return Complaint(
        id=ObjectId(),
        user_id=sample_user.id,
        organization_id=sample_department.organization_id,
        department_id=sample_department.id,
        category_id=sample_category.id,
        title="Test Complaint",
        description="Test description for complaint",
        status="SUBMITTED",
        priority_score=50.0,
        severity_score=sample_category.severity_level,
        location={"type": "Point", "coordinates": [-73.9857, 40.7484]},
        visibility="public",
        created_at=datetime.utcnow()
    )
```

### Factory Pattern (Factory Boy)
```python
# tests/factories.py
import factory
from factory import Faker
from bson import ObjectId

class UserFactory(factory.Factory):
    class Meta:
        model = User
    
    id = factory.LazyFunction(ObjectId)
    email = factory.LazyAttribute(lambda _: Faker("email").generate())
    phone = factory.LazyAttribute(lambda _: Faker("phone_number").generate())
    full_name = factory.LazyAttribute(lambda _: Faker("name").generate())
    role = "citizen"
    password_hash = bcrypt.hash("SecurePass123!")
    is_active = True
    is_verified = True
    created_at = factory.LazyFunction(datetime.utcnow)
```

---

## Test Commands

```bash
# Run all tests
pytest

# Unit only
pytest tests/unit -v

# Integration only
pytest tests/integration -v

# Security only
pytest tests/security -v

# With coverage
pytest tests/unit --cov=app --cov-report=html

# Performance
pytest tests/performance -v

# Specific test
pytest tests/unit/test_auth_service.py::TestAuthService::test_login_valid_credentials -v

# Parallel (if pytest-xdist installed)
pytest -n auto
```

---

## Quality Gates

| Metric | Threshold | Enforcement |
|--------|-----------|-------------|
| Unit coverage | 85%+ | CI fails if below |
| Integration coverage | 70%+ | CI warns if below |
| Security tests | 100% pass | CI fails if any fail |
| Performance (feed) | < 2s p95 | CI fails if exceeds |
| Bandit findings | 0 High | CI fails on High |
| Type checking (mypy) | 0 errors | CI fails on errors |