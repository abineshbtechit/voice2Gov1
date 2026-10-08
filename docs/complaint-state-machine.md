# Voice2Gov Complaint Status Machine

## Overview
Formal state machine for complaint lifecycle. Prevents invalid transitions, enforces actor permissions, and triggers side effects (notifications, audit logs).

---

## States

| State | Code | Description | Terminal? |
|-------|------|-------------|-----------|
| Submitted | `SUBMITTED` | Citizen created, awaiting triage | No |
| Ongoing | `ONGOING` | Assigned to staff, work started | No |
| Processing | `PROCESSING` | Active work in progress | No |
| Completed | `COMPLETED` | Work finished, citizen notified | Yes |
| Rejected | `REJECTED` | Invalid/out of scope, reason required | Yes |
| Duplicate | `DUPLICATE` | Duplicate of existing complaint | Yes |
| Closed | `CLOSED` | Admin closed, no further action | Yes |

---

## Primary Citizen-Facing Lifecycle
```
SUBMITTED → ONGOING → PROCESSING → COMPLETED
```

---

## Status Transition Matrix

### From SUBMITTED
| To Status | Allowed? | Actor | Reason Required | Audit | Notification |
|-----------|----------|-------|-----------------|-------|--------------|
| ONGOING | ✓ | org_staff, org_admin, admin | Optional | ✓ | ✓ (citizen) |
| PROCESSING | ✗ | - | - | - | - |
| COMPLETED | ✗ | - | - | - | - |
| REJECTED | ✓ | org_staff, org_admin, admin | **Required** | ✓ | ✓ (citizen) |
| DUPLICATE | ✓ | org_staff, org_admin, admin | **Required** (ref to original) | ✓ | ✓ (citizen) |
| CLOSED | ✓ | admin | Optional | ✓ | ✓ (citizen) |
| SUBMITTED | N/A | - | - | - | - |

### From ONGOING
| To Status | Allowed? | Actor | Reason Required | Audit | Notification |
|-----------|----------|-------|-----------------|-------|--------------|
| SUBMITTED | ✗ | - | - | - | - |
| ONGOING | N/A | - | - | - | - |
| PROCESSING | ✓ | org_staff (assigned), org_admin, admin | Optional | ✓ | ✓ (citizen) |
| COMPLETED | ✗ | - | - | - | - |
| REJECTED | ✓ | org_staff (assigned), org_admin, admin | **Required** | ✓ | ✓ (citizen) |
| DUPLICATE | ✓ | org_staff (assigned), org_admin, admin | **Required** | ✓ | ✓ (citizen) |
| CLOSED | ✓ | admin | Optional | ✓ | ✓ (citizen) |

### From PROCESSING
| To Status | Allowed? | Actor | Reason Required | Audit | Notification |
|-----------|----------|-------|-----------------|-------|--------------|
| SUBMITTED | ✗ | - | - | - | - |
| ONGOING | ✓ | org_staff (assigned), org_admin, admin | Optional | ✓ | ✓ (citizen) |
| PROCESSING | N/A | - | - | - | - |
| COMPLETED | ✓ | org_staff (assigned), org_admin, admin | **Required** (completion summary) | ✓ | ✓ (citizen) |
| REJECTED | ✓ | org_staff (assigned), org_admin, admin | **Required** | ✓ | ✓ (citizen) |
| DUPLICATE | ✓ | org_staff (assigned), org_admin, admin | **Required** | ✓ | ✓ (citizen) |
| CLOSED | ✓ | admin | Optional | ✓ | ✓ (citizen) |

### From COMPLETED (Terminal)
| To Status | Allowed? | Actor | Reason Required | Audit | Notification |
|-----------|----------|-------|-----------------|-------|--------------|
| Any | ✗ | - | - | - | - |
| *Exception* | REOPEN | admin | **Required** | ✓ | ✓ (citizen) |

**Note**: REOPEN is not a standard transition. Implemented as admin action creating new complaint linked to original.

### From REJECTED (Terminal)
| To Status | Allowed? | Actor | Reason Required | Audit | Notification |
|-----------|----------|-------|-----------------|-------|--------------|
| Any | ✗ | - | - | - | - |

### From DUPLICATE (Terminal)
| To Status | Allowed? | Actor | Reason Required | Audit | Notification |
|-----------|----------|-------|-----------------|-------|--------------|
| Any | ✗ | - | - | - | - |

### From CLOSED (Terminal)
| To Status | Allowed? | Actor | Reason Required | Audit | Notification |
|-----------|----------|-------|-----------------|-------|--------------|
| Any | ✗ | - | - | - | - |

---

## Transition Rules Summary

### Valid Transitions Graph
```
SUBMITTED ──► ONGOING ──► PROCESSING ──► COMPLETED
   │            │            │
   ├───────────►│            │
   │            ├───────────►│
   ▼            ▼            ▼
 REJECTED   REJECTED     REJECTED
   │            │            │
   └───────────►└───────────►│
                             ▼
                        DUPLICATE
                             │
                             ▼
                          CLOSED (admin only)
```

### Forbidden Transitions (Always)
- Any → SUBMITTED (except initial creation)
- Terminal states → Any non-terminal (except admin REOPEN)
- Backward: COMPLETED → PROCESSING, PROCESSING → SUBMITTED
- Skip: SUBMITTED → COMPLETED, SUBMITTED → PROCESSING

---

## Actor Permissions by Transition

| Transition | Citizen | Org Staff | Org Admin | Admin |
|------------|---------|-----------|-----------|-------|
| SUBMITTED → ONGOING | ✗ | ✓ (if dept match) | ✓ | ✓ |
| SUBMITTED → REJECTED | ✗ | ✓ (if dept match) | ✓ | ✓ |
| SUBMITTED → DUPLICATE | ✗ | ✓ (if dept match) | ✓ | ✓ |
| ONGOING → PROCESSING | ✗ | ✓ (if assigned) | ✓ | ✓ |
| ONGOING → REJECTED | ✗ | ✓ (if assigned) | ✓ | ✓ |
| ONGOING → DUPLICATE | ✗ | ✓ (if assigned) | ✓ | ✓ |
| ONGOING → ONGOING (reassign) | ✗ | ✗ | ✓ | ✓ |
| PROCESSING → COMPLETED | ✗ | ✓ (if assigned) | ✓ | ✓ |
| PROCESSING → ONGOING | ✗ | ✓ (if assigned) | ✓ | ✓ |
| PROCESSING → REJECTED | ✗ | ✓ (if assigned) | ✓ | ✓ |
| PROCESSING → DUPLICATE | ✗ | ✓ (if assigned) | ✓ | ✓ |
| Any → CLOSED | ✗ | ✗ | ✗ | ✓ |

---

## Required Fields by Transition

### SUBMITTED → ONGOING
```json
{
  "status": "ONGOING",
  "reason": "Optional: Assigned to John Doe",
  "assigned_to": "user_id"  // Required if not already assigned
}
```

### SUBMITTED → REJECTED
```json
{
  "status": "REJECTED",
  "reason": "Required: Out of jurisdiction",
  "rejection_reason": "Detailed explanation for citizen"
}
```

### SUBMITTED → DUPLICATE
```json
{
  "status": "DUPLICATE",
  "reason": "Required: Duplicate of complaint #12345",
  "duplicate_of": "complaint_id"  // Required: reference to original
}
```

### ONGOING → PROCESSING
```json
{
  "status": "PROCESSING",
  "reason": "Optional: Materials procured, starting work"
}
```

### ONGOING → REJECTED
```json
{
  "status": "REJECTED",
  "reason": "Required: Cannot resolve - private property",
  "rejection_reason": "Detailed explanation"
}
```

### ONGOING → DUPLICATE
```json
{
  "status": "DUPLICATE",
  "reason": "Required: Already tracked in complaint #12345",
  "duplicate_of": "complaint_id"
}
```

### PROCESSING → COMPLETED
```json
{
  "status": "COMPLETED",
  "reason": "Required: Pothole filled, road restored",
  "completion_images": ["image_id_1", "image_id_2"]  // Optional but encouraged
}
```

### PROCESSING → ONGOING
```json
{
  "status": "ONGOING",
  "reason": "Optional: Waiting for materials delivery"
}
```

### PROCESSING → REJECTED
```json
{
  "status": "REJECTED",
  "reason": "Required: Issue resolved by third party",
  "rejection_reason": "Detailed explanation"
}
```

---

## Validation Logic (Pseudocode)

```python
class ComplaintStateMachine:
    TRANSITIONS = {
        "SUBMITTED": ["ONGOING", "REJECTED", "DUPLICATE", "CLOSED"],
        "ONGOING": ["PROCESSING", "REJECTED", "DUPLICATE", "CLOSED", "ONGOING"],  # ONGOING for reassignment
        "PROCESSING": ["COMPLETED", "ONGOING", "REJECTED", "DUPLICATE", "CLOSED"],
        "COMPLETED": [],  # Terminal
        "REJECTED": [],   # Terminal
        "DUPLICATE": [],  # Terminal
        "CLOSED": [],     # Terminal
    }
    
    ACTOR_PERMISSIONS = {
        ("SUBMITTED", "ONGOING"): ["organization_staff", "organization_admin", "admin"],
        ("SUBMITTED", "REJECTED"): ["organization_staff", "organization_admin", "admin"],
        ("SUBMITTED", "DUPLICATE"): ["organization_staff", "organization_admin", "admin"],
        ("ONGOING", "PROCESSING"): ["organization_staff", "organization_admin", "admin"],
        ("ONGOING", "REJECTED"): ["organization_staff", "organization_admin", "admin"],
        ("ONGOING", "DUPLICATE"): ["organization_staff", "organization_admin", "admin"],
        ("ONGOING", "ONGOING"): ["organization_admin", "admin"],  # Reassignment
        ("PROCESSING", "COMPLETED"): ["organization_staff", "organization_admin", "admin"],
        ("PROCESSING", "ONGOING"): ["organization_staff", "organization_admin", "admin"],
        ("PROCESSING", "REJECTED"): ["organization_staff", "organization_admin", "admin"],
        ("PROCESSING", "DUPLICATE"): ["organization_staff", "organization_admin", "admin"],
        ("*", "CLOSED"): ["admin"],
    }
    
    REQUIRES_REASON = {
        ("SUBMITTED", "REJECTED"),
        ("SUBMITTED", "DUPLICATE"),
        ("ONGOING", "REJECTED"),
        ("ONGOING", "DUPLICATE"),
        ("PROCESSING", "COMPLETED"),
        ("PROCESSING", "REJECTED"),
        ("PROCESSING", "DUPLICATE"),
    }
    
    REQUIRES_AUDIT = True  # All transitions
    
    TRIGGERS_NOTIFICATION = True  # All transitions
    
    @classmethod
    def can_transition(cls, from_status: str, to_status: str, actor: User) -> bool:
        # Check if transition exists
        if to_status not in cls.TRANSITIONS.get(from_status, []):
            return False
        
        # Check actor permission
        allowed_roles = cls.ACTOR_PERMISSIONS.get((from_status, to_status), [])
        if actor.role not in allowed_roles:
            return False
        
        # Check org/dept scoping for org_staff
        if actor.role == "organization_staff":
            # Additional check: must be assigned to complaint or in same dept
            pass  # Implemented in service layer
        
        return True
    
    @classmethod
    def validate_transition(cls, from_status: str, to_status: str, 
                           actor: User, data: dict) -> ValidationResult:
        if not cls.can_transition(from_status, to_status, actor):
            return ValidationResult(
                valid=False,
                error="INVALID_STATUS_TRANSITION",
                message=f"Cannot transition from {from_status} to {to_status} for role {actor.role}"
            )
        
        if (from_status, to_status) in cls.REQUIRES_REASON:
            if not data.get("reason"):
                return ValidationResult(
                    valid=False,
                    error="REASON_REQUIRED",
                    message=f"Reason is required for {from_status} → {to_status}"
                )
        
        if to_status == "DUPLICATE" and not data.get("duplicate_of"):
            return ValidationResult(
                valid=False,
                error="DUPLICATE_REF_REQUIRED",
                message="duplicate_of complaint ID is required"
            )
        
        return ValidationResult(valid=True)
```

---

## Side Effects by Transition

### Audit Log Entry (All Transitions)
```json
{
  "actor_id": "user_id",
  "actor_role": "organization_staff",
  "action": "complaint.status_changed",
  "entity_type": "complaint",
  "entity_id": "complaint_id",
  "metadata": {
    "previous_status": "SUBMITTED",
    "new_status": "ONGOING",
    "reason": "Assigned to maintenance team"
  },
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0...",
  "created_at": "2024-01-16T09:00:00Z"
}
```

### Notification Triggers

| Transition | Notification Type | Recipient | Template |
|------------|-------------------|-----------|----------|
| SUBMITTED → ONGOING | `status_update` | Citizen | "Your complaint is now being processed" |
| SUBMITTED → REJECTED | `rejection` | Citizen | "Your complaint was rejected: {reason}" |
| SUBMITTED → DUPLICATE | `duplicate` | Citizen | "Your complaint is a duplicate of #{ref}" |
| ONGOING → PROCESSING | `status_update` | Citizen | "Work has started on your complaint" |
| ONGOING → REJECTED | `rejection` | Citizen | "Your complaint was rejected: {reason}" |
| PROCESSING → COMPLETED | `completion` | Citizen | "Your complaint has been resolved" |
| PROCESSING → ONGOING | `status_update` | Citizen | "Work paused: {reason}" |
| Any → CLOSED | `status_update` | Citizen | "Complaint closed by administrator" |
| Assignment | `assignment` | Staff | "You have been assigned complaint #{id}" |

### Complaint Update Record (All Transitions)
Created in `complaint_updates` collection with:
- `update_type`: `status_change`
- `previous_status`, `new_status`
- `message`: reason
- `visibility`: "public" (visible to citizen)

### SLA Tracking
- **Start**: `SUBMITTED` → `ONGOING` (assigned_at)
- **Pause**: `PROCESSING` → `ONGOING` (if applicable)
- **End**: `COMPLETED` (completed_at)
- **Breach**: Monitor `sla_deadline` vs `completed_at`

---

## API Implementation

### PATCH /complaints/{id}/status
```python
@router.patch("/{id}/status")
async def update_status(
    id: ObjectId,
    payload: StatusUpdateRequest,
    current_user: User = Depends(get_current_org_user),
    complaint_service: ComplaintService = Depends()
):
    complaint = await complaint_service.get_complaint(id, current_user)
    
    # Validate transition
    result = ComplaintStateMachine.validate_transition(
        complaint.status, payload.status, current_user, payload.dict()
    )
    if not result.valid:
        raise HTTPException(422, detail=result.message, error_code=result.error)
    
    # Execute transition
    updated = await complaint_service.change_status(
        complaint, payload.status, current_user, payload.reason, payload.duplicate_of
    )
    
    return SuccessResponse(data=updated)
```

### PATCH /complaints/{id}/complete
```python
@router.patch("/{id}/complete")
async def complete_complaint(
    id: ObjectId,
    payload: CompleteComplaintRequest,
    current_user: User = Depends(get_current_org_user),
    complaint_service: ComplaintService = Depends()
):
    # Validates PROCESSING → COMPLETED transition
    # Requires completion summary
    # Handles completion images
```

### PATCH /complaints/{id}/assign
```python
@router.patch("/{id}/assign")
async def assign_complaint(
    id: ObjectId,
    payload: AssignComplaintRequest,
    current_user: User = Depends(require_role("organization_admin", "admin")),
    complaint_service: ComplaintService = Depends()
):
    # Only org_admin/admin can assign
    # Validates staff belongs to same org/dept
    # Triggers SUBMITTED → ONGOING or ONGOING → ONGOING (reassign)
```

---

## Testing Scenarios

### Valid Transitions
1. Citizen creates → SUBMITTED
2. Org staff assigns → ONGOING
3. Assigned staff starts work → PROCESSING
4. Assigned staff completes → COMPLETED
5. Org staff rejects at SUBMITTED → REJECTED
6. Org staff marks duplicate at SUBMITTED → DUPLICATE
7. Admin closes any → CLOSED
8. Assigned staff moves back → ONGOING (waiting for materials)

### Invalid Transitions (Should Reject 422)
1. SUBMITTED → COMPLETED (skip)
2. SUBMITTED → PROCESSING (skip)
3. ONGOING → SUBMITTED (backward)
4. PROCESSING → SUBMITTED (backward)
4. COMPLETED → ONGOING (terminal)
5. REJECTED → ONGOING (terminal)
6. Citizen attempts any status change
7. Org staff from different org attempts change
8. Org staff not assigned attempts PROCESSING/COMPLETED

### Edge Cases
1. Concurrent status updates (optimistic locking via version)
2. Reassignment during ONGOING (ONGOING → ONGOING)
3. Duplicate marking with invalid reference
4. Completion without required images (warn but allow)