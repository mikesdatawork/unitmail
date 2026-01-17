"""
unitMail GTK Application.

This module provides the main GTK 4 application class that manages
the application lifecycle, actions, and window management.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import gi

if TYPE_CHECKING:
    from .main_window import MainWindow

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

logger = logging.getLogger(__name__)


class UnitMailApplication(Adw.Application):
    """
    Main unitMail GTK Application.

    Manages the application lifecycle, single instance handling,
    action registration, and CSS theme loading.

    Attributes:
        main_window: The primary application window.
    """

    APP_ID = "io.unitmail.client"

    def __init__(self) -> None:
        """Initialize the unitMail application."""
        super().__init__(
            application_id=self.APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )

        self.main_window: Optional["MainWindow"] = None
        self._css_provider: Optional[Gtk.CssProvider] = None

        # Set application metadata
        GLib.set_application_name("unitMail")
        GLib.set_prgname("unitmail")

    def do_startup(self) -> None:
        """
        Handle application startup.

        Called when the application is first started. Sets up
        actions, keyboard shortcuts, and loads CSS styles.
        """
        Adw.Application.do_startup(self)

        logger.info("unitMail application starting up")

        # Register actions
        self._register_actions()

        # Set up keyboard accelerators
        self._setup_accelerators()

        # Load CSS styles
        self._load_styles()

    def do_activate(self) -> None:
        """
        Handle application activation.

        Called when the application is activated (e.g., when the user
        launches it or clicks on the dock icon). Creates or presents
        the main window.
        """
        # Import here to avoid circular imports
        from client.ui.main_window import MainWindow

        if not self.main_window:
            logger.info("Creating main window")
            self.main_window = MainWindow(application=self)

        self.main_window.present()

    def do_open(
        self,
        files: list[Gio.File],
        n_files: int,
        hint: str,
    ) -> None:
        """
        Handle opening files.

        Called when the application is asked to open files (e.g., .eml files).

        Args:
            files: List of files to open.
            n_files: Number of files.
            hint: A hint about how to handle the files.
        """
        self.do_activate()

        if self.main_window:
            for file in files:
                path = file.get_path()
                if path:
                    logger.info(f"Opening file: {path}")
                    # TODO: Implement file opening logic
                    # self.main_window.open_message_file(path)

    def do_shutdown(self) -> None:
        """
        Handle application shutdown.

        Called when the application is shutting down. Performs cleanup
        and saves any pending state.
        """
        logger.info("unitMail application shutting down")

        # Save window state before closing
        if self.main_window:
            self.main_window.save_window_state()

        Adw.Application.do_shutdown(self)

    def _register_actions(self) -> None:
        """Register application-level actions."""
        # Quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self._on_quit)
        self.add_action(quit_action)

        # Compose action
        compose_action = Gio.SimpleAction.new("compose", None)
        compose_action.connect("activate", self._on_compose)
        self.add_action(compose_action)

        # Settings action
        settings_action = Gio.SimpleAction.new("settings", None)
        settings_action.connect("activate", self._on_settings)
        self.add_action(settings_action)

        # About action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        # Refresh action
        refresh_action = Gio.SimpleAction.new("refresh", None)
        refresh_action.connect("activate", self._on_refresh)
        self.add_action(refresh_action)

        # Dark mode toggle
        dark_mode_action = Gio.SimpleAction.new_stateful(
            "dark-mode",
            None,
            GLib.Variant.new_boolean(False),
        )
        dark_mode_action.connect("change-state", self._on_dark_mode_toggle)
        self.add_action(dark_mode_action)

        logger.debug("Application actions registered")

    def _setup_accelerators(self) -> None:
        """Set up keyboard accelerators for actions."""
        accelerators = {
            "app.quit": ["<Control>q"],
            "app.compose": ["<Control>n"],
            "app.settings": ["<Control>comma"],
            "app.refresh": ["<Control>r", "F5"],
            "win.delete-message": ["Delete"],
            "win.reply": ["<Control><Shift>r"],
            "win.reply-all": ["<Control><Shift>a"],
            "win.forward": ["<Control><Shift>f"],
            "win.mark-read": ["<Control>m"],
            "win.mark-starred": ["<Control>s"],
            "win.search": ["<Control>f"],
            "win.next-message": ["j", "Down"],
            "win.previous-message": ["k", "Up"],
        }

        for action, accels in accelerators.items():
            self.set_accels_for_action(action, accels)

        logger.debug("Keyboard accelerators set up")

    def _load_styles(self) -> None:
        """Load CSS styles for the application."""
        self._css_provider = Gtk.CssProvider()

        # Look for styles.css in the same directory as this module
        styles_path = Path(__file__).parent / "styles.css"

        if styles_path.exists():
            try:
                self._css_provider.load_from_path(str(styles_path))

                # Apply CSS to the default display
                display = Gdk.Display.get_default()
                if display:
                    Gtk.StyleContext.add_provider_for_display(
                        display,
                        self._css_provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                    )
                    logger.info(f"Loaded CSS styles from {styles_path}")
                else:
                    logger.warning("No default display available for CSS")
            except Exception as e:
                logger.warning(f"Failed to load CSS styles: {e}")
        else:
            logger.debug(f"No CSS file found at {styles_path}")

    def apply_css_to_display(self, display: "Gdk.Display") -> None:
        """
        Apply CSS styles to a specific display.

        Args:
            display: The GDK display to apply styles to.
        """
        if self._css_provider:
            Gtk.StyleContext.add_provider_for_display(
                display,
                self._css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def _on_quit(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle quit action."""
        logger.info("Quit action triggered")
        self.quit()

    def _on_compose(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle compose action."""
        logger.info("Compose action triggered")
        if self.main_window:
            self.main_window.show_compose_dialog()

    def _on_settings(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle settings action."""
        logger.info("Settings action triggered")
        if self.main_window:
            self.main_window.show_settings_dialog()

    def _on_about(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle about action."""
        about = Adw.AboutWindow(
            transient_for=self.main_window,
            application_name="unitMail",
            application_icon="mail-send-receive",
            developer_name="unitMail Team",
            version="1.0.0",
            copyright="Copyright 2024-2026 unitMail Team",
            license_type=Gtk.License.GPL_3_0,
            website="https://unitmail.io",
            issue_url="https://github.com/unitmail/unitmail/issues",
            developers=["unitMail Team"],
            comments="A modern, privacy-focused email client",
        )
        about.present()

    def _on_refresh(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle refresh action."""
        logger.info("Refresh action triggered")
        if self.main_window:
            self.main_window.refresh_messages()

    def _on_dark_mode_toggle(
        self,
        action: Gio.SimpleAction,
        state: GLib.Variant,
    ) -> None:
        """Handle dark mode toggle."""
        is_dark = state.get_boolean()
        action.set_state(state)

        style_manager = Adw.StyleManager.get_default()
        if is_dark:
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)

        logger.info(f"Dark mode {'enabled' if is_dark else 'disabled'}")


def run_application(args: Optional[list[str]] = None) -> int:
    """
    Run the unitMail application.

    Args:
        args: Command-line arguments. If None, uses sys.argv.

    Returns:
        Exit code from the application.
    """
    if args is None:
        args = sys.argv

    app = UnitMailApplication()
    return app.run(args)
