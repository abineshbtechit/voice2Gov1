import asyncio
import logging
from collections.abc import AsyncGenerator, Iterator
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.asynchronous.mongo_client import AsyncMongoClient

from app.core.config import settings
from app.db.database import close_database, db_manager, init_database
from app.main import create_app
from app.middleware.rate_limit import (
    disable_rate_limiting,
    enable_rate_limiting,
    reset_all_rate_limiters,
)
from scripts.create_indexes import INDEXES, create_indexes

logger = logging.getLogger(__name__)

# Isolated database used by the whole test session. Tests must never read or
# write the developer/production database configured by ``MONGODB_DATABASE``.
TEST_DATABASE_NAME = "voice2gov_test"


async def _prepare_isolated_database() -> None:
    """Create the authoritative indexes on the isolated test database.

    Indexes are the authoritative race-safety boundary exercised by the
    concurrency tests (unique ``complaint_number``, ``complaint_likes``,
    ``(organization_id, code)`` ...), so they must exist before any test runs.
    """
    client: AsyncMongoClient[Any] = AsyncMongoClient[Any](
        settings.mongodb_uri,
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
    )
    try:
        database = client[TEST_DATABASE_NAME]
        await database.command("ping")
        await create_indexes(database)
    finally:
        await client.close()


async def _drop_isolated_database() -> None:
    client: AsyncMongoClient[Any] = AsyncMongoClient[Any](
        settings.mongodb_uri,
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
    )
    try:
        await client.drop_database(TEST_DATABASE_NAME)
    finally:
        await client.close()


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database() -> Iterator[None]:
    """Redirect the session's MongoDB database to an isolated test database.

    ``DatabaseManager.connect`` reads ``settings.mongodb_database`` at connect
    time, so mutating the process-wide settings singleton here (before any
    function-scoped fixture connects) keeps every test off the real database.
    The isolated database is dropped at the end of the session.
    """
    original_database = settings.mongodb_database
    settings.mongodb_database = TEST_DATABASE_NAME
    asyncio.run(_prepare_isolated_database())
    try:
        yield
    finally:
        try:
            asyncio.run(_drop_isolated_database())
        finally:
            settings.mongodb_database = original_database


@pytest.fixture(scope="session")
def app() -> FastAPI:
    return create_app()


@pytest_asyncio.fixture(scope="function")
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client backed by a live (isolated) database connection."""
    await init_database()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await close_database()


@pytest_asyncio.fixture(scope="function")
async def db(client: AsyncClient) -> AsyncGenerator[AsyncDatabase[Any], None]:
    """Yield the live (isolated) database handle for real-MongoDB tests.

    Depends on ``client`` so the ``DatabaseManager`` is connected and the
    fixture tears down in the right order. Collections are cleared before the
    test so persisted-record assertions start from a deterministic state.
    """
    database = db_manager.database
    for collection_name in INDEXES:
        await database[collection_name].delete_many({})
    yield database


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
    enable_rate_limiting()
    yield
    disable_rate_limiting()


@pytest.fixture
def disable_rate_limiting_for_tests() -> Iterator[None]:
    """Disable rate limiting for tests that need it (e.g., lockout tests)."""
    disable_rate_limiting()
    yield
    enable_rate_limiting()
