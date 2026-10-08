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
