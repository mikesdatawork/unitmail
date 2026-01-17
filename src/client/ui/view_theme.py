"""
View theme manager for unitMail.

Provides three email view themes:
- standard (default): Balanced view with moderate spacing
- compact: Dense view for power users, hides preview
- comfortable: Spacious view with larger fonts and previews
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gio", "2.0")

from gi.repository import Gio, GObject, Gtk

logger = logging.getLogger(__name__)


class ViewTheme(Enum):
    """Available view themes for email list."""
    STANDARD = "standard"
    MINIMAL = "minimal"


# Theme descriptions for UI
THEME_DESCRIPTIONS = {
    ViewTheme.STANDARD: "Balanced view with sender, subject, and preview",
    ViewTheme.MINIMAL: "Single line: date | from | subject",
}


class ViewThemeManager(GObject.Object):
    """
    Manages view theme state and applies CSS classes.

    Signals:
        theme-changed: Emitted when the view theme changes
    """

    __gsignals__ = {
        "theme-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    _instance: Optional["ViewThemeManager"] = None

    def __new__(cls) -> "ViewThemeManager":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        super().__init__()
        self._initialized = True
        self._current_theme = ViewTheme.STANDARD
        self._managed_widgets: list[Gtk.Widget] = []
        self._settings = Gio.Settings.new("org.unitmail.client") if self._settings_exist() else None

        # Load saved theme
        if self._settings:
            saved = self._settings.get_string("view-theme")
            try:
                self._current_theme = ViewTheme(saved)
            except ValueError:
                self._current_theme = ViewTheme.STANDARD

    def _settings_exist(self) -> bool:
        """Check if GSettings schema exists."""
        try:
            schema_source = Gio.SettingsSchemaSource.get_default()
            if schema_source:
                schema = schema_source.lookup("org.unitmail.client", True)
                return schema is not None
        except Exception:
            pass
        return False

    @property
    def current_theme(self) -> ViewTheme:
        """Get current view theme."""
        return self._current_theme

    def set_theme(self, theme: ViewTheme) -> None:
        """
        Set the view theme and update all managed widgets.

        Args:
            theme: The new view theme to apply
        """
        logger.info(f"ViewThemeManager.set_theme called with: {theme.value}")
        current_value = self._current_theme.value if self._current_theme else "None"
        logger.info(f"Current theme: {current_value}, managed widgets: {len(self._managed_widgets)}")

        if theme == self._current_theme:
            logger.info("Theme unchanged, skipping")
            return

        # Initialize if None (recovery from corrupted state)
        if self._current_theme is None:
            self._current_theme = ViewTheme.STANDARD

        old_theme = self._current_theme
        self._current_theme = theme

        # Update all managed widgets
        for widget in self._managed_widgets:
            logger.info(f"Applying theme to widget: {widget}, has parent: {widget.get_parent() is not None}")
            self._apply_theme_to_widget(widget, old_theme, theme)

        # Save to settings
        if self._settings:
            self._settings.set_string("view-theme", theme.value)

        # Emit signal
        self.emit("theme-changed", theme.value)
        logger.info(f"Theme changed to: {theme.value}")

    def register_widget(self, widget: Gtk.Widget) -> None:
        """
        Register a widget to receive theme updates.

        Args:
            widget: Widget to manage (typically message list container)
        """
        logger.info(f"Registering widget: {widget}")
        if widget not in self._managed_widgets:
            self._managed_widgets.append(widget)
            self._apply_theme_to_widget(widget, None, self._current_theme)
            logger.info(f"Widget registered, applying theme: {self._current_theme.value}")

            # Clean up when widget is destroyed
            widget.connect("destroy", self._on_widget_destroyed)

    def unregister_widget(self, widget: Gtk.Widget) -> None:
        """Remove widget from theme management."""
        if widget in self._managed_widgets:
            self._managed_widgets.remove(widget)

    def _on_widget_destroyed(self, widget: Gtk.Widget) -> None:
        """Handle widget destruction."""
        self.unregister_widget(widget)

    def _apply_theme_to_widget(
        self,
        widget: Gtk.Widget,
        old_theme: Optional[ViewTheme],
        new_theme: ViewTheme,
    ) -> None:
        """Apply theme CSS class to widget."""
        # Remove old theme class
        if old_theme:
            old_class = f"view-theme-{old_theme.value}"
            widget.remove_css_class(old_class)
            logger.info(f"Removed CSS class: {old_class}")

        # Add new theme class
        new_class = f"view-theme-{new_theme.value}"
        widget.add_css_class(new_class)
        logger.info(f"Added CSS class: {new_class}")

    def get_theme_names(self) -> list[str]:
        """Get list of available theme names."""
        return [t.value for t in ViewTheme]

    def get_theme_description(self, theme: ViewTheme) -> str:
        """Get description for a theme."""
        return THEME_DESCRIPTIONS.get(theme, "")


class ViewThemeSelector(Gtk.Box):
    """
    Widget for selecting view theme.

    Displays radio buttons for each theme option.
    """

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        self._manager = ViewThemeManager()
        self._radio_group: Optional[Gtk.CheckButton] = None

        self._build_ui()

        # Listen for external theme changes
        self._manager.connect("theme-changed", self._on_theme_changed)

    def _build_ui(self) -> None:
        """Build the theme selector UI."""
        # Header
        header = Gtk.Label(label="Message List Density")
        header.add_css_class("heading")
        header.set_halign(Gtk.Align.START)
        self.append(header)

        # Theme options
        for theme in ViewTheme:
            radio = Gtk.CheckButton(label=theme.value.capitalize())
            radio.set_tooltip_text(THEME_DESCRIPTIONS[theme])

            if self._radio_group is None:
                self._radio_group = radio
            else:
                radio.set_group(self._radio_group)

            if theme == self._manager.current_theme:
                radio.set_active(True)

            radio.connect("toggled", self._on_radio_toggled, theme)

            # Add description label
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.append(radio)

            desc = Gtk.Label(label=THEME_DESCRIPTIONS[theme])
            desc.add_css_class("dim-label")
            desc.set_halign(Gtk.Align.START)
            desc.set_margin_start(24)
            box.append(desc)

            self.append(box)

    def _on_radio_toggled(self, button: Gtk.CheckButton, theme: ViewTheme) -> None:
        """Handle radio button toggle."""
        if button.get_active():
            self._manager.set_theme(theme)

    def _on_theme_changed(self, manager: ViewThemeManager, theme_name: str) -> None:
        """Handle external theme change."""
        # Update radio buttons if changed externally
        pass  # Radio buttons handle their own state


def get_view_theme_manager() -> ViewThemeManager:
    """Get the singleton view theme manager instance."""
    return ViewThemeManager()
