"""
Settings window for unitMail.

This module provides a comprehensive settings interface using
a sidebar navigation pattern with organized pages for account, server,
security, appearance, notifications, database, and advanced settings.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import gi

if TYPE_CHECKING:
    import cairo

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Adw, GdkPixbuf, Gio, GLib, Gtk

from client.services.settings_service import (
    SettingsService,
    get_settings_service,
)
from common.local_storage import get_local_storage
from .widgets.pgp_key_manager import PGPKeyManager

logger = logging.getLogger(__name__)


class VerticalBarChart(Gtk.DrawingArea):
    """A vertical bar chart widget using Cairo."""

    __gtype_name__ = "VerticalBarChart"

    def __init__(
        self,
        data: list[tuple[str, float]] = None,
        max_value: float = 100,
        bar_color: str = "#3584e4",
        height: int = 120,
    ) -> None:
        super().__init__()

        self._data = data or []
        self._max_value = max_value
        self._bar_color = bar_color

        self.set_size_request(-1, height)
        self.set_draw_func(self._draw)

    def _draw(
        self,
        area: Gtk.DrawingArea,
        cr: "cairo.Context",
        width: int,
        height: int,
    ) -> None:
        """Draw the bar chart."""
        if not self._data:
            return

        # Calculate bar dimensions
        bar_count = len(self._data)
        if bar_count == 0:
            return

        padding = 20
        bar_spacing = 8
        available_width = width - (2 * padding)
        bar_width = max(10, (available_width - (bar_spacing * (bar_count - 1))) / bar_count)
        chart_height = height - 35  # Leave room for labels

        # Auto-scale max value if needed
        max_val = self._max_value
        if max_val == 0:
            max_val = max((v for _, v in self._data), default=1)
        if max_val == 0:
            max_val = 1

        # Parse bar color
        color = self._parse_color(self._bar_color)

        # Draw bars
        for i, (label, value) in enumerate(self._data):
            x = padding + (i * (bar_width + bar_spacing))
            bar_height = (value / max_val) * chart_height if max_val > 0 else 0
            y = height - 30 - bar_height

            # Draw bar with rounded top
            cr.set_source_rgb(*color)
            if bar_height > 4:
                # Rounded rectangle
                radius = min(4, bar_width / 2)
                cr.move_to(x + radius, y)
                cr.line_to(x + bar_width - radius, y)
                cr.arc(x + bar_width - radius, y + radius, radius, -0.5 * 3.14159, 0)
                cr.line_to(x + bar_width, height - 30)
                cr.line_to(x, height - 30)
                cr.line_to(x, y + radius)
                cr.arc(x + radius, y + radius, radius, 3.14159, 1.5 * 3.14159)
                cr.close_path()
                cr.fill()
            elif bar_height > 0:
                cr.rectangle(x, y, bar_width, bar_height)
                cr.fill()

            # Draw label
            style = area.get_style_context()
            text_color = style.get_color()
            cr.set_source_rgba(
                text_color.red, text_color.green,
                text_color.blue, 0.7
            )
            cr.select_font_face("Sans", 0, 0)  # NORMAL slant and weight
            cr.set_font_size(9)

            extents = cr.text_extents(label)
            label_x = x + (bar_width / 2) - (extents.width / 2)
            cr.move_to(label_x, height - 8)
            cr.show_text(label)

    def _parse_color(self, color: str) -> tuple[float, float, float]:
        """Parse hex color to RGB floats."""
        color = color.lstrip("#")
        if len(color) == 6:
            return (
                int(color[0:2], 16) / 255,
                int(color[2:4], 16) / 255,
                int(color[4:6], 16) / 255,
            )
        return (0.2, 0.5, 0.9)

    def update_data(self, data: list[tuple[str, float]], max_value: float = None) -> None:
        """Update chart data and redraw."""
        self._data = data
        if max_value is not None:
            self._max_value = max_value
        self.queue_draw()


class SettingsWindow(Adw.Window):
    """
    Settings window for unitMail application with sidebar navigation.

    Provides organized pages for:
    - Account: Name, email, signature, avatar
    - Server: Gateway URL, SMTP settings, ports
    - Security: Password change, PGP key management, 2FA
    - Appearance: Theme, font size, compact mode
    - Notifications: Desktop notifications, sounds
    - Database: Storage statistics and charts
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
            default_width=900,
            default_height=650,
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
        """Build the settings UI with sidebar navigation."""
        # Main layout box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar
        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label="Settings", css_classes=["title"]))
        main_box.append(header)

        # Paned layout for sidebar + content
        paned = Gtk.Paned(
            orientation=Gtk.Orientation.HORIZONTAL,
            shrink_start_child=False,
            shrink_end_child=False,
            resize_start_child=False,
        )
        paned.set_position(200)
        paned.set_vexpand(True)
        main_box.append(paned)

        # Create sidebar
        sidebar = self._create_sidebar()
        paned.set_start_child(sidebar)

        # Create content stack
        self._content_stack = self._create_content_stack()
        paned.set_end_child(self._content_stack)

        # Select first category by default
        first_row = self._category_list.get_row_at_index(0)
        if first_row:
            self._category_list.select_row(first_row)

    def _create_sidebar(self) -> Gtk.Widget:
        """Create the settings category sidebar."""
        sidebar_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["navigation-sidebar"],
        )
        sidebar_box.set_size_request(200, -1)

        # Scrolled window for category list
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )

        self._category_list = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.SINGLE,
            css_classes=["navigation-sidebar"],
        )
        self._category_list.connect("row-selected", self._on_category_selected)

        # Add category rows
        categories = [
            ("account", "Account", "avatar-default-symbolic"),
            ("server", "Server", "network-server-symbolic"),
            ("security", "Security", "security-high-symbolic"),
            ("appearance", "Appearance", "applications-graphics-symbolic"),
            ("notifications", "Notifications", "preferences-system-notifications-symbolic"),
            ("database", "Database", "drive-harddisk-symbolic"),
            ("advanced", "Advanced", "preferences-other-symbolic"),
        ]

        for cat_id, label, icon in categories:
            row = self._create_category_row(cat_id, label, icon)
            self._category_list.append(row)

        scrolled.set_child(self._category_list)
        sidebar_box.append(scrolled)

        return sidebar_box

    def _create_category_row(self, cat_id: str, label: str, icon_name: str) -> Gtk.ListBoxRow:
        """Create a sidebar category row."""
        row = Gtk.ListBoxRow()
        row.set_name(cat_id)

        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_start=12,
            margin_end=12,
            margin_top=10,
            margin_bottom=10,
        )

        icon = Gtk.Image(icon_name=icon_name)
        box.append(icon)

        label_widget = Gtk.Label(label=label, xalign=0, hexpand=True)
        box.append(label_widget)

        row.set_child(box)
        return row

    def _on_category_selected(self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        """Handle category selection."""
        if row:
            cat_id = row.get_name()
            self._content_stack.set_visible_child_name(cat_id)

    def _create_content_stack(self) -> Gtk.Stack:
        """Create the content stack for settings pages."""
        stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.NONE,
            vexpand=True,
            hexpand=True,
        )

        # Add all pages
        stack.add_named(self._create_account_content(), "account")
        stack.add_named(self._create_server_content(), "server")
        stack.add_named(self._create_security_content(), "security")
        stack.add_named(self._create_appearance_content(), "appearance")
        stack.add_named(self._create_notifications_content(), "notifications")
        stack.add_named(self._create_database_content(), "database")
        stack.add_named(self._create_advanced_content(), "advanced")

        return stack

    def _create_page_container(self, title: str, subtitle: str = "") -> tuple[Gtk.Box, Gtk.Box]:
        """Create a standard page container with title and scrollable content."""
        page_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            margin_start=36,
            margin_end=36,
            margin_top=24,
            margin_bottom=24,
        )

        # Page header
        header_label = Gtk.Label(
            label=title,
            css_classes=["title-1"],
            xalign=0,
            margin_bottom=4,
        )
        page_box.append(header_label)

        if subtitle:
            subtitle_label = Gtk.Label(
                label=subtitle,
                css_classes=["dim-label"],
                xalign=0,
                margin_bottom=16,
            )
            page_box.append(subtitle_label)
        else:
            header_label.set_margin_bottom(16)

        # Scrolled content
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )

        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
            margin_end=12,  # Space for scrollbar
        )

        scrolled.set_child(content_box)
        page_box.append(scrolled)

        return page_box, content_box

    def _create_account_content(self) -> Gtk.Widget:
        """Create the account settings content."""
        page_box, content_box = self._create_page_container(
            "Account", "Your identity when sending emails"
        )

        # Profile group
        profile_group = Adw.PreferencesGroup(title="Profile")

        self._display_name_row = Adw.EntryRow(title="Display Name")
        self._display_name_row.connect("changed", self._on_account_changed)
        profile_group.add(self._display_name_row)

        self._email_row = Adw.EntryRow(title="Email Address")
        self._email_row.connect("changed", self._on_email_changed)
        profile_group.add(self._email_row)

        content_box.append(profile_group)

        # Avatar group
        avatar_group = Adw.PreferencesGroup(title="Avatar")

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
        content_box.append(avatar_group)

        # Signature group
        signature_group = Adw.PreferencesGroup(
            title="Email Signature",
            description="Automatically appended to outgoing messages",
        )

        signature_frame = Gtk.Frame(
            margin_start=0,
            margin_end=0,
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
        content_box.append(signature_group)

        return page_box

    def _create_server_content(self) -> Gtk.Widget:
        """Create the server settings content."""
        page_box, content_box = self._create_page_container(
            "Server", "Connection to mail servers"
        )

        # Gateway group
        gateway_group = Adw.PreferencesGroup(
            title="Gateway",
            description="Connection to the unitMail gateway server",
        )

        self._gateway_url_row = Adw.EntryRow(title="Gateway URL")
        self._gateway_url_row.connect("changed", self._on_server_changed)
        gateway_group.add(self._gateway_url_row)

        content_box.append(gateway_group)

        # SMTP group
        smtp_group = Adw.PreferencesGroup(title="SMTP (Outgoing Mail)")

        self._smtp_host_row = Adw.EntryRow(title="SMTP Server")
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

        content_box.append(smtp_group)

        # IMAP group
        imap_group = Adw.PreferencesGroup(title="IMAP (Incoming Mail)")

        self._imap_host_row = Adw.EntryRow(title="IMAP Server")
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

        content_box.append(imap_group)

        # Test connection
        test_group = Adw.PreferencesGroup()

        test_row = Adw.ActionRow(
            title="Test Connection",
            subtitle="Verify server settings",
            activatable=True,
        )
        test_row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        test_row.connect("activated", self._on_test_connection_clicked)
        test_group.add(test_row)

        content_box.append(test_group)

        return page_box

    def _create_security_content(self) -> Gtk.Widget:
        """Create the security settings content."""
        page_box, content_box = self._create_page_container(
            "Security", "Account security and encryption"
        )

        # Password group
        password_group = Adw.PreferencesGroup(title="Account Security")

        change_password_row = Adw.ActionRow(
            title="Change Password",
            subtitle="Update your account password",
            activatable=True,
        )
        change_password_row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        change_password_row.connect("activated", self._on_change_password_clicked)
        password_group.add(change_password_row)

        self._2fa_row = Adw.SwitchRow(
            title="Two-Factor Authentication",
            subtitle="Add an extra layer of security",
        )
        self._2fa_row.connect("notify::active", self._on_2fa_toggled)
        password_group.add(self._2fa_row)

        content_box.append(password_group)

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

        self._passphrase_timeout_row = Adw.SpinRow.new_with_range(1, 60, 1)
        self._passphrase_timeout_row.set_title("Passphrase Timeout")
        self._passphrase_timeout_row.set_subtitle("Minutes to remember passphrase")
        self._passphrase_timeout_row.set_value(5)
        self._passphrase_timeout_row.connect("notify::value", self._on_security_changed)
        pgp_settings_group.add(self._passphrase_timeout_row)

        content_box.append(pgp_settings_group)

        # PGP key management
        key_group = Adw.PreferencesGroup(title="PGP Keys")

        key_expander = Adw.ExpanderRow(
            title="Manage Keys",
            subtitle="View and manage your PGP keys",
        )

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

        key_expander.add_row(Adw.PreferencesRow(child=key_manager_box))
        key_group.add(key_expander)

        content_box.append(key_group)

        return page_box

    def _create_appearance_content(self) -> Gtk.Widget:
        """Create the appearance settings content."""
        page_box, content_box = self._create_page_container(
            "Appearance", "Customize how unitMail looks"
        )

        # Theme group
        theme_group = Adw.PreferencesGroup(
            title="Color Scheme",
            description="Choose how unitMail looks",
        )

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

        content_box.append(theme_group)

        # Message List Density group
        density_group = Adw.PreferencesGroup(
            title="Message List Density",
            description="How messages appear in the list",
        )

        self._density_buttons = {}

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

        minimal_row = Adw.ActionRow(
            title="Minimal",
            subtitle="Single line: date | from | subject",
            activatable=True,
        )
        minimal_row.add_prefix(Gtk.Image(icon_name="view-continuous-symbolic"))
        self._density_buttons["minimal"] = Gtk.CheckButton()
        self._density_buttons["minimal"].set_group(self._density_buttons["standard"])
        self._density_buttons["minimal"].connect("toggled", self._on_density_toggled, "minimal")
        minimal_row.add_suffix(self._density_buttons["minimal"])
        minimal_row.set_activatable_widget(self._density_buttons["minimal"])
        density_group.add(minimal_row)

        content_box.append(density_group)

        # Date Format group
        date_format_group = Adw.PreferencesGroup(
            title="Date Format",
            description="How dates appear in the message list",
        )

        date_formats = [
            "MM/DD/YYYY (US)",
            "DD/MM/YYYY (European)",
            "YYYY-MM-DD (ISO)",
            "DD MMM YYYY",
            "MMM DD, YYYY",
            "MM/DD/YYYY HH:MM (US 24-hour)",
            "DD/MM/YYYY HH:MM (European 24-hour)",
            "YYYY-MM-DD HH:MM (ISO 24-hour)",
            "DD MMM YYYY HH:MM (24-hour)",
            "MMM DD, YYYY HH:MM (24-hour)",
            "MM/DD/YYYY hh:mm am/pm (US 12-hour)",
            "DD/MM/YYYY hh:mm am/pm (European 12-hour)",
            "YYYY-MM-DD hh:mm am/pm (ISO 12-hour)",
            "DD MMM YYYY hh:mm am/pm (12-hour)",
            "MMM DD, YYYY hh:mm am/pm (12-hour)",
        ]
        date_format_model = Gtk.StringList.new(date_formats)
        self._date_format_row = Adw.ComboRow(
            title="Date Format",
            subtitle="Select how dates are displayed",
            model=date_format_model,
            selected=2,
        )
        self._date_format_row.connect("notify::selected", self._on_date_format_changed)
        date_format_group.add(self._date_format_row)

        # Preview label
        self._date_format_preview_label = Gtk.Label(
            label="2026-01-13",
            css_classes=["dim-label"],
            margin_top=8,
            margin_bottom=8,
        )
        date_format_group.add(self._date_format_preview_label)

        content_box.append(date_format_group)

        # Text group
        text_group = Adw.PreferencesGroup(title="Text")

        self._font_size_row = Adw.SpinRow.new_with_range(8, 24, 1)
        self._font_size_row.set_title("Font Size")
        self._font_size_row.set_value(12)
        self._font_size_row.connect("notify::value", self._on_appearance_changed)
        text_group.add(self._font_size_row)

        content_box.append(text_group)

        # Layout group
        layout_group = Adw.PreferencesGroup(title="Layout Options")

        self._compact_mode_row = Adw.SwitchRow(
            title="Compact Mode",
            subtitle="Reduce spacing in the interface",
        )
        self._compact_mode_row.connect("notify::active", self._on_appearance_changed)
        layout_group.add(self._compact_mode_row)

        self._show_avatars_row = Adw.SwitchRow(
            title="Show Avatars",
            subtitle="Display sender avatars in message list",
        )
        self._show_avatars_row.connect("notify::active", self._on_appearance_changed)
        layout_group.add(self._show_avatars_row)

        self._preview_lines_row = Adw.SpinRow.new_with_range(0, 5, 1)
        self._preview_lines_row.set_title("Preview Lines")
        self._preview_lines_row.set_subtitle("Lines of message preview to show")
        self._preview_lines_row.set_value(2)
        self._preview_lines_row.connect("notify::value", self._on_appearance_changed)
        layout_group.add(self._preview_lines_row)

        content_box.append(layout_group)

        return page_box

    def _create_notifications_content(self) -> Gtk.Widget:
        """Create the notifications settings content."""
        page_box, content_box = self._create_page_container(
            "Notifications", "Configure alerts and sounds"
        )

        # General group
        general_group = Adw.PreferencesGroup(title="Desktop Notifications")

        self._desktop_notif_row = Adw.SwitchRow(
            title="Enable Notifications",
            subtitle="Show desktop notifications for new messages",
        )
        self._desktop_notif_row.connect("notify::active", self._on_notifications_changed)
        general_group.add(self._desktop_notif_row)

        self._notif_preview_row = Adw.SwitchRow(
            title="Show Message Preview",
            subtitle="Include message preview in notifications",
        )
        self._notif_preview_row.connect("notify::active", self._on_notifications_changed)
        general_group.add(self._notif_preview_row)

        content_box.append(general_group)

        # Sound group
        sound_group = Adw.PreferencesGroup(title="Sounds")

        self._sound_row = Adw.SwitchRow(
            title="Notification Sound",
            subtitle="Play a sound for new messages",
        )
        self._sound_row.connect("notify::active", self._on_notifications_changed)
        sound_group.add(self._sound_row)

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
        sound_file_row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        sound_file_row.connect("activated", self._on_choose_sound_clicked)
        sound_group.add(sound_file_row)

        content_box.append(sound_group)

        # Events group
        events_group = Adw.PreferencesGroup(title="Notification Events")

        self._notify_new_mail_row = Adw.SwitchRow(
            title="New Mail",
            subtitle="Notify when new messages arrive",
        )
        self._notify_new_mail_row.connect("notify::active", self._on_notifications_changed)
        events_group.add(self._notify_new_mail_row)

        self._notify_send_row = Adw.SwitchRow(
            title="Send Success",
            subtitle="Notify when messages are sent successfully",
        )
        self._notify_send_row.connect("notify::active", self._on_notifications_changed)
        events_group.add(self._notify_send_row)

        self._notify_error_row = Adw.SwitchRow(
            title="Errors",
            subtitle="Notify when errors occur",
        )
        self._notify_error_row.connect("notify::active", self._on_notifications_changed)
        events_group.add(self._notify_error_row)

        content_box.append(events_group)

        return page_box

    def _create_database_content(self) -> Gtk.Widget:
        """Create the database statistics content."""
        page_box, content_box = self._create_page_container(
            "Database", "Storage statistics and information"
        )

        # Storage type group
        storage_group = Adw.PreferencesGroup(
            title="Storage Type",
            description="Current database backend",
        )

        self._storage_type_row = Adw.ActionRow(
            title="Database System",
            subtitle="Local JSON storage",
        )
        storage_type_icon = Gtk.Image(
            icon_name="drive-harddisk-symbolic",
            valign=Gtk.Align.CENTER,
        )
        self._storage_type_row.add_prefix(storage_type_icon)
        storage_group.add(self._storage_type_row)

        content_box.append(storage_group)

        # Statistics group
        stats_group = Adw.PreferencesGroup(title="Statistics")

        # Refresh button in header
        refresh_button = Gtk.Button(
            icon_name="view-refresh-symbolic",
            valign=Gtk.Align.CENTER,
            tooltip_text="Refresh statistics",
            css_classes=["flat"],
        )
        refresh_button.connect("clicked", self._on_refresh_stats_clicked)
        stats_group.set_header_suffix(refresh_button)

        # Statistics rows
        self._db_size_row = Adw.ActionRow(
            title="Database Size",
            subtitle="Total storage used",
        )
        self._db_size_label = Gtk.Label(
            label="--",
            css_classes=["dim-label"],
            valign=Gtk.Align.CENTER,
        )
        self._db_size_row.add_suffix(self._db_size_label)
        stats_group.add(self._db_size_row)

        self._total_messages_row = Adw.ActionRow(
            title="Total Messages",
            subtitle="All messages in database",
        )
        self._total_messages_label = Gtk.Label(
            label="--",
            css_classes=["dim-label"],
            valign=Gtk.Align.CENTER,
        )
        self._total_messages_row.add_suffix(self._total_messages_label)
        stats_group.add(self._total_messages_row)

        self._attachments_row = Adw.ActionRow(
            title="Attachments",
            subtitle="Files stored in database",
        )
        self._attachments_label = Gtk.Label(
            label="--",
            css_classes=["dim-label"],
            valign=Gtk.Align.CENTER,
        )
        self._attachments_row.add_suffix(self._attachments_label)
        stats_group.add(self._attachments_row)

        self._daily_received_row = Adw.ActionRow(
            title="Daily Avg (Received)",
            subtitle="Average emails received per day",
        )
        self._daily_received_label = Gtk.Label(
            label="--",
            css_classes=["dim-label"],
            valign=Gtk.Align.CENTER,
        )
        self._daily_received_row.add_suffix(self._daily_received_label)
        stats_group.add(self._daily_received_row)

        self._daily_sent_row = Adw.ActionRow(
            title="Daily Avg (Sent)",
            subtitle="Average emails sent per day",
        )
        self._daily_sent_label = Gtk.Label(
            label="--",
            css_classes=["dim-label"],
            valign=Gtk.Align.CENTER,
        )
        self._daily_sent_row.add_suffix(self._daily_sent_label)
        stats_group.add(self._daily_sent_row)

        self._disk_space_row = Adw.ActionRow(
            title="Disk Space Available",
            subtitle="Free space for email storage",
        )
        self._disk_space_label = Gtk.Label(
            label="--",
            css_classes=["dim-label"],
            valign=Gtk.Align.CENTER,
        )
        self._disk_space_row.add_suffix(self._disk_space_label)
        stats_group.add(self._disk_space_row)

        content_box.append(stats_group)

        # Size chart group
        size_chart_group = Adw.PreferencesGroup(
            title="Storage Growth",
            description="Database size over the last 6 months",
        )

        chart_frame = Gtk.Frame(
            margin_top=8,
            margin_bottom=8,
        )
        self._size_chart = VerticalBarChart(
            data=[],
            max_value=0,
            bar_color="#3584e4",
            height=140,
        )
        chart_frame.set_child(self._size_chart)
        size_chart_group.add(chart_frame)

        content_box.append(size_chart_group)

        # Volume chart group
        volume_chart_group = Adw.PreferencesGroup(
            title="Email Volume",
            description="Received vs Sent emails (last 30 days)",
        )

        # Received bar
        received_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=8,
            margin_bottom=4,
        )
        received_label = Gtk.Label(label="Received", xalign=0, width_chars=10)
        received_box.append(received_label)
        self._received_bar = Gtk.LevelBar(
            min_value=0,
            max_value=100,
            value=0,
            hexpand=True,
        )
        self._received_bar.add_css_class("received-bar")
        received_box.append(self._received_bar)
        self._received_count_label = Gtk.Label(label="0", width_chars=6, xalign=1)
        received_box.append(self._received_count_label)
        volume_chart_group.add(received_box)

        # Sent bar
        sent_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=4,
            margin_bottom=8,
        )
        sent_label = Gtk.Label(label="Sent", xalign=0, width_chars=10)
        sent_box.append(sent_label)
        self._sent_bar = Gtk.LevelBar(
            min_value=0,
            max_value=100,
            value=0,
            hexpand=True,
        )
        self._sent_bar.add_css_class("sent-bar")
        sent_box.append(self._sent_bar)
        self._sent_count_label = Gtk.Label(label="0", width_chars=6, xalign=1)
        sent_box.append(self._sent_count_label)
        volume_chart_group.add(sent_box)

        content_box.append(volume_chart_group)

        # Load initial stats
        GLib.idle_add(self._load_database_stats)

        return page_box

    def _load_database_stats(self) -> None:
        """Load and display database statistics."""
        try:
            storage = get_local_storage()

            # Get basic stats
            stats = storage.get_database_stats()

            # Update storage type
            self._storage_type_row.set_subtitle(stats.get("storage_type", "Unknown"))

            # Update database size
            size_bytes = stats.get("database_size_bytes", 0)
            self._db_size_label.set_label(self._format_size(size_bytes))

            # Update message count
            total_msgs = stats.get("total_messages", 0)
            self._total_messages_label.set_label(f"{total_msgs:,}")

            # Update attachments
            total_att = stats.get("total_attachments", 0)
            att_size = stats.get("attachment_size_bytes", 0)
            self._attachments_label.set_label(f"{total_att:,} ({self._format_size(att_size)})")

            # Get daily stats
            daily_stats = storage.get_daily_email_stats(30)
            self._daily_received_label.set_label(f"{daily_stats['received_avg']:.1f}")
            self._daily_sent_label.set_label(f"{daily_stats['sent_avg']:.1f}")

            # Get disk space
            disk_info = storage.get_disk_space_info()
            free_space = disk_info.get("free", 0)
            self._disk_space_label.set_label(self._format_size(free_space))

            # Update size chart
            monthly_stats = storage.get_monthly_size_stats(6)
            max_size = max((size for _, size in monthly_stats), default=1)
            self._size_chart.update_data(monthly_stats, max_size)

            # Update volume bars
            received_total = daily_stats.get("received_total", 0)
            sent_total = daily_stats.get("sent_total", 0)
            max_volume = max(received_total, sent_total, 1)

            self._received_bar.set_max_value(max_volume)
            self._received_bar.set_value(received_total)
            self._received_count_label.set_label(f"{received_total:,}")

            self._sent_bar.set_max_value(max_volume)
            self._sent_bar.set_value(sent_total)
            self._sent_count_label.set_label(f"{sent_total:,}")

        except Exception as e:
            logger.error(f"Failed to load database stats: {e}")

    def _on_refresh_stats_clicked(self, button: Gtk.Button) -> None:
        """Handle refresh statistics button click."""
        self._load_database_stats()

    def _create_advanced_content(self) -> Gtk.Widget:
        """Create the advanced settings content."""
        page_box, content_box = self._create_page_container(
            "Advanced", "Power user settings"
        )

        # Sync group
        sync_group = Adw.PreferencesGroup(title="Synchronization")

        self._sync_interval_row = Adw.SpinRow.new_with_range(60, 3600, 60)
        self._sync_interval_row.set_title("Sync Interval")
        self._sync_interval_row.set_subtitle("Seconds between automatic syncs")
        self._sync_interval_row.set_value(300)
        self._sync_interval_row.connect("notify::value", self._on_advanced_changed)
        sync_group.add(self._sync_interval_row)

        self._max_connections_row = Adw.SpinRow.new_with_range(1, 10, 1)
        self._max_connections_row.set_title("Max Connections")
        self._max_connections_row.set_subtitle("Maximum concurrent server connections")
        self._max_connections_row.set_value(4)
        self._max_connections_row.connect("notify::value", self._on_advanced_changed)
        sync_group.add(self._max_connections_row)

        content_box.append(sync_group)

        # Cache group
        cache_group = Adw.PreferencesGroup(title="Cache")

        self._cache_enabled_row = Adw.SwitchRow(
            title="Enable Cache",
            subtitle="Cache messages locally for faster access",
        )
        self._cache_enabled_row.connect("notify::active", self._on_advanced_changed)
        cache_group.add(self._cache_enabled_row)

        self._cache_size_row = Adw.SpinRow.new_with_range(100, 5000, 100)
        self._cache_size_row.set_title("Cache Size (MB)")
        self._cache_size_row.set_subtitle("Maximum cache storage")
        self._cache_size_row.set_value(500)
        self._cache_size_row.connect("notify::value", self._on_advanced_changed)
        cache_group.add(self._cache_size_row)

        # Cache usage
        cache_usage_row = Adw.ActionRow(
            title="Cache Usage",
            subtitle="Current cache size",
        )
        self._cache_usage_bar = Gtk.LevelBar(
            min_value=0,
            max_value=100,
            value=0,
            valign=Gtk.Align.CENTER,
        )
        self._cache_usage_bar.set_size_request(100, -1)
        cache_usage_row.add_suffix(self._cache_usage_bar)
        self._cache_usage_label = Gtk.Label(
            label="0 MB / 500 MB",
            css_classes=["dim-label"],
            valign=Gtk.Align.CENTER,
        )
        cache_usage_row.add_suffix(self._cache_usage_label)
        cache_group.add(cache_usage_row)

        # Clear cache
        clear_cache_row = Adw.ActionRow(
            title="Clear Cache",
            subtitle="Delete all cached data",
            activatable=True,
        )
        clear_cache_row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        clear_cache_row.connect("activated", self._on_clear_cache_clicked)
        cache_group.add(clear_cache_row)

        content_box.append(cache_group)

        # Storage quota group
        quota_group = Adw.PreferencesGroup(title="Storage Quota")

        self._show_quota_row = Adw.SwitchRow(
            title="Show Quota in Status Bar",
            subtitle="Display storage usage in the main window",
        )
        self._show_quota_row.connect("notify::active", self._on_advanced_changed)
        quota_group.add(self._show_quota_row)

        content_box.append(quota_group)

        # Logging group
        logging_group = Adw.PreferencesGroup(title="Logging")

        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        log_level_model = Gtk.StringList.new(log_levels)
        self._log_level_row = Adw.ComboRow(
            title="Log Level",
            subtitle="Amount of detail in logs",
            model=log_level_model,
            selected=1,
        )
        self._log_level_row.connect("notify::selected", self._on_advanced_changed)
        logging_group.add(self._log_level_row)

        open_logs_row = Adw.ActionRow(
            title="Open Log File",
            subtitle="View application logs",
            activatable=True,
        )
        open_logs_row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        open_logs_row.connect("activated", self._on_open_logs_clicked)
        logging_group.add(open_logs_row)

        content_box.append(logging_group)

        # Data export group
        export_group = Adw.PreferencesGroup(title="Data Export")

        export_mbox_row = Adw.ActionRow(
            title="Export to MBOX",
            subtitle="Export all emails in MBOX format",
            activatable=True,
        )
        export_mbox_row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        export_mbox_row.connect("activated", self._on_export_emails_clicked)
        export_group.add(export_mbox_row)

        export_json_row = Adw.ActionRow(
            title="Export to JSON",
            subtitle="Export all data in JSON format",
            activatable=True,
        )
        export_json_row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        export_json_row.connect("activated", self._on_export_json_clicked)
        export_group.add(export_json_row)

        content_box.append(export_group)

        # Reset group
        reset_group = Adw.PreferencesGroup(title="Reset")

        reset_row = Adw.ActionRow(
            title="Reset to Defaults",
            subtitle="Restore all settings to default values",
            activatable=True,
        )
        reset_row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        reset_row.connect("activated", self._on_reset_clicked)
        reset_row.add_css_class("error")
        reset_group.add(reset_row)

        content_box.append(reset_group)

        return page_box

    # -------------------------------------------------------------------------
    # Load Settings
    # -------------------------------------------------------------------------

    def _load_settings(self) -> None:
        """Load current settings into the UI."""
        # Account settings
        account = self._settings.account
        self._display_name_row.set_text(account.display_name or "")
        self._email_row.set_text(account.email_address or "")

        if account.signature:
            self._signature_text.get_buffer().set_text(account.signature)

        if account.avatar_path:
            self._load_avatar(account.avatar_path)

        # Server settings
        server = self._settings.server
        self._gateway_url_row.set_text(server.gateway_url or "")
        self._smtp_host_row.set_text(server.smtp_host or "")
        self._smtp_port_row.set_value(server.smtp_port)
        self._smtp_tls_row.set_active(server.smtp_use_tls)
        self._imap_host_row.set_text(server.imap_host or "")
        self._imap_port_row.set_value(server.imap_port)
        self._imap_tls_row.set_active(server.imap_use_tls)

        # Security settings
        security = self._settings.security
        self._2fa_row.set_active(security.two_factor_enabled)
        self._auto_encrypt_row.set_active(security.auto_encrypt)
        self._auto_sign_row.set_active(security.auto_sign)
        self._remember_passphrase_row.set_active(security.remember_passphrase)
        self._passphrase_timeout_row.set_value(security.passphrase_timeout // 60)

        # Appearance settings
        appearance = self._settings.appearance
        theme = appearance.theme_mode
        if theme in self._theme_buttons:
            self._theme_buttons[theme].set_active(True)

        density = appearance.view_density
        if density in self._density_buttons:
            self._density_buttons[density].set_active(True)

        # Date format
        format_index = self._get_date_format_index(appearance.date_format)
        self._date_format_row.set_selected(format_index)

        self._font_size_row.set_value(appearance.font_size)
        self._compact_mode_row.set_active(appearance.compact_mode)
        self._show_avatars_row.set_active(appearance.show_avatars)
        self._preview_lines_row.set_value(appearance.message_preview_lines)

        # Notifications settings
        notifications = self._settings.notifications
        self._desktop_notif_row.set_active(notifications.desktop_notifications)
        self._notif_preview_row.set_active(notifications.show_message_preview)
        self._sound_row.set_active(notifications.notification_sound)

        if notifications.notification_sound_path:
            self._sound_path_label.set_label(
                Path(notifications.notification_sound_path).name
            )

        self._notify_new_mail_row.set_active(notifications.notify_on_new_mail)
        self._notify_send_row.set_active(notifications.notify_on_send_success)
        self._notify_error_row.set_active(notifications.notify_on_error)

        # Advanced settings
        advanced = self._settings.advanced
        self._sync_interval_row.set_value(advanced.sync_interval_seconds)
        self._max_connections_row.set_value(advanced.max_concurrent_connections)
        self._cache_enabled_row.set_active(advanced.cache_enabled)
        self._cache_size_row.set_value(advanced.cache_size_mb)
        self._show_quota_row.set_active(advanced.show_quota)

        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if advanced.log_level in log_levels:
            self._log_level_row.set_selected(log_levels.index(advanced.log_level))

        self._update_cache_usage()

        logger.info("Settings loaded into UI")

    def _get_date_format_index(self, format_str: str) -> int:
        """Get the dropdown index for a date format string."""
        format_map = {
            "MM/DD/YYYY": 0,
            "DD/MM/YYYY": 1,
            "YYYY-MM-DD": 2,
            "DD MMM YYYY": 3,
            "MMM DD, YYYY": 4,
            "MM/DD/YYYY HH:MM": 5,
            "DD/MM/YYYY HH:MM": 6,
            "YYYY-MM-DD HH:MM": 7,
            "DD MMM YYYY HH:MM": 8,
            "MMM DD, YYYY HH:MM": 9,
            "MM/DD/YYYY hh:mm am/pm": 10,
            "DD/MM/YYYY hh:mm am/pm": 11,
            "YYYY-MM-DD hh:mm am/pm": 12,
            "DD MMM YYYY hh:mm am/pm": 13,
            "MMM DD, YYYY hh:mm am/pm": 14,
        }
        return format_map.get(format_str, 2)

    def _connect_signals(self) -> None:
        """Connect additional signals."""
        self.connect("close-request", self._on_close_request)

    def _load_avatar(self, path: str) -> None:
        """Load avatar image from path."""
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 48, 48, True)
            self._avatar_image.set_from_pixbuf(pixbuf)
        except Exception as e:
            logger.warning(f"Failed to load avatar: {e}")

    def _update_cache_usage(self) -> None:
        """Update the cache usage display."""
        # Placeholder - would need actual cache implementation
        cache_size = self._settings.advanced.cache_size_mb
        used = 0  # Would come from actual cache
        self._cache_usage_bar.set_value((used / cache_size) * 100 if cache_size > 0 else 0)
        self._cache_usage_label.set_label(f"{used} MB / {cache_size} MB")

    def _format_size(self, size: int) -> str:
        """Format a size in bytes to human-readable string."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"

    # -------------------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------------------

    def _on_close_request(self, window: Gtk.Window) -> bool:
        """Handle window close - save settings."""
        self._settings.save()
        logger.info("Settings saved on close")
        return False

    def _on_account_changed(self, *args) -> None:
        """Handle account field changes."""
        self._settings.update_account(
            display_name=self._display_name_row.get_text(),
        )

    def _on_email_changed(self, entry: Adw.EntryRow) -> None:
        """Handle email address change with validation."""
        email = entry.get_text()
        if email and "@" not in email:
            entry.add_css_class("error")
        else:
            entry.remove_css_class("error")
            self._settings.update_account(email_address=email)

    def _on_signature_changed(self, buffer: Gtk.TextBuffer) -> None:
        """Handle signature text change."""
        start, end = buffer.get_bounds()
        self._settings.update_account(signature=buffer.get_text(start, end, False))

    def _on_change_avatar_clicked(self, button: Gtk.Button) -> None:
        """Handle change avatar button click."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Choose Avatar")

        filter_images = Gtk.FileFilter()
        filter_images.set_name("Images")
        filter_images.add_mime_type("image/png")
        filter_images.add_mime_type("image/jpeg")
        filter_images.add_mime_type("image/gif")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_images)
        dialog.set_filters(filters)

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
            if e.code != Gtk.DialogError.DISMISSED:
                logger.error(f"Error selecting avatar: {e}")

    def _on_clear_avatar_clicked(self, button: Gtk.Button) -> None:
        """Handle clear avatar button click."""
        self._avatar_image.set_from_icon_name("avatar-default-symbolic")
        self._settings.update_account(avatar_path="")

    def _on_server_changed(self, *args) -> None:
        """Handle server settings change."""
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
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Testing Connection",
            body="Connecting to server...",
        )
        dialog.add_response("cancel", "Cancel")

        spinner = Gtk.Spinner(spinning=True)
        dialog.set_extra_child(spinner)
        dialog.present()

        def test_complete():
            dialog.set_heading("Connection Test")
            dialog.set_body("Connection successful!")
            spinner.set_spinning(False)
            dialog.add_response("ok", "OK")
            dialog.set_default_response("ok")
            return False

        GLib.timeout_add(2000, test_complete)

    def _on_security_changed(self, *args) -> None:
        """Handle security settings change."""
        self._settings.update_security(
            auto_encrypt=self._auto_encrypt_row.get_active(),
            auto_sign=self._auto_sign_row.get_active(),
            remember_passphrase=self._remember_passphrase_row.get_active(),
            passphrase_timeout=int(self._passphrase_timeout_row.get_value()) * 60,
        )

    def _on_2fa_toggled(self, row: Adw.SwitchRow, *args) -> None:
        """Handle 2FA toggle."""
        if row.get_active():
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Set Up Two-Factor Authentication",
                body="Two-factor authentication adds an extra layer of security.",
            )
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("setup", "Set Up")
            dialog.set_response_appearance("setup", Adw.ResponseAppearance.SUGGESTED)
            dialog.connect("response", self._on_2fa_setup_response)
            dialog.present()

    def _on_2fa_setup_response(
        self,
        dialog: Adw.MessageDialog,
        response: str,
    ) -> None:
        """Handle 2FA setup dialog response."""
        if response != "setup":
            self._2fa_row.set_active(False)
        else:
            self._settings.update_security(two_factor_enabled=True)

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
            self._settings.update_appearance(theme_mode=theme)

    def _on_density_toggled(
        self,
        button: Gtk.CheckButton,
        density: str,
    ) -> None:
        """Handle density radio button toggle."""
        if button.get_active():
            self._settings.update_appearance(view_density=density)
            # Use ViewThemeManager to change theme and notify main window
            from client.ui.view_theme import ViewTheme, get_view_theme_manager
            theme_map = {
                "standard": ViewTheme.STANDARD,
                "minimal": ViewTheme.MINIMAL,
            }
            if density in theme_map:
                manager = get_view_theme_manager()
                manager.set_theme(theme_map[density])
            logger.info(f"Density changed to: {density}")

    def _on_date_format_changed(self, row: Adw.ComboRow, *args) -> None:
        """Handle date format dropdown change."""
        selected_index = row.get_selected()

        format_map = {
            0: "MM/DD/YYYY",
            1: "DD/MM/YYYY",
            2: "YYYY-MM-DD",
            3: "DD MMM YYYY",
            4: "MMM DD, YYYY",
            5: "MM/DD/YYYY HH:MM",
            6: "DD/MM/YYYY HH:MM",
            7: "YYYY-MM-DD HH:MM",
            8: "DD MMM YYYY HH:MM",
            9: "MMM DD, YYYY HH:MM",
            10: "MM/DD/YYYY hh:mm am/pm",
            11: "DD/MM/YYYY hh:mm am/pm",
            12: "YYYY-MM-DD hh:mm am/pm",
            13: "DD MMM YYYY hh:mm am/pm",
            14: "MMM DD, YYYY hh:mm am/pm",
        }
        preview_map = {
            0: "01/13/2026",
            1: "13/01/2026",
            2: "2026-01-13",
            3: "13 Jan 2026",
            4: "Jan 13, 2026",
            5: "01/13/2026 14:30",
            6: "13/01/2026 14:30",
            7: "2026-01-13 14:30",
            8: "13 Jan 2026 14:30",
            9: "Jan 13, 2026 14:30",
            10: "01/13/2026 02:30 pm",
            11: "13/01/2026 02:30 pm",
            12: "2026-01-13 02:30 pm",
            13: "13 Jan 2026 02:30 pm",
            14: "Jan 13, 2026 02:30 pm",
        }
        date_format = format_map.get(selected_index, "YYYY-MM-DD")
        preview = preview_map.get(selected_index, "2026-01-13")

        logger.info(f"Date format changed to: {date_format}")
        self._date_format_preview_label.set_label(preview)
        self._settings.set_date_format(date_format)

    def _on_appearance_changed(self, *args) -> None:
        """Handle appearance settings change."""
        self._settings.update_appearance(
            font_size=int(self._font_size_row.get_value()),
            compact_mode=self._compact_mode_row.get_active(),
            show_avatars=self._show_avatars_row.get_active(),
            message_preview_lines=int(self._preview_lines_row.get_value()),
        )

    def _on_notifications_changed(self, *args) -> None:
        """Handle notifications settings change."""
        self._settings.update_notifications(
            desktop_notifications=self._desktop_notif_row.get_active(),
            show_message_preview=self._notif_preview_row.get_active(),
            notification_sound=self._sound_row.get_active(),
            notify_on_new_mail=self._notify_new_mail_row.get_active(),
            notify_on_send_success=self._notify_send_row.get_active(),
            notify_on_error=self._notify_error_row.get_active(),
        )

    def _on_choose_sound_clicked(self, row: Adw.ActionRow) -> None:
        """Handle choose sound button click."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Choose Notification Sound")

        filter_audio = Gtk.FileFilter()
        filter_audio.set_name("Audio Files")
        filter_audio.add_mime_type("audio/*")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_audio)
        dialog.set_filters(filters)

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
            if e.code != Gtk.DialogError.DISMISSED:
                logger.error(f"Error selecting sound: {e}")

    def _on_advanced_changed(self, *args) -> None:
        """Handle advanced settings change."""
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        log_level = log_levels[self._log_level_row.get_selected()]

        self._settings.update_advanced(
            sync_interval_seconds=int(self._sync_interval_row.get_value()),
            max_concurrent_connections=int(self._max_connections_row.get_value()),
            cache_enabled=self._cache_enabled_row.get_active(),
            cache_size_mb=int(self._cache_size_row.get_value()),
            show_quota=self._show_quota_row.get_active(),
            log_level=log_level,
        )

    def _on_clear_cache_clicked(self, row: Adw.ActionRow) -> None:
        """Handle clear cache button click."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Clear Cache?",
            body="This will delete all cached email data. This cannot be undone.",
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
        """Handle clear cache dialog response."""
        if response == "clear":
            # Would clear actual cache here
            self._update_cache_usage()
            logger.info("Cache cleared")

    def _on_open_logs_clicked(self, row: Adw.ActionRow) -> None:
        """Handle open logs button click."""
        log_path = Path.home() / ".unitmail" / "logs"
        log_path.mkdir(parents=True, exist_ok=True)

        try:
            Gio.AppInfo.launch_default_for_uri(f"file://{log_path}", None)
        except GLib.Error as e:
            logger.error(f"Failed to open logs folder: {e}")

    def _on_export_emails_clicked(self, row: Adw.ActionRow) -> None:
        """Handle export to MBOX button click."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Export to MBOX")
        dialog.select_folder(self, None, self._on_export_mbox_folder_selected)

    def _on_export_mbox_folder_selected(
        self,
        dialog: Gtk.FileDialog,
        result: Gio.AsyncResult,
    ) -> None:
        """Handle MBOX export folder selection."""
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                path = Path(folder.get_path())
                self._perform_mbox_export(path)
        except GLib.Error as e:
            if e.code != Gtk.DialogError.DISMISSED:
                logger.error(f"Error selecting export folder: {e}")

    def _perform_mbox_export(self, path: Path) -> None:
        """Perform MBOX export."""
        progress_dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Exporting...",
            body="Please wait while your emails are exported.",
        )
        spinner = Gtk.Spinner(spinning=True)
        progress_dialog.set_extra_child(spinner)
        progress_dialog.present()

        def do_export():
            try:
                # Export logic would go here
                export_file = path / f"unitmail_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mbox"
                export_file.write_text("# MBOX Export\n")
                GLib.idle_add(self._show_export_success, export_file, progress_dialog)
            except Exception as e:
                GLib.idle_add(self._show_export_error, str(e), progress_dialog)
            return False

        GLib.timeout_add(100, do_export)

    def _on_export_json_clicked(self, row: Adw.ActionRow) -> None:
        """Handle export to JSON button click."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Export to JSON")
        dialog.select_folder(self, None, self._on_export_json_folder_selected)

    def _on_export_json_folder_selected(
        self,
        dialog: Gtk.FileDialog,
        result: Gio.AsyncResult,
    ) -> None:
        """Handle JSON export folder selection."""
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                path = Path(folder.get_path())
                self._perform_json_export(path)
        except GLib.Error as e:
            if e.code != Gtk.DialogError.DISMISSED:
                logger.error(f"Error selecting export folder: {e}")

    def _perform_json_export(self, path: Path) -> None:
        """Perform JSON export."""
        progress_dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Exporting...",
            body="Please wait while your data is exported.",
        )
        spinner = Gtk.Spinner(spinning=True)
        progress_dialog.set_extra_child(spinner)
        progress_dialog.present()

        def do_export():
            try:
                storage = get_local_storage()
                export_file = path / f"unitmail_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

                data = {
                    "export_date": datetime.now().isoformat(),
                    "messages": storage.get_all_messages(limit=10000),
                    "folders": storage.get_folders(),
                }

                with open(export_file, "w") as f:
                    json.dump(data, f, indent=2, default=str)

                GLib.idle_add(self._show_export_success, export_file, progress_dialog)
            except Exception as e:
                GLib.idle_add(self._show_export_error, str(e), progress_dialog)
            return False

        GLib.timeout_add(100, do_export)

    def _show_export_success(self, path: Path, progress_dialog: Adw.MessageDialog) -> bool:
        """Show export success dialog."""
        progress_dialog.close()

        success_dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Export Complete",
            body=f"Data exported to:\n{path}",
        )
        success_dialog.add_response("close", "Close")
        success_dialog.add_response("open", "Open Folder")
        success_dialog.connect("response", self._on_export_success_response, path)
        success_dialog.present()
        return False

    def _on_export_success_response(
        self,
        dialog: Adw.MessageDialog,
        response: str,
        path: Path,
    ) -> None:
        """Handle export success dialog response."""
        if response == "open":
            try:
                Gio.AppInfo.launch_default_for_uri(f"file://{path.parent}", None)
            except GLib.Error as e:
                logger.error(f"Failed to open folder: {e}")

    def _show_export_error(self, error: str, progress_dialog: Adw.MessageDialog) -> bool:
        """Show export error dialog."""
        progress_dialog.close()

        error_dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Export Failed",
            body=f"An error occurred:\n{error}",
        )
        error_dialog.add_response("close", "Close")
        error_dialog.present()
        return False

    def _on_reset_clicked(self, row: Adw.ActionRow) -> None:
        """Handle reset to defaults button click."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Reset Settings?",
            body="This will restore all settings to their default values. This cannot be undone.",
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
        """Handle reset dialog response."""
        if response == "reset":
            self._settings.reset_to_defaults()
            self._load_settings()
            logger.info("Settings reset to defaults")


class PasswordChangeDialog(Adw.Window):
    """Dialog for changing account password."""

    __gtype_name__ = "PasswordChangeDialog"

    def __init__(self, parent: Gtk.Window) -> None:
        super().__init__(
            title="Change Password",
            modal=True,
            default_width=400,
            default_height=350,
        )
        self.set_transient_for(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the password change dialog UI."""
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
        )
        self.set_content(box)

        # Header bar
        header = Adw.HeaderBar()
        box.append(header)

        # Content
        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            margin_start=24,
            margin_end=24,
            margin_top=24,
            margin_bottom=24,
        )
        box.append(content)

        # Current password
        self._current_password = Adw.PasswordEntryRow(
            title="Current Password",
        )
        self._current_password.connect("changed", self._validate)

        # New password
        self._new_password = Adw.PasswordEntryRow(
            title="New Password",
        )
        self._new_password.connect("changed", self._validate)

        # Confirm password
        self._confirm_password = Adw.PasswordEntryRow(
            title="Confirm Password",
        )
        self._confirm_password.connect("changed", self._validate)

        password_group = Adw.PreferencesGroup()
        password_group.add(self._current_password)
        password_group.add(self._new_password)
        password_group.add(self._confirm_password)
        content.append(password_group)

        # Buttons
        button_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            halign=Gtk.Align.END,
            margin_top=16,
        )

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda b: self.close())
        button_box.append(cancel_button)

        self._save_button = Gtk.Button(
            label="Change Password",
            css_classes=["suggested-action"],
            sensitive=False,
        )
        self._save_button.connect("clicked", self._on_save_clicked)
        button_box.append(self._save_button)

        content.append(button_box)

    def _validate(self, *args) -> None:
        """Validate password fields."""
        current = self._current_password.get_text()
        new = self._new_password.get_text()
        confirm = self._confirm_password.get_text()

        valid = bool(current and new and confirm and new == confirm and len(new) >= 8)

        if new != confirm and confirm:
            self._confirm_password.add_css_class("error")
        else:
            self._confirm_password.remove_css_class("error")

        if new and len(new) < 8:
            self._new_password.add_css_class("error")
        else:
            self._new_password.remove_css_class("error")

        self._save_button.set_sensitive(valid)

    def _on_save_clicked(self, button: Gtk.Button) -> None:
        """Handle save button click."""
        # Would actually change password here
        logger.info("Password changed")
        self.close()


def create_settings_window(parent: Gtk.Window) -> SettingsWindow:
    """Create and return a settings window.

    Factory function for creating settings windows.

    Args:
        parent: Parent window for the settings dialog.

    Returns:
        A new SettingsWindow instance.
    """
    return SettingsWindow(parent=parent)
