# Voice2Gov Security Architecture

## Overview
Comprehensive security design for Voice2Gov covering authentication, authorization, data protection, input validation, and infrastructure security.

---

## Security Layers

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                          │
│  React Native App (Certificate Pinning, Secure Storage) │
└─────────────────────────────────────────────────────────┘
                            │ HTTPS/TLS 1.3
                            ▼
┌─────────────────────────────────────────────────────────┐
│                   EDGE LAYER                             │
│  Rate Limiting │ WAF │ DDoS Protection │ TLS Termination│
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                  APPLICATION LAYER                       │
│  Auth Middleware │ RBAC │ Input Validation │ Audit Logs │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    DATA LAYER                            │
│  Encryption at Rest │ Field-Level Encryption │ Backups  │
└─────────────────────────────────────────────────────────┘
```

---

## Authentication Security

### JWT Implementation
```python
# Token signing
ALGORITHM = "RS256"  # Asymmetric - private key signs, public key verifies
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30

# Key rotation
JWT_PRIVATE_KEY = load_private_key()      # Rotated every 90 days
JWT_PUBLIC_KEY = load_public_key()        # Distributed to services
JWT_KEY_ID = "key-2024-01"                # Key identifier in header
```

### Token Claims
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
  "jti": "unique_token_id",
  "kid": "key-2024-01"
}
```

### Refresh Token Security
- **Storage**: HTTP-only, Secure, SameSite=Strict cookie
- **Rotation**: New refresh token issued on each use, old revoked
- **Revocation**: Immediate via blacklist collection (TTL = token expiry)
- **Device binding**: Optional device fingerprint in token

### Password Security
- **Hashing**: bcrypt with cost factor 12
- **Policy**: Min 8 chars, 1 uppercase, 1 lowercase, 1 number, 1 special
- **Breach check**: Check against HaveIBeenPwned API (optional)
- **History**: Prevent last 5 passwords reuse

### Account Protection
| Protection | Implementation |
|------------|----------------|
| Brute force | 5 failed attempts → 15 min lockout |
| Credential stuffing | Rate limit login by IP (10/min) |
| Session fixation | New session ID on login |
| Concurrent sessions | Max 5, oldest revoked |
| Password reset | OTP-based, 10-min expiry, 3 attempts |

---

## Authorization Security

### RBAC Enforcement Points
1. **Middleware**: Role extraction from JWT
2. **Dependencies**: `require_role()`, `require_org_access()`
3. **Repository**: Query scoping by organization
4. **Service**: Business logic validation

### Organization Isolation (Critical)
```python
# Every repository query for org-scoped resources
async def get_complaints(self, user: User, filters: dict) -> List[Complaint]:
    query = filters.copy()
    
    if user.role == "citizen":
        query["user_id"] = user.id
    elif user.role in ["organization_staff", "organization_admin"]:
        query["organization_id"] = user.organization_id
        if user.role == "organization_staff":
            query["department_id"] = user.department_id
    # Admin: no org filter
    
    return await self.collection.find(query).to_list()
```

### Resource Ownership Checks
```python
# Service layer validation before mutation
async def update_complaint(self, complaint_id: ObjectId, user: User, data: dict):
    complaint = await self.repo.get_by_id(complaint_id)
    
    # Ownership verification
    if user.role == "citizen":
        if complaint.user_id != user.id:
            raise Forbidden("Not your complaint")
        if complaint.status != "SUBMITTED":
            raise Forbidden("Cannot update after assignment")
    
    # ... proceed with update
```

---

## Input Validation & Sanitization

### Pydantic Validation (All Inputs)
```python
class ComplaintCreate(BaseModel):
    title: constr(min_length=5, max_length=200, strip_whitespace=True)
    description: constr(min_length=10, max_length=5000, strip_whitespace=True)
    category_id: ObjectIdStr
    location: GeoJSONPoint
    address: Optional[constr(max_length=500)] = None
    
    @validator('location')
    def validate_coordinates(cls, v):
        lng, lat = v.coordinates
        if not (-180 <= lng <= 180) or not (-90 <= lat <= 90):
            raise ValueError("Invalid coordinates")
        return v
```

### Sanitization Rules
| Input Type | Sanitization |
|------------|--------------|
| Text fields | Strip whitespace, limit length, HTML escape on output |
| Filenames | Alphanumeric + `._-` only, basename only |
| HTML/Rich text | Not accepted (plain text only) |
| JSON metadata | Schema validation, depth limit 5 |
| Coordinates | Range validation, GeoJSON format |

### Injection Prevention
- **NoSQL Injection**: Use parameterized queries (PyMongo), never string concatenation
- **Command Injection**: No shell commands, use subprocess with args list if needed
- **Path Traversal**: `os.path.basename()`, validate against allowed paths
- **XSS**: API returns JSON only, frontend handles escaping

---

## File Upload Security

### Validation Pipeline
```
Upload Request
      │
      ▼
┌─────────────┐
│ Size Check  │ Content-Length header + stream limit
└─────────────┘
      │
      ▼
┌─────────────┐
│ MIME Check  │ Allowed types per image_type
└─────────────┘
      │
      ▼
┌─────────────┐
│ Magic Bytes │ Verify file signature matches MIME
└─────────────┘
      │
      ▼
┌─────────────┐
│ Filename    │ Sanitize, UUID prefix, no path traversal
│ Sanitization│
└─────────────┘
      │
      ▼
┌─────────────┐
│ Dimensions  │ Optional: Pillow verify image, max 4096x4096
└─────────────┘
      │
      ▼
┌─────────────┐
│ Virus Scan  │ Future: ClamAV integration
└─────────────┘
```

### Storage Security
- **No direct access**: All files served via signed URLs
- **Encryption at rest**: S3 SSE-S3 or SSE-KMS
- **Bucket policies**: No public read, access via CloudFront/OIDC
- **CDN**: Signed cookies for private content

---

## Data Protection

### Encryption
| Data | At Rest | In Transit |
|------|---------|------------|
| Passwords | bcrypt (irreversible) | TLS 1.3 |
| JWT Secrets | Environment variables / KMS | N/A |
| MongoDB | Volume encryption (LUKS/AWS EBS) | TLS |
| File Storage | SSE-S3 / SSE-KMS | HTTPS |
| Backups | AES-256 | TLS |

### Field-Level Encryption (Sensitive PII)
```python
# Fields requiring encryption
ENCRYPTED_FIELDS = [
    "users.phone",
    "users.email",  # Optional: hash for lookup, encrypt for storage
    "notifications.message",  # May contain complaint details
    "audit_logs.metadata"  # May contain PII
]

# Implementation: Application-level encryption with Fernet
# Key stored in AWS KMS / HashiCorp Vault
```

### Data Retention
| Data Type | Retention | Deletion |
|-----------|-----------|----------|
| Complaints | 7 years (legal) | Anonymize after |
| Audit Logs | 7 years | Archive |
| Notifications | 1 year | Auto-delete |
| Device Tokens | 90 days inactive | Auto-delete |
| Images | Permanent (evidence) | On complaint deletion |

---

## Audit Logging

### Events Logged
```python
AUDIT_EVENTS = {
    # Auth
    "auth.login_success": {"user_id", "ip", "user_agent"},
    "auth.login_failure": {"identifier", "ip", "reason"},
    "auth.logout": {"user_id"},
    "auth.token_refresh": {"user_id", "device_id"},
    "auth.password_change": {"user_id", "ip"},
    "auth.password_reset": {"user_id", "ip"},
    
    # User Management
    "user.create": {"actor_id", "target_user_id", "role"},
    "user.suspend": {"actor_id", "target_user_id", "reason"},
    "user.activate": {"actor_id", "target_user_id"},
    "user.role_change": {"actor_id", "target_user_id", "old_role", "new_role"},
    
    # Complaints
    "complaint.create": {"actor_id", "complaint_id"},
    "complaint.status_change": {"actor_id", "complaint_id", "from", "to", "reason"},
    "complaint.assign": {"actor_id", "complaint_id", "assignee_id"},
    "complaint.complete": {"actor_id", "complaint_id", "summary"},
    "complaint.reject": {"actor_id", "complaint_id", "reason"},
    "complaint.delete": {"actor_id", "complaint_id"},
    
    # Organization
    "organization.create": {"actor_id", "org_id"},
    "organization.update": {"actor_id", "org_id", "changes"},
    "organization.status_change": {"actor_id", "org_id", "status"},
    
    # Admin
    "admin.settings_change": {"actor_id", "key", "old_value", "new_value"},
    "admin.user_impersonate": {"actor_id", "target_user_id"},
}
```

### Audit Log Integrity
- **Immutable**: No UPDATE/DELETE on audit_logs collection
- **Append-only**: Enforced by application + MongoDB validation
- **Hash chaining**: Each log references previous hash (future)
- **Export**: Signed exports for compliance

---

## Rate Limiting

### Limits by Endpoint
```python
RATE_LIMITS = {
    # Auth - strict
    "/auth/login": {"requests": 10, "window": 60},           # 10/min
    "/auth/register": {"requests": 5, "window": 3600},       # 5/hour
    "/auth/forgot-password": {"requests": 3, "window": 3600}, # 3/hour
    "/auth/verify-otp": {"requests": 5, "window": 600},      # 5/10min
    
    # Complaints
    "/complaints": {"requests": 20, "window": 60},           # 20/min create
    "/complaints/*/images": {"requests": 10, "window": 60},  # 10/min upload
    
    # Feed
    "/feed": {"requests": 60, "window": 60},                 # 60/min
    "/complaints/*/like": {"requests": 30, "window": 60},    # 30/min
    
    # General API
    "default": {"requests": 100, "window": 60},              # 100/min
    
    # Admin
    "/admin/*": {"requests": 200, "window": 60},             # 200/min
}
```

### Implementation
- **Algorithm**: Sliding window
- **Key**: `user_id` for authenticated, `IP` for anonymous
- **Storage**:
  - **Phase 1**: In-memory (single-instance, `asyncio.Lock` protected)
  - **Production**: Redis sorted sets (multi-instance horizontal scaling)
- **Response Headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- **Exceeded**: 429 with `Retry-After` header

---

## Security Headers

```python
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self' https://api.voice2gov.example.com; frame-ancestors 'none';",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}
```

---

## CORS Policy
```python
CORS_CONFIG = {
    "allow_origins": [
        "https://app.voice2gov.example.com",
        "https://admin.voice2gov.example.com",
    ],
    "allow_origin_regex": r"https://.*\.voice2gov\.example\.com",
    "allow_credentials": True,
    "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    "allow_headers": ["Authorization", "Content-Type", "X-Request-ID", "X-CSRF-Token"],
    "expose_headers": ["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    "max_age": 86400,
}
```

---

## Secrets Management

### Development
- `.env` file (gitignored)
- `.env.example` committed with placeholders

### Production
- **AWS**: Secrets Manager / Parameter Store
- **Kubernetes**: Sealed Secrets / External Secrets Operator
- **HashiCorp Vault**: Dynamic secrets for DB, rotation

### Secret Categories
| Secret | Rotation | Storage |
|--------|----------|---------|
| JWT Private Key | 90 days | KMS/HSM |
| JWT Public Key | 90 days | ConfigMap |
| MongoDB Password | 90 days | Secrets Manager |
| S3 Credentials | 90 days | Secrets Manager |
| Email/SMS API Keys | 180 days | Secrets Manager |
| Encryption Keys | 1 year | KMS/HSM |

---

## Vulnerability Management

### Dependency Scanning
- **Tool**: `pip-audit` / `safety` / GitHub Dependabot
- **Frequency**: Every build + weekly scheduled
- **Policy**: Critical/High fixed within 7 days

### SAST/DAST
- **SAST**: Bandit (Python), Semgrep (CI)
- **DAST**: OWASP ZAP (staging)
- **Container**: Trivy/Grype for Docker images

### Penetration Testing
- Annual third-party pen test
- Bug bounty program (future)

---

## Incident Response

### Security Event Classification
| Severity | Examples | Response Time |
|----------|----------|---------------|
| Critical | Data breach, RCE, auth bypass | < 1 hour |
| High | SQLi/NoSQLi, privilege escalation | < 4 hours |
| Medium | XSS, CSRF, info disclosure | < 24 hours |
| Low | Rate limit bypass, weak config | < 1 week |

### Playbooks
1. **Credential Compromise**: Rotate keys, revoke tokens, notify users
2. **Data Breach**: Contain, assess, notify authorities (72hr GDPR), remediate
3. **DDoS**: Enable WAF rules, scale infrastructure, contact provider
4. **Vulnerability Exploit**: Patch, investigate scope, rotate secrets

---

## Compliance Considerations

### GDPR (If Applicable)
- **Lawful basis**: Consent (citizen), Legitimate interest (org)
- **Data subject rights**: Access, rectification, erasure, portability
- **DPIA**: Required for large-scale processing
- **DPO**: Designated for public authority

### Data Localization
- MongoDB: Region-specific clusters
- File storage: Region-specific buckets
- Backups: Same region

---

## Security Testing Checklist

### Pre-Deployment
- [ ] All endpoints require authentication (except public)
- [ ] RBAC enforced on all mutations
- [ ] Organization isolation verified
- [ ] Input validation on all fields
- [ ] File upload validation complete
- [ ] Rate limiting configured
- [ ] Security headers present
- [ ] Secrets not in code/config
- [ ] Audit logging for sensitive actions
- [ ] Dependency scan clean

### Ongoing
- [ ] Weekly dependency scans
- [ ] Monthly access review
- [ ] Quarterly pen test
- [ ] Annual security training