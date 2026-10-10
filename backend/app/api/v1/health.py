from fastapi import APIRouter

from app.db.database import db_manager
from app.exceptions import ServiceNotReadyException
from app.schemas.common import SuccessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=SuccessResponse)
async def health_check() -> SuccessResponse:
    """Liveness probe - indicates the application is running."""
    return SuccessResponse(message="Service is healthy", data={"status": "ok"})


@router.get("/ready", response_model=SuccessResponse)
async def readiness_check() -> SuccessResponse:
    """Readiness probe - indicates the application is ready to serve requests."""
    try:
        is_ready = await db_manager.ping()
        if is_ready:
            return SuccessResponse(
                message="Service is ready", data={"status": "ready", "mongodb": "connected"}
            )
        else:
            raise ServiceNotReadyException(
                errors=[{"field": "mongodb", "message": "MongoDB connection failed", "code": "CONNECTION_FAILED"}],
            )
    except ServiceNotReadyException:
        raise
    except Exception:
        # Phase 1.8 hardening: never surface internal exception details (e.g.
        # MongoDB connection URI) in the readiness response.  The full
        # exception is still recorded by the server-side logger.
        raise ServiceNotReadyException(
            errors=[{"field": "mongodb", "message": "Database check failed", "code": "CONNECTION_ERROR"}],
        )
