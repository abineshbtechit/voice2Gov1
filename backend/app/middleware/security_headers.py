"""Security headers middleware (Phase 1.8).

Adds defensive HTTP security headers to every response.  The header set
is deliberately conservative and compatible with a React-Native/JSON API
backend that is consumed by mobile clients and has no browser-served HTML:

* ``X-Content-Type-Options: nosniff``   — prevent MIME sniffing
* ``X-Frame-Options: DENY``             — prevent clickjacking (browser clients)
* ``X-XSS-Protection: 1; mode=block``  — legacy XSS filter (old browsers)
* ``Referrer-Policy``                   — limit referrer leakage
* ``Cache-Control``                     — disable caching for API responses

CORS and HSTS are handled elsewhere (CORSMiddleware in create_app; HSTS
belongs at the TLS-terminating edge proxy in production, not in the app layer).
"""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add a minimal defensive security-header set to every API response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)

        # Prevent MIME-type sniffing by the browser / mobile WebView.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")

        # Prevent the API response from being embedded in a frame.
        response.headers.setdefault("X-Frame-Options", "DENY")

        # Legacy XSS protection header (modern browsers ignore it but it costs
        # nothing and benefits old clients).
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")

        # Restrict how much referrer information is sent with cross-origin
        # requests.  Safe for API clients (no referrer is leaked).
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )

        # API responses must not be cached by intermediary proxies.
        response.headers.setdefault(
            "Cache-Control", "no-store, no-cache, must-revalidate"
        )

        return response
