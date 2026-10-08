# Voice2Gov Backend Architecture

## Overview
This document defines the recommended backend architecture for Voice2Gov, a citizen-centric civic complaint management platform built with Python FastAPI and MongoDB.

## Architectural Principles
- **Clean Architecture**: Business logic independent from HTTP route handlers
- **Separation of Concerns**: Clear layer boundaries with well-defined responsibilities
- **Testability**: Each layer testable in isolation
- **Extensibility**: Support future expansion without major restructuring
- **Security by Design**: RBAC, organization isolation, and audit logging built-in

---

## Application Layers

### 1. API Layer (`app/api/`)
**Responsibility**: HTTP request/response handling, routing, serialization
- FastAPI route handlers (endpoints)
- Request/response DTOs using Pydantic models
- Input validation at boundary
- HTTP status code mapping
- API versioning (`/api/v1/`)

### 2. Schema/Validation Layer (`app/schemas/`)
**Responsibility**: Data contracts, serialization, validation rules
- Pydantic models for request/response
- Enum definitions
- Custom validators
- OpenAPI schema generation

### 3. Service Layer (`app/services/`)
**Responsibility**: Business logic, orchestration, domain rules
- Complaint lifecycle management
- Priority calculation engine
- Routing logic
- Notification triggers
- Audit logging orchestration
- Cross-cutting concerns (transactions, retries)

### 4. Repository/Data Access Layer (`app/repositories/`)
**Responsibility**: Database operations abstraction
- CRUD operations per collection
- Query builders
- Aggregation pipelines
- Index management
- Transaction support (where applicable)

### 5. Database Layer (`app/db/`)
**Responsibility**: MongoDB connection, configuration, migrations
- Async MongoDB client (PyMongo AsyncMongoClient)
- Connection pooling
- Collection initialization
- Schema validation rules
- Index creation

### 6. Security Layer (`app/security/`)
**Responsibility**: Authentication, authorization, token management
- JWT token creation/validation
- Password hashing (bcrypt)
- Role-based access control
- Organization-scoped authorization
- Rate limiting
- Token blacklist/revocation

### 7. Middleware Layer (`app/middleware/`)
**Responsibility**: Cross-cutting HTTP concerns
- Request logging
- Error handling
- CORS
- Rate limiting
- Request ID correlation
- Security headers

### 8. Utility Layer (`app/utils/`)
**Responsibility**: Shared helpers, constants, common functions
- Date/time utilities
- File validation helpers
- GeoJSON helpers
- Pagination utilities
- Error code definitions

### 9. Testing Structure (`tests/`)
**Responsibility**: Test organization by type
- Unit tests (services, repositories, utilities)
- Integration tests (API endpoints, database)
- Security tests
- Performance tests

---

## Folder Structure

```
voice2gov-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application factory
│   ├── config.py               # Settings management (pydantic-settings)
│   ├── db/
│   │   ├── __init__.py
│   │   ├── client.py           # PyMongo AsyncMongoClient
│   │   ├── collections.py      # Collection names/constants
│   │   ├── indexes.py          # Index definitions
│   │   └── migrations/         # Schema migrations (future)
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── error_handler.py
│   │   ├── logging_middleware.py
│   │   ├── rate_limiter.py
│   │   └── correlation_id.py
│   ├── security/
│   │   ├── __init__.py
│   │   ├── jwt.py              # Token creation/validation
│   │   ├── password.py         # Bcrypt hashing
│   │   ├── rbac.py             # Role/permission checks
│   │   ├── dependencies.py     # FastAPI auth dependencies
│   │   └── token_blacklist.py  # Refresh token revocation
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── base.py             # Base models, enums
│   │   ├── auth.py             # Auth request/response
│   │   ├── user.py             # User models
│   │   ├── organization.py     # Organization models
│   │   ├── department.py       # Department models
│   │   ├── category.py         # Category models
│   │   ├── complaint.py        # Complaint models
│   │   ├── notification.py     # Notification models
│   │   ├── feed.py             # Feed query/response
│   │   ├── admin.py            # Admin models
│   │   └── common.py           # Pagination, error responses
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── base.py             # Base repository class
│   │   ├── user_repo.py
│   │   ├── organization_repo.py
│   │   ├── department_repo.py
│   │   ├── category_repo.py
│   │   ├── complaint_repo.py
│   │   ├── complaint_image_repo.py
│   │   ├── complaint_like_repo.py
│   │   ├── complaint_update_repo.py
│   │   ├── notification_repo.py
│   │   ├── device_token_repo.py
│   │   ├── audit_log_repo.py
│   │   └── admin_settings_repo.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── organization_service.py
│   │   ├── department_service.py
│   │   ├── category_service.py
│   │   ├── complaint_service.py
│   │   ├── routing_service.py
│   │   ├── priority_service.py
│   │   ├── notification_service.py
│   │   ├── feed_service.py
│   │   ├── image_service.py
│   │   ├── audit_service.py
│   │   └── admin_service.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── router.py       # Main v1 router
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── complaints.py
│   │   │   ├── feed.py
│   │   │   ├── organizations.py
│   │   │   ├── departments.py
│   │   │   ├── categories.py
│   │   │   ├── notifications.py
│   │   │   ├── admin.py
│   │   │   └── search.py
│   │   └── deps.py             # Shared API dependencies
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── datetime.py
│   │   ├── file_validation.py
│   │   ├── geojson.py
│   │   ├── pagination.py
│   │   ├── error_codes.py
│   │   └── constants.py
│   └── exceptions/
│       ├── __init__.py
│       ├── base.py
│       ├── auth.py
│       ├── validation.py
│       ├── not_found.py
│       ├── authorization.py
│       └── business_logic.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── unit/
│   │   ├── test_auth_service.py
│   │   ├── test_complaint_service.py
│   │   ├── test_priority_service.py
│   │   ├── test_routing_service.py
│   │   └── test_repositories.py
│   ├── integration/
│   │   ├── test_auth_api.py
│   │   ├── test_complaint_api.py
│   │   ├── test_feed_api.py
│   │   ├── test_organization_api.py
│   │   └── test_admin_api.py
│   ├── security/
│   │   ├── test_rbac.py
│   │   ├── test_token_security.py
│   │   ├── test_file_upload.py
│   │   └── test_injection.py
│   └── performance/
│       └── test_feed_performance.py
├── docs/                       # This documentation
├── scripts/
│   ├── create_indexes.py
│   └── seed_data.py
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
└── docker-compose.yml          # Optional: local MongoDB
```

---

## Dependency Flow
```
API Layer → Schemas (validation) → Services (business logic) → Repositories (data access) → Database
                ↑                      ↑
                └──── Security Layer ←──┘
                ↑
                └──── Middleware
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Async FastAPI + PyMongo AsyncMongoClient | High concurrency for I/O-bound operations |
| Repository Pattern | Testability, swap storage backend if needed |
| Service Layer | Single source of truth for business rules |
| Pydantic v2 | Performance, strict validation, OpenAPI |
| JWT + Refresh Tokens | Stateless auth, secure token rotation |
| Organization-scoped RBAC | Multi-tenant isolation requirement |
| 2dsphere Index | Geospatial queries for nearby complaints |
| Compound Unique Indexes | Prevent duplicate likes, enforce constraints |

---

## Future Expansion Points
- **Webhook System**: Event-driven notifications
- **Message Queue**: Background job processing (Celery/RQ)
- **Caching Layer**: Redis for feed/priority caching
- **Search Engine**: Elasticsearch for full-text search
- **File Storage**: S3/MinIO abstraction already designed
- **Analytics**: Separate read models for dashboards