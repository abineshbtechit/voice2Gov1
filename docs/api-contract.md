# Voice2Gov API Contract

## Overview
RESTful API for Voice2Gov civic complaint management platform. All endpoints under `/api/v1/`.

## Base URL
```
Production:  https://api.voice2gov.example.com/api/v1/
Development: http://localhost:8000/api/v1/
```

---

## Standard Response Envelope

### Success Response
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {}
}
```

### Error Response
```json
{
  "success": false,
  "message": "Human-readable error description",
  "error_code": "ERROR_CODE_CONSTANT",
  "errors": [
    {
      "field": "field_name",
      "message": "Field-specific error",
      "code": "VALIDATION_ERROR"
    }
  ]
}
```

### Paginated Response
```json
{
  "success": true,
  "message": "Results retrieved",
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 100,
      "total_pages": 5,
      "has_next": true,
      "has_prev": false
    }
  }
}
```

---

## HTTP Status Codes

| Code | Usage |
|------|-------|
| 200 | Success (GET, PUT, PATCH) |
| 201 | Created (POST) |
| 204 | No Content (DELETE) |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (invalid/expired token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not Found |
| 409 | Conflict (duplicate, state conflict) |
| 422 | Unprocessable Entity (semantic validation) |
| 429 | Too Many Requests (rate limited) |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

---

## Error Code Strategy

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Request body validation failed |
| `INVALID_CREDENTIALS` | 401 | Wrong email/phone or password |
| `TOKEN_EXPIRED` | 401 | Access token expired |
| `TOKEN_INVALID` | 401 | Malformed or tampered token |
| `TOKEN_REVOKED` | 401 | Refresh token revoked/blacklisted |
| `ACCOUNT_LOCKED` | 403 | Too many failed attempts |
| `ACCOUNT_INACTIVE` | 403 | User suspended/deactivated |
| `EMAIL_EXISTS` | 409 | Email already registered |
| `PHONE_EXISTS` | 409 | Phone already registered |
| `FORBIDDEN` | 403 | Insufficient role/permissions |
| `ORG_ISOLATION_VIOLATION` | 403 | Cross-org access attempt |
| `RESOURCE_NOT_FOUND` | 404 | Entity does not exist |
| `COMPLAINT_NOT_FOUND` | 404 | Complaint does not exist |
| `INVALID_STATUS_TRANSITION` | 422 | Status change not allowed |
| `DUPLICATE_LIKE` | 409 | User already liked complaint |
| `FILE_TOO_LARGE` | 400 | Upload exceeds size limit |
| `INVALID_FILE_TYPE` | 400 | MIME type not allowed |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |

---

## API Groups

### Authentication (`/auth`)
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/auth/register` | Register new citizen | Public |
| POST | `/auth/login` | Login, return tokens | Public |
| POST | `/auth/logout` | Revoke refresh token | Bearer |
| POST | `/auth/refresh` | Refresh access token | Refresh Token |
| POST | `/auth/forgot-password` | Request password reset | Public |
| POST | `/auth/reset-password` | Reset password with token | Public |
| POST | `/auth/verify-otp` | Verify OTP for phone/email | Public |
| GET | `/auth/me` | Get current user profile | Bearer |

### Users (`/users`)
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/users/me` | Current user profile | Bearer |
| PUT | `/users/me` | Update profile | Bearer |
| PATCH | `/users/me/password` | Change password | Bearer |
| POST | `/users/me/device-tokens` | Register device token | Bearer |
| DELETE | `/users/me/device-tokens/{token}` | Remove device token | Bearer |

### Complaints (`/complaints`)
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/complaints` | Create complaint | Bearer (citizen) |
| GET | `/complaints` | List complaints (org/dept scoped) | Bearer (org) |
| GET | `/complaints/my` | Current user's complaints | Bearer (citizen) |
| GET | `/complaints/{id}` | Get complaint details | Bearer |
| PUT | `/complaints/{id}` | Update complaint (citizen, before assignment) | Bearer (citizen) |
| DELETE | `/complaints/{id}` | Delete complaint (citizen, only SUBMITTED) | Bearer (citizen) |
| POST | `/complaints/{id}/images` | Upload complaint images | Bearer |
| GET | `/complaints/{id}/images` | List complaint images | Bearer |
| DELETE | `/complaints/{id}/images/{image_id}` | Soft-delete complaint image (uploader only) | Bearer |
| GET | `/complaints/{id}/priority` | Get priority breakdown | Bearer |
| POST | `/complaints/{id}/updates` | Add update (org staff) | Bearer (org) |
| GET | `/complaints/{id}/updates` | Get complaint updates | Bearer |
| PATCH | `/complaints/{id}/status` | Change status (org staff) | Bearer (org) |
| PATCH | `/complaints/{id}/complete` | Mark complete (org staff) | Bearer (org) |
| PATCH | `/complaints/{id}/assign` | Assign to staff (org admin) | Bearer (org_admin) |

### Feed (`/feed`)
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/feed` | Community feed with filters | Bearer (optional) |
| POST | `/complaints/{id}/like` | Like a complaint | Bearer (citizen) |
| DELETE | `/complaints/{id}/like` | Unlike a complaint | Bearer (citizen) |
| GET | `/complaints/{id}/like-status` | Check like status | Bearer (citizen) |
| GET | `/complaints/{id}/likes` | Get like count/list | Bearer (optional) |

### Organizations (`/organizations`)
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/organizations` | List organizations | Bearer (admin) |
| GET | `/organizations/{id}` | Get organization | Bearer |
| POST | `/organizations` | Create organization | Bearer (admin) |
| PUT | `/organizations/{id}` | Update organization | Bearer (admin) |
| PATCH | `/organizations/{id}/status` | Activate/deactivate | Bearer (admin) |
| GET | `/organizations/me/complaints` | My org's complaints | Bearer (org) |
| GET | `/organizations/me/complaints/priority` | Priority queue | Bearer (org) |

### Departments (`/departments`)
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/departments` | List departments (org-scoped) | Bearer (org) |
| GET | `/departments/{id}` | Get department | Bearer (org) |
| POST | `/departments` | Create department | Bearer (org_admin) |
| PUT | `/departments/{id}` | Update department | Bearer (org_admin) |
| DELETE | `/departments/{id}` | Delete department | Bearer (org_admin) |

### Categories (`/categories`)
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/categories` | List active categories | Bearer (optional) |
| POST | `/admin/categories` | Create category | Bearer (admin) |
| PUT | `/admin/categories/{id}` | Update category | Bearer (admin) |
| DELETE | `/admin/categories/{id}` | Delete category | Bearer (admin) |

### Notifications (`/notifications`)
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/notifications` | List notifications | Bearer |
| GET | `/notifications/unread-count` | Get unread count | Bearer |
| PATCH | `/notifications/{id}/read` | Mark as read | Bearer |
| PATCH | `/notifications/read-all` | Mark all as read | Bearer |
| POST | `/notifications/devices` | Register device token | Bearer |

### Search & Location (`/search`, `/location`)
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/search` | Search complaints | Bearer (optional) |
| GET | `/location/reverse` | Reverse geocode | Bearer (optional) |

### Admin (`/admin`)
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/admin/dashboard` | System dashboard stats | Bearer (admin) |
| GET | `/admin/users` | List all users | Bearer (admin) |
| GET | `/admin/users/{id}` | Get user details | Bearer (admin) |
| PATCH | `/admin/users/{id}/suspend` | Suspend user | Bearer (admin) |
| PATCH | `/admin/users/{id}/activate` | Activate user | Bearer (admin) |
| GET | `/admin/audit-logs` | Audit logs | Bearer (admin) |
| GET | `/admin/settings` | Get all settings | Bearer (admin) |
| PUT | `/admin/settings/{key}` | Update setting | Bearer (admin) |

---

## Request/Response Contracts

### Authentication

#### POST /auth/register
**Request**:
```json
{
  "email": "citizen@example.com",
  "phone": "+15551234567",
  "password": "SecurePass123!",
  "full_name": "John Doe"
}
```

**Response** (201):
```json
{
  "success": true,
  "message": "Registration successful. Please verify your phone/email.",
  "data": {
    "user_id": "507f1f77bcf86cd799439011",
    "requires_verification": true
  }
}
```

#### POST /auth/login
**Request**:
```json
{
  "identifier": "citizen@example.com",  // email or phone
  "password": "SecurePass123!",
  "device_token": "fcm_token_optional"  // for push notifications
}
```

**Response** (200):
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 900,
    "user": {
      "id": "507f1f77bcf86cd799439011",
      "email": "citizen@example.com",
      "full_name": "John Doe",
      "role": "citizen",
      "organization_id": null,
      "department_id": null,
      "is_verified": true
    }
  }
}
```

#### POST /auth/refresh
**Request**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response** (200):
```json
{
  "success": true,
  "message": "Token refreshed",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 900
  }
}
```

#### GET /auth/me
**Response** (200):
```json
{
  "success": true,
  "message": "User profile retrieved",
  "data": {
    "id": "507f1f77bcf86cd799439011",
    "email": "citizen@example.com",
    "phone": "+919876543210",
    "full_name": "John Doe",
    "role": "citizen",
    "status": "active",
    "is_verified": true
  }
}
```

#### POST /auth/forgot-password
**Request**:
```json
{
  "identifier": "citizen@example.com"
}
```

**Response** (200):
```json
{
  "message": "If an account exists with the provided information, a verification code has been sent.",
  "cooldown_seconds": 60
}
```

#### POST /auth/verify-otp
**Request**:
```json
{
  "identifier": "citizen@example.com",
  "otp": "123456"
}
```

**Response** (200):
```json
{
  "reset_token": "AbC123XyZ...",
  "expires_in": 900,
  "message": "Verification successful. Use the reset token to complete password update."
}
```

#### POST /auth/reset-password
**Request**:
```json
{
  "reset_token": "AbC123XyZ...",
  "new_password": "NewSecurePassword123!"
}
```

**Response** (200):
```json
{
  "message": "Password has been reset successfully. You may now log in."
}
```
  "message": "Profile retrieved",
  "data": {
    "id": "507f1f77bcf86cd799439011",
    "email": "citizen@example.com",
    "phone": "+15551234567",
    "full_name": "John Doe",
    "role": "citizen",
    "organization_id": null,
    "department_id": null,
    "avatar_url": null,
    "is_active": true,
    "is_verified": true,
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

---

### Complaints

#### POST /complaints
**Request**:
```json
{
  "title": "Large pothole on Main Street",
  "description": "Deep pothole causing vehicle damage near intersection of Main St and 1st Ave",
  "category_id": "507f1f77bcf86cd799439012",
  "location": {
    "type": "Point",
    "coordinates": [-73.9857, 40.7484]
  },
  "address": "Main St & 1st Ave, New York, NY"
}
```

**Response** (201):
```json
{
  "success": true,
  "message": "Complaint submitted successfully",
  "data": {
    "id": "507f1f77bcf86cd799439013",
    "title": "Large pothole on Main Street",
    "description": "Deep pothole causing vehicle damage near intersection of Main St and 1st Ave",
    "status": "SUBMITTED",
    "priority_score": 45.5,
    "category": {
      "id": "507f1f77bcf86cd799439012",
      "name": "Pothole",
      "severity_level": 3
    },
    "department": {
      "id": "507f1f77bcf86cd799439014",
      "name": "Road Maintenance"
    },
    "location": {
      "type": "Point",
      "coordinates": [-73.9857, 40.7484]
    },
    "address": "Main St & 1st Ave, New York, NY",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

#### GET /complaints/my
**Query Parameters**:
- `page` (default: 1)
- `page_size` (default: 20, max: 100)
- `status` (optional filter)

**Response** (200):
```json
{
  "success": true,
  "message": "Complaints retrieved",
  "data": {
    "items": [
      {
        "id": "507f1f77bcf86cd799439013",
        "title": "Large pothole on Main Street",
        "status": "ONGOING",
        "priority_score": 45.5,
        "category": {"id": "...", "name": "Pothole"},
        "department": {"id": "...", "name": "Road Maintenance"},
        "assigned_to": {"id": "...", "name": "Jane Smith"},
        "created_at": "2024-01-15T10:30:00Z",
        "updated_at": "2024-01-16T09:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 5,
      "total_pages": 1,
      "has_next": false,
      "has_prev": false
    }
  }
}
```

#### GET /complaints/{id}
**Response** (200):
```json
{
  "success": true,
  "message": "Complaint retrieved",
  "data": {
    "id": "507f1f77bcf86cd799439013",
    "title": "Large pothole on Main Street",
    "description": "Deep pothole causing vehicle damage...",
    "status": "ONGOING",
    "priority_score": 45.5,
    "severity_score": 3,
    "community_engagement_score": 12,
    "age_score": 15.2,
    "organization_priority_boost": 0,
    "user": {"id": "...", "name": "John Doe"},
    "category": {"id": "...", "name": "Pothole", "severity_level": 3},
    "department": {"id": "...", "name": "Road Maintenance"},
    "assigned_to": {"id": "...", "name": "Jane Smith"},
    "location": {"type": "Point", "coordinates": [-73.9857, 40.7484]},
    "address": "Main St & 1st Ave, New York, NY",
    "images": [
      {"id": "...", "image_type": "evidence", "url": "https://storage/...", "created_at": "..."}
    ],
    "visibility": "public",
    "sla_deadline": "2024-01-18T10:30:00Z",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-16T09:00:00Z"
  }
}
```

#### PATCH /complaints/{id}/status
**Request**:
```json
{
  "status": "PROCESSING",
  "reason": "Materials procured, work starting tomorrow"
}
```

**Response** (200):
```json
{
  "success": true,
  "message": "Status updated to PROCESSING",
  "data": {
    "id": "507f1f77bcf86cd799439013",
    "status": "PROCESSING",
    "updated_at": "2024-01-16T14:30:00Z"
  }
}
```

#### PATCH /complaints/{id}/assign
**Request**:
```json
{
  "assigned_to": "507f1f77bcf86cd799439015"
}
```

**Response** (200):
```json
{
  "success": true,
  "message": "Complaint assigned to Jane Smith",
  "data": {
    "id": "507f1f77bcf86cd799439013",
    "assigned_to": {"id": "507f1f77bcf86cd799439015", "name": "Jane Smith"},
    "assigned_at": "2024-01-16T14:30:00Z",
    "status": "ONGOING"
  }
}
```

#### POST /complaints/{id}/images
**Request**: multipart/form-data
- `files`: array of images (max 5)
- `image_type`: "evidence" | "progress" | "completion"

**Response** (201):
```json
{
  "success": true,
  "message": "Images uploaded",
  "data": {
    "images": [
      {
        "id": "507f1f77bcf86cd799439016",
        "image_type": "evidence",
        "url": "https://storage.example.com/...",
        "file_size": 2048576,
        "mime_type": "image/jpeg",
        "created_at": "2024-01-16T14:30:00Z"
      }
    ]
  }
}
```

#### GET /complaints/{id}/images
**Response** (200):
```json
{
  "success": true,
  "message": "Images retrieved",
  "data": {
    "images": [
      {
        "id": "507f1f77bcf86cd799439016",
        "image_type": "evidence",
        "url": "https://storage.example.com/...",
        "file_size": 2048576,
        "mime_type": "image/jpeg",
        "created_at": "2024-01-16T14:30:00Z"
      }
    ]
  }
}
```

#### DELETE /complaints/{id}/images/{image_id}
**Response** (200):
```json
{
  "success": true,
  "message": "Image deleted",
  "data": {
    "id": "507f1f77bcf86cd799439016",
    "is_deleted": true
  }
}
```

#### GET /complaints/{id}/priority
**Response** (200):
```json
{
  "success": true,
  "message": "Priority breakdown",
  "data": {
    "priority_score": 67.3,
    "breakdown": {
      "community_engagement_score": 25,
      "severity_score": 40,
      "age_score": 15.3,
      "organization_priority_boost": 0
    },
    "weights": {
      "community_engagement": 0.30,
      "severity": 0.40,
      "age": 0.20,
      "organization_boost": 0.10
    },
    "max_score": 100
  }
}
```

---

### Feed

#### GET /feed
**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Items per page (max 50) |
| `sort` | string | `recent` | `recent`, `popular`, `priority`, `nearby` |
| `status` | string | - | Filter by status |
| `category_id` | ObjectId | - | Filter by category |
| `organization_id` | ObjectId | - | Filter by organization |
| `lat` | float | - | Latitude for nearby |
| `lng` | float | - | Longitude for nearby |
| `radius_km` | float | 10 | Search radius for nearby |

**Response** (200):
```json
{
  "success": true,
  "message": "Feed retrieved",
  "data": {
    "items": [
      {
        "id": "507f1f77bcf86cd799439013",
        "title": "Large pothole on Main Street",
        "status": "ONGOING",
        "priority_score": 67.3,
        "like_count": 25,
        "user_liked": false,
        "category": {"id": "...", "name": "Pothole", "icon": "pothole", "color": "#FF6B35"},
        "department": {"id": "...", "name": "Road Maintenance"},
        "location": {"type": "Point", "coordinates": [-73.9857, 40.7484]},
        "address": "Main St & 1st Ave",
        "distance_km": 1.2,
        "created_at": "2024-01-15T10:30:00Z",
        "image_count": 3
      }
    ],
    "pagination": {...}
  }
}
```

#### POST /complaints/{id}/like
**Response** (201):
```json
{
  "success": true,
  "message": "Complaint liked",
  "data": {
    "like_count": 26,
    "user_liked": true
  }
}
```

#### DELETE /complaints/{id}/like
**Response** (200):
```json
{
  "success": true,
  "message": "Complaint unliked",
  "data": {
    "like_count": 25,
    "user_liked": false
  }
}
```

#### GET /complaints/{id}/like-status
**Response** (200):
```json
{
  "success": true,
  "message": "Like status",
  "data": {
    "like_count": 25,
    "user_liked": true
  }
}
```

---

### Organizations

#### GET /organizations/me/complaints
**Query Parameters**:
- `page`, `page_size`
- `status`
- `department_id`
- `assigned_to`
- `sort` (priority, recent, sla)

**Response** (200): Paginated complaints with org-scoped data

#### GET /organizations/me/complaints/priority
**Response** (200): Complaints sorted by priority_score for assignment queue

---

### Notifications

#### GET /notifications
**Query Parameters**:
- `page`, `page_size`
- `is_read` (true/false)

**Response** (200):
```json
{
  "success": true,
  "message": "Notifications retrieved",
  "data": {
    "items": [
      {
        "id": "507f1f77bcf86cd799439017",
        "type": "status_update",
        "title": "Your complaint status updated",
        "message": "Complaint 'Large pothole...' is now ONGOING",
        "complaint_id": "507f1f77bcf86cd799439013",
        "is_read": false,
        "created_at": "2024-01-16T09:00:00Z",
        "metadata": {"previous_status": "SUBMITTED", "new_status": "ONGOING"}
      }
    ],
    "pagination": {...}
  }
}
```

#### GET /notifications/unread-count
**Response** (200):
```json
{
  "success": true,
  "message": "Unread count",
  "data": {"count": 5}
}
```

---

### Admin

#### GET /admin/dashboard
**Response** (200):
```json
{
  "success": true,
  "message": "Dashboard stats",
  "data": {
    "total_users": 1250,
    "total_organizations": 15,
    "total_departments": 45,
    "total_complaints": 3420,
    "complaints_by_status": {
      "SUBMITTED": 120,
      "ONGOING": 340,
      "PROCESSING": 180,
      "COMPLETED": 2500,
      "REJECTED": 80,
      "DUPLICATE": 45,
      "CLOSED": 155
    },
    "avg_resolution_hours": 48.5,
    "sla_compliance_rate": 0.87
  }
}
```

---

### Location

#### GET /location/reverse
**Query Parameters**:
- `lat`: float, between -90.0 and 90.0
- `lng`: float, between -180.0 and 180.0

**Response** (200):
```json
{
  "success": true,
  "message": "Address resolved successfully",
  "data": {
    "formatted_address": "Location near 13.0827, 80.2707, Ward 12, Civic Zone",
    "locality": "Civic Center",
    "administrative_area": "State Division",
    "postal_code": "600001",
    "country": "India",
    "latitude": 13.0827,
    "longitude": 80.2707
  }
}
```

---

## Rate Limiting

**Implementation Strategy**:
- **Phase 1**: In-memory sliding window (single-instance, no Redis dependency)
- **Production**: Redis-backed sliding window (multi-instance horizontal scaling)

| Endpoint Group | Limit | Window |
|----------------|-------|--------|
| Auth (login/register) | 10 | 1 minute |
| Auth (password reset) | 3 | 1 hour |
| Complaint create | 5 | 1 minute |
| Image upload | 10 | 1 minute |
| Feed requests | 60 | 1 minute |
| Like/Unlike | 30 | 1 minute |
| General API | 100 | 1 minute |

Headers returned:
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

---

## Versioning
- All endpoints prefixed with `/api/v1/`
- Breaking changes require `/api/v2/`
- Deprecation: 6-month notice, `Deprecation` header

---

## Webhooks (Future)
- `complaint.created`
- `complaint.status_changed`
- `complaint.assigned`
- `complaint.completed`