import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


class TestSettings:
    def test_default_settings(self):
        settings = Settings()
        assert settings.app_name == "Voice2Gov API"
        assert settings.app_version == "0.1.0"
        assert settings.debug is False
        assert settings.environment == "development"
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000

    def test_mongodb_settings(self):
        settings = Settings()
        assert settings.mongodb_uri == "mongodb://localhost:27017"
        assert settings.mongodb_database == "voice2gov"
        assert settings.mongodb_max_pool_size == 100
        assert settings.mongodb_min_pool_size == 10

    def test_security_settings(self):
        settings = Settings()
        assert settings.algorithm == "HS256"
        assert settings.access_token_expire_minutes == 15
        assert settings.refresh_token_expire_days == 30
        assert settings.bcrypt_rounds == 12

    def test_cors_settings(self):
        settings = Settings()
        assert "http://localhost:3000" in settings.cors_origins
        assert "http://localhost:8081" in settings.cors_origins
        assert settings.cors_allow_credentials is True

    def test_rate_limit_settings(self):
        settings = Settings()
        assert settings.rate_limit_enabled is True
        assert settings.rate_limit_requests == 100
        assert settings.rate_limit_window_seconds == 60

    def test_file_upload_settings(self):
        settings = Settings()
        assert settings.max_file_size_mb == 10
        assert "image/jpeg" in settings.allowed_mime_types
        assert "image/png" in settings.allowed_mime_types

    def test_pagination_settings(self):
        settings = Settings()
        assert settings.default_page_size == 20
        assert settings.max_page_size == 100

    def test_settings_caching(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2


class TestSettingsValidation:
    def test_invalid_port(self):
        with pytest.raises(ValidationError):
            Settings(port=99999)

    def test_invalid_bcrypt_rounds(self):
        with pytest.raises(ValidationError):
            Settings(bcrypt_rounds=3)
