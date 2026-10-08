# Voice2Gov Phase 0 Architecture Decisions

## Overview
This document records key architectural decisions made during Phase 0, with rationale and alternatives considered. Each decision is traceable to SRS requirements.

---

## Decision Log

### DEC-001: Backend Framework - FastAPI
**Status**: Accepted  
**Date**: 2024-01-15  
**Context**: Need async Python framework for high-concurrency I/O operations (MongoDB, file uploads, push notifications)

**Decision**: Use FastAPI with async/await throughout

**Rationale**:
- Native async support for PyMongo AsyncMongoClient
- Automatic OpenAPI schema generation
- Pydantic v2 integration for validation
- Performance comparable to Node.js/Go
- Strong typing support

**Alternatives Considered**:
- Flask: No native async, requires extensions
- Django: Heavy, async support limited
- Starlette: Lower-level, more boilerplate

**Consequences**:
- All database operations must be async
- Team needs async Python proficiency
- Middleware must be async-compatible

---

### DEC-002: Database - MongoDB with PyMongo AsyncMongoClient
**Status**: Accepted  
**Date**: 2024-01-15  
**Context**: SRS specifies MongoDB for flexible schema, geospatial queries, and document model

**Decision**: Use MongoDB with PyMongo AsyncMongoClient (not Motor)

**Rationale**:
- Native GeoJSON Point + 2dsphere index for location queries
- Flexible schema for complaint metadata evolution
- Document model maps naturally to complaint hierarchy
- Horizontal scaling via sharding (future)
- SRS requirement
- PyMongo 4.x AsyncMongoClient is the official async driver (Motor is legacy wrapper)

**Alternatives Considered**:
- PostgreSQL + PostGIS: Stronger consistency, but rigid schema
- Redis + MongoDB hybrid: Added complexity
- Motor (legacy async wrapper): Deprecated in favor of native PyMongo async

**Consequences**:
- No foreign key enforcement - application-level validation required
- Eventual consistency model
- Need careful index design for query patterns
- Import from `pymongo.asynchronous` package

---

### DEC-003: Authentication - JWT with Refresh Token Rotation (Multi-Platform)
**Status**: Accepted  
**Date**: 2024-01-15  
**Context**: Stateless auth required for horizontal scaling, secure token management for web and mobile

**Decision**: 
- Access tokens: 15-min expiry, RS256
- Refresh tokens: 30-day expiry, stored in platform-appropriate secure storage
  - **Web Portal**: HTTP-only Secure cookie (SameSite=Strict) + database hash for revocation
  - **React Native Mobile**: Secure Storage (iOS Keychain / Android Keystore) + database hash for revocation
- Rotation: New refresh token on each use, old revoked
- Revocation: Server-side blacklist in `token_blacklist` collection (MongoDB TTL)

**Rationale**:
- Short-lived access tokens limit exposure
- Refresh token rotation prevents replay attacks
- Platform-appropriate storage prevents XSS token theft (web) and extraction (mobile)
- RS256 allows key rotation without invalidating all tokens
- Single token format works for both platforms

**Alternatives Considered**:
- Session/cookie based: Requires sticky sessions or shared store
- JWT only (no refresh): Poor UX, frequent re-login
- Opaque tokens: Requires token introspection endpoint
- HTTP-only cookie only: Incompatible with React Native

**Consequences**:
- Need secure key management (KMS/HSM)
- Clock synchronization critical
- Blacklist uses MongoDB TTL collection (no Redis dependency in Phase 1)
- Client must implement platform-specific storage

---

### DEC-004: RBAC Model - Role + Organization Scoping
**Status**: Accepted  
**Date**: 2024-01-15  
**Context**: Multi-tenant isolation required - org users cannot access other orgs' data

**Decision**: 
- Four roles: citizen, organization_staff, organization_admin, admin
- Organization-scoped permissions enforced at repository layer
- Admin bypasses org scoping (superuser)

**Rationale**:
- Matches SRS role definitions
- Repository-level scoping ensures no bypass
- Simple to understand and audit

**Alternatives Considered**:
- ABAC (Attribute-Based): More flexible but complex
- Policy engine (OPA): Overkill for current requirements
- Resource-level ACLs: Too granular, hard to manage

**Consequences**:
- Every query must apply org filter
- Cross-org queries only for admin
- Testing must verify isolation thoroughly

---

### DEC-005: Complaint Status Machine - Explicit Transitions
**Status**: Accepted  
**Date**: 2024-01-15  
**Context**: SRS defines 7 statuses with specific lifecycle; arbitrary transitions must be prevented

**Decision**: 
- Define explicit transition matrix in code
- Validate every transition in service layer
- Require reason for terminal transitions (REJECTED, DUPLICATE)
- Audit log every transition
- Notification on every transition

**Rationale**:
- Prevents invalid states (e.g., SUBMITTED -> COMPLETED)
- Clear audit trail for accountability
- Matches government process requirements

**Alternatives Considered**:
- Free-form status field: High risk of data corruption
- Database enum only: No transition logic enforcement
- State machine library: Added dependency, same logic needed

**Consequences**:
- More code for transition validation
- Testing must cover all valid/invalid transitions
- Future status additions require matrix update

---

### DEC-006: Priority Engine - Configurable Weights
**Status**: Accepted  
**Date**: 2024-01-15  
**Context**: SRS requires priority combining engagement, severity, age, org boost

**Decision**:
- Formula: weighted sum of 4 components
- Weights stored in admin_settings (global defaults)
- Organization override via organizations.settings.priority_weights (future)
- Denormalized priority_score on complaint document
- Recalculation on: like/unlike, status change, scheduled job

**Rationale**:
- Transparent, explainable priority
- Configurable without code changes
- Denormalized score enables efficient sorting
- Components match SRS requirements

**Alternatives Considered**:
- ML-based priority: Not in SRS, requires training data
- Simple FIFO: Doesn't match SRS
- Fixed formula: No organizational customization

**Consequences**:
- Background job needed for age component updates
- Cache invalidation on weight changes
- Organization override adds complexity (deferred to Phase 2)

---

### DEC-007: File Storage - Pluggable Provider with Metadata in MongoDB
**Status**: Accepted  
**Date**: 2024-01-15  
**Context**: Images for evidence, progress, completion; large files shouldn't bloat MongoDB

**Decision**:
- Store metadata in complaint_images collection
- Pluggable storage provider (Local/S3/GridFS/MinIO)
- Signed URLs for secure access
- Validation: MIME, magic bytes, size, filename sanitization

**Rationale**:
- MongoDB stores references, not blobs (performance)
- Provider abstraction allows dev (local) vs prod (S3)
- Signed URLs enforce authorization
- Multi-layer validation prevents malicious uploads

**Alternatives Considered**:
- GridFS only: Simpler but less scalable
- Base64 in MongoDB: Terrible performance
- Direct S3 upload: Requires presigned POST, more client complexity

**Consequences**:
- Need storage provider implementation per environment
- Cleanup jobs for orphaned files
- CDN integration for production

---

### DEC-008: Notification Architecture - Service Abstraction
**Status**: Accepted  
**Date**: 2024-01-15  
**Context**: In-app + push notifications; provider not yet selected

**Decision**:
- In-app notifications in MongoDB (notifications collection)
- Push notification provider abstraction (Mock/FCM/APNS)
- Fire-and-forget with retry for push
- Device tokens in device_tokens collection

**Rationale**:
- In-app reliable, queryable, no external dependency
- Provider abstraction defers FCM/APNS decision
- Mock provider enables full testing without credentials
- Device token management standard pattern

**Alternatives Considered**:
- WebSocket for real-time: Added infrastructure complexity
- Third-party (OneSignal, Firebase): Vendor lock-in
- Email only: Not real-time enough

**Consequences**:
- Push delivery best-effort only
- Need retry queue for production (future: Redis/RabbitMQ)
- Device token cleanup for uninstalled apps

---

### DEC-009: API Versioning - URL Path /api/v1/
**Status**: Accepted  
**Date**: 2024-01-15  
**Context**: SRS requires /api/v1/ prefix; need versioning strategy

**Decision**: 
- All endpoints under /api/v1/
- Breaking changes → /api/v2/
- Deprecation header for sunset
- No header-based versioning

**Rationale**:
- Simple, explicit, cacheable
- Matches SRS requirement
- Easy to route in reverse proxy

**Alternatives Considered**:
- Header-based: Harder to debug, cache issues
- Query param: Not RESTful
- Subdomain: DNS complexity

**Consequences**:
- URL changes on major version
- Need migration path for clients

---

### DEC-010: Error Handling - Standard Envelope
**Status**: Accepted  
**Date**: 2024-01-15  
**Context**: SRS defines success/error response format

**Decision**:
- Success: {success: true, message, data}
- Error: {success: false, message, error_code, errors[]}
- HTTP status codes map to error categories
- Consistent error_code constants

**Rationale**:
- Matches SRS specification
- Frontend can handle uniformly
- error_code enables programmatic handling
- errors[] supports field-level validation

**Alternatives Considered**:
- RFC 7807 Problem Details: More complex
- HTTP status only: Insufficient detail
- Custom per-endpoint: Inconsistent

**Consequences**:
- All exceptions must map to envelope
- Middleware for automatic conversion

---

### DEC-011: Audit Logging - Immutable Collection
**Status**: Accepted  
**Date**: 2024-01-15  
**Context**: SRS requires audit trail for admin/org actions

**Decision**:
- Dedicated audit_logs collection
- Immutable: no UPDATE/DELETE operations
- Structured fields: actor, action, entity, metadata, IP, UA
- Hash chaining for integrity (future)

**Rationale**:
- Regulatory compliance (government)
- Tamper-evident log
- Queryable for investigations

**Alternatives Considered**:
- Log files (ELK): Harder to correlate with entities
- Database triggers: Business logic in DB
- External service (AWS CloudTrail): Vendor lock-in

**Consequences**:
- Storage growth - need retention policy
- Write performance impact (async write)
- Must never fail silently

---

### DEC-012: Geospatial - GeoJSON Point with 2dsphere
**Status**: Accepted  
**Date**: 2024-01-15  
**Context**: SRS requires nearby complaints, location-based feed

**Decision**:
- Location stored as GeoJSON Point: {type: "Point", coordinates: [longitude, latitude]}
- 2dsphere index on complaints.location
- $nearSphere queries for nearby
- Reverse geocoding via external API (future)

**Rationale**:
- MongoDB native geospatial support
- Correct coordinate order (lng, lat)
- 2dsphere handles spherical geometry
- Standard format for mapping libraries

**Alternatives Considered**:
- Separate lat/lng fields: No native index, manual distance calc
- Geohash: Approximate, more complex
- PostGIS: Would require PostgreSQL

**Consequences**:
- Must validate coordinate order everywhere
- 2dsphere index required
- Coordinate validation in schema

---

### DEC-013: Like System - Compound Unique Index
**Status**: Accepted  
**Date**: 2024-01-15  
**Context**: Prevent duplicate likes, efficient like status check

**Decision**:
- complaint_likes collection with compound unique index on (complaint_id, user_id)
- Like count via aggregation or denormalized counter
- Like status check via findOne

**Rationale**:
- Database-enforced uniqueness (atomic)
- Simple query for "has user liked"
- No race conditions on concurrent likes

**Alternatives Considered**:
- Array in complaint document: Document size limits, $addToSet race conditions
- Application-level check: Race conditions
- Counter only: Can't check user like status

**Consequences**:
- Extra collection but simple queries
- Denormalized count needs sync (or compute on read)

---

### DEC-014: Organization Routing - Category Default Department
**Status**: Accepted  
**Date**: 2024-01-15  
**Context**: SRS permits category-based routing to organization/department

**Decision**:
- Routing flow: category → organization → department
- categories.default_department_id for initial routing (required)
- **NO fallback to organization.default_department_id** (removed)
- **NO silent routing** - raise RoutingConfigurationError if category.default_department_id is missing or references department in different organization
- categories.organization_id required (categories are organization-scoped)
- default_department_id must belong to same organization as category
- No AI/ML routing in Phase 1
- No duplicate detection AI in Phase 1

**Rationale**:
- Matches SRS "initial category-based routing"
- Explicit routing prevents misrouting
- Organization boundary enforcement prevents cross-org data leaks
- AI features explicitly deferred

**Alternatives Considered**:
- Round-robin assignment: Ignores category expertise
- Manual triage queue: Slower, not automated
- ML routing: Requires training data, not in SRS
- Silent fallback: Risk of misrouting, removed

**Consequences**:
- Categories MUST have default_department_id configured
- Categories MUST belong to an organization (organization_id required)
- Org admin must set up routing correctly per organization
- Future AI can replace without API changes

---

### DEC-015: Testing - Testcontainers for Integration
**Status**: Accepted  
**Date**: 2024-01-15  
**Context**: Need reliable integration tests with real MongoDB

**Decision**:
- Unit tests: Mock repositories
- Integration tests: Testcontainers MongoDB
- Security tests: Dedicated test suite
- Performance: Locust for load testing

**Rationale**:
- Testcontainers provides real MongoDB per test run
- No shared test database conflicts
- CI-friendly (Docker available)
- Matches production behavior

**Alternatives Considered**:
- Shared test DB: Flaky, conflicts between tests
- Mocking MongoDB: Doesn't test queries/indexes
- In-memory MongoDB (mongomock): Incomplete feature support

**Consequences**:
- Integration tests slower (container startup)
- Need Docker in CI
- Test data setup/teardown per test

---

### DEC-016: Configuration - Pydantic Settings + Admin Overrides
**Status**: Accepted  
**Date**: 2024-01-15  
**Context**: Need type-safe config with environment overrides and runtime admin settings

**Decision**:
- Base config: pydantic-settings from .env
- Runtime settings: admin_settings collection
- Organization overrides: organizations.settings (future)
- Secrets: Environment variables / KMS

**Rationale**:
- Type validation on startup
- Admin can tune without deploy
- Clear separation: infra vs business config
- Secure secret handling

**Alternatives Considered**:
- JSON/YAML config files: No validation, harder to override
- Consul/Etcd: Added infrastructure
- Environment only: No runtime changes

**Consequences**:
- Settings cache with TTL
- Cache invalidation on admin update
- Migration needed for new settings

---

### DEC-017: Soft Deletes - is_deleted/is_active Flags
**Status**: Accepted  
**Date**: 2024-01-15  
**Context**: Data retention requirements, referential integrity

**Decision**:
- Use is_deleted (collections) or is_active (users/orgs) flags
- Hard deletes only via admin purge (audited)
- Queries filter by default
- Orphan cleanup via background jobs

**Rationale**:
- Preserves audit trail and references
- Meets government retention requirements
- Allows "undo" for accidental deletes
- Simpler than archive tables

**Alternatives Considered**:
- Hard delete: Loses history, breaks references
- Archive collections: More complex queries
- Temporal tables: Not native to MongoDB

**Consequences**:
- All queries must include is_deleted/is_active filter
- Indexes need to include these fields
- Storage growth over time

---

### DEC-018: Rate Limiting - Sliding Window per User/IP
**Status**: Accepted  
**Date**: 2024-01-15  
**Context**: Protect auth endpoints, prevent abuse

**Decision**:
- Sliding window algorithm
- Keyed by user_id (auth) or IP (anonymous)
- Limits per endpoint group (auth stricter)
- **Phase 1**: In-memory implementation (single-instance)
- **Production**: Redis-backed for multi-instance horizontal scaling

**Rationale**:
- Sliding window smoother than fixed window
- Per-user fairer than per-IP
- Endpoint-specific limits match risk
- Phase 1 single-instance doesn't need Redis
- Redis added only when horizontal scaling required

**Alternatives Considered**:
- Token bucket: More complex implementation
- Fixed window: Burst at boundaries
- No rate limiting: High abuse risk

**Consequences**:
- Phase 1: In-memory with single instance (no Redis dependency)
- Production: Redis required for multi-instance
- Headers for client retry logic
- Admin endpoints higher limits

---

## Unresolved Decisions (Deferred to Phase 1+)

| ID | Decision | Deferred Because |
|----|----------|------------------|
| UND-001 | Organization priority weight overrides | SRS doesn't require Phase 1 |
| UND-002 | Push notification provider (FCM vs APNS vs unified) | Can use mock in Phase 1 |
| UND-003 | Message queue for background jobs (Celery/RQ/Redis) | Phase 1 uses async tasks |
| UND-004 | Full-text search (Elasticsearch/Meilisearch) | MongoDB text search sufficient initially |
| UND-005 | WebSocket for real-time updates | Not in SRS |
| UND-006 | Multi-language support (i18n) | Not in SRS |
| UND-007 | Advanced analytics/OLAP | Phase 2+ |
| UND-008 | Mobile app certificate pinning | Client-side concern |
| UND-009 | Virus scanning integration (ClamAV) | Can add later |
| UND-010 | Hash chaining for audit log integrity | Phase 2 compliance |

---

## Decision Template (For Future Use)

```markdown
### DEC-XXX: [Title]
**Status**: Proposed | Accepted | Rejected | Superseded  
**Date**: YYYY-MM-DD  
**Context**: [What problem are we solving?]  
**Decision**: [What did we decide?]  
**Rationale**: [Why this choice?]  
**Alternatives Considered**: [What else? Why not?]  
**Consequences**: [Trade-offs, follow-up work]  
**Related**: [SRS req, other decisions]
```