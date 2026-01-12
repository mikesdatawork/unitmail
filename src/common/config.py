"""
Application configuration management for unitMail.

This module provides configuration loading from environment variables
and configuration files, with type-safe settings classes.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .exceptions import ConfigurationError, InvalidConfigError, MissingConfigError


class DatabaseSettings(BaseSettings):
    """Database/Supabase configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="SUPABASE_",
        extra="ignore",
    )

    url: str = Field(..., description="Supabase project URL")
    key: str = Field(..., description="Supabase API key (anon or service role)")
    service_role_key: Optional[str] = Field(
        None, description="Supabase service role key for admin operations"
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate Supabase URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v.rstrip("/")


class SMTPSettings(BaseSettings):
    """SMTP server configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="SMTP_",
        extra="ignore",
    )

    host: str = Field(default="0.0.0.0", description="SMTP server bind host")
    port: int = Field(default=25, ge=1, le=65535, description="SMTP server port")
    tls_port: int = Field(default=465, ge=1, le=65535, description="SMTP TLS port")
    submission_port: int = Field(
        default=587, ge=1, le=65535, description="SMTP submission port"
    )
    hostname: str = Field(
        default="localhost", description="SMTP server hostname for HELO/EHLO"
    )
    max_message_size: int = Field(
        default=25 * 1024 * 1024, description="Maximum message size in bytes"
    )
    timeout: int = Field(default=300, description="Connection timeout in seconds")
    require_auth: bool = Field(
        default=True, description="Require authentication for sending"
    )
    tls_cert_file: Optional[str] = Field(None, description="Path to TLS certificate")
    tls_key_file: Optional[str] = Field(None, description="Path to TLS private key")


class APISettings(BaseSettings):
    """API server configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="API_",
        extra="ignore",
    )

    host: str = Field(default="0.0.0.0", description="API server bind host")
    port: int = Field(default=8000, ge=1, le=65535, description="API server port")
    debug: bool = Field(default=False, description="Enable debug mode")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"], description="Allowed CORS origins"
    )
    rate_limit: int = Field(
        default=100, description="Rate limit requests per minute"
    )
    jwt_secret: str = Field(
        default="change-me-in-production", description="JWT signing secret"
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiration: int = Field(
        default=3600, description="JWT expiration time in seconds"
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


class DNSSettings(BaseSettings):
    """DNS configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="DNS_",
        extra="ignore",
    )

    resolver: str = Field(default="8.8.8.8", description="DNS resolver address")
    timeout: int = Field(default=5, description="DNS query timeout in seconds")
    cache_ttl: int = Field(default=300, description="DNS cache TTL in seconds")
    dkim_selector: str = Field(default="unitmail", description="DKIM selector")
    dkim_private_key_path: Optional[str] = Field(
        None, description="Path to DKIM private key"
    )


class MeshSettings(BaseSettings):
    """Mesh network configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="MESH_",
        extra="ignore",
    )

    enabled: bool = Field(default=False, description="Enable mesh networking")
    node_id: Optional[str] = Field(None, description="This node's unique ID")
    listen_port: int = Field(
        default=9000, ge=1, le=65535, description="Mesh listen port"
    )
    bootstrap_peers: list[str] = Field(
        default_factory=list, description="Initial peer addresses"
    )
    max_peers: int = Field(default=50, description="Maximum number of peers")
    heartbeat_interval: int = Field(
        default=30, description="Heartbeat interval in seconds"
    )
    peer_timeout: int = Field(
        default=120, description="Peer timeout in seconds"
    )

    @field_validator("bootstrap_peers", mode="before")
    @classmethod
    def parse_bootstrap_peers(cls, v: Any) -> list[str]:
        """Parse bootstrap peers from comma-separated string or list."""
        if isinstance(v, str):
            if not v.strip():
                return []
            return [peer.strip() for peer in v.split(",")]
        return v


class CryptoSettings(BaseSettings):
    """Cryptography configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="CRYPTO_",
        extra="ignore",
    )

    key_size: int = Field(default=2048, description="RSA key size in bits")
    hash_algorithm: str = Field(default="sha256", description="Hash algorithm")
    encryption_algorithm: str = Field(
        default="aes-256-gcm", description="Symmetric encryption algorithm"
    )
    private_key_path: Optional[str] = Field(
        None, description="Path to server private key"
    )
    public_key_path: Optional[str] = Field(
        None, description="Path to server public key"
    )


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        extra="ignore",
    )

    level: str = Field(default="INFO", description="Log level")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format",
    )
    file: Optional[str] = Field(None, description="Log file path")
    json: bool = Field(default=False, description="Use JSON log format")

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v_upper


class Settings(BaseSettings):
    """Main application settings aggregating all configuration."""

    model_config = SettingsConfigDict(
        env_prefix="UNITMAIL_",
        extra="ignore",
    )

    # Application metadata
    app_name: str = Field(default="unitMail", description="Application name")
    environment: str = Field(default="development", description="Environment name")
    debug: bool = Field(default=False, description="Debug mode")

    # Sub-settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    smtp: SMTPSettings = Field(default_factory=SMTPSettings)
    api: APISettings = Field(default_factory=APISettings)
    dns: DNSSettings = Field(default_factory=DNSSettings)
    mesh: MeshSettings = Field(default_factory=MeshSettings)
    crypto: CryptoSettings = Field(default_factory=CryptoSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    @classmethod
    def from_toml(cls, path: str | Path) -> "Settings":
        """
        Load settings from a TOML configuration file.

        Args:
            path: Path to the TOML configuration file.

        Returns:
            Settings instance with loaded configuration.

        Raises:
            ConfigurationError: If the file cannot be read or parsed.
        """
        path = Path(path)
        if not path.exists():
            raise MissingConfigError(f"Configuration file not found: {path}")

        try:
            with open(path, "rb") as f:
                config_data = tomllib.load(f)
        except Exception as e:
            raise InvalidConfigError(
                config_key="config_file",
                value=str(path),
                reason=f"Failed to parse TOML: {e}",
            )

        return cls._from_dict(config_data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "Settings":
        """
        Create settings from a dictionary.

        Args:
            data: Configuration dictionary.

        Returns:
            Settings instance.
        """
        # Map TOML sections to settings classes
        settings_kwargs: dict[str, Any] = {}

        if "app" in data:
            settings_kwargs.update(data["app"])

        if "database" in data:
            settings_kwargs["database"] = DatabaseSettings(**data["database"])

        if "smtp" in data:
            settings_kwargs["smtp"] = SMTPSettings(**data["smtp"])

        if "api" in data:
            settings_kwargs["api"] = APISettings(**data["api"])

        if "dns" in data:
            settings_kwargs["dns"] = DNSSettings(**data["dns"])

        if "mesh" in data:
            settings_kwargs["mesh"] = MeshSettings(**data["mesh"])

        if "crypto" in data:
            settings_kwargs["crypto"] = CryptoSettings(**data["crypto"])

        if "logging" in data:
            settings_kwargs["logging"] = LoggingSettings(**data["logging"])

        return cls(**settings_kwargs)

    def validate_required(self) -> None:
        """
        Validate that all required configuration is present.

        Raises:
            MissingConfigError: If required configuration is missing.
        """
        # Check database configuration
        if not self.database.url:
            raise MissingConfigError("SUPABASE_URL")
        if not self.database.key:
            raise MissingConfigError("SUPABASE_KEY")

        # Check JWT secret in production
        if self.environment == "production":
            if self.api.jwt_secret == "change-me-in-production":
                raise InvalidConfigError(
                    config_key="API_JWT_SECRET",
                    value="(default)",
                    reason="JWT secret must be changed in production",
                )


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings.

    This function loads settings from environment variables and
    optionally from a configuration file. The result is cached
    for performance.

    Returns:
        Settings instance.
    """
    # Check for config file path
    config_file = os.getenv("UNITMAIL_CONFIG_FILE")

    if config_file and Path(config_file).exists():
        settings = Settings.from_toml(config_file)
    else:
        settings = Settings()

    return settings


def reload_settings() -> Settings:
    """
    Reload settings, clearing the cache.

    Returns:
        Fresh Settings instance.
    """
    get_settings.cache_clear()
    return get_settings()
