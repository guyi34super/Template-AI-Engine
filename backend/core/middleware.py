"""
Middleware stack — rate-limiting, idempotency, request-id, timing.
Wired into FastAPI in api_server.py.
"""
from __future__ import annotations

import time
import uuid
import json
import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from core.redis_client import (
    check_rate_limit_ip,
    check_rate_limit_user,
    get_idempotency,
    set_idempotency,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Request-ID + Timing middleware
# ---------------------------------------------------------------------------
class RequestIdMiddleware(BaseHTTPMiddleware):
    """Inject X-Request-ID into every request/response and log duration."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        start = time.perf_counter()

        response = await call_next(request)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(elapsed_ms)

        logger.debug(
            "%s %s → %s  [%sms]  rid=%s",
            request.method, request.url.path, response.status_code, elapsed_ms, request_id,
        )
        return response


# ---------------------------------------------------------------------------
# 2. Rate-Limit middleware (uses Redis counters)
# ---------------------------------------------------------------------------
class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-IP and per-user rate limiting via Redis sliding-window counters.
    Falls through silently when Redis is unavailable.
    """

    def __init__(self, app, ip_limit: int = 60, user_limit: int = 120, window: int = 60):
        super().__init__(app)
        self.ip_limit = ip_limit
        self.user_limit = user_limit
        self.window = window

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        ip = request.client.host if request.client else "unknown"

        # IP-based limit
        if not await check_rate_limit_ip(ip, self.ip_limit, self.window):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded — try again later"},
                headers={"Retry-After": str(self.window)},
            )

        # User-based limit (requires auth header already parsed)
        user_id = getattr(request.state, "user_id", None)
        if user_id and not await check_rate_limit_user(user_id, self.user_limit, self.window):
            return JSONResponse(
                status_code=429,
                content={"detail": "User rate limit exceeded"},
                headers={"Retry-After": str(self.window)},
            )

        return await call_next(request)


# ---------------------------------------------------------------------------
# 3. Idempotency middleware (POST / PUT / PATCH)
# ---------------------------------------------------------------------------
class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Replay cached responses for repeated requests sharing the same
    X-Idempotency-Key header.  Only applies to mutating methods.
    """

    METHODS = {"POST", "PUT", "PATCH"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method not in self.METHODS:
            return await call_next(request)

        key = request.headers.get("X-Idempotency-Key")
        if not key:
            return await call_next(request)

        # Check cache
        cached = await get_idempotency(key)
        if cached:
            logger.info("Idempotency cache hit for key=%s", key)
            return JSONResponse(
                status_code=cached.get("status_code", 200),
                content=cached.get("body"),
                headers={"X-Idempotency-Replay": "true"},
            )

        response = await call_next(request)

        # Cache the response (only 2xx)
        if 200 <= response.status_code < 300:
            body_bytes = b""
            async for chunk in response.body_iterator:
                if isinstance(chunk, str):
                    chunk = chunk.encode()
                body_bytes += chunk

            try:
                body_json = json.loads(body_bytes)
            except Exception:
                body_json = body_bytes.decode(errors="replace")

            await set_idempotency(key, {"status_code": response.status_code, "body": body_json})

            # Re-create response since we consumed the iterator
            return Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        return response


# ---------------------------------------------------------------------------
# 4. Security headers middleware
# ---------------------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach standard security headers to every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response
