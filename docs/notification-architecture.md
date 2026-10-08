# Voice2Gov Notification Architecture

## Overview
Notification system for real-time updates to citizens and organization staff via in-app notifications and push notifications (abstraction for future provider integration).

---

## Notification Types

| Type | Trigger | Recipient | Channel |
|------|---------|-----------|---------|
| `status_update` | Complaint status changes | Citizen | In-app + Push |
| `assignment` | Complaint assigned to staff | Staff | In-app + Push |
| `completion` | Complaint marked COMPLETED | Citizen | In-app + Push |
| `rejection` | Complaint REJECTED | Citizen | In-app + Push |
| `duplicate` | Complaint marked DUPLICATE | Citizen | In-app + Push |
| `comment` | Progress update added | Citizen | In-app + Push |
| `like` | Citizen likes complaint | Citizen (optional) | In-app only |
| `system` | Admin announcements, maintenance | Targeted users | In-app + Push |

---

## Data Model

### notifications Collection
```json
{
  "_id": ObjectId,
  "user_id": ObjectId,           // Ref: users
  "complaint_id": ObjectId,      // Ref: complaints (nullable)
  "type": "status_update",       // Enum
  "title": "Status Updated",
  "message": "Your complaint is now ONGOING",
  "is_read": false,
  "read_at": null,
  "metadata": {
    "previous_status": "SUBMITTED",
    "new_status": "ONGOING",
    "deep_link": "app://complaint/123"
  },
  "created_at": ISODate
}
```

### device_tokens Collection
```json
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "device_token": "fcm_token_or_apns_token",
  "platform": "android",         // ios, android, web
  "device_id": "device_uuid",
  "app_version": "1.0.0",
  "is_active": true,
  "last_used_at": ISODate,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

---

## Notification Generation Triggers

### Automatic Triggers (Service Layer)

| Event | Method | Creates Notification For |
|-------|--------|-------------------------|
| Complaint created | `ComplaintService.create()` | - (none, citizen knows) |
| Status changed | `ComplaintService.change_status()` | Citizen (complaint.user_id) |
| Complaint assigned | `ComplaintService.assign()` | Staff (assigned_to) |
| Complaint completed | `ComplaintService.complete()` | Citizen |
| Complaint rejected | `ComplaintService.reject()` | Citizen |
| Duplicate marked | `ComplaintService.mark_duplicate()` | Citizen |
| Update added | `ComplaintService.add_update()` | Citizen (if visibility == 'public') |
| Like added | `FeedService.like()` | Complaint owner (optional) |

### Notification Content Templates

```python
NOTIFICATION_TEMPLATES = {
    "status_update": {
        "title": "Complaint Status Updated",
        "message": "Your complaint '{title}' is now {new_status}",
    },
    "assignment": {
        "title": "New Complaint Assigned",
        "message": "You have been assigned: '{title}'",
    },
    "completion": {
        "title": "Complaint Resolved",
        "message": "Your complaint '{title}' has been completed",
    },
    "rejection": {
        "title": "Complaint Rejected",
        "message": "Your complaint '{title}' was rejected: {reason}",
    },
    "duplicate": {
        "title": "Duplicate Complaint",
        "message": "Your complaint '{title}' is a duplicate of #{ref_number}",
    },
    "comment": {
        "title": "New Update on Your Complaint",
        "message": "{author} added an update to '{title}'",
    },
    "like": {
        "title": "New Like",
        "message": "Someone liked your complaint '{title}'",
    },
    "system": {
        "title": "{custom_title}",
        "message": "{custom_message}",
    }
}
```

---

## Service Abstraction

### NotificationService Interface
```python
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class NotificationPayload:
    user_id: ObjectId
    type: str
    title: str
    message: str
    complaint_id: Optional[ObjectId] = None
    metadata: dict = None
    push: bool = True  # Whether to send push

class NotificationProvider(ABC):
    """Abstract base for push notification providers"""
    
    @abstractmethod
    async def send_push(self, tokens: List[str], title: str, body: str, data: dict) -> dict:
        """Send push notification to device tokens"""
        pass
    
    @abstractmethod
    async def send_multicast(self, tokens: List[str], title: str, body: str, data: dict) -> dict:
        """Send to multiple tokens"""
        pass

class MockProvider(NotificationProvider):
    """Development provider - logs only"""
    async def send_push(self, tokens, title, body, data):
        print(f"[MOCK PUSH] To: {tokens}, Title: {title}, Body: {body}")
        return {"success": True, "sent": len(tokens)}
    
    async def send_multicast(self, tokens, title, body, data):
        return await self.send_push(tokens, title, body, data)

class FCMProvider(NotificationProvider):
    """Firebase Cloud Messaging - Phase 2 implementation"""
    async def send_push(self, tokens, title, body, data):
        # Implementation using firebase-admin
        pass

class APNSProvider(NotificationProvider):
    """Apple Push Notification Service - Phase 2 implementation"""
    async def send_push(self, tokens, title, body, data):
        # Implementation using apns2
        pass

class NotificationService:
    def __init__(
        self,
        repo: NotificationRepository,
        device_repo: DeviceTokenRepository,
        provider: NotificationProvider = None
    ):
        self.repo = repo
        self.device_repo = device_repo
        self.provider = provider or MockProvider()
    
    async def create_notification(self, payload: NotificationPayload) -> Notification:
        # 1. Create in-app notification
        notification = await self.repo.create(
            user_id=payload.user_id,
            complaint_id=payload.complaint_id,
            type=payload.type,
            title=payload.title,
            message=payload.message,
            metadata=payload.metadata or {}
        )
        
        # 2. Queue push notification if enabled
        if payload.push:
            await self._queue_push_notification(payload)
        
        return notification
    
    async def _queue_push_notification(self, payload: NotificationPayload):
        # Get active device tokens for user
        tokens = await self.device_repo.get_active_tokens(payload.user_id)
        if not tokens:
            return
        
        token_strings = [t.device_token for t in tokens]
        
        # Prepare push payload
        push_data = {
            "notification_id": str(payload.notification_id) if hasattr(payload, 'notification_id') else "",
            "type": payload.type,
            "complaint_id": str(payload.complaint_id) if payload.complaint_id else "",
            "deep_link": payload.metadata.get("deep_link") if payload.metadata else ""
        }
        
        # Send async (fire-and-forget with retry)
        asyncio.create_task(self._send_with_retry(token_strings, payload.title, payload.message, push_data))
    
    async def _send_with_retry(self, tokens, title, body, data, max_retries=3):
        for attempt in range(max_retries):
            try:
                if len(tokens) == 1:
                    await self.provider.send_push(tokens, title, body, data)
                else:
                    await self.provider.send_multicast(tokens, title, body, data)
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    # Log failure, don't raise
                    logger.error(f"Push failed after {max_retries} attempts: {e}")
                else:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    async def mark_read(self, notification_id: ObjectId, user_id: ObjectId) -> bool:
        return await self.repo.mark_read(notification_id, user_id)
    
    async def mark_all_read(self, user_id: ObjectId) -> int:
        return await self.repo.mark_all_read(user_id)
    
    async def get_unread_count(self, user_id: ObjectId) -> int:
        return await self.repo.count_unread(user_id)
```

---

## Device Token Management

### Registration (POST /notifications/devices)
```python
@router.post("/devices")
async def register_device(
    payload: DeviceTokenRequest,
    current_user: User = Depends(get_current_user),
    device_repo: DeviceTokenRepository = Depends()
):
    # Upsert device token
    await device_repo.upsert_token(
        user_id=current_user.id,
        device_token=payload.device_token,
        platform=payload.platform,
        device_id=payload.device_id,
        app_version=payload.app_version
    )
    return SuccessResponse(message="Device registered")
```

### Cleanup Strategy
- **Inactive tokens**: Mark `is_active=false` on push failure (invalid token)
- **Old tokens**: TTL-based cleanup (90 days inactive)
- **App update**: Re-register on version change

---

## In-App Notification API

### GET /notifications
**Query**: `page`, `page_size`, `is_read` (optional)
**Response**: Paginated notifications with complaint context

### GET /notifications/unread-count
**Response**: `{ "count": 5 }`

### PATCH /notifications/{id}/read
Marks single notification as read

### PATCH /notifications/read-all
Marks all user's notifications as read

---

## Delivery Guarantees

| Channel | Guarantee | Retry | Ordering |
|---------|-----------|-------|----------|
| In-app | At-least-once (DB write) | N/A | FIFO per user |
| Push | Best-effort | 3 retries exponential | Not guaranteed |

### Failure Handling
- **Push failure**: Log, don't block API response
- **Invalid token**: Mark inactive, don't retry
- **Provider down**: Queue in DB (future: message queue)
- **Rate limits**: Respect provider limits, batch sends

---

## Privacy & Security

### Data Minimization
- **No PII in push payload**: Only notification_id, type, complaint_id, deep_link
- **Message content**: Only in in-app notification (encrypted at rest)
- **Device tokens**: Encrypted at rest, transmitted via HTTPS

### Access Control
- Users only see their own notifications
- Organization staff see notifications for assigned complaints (via complaint updates)
- Admin sees all (audit)

### Rate Limiting
- Push notifications: Max 10/minute per user
- In-app: No limit (DB write)

---

## Testing Strategy

### Unit Tests
1. Template rendering with metadata
2. Push payload construction
3. Token filtering (active only)
4. Retry logic with backoff
5. Provider interface compliance

### Integration Tests
1. Status change → notification created
2. Assignment → staff notification
3. Completion → citizen notification
4. Device registration → token stored
5. Push sent on notification create (mock provider)

### Mock Provider Verification
```python
async def test_push_sent_on_status_change():
    mock_provider = MockProvider()
    service = NotificationService(repo, device_repo, mock_provider)
    
    await service.create_notification(NotificationPayload(
        user_id=user.id,
        type="status_update",
        title="Test",
        message="Test",
        complaint_id=complaint.id
    ))
    
    # Verify push was attempted
    assert mock_provider.send_called
    assert mock_provider.last_tokens == [user_device_token]
```

---

## Future Enhancements (Post-Phase 1)

1. **Message Queue**: Redis/RabbitMQ for reliable push delivery
2. **Provider Selection**: Per-platform (FCM for Android, APNS for iOS)
3. **Rich Notifications**: Images, actions, categories
4. **Scheduled Notifications**: Reminders, SLA warnings
5. **Broadcast**: Admin announcements to user segments
6. **Preferences**: User notification settings (email, push, in-app per type)
7. **Analytics**: Delivery rates, open rates, click-through