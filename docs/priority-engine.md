# Voice2Gov Priority Engine

## Overview
Configurable priority scoring system for complaints combining community engagement, severity, age, and organization-configured boost.

---

## Priority Score Formula

**Calculation Pipeline** (explicit step-by-step to avoid double-weighting ambiguity):

```
For each component:
  1. RAW VALUE          →  e.g., likes_count = 25
  2. NORMALIZE/CAP      →  min(25 × 1.0, 30) = 25
  3. APPLY WEIGHT       →  25 × 0.30 = 7.5  (weighted component)
  4. SUM WEIGHTED       →  7.5 + 12.8 + 1.71 + 0.0 = 22.01
  5. FINAL CAP          →  min(22.01, 100) = 22.0
```

**Formula**:
```
priority_score = min(
    (min(likes_count × engagement_multiplier, max_engagement_score) × weight_community) +
    ((severity_level / 5) × max_severity_score × weight_severity) +
    (min(hours_since_creation / hours_to_max_age × max_age_score, max_age_score) × weight_age) +
    (min(organization_priority_boost, max_org_boost) × weight_org_boost)
  , max_score)
```

**Maximum Score**: 100 (configurable via `priority.max_score`)

---

## Component Definitions

### 1. Community Engagement Score
**Source**: Complaint likes count (`likes_count` field on complaint document, denormalized)

**Pipeline**:
```
RAW: likes_count (integer, ≥0)
NORMALIZE/CAP: min(likes_count × engagement_multiplier, max_engagement_score)
WEIGHTED: normalized_value × weight_community
```
- **engagement_multiplier**: Points per like (default: 1.0)
- **max_engagement_score**: Cap on normalized value (default: 30)
- **weight_community**: Weight for this component (default: 0.30)

*Example*: 25 likes → RAW=25 → NORMALIZE=min(25×1.0, 30)=25 → WEIGHTED=25×0.30=7.5

### 2. Severity Score
**Source**: Category severity level (1-5)

**Pipeline**:
```
RAW: severity_level (integer 1-5)
NORMALIZE: (severity_level / 5) × max_severity_score
WEIGHTED: normalized_value × weight_severity
```
- **max_severity_score**: Maximum normalized contribution (default: 40)
- **weight_severity**: Weight for this component (default: 0.40)

*Example*: Severity 4 → RAW=4 → NORMALIZE=(4/5)×40=32 → WEIGHTED=32×0.40=12.8

### 3. Age Score
**Source**: Time since complaint creation

**Pipeline**:
```
RAW: hours_since_creation = (now - created_at) in hours
NORMALIZE/CAP: min(hours_since_creation / hours_to_max_age × max_age_score, max_age_score)
WEIGHTED: normalized_value × weight_age
```
- **hours_to_max_age**: Hours to reach max age score (default: 168 = 1 week)
- **max_age_score**: Maximum normalized contribution (default: 20)
- **weight_age**: Weight for this component (default: 0.20)

*Example*: 72 hours old → RAW=72 → NORMALIZE=min(72/168×20, 20)=8.57 → WEIGHTED=8.57×0.20=1.71

### 4. Organization Priority Boost
**Source**: Organization configuration per complaint (`organization_priority_boost` field)

**Pipeline**:
```
RAW: organization_priority_boost (float 0-100)
NORMALIZE/CAP: min(organization_priority_boost, max_org_boost)
WEIGHTED: normalized_value × weight_org_boost
```
- **max_org_boost**: Cap on normalized value (default: 10)
- **weight_org_boost**: Weight for this component (default: 0.10)

*Example*: Org boost 50 → RAW=50 → NORMALIZE=min(50, 10)=10 → WEIGHTED=10×0.10=1.0

---

## Default Weights (Configurable)

| Component | Weight | Default | Config Key |
|-----------|--------|---------|------------|
| Community Engagement | 0.30 | 30% | `priority.weights.community_engagement` |
| Severity | 0.40 | 40% | `priority.weights.severity` |
| Age | 0.20 | 20% | `priority.weights.age` |
| Organization Boost | 0.10 | 10% | `priority.weights.organization_boost` |

**Sum must equal 1.0** (validated on config update)

---

## Configuration Storage

### Admin Settings (Global Defaults)
```json
{
  "key": "priority.weights.community_engagement",
  "value": 0.30,
  "category": "priority"
}
{
  "key": "priority.weights.severity",
  "value": 0.40,
  "category": "priority"
}
{
  "key": "priority.weights.age",
  "value": 0.20,
  "category": "priority"
}
{
  "key": "priority.weights.organization_boost",
  "value": 0.10,
  "category": "priority"
}
{
  "key": "priority.max_score",
  "value": 100,
  "category": "priority"
}
{
  "key": "priority.engagement_multiplier",
  "value": 1.0,
  "category": "priority"
}
{
  "key": "priority.max_engagement_score",
  "value": 30,
  "category": "priority"
}
{
  "key": "priority.max_severity_score",
  "value": 40,
  "category": "priority"
}
{
  "key": "priority.hours_to_max_age",
  "value": 168,
  "category": "priority"
}
{
  "key": "priority.max_age_score",
  "value": 20,
  "category": "priority"
}
{
  "key": "priority.max_org_boost",
  "value": 10,
  "category": "priority"
}
```

### Organization Override (Future)
Organizations can override weights via `organizations.settings.priority_weights`:
```json
{
  "community_engagement": 0.25,
  "severity": 0.45,
  "age": 0.20,
  "organization_boost": 0.10
}
```
*Validation*: Sum must equal 1.0, values 0-1

---

## Calculation Architecture

### Where Calculation Happens
**Service Layer**: `PriorityService.calculate_priority(complaint)`

```python
class PriorityService:
    def __init__(self, settings_repo: AdminSettingsRepository):
        self.settings_repo = settings_repo
        self._weights_cache = None
        self._cache_ttl = 300  # 5 minutes
    
    async def calculate_priority(self, complaint: Complaint) -> PriorityBreakdown:
        weights = await self._get_weights(complaint.organization_id)
        
        # Community engagement
        likes = await self.like_repo.count_by_complaint(complaint.id)
        engagement_raw = min(likes * weights.engagement_multiplier, weights.max_engagement_score)
        engagement_score = engagement_raw * weights.community_engagement
        
        # Severity
        severity_raw = (complaint.severity_score / 5) * weights.max_severity_score
        severity_score = severity_raw * weights.severity
        
        # Age
        hours_old = (datetime.utcnow() - complaint.created_at).total_seconds() / 3600
        age_raw = min(hours_old / weights.hours_to_max_age * weights.max_age_score, weights.max_age_score)
        age_score = age_raw * weights.age
        
        # Org boost
        org_boost_raw = min(complaint.organization_priority_boost, weights.max_org_boost)
        org_boost_score = org_boost_raw * weights.organization_boost
        
        total = engagement_score + severity_score + age_score + org_boost_score
        total = min(total, weights.max_score)
        
        return PriorityBreakdown(
            priority_score=round(total, 1),
            community_engagement_score=round(engagement_score, 1),
            severity_score=round(severity_score, 1),
            age_score=round(age_score, 1),
            organization_priority_boost=round(org_boost_score, 1),
            weights=weights,
            max_score=weights.max_score
        )
```

### Caching Strategy
- **Weights**: Cached 5 minutes (invalidated on settings update)
- **Complaint Priority**: Not cached (changes with likes/age)
- **Batch Recalculation**: Background job every 15 minutes for active complaints

### Triggers for Recalculation
1. **Like/Unlike** → Immediate recalculation for that complaint
2. **New Complaint** → Calculate on creation
3. **Status Change** → Recalculate (age component changes)
4. **Org Boost Update** → Recalculate affected complaints
5. **Scheduled Job** → Batch recalc for all non-terminal complaints

---

## API Contract

### GET /complaints/{id}/priority
**Response**:
```json
{
  "success": true,
  "message": "Priority breakdown",
  "data": {
    "priority_score": 67.3,
    "breakdown": {
      "community_engagement_score": 22.5,
      "severity_score": 32.0,
      "age_score": 12.8,
      "organization_priority_boost": 0.0
    },
    "weights": {
      "community_engagement": 0.30,
      "severity": 0.40,
      "age": 0.20,
      "organization_boost": 0.10
    },
    "raw_components": {
      "likes_count": 25,
      "severity_level": 4,
      "hours_since_creation": 108,
      "org_boost_value": 0
    },
    "max_score": 100
  }
}
```

### GET /organizations/me/complaints/priority
**Query**: `page`, `page_size`, `min_score`, `status`
**Response**: Complaints sorted by `priority_score` descending

---

## Feed Sorting Integration

### Sort Options for GET /feed
| Sort | Order By | Description |
|------|----------|-------------|
| `priority` | `priority_score DESC, created_at DESC` | Highest priority first |
| `popular` | `community_engagement_score DESC, created_at DESC` | Most liked |
| `recent` | `created_at DESC` | Newest first |
| `nearby` | Geo distance, then `priority_score DESC` | Location-based |

### Priority in Feed Query
```python
# MongoDB aggregation for feed with priority sort
pipeline = [
    {"$match": {"visibility": "public", "status": {"$nin": ["REJECTED", "DUPLICATE", "CLOSED"]}}},
    {"$addFields": {
        "likes_count": {"$size": "$likes"},  # or lookup
        "hours_old": {"$divide": [{"$subtract": ["$$NOW", "$created_at"]}, 3600000]}
    }},
    {"$addFields": {
        "engagement_score": {"$min": [{"$multiply": ["$likes_count", 1.0]}, 30]},
        "severity_score": {"$multiply": [{"$divide": ["$severity_score", 5]}, 40]},
        "age_score": {"$min": [{"$multiply": [{"$divide": ["$hours_old", 168]}, 20]}, 20]},
        "org_boost_score": {"$min": ["$organization_priority_boost", 10]}
    }},
    {"$addFields": {
        "priority_score": {
            "$add": [
                {"$multiply": ["$engagement_score", 0.30]},
                {"$multiply": ["$severity_score", 0.40]},
                {"$multiply": ["$age_score", 0.20]},
                {"$multiply": ["$org_boost_score", 0.10]}
            ]
        }
    }},
    {"$sort": {"priority_score": -1}},
    {"$skip": 0}, {"$limit": 20}
]
```

---

## Configuration Management

### Admin API for Weights
```
PUT /admin/settings/priority.weights.community_engagement
Body: {"value": 0.35}
```
- Validates sum of all 4 weights = 1.0
- Invalidates cache on update
- Audit logged

### Organization Override API (Future)
```
PUT /organizations/{id}/priority-weights
Body: {"community_engagement": 0.25, "severity": 0.45, "age": 0.20, "organization_boost": 0.10}
```

---

## Testing Scenarios

### Unit Tests
1. **Weight Validation**: Sum = 1.0, each 0-1
2. **Engagement Cap**: 100 likes → max 30 (not 100)
3. **Severity Scaling**: Level 1=8, Level 5=40 (with defaults)
4. **Age Progression**: 0h=0, 168h=20, 336h=20 (cap)
5. **Org Boost Cap**: Boost 50 → max 10 contribution
6. **Total Cap**: All max → 100 (not 100+)
7. **Weight Changes**: Recalculation reflects new weights

### Integration Tests
1. **Like → Priority Update**: Like added, GET /priority reflects new score
2. **Feed Sort**: Priority sort returns highest first
3. **Org Override**: Org weights differ from global (when implemented)
4. **Batch Job**: Non-terminal complaints recalculated

### Edge Cases
1. **New Complaint**: 0 likes, 0 hours → score = severity only
2. **Terminal Complaint**: COMPLETED - still calculable but not in feed
3. **Negative Values**: Never (all components ≥ 0)
4. **Missing Category**: Default severity 3
5. **Config Reload**: Cache invalidation works

---

## Performance Considerations

### Indexes for Priority Queries
```javascript
// Complaints collection
{ "priority_score": -1 }                    // Priority feed sort
{ "organization_id": 1, "priority_score": -1, "status": 1 }  // Org priority queue
{ "department_id": 1, "priority_score": -1, "status": 1 }    // Dept priority queue
```

### Optimization
- **Denormalized priority_score** on complaint document (updated on triggers)
- **Aggregation pipeline** for feed avoids N+1 queries
- **Background job** updates scores for stale complaints (age component)
- **Materialized view** for org/dept priority queues (future)

---

## Ambiguities & Decisions

| Ambiguity | Decision | Rationale |
|-----------|----------|-----------|
| Real-time vs batch recalc | Hybrid: immediate for likes, batch for age | Likes are discrete events; age changes continuously |
| Org override in Phase 1 | No - global weights only | SRS doesn't specify org-level config |
| Negative weights | Not allowed (0-1) | Priority should only increase |
| Completed complaints in priority | Excluded from feed, calculable for history | Feed shows actionable items |
| Decimal precision | 1 decimal place | Sufficient for sorting |