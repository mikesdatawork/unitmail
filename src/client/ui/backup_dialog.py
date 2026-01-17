"""
Backup dialog for unitMail.

This module provides a dialog for creating encrypted backups of user data
including messages, contacts, folders, configuration, and cryptographic keys.
"""

import logging
from pathlib import Path
from typing import Optional
from uuid import UUID

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from client.services.backup_service import (
    BackupContents,
    BackupMetadata,
    BackupProgress,
    BackupService,
    get_backup_service,
)

logger = logging.getLogger(__name__)


class BackupDialog(Adw.Window):
    """
    Dialog for creating unitMail backups.

    Provides options for:
    - Selecting backup destination
    - Setting encryption password
    - Choosing what data to include
    - Full or incremental backup mode
    - Progress display
    """

    __gtype_name__ = "BackupDialog"

    def __init__(
        self,
        parent: Optional[Gtk.Window] = None,
        user_id: Optional[UUID] = None,
        user_email: str = "",
        backup_service: Optional[BackupService] = None,
    ) -> None:
        """
        Initialize the backup dialog.

        Args:
            parent: Parent window.
            user_id: ID of user to backup.
            user_email: User's email address.
            backup_service: Backup service instance.
        """
        super().__init__(
            title="Create Backup",
            modal=True,
            default_width=500,
            default_height=600,
        )

        if parent:
            self.set_transient_for(parent)

        self._user_id = user_id
        self._user_email = user_email
        self._backup_service = backup_service or get_backup_service()
        self._output_path: Optional[Path] = None
        self._is_running = False

        self._build_ui()
        self._connect_signals()

        logger.info("BackupDialog initialized")

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar
        header = Adw.HeaderBar()
        header.add_css_class("flat")

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", self._on_cancel_clicked)
        header.pack_start(cancel_button)
        self._cancel_button = cancel_button

        backup_button = Gtk.Button(label="Create Backup")
        backup_button.add_css_class("suggested-action")
        backup_button.set_sensitive(False)
        backup_button.connect("clicked", self._on_backup_clicked)
        header.pack_end(backup_button)
        self._backup_button = backup_button

        main_box.append(header)

        # Content area with scroll
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
            margin_start=24,
            margin_end=24,
            margin_top=24,
            margin_bottom=24,
        )

        # Destination group
        dest_group = Adw.PreferencesGroup(
            title="Backup Destination",
            description="Choose where to save the backup file",
        )

        dest_row = Adw.ActionRow(
            title="Location",
            subtitle="Select a folder to save the backup",
            activatable=True,
        )

        self._dest_label = Gtk.Label(
            label="Not selected",
            css_classes=["dim-label"],
            valign=Gtk.Align.CENTER,
            ellipsize=3,  # PANGO_ELLIPSIZE_END
            max_width_chars=25,
        )
        dest_row.add_suffix(self._dest_label)

        browse_button = Gtk.Button(
            icon_name="folder-open-symbolic",
            valign=Gtk.Align.CENTER,
            tooltip_text="Browse",
        )
        browse_button.connect("clicked", self._on_browse_clicked)
        dest_row.add_suffix(browse_button)

        dest_group.add(dest_row)

        # Filename
        self._filename_row = Adw.EntryRow(
            title="Filename",
        )
        self._filename_row.set_text(self._generate_default_filename())
        self._filename_row.connect("changed", self._validate_form)
        dest_group.add(self._filename_row)

        content.append(dest_group)

        # Security group
        security_group = Adw.PreferencesGroup(
            title="Encryption",
            description="Protect your backup with a password",
        )

        self._password_row = Adw.PasswordEntryRow(
            title="Password",
        )
        self._password_row.connect("changed", self._validate_form)
        security_group.add(self._password_row)

        self._confirm_password_row = Adw.PasswordEntryRow(
            title="Confirm Password",
        )
        self._confirm_password_row.connect("changed", self._validate_form)
        security_group.add(self._confirm_password_row)

        # Password strength indicator
        strength_row = Adw.ActionRow(
            title="Password Strength",
        )
        self._strength_bar = Gtk.LevelBar(
            min_value=0,
            max_value=4,
            value=0,
            valign=Gtk.Align.CENTER,
            hexpand=True,
        )
        self._strength_bar.set_size_request(150, -1)
        strength_row.add_suffix(self._strength_bar)

        self._strength_label = Gtk.Label(
            label="",
            css_classes=["dim-label"],
            valign=Gtk.Align.CENTER,
        )
        strength_row.add_suffix(self._strength_label)

        security_group.add(strength_row)

        content.append(security_group)

        # Contents group
        contents_group = Adw.PreferencesGroup(
            title="Backup Contents",
            description="Select what to include in the backup",
        )

        self._messages_switch = Adw.SwitchRow(
            title="Messages",
            subtitle="All email messages",
            active=True,
        )
        contents_group.add(self._messages_switch)

        self._contacts_switch = Adw.SwitchRow(
            title="Contacts",
            subtitle="Address book entries",
            active=True,
        )
        contents_group.add(self._contacts_switch)

        self._folders_switch = Adw.SwitchRow(
            title="Folders",
            subtitle="Custom folder structure",
            active=True,
        )
        contents_group.add(self._folders_switch)

        self._config_switch = Adw.SwitchRow(
            title="Configuration",
            subtitle="Application settings",
            active=True,
        )
        contents_group.add(self._config_switch)

        self._dkim_switch = Adw.SwitchRow(
            title="DKIM Keys",
            subtitle="Email signing keys",
            active=True,
        )
        contents_group.add(self._dkim_switch)

        self._pgp_switch = Adw.SwitchRow(
            title="PGP Keys",
            subtitle="Encryption keys (stored encrypted)",
            active=True,
        )
        contents_group.add(self._pgp_switch)

        content.append(contents_group)

        # Options group
        options_group = Adw.PreferencesGroup(
            title="Backup Type",
        )

        self._incremental_switch = Adw.SwitchRow(
            title="Incremental Backup",
            subtitle="Only backup changes since last backup",
            active=False,
        )
        options_group.add(self._incremental_switch)

        content.append(options_group)

        # Progress group (hidden initially)
        self._progress_group = Adw.PreferencesGroup(
            title="Progress",
            visible=False,
        )

        progress_row = Adw.ActionRow(
            title="Creating backup...",
        )
        self._progress_status = progress_row

        self._progress_bar = Gtk.ProgressBar(
            valign=Gtk.Align.CENTER,
            hexpand=True,
            show_text=True,
        )
        self._progress_bar.set_size_request(200, -1)
        progress_row.add_suffix(self._progress_bar)

        self._progress_group.add(progress_row)

        content.append(self._progress_group)

        scrolled.set_child(content)
        main_box.append(scrolled)

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self.connect("close-request", self._on_close_request)

    def _generate_default_filename(self) -> str:
        """Generate a default backup filename."""
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"unitmail_backup_{timestamp}"

    def _validate_form(self, *args) -> None:
        """Validate form and enable/disable backup button."""
        is_valid = True

        # Check destination
        if self._output_path is None:
            is_valid = False

        # Check filename
        filename = self._filename_row.get_text().strip()
        if not filename:
            is_valid = False

        # Check passwords
        password = self._password_row.get_text()
        confirm = self._confirm_password_row.get_text()

        if len(password) < 8:
            is_valid = False
        elif password != confirm:
            is_valid = False
            if confirm:
                self._confirm_password_row.add_css_class("error")
        else:
            self._confirm_password_row.remove_css_class("error")

        # Update password strength
        self._update_password_strength(password)

        self._backup_button.set_sensitive(is_valid and not self._is_running)

    def _update_password_strength(self, password: str) -> None:
        """Update password strength indicator."""
        strength = 0
        label = "Weak"

        if len(password) >= 8:
            strength += 1
        if len(password) >= 12:
            strength += 1
        if any(c.isupper() for c in password) and any(c.islower() for c in password):
            strength += 1
        if any(c.isdigit() for c in password):
            strength += 0.5
        if any(not c.isalnum() for c in password):
            strength += 0.5

        self._strength_bar.set_value(strength)

        if strength <= 1:
            label = "Weak"
            self._strength_label.remove_css_class("success")
            self._strength_label.add_css_class("error")
        elif strength <= 2:
            label = "Fair"
            self._strength_label.remove_css_class("error")
            self._strength_label.remove_css_class("success")
        elif strength <= 3:
            label = "Good"
            self._strength_label.remove_css_class("error")
            self._strength_label.remove_css_class("success")
        else:
            label = "Strong"
            self._strength_label.remove_css_class("error")
            self._strength_label.add_css_class("success")

        self._strength_label.set_label(label)

    def _on_browse_clicked(self, button: Gtk.Button) -> None:
        """Handle browse button click."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Select Backup Destination")

        # Default to user's documents or home
        initial_folder = Gio.File.new_for_path(
            str(Path.home() / "Documents")
        )
        if not initial_folder.query_exists(None):
            initial_folder = Gio.File.new_for_path(str(Path.home()))

        dialog.set_initial_folder(initial_folder)
        dialog.select_folder(self, None, self._on_folder_selected)

    def _on_folder_selected(
        self,
        dialog: Gtk.FileDialog,
        result: Gio.AsyncResult,
    ) -> None:
        """Handle folder selection response."""
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                self._output_path = Path(folder.get_path())
                self._dest_label.set_label(self._output_path.name)
                self._dest_label.set_tooltip_text(str(self._output_path))
                self._validate_form()

        except GLib.Error as e:
            if e.code != Gtk.DialogError.DISMISSED:
                logger.error("Failed to select folder: %s", e.message)

    def _on_cancel_clicked(self, button: Gtk.Button) -> None:
        """Handle cancel button click."""
        if self._is_running:
            # Confirm cancellation
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Cancel Backup?",
                body="The backup is still in progress. Are you sure you want to cancel?",
            )
            dialog.add_response("continue", "Continue Backup")
            dialog.add_response("cancel", "Cancel Backup")
            dialog.set_response_appearance("cancel", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.connect("response", self._on_cancel_confirmed)
            dialog.present()
        else:
            self.close()

    def _on_cancel_confirmed(
        self,
        dialog: Adw.MessageDialog,
        response: str,
    ) -> None:
        """Handle cancel confirmation response."""
        if response == "cancel":
            self._is_running = False
            self.close()

    def _on_backup_clicked(self, button: Gtk.Button) -> None:
        """Handle backup button click."""
        if self._user_id is None:
            self._show_error("No user ID provided")
            return

        self._start_backup()

    def _start_backup(self) -> None:
        """Start the backup process."""
        self._is_running = True
        self._backup_button.set_sensitive(False)
        self._progress_group.set_visible(True)

        # Get backup path
        filename = self._filename_row.get_text().strip()
        if not filename.endswith(".unitmail-backup"):
            filename += ".unitmail-backup"

        backup_path = self._output_path / filename
        password = self._password_row.get_text()

        # Get contents selection
        contents = BackupContents(
            messages=self._messages_switch.get_active(),
            contacts=self._contacts_switch.get_active(),
            folders=self._folders_switch.get_active(),
            configuration=self._config_switch.get_active(),
            dkim_keys=self._dkim_switch.get_active(),
            pgp_keys=self._pgp_switch.get_active(),
        )

        incremental = self._incremental_switch.get_active()

        # Set progress callback
        self._backup_service.set_progress_callback(self._on_progress)

        # Run backup in thread
        def run_backup():
            import asyncio

            async def do_backup():
                return await self._backup_service.create_backup(
                    output_path=backup_path,
                    password=password,
                    user_id=self._user_id,
                    user_email=self._user_email,
                    contents=contents,
                    incremental=incremental,
                )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(do_backup())
            finally:
                loop.close()

        def on_complete(metadata):
            GLib.idle_add(self._on_backup_complete, metadata, None)

        def on_error(error):
            GLib.idle_add(self._on_backup_complete, None, error)

        # Run in thread
        import threading

        def thread_target():
            try:
                result = run_backup()
                on_complete(result)
            except Exception as e:
                on_error(e)

        thread = threading.Thread(target=thread_target, daemon=True)
        thread.start()

    def _on_progress(self, progress: BackupProgress) -> None:
        """Handle progress update from backup service."""
        GLib.idle_add(self._update_progress_ui, progress)

    def _update_progress_ui(self, progress: BackupProgress) -> None:
        """Update progress UI (must be called from main thread)."""
        self._progress_status.set_title(progress.current_step)
        self._progress_bar.set_fraction(progress.percent_complete / 100)
        self._progress_bar.set_text(f"{progress.percent_complete:.0f}%")

        return False

    def _on_backup_complete(
        self,
        metadata: Optional[BackupMetadata],
        error: Optional[Exception],
    ) -> None:
        """Handle backup completion."""
        self._is_running = False
        self._backup_service.set_progress_callback(None)

        if error:
            self._show_error(str(error))
            self._progress_group.set_visible(False)
            self._backup_button.set_sensitive(True)
        else:
            self._show_success(metadata)

        return False

    def _show_error(self, message: str) -> None:
        """Show error dialog."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Backup Failed",
            body=message,
        )
        dialog.add_response("ok", "OK")
        dialog.present()

    def _show_success(self, metadata: Optional[BackupMetadata]) -> None:
        """Show success dialog."""
        if metadata:
            items = metadata.contents
            body = "Backup created successfully.\n\n"
            body += "Items backed up:\n"

            if items.get("messages", 0) > 0:
                body += f"  Messages: {items['messages']}\n"
            if items.get("contacts", 0) > 0:
                body += f"  Contacts: {items['contacts']}\n"
            if items.get("folders", 0) > 0:
                body += f"  Folders: {items['folders']}\n"
            if items.get("configuration", 0) > 0:
                body += f"  Configuration: {items['configuration']} settings\n"
            if items.get("dkim_keys", 0) > 0:
                body += "  DKIM Keys: included\n"
            if items.get("pgp_keys", 0) > 0:
                body += "  PGP Keys: included\n"
        else:
            body = "Backup created successfully."

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Backup Complete",
            body=body,
        )
        dialog.add_response("ok", "OK")
        dialog.connect("response", lambda d, r: self.close())
        dialog.present()

    def _on_close_request(self, window: Gtk.Window) -> bool:
        """Handle window close request."""
        if self._is_running:
            self._on_cancel_clicked(None)
            return True  # Prevent immediate close
        return False


def create_backup_dialog(
    parent: Optional[Gtk.Window] = None,
    user_id: Optional[UUID] = None,
    user_email: str = "",
) -> BackupDialog:
    """
    Create and return a backup dialog.

    Args:
        parent: Optional parent window.
        user_id: ID of user to backup.
        user_email: User's email address.

    Returns:
        New BackupDialog instance.
    """
    return BackupDialog(
        parent=parent,
        user_id=user_id,
        user_email=user_email,
    )
