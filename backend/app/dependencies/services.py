"""Shared service-provider dependencies.

Kept in a neutral module so both the API routes and the authentication
dependency can consume the same providers without importing each other.
"""

from typing import Any
from unittest.mock import MagicMock

from fastapi import Depends
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import settings
from app.db.database import get_database, get_database_optional
from app.repositories.admin_settings_repository import AdminSettingsRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.complaint_image_repository import ComplaintImageRepository
from app.repositories.complaint_like_repository import ComplaintLikeRepository
from app.repositories.account_verification_otp_repository import AccountVerificationOTPRepository
from app.repositories.complaint_repository import ComplaintRepository
from app.repositories.complaint_update_repository import ComplaintUpdateRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.device_token_repository import DeviceTokenRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.password_reset_otp_repository import PasswordResetOTPRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.account_verification_service import AccountVerificationService
from app.services.admin_service import AdminService
from app.services.category_service import CategoryService
from app.services.complaint_service import ComplaintService
from app.services.geocoding_provider import GeocodingProvider, MockGeocodingProvider
from app.services.geocoding_service import GeocodingService
from app.services.image_service import ImageService, build_image_service
from app.services.notification_provider import MockNotificationProvider, NotificationProvider
from app.services.notification_service import NotificationService
from app.services.organization_service import OrganizationService
from app.services.otp_provider import MockOTPDeliveryProvider, OTPDeliveryProvider
from app.services.password_recovery_service import PasswordRecoveryService
from app.services.priority_service import PriorityService
from app.services.token_service import RefreshTokenService
from app.services.user_service import UserService
from app.storage.base import StorageProvider
from app.storage.factory import create_storage_provider


def get_user_service(
    database: AsyncDatabase[Any] = Depends(get_database),
) -> UserService:
    """Build a :class:`UserService` bound to the request's database."""
    return UserService(UserRepository(database))


def get_refresh_token_service(
    database: AsyncDatabase[Any] = Depends(get_database),
    user_service: UserService = Depends(get_user_service),
) -> RefreshTokenService:
    """Build a :class:`RefreshTokenService` bound to the request's database."""
    return RefreshTokenService(RefreshTokenRepository(database), user_service)


_notification_provider: NotificationProvider | None = None


def get_notification_provider() -> NotificationProvider:
    """Return the process-wide push notification provider instance."""
    global _notification_provider
    if _notification_provider is None:
        _notification_provider = MockNotificationProvider()
    return _notification_provider


def reset_notification_provider() -> None:
    """Reset the cached notification provider (for tests)."""
    global _notification_provider
    _notification_provider = None


def get_notification_service(
    database: AsyncDatabase[Any] = Depends(get_database),
    provider: NotificationProvider = Depends(get_notification_provider),
) -> NotificationService:
    """Build a :class:`NotificationService` bound to the request's database."""
    return NotificationService(
        repo=NotificationRepository(database),
        device_repo=DeviceTokenRepository(database),
        provider=provider,
    )


def get_priority_service(
    database: AsyncDatabase[Any] = Depends(get_database),
) -> PriorityService:
    """Build a :class:`PriorityService` bound to the request's database."""
    return PriorityService(
        like_repo=ComplaintLikeRepository(database),
        settings_repo=AdminSettingsRepository(database),
    )


def get_complaint_service(
    database: AsyncDatabase[Any] = Depends(get_database),
    notification_service: NotificationService = Depends(get_notification_service),
    priority_service: PriorityService = Depends(get_priority_service),
) -> ComplaintService:
    """Build a :class:`ComplaintService` bound to the request's database."""
    like_repo = ComplaintLikeRepository(database)
    return ComplaintService(
        ComplaintRepository(database),
        CategoryRepository(database),
        DepartmentRepository(database),
        ComplaintUpdateRepository(database),
        ComplaintImageRepository(database),
        UserRepository(database),
        priority_service,
        like_repo=like_repo,
        notification_service=notification_service,
    )


def get_organization_service(
    database: AsyncDatabase[Any] = Depends(get_database),
) -> OrganizationService:
    """Build an :class:`OrganizationService` bound to the request's database."""
    return OrganizationService(
        org_repo=OrganizationRepository(database),
        dept_repo=DepartmentRepository(database),
        user_repo=UserRepository(database),
        complaint_repo=ComplaintRepository(database),
        audit_repo=AuditLogRepository(database),
    )


def get_category_service(
    database: AsyncDatabase[Any] = Depends(get_database),
) -> CategoryService:
    """Build a :class:`CategoryService` bound to the request's database."""
    return CategoryService(
        category_repo=CategoryRepository(database),
        dept_repo=DepartmentRepository(database),
        org_repo=OrganizationRepository(database),
        audit_repo=AuditLogRepository(database),
    )


def get_admin_service(
    database: AsyncDatabase[Any] | None = Depends(get_database_optional),
) -> AdminService:
    """Build an :class:`AdminService` bound to the request's database."""
    if database is None:
        dummy_mock: Any = MagicMock()
        async def dummy_zero(*args: Any, **kwargs: Any) -> int:
            return 0
        async def dummy_aggregates(*args: Any, **kwargs: Any) -> tuple[dict[str, int], float, float]:
            return ({}, 0.0, 1.0)
        dummy_mock.count_all = dummy_zero
        dummy_mock.get_dashboard_aggregates = dummy_aggregates
        return AdminService(
            user_repo=dummy_mock,
            org_repo=dummy_mock,
            dept_repo=dummy_mock,
            complaint_repo=dummy_mock,
            settings_repo=dummy_mock,
            audit_repo=dummy_mock,
        )
    priority_service = PriorityService(
        like_repo=ComplaintLikeRepository(database),
        settings_repo=AdminSettingsRepository(database),
    )
    return AdminService(
        user_repo=UserRepository(database),
        org_repo=OrganizationRepository(database),
        dept_repo=DepartmentRepository(database),
        complaint_repo=ComplaintRepository(database),
        settings_repo=AdminSettingsRepository(database),
        audit_repo=AuditLogRepository(database),
        priority_service=priority_service,
    )


_storage_provider: StorageProvider | None = None


def get_storage_provider() -> StorageProvider:
    """Return the process-wide storage provider (built lazily from settings)."""
    global _storage_provider
    if _storage_provider is None:
        _storage_provider = create_storage_provider(settings)
    return _storage_provider


def reset_storage_provider() -> None:
    """Clear the cached storage provider (for tests)."""
    global _storage_provider
    _storage_provider = None


def get_image_service(
    database: AsyncDatabase[Any] = Depends(get_database),
    storage: StorageProvider = Depends(get_storage_provider),
) -> ImageService:
    """Build an :class:`ImageService` bound to the request's database and storage."""
    return build_image_service(
        ComplaintImageRepository(database),
        ComplaintRepository(database),
        storage,
        settings,
    )


_otp_provider: OTPDeliveryProvider | None = None


def get_otp_delivery_provider() -> OTPDeliveryProvider:
    """Return the process-wide OTP delivery provider."""
    global _otp_provider
    if _otp_provider is None:
        _otp_provider = MockOTPDeliveryProvider()
    return _otp_provider


def reset_otp_delivery_provider() -> None:
    """Reset the cached OTP provider (for tests)."""
    global _otp_provider
    _otp_provider = None


def get_password_recovery_service(
    database: AsyncDatabase[Any] = Depends(get_database),
    provider: OTPDeliveryProvider = Depends(get_otp_delivery_provider),
) -> PasswordRecoveryService:
    """Build a :class:`PasswordRecoveryService`."""
    return PasswordRecoveryService(
        otp_repo=PasswordResetOTPRepository(database),
        user_repo=UserRepository(database),
        delivery_provider=provider,
        token_repo=RefreshTokenRepository(database),
    )


_geocoding_provider: GeocodingProvider | None = None


def get_geocoding_provider() -> GeocodingProvider:
    """Return the process-wide geocoding provider."""
    global _geocoding_provider
    if _geocoding_provider is None:
        _geocoding_provider = MockGeocodingProvider()
    return _geocoding_provider


def reset_geocoding_provider() -> None:
    """Reset the cached geocoding provider (for tests)."""
    global _geocoding_provider
    _geocoding_provider = None


def get_geocoding_service(
    provider: GeocodingProvider = Depends(get_geocoding_provider),
) -> GeocodingService:
    """Build a :class:`GeocodingService`."""
    return GeocodingService(provider=provider)


def get_account_verification_service(
    database: AsyncDatabase[Any] = Depends(get_database),
    token_service: RefreshTokenService = Depends(get_refresh_token_service),
) -> AccountVerificationService:
    """Build an :class:`AccountVerificationService`."""
    return AccountVerificationService(
        user_repo=UserRepository(database),
        otp_repo=AccountVerificationOTPRepository(database),
        token_service=token_service,
    )

