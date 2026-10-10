from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Service is healthy"
        assert data["data"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_ready_endpoint_success(self, client):
        with patch("app.db.database.db_manager.ping", new_callable=AsyncMock) as mock_ping:
            mock_ping.return_value = True
            response = await client.get("/api/v1/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "Service is ready"
            assert data["data"]["status"] == "ready"
            assert data["data"]["mongodb"] == "connected"

    @pytest.mark.asyncio
    async def test_ready_endpoint_failure(self, client):
        with patch("app.db.database.db_manager.ping", new_callable=AsyncMock) as mock_ping:
            mock_ping.return_value = False
            response = await client.get("/api/v1/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["success"] is False
            assert data["error_code"] == "SERVICE_NOT_READY"

    @pytest.mark.asyncio
    async def test_ready_endpoint_exception(self, client):
        with patch("app.db.database.db_manager.ping", new_callable=AsyncMock) as mock_ping:
            mock_ping.side_effect = Exception("Connection failed")
            response = await client.get("/api/v1/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["success"] is False
            assert data["error_code"] == "SERVICE_NOT_READY"


class TestDocumentationEndpoints:
    @pytest.mark.asyncio
    async def test_root_endpoint_advertises_docs(self, client):
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Voice2Gov API"
        assert "version" in data
        assert data.get("docs") == "/docs"

    @pytest.mark.asyncio
    async def test_docs_endpoint_returns_swagger_ui_html(self, client):
        response = await client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "swagger-ui" in response.text.lower()

    @pytest.mark.asyncio
    async def test_openapi_json_returns_schema(self, client):
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    @pytest.mark.asyncio
    async def test_redoc_endpoint_returns_html(self, client):
        response = await client.get("/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_production_environment_disables_documentation_routes(self):
        from httpx import ASGITransport

        from app.core.config import Settings

        prod_settings = Settings(
            environment="production",
            debug=False,
            secret_key="a" * 32,
            otp_delivery_provider="external",
            geocoding_provider="external",
        )
        with patch("app.main.settings", prod_settings):
            prod_app = create_app()
            async with AsyncClient(
                transport=ASGITransport(app=prod_app),
                base_url="http://test",
            ) as prod_client:
                # Root should not advertise /docs in production
                r_root = await prod_client.get("/")
                assert r_root.status_code == 200
                assert "docs" not in r_root.json()

                # /docs, /redoc, and /openapi.json must return 404
                r_docs = await prod_client.get("/docs")
                assert r_docs.status_code == 404

                r_redoc = await prod_client.get("/redoc")
                assert r_redoc.status_code == 404

                r_openapi = await prod_client.get("/openapi.json")
                assert r_openapi.status_code == 404
