from typing import Any


class AppException(Exception):
    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class BadRequestException(AppException):
    def __init__(
        self,
        message: str = "Bad request",
        error_code: str = "BAD_REQUEST",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, error_code, 400, details)


class ValidationException(AppException):
    def __init__(
        self,
        message: str = "Validation failed",
        error_code: str = "VALIDATION_ERROR",
        errors: list[dict[str, Any]] | None = None,
    ):
        super().__init__(message, error_code, 422)
        self.details["errors"] = errors or []


class NotFoundException(AppException):
    def __init__(
        self,
        message: str = "Resource not found",
        error_code: str = "RESOURCE_NOT_FOUND",
    ):
        super().__init__(message, error_code, 404)


class ConflictException(AppException):
    def __init__(
        self,
        message: str = "Resource conflict",
        error_code: str = "CONFLICT",
    ):
        super().__init__(message, error_code, 409)


class UnauthorizedException(AppException):
    def __init__(
        self,
        message: str = "Unauthorized",
        error_code: str = "UNAUTHORIZED",
    ):
        super().__init__(message, error_code, 401)


class ForbiddenException(AppException):
    def __init__(
        self,
        message: str = "Forbidden",
        error_code: str = "FORBIDDEN",
    ):
        super().__init__(message, error_code, 403)


class RateLimitException(AppException):
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        error_code: str = "RATE_LIMIT_EXCEEDED",
        retry_after: int | None = None,
        rate_limit_headers: dict[str, str] | None = None,
    ):
        super().__init__(message, error_code, 429)
        if retry_after:
            self.details["retry_after"] = retry_after
        if rate_limit_headers:
            self.details["rate_limit_headers"] = rate_limit_headers


class BusinessLogicException(AppException):
    def __init__(
        self,
        message: str = "Business logic error",
        error_code: str = "BUSINESS_LOGIC_ERROR",
    ):
        super().__init__(message, error_code, 422)


class FileUploadException(AppException):
    def __init__(
        self,
        message: str = "File upload failed",
        error_code: str = "FILE_UPLOAD_ERROR",
    ):
        super().__init__(message, error_code, 400)


class FileValidationException(AppException):
    """Base for file-upload validation failures (HTTP 400 per the API contract)."""

    def __init__(
        self,
        message: str = "File validation failed",
        error_code: str = "INVALID_FILE_TYPE",
    ):
        super().__init__(message, error_code, 400)


class InvalidFileTypeException(FileValidationException):
    """Declared/actual MIME type is not allowed for the image type."""

    def __init__(
        self,
        message: str = "File type is not allowed",
        error_code: str = "INVALID_FILE_TYPE",
    ):
        super().__init__(message, error_code)


class FileTooLargeException(FileValidationException):
    """Uploaded file exceeds the configured size limit for its image type."""

    def __init__(
        self,
        message: str = "File exceeds the maximum allowed size",
        error_code: str = "FILE_TOO_LARGE",
    ):
        super().__init__(message, error_code)


class InvalidFilenameException(FileValidationException):
    """Filename is unsafe (path traversal, absolute path, control characters)."""

    def __init__(
        self,
        message: str = "Filename is not allowed",
        error_code: str = "INVALID_FILENAME",
    ):
        super().__init__(message, error_code)


class StorageException(AppException):
    """Storage backend failure (upload/download/delete)."""

    def __init__(
        self,
        message: str = "Storage operation failed",
        error_code: str = "STORAGE_ERROR",
    ):
        super().__init__(message, error_code, 500)


class ServiceNotReadyException(AppException):
    def __init__(
        self,
        message: str = "Service not ready",
        error_code: str = "SERVICE_NOT_READY",
        errors: list[dict[str, Any]] | None = None,
    ):
        super().__init__(message, error_code, 503)
        if errors:
            self.details["errors"] = errors
