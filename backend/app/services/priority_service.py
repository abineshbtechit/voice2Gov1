"""Priority calculation service (Phase 1.4).

Implements the configurable priority scoring engine combining:
1. Community Engagement (likes)
2. Severity (category severity 1-5)
3. Age (time since creation)
4. Organization Boost

Authoritative specification: docs/priority-engine.md, docs/database-schema.md §12.
"""

from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings, get_settings
from app.exceptions.base import ValidationException
from app.repositories.admin_settings_repository import AdminSettingsRepository
from app.repositories.complaint_like_repository import ComplaintLikeRepository
from app.schemas.complaint import (
    PriorityBreakdownComponents,
    PriorityBreakdownData,
    PriorityBreakdownWeights,
    PriorityRawComponents,
)


class PriorityService:
    """Calculates deterministic complaint priority scores and breakdowns."""

    def __init__(
        self,
        like_repo: ComplaintLikeRepository | None = None,
        settings_repo: AdminSettingsRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._like_repo = like_repo
        self._settings_repo = settings_repo
        self._settings = settings or get_settings()
        self._cached_config: dict[str, Any] | None = None
        self._cache_time: datetime | None = None
        self._cache_ttl_seconds = 300.0  # 5 minutes per docs/priority-engine.md

    def invalidate_cache(self) -> None:
        """Invalidate the in-memory priority configuration cache."""
        self._cached_config = None
        self._cache_time = None

    async def get_effective_config(self) -> dict[str, Any]:
        """Retrieve dynamic configuration from admin_settings with fallback to static settings.

        Caches the config dictionary for up to 5 minutes (_cache_ttl_seconds).
        """
        now = datetime.now(UTC)
        if (
            self._cached_config is not None
            and self._cache_time is not None
            and (now - self._cache_time).total_seconds() < self._cache_ttl_seconds
        ):
            return self._cached_config

        # Base default values from static settings
        config: dict[str, Any] = {
            "priority.weights.community_engagement": self._settings.priority_weight_community_engagement,
            "priority.weights.severity": self._settings.priority_weight_severity,
            "priority.weights.age": self._settings.priority_weight_age,
            "priority.weights.organization_boost": self._settings.priority_weight_organization_boost,
            "priority.max_score": self._settings.priority_max_score,
            "priority.engagement_multiplier": self._settings.priority_engagement_multiplier,
            "priority.max_engagement_score": self._settings.priority_max_engagement_score,
            "priority.max_severity_score": self._settings.priority_max_severity_score,
            "priority.hours_to_max_age": self._settings.priority_hours_to_max_age,
            "priority.max_age_score": self._settings.priority_max_age_score,
            "priority.max_org_boost": self._settings.priority_max_org_boost,
        }

        # Override from admin_settings repository if present
        if self._settings_repo is not None:
            db_settings = await self._settings_repo.get_settings_by_category("priority")
            for key, val in db_settings.items():
                if val is not None:
                    config[key] = val

        self._cached_config = config
        self._cache_time = now
        return config

    async def get_weights(self) -> PriorityBreakdownWeights:
        """Retrieve authoritative priority weights from admin_settings (with fallback).

        Validates that weights sum to exactly 1.0 (within epsilon tolerance).
        """
        config = await self.get_effective_config()
        w_comm = float(config["priority.weights.community_engagement"])
        w_sev = float(config["priority.weights.severity"])
        w_age = float(config["priority.weights.age"])
        w_org = float(config["priority.weights.organization_boost"])

        total_weight = w_comm + w_sev + w_age + w_org
        if abs(total_weight - 1.0) > 1e-6:
            raise ValidationException(
                f"Priority weights must sum to 1.0, got {total_weight:.4f}",
                error_code="INVALID_WEIGHT_CONFIGURATION",
            )

        return PriorityBreakdownWeights(
            community_engagement=w_comm,
            severity=w_sev,
            age=w_age,
            organization_boost=w_org,
        )

    async def calculate_priority(
        self,
        complaint: dict[str, Any],
        reference_time: datetime | None = None,
    ) -> PriorityBreakdownData:
        """Calculate the priority breakdown for a complaint document.

        Formula per docs/priority-engine.md:
        1. Community Engagement:
           RAW: unique likes_count
           NORMALIZE/CAP: min(likes_count * engagement_multiplier, max_engagement_score)
           WEIGHTED: normalized_value * weight_community
        2. Severity:
           RAW: severity_level (1-5)
           NORMALIZE: (severity_level / 5) * max_severity_score
           WEIGHTED: normalized_value * weight_severity
        3. Age:
           RAW: hours_since_creation = (now - created_at) in hours
           NORMALIZE/CAP: min(hours_since_creation / hours_to_max_age * max_age_score, max_age_score)
           WEIGHTED: normalized_value * weight_age
        4. Organization Boost:
           RAW: organization_priority_boost (>= 0)
           NORMALIZE/CAP: min(organization_priority_boost, max_org_boost)
           WEIGHTED: normalized_value * weight_org_boost

        Total = min(sum of weighted components, max_score)
        """
        weights = await self.get_weights()
        config = await self.get_effective_config()
        now = reference_time or datetime.now(UTC)

        # 1. Community Engagement
        likes_count = await self._get_likes_count(complaint)
        engagement_multiplier = float(config["priority.engagement_multiplier"])
        max_engagement_score = float(config["priority.max_engagement_score"])
        engagement_raw = min(likes_count * engagement_multiplier, max_engagement_score)
        engagement_weighted = engagement_raw * weights.community_engagement

        # 2. Severity
        severity_level = int(complaint.get("severity_score", 1))
        severity_level = max(1, min(5, severity_level))
        max_severity_score = float(config["priority.max_severity_score"])
        severity_raw = (severity_level / 5.0) * max_severity_score
        severity_weighted = severity_raw * weights.severity

        # 3. Age
        created_at = complaint.get("created_at")
        if isinstance(created_at, datetime):
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
        else:
            created_at = now

        hours_since_creation = max(0.0, (now - created_at).total_seconds() / 3600.0)
        hours_to_max_age = float(config["priority.hours_to_max_age"])
        max_age_score = float(config["priority.max_age_score"])

        if hours_to_max_age > 0:
            age_normalized = (hours_since_creation / hours_to_max_age) * max_age_score
            age_raw = min(age_normalized, max_age_score)
        else:
            age_raw = 0.0
        age_weighted = age_raw * weights.age

        # 4. Organization Boost
        org_boost_val = float(complaint.get("organization_priority_boost", 0.0) or 0.0)
        org_boost_val = max(0.0, org_boost_val)
        max_org_boost = float(config["priority.max_org_boost"])
        org_boost_raw = min(org_boost_val, max_org_boost)
        org_boost_weighted = org_boost_raw * weights.organization_boost

        # Sum & Cap
        total = engagement_weighted + severity_weighted + age_weighted + org_boost_weighted
        max_score = float(config["priority.max_score"])
        final_score = min(total, max_score)

        return PriorityBreakdownData(
            priority_score=round(final_score, 1),
            breakdown=PriorityBreakdownComponents(
                community_engagement_score=round(engagement_weighted, 1),
                severity_score=round(severity_weighted, 1),
                age_score=round(age_weighted, 1),
                organization_priority_boost=round(org_boost_weighted, 1),
            ),
            weights=weights,
            raw_components=PriorityRawComponents(
                likes_count=likes_count,
                severity_level=severity_level,
                hours_since_creation=round(hours_since_creation, 2),
                org_boost_value=round(org_boost_val, 2),
            ),
            max_score=round(max_score, 1),
        )

    async def _get_likes_count(self, complaint: dict[str, Any]) -> int:
        """Resolve authoritative like count: prefer repository count, fallback to denormalized likes_count."""
        if self._like_repo is not None:
            cid = complaint.get("_id")
            if cid is not None:
                try:
                    count = await self._like_repo.count_by_complaint(cid)
                    if count > 0:
                        return count
                except Exception:
                    pass
        return int(complaint.get("likes_count", 0) or 0)

