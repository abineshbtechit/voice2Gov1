# Voice2Gov Authentication & RBAC Architecture

## Overview
Authentication and authorization system for Voice2Gov using JWT tokens with role-based access control and organization-scoped tenant isolation.

---

## Authentication Architecture

### Token Strategy

#### Access Token (JWT)
- **Algorithm**: RS256 (asymmetric) or HS256 (symmetric for simplicity)
- **Expiration**: 15 minutes (configurable via `admin_settings`)
- **Payload**:
```json
{
  "sub": "user_id",
  "email": "user@example.com",
  "role": "citizen",
  "organization_id": "org_id_or_null",
  "department_id": "dept_id_or_null",
  "type": "access",
  "iat": 1705312800,
  "exp": 1705313700,
  "jti": "unique_token_id"
}
```

#### Refresh Token (JWT)
- **Algorithm**: Same as access token
- **Expiration**: 30 days (configurable)
- **Storage Options** (client chooses based on platform):
  - **Web Portal**: HTTP-only Secure cookie + database hash for revocation
  - **React Native Mobile**: Secure storage (iOS Keychain / Android Keystore) + database hash for revocation
- **Payload**:
```json
{
  "sub": "user_id",
  "type": "refresh",
  "iat": 1705312800,
  "exp": 1707904800,
  "jti": "unique_token_id",
  "device_id": "device_fingerprint"
}
```
- **Rotation**: New refresh token on each use, old revoked (both platforms)
- **Revocation**: Server-side blacklist in `token_blacklist` collection (MongoDB TTL)

### Token Flow

#### Web Portal (HTTP-only Cookie)
```
┌─────────┐     POST /auth/login      ┌──────────────┐
│ Browser │ ───────────────────────► │  Auth Server │
└─────────┘ ◄─────────────────────── │              │
       │         Access Token +       └──────────────┘
       │         Set-Cookie: refresh=...
       ▼                                     │
┌─────────┐     GET /api/...                │
│ Browser │ ──────────────────────────────► │
│         │  Authorization: Bearer <access> │
└─────────┘ ◄────────────────────────────── │
       │         401 if expired              │
       ▼                                     │
┌─────────┐     POST /auth/refresh          │
│ Browser │ ──────────────────────────────► │
│         │  Cookie: refresh=...            │
└─────────┘ ◄────────────────────────────── │
       │         New access token +          │
       │         Set-Cookie: new_refresh=... │
       ▼                                     │
```

#### React Native Mobile (Secure Storage)
```
┌─────────┐     POST /auth/login      ┌──────────────┐
│ Mobile  │ ───────────────────────► │  Auth Server │
└─────────┘ ◄─────────────────────── │              │
       │         Access + Refresh     └──────────────┘
       │         Tokens in JSON body          │
       │         Store in Keychain/Keystore   │
       ▼                                     │
┌─────────┐     GET /api/...                │
│ Mobile  │ ──────────────────────────────► │
│         │  Authorization: Bearer <access> │
└─────────┘ ◄────────────────────────────── │
       │         401 if expired              │
       ▼                                     │
┌─────────┐     POST /auth/refresh          │
│ Mobile  │ ──────────────────────────────► │
│         │  Body: {refresh_token: "..."}   │
└─────────┘ ◄────────────────────────────── │
       │         New access + refresh        │
       │         Update Keychain/Keystore    │
       ▼                                     │
```

### Token Invalidation Strategy

1. **Access Token**: Short-lived, no server-side invalidation (stateless)
2. **Refresh Token**: Server-side blacklist in `token_blacklist` collection
   - On logout: add JTI to blacklist with TTL = refresh token remaining time
   - On password change: revoke all user's refresh tokens
   - On admin suspend: revoke all user's refresh tokens
   - On token rotation: revoke old, issue new

### Password Hashing
- **Algorithm**: bcrypt with cost factor 12
- **Salt**: Generated per password (bcrypt handles internally)
- **Verification**: Constant-time comparison

### Account Status Handling

| Status | Description | Login Allowed |
|--------|-------------|---------------|
| `active` | Normal account | Yes |
| `inactive` | Soft deleted | No |
| `suspended` | Admin suspended | No |
| `pending_verification` | OTP not verified | No (limited) |
| `locked` | Failed attempts exceeded | No (until unlock) |

### Account Lockout
- **Threshold**: 5 failed attempts (configurable)
- **Duration**: 15 minutes (configurable)
- **Fields**: `failed_login_attempts`, `locked_until`
- **Reset**: On successful login or admin unlock

---

## Password Recovery Flow

### Forgot Password
1. User submits email/phone via `POST /auth/forgot-password`
2. System generates 6-digit OTP, stores hash with 10-min TTL
3. OTP sent via email/SMS (mock in Phase 1)
4. User submits OTP via `POST /auth/verify-otp`
4. System validates OTP, issues short-lived reset token (15 min)
5. User submits new password via `POST /auth/reset-password` with reset token

### OTP Flow
- **Length**: 6 digits
- **TTL**: 10 minutes
- **Attempts**: Max 3 per OTP
- **Storage**: `password_reset_otps` collection (ephemeral)
- **Rate Limit**: 3 requests/hour per identifier

---

## Role-Based Access Control (RBAC)

### Roles

| Role | Description | Scope |
|------|-------------|-------|
| `citizen` | Complaint submitter, feed viewer | Own data + public feed |
| `organization_staff` | Process assigned complaints | Own org + assigned dept |
| `organization_admin` | Manage org, departments, staff | Own org (all depts) |
| `admin` | System-wide administration | All organizations |

### Permission Matrix

| Resource | citizen | org_staff | org_admin | admin |
|----------|---------|-----------|-----------|-------|
| **Complaints** | | | | |
| Create | ✓ | ✗ | ✗ | ✓ |
| Read Own | ✓ | ✗ | ✗ | ✓ |
| Read Org | ✗ | ✓ (dept) | ✓ (all) | ✓ |
| Update Own (SUBMITTED) | ✓ | ✗ | ✗ | ✓ |
| Delete Own (SUBMITTED) | ✓ | ✗ | ✗ | ✓ |
| Update Status | ✗ | ✓ (assigned) | ✓ | ✓ |
| Assign | ✗ | ✗ | ✓ | ✓ |
| Complete | ✗ | ✓ (assigned) | ✓ | ✓ |
| **Feed** | | | | |
| View Public | ✓ | ✓ | ✓ | ✓ |
| Like/Unlike | ✓ | ✗ | ✗ | ✓ |
| **Organizations** | | | | |
| List | ✗ | ✗ | ✗ | ✓ |
| Create | ✗ | ✗ | ✗ | ✓ |
| Read Own | ✗ | ✗ | ✓ | ✓ |
| Update Own | ✗ | ✗ | ✓ | ✓ |
| **Departments** | | | | |
| List Org | ✗ | ✓ | ✓ | ✓ |
| Create | ✗ | ✗ | ✓ | ✓ |
| Update | ✗ | ✗ | ✓ | ✓ |
| Delete | ✗ | ✗ | ✓ | ✓ |
| **Categories** | | | | |
| List Active | ✓ | ✓ | ✓ | ✓ |
| Manage | ✗ | ✗ | ✗ | ✓ |
| **Users** | | | | |
| Read Own Profile | ✓ | ✓ | ✓ | ✓ |
| Update Own Profile | ✓ | ✓ | ✓ | ✓ |
| List Org Users | ✗ | ✗ | ✓ | ✓ |
| Suspend/Activate | ✗ | ✗ | ✗ | ✓ |
| **Notifications** | | | | |
| Read Own | ✓ | ✓ | ✓ | ✓ |
| **Admin** | | | | |
| Dashboard | ✗ | ✗ | ✗ | ✓ |
| Audit Logs | ✗ | ✗ | ✗ | ✓ |
| Settings | ✗ | ✗ | ✗ | ✓ |

---

## Organization Tenant Isolation

### Core Principle
**Organization users (staff/admin) can ONLY access resources within their own organization.**

### Implementation

#### 1. Request-Level Enforcement
```python
# FastAPI dependency
async def get_current_org_user(current_user: User = Depends(get_current_user)):
    if current_user.role in ["organization_staff", "organization_admin"]:
        if not current_user.organization_id:
            raise Forbidden("Organization context required")
    return current_user
```

#### 2. Repository-Level Scoping
```python
class ComplaintRepository:
    async def get_by_id(self, complaint_id: ObjectId, user: User) -> Complaint:
        query = {"_id": complaint_id}
        
        # Apply org isolation
        if user.role in ["organization_staff", "organization_admin"]:
            query["organization_id"] = user.organization_id
            if user.role == "organization_staff":
                query["department_id"] = user.department_id
        elif user.role == "citizen":
            query["user_id"] = user.id
            
        return await self.collection.find_one(query)
```

#### 3. Service-Level Validation
```python
async def assign_complaint(self, complaint_id: ObjectId, staff_id: ObjectId, admin: User):
    # Verify admin owns the org
    if admin.organization_id != complaint.organization_id:
        raise Forbidden("Cannot assign complaint from another organization")
    
    # Verify staff belongs to same org/dept
    staff = await self.user_repo.get_by_id(staff_id)
    if staff.organization_id != admin.organization_id:
        raise Forbidden("Staff must belong to same organization")
```

### Cross-Organization Access Rules

| Scenario | Allowed? | Mechanism |
|----------|----------|-----------|
| Citizen views own complaints | ✓ | `user_id` filter |
| Citizen views public feed | ✓ | `visibility == 'public'` filter |
| Org staff views assigned complaints | ✓ | `assigned_to` + `department_id` |
| Org staff views other org's complaints | ✗ | Repo filter blocks |
| Org admin views all org complaints | ✓ | `organization_id` filter |
| Admin views all complaints | ✓ | No org filter (superuser) |
| Staff assigns to other org staff | ✗ | Validation rejects |

---

## Resource Ownership Checks

### Complaint Ownership
- **Citizen**: Owns complaints where `user_id == current_user.id`
- **Org Staff**: "Owns" complaints assigned to them (`assigned_to == current_user.id`)
- **Org Admin**: "Owns" all complaints in their organization
- **Admin**: Owns all complaints

### Authorization Decorators
```python
# Permission checks as dependencies
def require_role(*roles: str):
    async def checker(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise Forbidden(f"Required role: {roles}")
        return user
    return Depends(checker)

def require_org_access(resource_org_id: ObjectId):
    async def checker(user: User = Depends(get_current_user)):
        if user.role == "admin":
            return user
        if user.organization_id != resource_org_id:
            raise Forbidden("Organization access denied")
        return user
    return Depends(checker)
```

---

## API Security Headers

```
Content-Security-Policy: default-src 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=()
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

---

## CORS Configuration
```python
CORS_ORIGINS = [
    "https://app.voice2gov.example.com",
    "https://admin.voice2gov.example.com",
    "http://localhost:3000",  # dev
    "http://localhost:8081",  # react native
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = ["Authorization", "Content-Type", "X-Request-ID"]
```

---

## Session Management

### Refresh Token Rotation
1. Client uses refresh token to get new access token
2. Server validates refresh token (not blacklisted, not expired)
3. Server **revokes old refresh token** (adds to blacklist)
4. Server issues **new refresh token** + new access token
5. Client stores new tokens

### Concurrent Session Limits
- **Default**: 5 active refresh tokens per user
- **Exceed**: Oldest revoked on new login
- **Admin**: Can view/revoke sessions via admin API

---

## Security Considerations

### Token Storage (Client)

| Platform | Access Token | Refresh Token |
|----------|--------------|---------------|
| **Web Portal** | Memory (JavaScript variable) | HTTP-only Secure cookie (SameSite=Strict) |
| **React Native** | Memory (React state) | Secure Storage (iOS Keychain / Android Keystore) |
| **Both** | Never in localStorage/sessionStorage | Never in AsyncStorage/plaintext |

### Transport Security
- **HTTPS Only**: All production endpoints
- **HSTS**: Enabled with preload
- **Certificate Pinning**: Mobile app (Phase 2)

### Audit Trail
All auth events logged to `audit_logs`:
- Login success/failure
- Token refresh
- Password change
- Account lock/unlock
- Role change
- Suspension/activation