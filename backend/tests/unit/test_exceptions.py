from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.exceptions.base import (
    AppException,
    BusinessLogicException,
    ConflictException,
    FileUploadException,
    ForbiddenException,
    NotFoundException,
    RateLimitException,
    UnauthorizedException,
    ValidationException,
)
from app.exceptions.handlers import register_exception_handlers


def create_test_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/test/app-exception")
    async def test_app_exception():
        raise AppException("Test error", "TEST_ERROR", 400)

    @app.get("/test/validation-exception")
    async def test_validation_exception():
        raise ValidationException("Validation failed", errors=[{"field": "email", "message": "Invalid email", "code": "INVALID_EMAIL"}])

    @app.get("/test/not-found")
    async def test_not_found():
        raise NotFoundException("User not found")

    @app.get("/test/conflict")
    async def test_conflict():
        raise ConflictException("Email already exists")

    @app.get("/test/unauthorized")
    async def test_unauthorized():
        raise UnauthorizedException("Invalid credentials")

    @app.get("/test/forbidden")
    async def test_forbidden():
        raise ForbiddenException("Access denied")

    @app.get("/test/rate-limit")
    async def test_rate_limit():
        raise RateLimitException("Too many requests", retry_after=60)

    @app.get("/test/business-logic")
    async def test_business_logic():
        raise BusinessLogicException("Invalid state transition")

    @app.get("/test/file-upload")
    async def test_file_upload():
        raise FileUploadException("File too large")

    return app


@pytest.fixture
def app():
    return create_test_app()


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestExceptionHandlers:
    @pytest.mark.asyncio
    async def test_app_exception(self, client):
        response = await client.get("/test/app-exception")
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["message"] == "Test error"
        assert data["error_code"] == "TEST_ERROR"

    @pytest.mark.asyncio
    async def test_validation_exception(self, client):
        response = await client.get("/test/validation-exception")
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "VALIDATION_ERROR"
        assert len(data["errors"]) == 1
        assert data["errors"][0]["field"] == "email"

    @pytest.mark.asyncio
    async def test_not_found_exception(self, client):
        response = await client.get("/test/not-found")
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "RESOURCE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_conflict_exception(self, client):
        response = await client.get("/test/conflict")
        assert response.status_code == 409
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "CONFLICT"

    @pytest.mark.asyncio
    async def test_unauthorized_exception(self, client):
        response = await client.get("/test/unauthorized")
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "UNAUTHORIZED"

    @pytest.mark.asyncio
    async def test_forbidden_exception(self, client):
        response = await client.get("/test/forbidden")
        assert response.status_code == 403
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "FORBIDDEN"

    @pytest.mark.asyncio
    async def test_rate_limit_exception(self, client):
        response = await client.get("/test/rate-limit")
        assert response.status_code == 429
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "RATE_LIMIT_EXCEEDED"
        assert data["details"]["retry_after"] == 60

    @pytest.mark.asyncio
    async def test_business_logic_exception(self, client):
        response = await client.get("/test/business-logic")
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "BUSINESS_LOGIC_ERROR"

    @pytest.mark.asyncio
    async def test_file_upload_exception(self, client):
        response = await client.get("/test/file-upload")
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "FILE_UPLOAD_ERROR"
