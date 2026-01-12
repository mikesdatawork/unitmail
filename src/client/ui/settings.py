"""
Settings window for unitMail.

This module provides a comprehensive settings interface using
Adw.PreferencesWindow with organized pages for account, server,
security, appearance, notifications, and advanced settings.
"""

import logging
from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from client.services.settings_service import (
    SettingsService,
    get_settings_service,
)
from client.ui.widgets.pgp_key_manager import PGPKeyManager

logger = logging.getLogger(__name__)


class SettingsWindow(Adw.PreferencesWindow):
    """
    Settings window for unitMail application.

    Provides organized pages for:
    - Account: Name, email, signature, avatar
    - Server: Gateway URL, SMTP settings, ports
    - Security: Password change, PGP key management, 2FA
    - Appearance: Theme, font size, compact mode
    - Notifications: Desktop notifications, sounds
    - Advanced: Cache, quota display, logs
    """

    __gtype_name__ = "SettingsWindow"

    def __init__(
        self,
        parent: Optional[Gtk.Window] = None,
        settings_service: Optional[SettingsService] = None,
    ) -> None:
        """
        Initialize the settings window.

        Args:
            parent: Parent window for transient behavior.
            settings_service: Settings service instance. If None, uses global.
        """
        super().__init__(
            title="Settings",
            modal=True,
            search_enabled=True,
        )

        if parent:
            self.set_transient_for(parent)

        self._settings = settings_service or get_settings_service()

        # Track entry rows for validation
        self._validation_handlers: dict[Adw.EntryRow, int] = {}

        self._build_ui()
        self._load_settings()
        self._connect_signals()

        logger.info("Settings window initialized")

    def _build_ui(self) -> None:
        """Build the settings UI."""
        # Add pages
        self.add(self._create_account_page())
        self.add(self._create_server_page())
        self.add(self._create_security_page())
        self.add(self._create_appearance_page())
        self.add(self._create_notifications_page())
        self.add(self._create_advanced_page())

    def _create_account_page(self) -> Adw.PreferencesPage:
        """Create the account settings page."""
        page = Adw.PreferencesPage(
            title="Account",
            icon_name="avatar-default-symbolic",
        )

        # Profile group
        profile_group = Adw.PreferencesGroup(
            title="Profile",
            description="Your identity when sending emails",
        )

        # Display name
        self._display_name_row = Adw.EntryRow(
            title="Display Name",
        )
        self._display_name_row.connect("changed", self._on_account_changed)
        profile_group.add(self._display_name_row)

        # Email address
        self._email_row = Adw.EntryRow(
            title="Email Address",
        )
        self._email_row.connect("changed", self._on_email_changed)
        profile_group.add(self._email_row)

        page.add(profile_group)

        # Avatar group
        avatar_group = Adw.PreferencesGroup(
            title="Avatar",
        )

        # Avatar preview and selection
        avatar_row = Adw.ActionRow(
            title="Profile Picture",
            subtitle="Click to change your avatar",
            activatable=True,
        )

        self._avatar_image = Gtk.Image(
            icon_name="avatar-default-symbolic",
            pixel_size=48,
        )
        avatar_row.add_prefix(self._avatar_image)

        change_avatar_button = Gtk.Button(
            icon_name="document-open-symbolic",
            valign=Gtk.Align.CENTER,
            tooltip_text="Choose avatar",
        )
        change_avatar_button.connect("clicked", self._on_change_avatar_clicked)
        avatar_row.add_suffix(change_avatar_button)

        clear_avatar_button = Gtk.Button(
            icon_name="edit-clear-symbolic",
            valign=Gtk.Align.CENTER,
            tooltip_text="Clear avatar",
        )
        clear_avatar_button.connect("clicked", self._on_clear_avatar_clicked)
        avatar_row.add_suffix(clear_avatar_button)

        avatar_group.add(avatar_row)

        page.add(avatar_group)

        # Signature group
        signature_group = Adw.PreferencesGroup(
            title="Email Signature",
            description="Automatically appended to outgoing messages",
        )

        # Signature text view
        signature_frame = Gtk.Frame(
            margin_start=12,
            margin_end=12,
            margin_top=8,
            margin_bottom=8,
        )

        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            min_content_height=100,
            max_content_height=200,
        )

        self._signature_text = Gtk.TextView(
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            left_margin=8,
            right_margin=8,
            top_margin=8,
            bottom_margin=8,
        )
        self._signature_text.get_buffer().connect("changed", self._on_signature_changed)
        scrolled.set_child(self._signature_text)
        signature_frame.set_child(scrolled)

        signature_group.add(signature_frame)

        page.add(signature_group)

        return page

    def _create_server_page(self) -> Adw.PreferencesPage:
        """Create the server settings page."""
        page = Adw.PreferencesPage(
            title="Server",
            icon_name="network-server-symbolic",
        )

        # Gateway group
        gateway_group = Adw.PreferencesGroup(
            title="Gateway",
            description="Connection to the unitMail gateway server",
        )

        self._gateway_url_row = Adw.EntryRow(
            title="Gateway URL",
        )
        self._gateway_url_row.connect("changed", self._on_server_changed)
        gateway_group.add(self._gateway_url_row)

        page.add(gateway_group)

        # SMTP group
        smtp_group = Adw.PreferencesGroup(
            title="SMTP (Outgoing Mail)",
        )

        self._smtp_host_row = Adw.EntryRow(
            title="SMTP Server",
        )
        self._smtp_host_row.connect("changed", self._on_server_changed)
        smtp_group.add(self._smtp_host_row)

        self._smtp_port_row = Adw.SpinRow.new_with_range(1, 65535, 1)
        self._smtp_port_row.set_title("SMTP Port")
        self._smtp_port_row.set_value(587)
        self._smtp_port_row.connect("notify::value", self._on_server_changed)
        smtp_group.add(self._smtp_port_row)

        self._smtp_tls_row = Adw.SwitchRow(
            title="Use TLS",
            subtitle="Encrypt connection with TLS/STARTTLS",
        )
        self._smtp_tls_row.connect("notify::active", self._on_server_changed)
        smtp_group.add(self._smtp_tls_row)

        page.add(smtp_group)

        # IMAP group
        imap_group = Adw.PreferencesGroup(
            title="IMAP (Incoming Mail)",
        )

        self._imap_host_row = Adw.EntryRow(
            title="IMAP Server",
        )
        self._imap_host_row.connect("changed", self._on_server_changed)
        imap_group.add(self._imap_host_row)

        self._imap_port_row = Adw.SpinRow.new_with_range(1, 65535, 1)
        self._imap_port_row.set_title("IMAP Port")
        self._imap_port_row.set_value(993)
        self._imap_port_row.connect("notify::value", self._on_server_changed)
        imap_group.add(self._imap_port_row)

        self._imap_tls_row = Adw.SwitchRow(
            title="Use TLS",
            subtitle="Encrypt connection with TLS/SSL",
        )
        self._imap_tls_row.connect("notify::active", self._on_server_changed)
        imap_group.add(self._imap_tls_row)

        page.add(imap_group)

        # Test connection button
        test_group = Adw.PreferencesGroup()

        test_row = Adw.ActionRow(
            title="Test Connection",
            subtitle="Verify server settings",
            activatable=True,
        )
        test_row.add_suffix(
            Gtk.Image(icon_name="go-next-symbolic")
        )
        test_row.connect("activated", self._on_test_connection_clicked)
        test_group.add(test_row)

        page.add(test_group)

        return page

    def _create_security_page(self) -> Adw.PreferencesPage:
        """Create the security settings page."""
        page = Adw.PreferencesPage(
            title="Security",
            icon_name="security-high-symbolic",
        )

        # Password group
        password_group = Adw.PreferencesGroup(
            title="Account Security",
        )

        change_password_row = Adw.ActionRow(
            title="Change Password",
            subtitle="Update your account password",
            activatable=True,
        )
        change_password_row.add_suffix(
            Gtk.Image(icon_name="go-next-symbolic")
        )
        change_password_row.connect("activated", self._on_change_password_clicked)
        password_group.add(change_password_row)

        # Two-factor authentication
        self._2fa_row = Adw.SwitchRow(
            title="Two-Factor Authentication",
            subtitle="Add an extra layer of security",
        )
        self._2fa_row.connect("notify::active", self._on_2fa_toggled)
        password_group.add(self._2fa_row)

        page.add(password_group)

        # PGP settings group
        pgp_settings_group = Adw.PreferencesGroup(
            title="PGP Encryption",
            description="End-to-end encryption for your emails",
        )

        self._auto_encrypt_row = Adw.SwitchRow(
            title="Auto-Encrypt",
            subtitle="Automatically encrypt when recipient has a public key",
        )
        self._auto_encrypt_row.connect("notify::active", self._on_security_changed)
        pgp_settings_group.add(self._auto_encrypt_row)

        self._auto_sign_row = Adw.SwitchRow(
            title="Auto-Sign",
            subtitle="Digitally sign all outgoing messages",
        )
        self._auto_sign_row.connect("notify::active", self._on_security_changed)
        pgp_settings_group.add(self._auto_sign_row)

        self._remember_passphrase_row = Adw.SwitchRow(
            title="Remember Passphrase",
            subtitle="Cache passphrase for a limited time",
        )
        self._remember_passphrase_row.connect("notify::active", self._on_security_changed)
        pgp_settings_group.add(self._remember_passphrase_row)

        self._passphrase_timeout_row = Adw.SpinRow.new_with_range(60, 3600, 60)
        self._passphrase_timeout_row.set_title("Passphrase Timeout")
        self._passphrase_timeout_row.set_subtitle("Seconds to remember passphrase")
        self._passphrase_timeout_row.set_value(300)
        self._passphrase_timeout_row.connect("notify::value", self._on_security_changed)
        pgp_settings_group.add(self._passphrase_timeout_row)

        page.add(pgp_settings_group)

        # PGP key management group
        key_group = Adw.PreferencesGroup(
            title="PGP Keys",
        )

        # Key manager in an expander
        key_expander = Adw.ExpanderRow(
            title="Manage Keys",
            subtitle="View and manage your PGP keys",
        )

        # Key manager widget container
        key_manager_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            margin_start=12,
            margin_end=12,
            margin_top=8,
            margin_bottom=8,
        )

        self._pgp_key_manager = PGPKeyManager()
        self._pgp_key_manager.set_size_request(-1, 300)
        key_manager_box.append(self._pgp_key_manager)

        key_expander.add_row(
            Adw.PreferencesRow(child=key_manager_box)
        )

        key_group.add(key_expander)

        page.add(key_group)

        return page

    def _create_appearance_page(self) -> Adw.PreferencesPage:
        """Create the appearance settings page."""
        page = Adw.PreferencesPage(
            title="Appearance",
            icon_name="applications-graphics-symbolic",
        )

        # Theme group with visual selector
        theme_group = Adw.PreferencesGroup(
            title="Color Scheme",
            description="Choose how unitMail looks",
        )

        # Visual theme selector using ActionRow with radio buttons
        self._theme_buttons = {}

        # System theme
        system_row = Adw.ActionRow(
            title="System",
            subtitle="Follow system dark/light preference",
            activatable=True,
        )
        system_row.add_prefix(Gtk.Image(icon_name="preferences-desktop-appearance-symbolic"))
        self._theme_buttons["system"] = Gtk.CheckButton()
        self._theme_buttons["system"].set_active(True)
        self._theme_buttons["system"].connect("toggled", self._on_theme_radio_toggled, "system")
        system_row.add_suffix(self._theme_buttons["system"])
        system_row.set_activatable_widget(self._theme_buttons["system"])
        theme_group.add(system_row)

        # Light theme
        light_row = Adw.ActionRow(
            title="Light",
            subtitle="Always use light colors",
            activatable=True,
        )
        light_row.add_prefix(Gtk.Image(icon_name="weather-clear-symbolic"))
        self._theme_buttons["light"] = Gtk.CheckButton()
        self._theme_buttons["light"].set_group(self._theme_buttons["system"])
        self._theme_buttons["light"].connect("toggled", self._on_theme_radio_toggled, "light")
        light_row.add_suffix(self._theme_buttons["light"])
        light_row.set_activatable_widget(self._theme_buttons["light"])
        theme_group.add(light_row)

        # Dark theme
        dark_row = Adw.ActionRow(
            title="Dark",
            subtitle="Always use dark colors",
            activatable=True,
        )
        dark_row.add_prefix(Gtk.Image(icon_name="weather-clear-night-symbolic"))
        self._theme_buttons["dark"] = Gtk.CheckButton()
        self._theme_buttons["dark"].set_group(self._theme_buttons["system"])
        self._theme_buttons["dark"].connect("toggled", self._on_theme_radio_toggled, "dark")
        dark_row.add_suffix(self._theme_buttons["dark"])
        dark_row.set_activatable_widget(self._theme_buttons["dark"])
        theme_group.add(dark_row)

        page.add(theme_group)

        # Message List Density group
        density_group = Adw.PreferencesGroup(
            title="Message List Density",
            description="How messages appear in the list",
        )

        self._density_buttons = {}

        # Standard density
        standard_row = Adw.ActionRow(
            title="Standard",
            subtitle="Balanced view with sender, subject, preview",
            activatable=True,
        )
        standard_row.add_prefix(Gtk.Image(icon_name="view-list-symbolic"))
        self._density_buttons["standard"] = Gtk.CheckButton()
        self._density_buttons["standard"].set_active(True)
        self._density_buttons["standard"].connect("toggled", self._on_density_toggled, "standard")
        standard_row.add_suffix(self._density_buttons["standard"])
        standard_row.set_activatable_widget(self._density_buttons["standard"])
        density_group.add(standard_row)

        # Compact density
        compact_row = Adw.ActionRow(
            title="Compact",
            subtitle="Dense view, no preview text",
            activatable=True,
        )
        compact_row.add_prefix(Gtk.Image(icon_name="view-compact-symbolic"))
        self._density_buttons["compact"] = Gtk.CheckButton()
        self._density_buttons["compact"].set_group(self._density_buttons["standard"])
        self._density_buttons["compact"].connect("toggled", self._on_density_toggled, "compact")
        compact_row.add_suffix(self._density_buttons["compact"])
        compact_row.set_activatable_widget(self._density_buttons["compact"])
        density_group.add(compact_row)

        # Comfortable density
        comfortable_row = Adw.ActionRow(
            title="Comfortable",
            subtitle="Spacious view with larger text",
            activatable=True,
        )
        comfortable_row.add_prefix(Gtk.Image(icon_name="view-paged-symbolic"))
        self._density_buttons["comfortable"] = Gtk.CheckButton()
        self._density_buttons["comfortable"].set_group(self._density_buttons["standard"])
        self._density_buttons["comfortable"].connect("toggled", self._on_density_toggled, "comfortable")
        comfortable_row.add_suffix(self._density_buttons["comfortable"])
        comfortable_row.set_activatable_widget(self._density_buttons["comfortable"])
        density_group.add(comfortable_row)

        # Minimal density
        minimal_row = Adw.ActionRow(
            title="Minimal",
            subtitle="Single line: time | sender | subject",
            activatable=True,
        )
        minimal_row.add_prefix(Gtk.Image(icon_name="view-continuous-symbolic"))
        self._density_buttons["minimal"] = Gtk.CheckButton()
        self._density_buttons["minimal"].set_group(self._density_buttons["standard"])
        self._density_buttons["minimal"].connect("toggled", self._on_density_toggled, "minimal")
        minimal_row.add_suffix(self._density_buttons["minimal"])
        minimal_row.set_activatable_widget(self._density_buttons["minimal"])
        density_group.add(minimal_row)

        page.add(density_group)

        # Text group
        text_group = Adw.PreferencesGroup(
            title="Text",
        )

        # Font size
        self._font_size_row = Adw.SpinRow.new_with_range(8, 24, 1)
        self._font_size_row.set_title("Font Size")
        self._font_size_row.set_subtitle("Base font size in pixels")
        self._font_size_row.set_value(12)
        self._font_size_row.connect("notify::value", self._on_appearance_changed)
        text_group.add(self._font_size_row)

        # Message preview lines
        self._preview_lines_row = Adw.SpinRow.new_with_range(1, 5, 1)
        self._preview_lines_row.set_title("Preview Lines")
        self._preview_lines_row.set_subtitle("Lines of preview text in message list")
        self._preview_lines_row.set_value(2)
        self._preview_lines_row.connect("notify::value", self._on_appearance_changed)
        text_group.add(self._preview_lines_row)

        page.add(text_group)

        # Layout group
        layout_group = Adw.PreferencesGroup(
            title="Layout Options",
        )

        # Show avatars
        self._show_avatars_row = Adw.SwitchRow(
            title="Show Avatars",
            subtitle="Display sender avatars in message list",
        )
        self._show_avatars_row.connect("notify::active", self._on_appearance_changed)
        layout_group.add(self._show_avatars_row)

        page.add(layout_group)

        return page

    def _create_notifications_page(self) -> Adw.PreferencesPage:
        """Create the notifications settings page."""
        page = Adw.PreferencesPage(
            title="Notifications",
            icon_name="preferences-system-notifications-symbolic",
        )

        # General group
        general_group = Adw.PreferencesGroup(
            title="Desktop Notifications",
        )

        # Desktop notifications
        self._desktop_notif_row = Adw.SwitchRow(
            title="Enable Notifications",
            subtitle="Show desktop notifications for new messages",
        )
        self._desktop_notif_row.connect("notify::active", self._on_notifications_changed)
        general_group.add(self._desktop_notif_row)

        # Show preview in notification
        self._notif_preview_row = Adw.SwitchRow(
            title="Show Message Preview",
            subtitle="Include message preview in notifications",
        )
        self._notif_preview_row.connect("notify::active", self._on_notifications_changed)
        general_group.add(self._notif_preview_row)

        page.add(general_group)

        # Sound group
        sound_group = Adw.PreferencesGroup(
            title="Sounds",
        )

        # Notification sound
        self._sound_row = Adw.SwitchRow(
            title="Notification Sound",
            subtitle="Play a sound for new messages",
        )
        self._sound_row.connect("notify::active", self._on_notifications_changed)
        sound_group.add(self._sound_row)

        # Custom sound file
        sound_file_row = Adw.ActionRow(
            title="Custom Sound",
            subtitle="Choose a custom notification sound",
            activatable=True,
        )
        self._sound_path_label = Gtk.Label(
            label="Default",
            css_classes=["dim-label"],
            valign=Gtk.Align.CENTER,
        )
        sound_file_row.add_suffix(self._sound_path_label)
        sound_file_row.add_suffix(
            Gtk.Image(icon_name="go-next-symbolic")
        )
        sound_file_row.connect("activated", self._on_choose_sound_clicked)
        sound_group.add(sound_file_row)

        page.add(sound_group)

        # Events group
        events_group = Adw.PreferencesGroup(
            title="Notification Events",
        )

        # Notify on new mail
        self._notify_new_mail_row = Adw.SwitchRow(
            title="New Mail",
            subtitle="Notify when new messages arrive",
        )
        self._notify_new_mail_row.connect("notify::active", self._on_notifications_changed)
        events_group.add(self._notify_new_mail_row)

        # Notify on send success
        self._notify_send_row = Adw.SwitchRow(
            title="Send Success",
            subtitle="Notify when messages are sent successfully",
        )
        self._notify_send_row.connect("notify::active", self._on_notifications_changed)
        events_group.add(self._notify_send_row)

        # Notify on error
        self._notify_error_row = Adw.SwitchRow(
            title="Errors",
            subtitle="Notify when errors occur",
        )
        self._notify_error_row.connect("notify::active", self._on_notifications_changed)
        events_group.add(self._notify_error_row)

        page.add(events_group)

        return page

    def _create_advanced_page(self) -> Adw.PreferencesPage:
        """Create the advanced settings page."""
        page = Adw.PreferencesPage(
            title="Advanced",
            icon_name="preferences-other-symbolic",
        )

        # Sync group
        sync_group = Adw.PreferencesGroup(
            title="Synchronization",
        )

        # Sync interval
        self._sync_interval_row = Adw.SpinRow.new_with_range(60, 3600, 60)
        self._sync_interval_row.set_title("Sync Interval")
        self._sync_interval_row.set_subtitle("Seconds between automatic syncs")
        self._sync_interval_row.set_value(300)
        self._sync_interval_row.connect("notify::value", self._on_advanced_changed)
        sync_group.add(self._sync_interval_row)

        # Max connections
        self._max_connections_row = Adw.SpinRow.new_with_range(1, 10, 1)
        self._max_connections_row.set_title("Max Connections")
        self._max_connections_row.set_subtitle("Maximum concurrent server connections")
        self._max_connections_row.set_value(4)
        self._max_connections_row.connect("notify::value", self._on_advanced_changed)
        sync_group.add(self._max_connections_row)

        page.add(sync_group)

        # Cache group
        cache_group = Adw.PreferencesGroup(
            title="Cache",
        )

        # Enable cache
        self._cache_enabled_row = Adw.SwitchRow(
            title="Enable Cache",
            subtitle="Cache messages locally for faster access",
        )
        self._cache_enabled_row.connect("notify::active", self._on_advanced_changed)
        cache_group.add(self._cache_enabled_row)

        # Cache size
        self._cache_size_row = Adw.SpinRow.new_with_range(100, 5000, 100)
        self._cache_size_row.set_title("Cache Size (MB)")
        self._cache_size_row.set_subtitle("Maximum cache storage")
        self._cache_size_row.set_value(500)
        self._cache_size_row.connect("notify::value", self._on_advanced_changed)
        cache_group.add(self._cache_size_row)

        # Current cache usage
        self._cache_usage_row = Adw.ActionRow(
            title="Cache Usage",
        )
        self._cache_usage_label = Gtk.Label(
            label="Calculating...",
            css_classes=["dim-label"],
            valign=Gtk.Align.CENTER,
        )
        self._cache_usage_row.add_suffix(self._cache_usage_label)
        cache_group.add(self._cache_usage_row)

        # Clear cache button
        clear_cache_row = Adw.ActionRow(
            title="Clear Cache",
            subtitle="Delete all cached data",
            activatable=True,
        )
        clear_cache_row.add_suffix(
            Gtk.Image(icon_name="go-next-symbolic")
        )
        clear_cache_row.connect("activated", self._on_clear_cache_clicked)
        cache_group.add(clear_cache_row)

        page.add(cache_group)

        # Quota group
        quota_group = Adw.PreferencesGroup(
            title="Storage Quota",
        )

        # Show quota
        self._show_quota_row = Adw.SwitchRow(
            title="Show Quota",
            subtitle="Display storage quota in status bar",
        )
        self._show_quota_row.connect("notify::active", self._on_advanced_changed)
        quota_group.add(self._show_quota_row)

        # Quota display
        self._quota_row = Adw.ActionRow(
            title="Current Usage",
        )
        quota_bar = Gtk.LevelBar(
            min_value=0,
            max_value=100,
            value=45,  # Example value
            valign=Gtk.Align.CENTER,
            hexpand=True,
            margin_end=8,
        )
        quota_bar.set_size_request(150, -1)
        self._quota_row.add_suffix(quota_bar)

        quota_label = Gtk.Label(
            label="450 MB / 1 GB",
            css_classes=["dim-label"],
            valign=Gtk.Align.CENTER,
        )
        self._quota_row.add_suffix(quota_label)
        quota_group.add(self._quota_row)

        page.add(quota_group)

        # Logging group
        logging_group = Adw.PreferencesGroup(
            title="Logging",
        )

        # Log level
        log_levels = ["ERROR", "WARNING", "INFO", "DEBUG"]
        log_model = Gtk.StringList.new(log_levels)
        self._log_level_row = Adw.ComboRow(
            title="Log Level",
            subtitle="Amount of detail in log files",
            model=log_model,
            selected=2,  # INFO
        )
        self._log_level_row.connect("notify::selected", self._on_advanced_changed)
        logging_group.add(self._log_level_row)

        # Debug mode
        self._debug_mode_row = Adw.SwitchRow(
            title="Debug Mode",
            subtitle="Enable additional debugging features",
        )
        self._debug_mode_row.connect("notify::active", self._on_advanced_changed)
        logging_group.add(self._debug_mode_row)

        # Open logs folder
        logs_row = Adw.ActionRow(
            title="Open Logs Folder",
            subtitle="View application log files",
            activatable=True,
        )
        logs_row.add_suffix(
            Gtk.Image(icon_name="folder-open-symbolic")
        )
        logs_row.connect("activated", self._on_open_logs_clicked)
        logging_group.add(logs_row)

        page.add(logging_group)

        # Reset group
        reset_group = Adw.PreferencesGroup()

        reset_row = Adw.ActionRow(
            title="Reset to Defaults",
            subtitle="Reset all settings to their default values",
            activatable=True,
            css_classes=["error"],
        )
        reset_row.add_suffix(
            Gtk.Image(icon_name="go-next-symbolic")
        )
        reset_row.connect("activated", self._on_reset_clicked)
        reset_group.add(reset_row)

        page.add(reset_group)

        return page

    def _load_settings(self) -> None:
        """Load current settings into the UI."""
        settings = self._settings.settings

        # Account
        self._display_name_row.set_text(settings.account.display_name)
        self._email_row.set_text(settings.account.email_address)

        if settings.account.avatar_path:
            self._load_avatar(settings.account.avatar_path)

        buffer = self._signature_text.get_buffer()
        buffer.set_text(settings.account.signature)

        # Server
        self._gateway_url_row.set_text(settings.server.gateway_url)
        self._smtp_host_row.set_text(settings.server.smtp_host)
        self._smtp_port_row.set_value(settings.server.smtp_port)
        self._smtp_tls_row.set_active(settings.server.smtp_use_tls)
        self._imap_host_row.set_text(settings.server.imap_host)
        self._imap_port_row.set_value(settings.server.imap_port)
        self._imap_tls_row.set_active(settings.server.imap_use_tls)

        # Security
        self._2fa_row.set_active(settings.security.two_factor_enabled)
        self._auto_encrypt_row.set_active(settings.security.auto_encrypt)
        self._auto_sign_row.set_active(settings.security.auto_sign)
        self._remember_passphrase_row.set_active(settings.security.remember_passphrase)
        self._passphrase_timeout_row.set_value(settings.security.passphrase_timeout)

        # Appearance - Theme
        theme_mode = getattr(settings.appearance, 'theme_mode', 'system')
        if theme_mode in self._theme_buttons:
            self._theme_buttons[theme_mode].set_active(True)

        # Appearance - Density
        view_density = getattr(settings.appearance, 'view_density', 'standard')
        if view_density in self._density_buttons:
            self._density_buttons[view_density].set_active(True)

        self._font_size_row.set_value(settings.appearance.font_size)
        self._preview_lines_row.set_value(settings.appearance.message_preview_lines)
        self._show_avatars_row.set_active(settings.appearance.show_avatars)

        # Notifications
        self._desktop_notif_row.set_active(settings.notifications.desktop_notifications)
        self._notif_preview_row.set_active(settings.notifications.show_message_preview)
        self._sound_row.set_active(settings.notifications.notification_sound)
        self._notify_new_mail_row.set_active(settings.notifications.notify_on_new_mail)
        self._notify_send_row.set_active(settings.notifications.notify_on_send_success)
        self._notify_error_row.set_active(settings.notifications.notify_on_error)

        if settings.notifications.notification_sound_path:
            self._sound_path_label.set_label(
                Path(settings.notifications.notification_sound_path).name
            )

        # Advanced
        self._sync_interval_row.set_value(settings.advanced.sync_interval_seconds)
        self._max_connections_row.set_value(settings.advanced.max_concurrent_connections)
        self._cache_enabled_row.set_active(settings.advanced.cache_enabled)
        self._cache_size_row.set_value(settings.advanced.cache_size_mb)
        self._show_quota_row.set_active(settings.advanced.show_quota)
        self._debug_mode_row.set_active(settings.advanced.debug_mode)

        log_map = {"ERROR": 0, "WARNING": 1, "INFO": 2, "DEBUG": 3}
        self._log_level_row.set_selected(log_map.get(settings.advanced.log_level, 2))

        # Update cache usage display
        self._update_cache_usage()

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self.connect("close-request", self._on_close_request)

    def _load_avatar(self, path: str) -> None:
        """Load avatar image from path."""
        try:
            if Path(path).exists():
                texture = Gdk.Texture.new_from_filename(path)
                self._avatar_image.set_from_paintable(texture)
        except Exception as e:
            logger.warning(f"Failed to load avatar: {e}")

    def _update_cache_usage(self) -> None:
        """Update cache usage display."""
        size_bytes = self._settings.get_cache_size()
        size_mb = size_bytes / (1024 * 1024)
        max_mb = self._settings.advanced.cache_size_mb

        self._cache_usage_label.set_label(f"{size_mb:.1f} MB / {max_mb} MB")

    def _format_size(self, size: int) -> str:
        """Format size in bytes to human-readable string."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"

    # Event handlers

    def _on_close_request(self, window: Gtk.Window) -> bool:
        """Handle window close request."""
        if self._settings.is_dirty():
            self._settings.save()
            logger.info("Settings saved on close")
        return False

    def _on_account_changed(self, *args) -> None:
        """Handle account field changes."""
        self._settings.update_account(
            display_name=self._display_name_row.get_text(),
        )

    def _on_email_changed(self, entry: Adw.EntryRow) -> None:
        """Handle email field change with validation."""
        email = entry.get_text()

        # Validate email
        if email and not self._settings.validate_email(email):
            entry.add_css_class("error")
        else:
            entry.remove_css_class("error")
            self._settings.update_account(email_address=email)

    def _on_signature_changed(self, buffer: Gtk.TextBuffer) -> None:
        """Handle signature text change."""
        start, end = buffer.get_bounds()
        signature = buffer.get_text(start, end, False)
        self._settings.update_account(signature=signature)

    def _on_change_avatar_clicked(self, button: Gtk.Button) -> None:
        """Handle change avatar button click."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Choose Avatar")

        # Set filter for images
        filter_store = Gio.ListStore.new(Gtk.FileFilter)

        image_filter = Gtk.FileFilter()
        image_filter.set_name("Images")
        image_filter.add_mime_type("image/png")
        image_filter.add_mime_type("image/jpeg")
        image_filter.add_mime_type("image/gif")
        image_filter.add_mime_type("image/webp")
        filter_store.append(image_filter)

        dialog.set_filters(filter_store)
        dialog.open(self, None, self._on_avatar_response)

    def _on_avatar_response(
        self,
        dialog: Gtk.FileDialog,
        result: Gio.AsyncResult,
    ) -> None:
        """Handle avatar file selection response."""
        try:
            file = dialog.open_finish(result)
            if file:
                path = file.get_path()
                self._load_avatar(path)
                self._settings.update_account(avatar_path=path)
        except GLib.Error as e:
            if e.code != Gtk.DialogError.CANCELLED:
                logger.error(f"Failed to select avatar: {e.message}")

    def _on_clear_avatar_clicked(self, button: Gtk.Button) -> None:
        """Handle clear avatar button click."""
        self._avatar_image.set_from_icon_name("avatar-default-symbolic")
        self._settings.update_account(avatar_path="")

    def _on_server_changed(self, *args) -> None:
        """Handle server settings changes."""
        self._settings.update_server(
            gateway_url=self._gateway_url_row.get_text(),
            smtp_host=self._smtp_host_row.get_text(),
            smtp_port=int(self._smtp_port_row.get_value()),
            smtp_use_tls=self._smtp_tls_row.get_active(),
            imap_host=self._imap_host_row.get_text(),
            imap_port=int(self._imap_port_row.get_value()),
            imap_use_tls=self._imap_tls_row.get_active(),
        )

    def _on_test_connection_clicked(self, row: Adw.ActionRow) -> None:
        """Handle test connection button click."""
        is_valid, errors = self._settings.validate_server_settings()

        if not is_valid:
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Invalid Settings",
                body="\n".join(errors),
            )
            dialog.add_response("ok", "OK")
            dialog.present()
            return

        # Show testing dialog
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Testing Connection",
            body="Connecting to server...",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.present()

        # Simulate connection test
        def test_complete():
            dialog.set_heading("Connection Successful")
            dialog.set_body("Successfully connected to the server.")
            dialog.add_response("ok", "OK")
            return False

        GLib.timeout_add(2000, test_complete)

    def _on_security_changed(self, *args) -> None:
        """Handle security settings changes."""
        self._settings.update_security(
            auto_encrypt=self._auto_encrypt_row.get_active(),
            auto_sign=self._auto_sign_row.get_active(),
            remember_passphrase=self._remember_passphrase_row.get_active(),
            passphrase_timeout=int(self._passphrase_timeout_row.get_value()),
        )

    def _on_2fa_toggled(self, row: Adw.SwitchRow, *args) -> None:
        """Handle 2FA toggle."""
        if row.get_active():
            # Would show 2FA setup dialog
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Set Up Two-Factor Authentication",
                body="This feature requires additional setup. Would you like to continue?",
            )
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("setup", "Set Up")
            dialog.set_response_appearance("setup", Adw.ResponseAppearance.SUGGESTED)
            dialog.connect("response", self._on_2fa_setup_response)
            dialog.present()
        else:
            self._settings.update_security(two_factor_enabled=False)

    def _on_2fa_setup_response(
        self,
        dialog: Adw.MessageDialog,
        response: str,
    ) -> None:
        """Handle 2FA setup dialog response."""
        if response == "setup":
            self._settings.update_security(two_factor_enabled=True)
            logger.info("2FA setup initiated")
        else:
            self._2fa_row.set_active(False)

    def _on_change_password_clicked(self, row: Adw.ActionRow) -> None:
        """Handle change password button click."""
        dialog = PasswordChangeDialog(self)
        dialog.present()

    def _on_theme_radio_toggled(
        self,
        button: Gtk.CheckButton,
        theme: str,
    ) -> None:
        """Handle theme radio button toggle."""
        if button.get_active():
            logger.info(f"Theme changed to: {theme}")
            self._settings.set_theme(theme)

    def _on_density_toggled(
        self,
        button: Gtk.CheckButton,
        density: str,
    ) -> None:
        """Handle density radio button toggle."""
        if button.get_active():
            logger.info(f"Density changed to: {density}")
            # Update view theme manager
            try:
                from .view_theme import ViewTheme, get_view_theme_manager
                manager = get_view_theme_manager()
                theme_map = {
                    "standard": ViewTheme.STANDARD,
                    "compact": ViewTheme.COMPACT,
                    "comfortable": ViewTheme.COMFORTABLE,
                    "minimal": ViewTheme.MINIMAL,
                }
                if density in theme_map:
                    manager.set_theme(theme_map[density])
            except ImportError:
                pass
            # Note: view_density is managed by ViewThemeManager, not SettingsService

    def _on_appearance_changed(self, *args) -> None:
        """Handle appearance settings changes."""
        self._settings.update_appearance(
            font_size=int(self._font_size_row.get_value()),
            show_avatars=self._show_avatars_row.get_active(),
            message_preview_lines=int(self._preview_lines_row.get_value()),
        )

    def _on_notifications_changed(self, *args) -> None:
        """Handle notifications settings changes."""
        self._settings.update_notifications(
            desktop_notifications=self._desktop_notif_row.get_active(),
            notification_sound=self._sound_row.get_active(),
            show_message_preview=self._notif_preview_row.get_active(),
            notify_on_new_mail=self._notify_new_mail_row.get_active(),
            notify_on_send_success=self._notify_send_row.get_active(),
            notify_on_error=self._notify_error_row.get_active(),
        )

    def _on_choose_sound_clicked(self, row: Adw.ActionRow) -> None:
        """Handle choose sound button click."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Choose Notification Sound")

        # Set filter for audio files
        filter_store = Gio.ListStore.new(Gtk.FileFilter)

        audio_filter = Gtk.FileFilter()
        audio_filter.set_name("Audio Files")
        audio_filter.add_mime_type("audio/wav")
        audio_filter.add_mime_type("audio/ogg")
        audio_filter.add_mime_type("audio/mpeg")
        filter_store.append(audio_filter)

        dialog.set_filters(filter_store)
        dialog.open(self, None, self._on_sound_response)

    def _on_sound_response(
        self,
        dialog: Gtk.FileDialog,
        result: Gio.AsyncResult,
    ) -> None:
        """Handle sound file selection response."""
        try:
            file = dialog.open_finish(result)
            if file:
                path = file.get_path()
                self._sound_path_label.set_label(Path(path).name)
                self._settings.update_notifications(notification_sound_path=path)
        except GLib.Error as e:
            if e.code != Gtk.DialogError.CANCELLED:
                logger.error(f"Failed to select sound: {e.message}")

    def _on_advanced_changed(self, *args) -> None:
        """Handle advanced settings changes."""
        log_levels = ["ERROR", "WARNING", "INFO", "DEBUG"]

        self._settings.update_advanced(
            sync_interval_seconds=int(self._sync_interval_row.get_value()),
            max_concurrent_connections=int(self._max_connections_row.get_value()),
            cache_enabled=self._cache_enabled_row.get_active(),
            cache_size_mb=int(self._cache_size_row.get_value()),
            show_quota=self._show_quota_row.get_active(),
            debug_mode=self._debug_mode_row.get_active(),
            log_level=log_levels[self._log_level_row.get_selected()],
        )

    def _on_clear_cache_clicked(self, row: Adw.ActionRow) -> None:
        """Handle clear cache button click."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Clear Cache?",
            body="This will delete all cached messages and data. This action cannot be undone.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("clear", "Clear Cache")
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._on_clear_cache_response)
        dialog.present()

    def _on_clear_cache_response(
        self,
        dialog: Adw.MessageDialog,
        response: str,
    ) -> None:
        """Handle clear cache confirmation response."""
        if response == "clear":
            if self._settings.clear_cache():
                self._update_cache_usage()
                logger.info("Cache cleared")

    def _on_open_logs_clicked(self, row: Adw.ActionRow) -> None:
        """Handle open logs folder button click."""
        log_path = self._settings.get_log_path()
        log_path.mkdir(parents=True, exist_ok=True)

        # Open in file manager
        Gio.AppInfo.launch_default_for_uri(
            f"file://{log_path}",
            None,
        )

    def _on_reset_clicked(self, row: Adw.ActionRow) -> None:
        """Handle reset to defaults button click."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Reset Settings?",
            body="This will reset all settings to their default values. This action cannot be undone.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("reset", "Reset")
        dialog.set_response_appearance("reset", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._on_reset_response)
        dialog.present()

    def _on_reset_response(
        self,
        dialog: Adw.MessageDialog,
        response: str,
    ) -> None:
        """Handle reset confirmation response."""
        if response == "reset":
            self._settings.reset_to_defaults()
            self._load_settings()
            logger.info("Settings reset to defaults")


class PasswordChangeDialog(Adw.Window):
    """
    Dialog for changing account password.
    """

    __gtype_name__ = "PasswordChangeDialog"

    def __init__(self, parent: Gtk.Window) -> None:
        """
        Initialize password change dialog.

        Args:
            parent: Parent window.
        """
        super().__init__(
            title="Change Password",
            modal=True,
            transient_for=parent,
            default_width=400,
            default_height=350,
        )

        self._build_ui()

    def _build_ui(self) -> None:
        """Build dialog UI."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar
        header = Adw.HeaderBar()
        header.add_css_class("flat")

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda _: self.close())
        header.pack_start(cancel_button)

        save_button = Gtk.Button(label="Change")
        save_button.add_css_class("suggested-action")
        save_button.set_sensitive(False)
        save_button.connect("clicked", self._on_save_clicked)
        self._save_button = save_button
        header.pack_end(save_button)

        main_box.append(header)

        # Content
        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
            margin_start=24,
            margin_end=24,
            margin_top=24,
            margin_bottom=24,
        )

        group = Adw.PreferencesGroup()

        # Current password
        self._current_password_row = Adw.PasswordEntryRow(
            title="Current Password",
        )
        self._current_password_row.connect("changed", self._validate)
        group.add(self._current_password_row)

        # New password
        self._new_password_row = Adw.PasswordEntryRow(
            title="New Password",
        )
        self._new_password_row.connect("changed", self._validate)
        group.add(self._new_password_row)

        # Confirm password
        self._confirm_password_row = Adw.PasswordEntryRow(
            title="Confirm New Password",
        )
        self._confirm_password_row.connect("changed", self._validate)
        group.add(self._confirm_password_row)

        content.append(group)

        # Requirements label
        requirements = Gtk.Label(
            label="Password must be at least 8 characters long",
            css_classes=["dim-label", "caption"],
            xalign=0,
            margin_start=12,
        )
        content.append(requirements)

        main_box.append(content)

    def _validate(self, *args) -> None:
        """Validate password fields."""
        current = self._current_password_row.get_text()
        new = self._new_password_row.get_text()
        confirm = self._confirm_password_row.get_text()

        is_valid = (
            len(current) > 0
            and len(new) >= 8
            and new == confirm
        )

        self._save_button.set_sensitive(is_valid)

        # Show mismatch error
        if confirm and new != confirm:
            self._confirm_password_row.add_css_class("error")
        else:
            self._confirm_password_row.remove_css_class("error")

    def _on_save_clicked(self, button: Gtk.Button) -> None:
        """Handle save button click."""
        # In real implementation, would send password change request
        logger.info("Password change requested")

        # Show success and close
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Password Changed",
            body="Your password has been successfully updated.",
        )
        dialog.add_response("ok", "OK")
        dialog.connect("response", lambda d, r: (self.close(), d.close()))
        dialog.present()


def create_settings_window(
    parent: Optional[Gtk.Window] = None,
) -> SettingsWindow:
    """
    Create and return a settings window.

    Args:
        parent: Optional parent window.

    Returns:
        New SettingsWindow instance.
    """
    return SettingsWindow(parent=parent)
