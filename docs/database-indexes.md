# Voice2Gov Database Indexes

## Overview
This document defines all required MongoDB indexes for Voice2Gov collections. Indexes are designed based on query patterns from the SRS and API contract.

## Index Types
- **Single Field**: Simple ascending/descending
- **Compound**: Multiple fields for query + sort combinations
- **Unique**: Enforce uniqueness constraints
- **2dsphere**: Geospatial queries (location-based)
- **Partial**: Index only documents matching filter (sparse/conditional)
- **TTL**: Auto-expire documents (not used currently)

---

## Index Definitions by Collection

### users Collection

| Index | Fields | Type | Options | Purpose |
|-------|--------|------|---------|---------|
| `idx_users_email` | `email: 1` | Single | `unique: true, sparse: true` | Login, registration uniqueness |
| `idx_users_phone` | `phone: 1` | Single | `unique: true, sparse: true` | Login, registration uniqueness |
| `idx_users_organization_id` | `organization_id: 1` | Single | | Org-scoped queries |
| `idx_users_department_id` | `department_id: 1` | Single | | Department-scoped queries |
| `idx_users_role` | `role: 1` | Single | | Role-based queries |
| `idx_users_org_role` | `organization_id: 1, role: 1` | Compound | | Org users by role |

**Notes**: Email/phone sparse unique allows soft-deleted users (is_active: false) to not block new registrations.

---

### organizations Collection

| Index | Fields | Type | Options | Purpose |
|-------|--------|------|---------|---------|
| `idx_orgs_code` | `code: 1` | Single | `unique: true` | Lookup by code |
| `idx_orgs_name` | `name: 1` | Single | `unique: true` | Lookup by name |
| `idx_orgs_is_active` | `is_active: 1` | Single | | Active org filtering |

---

### departments Collection

| Index | Fields | Type | Options | Purpose |
|-------|--------|------|---------|---------|
| `idx_depts_org_id` | `organization_id: 1` | Single | | Org-scoped department listing |
| `idx_depts_org_code` | `organization_id: 1, code: 1` | Compound | `unique: true` | Unique code within org |
| `idx_depts_org_name` | `organization_id: 1, name: 1` | Compound | `unique: true` | Unique name within org |
| `idx_depts_org_active` | `organization_id: 1, is_active: 1` | Compound | | Active departments in org |

---

### categories Collection

| Index | Fields | Type | Options | Purpose |
|-------|--------|------|---------|---------|
| `idx_cats_org_name` | `organization_id: 1, name: 1` | Compound | `unique: true` | Category uniqueness per organization |
| `idx_cats_org_id` | `organization_id: 1` | Single | | Org-scoped category queries |
| `idx_cats_org_status` | `organization_id: 1, status: 1` | Compound | | Active categories in org |
| `idx_cats_default_dept` | `default_department_id: 1` | Single | | Routing lookups |
| `idx_cats_sort` | `sort_order: 1` | Single | | Display ordering |

**Notes**:
- Category names are unique within an organization (not globally)
- Categories are organization-scoped; `organization_id` is required
- `status` enum (`active`/`inactive`) replaces `is_active` boolean

---

### complaints Collection

| Index | Fields | Type | Options | Purpose |
|-------|--------|------|---------|---------|
| `idx_complaints_complaint_number` | `complaint_number: 1` | Single | `unique: true` | Lookup by complaint number |
| `idx_complaints_user_id` | `user_id: 1` | Single | | "My complaints" query |
| `idx_complaints_org_id` | `organization_id: 1` | Single | | Org-scoped complaints |
| `idx_complaints_dept_id` | `department_id: 1` | Single | | Dept-scoped complaints |
| `idx_complaints_status` | `status: 1` | Single | | Status filtering |
| `idx_complaints_category_id` | `category_id: 1` | Single | | Category filtering |
| `idx_complaints_created_at` | `created_at: -1` | Single | Descending | Recent complaints, pagination |
| `idx_complaints_priority` | `priority_score: -1` | Single | Descending | Priority feed sorting |
| `idx_complaints_location` | `location: "2dsphere"` | 2dsphere | | Nearby complaints, geo queries |
| `idx_complaints_org_status_created` | `organization_id: 1, status: 1, created_at: -1` | Compound | | Org dashboard: status + recent |
| `idx_complaints_dept_status_priority` | `department_id: 1, status: 1, priority_score: -1` | Compound | | Dept queue: status + priority |
| `idx_complaints_user_created` | `user_id: 1, created_at: -1` | Compound | | User complaint history |
| `idx_complaints_assigned_to` | `assigned_to: 1` | Single | | Staff assigned complaints |
| `idx_complaints_sla_deadline` | `sla_deadline: 1` | Single | `sparse: true` | SLA monitoring |
| `idx_complaints_visibility_status_created` | `visibility: 1, status: 1, created_at: -1` | Compound | | Public feed queries |

**Critical Indexes**:
1. `location` **2dsphere** - Required for "nearby" feed filter
2. `priority_score` descending - Required for "priority" feed sort
3. Compound org/dept + status + priority - Required for dashboard queues
4. `complaint_number` unique - Required for human-readable lookup

---

### complaint_images Collection

| Index | Fields | Type | Options | Purpose |
|-------|--------|------|---------|---------|
| `idx_images_complaint_id` | `complaint_id: 1` | Single | | All images for complaint |
| `idx_images_complaint_type` | `complaint_id: 1, image_type: 1` | Compound | | Images by type (evidence/progress) |
| `idx_images_uploaded_by` | `uploaded_by: 1` | Single | | User's uploaded images |
| `idx_images_created_at` | `created_at: -1` | Single | Descending | Recent uploads |

---

### complaint_likes Collection

| Index | Fields | Type | Options | Purpose |
|-------|--------|------|---------|---------|
| `idx_likes_complaint_user` | `complaint_id: 1, user_id: 1` | Compound | `unique: true` | **Prevent duplicate likes**, like status check |
| `idx_likes_user_id` | `user_id: 1` | Single | | User's liked complaints |
| `idx_likes_created_at` | `created_at: -1` | Single | Descending | Recent likes |

**Critical**: The compound unique index on `complaint_id + user_id` is the **primary mechanism** preventing duplicate likes at database level.

---

### complaint_updates Collection

| Index | Fields | Type | Options | Purpose |
|-------|--------|------|---------|---------|
| `idx_updates_complaint_id` | `complaint_id: 1` | Single | | All updates for complaint |
| `idx_updates_complaint_created` | `complaint_id: 1, created_at: -1` | Compound | | **Chronological updates for complaint** |
| `idx_updates_org_id` | `organization_id: 1` | Single | | Org-scoped updates |
| `idx_updates_dept_id` | `department_id: 1` | Single | | Dept-scoped updates |
| `idx_updates_updated_by` | `updated_by: 1` | Single | | Staff activity log |

**Critical**: Compound `complaint_id + created_at` descending for complaint timeline view.

---

### notifications Collection

| Index | Fields | Type | Options | Purpose |
|-------|--------|------|---------|---------|
| `idx_notifs_user_id` | `user_id: 1` | Single | | All notifications for user |
| `idx_notifs_user_unread` | `user_id: 1, is_read: 1` | Compound | | **Unread count, unread list** |
| `idx_notifs_user_created` | `user_id: 1, created_at: -1` | Compound | | Paginated notification history |
| `idx_notifs_complaint_id` | `complaint_id: 1` | Single | | Notifications for complaint |

**Critical**: Compound `user_id + is_read` for efficient unread count query.

---

### device_tokens Collection

| Index | Fields | Type | Options | Purpose |
|-------|--------|------|---------|---------|
| `idx_device_user_id` | `user_id: 1` | Single | | User's devices |
| `idx_device_token` | `device_token: 1` | Single | | Token lookup |
| `idx_device_user_active` | `user_id: 1, is_active: 1` | Compound | | Active tokens for user |
| `idx_device_user_token` | `user_id: 1, device_token: 1` | Compound | `unique: true` | Prevent duplicate registrations |

---

### audit_logs Collection

| Index | Fields | Type | Options | Purpose |
|-------|--------|------|---------|---------|
| `idx_audit_actor_id` | `actor_id: 1` | Single | | Actor activity log |
| `idx_audit_entity_type` | `entity_type: 1` | Single | | Filter by entity type |
| `idx_audit_entity_id` | `entity_id: 1` | Single | | Entity history |
| `idx_audit_action` | `action: 1` | Single | | Action type filtering |
| `idx_audit_created_at` | `created_at: -1` | Single | Descending | Recent audit logs |
| `idx_audit_entity_timeline` | `entity_type: 1, entity_id: 1, created_at: -1` | Compound | | **Complete entity audit trail** |

---

### admin_settings Collection

| Index | Fields | Type | Options | Purpose |
|-------|--------|------|---------|---------|
| `idx_settings_key` | `key: 1` | Single | `unique: true` | Setting lookup by key |
| `idx_settings_category` | `category: 1` | Single | | Category grouping |

---

## Index Creation Script

```python
# scripts/create_indexes.py
import asyncio
from pymongo.asynchronous import AsyncMongoClient
from app.db.collections import Collections

INDEXES = {
    Collections.USERS: [
        ([("email", 1)], {"unique": True, "sparse": True, "name": "idx_users_email"}),
        ([("phone", 1)], {"unique": True, "sparse": True, "name": "idx_users_phone"}),
        ([("organization_id", 1)], {"name": "idx_users_organization_id"}),
        ([("department_id", 1)], {"name": "idx_users_department_id"}),
        ([("role", 1)], {"name": "idx_users_role"}),
        ([("organization_id", 1), ("role", 1)], {"name": "idx_users_org_role"}),
    ],
    Collections.ORGANIZATIONS: [
        ([("code", 1)], {"unique": True, "name": "idx_orgs_code"}),
        ([("name", 1)], {"unique": True, "name": "idx_orgs_name"}),
        ([("is_active", 1)], {"name": "idx_orgs_is_active"}),
    ],
    Collections.DEPARTMENTS: [
        ([("organization_id", 1)], {"name": "idx_depts_org_id"}),
        ([("organization_id", 1), ("code", 1)], {"unique": True, "name": "idx_depts_org_code"}),
        ([("organization_id", 1), ("name", 1)], {"unique": True, "name": "idx_depts_org_name"}),
        ([("organization_id", 1), ("status", 1)], {"name": "idx_depts_org_status"}),
    ],
    Collections.CATEGORIES: [
        ([("organization_id", 1), ("name", 1)], {"unique": True, "name": "idx_cats_org_name"}),
        ([("organization_id", 1)], {"name": "idx_cats_org_id"}),
        ([("organization_id", 1), ("status", 1)], {"name": "idx_cats_org_status"}),
        ([("default_department_id", 1)], {"name": "idx_cats_default_dept"}),
        ([("sort_order", 1)], {"name": "idx_cats_sort"}),
    ],
    Collections.COMPLAINTS: [
        ([("user_id", 1)], {"name": "idx_complaints_user_id"}),
        ([("organization_id", 1)], {"name": "idx_complaints_org_id"}),
        ([("department_id", 1)], {"name": "idx_complaints_dept_id"}),
        ([("status", 1)], {"name": "idx_complaints_status"}),
        ([("category_id", 1)], {"name": "idx_complaints_category_id"}),
        ([("created_at", -1)], {"name": "idx_complaints_created_at"}),
        ([("priority_score", -1)], {"name": "idx_complaints_priority"}),
        ([("location", "2dsphere")], {"name": "idx_complaints_location"}),
        ([("organization_id", 1), ("status", 1), ("created_at", -1)], {"name": "idx_complaints_org_status_created"}),
        ([("department_id", 1), ("status", 1), ("priority_score", -1)], {"name": "idx_complaints_dept_status_priority"}),
        ([("user_id", 1), ("created_at", -1)], {"name": "idx_complaints_user_created"}),
        ([("assigned_to", 1)], {"name": "idx_complaints_assigned_to"}),
        ([("sla_deadline", 1)], {"sparse": True, "name": "idx_complaints_sla_deadline"}),
        ([("visibility", 1), ("status", 1), ("created_at", -1)], {"name": "idx_complaints_visibility_status_created"}),
    ],
    Collections.COMPLAINT_IMAGES: [
        ([("complaint_id", 1)], {"name": "idx_images_complaint_id"}),
        ([("complaint_id", 1), ("image_type", 1)], {"name": "idx_images_complaint_type"}),
        ([("uploaded_by", 1)], {"name": "idx_images_uploaded_by"}),
        ([("created_at", -1)], {"name": "idx_images_created_at"}),
    ],
    Collections.COMPLAINT_LIKES: [
        ([("complaint_id", 1), ("user_id", 1)], {"unique": True, "name": "idx_likes_complaint_user"}),
        ([("user_id", 1)], {"name": "idx_likes_user_id"}),
        ([("created_at", -1)], {"name": "idx_likes_created_at"}),
    ],
    Collections.COMPLAINT_UPDATES: [
        ([("complaint_id", 1)], {"name": "idx_updates_complaint_id"}),
        ([("complaint_id", 1), ("created_at", -1)], {"name": "idx_updates_complaint_created"}),
        ([("organization_id", 1)], {"name": "idx_updates_org_id"}),
        ([("department_id", 1)], {"name": "idx_updates_dept_id"}),
        ([("updated_by", 1)], {"name": "idx_updates_updated_by"}),
    ],
    Collections.NOTIFICATIONS: [
        ([("user_id", 1)], {"name": "idx_notifs_user_id"}),
        ([("user_id", 1), ("is_read", 1)], {"name": "idx_notifs_user_unread"}),
        ([("user_id", 1), ("created_at", -1)], {"name": "idx_notifs_user_created"}),
        ([("complaint_id", 1)], {"name": "idx_notifs_complaint_id"}),
    ],
    Collections.DEVICE_TOKENS: [
        ([("user_id", 1)], {"name": "idx_device_user_id"}),
        ([("device_token", 1)], {"name": "idx_device_token"}),
        ([("user_id", 1), ("is_active", 1)], {"name": "idx_device_user_active"}),
        ([("user_id", 1), ("device_token", 1)], {"unique": True, "name": "idx_device_user_token"}),
    ],
    Collections.AUDIT_LOGS: [
        ([("actor_id", 1)], {"name": "idx_audit_actor_id"}),
        ([("entity_type", 1)], {"name": "idx_audit_entity_type"}),
        ([("entity_id", 1)], {"name": "idx_audit_entity_id"}),
        ([("action", 1)], {"name": "idx_audit_action"}),
        ([("created_at", -1)], {"name": "idx_audit_created_at"}),
        ([("entity_type", 1), ("entity_id", 1), ("created_at", -1)], {"name": "idx_audit_entity_timeline"}),
    ],
    Collections.ADMIN_SETTINGS: [
        ([("key", 1)], {"unique": True, "name": "idx_settings_key"}),
        ([("category", 1)], {"name": "idx_settings_category"}),
    ],
}

async def create_all_indexes(db):
    for collection_name, indexes in INDEXES.items():
        collection = db[collection_name]
        for keys, options in indexes:
            try:
                await collection.create_index(keys, **options)
                print(f"Created index: {options['name']} on {collection_name}")
            except Exception as e:
                print(f"Index {options['name']} on {collection_name} exists or error: {e}")

if __name__ == "__main__":
    # Run with: python scripts/create_indexes.py
    pass
```

---

## Index Strategy Guidelines

### Do Not Create Indexes Arbitrarily
1. **Only index fields used in queries** - verified via query analysis
2. **Compound indexes for query + sort** - avoid in-memory sorts
3. **Unique indexes for business constraints** - not just "might be unique"
4. **2dsphere only for GeoJSON Point** - not for legacy coordinate pairs

### Index Maintenance
- Monitor index usage via `db.collection.aggregate([{$indexStats: {}}])`
- Drop unused indexes after 30 days
- Rebuild indexes after major data migrations
- Use `background: true` for production (default in MongoDB 4.2+)

### Performance Targets
| Query Pattern | Target | Index Strategy |
|---------------|--------|----------------|
| My complaints | < 100ms | `user_id + created_at` |
| Org dashboard | < 200ms | `org_id + status + created_at` |
| Dept queue | < 200ms | `dept_id + status + priority` |
| Nearby feed | < 500ms | `location` 2dsphere |
| Priority feed | < 300ms | `priority_score` desc |
| Unread count | < 50ms | `user_id + is_read` |
| Like check | < 20ms | `complaint_id + user_id` unique |

---

## Index Creation Order (Dependencies)
1. **Users** - Auth depends on email/phone unique
2. **Organizations** - Departments reference orgs
3. **Departments** - Categories reference departments
4. **Categories** - Complaints reference categories
5. **Complaints** - Core entity, most indexes
6. **Dependent collections** - Images, likes, updates, notifications
7. **Audit/Admin** - Independent, can be created anytime