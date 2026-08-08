"""Rate Limiting Middleware

Provides rate limiting for API endpoints using an in-memory sliding window approach.
Supports per-IP and per-endpoint rate limiting with configurable limits.
"""
import time
import logging
from collections import defaultdict

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """In-memory sliding window rate limiter.

    Tracks request counts per client IP within configurable time windows.
    """

    def __init__(self):
        self._windows: dict[str, list[float]] = defaultdict(list)

    def _clean_window(self, key: str, window_seconds: float) -> None:
        """Remove timestamps outside the current window."""
        now = time.time()
        cutoff = now - window_seconds
        self._windows[key] = [t for t in self._windows[key] if t > cutoff]

    def check(self, key: str, max_requests: int, window_seconds: float) -> bool:
        """Check if a request is within rate limits.

        Args:
            key: Unique identifier (e.g., IP + endpoint)
            max_requests: Maximum number of requests allowed
            window_seconds: Time window in seconds

        Returns:
            True if request is allowed, False if rate limited
        """
        self._clean_window(key, window_seconds)
        if len(self._windows[key]) >= max_requests:
            return False
        self._windows[key].append(time.time())
        return True

    def get_remaining(self, key: str, max_requests: int, window_seconds: float) -> int:
        """Get remaining requests allowed."""
        self._clean_window(key, window_seconds)
        return max(0, max_requests - len(self._windows[key]))


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that applies rate limiting to all incoming requests.

    Uses a sliding window algorithm to track requests per IP address.
    Public endpoints (like /click) have higher limits; authenticated
    endpoints have standard limits.
    """

    def __init__(
        self,
        app: ASGIApp,
        default_max_requests: int = 60,
        default_window_seconds: float = 60.0,
        public_max_requests: int = 120,
        public_window_seconds: float = 60.0,
    ) -> None:
        super().__init__(app)
        self.limiter = SlidingWindowRateLimiter()
        self.default_max_requests = default_max_requests
        self.default_window_seconds = default_window_seconds
        self.public_max_requests = public_max_requests
        self.public_window_seconds = public_window_seconds
        # Endpoints that are public (no auth required)
        self.public_paths = {"/click", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request and apply rate limiting."""
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # Determine rate limit config based on endpoint type
        if any(path.startswith(p) for p in self.public_paths):
            max_requests = self.public_max_requests
            window_seconds = self.public_window_seconds
        else:
            max_requests = self.default_max_requests
            window_seconds = self.default_window_seconds

        # Create a rate limit key from IP + endpoint
        key = f"{client_ip}:{path}"

        # Check rate limit
        if not self.limiter.check(key, max_requests, window_seconds):
            remaining = self.limiter.get_remaining(key, max_requests, window_seconds)
            logger.warning(
                f"Rate limit exceeded for {client_ip} on {path}. "
                f"Limit: {max_requests} per {window_seconds}s"
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded. Try again in {window_seconds}s.",
                    "limit": max_requests,
                    "remaining": remaining,
                },
            )

        # Process the request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(
            self.limiter.get_remaining(key, max_requests, window_seconds)
        )
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + window_seconds))

        return response
