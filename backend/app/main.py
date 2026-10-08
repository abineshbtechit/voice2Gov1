import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.database import close_database, get_database, init_database
from app.exceptions.handlers import register_exception_handlers
from app.middleware.rate_limit import RateLimitHeadersMiddleware, RateLimitMiddleware
from scripts.create_indexes import create_indexes

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting Voice2Gov API...")
    await init_database()
    try:
        db = await get_database()
        await create_indexes(db)
        logger.info("Database indexes verified")
    except Exception as e:
        logger.error(f"Failed to initialize database indexes: {e}")
    yield
    logger.info("Shutting down Voice2Gov API...")
    await close_database()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Voice2Gov Civic Complaint Management Platform API",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # Add rate limiting middleware
    app.add_middleware(
        RateLimitMiddleware,
        rate_limiter=None,  # Use default general rate limiter
        key_prefix="api",
        enabled=settings.rate_limit_enabled,
    )

    # Add rate limit headers middleware (must be added after RateLimitMiddleware to run after)
    app.add_middleware(RateLimitHeadersMiddleware)

    register_exception_handlers(app)

    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
        }

    return app


app = create_app()
