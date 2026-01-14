"""
Settings service for unitMail client.

This module provides persistent settings management with support for
loading, saving, and applying application settings including theme,
notifications, server configuration, and user preferences.
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, GObject

logger = logging.getLogger(__name__)


class ThemeMode(Enum):
    """Theme mode options."""

    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


@dataclass
class AccountSettings:
    """Account-related settings."""

    display_name: str = ""
    email_address: str = ""
    signature: str = ""
    avatar_path: str = ""


@dataclass
class ServerSettings:
    """Server connection settings."""

    gateway_url: str = "https://localhost:8443"
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_use_tls: bool = True
    imap_host: str = "localhost"
    imap_port: int = 993
    imap_use_tls: bool = True


@dataclass
class SecuritySettings:
    """Security-related settings."""

    pgp_key_id: str = ""
    pgp_key_fingerprint: str = ""
    auto_encrypt: bool = False
    auto_sign: bool = True
    two_factor_enabled: bool = False
    remember_passphrase: bool = False
    passphrase_timeout: int = 300  # seconds


@dataclass
class AppearanceSettings:
    """Appearance-related settings."""

    theme_mode: str = "system"  # system, light, dark
    view_density: str = "standard"  # standard, compact, minimal
    font_size: int = 12
    compact_mode: bool = False
    show_avatars: bool = True
    message_preview_lines: int = 2
    # Column widths for minimal view (received, from, subject)
    column_width_received: int = 120
    column_width_from: int = 250
    column_width_subject: int = -1  # -1 means expand to fill


@dataclass
class NotificationSettings:
    """Notification-related settings."""

    desktop_notifications: bool = True
    notification_sound: bool = True
    notification_sound_path: str = ""
    show_message_preview: bool = True
    notify_on_new_mail: bool = True
    notify_on_send_success: bool = False
    notify_on_error: bool = True


@dataclass
class AdvancedSettings:
    """Advanced settings."""

    cache_enabled: bool = True
    cache_size_mb: int = 500
    cache_path: str = ""
    log_level: str = "INFO"
    log_path: str = ""
    sync_interval_seconds: int = 300
    max_concurrent_connections: int = 4
    show_quota: bool = True
    debug_mode: bool = False


@dataclass
class Settings:
    """Complete application settings."""

    account: AccountSettings = field(default_factory=AccountSettings)
    server: ServerSettings = field(default_factory=ServerSettings)
    security: SecuritySettings = field(default_factory=SecuritySettings)
    appearance: AppearanceSettings = field(default_factory=AppearanceSettings)
    notifications: NotificationSettings = field(default_factory=NotificationSettings)
    advanced: AdvancedSettings = field(default_factory=AdvancedSettings)

    def to_dict(self) -> dict[str, Any]:
        """Convert settings to dictionary."""
        return {
            "account": asdict(self.account),
            "server": asdict(self.server),
            "security": asdict(self.security),
            "appearance": asdict(self.appearance),
            "notifications": asdict(self.notifications),
            "advanced": asdict(self.advanced),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        """Create settings from dictionary."""
        settings = cls()

        if "account" in data:
            settings.account = AccountSettings(**data["account"])
        if "server" in data:
            settings.server = ServerSettings(**data["server"])
        if "security" in data:
            settings.security = SecuritySettings(**data["security"])
        if "appearance" in data:
            settings.appearance = AppearanceSettings(**data["appearance"])
        if "notifications" in data:
            settings.notifications = NotificationSettings(**data["notifications"])
        if "advanced" in data:
            settings.advanced = AdvancedSettings(**data["advanced"])

        return settings


class SettingsService(GObject.Object):
    """
    Service for managing application settings.

    Provides loading, saving, and applying settings with support for
    change notifications and default values.

    Signals:
        settings-changed: Emitted when any setting changes.
        theme-changed: Emitted when theme setting changes.
    """

    __gtype_name__ = "SettingsService"

    __gsignals__ = {
        "settings-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "theme-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    # Default config paths
    APP_ID = "io.unitmail.client"
    CONFIG_FILENAME = "settings.json"

    def __init__(self) -> None:
        """Initialize the settings service."""
        super().__init__()

        self._settings = Settings()
        self._config_path = self._get_config_path()
        self._change_callbacks: list[Callable[[str], None]] = []
        self._is_dirty = False

        # Ensure config directory exists
        self._config_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Settings service initialized, config path: {self._config_path}")

    def _get_config_path(self) -> Path:
        """Get the configuration file path."""
        config_dir = GLib.get_user_config_dir()
        return Path(config_dir) / "unitmail" / self.CONFIG_FILENAME

    @property
    def settings(self) -> Settings:
        """Get current settings."""
        return self._settings

    @property
    def account(self) -> AccountSettings:
        """Get account settings."""
        return self._settings.account

    @property
    def server(self) -> ServerSettings:
        """Get server settings."""
        return self._settings.server

    @property
    def security(self) -> SecuritySettings:
        """Get security settings."""
        return self._settings.security

    @property
    def appearance(self) -> AppearanceSettings:
        """Get appearance settings."""
        return self._settings.appearance

    @property
    def notifications(self) -> NotificationSettings:
        """Get notification settings."""
        return self._settings.notifications

    @property
    def advanced(self) -> AdvancedSettings:
        """Get advanced settings."""
        return self._settings.advanced

    def load(self) -> bool:
        """
        Load settings from config file.

        Returns:
            True if settings were loaded successfully, False otherwise.
        """
        if not self._config_path.exists():
            logger.info("No settings file found, using defaults")
            return False

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._settings = Settings.from_dict(data)
            self._is_dirty = False

            logger.info("Settings loaded successfully")
            return True

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse settings file: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            return False

    def save(self) -> bool:
        """
        Save settings to config file.

        Returns:
            True if settings were saved successfully, False otherwise.
        """
        try:
            data = self._settings.to_dict()

            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            self._is_dirty = False
            logger.info("Settings saved successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False

    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        self._settings = Settings()
        self._is_dirty = True
        self.emit("settings-changed", "all")
        logger.info("Settings reset to defaults")

    def apply_theme(self) -> None:
        """Apply current theme setting to the application."""
        style_manager = Adw.StyleManager.get_default()
        theme = self._settings.appearance.theme_mode

        if theme == "light":
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        elif theme == "dark":
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:  # system
            style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

        logger.info(f"Applied theme: {theme}")

    def set_theme(self, theme: str) -> None:
        """
        Set and apply theme.

        Args:
            theme: Theme mode ('system', 'light', or 'dark').
        """
        if theme not in ("system", "light", "dark"):
            logger.warning(f"Invalid theme: {theme}")
            return

        self._settings.appearance.theme_mode = theme
        self._is_dirty = True
        self.apply_theme()
        self.emit("theme-changed", theme)
        self.emit("settings-changed", "appearance.theme_mode")

    def get_theme(self) -> str:
        """Get current theme mode."""
        return self._settings.appearance.theme_mode

    def update_account(
        self,
        display_name: Optional[str] = None,
        email_address: Optional[str] = None,
        signature: Optional[str] = None,
        avatar_path: Optional[str] = None,
    ) -> None:
        """Update account settings."""
        if display_name is not None:
            self._settings.account.display_name = display_name
        if email_address is not None:
            self._settings.account.email_address = email_address
        if signature is not None:
            self._settings.account.signature = signature
        if avatar_path is not None:
            self._settings.account.avatar_path = avatar_path

        self._is_dirty = True
        self.emit("settings-changed", "account")

    def update_server(
        self,
        gateway_url: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_use_tls: Optional[bool] = None,
        imap_host: Optional[str] = None,
        imap_port: Optional[int] = None,
        imap_use_tls: Optional[bool] = None,
    ) -> None:
        """Update server settings."""
        if gateway_url is not None:
            self._settings.server.gateway_url = gateway_url
        if smtp_host is not None:
            self._settings.server.smtp_host = smtp_host
        if smtp_port is not None:
            self._settings.server.smtp_port = smtp_port
        if smtp_use_tls is not None:
            self._settings.server.smtp_use_tls = smtp_use_tls
        if imap_host is not None:
            self._settings.server.imap_host = imap_host
        if imap_port is not None:
            self._settings.server.imap_port = imap_port
        if imap_use_tls is not None:
            self._settings.server.imap_use_tls = imap_use_tls

        self._is_dirty = True
        self.emit("settings-changed", "server")

    def update_security(
        self,
        pgp_key_id: Optional[str] = None,
        pgp_key_fingerprint: Optional[str] = None,
        auto_encrypt: Optional[bool] = None,
        auto_sign: Optional[bool] = None,
        two_factor_enabled: Optional[bool] = None,
        remember_passphrase: Optional[bool] = None,
        passphrase_timeout: Optional[int] = None,
    ) -> None:
        """Update security settings."""
        if pgp_key_id is not None:
            self._settings.security.pgp_key_id = pgp_key_id
        if pgp_key_fingerprint is not None:
            self._settings.security.pgp_key_fingerprint = pgp_key_fingerprint
        if auto_encrypt is not None:
            self._settings.security.auto_encrypt = auto_encrypt
        if auto_sign is not None:
            self._settings.security.auto_sign = auto_sign
        if two_factor_enabled is not None:
            self._settings.security.two_factor_enabled = two_factor_enabled
        if remember_passphrase is not None:
            self._settings.security.remember_passphrase = remember_passphrase
        if passphrase_timeout is not None:
            self._settings.security.passphrase_timeout = passphrase_timeout

        self._is_dirty = True
        self.emit("settings-changed", "security")

    def update_appearance(
        self,
        theme_mode: Optional[str] = None,
        view_density: Optional[str] = None,
        font_size: Optional[int] = None,
        compact_mode: Optional[bool] = None,
        show_avatars: Optional[bool] = None,
        message_preview_lines: Optional[int] = None,
        column_width_received: Optional[int] = None,
        column_width_from: Optional[int] = None,
        column_width_subject: Optional[int] = None,
    ) -> None:
        """Update appearance settings."""
        theme_changed = False

        if theme_mode is not None and theme_mode != self._settings.appearance.theme_mode:
            self._settings.appearance.theme_mode = theme_mode
            theme_changed = True
        if view_density is not None:
            self._settings.appearance.view_density = view_density
        if font_size is not None:
            self._settings.appearance.font_size = font_size
        if compact_mode is not None:
            self._settings.appearance.compact_mode = compact_mode
        if show_avatars is not None:
            self._settings.appearance.show_avatars = show_avatars
        if message_preview_lines is not None:
            self._settings.appearance.message_preview_lines = message_preview_lines
        if column_width_received is not None:
            self._settings.appearance.column_width_received = column_width_received
        if column_width_from is not None:
            self._settings.appearance.column_width_from = column_width_from
        if column_width_subject is not None:
            self._settings.appearance.column_width_subject = column_width_subject

        self._is_dirty = True

        if theme_changed:
            self.apply_theme()
            self.emit("theme-changed", self._settings.appearance.theme_mode)

        self.emit("settings-changed", "appearance")

    def update_notifications(
        self,
        desktop_notifications: Optional[bool] = None,
        notification_sound: Optional[bool] = None,
        notification_sound_path: Optional[str] = None,
        show_message_preview: Optional[bool] = None,
        notify_on_new_mail: Optional[bool] = None,
        notify_on_send_success: Optional[bool] = None,
        notify_on_error: Optional[bool] = None,
    ) -> None:
        """Update notification settings."""
        if desktop_notifications is not None:
            self._settings.notifications.desktop_notifications = desktop_notifications
        if notification_sound is not None:
            self._settings.notifications.notification_sound = notification_sound
        if notification_sound_path is not None:
            self._settings.notifications.notification_sound_path = notification_sound_path
        if show_message_preview is not None:
            self._settings.notifications.show_message_preview = show_message_preview
        if notify_on_new_mail is not None:
            self._settings.notifications.notify_on_new_mail = notify_on_new_mail
        if notify_on_send_success is not None:
            self._settings.notifications.notify_on_send_success = notify_on_send_success
        if notify_on_error is not None:
            self._settings.notifications.notify_on_error = notify_on_error

        self._is_dirty = True
        self.emit("settings-changed", "notifications")

    def update_advanced(
        self,
        cache_enabled: Optional[bool] = None,
        cache_size_mb: Optional[int] = None,
        cache_path: Optional[str] = None,
        log_level: Optional[str] = None,
        log_path: Optional[str] = None,
        sync_interval_seconds: Optional[int] = None,
        max_concurrent_connections: Optional[int] = None,
        show_quota: Optional[bool] = None,
        debug_mode: Optional[bool] = None,
    ) -> None:
        """Update advanced settings."""
        if cache_enabled is not None:
            self._settings.advanced.cache_enabled = cache_enabled
        if cache_size_mb is not None:
            self._settings.advanced.cache_size_mb = cache_size_mb
        if cache_path is not None:
            self._settings.advanced.cache_path = cache_path
        if log_level is not None:
            self._settings.advanced.log_level = log_level
        if log_path is not None:
            self._settings.advanced.log_path = log_path
        if sync_interval_seconds is not None:
            self._settings.advanced.sync_interval_seconds = sync_interval_seconds
        if max_concurrent_connections is not None:
            self._settings.advanced.max_concurrent_connections = max_concurrent_connections
        if show_quota is not None:
            self._settings.advanced.show_quota = show_quota
        if debug_mode is not None:
            self._settings.advanced.debug_mode = debug_mode

        self._is_dirty = True
        self.emit("settings-changed", "advanced")

    def is_dirty(self) -> bool:
        """Check if settings have unsaved changes."""
        return self._is_dirty

    def get_cache_path(self) -> Path:
        """Get the cache directory path."""
        if self._settings.advanced.cache_path:
            return Path(self._settings.advanced.cache_path)
        return Path(GLib.get_user_cache_dir()) / "unitmail"

    def get_log_path(self) -> Path:
        """Get the log directory path."""
        if self._settings.advanced.log_path:
            return Path(self._settings.advanced.log_path)
        return Path(GLib.get_user_data_dir()) / "unitmail" / "logs"

    def clear_cache(self) -> bool:
        """
        Clear the application cache.

        Returns:
            True if cache was cleared successfully.
        """
        cache_path = self.get_cache_path()

        try:
            if cache_path.exists():
                import shutil

                shutil.rmtree(cache_path)
                cache_path.mkdir(parents=True, exist_ok=True)

            logger.info("Cache cleared successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False

    def get_cache_size(self) -> int:
        """
        Get current cache size in bytes.

        Returns:
            Total size of cache directory in bytes.
        """
        cache_path = self.get_cache_path()

        if not cache_path.exists():
            return 0

        total_size = 0
        try:
            for path in cache_path.rglob("*"):
                if path.is_file():
                    total_size += path.stat().st_size
        except Exception as e:
            logger.warning(f"Error calculating cache size: {e}")

        return total_size

    def validate_server_settings(self) -> tuple[bool, list[str]]:
        """
        Validate server settings.

        Returns:
            Tuple of (is_valid, list of error messages).
        """
        errors = []
        server = self._settings.server

        if not server.gateway_url:
            errors.append("Gateway URL is required")
        elif not (
            server.gateway_url.startswith("http://")
            or server.gateway_url.startswith("https://")
        ):
            errors.append("Gateway URL must start with http:// or https://")

        if not server.smtp_host:
            errors.append("SMTP host is required")

        if not 1 <= server.smtp_port <= 65535:
            errors.append("SMTP port must be between 1 and 65535")

        if not 1 <= server.imap_port <= 65535:
            errors.append("IMAP port must be between 1 and 65535")

        return len(errors) == 0, errors

    def validate_email(self, email: str) -> bool:
        """
        Validate an email address format.

        Args:
            email: Email address to validate.

        Returns:
            True if email format is valid.
        """
        import re

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))


# Singleton instance
_settings_service: Optional[SettingsService] = None


def get_settings_service() -> SettingsService:
    """
    Get the global settings service instance.

    Returns:
        The singleton SettingsService instance.
    """
    global _settings_service

    if _settings_service is None:
        _settings_service = SettingsService()
        _settings_service.load()

    return _settings_service
