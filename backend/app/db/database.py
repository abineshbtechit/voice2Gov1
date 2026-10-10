import logging
from typing import TYPE_CHECKING, Any

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.asynchronous.mongo_client import AsyncMongoClient

from app.core.config import settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self) -> None:
        self._client: AsyncMongoClient[Any] | None = None
        self._database: AsyncDatabase[Any] | None = None

    async def connect(self) -> None:
        if self._client is not None:
            logger.warning("Database already connected")
            return

        try:
            self._client = AsyncMongoClient[Any](
                settings.mongodb_uri,
                maxPoolSize=settings.mongodb_max_pool_size,
                minPoolSize=settings.mongodb_min_pool_size,
                maxIdleTimeMS=settings.mongodb_max_idle_time_ms,
                serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
            )
            self._database = self._client[settings.mongodb_database]
            # Ping to verify connection
            await self._database.command("ping")
            # Phase 1.8 hardening: never log the MongoDB URI — it can contain
            # credentials. Log only the database name.
            logger.info("Connected to MongoDB: %s", settings.mongodb_database)
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            await self.disconnect()
            raise

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
            self._database = None
            logger.info("Disconnected from MongoDB")

    @property
    def client(self) -> "AsyncMongoClient[Any]":
        if self._client is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._client

    @property
    def database(self) -> "AsyncDatabase[Any]":
        if self._database is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._database

    async def ping(self) -> bool:
        try:
            assert self._database is not None
            await self._database.command("ping")
            return True
        except Exception:
            return False


db_manager = DatabaseManager()


async def get_database() -> "AsyncDatabase[Any]":
    return db_manager.database


async def get_database_optional() -> "AsyncDatabase[Any] | None":
    """Return the database if connected, or None if disconnected."""
    return db_manager._database


async def init_database() -> None:
    await db_manager.connect()


async def close_database() -> None:
    await db_manager.disconnect()
