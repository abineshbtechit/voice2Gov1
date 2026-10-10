"""Unit tests for Priority Engine calculation (Phase 1.4, CMP-12)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.exceptions.base import ValidationException
from app.repositories.complaint_like_repository import ComplaintLikeRepository
from app.services.priority_service import PriorityService


class TestPriorityServiceUnit:
    """Test priority engine calculation pipelines, weighting, caps, and determinism."""

    @pytest.fixture
    def default_settings(self) -> Settings:
        return Settings(
            priority_weight_community_engagement=0.30,
            priority_weight_severity=0.40,
            priority_weight_age=0.20,
            priority_weight_organization_boost=0.10,
            priority_max_score=100.0,
            priority_engagement_multiplier=1.0,
            priority_max_engagement_score=30.0,
            priority_max_severity_score=40.0,
            priority_hours_to_max_age=168.0,
            priority_max_age_score=20.0,
            priority_max_org_boost=10.0,
        )

    @pytest.mark.asyncio
    async def test_invalid_weights_sum_fails_closed(self) -> None:
        bad_settings = Settings(
            priority_weight_community_engagement=0.40,
            priority_weight_severity=0.40,
            priority_weight_age=0.20,
            priority_weight_organization_boost=0.20,  # Sum = 1.20
        )
        service = PriorityService(settings=bad_settings)
        with pytest.raises(ValidationException) as exc:
            await service.get_weights()
        assert exc.value.error_code == "INVALID_WEIGHT_CONFIGURATION"


    @pytest.mark.asyncio
    async def test_zero_likes_and_zero_boost(self, default_settings: Settings) -> None:
        service = PriorityService(settings=default_settings)
        now = datetime.now(UTC)
        complaint = {
            "_id": "507f1f77bcf86cd799439011",
            "likes_count": 0,
            "severity_score": 1,
            "created_at": now,
            "organization_priority_boost": 0.0,
        }
        res = await service.calculate_priority(complaint, reference_time=now)
        # Engagement: 0 * 0.3 = 0.0
        # Severity: (1/5) * 40 * 0.4 = 8 * 0.4 = 3.2
        # Age: 0 * 0.2 = 0.0
        # Org boost: 0 * 0.1 = 0.0
        # Total: 3.2
        assert res.priority_score == 3.2
        assert res.breakdown.community_engagement_score == 0.0
        assert res.breakdown.severity_score == 3.2
        assert res.breakdown.age_score == 0.0
        assert res.breakdown.organization_priority_boost == 0.0

    @pytest.mark.asyncio
    async def test_engagement_calculation_and_cap(self, default_settings: Settings) -> None:
        service = PriorityService(settings=default_settings)
        now = datetime.now(UTC)
        # 100 likes: normalized = min(100 * 1.0, 30.0) = 30.0 -> weighted = 30.0 * 0.3 = 9.0
        complaint = {
            "_id": "507f1f77bcf86cd799439011",
            "likes_count": 100,
            "severity_score": 5,
            "created_at": now,
            "organization_priority_boost": 0.0,
        }
        res = await service.calculate_priority(complaint, reference_time=now)
        assert res.breakdown.community_engagement_score == 9.0
        assert res.raw_components.likes_count == 100

    @pytest.mark.asyncio
    async def test_severity_level_calculation(self, default_settings: Settings) -> None:
        service = PriorityService(settings=default_settings)
        now = datetime.now(UTC)
        # Severity 4: (4/5) * 40 = 32.0 -> weighted = 32.0 * 0.4 = 12.8
        complaint = {
            "_id": "507f1f77bcf86cd799439011",
            "likes_count": 0,
            "severity_score": 4,
            "created_at": now,
            "organization_priority_boost": 0.0,
        }
        res = await service.calculate_priority(complaint, reference_time=now)
        assert res.breakdown.severity_score == 12.8

    @pytest.mark.asyncio
    async def test_age_calculation_and_cap(self, default_settings: Settings) -> None:
        service = PriorityService(settings=default_settings)
        now = datetime.now(UTC)

        # 72 hours old:
        # min(72 / 168 * 20, 20) = 8.5714 -> weighted = 8.5714 * 0.20 = 1.714 -> 1.7
        c1 = {
            "_id": "507f1f77bcf86cd799439011",
            "likes_count": 0,
            "severity_score": 1,
            "created_at": now - timedelta(hours=72),
            "organization_priority_boost": 0.0,
        }
        res1 = await service.calculate_priority(c1, reference_time=now)
        assert res1.breakdown.age_score == 1.7

        # 300 hours old (> 168 cap):
        # min(300 / 168 * 20, 20) = 20.0 -> weighted = 20.0 * 0.20 = 4.0
        c2 = {
            "_id": "507f1f77bcf86cd799439011",
            "likes_count": 0,
            "severity_score": 1,
            "created_at": now - timedelta(hours=300),
            "organization_priority_boost": 0.0,
        }
        res2 = await service.calculate_priority(c2, reference_time=now)
        assert res2.breakdown.age_score == 4.0

    @pytest.mark.asyncio
    async def test_org_boost_calculation_and_cap(self, default_settings: Settings) -> None:
        service = PriorityService(settings=default_settings)
        now = datetime.now(UTC)

        # org boost 5: min(5, 10) = 5.0 -> weighted = 5.0 * 0.10 = 0.5
        c1 = {
            "_id": "507f1f77bcf86cd799439011",
            "likes_count": 0,
            "severity_score": 1,
            "created_at": now,
            "organization_priority_boost": 5.0,
        }
        res1 = await service.calculate_priority(c1, reference_time=now)
        assert res1.breakdown.organization_priority_boost == 0.5

        # org boost 50 (> 10 cap): min(50, 10) = 10.0 -> weighted = 10.0 * 0.10 = 1.0
        c2 = {
            "_id": "507f1f77bcf86cd799439011",
            "likes_count": 0,
            "severity_score": 1,
            "created_at": now,
            "organization_priority_boost": 50.0,
        }
        res2 = await service.calculate_priority(c2, reference_time=now)
        assert res2.breakdown.organization_priority_boost == 1.0

    @pytest.mark.asyncio
    async def test_full_weighted_pipeline_example_from_spec(self, default_settings: Settings) -> None:
        """Verify the exact example calculation from docs/priority-engine.md §8:

        likes_count = 25 -> min(25*1.0, 30) = 25 -> 25 * 0.30 = 7.5
        severity = 4 -> (4/5)*40 = 32 -> 32 * 0.40 = 12.8
        age = 72h -> min(72/168*20, 20) = 8.5714 -> 8.5714 * 0.20 = 1.714
        org_boost = 0 -> 0.0
        Total = 7.5 + 12.8 + 1.714 + 0 = 22.014 -> rounded = 22.0
        """
        service = PriorityService(settings=default_settings)
        now = datetime.now(UTC)
        complaint = {
            "_id": "507f1f77bcf86cd799439011",
            "likes_count": 25,
            "severity_score": 4,
            "created_at": now - timedelta(hours=72),
            "organization_priority_boost": 0.0,
        }
        res = await service.calculate_priority(complaint, reference_time=now)
        assert res.breakdown.community_engagement_score == 7.5
        assert res.breakdown.severity_score == 12.8
        assert res.breakdown.age_score == 1.7
        assert res.breakdown.organization_priority_boost == 0.0
        assert res.priority_score == 22.0

    @pytest.mark.asyncio
    async def test_maximum_score_cap(self, default_settings: Settings) -> None:
        """Even with all components maxed, score cannot exceed max_score (100)."""
        service = PriorityService(settings=default_settings)
        now = datetime.now(UTC)
        complaint = {
            "_id": "507f1f77bcf86cd799439011",
            "likes_count": 9999,
            "severity_score": 5,
            "created_at": now - timedelta(days=365),
            "organization_priority_boost": 9999.0,
        }
        res = await service.calculate_priority(complaint, reference_time=now)
        # Max scores:
        # Eng: 30 * 0.30 = 9.0
        # Sev: 40 * 0.40 = 16.0
        # Age: 20 * 0.20 = 4.0
        # Org: 10 * 0.10 = 1.0
        # Total = 30.0 <= 100.0
        assert res.priority_score <= 100.0

    @pytest.mark.asyncio
    async def test_deterministic_calculation(self, default_settings: Settings) -> None:
        service = PriorityService(settings=default_settings)
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        complaint = {
            "_id": "507f1f77bcf86cd799439011",
            "likes_count": 15,
            "severity_score": 3,
            "created_at": now - timedelta(hours=24),
            "organization_priority_boost": 2.5,
        }
        r1 = await service.calculate_priority(complaint, reference_time=now)
        r2 = await service.calculate_priority(complaint, reference_time=now)
        assert r1.priority_score == r2.priority_score
        assert r1.breakdown.community_engagement_score == r2.breakdown.community_engagement_score
        assert r1.breakdown.severity_score == r2.breakdown.severity_score
        assert r1.breakdown.age_score == r2.breakdown.age_score

    @pytest.mark.asyncio
    async def test_like_repo_integration(self, default_settings: Settings) -> None:
        like_repo = AsyncMock(spec=ComplaintLikeRepository)
        like_repo.count_by_complaint.return_value = 18

        service = PriorityService(like_repo=like_repo, settings=default_settings)
        now = datetime.now(UTC)
        complaint = {
            "_id": "507f1f77bcf86cd799439011",
            "likes_count": 0,  # Denormalized is 0, but repo has 18
            "severity_score": 1,
            "created_at": now,
            "organization_priority_boost": 0.0,
        }
        res = await service.calculate_priority(complaint, reference_time=now)
        assert res.raw_components.likes_count == 18
        # 18 * 1.0 = 18 -> 18 * 0.3 = 5.4
        assert res.breakdown.community_engagement_score == 5.4

    @pytest.mark.asyncio
    async def test_admin_settings_repository_dynamic_configuration(self) -> None:
        """Verify PriorityService loads weights and thresholds dynamically from AdminSettingsRepository."""
        from tests.fakes import FakeAdminSettingsRepository

        settings_repo = FakeAdminSettingsRepository()
        # Custom weights summing to 1.0
        await settings_repo.set_setting("priority.weights.community_engagement", 0.50)
        await settings_repo.set_setting("priority.weights.severity", 0.30)
        await settings_repo.set_setting("priority.weights.age", 0.10)
        await settings_repo.set_setting("priority.weights.organization_boost", 0.10)
        await settings_repo.set_setting("priority.max_score", 120.0)

        service = PriorityService(settings_repo=settings_repo)
        weights = await service.get_weights()
        assert weights.community_engagement == 0.50
        assert weights.severity == 0.30
        assert weights.age == 0.10
        assert weights.organization_boost == 0.10

        cfg = await service.get_effective_config()
        assert cfg["priority.max_score"] == 120.0

    @pytest.mark.asyncio
    async def test_admin_settings_invalid_weights_fail_closed(self) -> None:
        """Invalid weights in admin_settings raise ValidationException(INVALID_WEIGHT_CONFIGURATION)."""
        from tests.fakes import FakeAdminSettingsRepository

        settings_repo = FakeAdminSettingsRepository()
        # Invalid weights summing to 1.25
        await settings_repo.set_setting("priority.weights.community_engagement", 0.50)
        await settings_repo.set_setting("priority.weights.severity", 0.50)
        await settings_repo.set_setting("priority.weights.age", 0.15)
        await settings_repo.set_setting("priority.weights.organization_boost", 0.10)

        service = PriorityService(settings_repo=settings_repo)
        with pytest.raises(ValidationException) as exc:
            await service.get_weights()
        assert exc.value.error_code == "INVALID_WEIGHT_CONFIGURATION"

    @pytest.mark.asyncio
    async def test_cache_and_invalidation(self) -> None:
        """Verify cache returns cached config until invalidated."""
        from tests.fakes import FakeAdminSettingsRepository

        settings_repo = FakeAdminSettingsRepository()
        await settings_repo.set_setting("priority.weights.community_engagement", 0.30)
        await settings_repo.set_setting("priority.weights.severity", 0.40)
        await settings_repo.set_setting("priority.weights.age", 0.20)
        await settings_repo.set_setting("priority.weights.organization_boost", 0.10)

        service = PriorityService(settings_repo=settings_repo)
        w1 = await service.get_weights()
        assert w1.community_engagement == 0.30

        # Change in repo without invalidating service cache
        await settings_repo.set_setting("priority.weights.community_engagement", 0.35)
        await settings_repo.set_setting("priority.weights.severity", 0.35)
        w2 = await service.get_weights()
        assert w2.community_engagement == 0.30  # Still cached

        # Invalidate cache
        service.invalidate_cache()
        w3 = await service.get_weights()
        assert w3.community_engagement == 0.35
        assert w3.severity == 0.35

