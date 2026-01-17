"""
Gateway-specific configuration for unitMail.

This module provides configuration settings specific to the Gateway service,
extending the common application configuration.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    """Gateway service configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="GATEWAY_",
        extra="ignore",
    )

    # Server settings
    host: str = Field(
        default="0.0.0.0",
        description="Host address to bind the gateway server",
    )
    port: int = Field(
        default=8080,
        ge=1,
        le=65535,
        description="Port to bind the gateway server",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )

    # WebSocket settings
    websocket_enabled: bool = Field(
        default=True,
        description="Enable WebSocket support for real-time updates",
    )
    websocket_ping_interval: int = Field(
        default=25,
        description="WebSocket ping interval in seconds",
    )
    websocket_ping_timeout: int = Field(
        default=60,
        description="WebSocket ping timeout in seconds",
    )

    # CORS settings
    cors_enabled: bool = Field(
        default=True,
        description="Enable CORS support",
    )
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(
        default=True,
        description="Allow credentials in CORS requests",
    )
    cors_max_age: int = Field(
        default=600,
        description="CORS preflight cache max age in seconds",
    )

    # Rate limiting settings
    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable rate limiting",
    )
    rate_limit_requests: int = Field(
        default=100,
        description="Maximum requests per window",
    )
    rate_limit_window: int = Field(
        default=60,
        description="Rate limit window in seconds",
    )
    rate_limit_storage: str = Field(
        default="memory",
        description="Rate limit storage backend (memory or redis)",
    )
    redis_url: Optional[str] = Field(
        default=None,
        description="Redis URL for rate limiting storage",
    )

    # Request settings
    max_content_length: int = Field(
        default=16 * 1024 * 1024,  # 16 MB
        description="Maximum request content length in bytes",
    )
    request_timeout: int = Field(
        default=30,
        description="Request timeout in seconds",
    )

    # Logging settings
    log_requests: bool = Field(
        default=True,
        description="Enable request/response logging",
    )
    log_request_body: bool = Field(
        default=False,
        description="Log request bodies (may expose sensitive data)",
    )
    log_response_body: bool = Field(
        default=False,
        description="Log response bodies (may expose sensitive data)",
    )

    # Security settings
    secret_key: str = Field(
        default="change-me-in-production",
        description="Flask secret key for session management",
    )
    session_cookie_secure: bool = Field(
        default=True,
        description="Only send session cookies over HTTPS",
    )
    session_cookie_httponly: bool = Field(
        default=True,
        description="Prevent JavaScript access to session cookies",
    )
    session_cookie_samesite: str = Field(
        default="Lax",
        description="SameSite cookie attribute",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip()
                    for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("rate_limit_storage")
    @classmethod
    def validate_rate_limit_storage(cls, v: str) -> str:
        """Validate rate limit storage backend."""
        valid_backends = ["memory", "redis"]
        if v.lower() not in valid_backends:
            raise ValueError(
                f"Rate limit storage must be one of: {', '.join(valid_backends)}")
        return v.lower()

    @field_validator("session_cookie_samesite")
    @classmethod
    def validate_samesite(cls, v: str) -> str:
        """Validate SameSite cookie attribute."""
        valid_values = ["Strict", "Lax", "None"]
        if v not in valid_values:
            raise ValueError(
                f"SameSite must be one of: {', '.join(valid_values)}")
        return v


@lru_cache()
def get_gateway_settings() -> GatewaySettings:
    """
    Get cached gateway settings.

    Returns:
        GatewaySettings instance loaded from environment variables.
    """
    return GatewaySettings()


def reload_gateway_settings() -> GatewaySettings:
    """
    Reload gateway settings, clearing the cache.

    Returns:
        Fresh GatewaySettings instance.
    """
    get_gateway_settings.cache_clear()
    return get_gateway_settings()
