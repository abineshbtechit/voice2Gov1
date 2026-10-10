# Voice2Gov Database Schema

## Overview
MongoDB collections for Voice2Gov civic complaint management platform. All collections use ObjectId references for relationships with application-level validation.

## Naming Conventions
- Collection names: plural, snake_case (e.g., `users`, `complaint_images`)
- Field names: snake_case
- Boolean fields: `is_` or `has_` prefix
- Timestamps: `created_at`, `updated_at` (ISO 8601 UTC)
- ObjectId references: `_id` suffix (e.g., `user_id`, `organization_id`)

---

## 1. users Collection

**Purpose**: Citizen, organization staff, organization admin, and system admin accounts.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | Primary key |
| `email` | String | Yes | Unique, lowercase, indexed |
| `phone` | String | Yes | Unique, E.164 format, indexed |
| `password_hash` | String | Yes | Bcrypt hash |
| `full_name` | String | Yes | Display name |
| `role` | String | Yes | Enum: `citizen`, `organization_staff`, `organization_admin`, `admin` |
| `organization_id` | ObjectId | Conditional | Required for org roles, ref: `organizations._id` |
| `department_id` | ObjectId | Conditional | Required for org_staff, ref: `departments._id` |
| `avatar_url` | String | No | Profile image reference (stored in users collection, not complaint_images) |
| `is_active` | Boolean | Yes | Default: true |
| `is_verified` | Boolean | Yes | Default: false (OTP verified) |
| `last_login_at` | DateTime | No | Track last activity |
| `failed_login_attempts` | Integer | Yes | Default: 0 |
| `locked_until` | DateTime | No | Account lockout timestamp |
| `created_at` | DateTime | Yes | Auto-set |
| `updated_at` | DateTime | Yes | Auto-updated |

**Enum Values (role)**: `citizen`, `organization_staff`, `organization_admin`, `admin`

**Uniqueness Constraints**:
- `email` (unique, sparse for soft-delete)
- `phone` (unique, sparse for soft-delete)

**Indexes**:
- `email` (unique, ascending)
- `phone` (unique, ascending)
- `organization_id` (ascending)
- `department_id` (ascending)
- `role` (ascending)
- Compound: `organization_id` + `role` (ascending)

**Validation Rules**:
- Email: RFC 5322 format, lowercase
- Phone: E.164 format (+<country><number>)
- Password hash: bcrypt cost factor 12
- Role must be valid enum
- `organization_id` required for non-citizen roles
- `department_id` required for `organization_staff`

---

## 2. organizations Collection

**Purpose**: Government/municipal organizations that handle complaints.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | Primary key |
| `name` | String | Yes | Organization name |
| `code` | String | Yes | Short code (e.g., "MCD", "DDA"), unique |
| `description` | String | No | Details about organization |
| `address` | String | No | Physical address |
| `contact_email` | String | No | Official contact |
| `contact_phone` | String | No | Official phone |
| `logo_url` | String | No | Logo image reference |
| `website` | String | No | Official website |
| `is_active` | Boolean | Yes | Default: true |
| `settings` | Object | No | Organization-specific config |
| `settings.priority_weights` | Object | No | Custom priority weights (Phase 2) |
| `settings.auto_assign` | Boolean | No | Default: false |
| `settings.sla_hours` | Integer | No | Default SLA in hours |
| `created_at` | DateTime | Yes | Auto-set |
| `updated_at` | DateTime | Yes | Auto-updated |

**Note**: `organization.default_department_id` is intentionally omitted. Routing uses `categories.default_department_id` which must belong to the same organization. No silent fallback to arbitrary department.

**Uniqueness Constraints**:
- `code` (unique, case-insensitive)
- `name` (unique)

**Indexes**:
- `code` (unique, ascending)
- `name` (ascending)
- `is_active` (ascending)

**Validation Rules**:
- Code: 2-10 alphanumeric chars, uppercase
- Name: 2-200 chars
- Settings: validated JSON schema

---

## 3. departments Collection

**Purpose**: Departments within organizations that handle specific complaint categories.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | Primary key |
| `organization_id` | ObjectId | Yes | Ref: `organizations._id` |
| `name` | String | Yes | Department name |
| `code` | String | Yes | Short code, unique within org |
| `description` | String | No | Department description |
| `contact_email` | String | No | Department contact |
| `contact_phone` | String | No | Department phone |
| `head_user_id` | ObjectId | No | Ref: `users._id` (organization_admin) |
| `is_active` | Boolean | Yes | Default: true |
| `created_at` | DateTime | Yes | Auto-set |
| `updated_at` | DateTime | Yes | Auto-updated |

**Uniqueness Constraints**:
- Compound: `organization_id` + `code` (unique)
- Compound: `organization_id` + `name` (unique)

**Indexes**:
- `organization_id` (ascending)
- Compound: `organization_id` + `code` (unique, ascending)
- Compound: `organization_id` + `is_active` (ascending)

**Validation Rules**:
- Code: 2-10 alphanumeric chars, uppercase
- Name: 2-200 chars
- `head_user_id` must belong to same organization with role `organization_admin`

---

## 4. categories Collection

**Purpose**: Complaint categories for routing and classification.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | Primary key |
| `organization_id` | ObjectId | Yes | Ref: `organizations._id` - categories belong to an organization |
| `name` | String | Yes | Category name (e.g., "Pothole", "Street Light") |
| `description` | String | No | Category description |
| `icon` | String | No | Icon identifier for UI |
| `color` | String | No | Hex color for UI |
| `default_department_id` | ObjectId | No | Ref: `departments._id` for auto-routing (must belong to same organization) |
| `severity_level` | Integer | Yes | 1-5 (1=Low, 5=Critical) |
| `priority_weight` | Float | No | Category-specific priority weight multiplier (default: 1.0) |
| `status` | String | Yes | Enum: `active`, `inactive` (replaces is_active) |
| `sort_order` | Integer | Yes | Default: 0 (display order) |
| `created_at` | DateTime | Yes | Auto-set |
| `updated_at` | DateTime | Yes | Auto-updated |

**Uniqueness Constraints**:
- Compound: `organization_id` + `name` (unique within organization)

**Indexes**:
- `organization_id` (ascending)
- Compound: `organization_id` + `name` (unique, ascending)
- `default_department_id` (ascending)
- `status` (ascending)
- `sort_order` (ascending)

**Validation Rules**:
- Name: 2-100 chars
- Severity: integer 1-5
- Priority weight: float 0.1-10.0
- Status must be valid enum
- `default_department_id` must reference active department in same organization
- `organization_id` required (categories are organization-scoped)

**Intentional SRS Deviations (Phase 1)**:
- **organization_id required** (SRS: optional) — Every category must belong to exactly one organization for deterministic tenant-aware routing.
- **default_department_id required for active categories** (SRS: optional) — Every routable category must have deterministic routing; missing config fails explicitly.
- **Uniqueness: organization_id + name** (SRS: global name uniqueness) — Categories are organization-scoped; different orgs may use same name.

---

## 5. complaints Collection

**Purpose**: Core complaint records submitted by citizens.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | Primary key |
| `complaint_number` | String | Yes | Human-readable complaint number (e.g., "CMP-2024-001234"), unique |
| `user_id` | ObjectId | Yes | Ref: `users._id` (citizen) |
| `organization_id` | ObjectId | Yes | Ref: `organizations._id` |
| `department_id` | ObjectId | Yes | Ref: `departments._id` |
| `category_id` | ObjectId | Yes | Ref: `categories._id` |
| `title` | String | Yes | Brief complaint title |
| `description` | String | Yes | Detailed description |
| `status` | String | Yes | Enum: `SUBMITTED`, `ONGOING`, `PROCESSING`, `COMPLETED`, `REJECTED`, `DUPLICATE`, `CLOSED` |
| `priority_score` | Float | Yes | Computed priority (0-100) |
| `severity_score` | Integer | Yes | 1-5 from category |
| `location` | GeoJSON Point | Yes | `{type: "Point", coordinates: [lng, lat]}` |
| `address` | String | No | Reverse-geocoded address |
| `assigned_to` | ObjectId | No | Ref: `users._id` (org_staff) |
| `assigned_at` | DateTime | No | Assignment timestamp |
| `completed_at` | DateTime | No | Completion timestamp |
| `rejected_at` | DateTime | No | Rejection timestamp |
| `rejection_reason` | String | No | Reason if rejected |
| `duplicate_of` | ObjectId | No | Ref: `complaints._id` if duplicate |
| `likes_count` | Integer | Yes | Default: 0 (denormalized from complaint_likes) |
| `community_engagement_score` | Integer | Yes | Default: 0 (normalized engagement for priority) |
| `age_score` | Float | Yes | Default: 0 (time-based) |
| `organization_priority_boost` | Float | Yes | Default: 0 (org config) |
| `sla_deadline` | DateTime | No | Calculated from org SLA |
| `visibility` | String | Yes | Enum: `public`, `organization`, `private` (replaces is_public) |
| `metadata` | Object | No | Flexible extra data |
| `created_at` | DateTime | Yes | Auto-set |
| `updated_at` | DateTime | Yes | Auto-updated |

**Note**: `likes_count` is denormalized for feed performance. `visibility` replaces `is_public` with three states. `complaint_number` is generated on creation (format: CMP-YYYY-NNNNNN).

**Enum Values (status)**: `SUBMITTED`, `ONGOING`, `PROCESSING`, `COMPLETED`, `REJECTED`, `DUPLICATE`, `CLOSED`

**Indexes**:
- `complaint_number` (unique, ascending)
- `user_id` (ascending)
- `organization_id` (ascending)
- `department_id` (ascending)
- `status` (ascending)
- `category_id` (ascending)
- `created_at` (descending)
- `priority_score` (descending)
- `location` (2dsphere)
- `visibility` (ascending)
- Compound: `organization_id` + `status` + `created_at` (ascending)
- Compound: `department_id` + `status` + `priority_score` (descending)
- Compound: `user_id` + `created_at` (descending)
- Compound: `organization_id` + `visibility` + `status` + `created_at` (ascending)

**Validation Rules**:
- Title: 5-200 chars
- Description: 10-5000 chars
- Status must be valid enum
- Location: valid GeoJSON Point, coordinates [longitude, latitude]
- Priority score: 0-100
- Severity: 1-5 (copied from category at creation)
- `assigned_to` must be org_staff in same department
- `duplicate_of` must reference existing complaint in same org
- `visibility` must be valid enum: `public`, `organization`, `private`
- `complaint_number` auto-generated, format: CMP-YYYY-NNNNNN
- `likes_count` >= 0

---

## 6. complaint_images Collection

**Purpose**: Image metadata for complaint evidence, progress, and completion. Profile images are stored in `users.avatar_url`, not in this collection.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | Primary key |
| `complaint_id` | ObjectId | Yes | Ref: `complaints._id` (required for evidence/progress/completion) |
| `image_type` | String | Yes | Enum: `evidence`, `progress`, `completion` |
| `storage_path` | String | Yes | Object storage key/path |
| `original_filename` | String | Yes | Sanitized original name |
| `mime_type` | String | Yes | Validated MIME type |
| `file_size` | Integer | Yes | Bytes |
| `width` | Integer | No | Image width |
| `height` | Integer | No | Image height |
| `checksum` | String | Yes | SHA-256 for integrity |
| `uploaded_by` | ObjectId | Yes | Ref: `users._id` |
| `is_deleted` | Boolean | Yes | Default: false (soft delete) |
| `created_at` | DateTime | Yes | Auto-set |

**Enum Values (image_type)**: `evidence`, `progress`, `completion`

**Indexes**:
- `complaint_id` (ascending)
- Compound: `complaint_id` + `image_type` (ascending)
- `uploaded_by` (ascending)
- `created_at` (descending)

**Validation Rules**:
- MIME types: `image/jpeg`, `image/png`, `image/webp`, `image/heic`
- Max file size: 10MB (evidence), 5MB (progress/completion)
- Filename: sanitized, no path traversal
- Checksum: SHA-256 hex string
- `uploaded_by` must have access to complaint
- `complaint_id` required (no profile images in this collection)

**Intentional SRS Deviations (Phase 1)**:
- **Canonical image_type values**: `evidence`, `progress`, `completion` (Database Design SRS v1.0 conceptually noted `complaint_evidence`, `progress_evidence`, `completion_evidence`). A single unified enum is used across database, storage keys, and API contracts.
- **storage_path vs storage_key**: Stored as `storage_path` containing the relative object storage key (e.g., `evidence/YYYY/MM/DD/{complaint_id}/{uuid}_{filename}`).
- **original_filename vs file_name**: Stored as `original_filename` containing the sanitized original client filename.
- **Dynamic Signed URLs vs file_url**: Expiring signed URLs are generated dynamically on read (`url`), rather than persisting static or leaking access URLs in `file_url`.
- **Integrity and Audit fields**: `checksum` (SHA-256) and `is_deleted` (soft-delete flag) added to support upload compensation, integrity checks, and soft deletion.
- **Caption deferred**: `caption` field from Database Design SRS is deferred to later UI integration phases; not stored or accepted in Phase 1.3.4.

---

## 7. complaint_likes Collection

**Purpose**: Community likes on complaints for priority calculation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | Primary key |
| `complaint_id` | ObjectId | Yes | Ref: `complaints._id` |
| `user_id` | ObjectId | Yes | Ref: `users._id` (citizen) |
| `created_at` | DateTime | Yes | Auto-set |

**Uniqueness Constraints**:
- Compound: `complaint_id` + `user_id` (unique) - prevents duplicate likes

**Indexes**:
- Compound: `complaint_id` + `user_id` (unique, ascending)
- `user_id` (ascending)
- `created_at` (descending)

**Validation Rules**:
- User must be `citizen` role
- Complaint must have `visibility: "public"`
- Complaint status not in `REJECTED`, `DUPLICATE`, `CLOSED`

---

## 8. complaint_updates Collection

**Purpose**: Status updates and progress notes on complaints by organization staff.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | Primary key |
| `complaint_id` | ObjectId | Yes | Ref: `complaints._id` |
| `organization_id` | ObjectId | Yes | Ref: `organizations._id` |
| `department_id` | ObjectId | Yes | Ref: `departments._id` |
| `updated_by` | ObjectId | Yes | Ref: `users._id` (org_staff/admin) |
| `update_type` | String | Yes | Enum: `status_change`, `progress_note`, `assignment`, `completion`, `rejection` |
| `previous_status` | String | No | Previous complaint status |
| `new_status` | String | No | New complaint status |
| `message` | String | Yes | Update description |
| `images` | Array<ObjectId> | No | Ref: `complaint_images._id` (progress/completion) |
| `is_public` | Boolean | Yes | Default: true (update visible to citizen; distinct from complaint.visibility) |
| `created_at` | DateTime | Yes | Auto-set |

**Enum Values (update_type)**: `status_change`, `progress_note`, `assignment`, `completion`, `rejection`

**Indexes**:
- `complaint_id` (ascending)
- Compound: `complaint_id` + `created_at` (descending)
- `organization_id` (ascending)
- `department_id` (ascending)
- `updated_by` (ascending)

**Validation Rules**:
- `updated_by` must belong to same organization/department
- Status values must be valid enums
- Images must reference valid complaint_images of type `progress` or `completion`
- Message: 1-2000 chars

---

## 9. notifications Collection

**Purpose**: User notifications for complaint updates, assignments, etc.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | Primary key |
| `user_id` | ObjectId | Yes | Ref: `users._id` |
| `complaint_id` | ObjectId | No | Ref: `complaints._id` (nullable for system notifications) |
| `type` | String | Yes | Enum: `status_update`, `assignment`, `completion`, `rejection`, `comment`, `like`, `system` |
| `title` | String | Yes | Notification title |
| `message` | String | Yes | Notification body |
| `is_read` | Boolean | Yes | Default: false |
| `read_at` | DateTime | No | Read timestamp |
| `metadata` | Object | No | Extra data (deep link, etc.) |
| `created_at` | DateTime | Yes | Auto-set |

**Enum Values (type)**: `status_update`, `assignment`, `completion`, `rejection`, `comment`, `like`, `system`

**Indexes**:
- `user_id` (ascending)
- Compound: `user_id` + `is_read` (ascending)
- Compound: `user_id` + `created_at` (descending)
- `complaint_id` (ascending)

**Validation Rules**:
- Title: 1-100 chars
- Message: 1-500 chars
- `user_id` must exist
- If `complaint_id` present, user must have access to complaint

---

## 10. device_tokens Collection

**Purpose**: Push notification device tokens for mobile devices.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | Primary key |
| `user_id` | ObjectId | Yes | Ref: `users._id` |
| `device_token` | String | Yes | FCM/APNs token |
| `platform` | String | Yes | Enum: `ios`, `android`, `web` |
| `device_id` | String | No | Unique device identifier |
| `app_version` | String | No | App version |
| `is_active` | Boolean | Yes | Default: true |
| `last_used_at` | DateTime | No | Last notification sent |
| `created_at` | DateTime | Yes | Auto-set |
| `updated_at` | DateTime | Yes | Auto-updated |

**Enum Values (platform)**: `ios`, `android`, `web`

**Uniqueness Constraints**:
- Compound: `user_id` + `device_token` (unique)

**Indexes**:
- `user_id` (ascending)
- `device_token` (ascending)
- `is_active` (ascending)
- Compound: `user_id` + `is_active` (ascending)

**Validation Rules**:
- Device token: non-empty string
- Platform: valid enum
- One active token per device per user

---

## 11. audit_logs Collection

**Purpose**: Immutable audit trail for administrative and organization actions.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | Primary key |
| `actor_id` | ObjectId | Yes | Ref: `users._id` |
| `actor_role` | String | Yes | Role at time of action |
| `action` | String | Yes | Action identifier (e.g., `user.suspend`, `complaint.assign`) |
| `entity_type` | String | Yes | Entity affected (e.g., `user`, `complaint`, `organization`) |
| `entity_id` | ObjectId | Yes | Ref to affected entity |
| `metadata` | Object | No | Before/after values, context |
| `ip_address` | String | No | Client IP |
| `user_agent` | String | No | Client user agent |
| `created_at` | DateTime | Yes | Auto-set (immutable) |

**Indexes**:
- `actor_id` (ascending)
- `entity_type` (ascending)
- `entity_id` (ascending)
- `action` (ascending)
- `created_at` (descending)
- Compound: `entity_type` + `entity_id` + `created_at` (descending)

**Validation Rules**:
- Action: predefined action constants
- Entity type: predefined entity constants
- Metadata: JSON serializable
- Immutable: no updates/deletes allowed

**Actions Requiring Audit Records**:
- User: create, suspend, activate, role_change, delete
- Organization: create, update, status_change, delete
- Department: create, update, delete, head_change
- Category: create, update, delete, default_department_change
- Complaint: assign, status_change, reject, close, priority_override
- Admin Settings: create, update, delete

---

## 12. admin_settings Collection

**Purpose**: System-wide configuration and priority weight configuration.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | Primary key |
| `key` | String | Yes | Setting key (unique) |
| `value` | Mixed | Yes | Setting value (JSON) |
| `description` | String | No | Human-readable description |
| `category` | String | Yes | Enum: `priority`, `general`, `notification`, `security`, `sla` |
| `is_public` | Boolean | Yes | Default: false (admin only) |
| `created_at` | DateTime | Yes | Auto-set |
| `updated_at` | DateTime | Yes | Auto-updated |
| `updated_by` | ObjectId | No | Ref: `users._id` (admin) |

**Enum Values (category)**: `priority`, `general`, `notification`, `security`, `sla`

**Uniqueness Constraints**:
- `key` (unique)

**Indexes**:
- `key` (unique, ascending)
- `category` (ascending)

**Predefined Keys**:
| Key | Category | Default Value | Description |
|-----|----------|---------------|-------------|
| `priority.weights.community_engagement` | priority | 0.30 | Weight for likes/engagement |
| `priority.weights.severity` | priority | 0.40 | Weight for severity level |
| `priority.weights.age` | priority | 0.20 | Weight for complaint age |
| `priority.weights.organization_boost` | priority | 0.10 | Weight for org priority boost |
| `priority.max_score` | priority | 100 | Maximum priority score |
| `general.max_file_size_mb` | general | 10 | Max upload size |
| `general.allowed_mime_types` | general | ["image/jpeg","image/png","image/webp","image/heic"] | Allowed image types |
| `notification.push_enabled` | notification | true | Enable push notifications |
| `security.jwt_access_token_minutes` | security | 15 | Access token expiry |
| `security.jwt_refresh_token_days` | security | 30 | Refresh token expiry |
| `security.max_login_attempts` | security | 5 | Account lockout threshold |
| `security.lockout_duration_minutes` | security | 15 | Lockout duration |
| `sla.default_hours` | sla | 72 | Default SLA hours |

---

## 13. token_blacklist Collection

**Purpose**: Server-side revocation list for refresh tokens (JWT rotation and reuse detection).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | ObjectId | Yes | Primary key |
| `token_hash` | String | Yes | SHA-256 hash of the refresh token (never store raw token) |
| `user_id` | ObjectId | Yes | Ref: `users._id` |
| `token_family_id` | String | Yes | UUID linking rotated tokens in the same family |
| `expires_at` | DateTime | Yes | Token expiry timestamp (for TTL index) |
| `revoked_at` | DateTime | No | Revocation timestamp (null if active) |
| `reason` | String | No | Revocation reason: `rotation`, `logout`, `password_change`, `suspend`, `reuse_detected` |
| `replaced_by` | ObjectId | No | Ref: `token_blacklist._id` (the newer token that replaced this one) |
| `created_at` | DateTime | Yes | Auto-set |

**Indexes**:
- `token_hash` (unique, ascending) - Fast lookup by token hash
- `user_id` (ascending) - Find all revoked tokens for a user
- `token_family_id` (ascending) - Find all tokens in a family for reuse detection
- `expires_at` (ascending) - **TTL index** (expireAfterSeconds: 0) - Auto-remove expired records
- Compound: `user_id` + `revoked_at` (ascending) - Active revoked tokens per user

**Token Family & Reuse Detection**:
- Each user login creates a new **token family** (UUID)
- On rotation: old refresh token hash added to blacklist with `reason: "rotation"`, new token issued with same `token_family_id`
- If a **revoked** token is presented again: `reason: "reuse_detected"`, entire token family revoked (all tokens in family marked revoked), user forced to re-authenticate
- Password change / admin suspend: revoke all families for user (`reason: "password_change"` or `"suspend"`)
- Logout: revoke current family (`reason: "logout"`)
- Raw refresh tokens are **never stored**; only SHA-256 hash persisted

**Validation Rules**:
- `token_hash` must be SHA-256 hex string (64 chars)
- `expires_at` must be in future at creation
- TTL index on `expires_at` auto-removes stale records
- `token_family_id` must be valid UUID

---

## Relationship Summary

```
users (citizen) ──────► complaints ◄────── users (org_staff)
       │                    │
       │                    ├──► complaint_images
       │                    ├──► complaint_likes ◄──── users (citizen)
       │                    ├──► complaint_updates ◄── users (org_staff)
       │                    └──► notifications ◄────── users (all)
       │
       ├──► device_tokens
       └──► audit_logs (actor)

organizations ◄──── departments ◄──── users (org_staff, org_admin)
     │                    │
     │                    └──► categories (default_department_id)
     │
     ├──► complaints
     ├──► complaint_updates
     └──► admin_settings (org-specific overrides)

categories ──────► complaints (routing via default_department_id)
```

---

## MongoDB Relationship Notes
- **No Foreign Keys**: MongoDB does not enforce referential integrity
- **Application-Level Validation**: All references validated in service layer
- **Cascade Behavior**: Defined per relationship (see service specs)
- **Soft Deletes**: `is_deleted`/`is_active` flags preferred over hard deletes
- **Orphan Cleanup**: Background jobs for orphaned references