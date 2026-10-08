# Voice2Gov Traceability Matrix

## Overview
This matrix maps SRS requirements to architecture decisions, planned implementation locations, and planned tests.

---

## Legend
- **SRS Ref**: Requirement identifier from SRS documents
- **Architecture Decision**: Key design choice addressing the requirement
- **Implementation Location**: File/module where implemented
- **Test Coverage**: Test file/type verifying the requirement

---

## Authentication & Authorization

| SRS Ref | Requirement | Architecture Decision | Implementation Location | Test Coverage |
|---------|-------------|----------------------|------------------------|---------------|
| AUTH-01 | Citizen registration with email/phone | JWT + OTP verification | `app/services/auth_service.py` | `tests/unit/test_auth_service.py`, `tests/integration/test_auth_api.py` |
| AUTH-02 | Login with email or phone | Identifier-based lookup | `app/services/auth_service.py:login()` | `tests/unit/test_auth_service.py::test_login_*` |
| AUTH-03 | JWT access + refresh tokens | RS256, 15min/30day, rotation | `app/security/jwt.py`, `app/security/token_blacklist.py` | `tests/unit/test_jwt.py`, `tests/security/test_token_security.py` |
| AUTH-04 | Password hashing | bcrypt cost 12 | `app/security/password.py` | `tests/unit/test_password.py` |
| AUTH-05 | Account lockout after failed attempts | 5 attempts, 15min lockout | `app/services/auth_service.py:track_failed_login()` | `tests/unit/test_auth_service.py::test_lockout` |
| AUTH-06 | Password reset via OTP | 6-digit OTP, 10min TTL | `app/services/auth_service.py:forgot_password/reset_password` | `tests/integration/test_auth_api.py::test_password_reset` |
| AUTH-07 | Role-based access control | 4 roles, org scoping | `app/security/rbac.py`, `app/security/dependencies.py` | `tests/security/test_rbac.py` |
| AUTH-08 | Organization tenant isolation | Repository-level org filtering | `app/repositories/*.py` (base query scoping) | `tests/security/test_org_isolation.py` |
| AUTH-09 | Resource ownership checks | Service-layer validation | `app/services/complaint_service.py` | `tests/unit/test_complaint_service.py::test_ownership` |
| AUTH-10 | Admin user management | Suspend/activate endpoints | `app/api/v1/admin.py` | `tests/integration/test_admin_api.py` |

---

## Complaint Management

| SRS Ref | Requirement | Architecture Decision | Implementation Location | Test Coverage |
|---------|-------------|----------------------|------------------------|---------------|
| CMP-01 | Create complaint with image + location (generates complaint_number) | POST /complaints, multipart upload | `app/api/v1/complaints.py`, `app/services/image_service.py` | `tests/integration/test_complaint_api.py::test_create` |
| CMP-02 | Get complaint by ID | GET /complaints/{id} | `app/api/v1/complaints.py:get_complaint()` | `tests/integration/test_complaint_api.py::test_get` |
| CMP-03 | Get my complaints | GET /complaints/my | `app/api/v1/complaints.py:get_my_complaints()` | `tests/integration/test_complaint_api.py::test_my` |
| CMP-04 | Update complaint (citizen, SUBMITTED only) | PUT /complaints/{id} | `app/services/complaint_service.py:update_by_citizen()` | `tests/unit/test_complaint_service.py::test_update_*` |
| CMP-05 | Delete complaint (citizen, SUBMITTED only) | DELETE /complaints/{id} | `app/services/complaint_service.py:delete_by_citizen()` | `tests/unit/test_complaint_service.py::test_delete_*` |
| CMP-06 | Upload complaint images | POST /complaints/{id}/images | `app/services/image_service.py:upload_complaint_image()` | `tests/integration/test_complaint_api.py::test_upload_images` |
| CMP-07 | Category-based routing (category → org → dept) | categories.default_department_id (org-scoped, required) | `app/services/routing_service.py:route_complaint()` | `tests/unit/test_routing_service.py` |
| CMP-08 | Department assignment | PATCH /complaints/{id}/assign | `app/services/complaint_service.py:assign()` | `tests/integration/test_complaint_api.py::test_assign` |
| CMP-09 | Status transitions | Explicit state machine | `app/services/complaint_service.py:change_status()`, `app/schemas/complaint.py:StateMachine` | `tests/unit/test_complaint_service.py::test_state_machine` |
| CMP-10 | Complaint updates (progress) | POST/GET /complaints/{id}/updates | `app/services/complaint_service.py:add_update/get_updates()` | `tests/integration/test_complaint_api.py::test_updates` |
| CMP-11 | Complete complaint | PATCH /complaints/{id}/complete | `app/services/complaint_service.py:complete()` | `tests/unit/test_complaint_service.py::test_complete` |
| CMP-12 | Priority score calculation | Weighted formula: raw → normalize/cap → weight → sum | `app/services/priority_service.py:calculate_priority()` | `tests/unit/test_priority_service.py` |
| CMP-13 | Priority breakdown endpoint | GET /complaints/{id}/priority | `app/api/v1/complaints.py:get_priority()` | `tests/integration/test_complaint_api.py::test_priority` |
| CMP-14 | Complaint fields per SRS | complaint_number, likes_count, visibility | `app/schemas/complaint.py` | `tests/unit/test_complaint_schema.py` |

---

## Community Feed

| SRS Ref | Requirement | Architecture Decision | Implementation Location | Test Coverage |
|---------|-------------|----------------------|------------------------|---------------|
| FEED-01 | Public complaint feed | GET /feed with filters | `app/api/v1/feed.py`, `app/services/feed_service.py` | `tests/integration/test_feed_api.py` |
| FEED-02 | Pagination | page, page_size params | `app/utils/pagination.py` | `tests/unit/test_pagination.py`, `tests/integration/test_feed_api.py::test_pagination` |
| FEED-03 | Sort: recent, popular, priority, nearby | sort param with different orderings | `app/services/feed_service.py:get_feed()` | `tests/integration/test_feed_api.py::test_sort_*` |
| FEED-04 | Filter by status, category, org | Query parameters | `app/services/feed_service.py:build_query()` | `tests/integration/test_feed_api.py::test_filter_*` |
| FEED-05 | Like complaint | POST /complaints/{id}/like | `app/services/feed_service.py:like()` | `tests/integration/test_feed_api.py::test_like` |
| FEED-06 | Unlike complaint | DELETE /complaints/{id}/like | `app/services/feed_service.py:unlike()` | `tests/integration/test_feed_api.py::test_unlike` |
| FEED-07 | Like status check | GET /complaints/{id}/like-status | `app/services/feed_service.py:get_like_status()` | `tests/integration/test_feed_api.py::test_like_status` |
| FEED-08 | Prevent duplicate likes | Compound unique index (complaint_id, user_id) | `app/db/indexes.py`, `app/repositories/complaint_like_repo.py` | `tests/security/test_duplicate_like.py` |
| FEED-09 | Feed performance < 2s | Indexed queries, aggregation | `app/db/indexes.py`, `app/services/feed_service.py` | `tests/performance/test_feed_performance.py` |

---

## Organizations & Departments

| SRS Ref | Requirement | Architecture Decision | Implementation Location | Test Coverage |
|---------|-------------|----------------------|------------------------|---------------|
| ORG-01 | List organizations (admin) | GET /organizations | `app/api/v1/organizations.py` | `tests/integration/test_organization_api.py` |
| ORG-02 | Create organization (admin) | POST /organizations | `app/services/organization_service.py:create()` | `tests/integration/test_organization_api.py::test_create` |
| ORG-03 | Update organization | PUT /organizations/{id} | `app/services/organization_service.py:update()` | `tests/integration/test_organization_api.py::test_update` |
| ORG-04 | Organization status toggle | PATCH /organizations/{id}/status | `app/services/organization_service.py:toggle_status()` | `tests/integration/test_organization_api.py::test_status` |
| ORG-05 | Org complaint dashboard | GET /organizations/me/complaints | `app/api/v1/organizations.py:get_my_complaints()` | `tests/integration/test_organization_api.py::test_my_complaints` |
| ORG-06 | Org priority queue | GET /organizations/me/complaints/priority | `app/api/v1/organizations.py:get_priority_queue()` | `tests/integration/test_organization_api.py::test_priority_queue` |
| ORG-07 | Department CRUD | GET/POST/PUT/DELETE /departments | `app/api/v1/departments.py`, `app/services/department_service.py` | `tests/integration/test_organization_api.py::test_departments` |
| ORG-08 | Org-scoped department access | Repository org filtering | `app/repositories/department_repo.py` | `tests/security/test_org_isolation.py::test_departments` |

---

## Categories

| SRS Ref | Requirement | Architecture Decision | Implementation Location | Test Coverage |
|---------|-------------|----------------------|------------------------|---------------|
| CAT-01 | List active categories | GET /categories | `app/api/v1/categories.py` | `tests/integration/test_category_api.py` |
| CAT-02 | Admin category management | POST/PUT/DELETE /admin/categories | `app/api/v1/categories.py` (admin), `app/services/category_service.py` | `tests/integration/test_admin_api.py::test_categories` |
| CAT-03 | Category fields per SRS | name, description, icon, color, default_department_id, severity_level, organization_id, priority_weight, status | `app/schemas/category.py` | `tests/unit/test_category_schema.py` |
| CAT-04 | Default department for routing | categories.default_department_id | `app/services/routing_service.py` | `tests/unit/test_routing_service.py` |

---

## Notifications

| SRS Ref | Requirement | Architecture Decision | Implementation Location | Test Coverage |
|---------|-------------|----------------------|------------------------|---------------|
| NOTIF-01 | In-app notifications | notifications collection | `app/repositories/notification_repo.py` | `tests/unit/test_notification_repo.py` |
| NOTIF-02 | Notification types | status_update, assignment, completion, rejection, duplicate, comment, like, system | `app/services/notification_service.py` | `tests/unit/test_notification_service.py` |
| NOTIF-03 | List notifications | GET /notifications | `app/api/v1/notifications.py` | `tests/integration/test_notification_api.py` |
| NOTIF-04 | Unread count | GET /notifications/unread-count | `app/services/notification_service.py:get_unread_count()` | `tests/integration/test_notification_api.py::test_unread_count` |
| NOTIF-05 | Mark read / read all | PATCH /notifications/{id}/read, PATCH /notifications/read-all | `app/services/notification_service.py:mark_read/mark_all_read()` | `tests/integration/test_notification_api.py::test_mark_read` |
| NOTIF-06 | Device token registration | POST /notifications/devices | `app/api/v1/notifications.py:register_device()` | `tests/integration/test_notification_api.py::test_register_device` |
| NOTIF-07 | Push notification abstraction | Provider interface (Mock/FCM/APNS) | `app/services/notification_service.py:NotificationProvider` | `tests/unit/test_notification_service.py::test_push_mock` |
| NOTIF-08 | Notification triggers | Auto on status change, assignment, completion | `app/services/complaint_service.py` (calls notification_service) | `tests/integration/test_complaint_api.py::test_notifications` |

---

## Search & Location

| SRS Ref | Requirement | Architecture Decision | Implementation Location | Test Coverage |
|---------|-------------|----------------------|------------------------|---------------|
| LOC-01 | Complaint location as GeoJSON Point | {type: "Point", coordinates: [lng, lat]} | `app/schemas/complaint.py:GeoJSONPoint` | `tests/unit/test_geojson.py` |
| LOC-02 | 2dsphere index on location | complaints.location 2dsphere | `app/db/indexes.py` | `tests/unit/test_indexes.py` |
| LOC-03 | Nearby complaints feed | $nearSphere in feed query | `app/services/feed_service.py:get_nearby()` | `tests/integration/test_feed_api.py::test_nearby` |
| LOC-04 | Reverse geocoding | GET /location/reverse | `app/api/v1/search.py:reverse_geocode()` | `tests/integration/test_search_api.py` |
| LOC-05 | Search complaints | GET /search | `app/api/v1/search.py`, `app/services/search_service.py` | `tests/integration/test_search_api.py` |

---

## Admin & Audit

| SRS Ref | Requirement | Architecture Decision | Implementation Location | Test Coverage |
|---------|-------------|----------------------|------------------------|---------------|
| ADM-01 | Admin dashboard stats | GET /admin/dashboard | `app/api/v1/admin.py:dashboard()`, `app/services/admin_service.py` | `tests/integration/test_admin_api.py::test_dashboard` |
| ADM-02 | User management | GET/PATCH /admin/users | `app/api/v1/admin.py`, `app/services/admin_service.py` | `tests/integration/test_admin_api.py::test_users` |
| ADM-03 | Audit logging | Immutable audit_logs collection | `app/services/audit_service.py`, `app/repositories/audit_log_repo.py` | `tests/unit/test_audit_service.py`, `tests/security/test_audit.py` |
| ADM-04 | Audit events per SRS | All admin/org actions logged | `app/services/audit_service.py:AUDIT_EVENTS` | `tests/unit/test_audit_service.py::test_events` |
| ADM-05 | System settings | GET/PUT /admin/settings | `app/api/v1/admin.py`, `app/repositories/admin_settings_repo.py` | `tests/integration/test_admin_api.py::test_settings` |

---

## File Storage

| SRS Ref | Requirement | Architecture Decision | Implementation Location | Test Coverage |
|---------|-------------|----------------------|------------------------|---------------|
| FILE-01 | Image types: evidence, progress, completion | image_type enum (profile in users.avatar_url) | `app/schemas/complaint_image.py` | `tests/unit/test_image_schema.py` |
| FILE-02 | MIME validation | Allowed types per image_type | `app/utils/file_validation.py` | `tests/unit/test_file_validator.py` |
| FILE-03 | File size limits | 10MB evidence, 5MB progress/completion | `app/utils/file_validation.py` | `tests/unit/test_file_validator.py::test_size` |
| FILE-04 | Filename sanitization | Basename, alphanumeric + ._- | `app/utils/file_validation.py:sanitize_filename()` | `tests/unit/test_file_validator.py::test_sanitize` |
| FILE-05 | Magic bytes validation | Verify file signature | `app/utils/file_validation.py:validate_magic_bytes()` | `tests/security/test_file_upload.py::test_magic_bytes` |
| FILE-06 | Storage abstraction | Provider interface (Local/S3/GridFS) | `app/services/image_service.py:StorageProvider` | `tests/unit/test_image_service.py::test_provider` |
| FILE-07 | Signed URLs for access | generate_presigned_url() | `app/services/image_service.py:get_image_url()` | `tests/integration/test_complaint_api.py::test_image_url` |
| FILE-08 | Authorization on image access | Service-layer permission check | `app/services/image_service.py:_verify_image_access()` | `tests/security/test_file_upload.py::test_auth` |

---

## Security

| SRS Ref | Requirement | Architecture Decision | Implementation Location | Test Coverage |
|---------|-------------|----------------------|------------------------|---------------|
| SEC-01 | Password storage | bcrypt cost 12 | `app/security/password.py` | `tests/unit/test_password.py` |
| SEC-02 | JWT security | RS256, short expiry, rotation | `app/security/jwt.py` | `tests/security/test_token_security.py` |
| SEC-03 | RBAC enforcement | Middleware + dependencies + repo scoping | `app/security/rbac.py`, `app/security/dependencies.py` | `tests/security/test_rbac.py` |
| SEC-04 | Organization isolation | Repository query scoping | `app/repositories/base.py:apply_org_scope()` | `tests/security/test_org_isolation.py` |
| SEC-05 | Input validation | Pydantic models on all endpoints | `app/schemas/*.py` | `tests/unit/test_*_schema.py` |
| SEC-06 | File upload validation | MIME + magic bytes + size + sanitization | `app/utils/file_validation.py` | `tests/security/test_file_upload.py` |
| SEC-07 | Rate limiting | Sliding window per endpoint group | `app/middleware/rate_limiter.py` | `tests/security/test_rate_limiting.py` |
| SEC-08 | Public feed privacy | No PII in feed responses | `app/services/feed_service.py:serialize_feed_item()` | `tests/security/test_feed_privacy.py` |
| SEC-09 | Audit logging | All sensitive actions | `app/services/audit_service.py` | `tests/security/test_audit.py` |
| SEC-10 | CORS policy | Restricted origins | `app/main.py:CORS_CONFIG` | `tests/security/test_cors.py` |
| SEC-11 | Security headers | CSP, HSTS, X-Frame-Options, etc. | `app/middleware/security_headers.py` | `tests/security/test_headers.py` |
| SEC-12 | NoSQL injection prevention | Pydantic validation, no raw queries | `app/schemas/*.py`, `app/repositories/*.py` | `tests/security/test_injection.py` |

---

## Performance

| SRS Ref | Requirement | Architecture Decision | Implementation Location | Test Coverage |
|---------|-------------|----------------------|------------------------|---------------|
| PERF-01 | API response < 500ms | Async FastAPI, indexed queries | `app/db/indexes.py`, async throughout | `tests/performance/test_api_performance.py` |
| PERF-02 | Feed load < 2s | Aggregation pipeline, compound indexes | `app/services/feed_service.py`, `app/db/indexes.py` | `tests/performance/test_feed_performance.py` |
| PERF-03 | Pagination | Cursor/offset pagination | `app/utils/pagination.py` | `tests/unit/test_pagination.py` |
| PERF-04 | Indexed queries | All query patterns indexed | `app/db/indexes.py` | `tests/unit/test_indexes.py` |
| PERF-05 | Aggregation pipelines | Feed, priority, analytics | `app/services/feed_service.py`, `app/services/priority_service.py` | `tests/unit/test_aggregations.py` |
| PERF-06 | Async operations | PyMongo AsyncMongoClient, async/await throughout | All services/repositories | N/A (architectural) |
| PERF-07 | Image/notification async | Fire-and-forget with retry | `app/services/image_service.py`, `app/services/notification_service.py` | `tests/unit/test_async_handling.py` |
| PERF-08 | Retry strategy | Exponential backoff for external calls | `app/utils/retry.py` | `tests/unit/test_retry.py` |

---

## Database Schema Coverage

| Collection | SRS Coverage | Schema Doc | Indexes Doc | Repository | Service |
|------------|--------------|------------|-------------|------------|---------|
| users | AUTH-01, AUTH-07, ORG-05 | `database-schema.md#1` | `database-indexes.md#users` | `user_repo.py` | `user_service.py`, `auth_service.py` |
| organizations | ORG-01 to ORG-06 | `database-schema.md#2` | `database-indexes.md#organizations` | `organization_repo.py` | `organization_service.py` |
| departments | ORG-07, ORG-08 | `database-schema.md#3` | `database-indexes.md#departments` | `department_repo.py` | `department_service.py` |
| categories | CAT-01 to CAT-04 | `database-schema.md#4` | `database-indexes.md#categories` | `category_repo.py` | `category_service.py`, `routing_service.py` |
| complaints | CMP-01 to CMP-13 | `database-schema.md#5` | `database-indexes.md#complaints` | `complaint_repo.py` | `complaint_service.py`, `routing_service.py`, `priority_service.py` |
| complaint_images | FILE-01 to FILE-08 | `database-schema.md#6` | `database-indexes.md#complaint_images` | `complaint_image_repo.py` | `image_service.py` |
| complaint_likes | FEED-05 to FEED-08 | `database-schema.md#7` | `database-indexes.md#complaint_likes` | `complaint_like_repo.py` | `feed_service.py` |
| complaint_updates | CMP-10 | `database-schema.md#8` | `database-indexes.md#complaint_updates` | `complaint_update_repo.py` | `complaint_service.py` |
| notifications | NOTIF-01 to NOTIF-08 | `database-schema.md#9` | `database-indexes.md#notifications` | `notification_repo.py` | `notification_service.py` |
| device_tokens | NOTIF-06, NOTIF-07 | `database-schema.md#10` | `database-indexes.md#device_tokens` | `device_token_repo.py` | `notification_service.py` |
| audit_logs | ADM-03, ADM-04 | `database-schema.md#11` | `database-indexes.md#audit_logs` | `audit_log_repo.py` | `audit_service.py` |
| admin_settings | ADM-05, PRIORITY config | `database-schema.md#12` | `database-indexes.md#admin_settings` | `admin_settings_repo.py` | `priority_service.py`, `admin_service.py` |

---

## API Endpoint Coverage

| Endpoint Group | Endpoints | API Contract Doc | Auth Doc | Test File |
|----------------|-----------|------------------|----------|-----------|
| Auth | 8 endpoints | `api-contract.md#authentication` | `authentication-rbac.md` | `test_auth_api.py` |
| Users | 5 endpoints | `api-contract.md#users` | `authentication-rbac.md` | `test_auth_api.py` |
| Complaints | 12 endpoints | `api-contract.md#complaints` | `authentication-rbac.md` | `test_complaint_api.py` |
| Feed | 5 endpoints | `api-contract.md#feed` | `authentication-rbac.md` | `test_feed_api.py` |
| Organizations | 7 endpoints | `api-contract.md#organizations` | `authentication-rbac.md` | `test_organization_api.py` |
| Departments | 5 endpoints | `api-contract.md#departments` | `authentication-rbac.md` | `test_organization_api.py` |
| Categories | 4 endpoints | `api-contract.md#categories` | `authentication-rbac.md` | `test_admin_api.py` |
| Notifications | 5 endpoints | `api-contract.md#notifications` | `authentication-rbac.md` | `test_notification_api.py` |
| Search/Location | 2 endpoints | `api-contract.md#search` | `authentication-rbac.md` | `test_search_api.py` |
| Admin | 8 endpoints | `api-contract.md#admin` | `authentication-rbac.md` | `test_admin_api.py` |

---

## Test Coverage Summary

| Test Type | Files | Requirements Covered |
|-----------|-------|---------------------|
| Unit | 15+ files | All service logic, validators, utilities |
| Integration | 8 files | All API endpoints, DB operations |
| Security | 7 files | RBAC, tokens, upload, injection, isolation, rate limit, audit |
| Performance | 3 files | Feed, priority, concurrent load |

---

## Gap Analysis

| Requirement | Status | Gap | Mitigation |
|-------------|--------|-----|------------|
| Voice processing | Not in scope | SRS mentions "Voice2Gov" but no voice reqs | Document as future |
| AI routing | Deferred | SRS says "permits initial category-based" only | DEC-014 documents deferral (no silent fallback) |
| Duplicate detection AI | Deferred | Not in current SRS | Document as future |
| Org priority overrides | Deferred | Not required Phase 1 | UND-001 |
| Push provider selection | Deferred | Mock provider for Phase 1 | UND-002 |
| Message queue | Deferred | Async tasks sufficient Phase 1 | UND-003 |
| Full-text search | Deferred | MongoDB text search initially | UND-004 |
| WebSocket real-time | Not in SRS | Not required | UND-005 |
| i18n | Not in SRS | Single language Phase 1 | UND-006 |
| MongoDB Driver | **Corrected** | Was Motor, now PyMongo AsyncMongoClient | DEC-002 updated |
| Authentication | **Corrected** | Was HTTP-only cookie only, now multi-platform | DEC-003 updated |
| Complaint Routing | **Corrected** | Was silent fallback, now explicit with error | DEC-014 updated |
| Database Schema | **Corrected** | Aligned with Database Design SRS fields | database-schema.md updated |
| Profile Images | **Corrected** | Moved from complaint_images to users.avatar_url | database-schema.md updated |
| Priority Calculation | **Corrected** | Explicit pipeline: raw → normalize → weight → sum | priority-engine.md updated |
| Rate Limiting | **Corrected** | Phase 1 in-memory, Production Redis | DEC-018 updated |

---

## Verification Checklist

Before Phase 1 implementation begins, verify:

- [ ] All 12 collections defined with fields, indexes, relationships
- [ ] All 10 API groups documented with request/response contracts
- [ ] State machine covers all 7 statuses with valid transitions
- [ ] Priority formula documented with configurable weights
- [ ] RBAC matrix covers all 4 roles x all resources
- [ ] Organization isolation enforced at repository layer
- [ ] File upload validation pipeline complete
- [ ] Notification provider abstraction defined
- [ ] Audit events list complete
- [ ] Test structure defined with quality gates
- [ ] Security headers, CORS, rate limiting configured
- [ ] Traceability matrix maps all SRS requirements
- [ ] Unresolved decisions documented with deferral rationale