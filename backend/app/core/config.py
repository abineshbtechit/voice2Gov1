from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default development secret; production must never run with it.
_INSECURE_DEFAULT_SECRET = "dev-secret-key-change-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Voice2Gov API"
    app_version: str = "0.1.0"
    debug: bool = Field(default=False, description="Enable debug mode")
    environment: str = Field(default="development", description="Environment name")

    # Server
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")

    # MongoDB
    mongodb_uri: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection URI",
    )
    mongodb_database: str = Field(
        default="voice2gov",
        description="MongoDB database name",
    )
    mongodb_max_pool_size: int = Field(
        default=100, description="MongoDB max connection pool size"
    )
    mongodb_min_pool_size: int = Field(
        default=10, description="MongoDB min connection pool size"
    )
    mongodb_max_idle_time_ms: int = Field(
        default=30000, description="MongoDB max idle time in milliseconds"
    )
    mongodb_server_selection_timeout_ms: int = Field(
        default=5000, description="MongoDB server selection timeout"
    )

    # Security
    secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        description="Secret key for JWT signing",
    )
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(
        default=15, description="Access token expiration in minutes"
    )
    refresh_token_expire_days: int = Field(
        default=30, description="Refresh token expiration in days"
    )
    bcrypt_rounds: int = Field(default=12, ge=4, le=31, description="Bcrypt cost factor")

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8081"],
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = Field(
        default=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    )
    cors_allow_headers: list[str] = Field(
        default=["Authorization", "Content-Type", "X-Request-ID"]
    )

    # Rate Limiting (Phase 1: in-memory)
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests: int = Field(default=100)
    rate_limit_window_seconds: int = Field(default=60)

    # File Upload
    max_file_size_mb: int = Field(default=10)
    allowed_mime_types: list[str] = Field(
        default=["image/jpeg", "image/png", "image/webp", "image/heic"]
    )

    # Image storage (Phase 1.3.4)
    storage_provider: str = Field(
        default="local",
        description="Active storage provider: 'local' (dev/test) or 'memory' (tests).",
    )
    storage_local_path: str = Field(
        default="uploads", description="Root directory for the local storage provider"
    )
    storage_local_url: str = Field(
        default="http://localhost:8000/uploads",
        description="Base URL advertised for locally stored objects",
    )
    storage_signed_url_expiry_seconds: int = Field(
        default=3600, description="Expiry (seconds) for generated signed image URLs"
    )
    max_images_per_request: int = Field(
        default=5, gt=0, description="Maximum images accepted in one upload request"
    )
    max_evidence_size_mb: int = Field(default=10, gt=0, description="Evidence image size limit")
    max_progress_size_mb: int = Field(default=5, gt=0, description="Progress image size limit")
    max_completion_size_mb: int = Field(
        default=5, gt=0, description="Completion image size limit"
    )
    max_image_filename_length: int = Field(
        default=100, gt=0, description="Maximum sanitized filename stem length"
    )
    image_upload_rate_limit: int = Field(
        default=10, gt=0, description="Max image uploads per minute per user"
    )

    # Pagination
    default_page_size: int = Field(default=20)
    max_page_size: int = Field(default=100)

    # Priority Engine (Phase 1.4)
    priority_weight_community_engagement: float = Field(
        default=0.30, ge=0.0, le=1.0, description="Priority weight for community engagement"
    )
    priority_weight_severity: float = Field(
        default=0.40, ge=0.0, le=1.0, description="Priority weight for severity"
    )
    priority_weight_age: float = Field(
        default=0.20, ge=0.0, le=1.0, description="Priority weight for age"
    )
    priority_weight_organization_boost: float = Field(
        default=0.10, ge=0.0, le=1.0, description="Priority weight for organization boost"
    )
    priority_max_score: float = Field(
        default=100.0, gt=0.0, description="Maximum total priority score"
    )
    priority_engagement_multiplier: float = Field(
        default=1.0, ge=0.0, description="Points per like"
    )
    priority_max_engagement_score: float = Field(
        default=30.0, ge=0.0, description="Max normalized community engagement score"
    )
    priority_max_severity_score: float = Field(
        default=40.0, ge=0.0, description="Max normalized severity score"
    )
    priority_hours_to_max_age: float = Field(
        default=168.0, gt=0.0, description="Hours to reach max age score (168 = 1 week)"
    )
    priority_max_age_score: float = Field(
        default=20.0, ge=0.0, description="Max normalized age score"
    )
    priority_max_org_boost: float = Field(
        default=10.0, ge=0.0, description="Max normalized organization boost"
    )

    # OTP and Geocoding Providers
    otp_delivery_provider: str = Field(
        default="mock",
        description="Active OTP delivery provider: 'mock' (dev/test) or 'external' (sms/email gateway)",
    )
    geocoding_provider: str = Field(
        default="mock",
        description="Active geocoding provider: 'mock' (dev/test) or 'external' (gis/tiles)",
    )

    # Google SMTP Settings (Free Email Verification)
    smtp_host: str = Field(default="smtp.gmail.com", description="SMTP server hostname")
    smtp_port: int = Field(default=587, description="SMTP server port (587 TLS, 465 SSL)")
    smtp_user: str = Field(default="", description="Google/Gmail username (e.g. yourname@gmail.com)")
    smtp_password: str = Field(default="", description="Google 16-character App Password")
    smtp_from_email: str = Field(default="", description="Sender email address")
    smtp_from_name: str = Field(default="Voice2Gov Verification", description="Sender display name")
    smtp_use_tls: bool = Field(default=True, description="Enable STARTTLS for SMTP")

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")

    @model_validator(mode="after")
    def _fail_fast_on_unsafe_production_config(self) -> "Settings":
        """Refuse to start in production with unsafe configuration.

        Fails fast instead of silently running insecurely: an insecure default
        JWT secret lets anyone forge tokens, and debug mode exposes /docs and
        verbose error behaviour to the public internet.
        Mock providers must never run in production — they never deliver OTPs
        or resolve real addresses, so allowing them silently would mean the
        system appears to work while delivering no security or geocoding value.
        """
        if self.environment.strip().lower() != "production":
            return self
        if self.secret_key == _INSECURE_DEFAULT_SECRET or not self.secret_key.strip():
            raise ValueError(
                "SECRET_KEY must be set to a strong, environment-provided value in production"
            )
        if self.debug:
            raise ValueError("DEBUG must not be enabled in production")
        if self.otp_delivery_provider.strip().lower() == "mock":
            raise ValueError(
                "OTP_DELIVERY_PROVIDER must not be 'mock' in production; "
                "configure a real SMS/email gateway provider"
            )
        if self.geocoding_provider.strip().lower() == "mock":
            raise ValueError(
                "GEOCODING_PROVIDER must not be 'mock' in production; "
                "configure a real geocoding service provider"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
