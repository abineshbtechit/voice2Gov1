import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions.base import AppException

logger = logging.getLogger(__name__)


def create_error_response(
    success: bool = False,
    message: str = "",
    error_code: str = "",
    errors: list[dict[str, Any]] | None = None,
    details: dict[str, Any] | None = None,
    status_code: int = 500,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "message": message,
            "error_code": error_code,
            "errors": errors or [],
            "details": details or {},
        },
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    logger.warning(
        f"AppException: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "details": exc.details,
            "path": request.url.path,
        },
    )
    response = create_error_response(
        success=False,
        message=exc.message,
        error_code=exc.error_code,
        errors=exc.details.get("errors", []),
        details=exc.details,
        status_code=exc.status_code,
    )
    # Add rate limit headers if present
    rate_limit_headers = exc.details.get("rate_limit_headers")
    if rate_limit_headers:
        for key, value in rate_limit_headers.items():
            response.headers[key] = value
    return response


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "code": error["type"],
        })
    logger.warning(
        f"Validation error: {errors}",
        extra={"path": request.url.path, "errors": errors},
    )
    return create_error_response(
        success=False,
        message="Validation failed",
        error_code="VALIDATION_ERROR",
        errors=errors,
        status_code=422,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    logger.warning(
        f"HTTPException: {exc.status_code} - {exc.detail}",
        extra={"path": request.url.path, "status_code": exc.status_code},
    )
    return create_error_response(
        success=False,
        message=str(exc.detail),
        error_code="HTTP_ERROR",
        status_code=exc.status_code,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        f"Unhandled exception: {type(exc).__name__}: {exc}",
        extra={"path": request.url.path},
    )
    return create_error_response(
        success=False,
        message="Internal server error",
        error_code="INTERNAL_SERVER_ERROR",
        status_code=500,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_exception_handler)
