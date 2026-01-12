"""
Middleware components for unitMail Gateway API.

This module provides middleware for request validation, rate limiting,
request ID tracking, and timing/metrics collection.
"""

import hashlib
import logging
import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps
from threading import Lock
from typing import Any, Callable, Optional, TypeVar

from flask import Flask, Response, abort, g, jsonify, request
from werkzeug.exceptions import BadRequest, TooManyRequests

from ..config import GatewaySettings, get_gateway_settings

# Configure module logger
logger = logging.getLogger(__name__)

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# Rate Limiting
# =============================================================================


@dataclass
class RateLimitEntry:
    """Entry for tracking rate limit state."""

    count: int = 0
    window_start: float = field(default_factory=time.time)
    lock: Lock = field(default_factory=Lock)


class InMemoryRateLimiter:
    """
    In-memory rate limiter using token bucket algorithm.

    This implementation uses a sliding window approach to track
    request counts per client.

    Thread-safe for use with multi-threaded Flask applications.
    """

    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: int = 60,
    ) -> None:
        """
        Initialize the rate limiter.

        Args:
            max_requests: Maximum number of requests per window.
            window_seconds: Window size in seconds.
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._cleanup_lock = Lock()
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes

    def _get_client_key(self) -> str:
        """
        Get a unique key for the current client.

        Uses a combination of IP address and optional user ID.

        Returns:
            Client identifier string.
        """
        # Get client IP (consider X-Forwarded-For for proxied requests)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.remote_addr or "unknown"

        # Include user ID if authenticated
        user_id = getattr(g, "user_id", None)
        if user_id:
            return f"user:{user_id}"

        return f"ip:{client_ip}"

    def _cleanup_old_entries(self) -> None:
        """Remove expired rate limit entries."""
        current_time = time.time()

        # Only cleanup periodically
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        with self._cleanup_lock:
            if current_time - self._last_cleanup < self._cleanup_interval:
                return

            expired_keys = []
            for key, entry in self._buckets.items():
                if current_time - entry.window_start > self.window_seconds * 2:
                    expired_keys.append(key)

            for key in expired_keys:
                del self._buckets[key]

            self._last_cleanup = current_time

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired rate limit entries")

    def is_allowed(self, key: Optional[str] = None) -> tuple[bool, dict[str, Any]]:
        """
        Check if a request is allowed under rate limiting.

        Args:
            key: Optional custom key. If not provided, client key is used.

        Returns:
            Tuple of (is_allowed, rate_limit_info).
        """
        self._cleanup_old_entries()

        if key is None:
            key = self._get_client_key()

        current_time = time.time()
        entry = self._buckets[key]

        with entry.lock:
            # Reset window if expired
            if current_time - entry.window_start > self.window_seconds:
                entry.count = 0
                entry.window_start = current_time

            # Check if under limit
            entry.count += 1
            remaining = max(0, self.max_requests - entry.count)
            reset_time = entry.window_start + self.window_seconds

            rate_limit_info = {
                "limit": self.max_requests,
                "remaining": remaining,
                "reset": int(reset_time),
                "reset_after": max(0, int(reset_time - current_time)),
            }

            if entry.count > self.max_requests:
                return False, rate_limit_info

            return True, rate_limit_info

    def reset(self, key: Optional[str] = None) -> None:
        """
        Reset rate limit for a key.

        Args:
            key: Key to reset. If not provided, client key is used.
        """
        if key is None:
            key = self._get_client_key()

        if key in self._buckets:
            with self._buckets[key].lock:
                self._buckets[key].count = 0
                self._buckets[key].window_start = time.time()


class RedisRateLimiter:
    """
    Redis-backed rate limiter for distributed deployments.

    Uses Redis INCR and EXPIRE for atomic rate limit tracking.
    """

    def __init__(
        self,
        redis_url: str,
        max_requests: int = 100,
        window_seconds: int = 60,
        key_prefix: str = "ratelimit:",
    ) -> None:
        """
        Initialize the Redis rate limiter.

        Args:
            redis_url: Redis connection URL.
            max_requests: Maximum number of requests per window.
            window_seconds: Window size in seconds.
            key_prefix: Prefix for Redis keys.
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix
        self._redis: Optional[Any] = None
        self._redis_url = redis_url

    @property
    def redis(self) -> Any:
        """Lazy-load Redis connection."""
        if self._redis is None:
            try:
                import redis
                self._redis = redis.from_url(self._redis_url)
            except ImportError:
                raise RuntimeError("redis package is required for Redis rate limiting")
        return self._redis

    def _get_client_key(self) -> str:
        """Get a unique key for the current client."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.remote_addr or "unknown"

        user_id = getattr(g, "user_id", None)
        if user_id:
            return f"{self.key_prefix}user:{user_id}"

        return f"{self.key_prefix}ip:{client_ip}"

    def is_allowed(self, key: Optional[str] = None) -> tuple[bool, dict[str, Any]]:
        """
        Check if a request is allowed under rate limiting.

        Args:
            key: Optional custom key.

        Returns:
            Tuple of (is_allowed, rate_limit_info).
        """
        if key is None:
            key = self._get_client_key()

        current_time = time.time()

        try:
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.ttl(key)
            count, ttl = pipe.execute()

            # Set expiration if this is a new key
            if ttl == -1:
                self.redis.expire(key, self.window_seconds)
                ttl = self.window_seconds

            remaining = max(0, self.max_requests - count)
            reset_time = current_time + ttl

            rate_limit_info = {
                "limit": self.max_requests,
                "remaining": remaining,
                "reset": int(reset_time),
                "reset_after": max(0, ttl),
            }

            if count > self.max_requests:
                return False, rate_limit_info

            return True, rate_limit_info

        except Exception as e:
            logger.error(f"Redis rate limiter error: {e}")
            # Fail open - allow request if Redis is unavailable
            return True, {
                "limit": self.max_requests,
                "remaining": self.max_requests,
                "reset": int(current_time + self.window_seconds),
                "reset_after": self.window_seconds,
            }

    def reset(self, key: Optional[str] = None) -> None:
        """Reset rate limit for a key."""
        if key is None:
            key = self._get_client_key()

        try:
            self.redis.delete(key)
        except Exception as e:
            logger.error(f"Redis rate limiter reset error: {e}")


# Global rate limiter instance
_rate_limiter: Optional[InMemoryRateLimiter | RedisRateLimiter] = None


def get_rate_limiter(
    settings: Optional[GatewaySettings] = None,
) -> InMemoryRateLimiter | RedisRateLimiter:
    """
    Get or create the rate limiter instance.

    Args:
        settings: Optional gateway settings.

    Returns:
        Rate limiter instance.
    """
    global _rate_limiter

    if _rate_limiter is None:
        settings = settings or get_gateway_settings()

        if settings.rate_limit_storage == "redis" and settings.redis_url:
            _rate_limiter = RedisRateLimiter(
                redis_url=settings.redis_url,
                max_requests=settings.rate_limit_requests,
                window_seconds=settings.rate_limit_window,
            )
        else:
            _rate_limiter = InMemoryRateLimiter(
                max_requests=settings.rate_limit_requests,
                window_seconds=settings.rate_limit_window,
            )

    return _rate_limiter


def rate_limit(
    max_requests: Optional[int] = None,
    window_seconds: Optional[int] = None,
    key_func: Optional[Callable[[], str]] = None,
) -> Callable[[F], F]:
    """
    Rate limiting decorator for Flask routes.

    Args:
        max_requests: Override max requests from settings.
        window_seconds: Override window from settings.
        key_func: Custom function to generate rate limit key.

    Returns:
        Decorated function.
    """
    def decorator(f: F) -> F:
        @wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            settings = get_gateway_settings()

            if not settings.rate_limit_enabled:
                return f(*args, **kwargs)

            limiter = get_rate_limiter(settings)

            # Override limiter settings if provided
            if max_requests is not None:
                limiter.max_requests = max_requests
            if window_seconds is not None:
                limiter.window_seconds = window_seconds

            # Get rate limit key
            key = key_func() if key_func else None

            is_allowed, info = limiter.is_allowed(key)

            # Add rate limit headers to response
            g.rate_limit_info = info

            if not is_allowed:
                logger.warning(
                    "Rate limit exceeded",
                    extra={
                        "request_id": getattr(g, "request_id", None),
                        "client_key": key,
                        "limit": info["limit"],
                    },
                )
                abort(429, description="Rate limit exceeded. Please try again later.")

            return f(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


# =============================================================================
# Request Validation
# =============================================================================


class RequestValidator:
    """Request validation utilities."""

    # Common patterns for validation
    UUID_PATTERN = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )
    EMAIL_PATTERN = re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    )
    SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

    @staticmethod
    def validate_json_body(
        required_fields: Optional[list[str]] = None,
        optional_fields: Optional[list[str]] = None,
    ) -> Callable[[F], F]:
        """
        Decorator to validate JSON request body.

        Args:
            required_fields: List of required field names.
            optional_fields: List of optional field names.

        Returns:
            Decorated function.
        """
        def decorator(f: F) -> F:
            @wraps(f)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                if not request.is_json:
                    abort(400, description="Request must be JSON")

                data = request.get_json(silent=True)
                if data is None:
                    abort(400, description="Invalid JSON body")

                # Check required fields
                if required_fields:
                    missing = [
                        field for field in required_fields
                        if field not in data or data[field] is None
                    ]
                    if missing:
                        abort(
                            400,
                            description=f"Missing required fields: {', '.join(missing)}",
                        )

                # Store validated data in g for access in route
                g.validated_data = data

                return f(*args, **kwargs)

            return wrapper  # type: ignore

        return decorator

    @staticmethod
    def validate_query_params(
        required_params: Optional[list[str]] = None,
        type_mapping: Optional[dict[str, type]] = None,
    ) -> Callable[[F], F]:
        """
        Decorator to validate query parameters.

        Args:
            required_params: List of required parameter names.
            type_mapping: Dictionary mapping parameter names to types.

        Returns:
            Decorated function.
        """
        def decorator(f: F) -> F:
            @wraps(f)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Check required params
                if required_params:
                    missing = [
                        param for param in required_params
                        if param not in request.args
                    ]
                    if missing:
                        abort(
                            400,
                            description=f"Missing required query parameters: {', '.join(missing)}",
                        )

                # Type conversion
                validated_params: dict[str, Any] = {}
                if type_mapping:
                    for param, param_type in type_mapping.items():
                        value = request.args.get(param)
                        if value is not None:
                            try:
                                if param_type == bool:
                                    validated_params[param] = value.lower() in (
                                        "true", "1", "yes"
                                    )
                                else:
                                    validated_params[param] = param_type(value)
                            except (ValueError, TypeError):
                                abort(
                                    400,
                                    description=f"Invalid type for parameter '{param}'",
                                )
                        else:
                            validated_params[param] = None

                g.validated_params = validated_params

                return f(*args, **kwargs)

            return wrapper  # type: ignore

        return decorator

    @classmethod
    def is_valid_uuid(cls, value: str) -> bool:
        """Check if a string is a valid UUID."""
        return bool(cls.UUID_PATTERN.match(value))

    @classmethod
    def is_valid_email(cls, value: str) -> bool:
        """Check if a string is a valid email address."""
        return bool(cls.EMAIL_PATTERN.match(value))

    @classmethod
    def is_valid_slug(cls, value: str) -> bool:
        """Check if a string is a valid slug."""
        return bool(cls.SLUG_PATTERN.match(value))


def validate_content_type(allowed_types: list[str]) -> Callable[[F], F]:
    """
    Decorator to validate request Content-Type.

    Args:
        allowed_types: List of allowed MIME types.

    Returns:
        Decorated function.
    """
    def decorator(f: F) -> F:
        @wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            content_type = request.content_type or ""

            # Check if content type matches any allowed type
            if not any(
                content_type.startswith(allowed_type)
                for allowed_type in allowed_types
            ):
                abort(
                    415,
                    description=f"Unsupported Content-Type. Allowed: {', '.join(allowed_types)}",
                )

            return f(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


# =============================================================================
# Request ID Tracking
# =============================================================================


def request_id_middleware(app: Flask) -> None:
    """
    Register request ID tracking middleware.

    Args:
        app: Flask application instance.
    """

    @app.before_request
    def add_request_id() -> None:
        """Add request ID to the request context."""
        # Use existing request ID from header or generate new one
        g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    @app.after_request
    def add_request_id_header(response: Response) -> Response:
        """Add request ID to response headers."""
        request_id = getattr(g, "request_id", None)
        if request_id:
            response.headers["X-Request-ID"] = request_id
        return response


# =============================================================================
# Timing / Metrics Middleware
# =============================================================================


@dataclass
class RequestMetrics:
    """Container for request metrics."""

    method: str
    path: str
    status_code: int
    response_time_ms: float
    request_size: int
    response_size: int
    timestamp: datetime


class MetricsCollector:
    """
    Collector for request metrics.

    Stores recent metrics in memory for monitoring and debugging.
    """

    def __init__(self, max_entries: int = 1000) -> None:
        """
        Initialize the metrics collector.

        Args:
            max_entries: Maximum number of metrics entries to keep.
        """
        self.max_entries = max_entries
        self._metrics: list[RequestMetrics] = []
        self._lock = Lock()

        # Aggregated stats
        self._total_requests = 0
        self._total_errors = 0
        self._total_response_time_ms = 0.0

    def record(self, metrics: RequestMetrics) -> None:
        """
        Record request metrics.

        Args:
            metrics: RequestMetrics instance to record.
        """
        with self._lock:
            self._metrics.append(metrics)

            # Update aggregated stats
            self._total_requests += 1
            if metrics.status_code >= 400:
                self._total_errors += 1
            self._total_response_time_ms += metrics.response_time_ms

            # Trim old entries
            if len(self._metrics) > self.max_entries:
                self._metrics = self._metrics[-self.max_entries:]

    def get_stats(self) -> dict[str, Any]:
        """
        Get aggregated statistics.

        Returns:
            Dictionary with statistics.
        """
        with self._lock:
            avg_response_time = (
                self._total_response_time_ms / self._total_requests
                if self._total_requests > 0
                else 0
            )

            return {
                "total_requests": self._total_requests,
                "total_errors": self._total_errors,
                "error_rate": (
                    self._total_errors / self._total_requests
                    if self._total_requests > 0
                    else 0
                ),
                "avg_response_time_ms": round(avg_response_time, 2),
                "recent_entries": len(self._metrics),
            }

    def get_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Get recent metrics entries.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of metrics dictionaries.
        """
        with self._lock:
            entries = self._metrics[-limit:]
            return [
                {
                    "method": m.method,
                    "path": m.path,
                    "status_code": m.status_code,
                    "response_time_ms": round(m.response_time_ms, 2),
                    "request_size": m.request_size,
                    "response_size": m.response_size,
                    "timestamp": m.timestamp.isoformat(),
                }
                for m in entries
            ]


# Global metrics collector
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def timing_middleware(app: Flask) -> None:
    """
    Register timing/metrics middleware.

    Args:
        app: Flask application instance.
    """
    collector = get_metrics_collector()

    @app.before_request
    def start_timer() -> None:
        """Record request start time."""
        g.request_start_time = time.perf_counter()

    @app.after_request
    def record_metrics(response: Response) -> Response:
        """Record request metrics."""
        start_time = getattr(g, "request_start_time", None)
        if start_time is None:
            return response

        response_time_ms = (time.perf_counter() - start_time) * 1000

        # Add timing header
        response.headers["X-Response-Time"] = f"{response_time_ms:.2f}ms"

        # Record metrics
        metrics = RequestMetrics(
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            response_time_ms=response_time_ms,
            request_size=request.content_length or 0,
            response_size=response.content_length or 0,
            timestamp=datetime.now(timezone.utc),
        )
        collector.record(metrics)

        return response


def add_rate_limit_headers(response: Response) -> Response:
    """
    Add rate limit headers to response.

    Args:
        response: Flask response object.

    Returns:
        Response with rate limit headers.
    """
    info = getattr(g, "rate_limit_info", None)
    if info:
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])

    return response


def register_middleware(app: Flask) -> None:
    """
    Register all middleware with the Flask application.

    Args:
        app: Flask application instance.
    """
    request_id_middleware(app)
    timing_middleware(app)

    # Add rate limit headers to all responses
    app.after_request(add_rate_limit_headers)

    logger.info("Middleware registered")


# Export public components
__all__ = [
    # Rate limiting
    "InMemoryRateLimiter",
    "RedisRateLimiter",
    "get_rate_limiter",
    "rate_limit",
    # Validation
    "RequestValidator",
    "validate_content_type",
    # Request ID
    "request_id_middleware",
    # Metrics
    "MetricsCollector",
    "RequestMetrics",
    "get_metrics_collector",
    "timing_middleware",
    # Registration
    "register_middleware",
]
