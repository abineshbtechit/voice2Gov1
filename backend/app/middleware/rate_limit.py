"""In-memory rate limiting middleware (Phase 1.2.6).

Provides a simple sliding window rate limiter for protecting sensitive endpoints.
Phase 1 implementation uses in-memory storage; production should use Redis.
"""

import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.exceptions.base import RateLimitException

# Global flag to disable rate limiting for tests
_rate_limiting_disabled = False


def disable_rate_limiting() -> None:
    """Disable rate limiting globally (for tests)."""
    global _rate_limiting_disabled
    _rate_limiting_disabled = True


def enable_rate_limiting() -> None:
    """Enable rate limiting globally."""
    global _rate_limiting_disabled
    _rate_limiting_disabled = False


def reset_all_rate_limiters() -> None:
    """Reset all rate limiter buckets (for tests)."""
    _auth_rate_limiter.reset()
    _general_rate_limiter.reset()


@dataclass
class RateLimitBucket:
    """Represents a rate limit bucket for a specific key."""
    requests: list[float] = field(default_factory=list)

    def add_request(self, now: float) -> None:
        self.requests.append(now)

    def get_request_count(self, now: float, window_seconds: int) -> int:
        """Count requests within the sliding window."""
        cutoff = now - window_seconds
        # Remove expired requests
        self.requests = [t for t in self.requests if t > cutoff]
        return len(self.requests)


class RateLimiter:
    """In-memory rate limiter using sliding window algorithm."""

    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: int = 60,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.buckets: dict[str, RateLimitBucket] = defaultdict(RateLimitBucket)

    def _get_key(self, request: Request, key_prefix: str = "") -> str:
        """Generate rate limit key from request."""
        # Use client IP as default identifier
        client_ip = request.client.host if request.client else "unknown"
        # Include path for endpoint-specific limiting
        path = request.url.path
        return f"{key_prefix}:{client_ip}:{path}"

    def is_allowed(self, request: Request, key_prefix: str = "") -> tuple[bool, dict[str, Any]]:
        """Check if request is allowed under rate limit.
        Returns:
            Tuple of (allowed, headers_dict)
        """
        key = self._get_key(request, key_prefix)
        now = time.time()
        bucket = self.buckets[key]

        count = bucket.get_request_count(now, self.window_seconds)

        if count >= self.max_requests:
            # Calculate retry after
            oldest = min(bucket.requests) if bucket.requests else now
            retry_after = int(oldest + self.window_seconds - now) + 1
            return False, {
                "X-RateLimit-Limit": str(self.max_requests),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(now + retry_after)),
                "Retry-After": str(retry_after),
            }

        bucket.add_request(now)
        remaining = self.max_requests - count - 1
        reset_time = int(now + self.window_seconds)

        return True, {
            "X-RateLimit-Limit": str(self.max_requests),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_time),
        }

    def reset(self) -> None:
        """Reset all buckets (for tests)."""
        self.buckets.clear()


# Global rate limiter instances for different endpoint groups
_auth_rate_limiter = RateLimiter(
    max_requests=5,  # Stricter limit for auth endpoints
    window_seconds=60,
)

_general_rate_limiter = RateLimiter(
    max_requests=1000,
    window_seconds=60,
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""

    def __init__(
        self,
        app: FastAPI,
        rate_limiter: RateLimiter | None = None,
        key_prefix: str = "",
        enabled: bool = True,
    ):
        super().__init__(app)
        self.rate_limiter = rate_limiter or _general_rate_limiter
        self.key_prefix = key_prefix
        self.enabled = True

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if not self.enabled or not settings.rate_limit_enabled or _rate_limiting_disabled:
            return await call_next(request)

        # Skip rate limiting for auth endpoints (they have their own rate limiting via dependency)
        auth_paths = {"/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/refresh", "/api/v1/auth/logout"}
        if request.url.path in auth_paths:
            return await call_next(request)

        allowed, headers = self.rate_limiter.is_allowed(request, self.key_prefix)

        if not allowed:
            raise RateLimitException(
                "Rate limit exceeded",
                retry_after=int(headers.get("Retry-After", 60)),
                rate_limit_headers=headers,
            )

        response = await call_next(request)

        # Add rate limit headers to response
        for key, value in headers.items():
            response.headers[key] = value

        return response


def get_auth_rate_limiter() -> RateLimiter:
    """Get the authentication-specific rate limiter."""
    return _auth_rate_limiter


def get_general_rate_limiter() -> RateLimiter:
    """Get the general API rate limiter."""
    return _general_rate_limiter


async def rate_limit_auth(request: Request) -> None:
    """Dependency for applying auth rate limiting to specific endpoints."""
    if not settings.rate_limit_enabled or _rate_limiting_disabled:
        return

    allowed, headers = _auth_rate_limiter.is_allowed(request, "auth")

    # Always store headers for response
    request.state.rate_limit_headers = headers

    if not allowed:
        raise RateLimitException(
            "Rate limit exceeded",
            retry_after=int(headers.get("Retry-After", 60)),
            rate_limit_headers=headers,
        )


class RateLimitHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add rate limit headers from request.state to all responses."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)

        # Add rate limit headers from request.state if present
        rate_limit_headers = getattr(request.state, "rate_limit_headers", None)
        if rate_limit_headers:
            for key, value in rate_limit_headers.items():
                response.headers[key] = value

        return response
