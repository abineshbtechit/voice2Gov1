from collections.abc import AsyncGenerator, Iterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.db.database import close_database, db_manager, init_database
from app.main import create_app
from app.middleware.rate_limit import (
    disable_rate_limiting,
    enable_rate_limiting,
    reset_all_rate_limiters,
)


@pytest.fixture(scope="session")
def app() -> FastAPI:
    return create_app()


@pytest_asyncio.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client backed by a live database connection."""
    await init_database()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await close_database()


@pytest.fixture(autouse=True)
def reset_db_manager() -> Iterator[None]:
    db_manager._client = None
    db_manager._database = None
    yield
    db_manager._client = None
    db_manager._database = None


@pytest.fixture(autouse=True)
def reset_rate_limiters() -> Iterator[None]:
    """Reset rate limiters between tests to avoid cross-test contamination."""
    reset_all_rate_limiters()
    yield
    reset_all_rate_limiters()


@pytest.fixture
def enable_rate_limiting_for_tests() -> Iterator[None]:
    """Enable rate limiting for tests that need it (e.g., security tests)."""
    print("DEBUG CONFTEST FIXTURE: enable_rate_limiting_for_tests SETUP")
    enable_rate_limiting()
    print("DEBUG CONFTEST: rate limiting enabled", flush=True)
    yield
    print("DEBUG CONFTEST FIXTURE: enable_rate_limiting_for_tests TEARDOWN", flush=True)
    disable_rate_limiting()
    print("DEBUG CONFTEST: rate limiting disabled", flush=True)


@pytest.fixture
def disable_rate_limiting_for_tests() -> Iterator[None]:
    """Disable rate limiting for tests that need it (e.g., lockout tests)."""
    disable_rate_limiting()
    yield
    enable_rate_limiting()
