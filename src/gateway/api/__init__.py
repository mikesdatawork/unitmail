"""
unitMail Gateway API package.

This package contains the API server, routes, and middleware
for the Gateway service.
"""

from .server import GatewayServer, create_server
from .middleware import (
    InMemoryRateLimiter,
    RedisRateLimiter,
    RequestValidator,
    MetricsCollector,
    get_rate_limiter,
    get_metrics_collector,
    rate_limit,
    validate_content_type,
    register_middleware,
)

__all__ = [
    # Server
    "GatewayServer",
    "create_server",
    # Rate limiting
    "InMemoryRateLimiter",
    "RedisRateLimiter",
    "get_rate_limiter",
    "rate_limit",
    # Validation
    "RequestValidator",
    "validate_content_type",
    # Metrics
    "MetricsCollector",
    "get_metrics_collector",
    # Registration
    "register_middleware",
]
