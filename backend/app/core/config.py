from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Pagination
    default_page_size: int = Field(default=20)
    max_page_size: int = Field(default=100)

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
