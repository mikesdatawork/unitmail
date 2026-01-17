"""
Restore dialog for unitMail.

This module provides a dialog for restoring data from encrypted backups,
with preview capability, selective restore options, and conflict resolution.
"""

import logging
from pathlib import Path
from typing import Optional
from uuid import UUID

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from client.services.backup_service import (
    BackupContents,
    BackupService,
    ConflictResolution,
    RestoreError,
    RestoreMode,
    RestorePreview,
    BackupProgress,
    get_backup_service,
)

logger = logging.getLogger(__name__)


class RestoreDialog(Adw.Window):
    """
    Dialog for restoring unitMail backups.

    Provides:
    - File selection for backup
    - Password entry for decryption
    - Preview of backup contents
    - Selective restore options
    - Conflict resolution settings
    - Progress display
    """

    __gtype_name__ = "RestoreDialog"

    # Dialog states
    STATE_SELECT_FILE = "select_file"
    STATE_ENTER_PASSWORD = "enter_password"
    STATE_PREVIEW = "preview"
    STATE_RESTORING = "restoring"

    def __init__(
        self,
        parent: Optional[Gtk.Window] = None,
        user_id: Optional[UUID] = None,
        backup_service: Optional[BackupService] = None,
    ) -> None:
        """
        Initialize the restore dialog.

        Args:
            parent: Parent window.
            user_id: ID of user to restore data for.
            backup_service: Backup service instance.
        """
        super().__init__(
            title="Restore from Backup",
            modal=True,
            default_width=550,
            default_height=650,
        )

        if parent:
            self.set_transient_for(parent)

        self._user_id = user_id
        self._backup_service = backup_service or get_backup_service()
        self._backup_path: Optional[Path] = None
        self._preview: Optional[RestorePreview] = None
        self._state = self.STATE_SELECT_FILE
        self._is_running = False

        self._build_ui()
        self._connect_signals()
        self._update_state()

        logger.info("RestoreDialog initialized")

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

        # Back button (hidden initially)
        back_button = Gtk.Button(
            icon_name="go-previous-symbolic",
            tooltip_text="Back",
            visible=False,
        )
        back_button.connect("clicked", self._on_back_clicked)
        header.pack_start(back_button)
        self._back_button = back_button

        # Action button (changes based on state)
        action_button = Gtk.Button(label="Next")
        action_button.add_css_class("suggested-action")
        action_button.set_sensitive(False)
        action_button.connect("clicked", self._on_action_clicked)
        header.pack_end(action_button)
        self._action_button = action_button

        main_box.append(header)

        # Stack for different states
        self._stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT,
            vexpand=True,
        )

        # Build pages
        self._stack.add_named(self._build_file_select_page(), "select_file")
        self._stack.add_named(self._build_password_page(), "enter_password")
        self._stack.add_named(self._build_preview_page(), "preview")
        self._stack.add_named(self._build_progress_page(), "restoring")

        main_box.append(self._stack)

    def _build_file_select_page(self) -> Gtk.Widget:
        """Build the file selection page."""
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        )

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
            margin_start=24,
            margin_end=24,
            margin_top=24,
            margin_bottom=24,
        )

        # Description
        description = Gtk.Label(
            label="Select a unitMail backup file to restore your data.",
            wrap=True,
            xalign=0,
            css_classes=["dim-label"],
        )
        content.append(description)

        # File selection group
        file_group = Adw.PreferencesGroup(
            title="Backup File",
        )

        file_row = Adw.ActionRow(
            title="Select Backup",
            subtitle="Choose a .unitmail-backup file",
            activatable=True,
        )
        file_row.connect("activated", self._on_select_file_clicked)

        self._file_label = Gtk.Label(
            label="No file selected",
            css_classes=["dim-label"],
            valign=Gtk.Align.CENTER,
            ellipsize=3,
            max_width_chars=25,
        )
        file_row.add_suffix(self._file_label)

        browse_icon = Gtk.Image(icon_name="document-open-symbolic")
        file_row.add_suffix(browse_icon)

        file_group.add(file_row)

        # File info (hidden initially)
        self._file_info_row = Adw.ActionRow(
            title="File Info",
            visible=False,
        )
        self._file_size_label = Gtk.Label(
            css_classes=["dim-label"],
            valign=Gtk.Align.CENTER,
        )
        self._file_info_row.add_suffix(self._file_size_label)
        file_group.add(self._file_info_row)

        content.append(file_group)

        # Drop target hint
        drop_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            vexpand=True,
            css_classes=["dim-label"],
        )

        drop_icon = Gtk.Image(
            icon_name="document-open-symbolic",
            pixel_size=48,
        )
        drop_box.append(drop_icon)

        drop_label = Gtk.Label(
            label="Or drag and drop a backup file here",
        )
        drop_box.append(drop_label)

        content.append(drop_box)

        # Set up drop target
        drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_file_dropped)
        content.add_controller(drop_target)

        scrolled.set_child(content)
        return scrolled

    def _build_password_page(self) -> Gtk.Widget:
        """Build the password entry page."""
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        )

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
            margin_start=24,
            margin_end=24,
            margin_top=24,
            margin_bottom=24,
        )

        # Description
        description = Gtk.Label(
            label="Enter the password used to encrypt this backup.",
            wrap=True,
            xalign=0,
            css_classes=["dim-label"],
        )
        content.append(description)

        # Password group
        password_group = Adw.PreferencesGroup(
            title="Decryption",
        )

        self._restore_password_row = Adw.PasswordEntryRow(
            title="Password",
        )
        self._restore_password_row.connect("changed", self._on_password_changed)
        self._restore_password_row.connect("entry-activated", self._on_password_activated)
        password_group.add(self._restore_password_row)

        content.append(password_group)

        # Error message (hidden initially)
        self._password_error = Gtk.Label(
            label="",
            css_classes=["error"],
            wrap=True,
            xalign=0,
            visible=False,
        )
        content.append(self._password_error)

        scrolled.set_child(content)
        return scrolled

    def _build_preview_page(self) -> Gtk.Widget:
        """Build the backup preview page."""
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        )

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
            margin_start=24,
            margin_end=24,
            margin_top=24,
            margin_bottom=24,
        )

        # Backup info group
        info_group = Adw.PreferencesGroup(
            title="Backup Information",
        )

        self._backup_date_row = Adw.ActionRow(
            title="Created",
        )
        self._backup_date_label = Gtk.Label(
            css_classes=["dim-label"],
            valign=Gtk.Align.CENTER,
        )
        self._backup_date_row.add_suffix(self._backup_date_label)
        info_group.add(self._backup_date_row)

        self._backup_type_row = Adw.ActionRow(
            title="Backup Type",
        )
        self._backup_type_label = Gtk.Label(
            css_classes=["dim-label"],
            valign=Gtk.Align.CENTER,
        )
        self._backup_type_row.add_suffix(self._backup_type_label)
        info_group.add(self._backup_type_row)

        self._backup_email_row = Adw.ActionRow(
            title="Account",
        )
        self._backup_email_label = Gtk.Label(
            css_classes=["dim-label"],
            valign=Gtk.Align.CENTER,
        )
        self._backup_email_row.add_suffix(self._backup_email_label)
        info_group.add(self._backup_email_row)

        content.append(info_group)

        # Contents selection group
        contents_group = Adw.PreferencesGroup(
            title="Select What to Restore",
            description="Choose which items to restore from the backup",
        )

        self._restore_messages_switch = Adw.SwitchRow(
            title="Messages",
            active=True,
        )
        contents_group.add(self._restore_messages_switch)

        self._restore_contacts_switch = Adw.SwitchRow(
            title="Contacts",
            active=True,
        )
        contents_group.add(self._restore_contacts_switch)

        self._restore_folders_switch = Adw.SwitchRow(
            title="Folders",
            active=True,
        )
        contents_group.add(self._restore_folders_switch)

        self._restore_config_switch = Adw.SwitchRow(
            title="Configuration",
            active=True,
        )
        contents_group.add(self._restore_config_switch)

        self._restore_dkim_switch = Adw.SwitchRow(
            title="DKIM Keys",
            active=True,
        )
        contents_group.add(self._restore_dkim_switch)

        self._restore_pgp_switch = Adw.SwitchRow(
            title="PGP Keys",
            active=True,
        )
        contents_group.add(self._restore_pgp_switch)

        content.append(contents_group)

        # Conflict resolution group
        conflict_group = Adw.PreferencesGroup(
            title="Conflict Resolution",
            description="How to handle items that already exist",
        )

        conflict_items = ["Skip existing", "Overwrite existing", "Keep both"]
        conflict_model = Gtk.StringList.new(conflict_items)
        self._conflict_row = Adw.ComboRow(
            title="When conflicts occur",
            model=conflict_model,
            selected=0,
        )
        conflict_group.add(self._conflict_row)

        content.append(conflict_group)

        scrolled.set_child(content)
        return scrolled

    def _build_progress_page(self) -> Gtk.Widget:
        """Build the restore progress page."""
        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
            margin_start=24,
            margin_end=24,
            margin_top=48,
            margin_bottom=48,
            valign=Gtk.Align.CENTER,
        )

        # Spinner
        spinner = Gtk.Spinner(
            spinning=True,
            halign=Gtk.Align.CENTER,
        )
        spinner.set_size_request(48, 48)
        content.append(spinner)
        self._spinner = spinner

        # Status label
        self._restore_status_label = Gtk.Label(
            label="Restoring...",
            css_classes=["title-2"],
        )
        content.append(self._restore_status_label)

        # Progress bar
        self._restore_progress_bar = Gtk.ProgressBar(
            halign=Gtk.Align.CENTER,
            show_text=True,
        )
        self._restore_progress_bar.set_size_request(300, -1)
        content.append(self._restore_progress_bar)

        # Detail label
        self._restore_detail_label = Gtk.Label(
            label="",
            css_classes=["dim-label"],
        )
        content.append(self._restore_detail_label)

        return content

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self.connect("close-request", self._on_close_request)

    def _update_state(self) -> None:
        """Update UI based on current state."""
        self._stack.set_visible_child_name(self._state)

        if self._state == self.STATE_SELECT_FILE:
            self._back_button.set_visible(False)
            self._action_button.set_label("Next")
            self._action_button.set_sensitive(self._backup_path is not None)
            self._cancel_button.set_label("Cancel")

        elif self._state == self.STATE_ENTER_PASSWORD:
            self._back_button.set_visible(True)
            self._action_button.set_label("Next")
            self._action_button.set_sensitive(
                len(self._restore_password_row.get_text()) > 0
            )
            self._cancel_button.set_label("Cancel")
            # Focus password entry
            self._restore_password_row.grab_focus()

        elif self._state == self.STATE_PREVIEW:
            self._back_button.set_visible(True)
            self._action_button.set_label("Restore")
            self._action_button.set_sensitive(True)
            self._action_button.remove_css_class("suggested-action")
            self._action_button.add_css_class("destructive-action")
            self._cancel_button.set_label("Cancel")

        elif self._state == self.STATE_RESTORING:
            self._back_button.set_visible(False)
            self._action_button.set_visible(False)
            self._cancel_button.set_label("Cancel")
            self._cancel_button.set_sensitive(False)

    def _on_select_file_clicked(self, *args) -> None:
        """Handle file selection row click."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Select Backup File")

        # Set file filter
        filter_store = Gio.ListStore.new(Gtk.FileFilter)

        backup_filter = Gtk.FileFilter()
        backup_filter.set_name("unitMail Backups")
        backup_filter.add_pattern("*.unitmail-backup")
        filter_store.append(backup_filter)

        all_filter = Gtk.FileFilter()
        all_filter.set_name("All Files")
        all_filter.add_pattern("*")
        filter_store.append(all_filter)

        dialog.set_filters(filter_store)
        dialog.set_default_filter(backup_filter)

        dialog.open(self, None, self._on_file_selected)

    def _on_file_selected(
        self,
        dialog: Gtk.FileDialog,
        result: Gio.AsyncResult,
    ) -> None:
        """Handle file selection response."""
        try:
            file = dialog.open_finish(result)
            if file:
                self._set_backup_file(Path(file.get_path()))

        except GLib.Error as e:
            if e.code != Gtk.DialogError.DISMISSED:
                logger.error("Failed to select file: %s", e.message)

    def _on_file_dropped(
        self,
        drop_target: Gtk.DropTarget,
        value: GObject.Value,
        x: float,
        y: float,
    ) -> bool:
        """Handle file drop."""
        if isinstance(value, Gio.File):
            path = Path(value.get_path())
            if path.suffix == ".unitmail-backup":
                self._set_backup_file(path)
                return True

        return False

    def _set_backup_file(self, path: Path) -> None:
        """Set the selected backup file."""
        if not path.exists():
            self._show_error("File does not exist")
            return

        if not BackupService.validate_backup_file(path):
            self._show_error("Invalid backup file")
            return

        self._backup_path = path
        self._file_label.set_label(path.name)
        self._file_label.set_tooltip_text(str(path))

        # Show file info
        size = path.stat().st_size
        size_str = self._format_size(size)
        self._file_size_label.set_label(size_str)
        self._file_info_row.set_visible(True)

        self._update_state()

    def _format_size(self, size: int) -> str:
        """Format file size to human-readable string."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"

    def _on_password_changed(self, row: Adw.PasswordEntryRow) -> None:
        """Handle password entry change."""
        self._password_error.set_visible(False)
        self._action_button.set_sensitive(len(row.get_text()) > 0)

    def _on_password_activated(self, row: Adw.PasswordEntryRow) -> None:
        """Handle Enter key in password entry."""
        if len(row.get_text()) > 0:
            self._on_action_clicked(None)

    def _on_back_clicked(self, button: Gtk.Button) -> None:
        """Handle back button click."""
        if self._state == self.STATE_ENTER_PASSWORD:
            self._state = self.STATE_SELECT_FILE
        elif self._state == self.STATE_PREVIEW:
            self._state = self.STATE_ENTER_PASSWORD

        self._update_state()

    def _on_cancel_clicked(self, button: Gtk.Button) -> None:
        """Handle cancel button click."""
        self.close()

    def _on_action_clicked(self, button: Optional[Gtk.Button]) -> None:
        """Handle action button click."""
        if self._state == self.STATE_SELECT_FILE:
            self._state = self.STATE_ENTER_PASSWORD
            self._update_state()

        elif self._state == self.STATE_ENTER_PASSWORD:
            self._load_preview()

        elif self._state == self.STATE_PREVIEW:
            self._start_restore()

    def _load_preview(self) -> None:
        """Load and display backup preview."""
        if self._backup_path is None:
            return

        password = self._restore_password_row.get_text()

        # Disable UI while loading
        self._action_button.set_sensitive(False)

        def do_preview():
            import asyncio

            async def get_preview():
                return await self._backup_service.preview_restore(
                    self._backup_path,
                    password,
                )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(get_preview())
            finally:
                loop.close()

        def on_complete(preview):
            GLib.idle_add(self._on_preview_loaded, preview, None)

        def on_error(error):
            GLib.idle_add(self._on_preview_loaded, None, error)

        import threading

        def thread_target():
            try:
                result = do_preview()
                on_complete(result)
            except Exception as e:
                on_error(e)

        thread = threading.Thread(target=thread_target, daemon=True)
        thread.start()

    def _on_preview_loaded(
        self,
        preview: Optional[RestorePreview],
        error: Optional[Exception],
    ) -> None:
        """Handle preview load completion."""
        self._action_button.set_sensitive(True)

        if error:
            self._password_error.set_label(
                "Invalid password or corrupted backup file"
            )
            self._password_error.set_visible(True)
            return

        if preview is None:
            return

        self._preview = preview

        # Update preview UI
        metadata = preview.metadata

        # Format date
        from datetime import datetime

        try:
            created = datetime.fromisoformat(metadata.created_at)
            self._backup_date_label.set_label(
                created.strftime("%Y-%m-%d %H:%M:%S")
            )
        except (ValueError, TypeError):
            self._backup_date_label.set_label(metadata.created_at)

        # Backup type
        self._backup_type_label.set_label(
            "Incremental" if metadata.backup_type == "incremental" else "Full"
        )

        # Account email
        self._backup_email_label.set_label(
            metadata.user_email or "Unknown"
        )

        # Update switches with counts
        self._restore_messages_switch.set_subtitle(
            f"{preview.messages_count} messages"
        )
        self._restore_messages_switch.set_active(preview.messages_count > 0)
        self._restore_messages_switch.set_sensitive(preview.messages_count > 0)

        self._restore_contacts_switch.set_subtitle(
            f"{preview.contacts_count} contacts"
        )
        self._restore_contacts_switch.set_active(preview.contacts_count > 0)
        self._restore_contacts_switch.set_sensitive(preview.contacts_count > 0)

        self._restore_folders_switch.set_subtitle(
            f"{preview.folders_count} folders"
        )
        self._restore_folders_switch.set_active(preview.folders_count > 0)
        self._restore_folders_switch.set_sensitive(preview.folders_count > 0)

        self._restore_config_switch.set_subtitle(
            "Included" if preview.has_configuration else "Not included"
        )
        self._restore_config_switch.set_active(preview.has_configuration)
        self._restore_config_switch.set_sensitive(preview.has_configuration)

        self._restore_dkim_switch.set_subtitle(
            "Included" if preview.has_dkim_keys else "Not included"
        )
        self._restore_dkim_switch.set_active(preview.has_dkim_keys)
        self._restore_dkim_switch.set_sensitive(preview.has_dkim_keys)

        self._restore_pgp_switch.set_subtitle(
            "Included" if preview.has_pgp_keys else "Not included"
        )
        self._restore_pgp_switch.set_active(preview.has_pgp_keys)
        self._restore_pgp_switch.set_sensitive(preview.has_pgp_keys)

        # Move to preview state
        self._state = self.STATE_PREVIEW
        self._update_state()

        return False

    def _start_restore(self) -> None:
        """Start the restore process."""
        if self._user_id is None:
            self._show_error("No user ID provided")
            return

        self._is_running = True
        self._state = self.STATE_RESTORING
        self._update_state()

        password = self._restore_password_row.get_text()

        # Get selected contents
        contents = BackupContents(
            messages=self._restore_messages_switch.get_active(),
            contacts=self._restore_contacts_switch.get_active(),
            folders=self._restore_folders_switch.get_active(),
            configuration=self._restore_config_switch.get_active(),
            dkim_keys=self._restore_dkim_switch.get_active(),
            pgp_keys=self._restore_pgp_switch.get_active(),
        )

        # Get conflict resolution
        conflict_map = {
            0: ConflictResolution.SKIP,
            1: ConflictResolution.OVERWRITE,
            2: ConflictResolution.KEEP_BOTH,
        }
        conflict_resolution = conflict_map.get(
            self._conflict_row.get_selected(),
            ConflictResolution.SKIP,
        )

        # Set progress callback
        self._backup_service.set_progress_callback(self._on_progress)

        def do_restore():
            import asyncio

            async def run_restore():
                return await self._backup_service.restore(
                    backup_path=self._backup_path,
                    password=password,
                    user_id=self._user_id,
                    mode=RestoreMode.SELECTIVE,
                    contents=contents,
                    conflict_resolution=conflict_resolution,
                )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(run_restore())
            finally:
                loop.close()

        def on_complete(result):
            GLib.idle_add(self._on_restore_complete, result, None)

        def on_error(error):
            GLib.idle_add(self._on_restore_complete, None, error)

        import threading

        def thread_target():
            try:
                result = do_restore()
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
        self._restore_status_label.set_label(progress.current_step)
        self._restore_progress_bar.set_fraction(progress.percent_complete / 100)
        self._restore_progress_bar.set_text(f"{progress.percent_complete:.0f}%")

        return False

    def _on_restore_complete(
        self,
        result: Optional[dict[str, int]],
        error: Optional[Exception],
    ) -> None:
        """Handle restore completion."""
        self._is_running = False
        self._spinner.stop()
        self._backup_service.set_progress_callback(None)

        if error:
            self._show_error(str(error))
            # Go back to preview state
            self._state = self.STATE_PREVIEW
            self._update_state()
        else:
            self._show_success(result)

        return False

    def _show_error(self, message: str) -> None:
        """Show error dialog."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Restore Failed",
            body=message,
        )
        dialog.add_response("ok", "OK")
        dialog.present()

    def _show_success(self, result: Optional[dict[str, int]]) -> None:
        """Show success dialog."""
        if result:
            body = "Restore completed successfully.\n\n"
            body += "Items restored:\n"

            if result.get("messages", 0) > 0:
                body += f"  Messages: {result['messages']}\n"
            if result.get("contacts", 0) > 0:
                body += f"  Contacts: {result['contacts']}\n"
            if result.get("folders", 0) > 0:
                body += f"  Folders: {result['folders']}\n"
            if result.get("configuration", 0) > 0:
                body += f"  Configuration: {result['configuration']} settings\n"
            if result.get("dkim_keys", 0) > 0:
                body += "  DKIM Keys: restored\n"
            if result.get("pgp_keys", 0) > 0:
                body += "  PGP Keys: restored\n"
        else:
            body = "Restore completed successfully."

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Restore Complete",
            body=body,
        )
        dialog.add_response("ok", "OK")
        dialog.connect("response", lambda d, r: self.close())
        dialog.present()

    def _on_close_request(self, window: Gtk.Window) -> bool:
        """Handle window close request."""
        if self._is_running:
            return True  # Prevent close while restoring
        return False


def create_restore_dialog(
    parent: Optional[Gtk.Window] = None,
    user_id: Optional[UUID] = None,
) -> RestoreDialog:
    """
    Create and return a restore dialog.

    Args:
        parent: Optional parent window.
        user_id: ID of user to restore data for.

    Returns:
        New RestoreDialog instance.
    """
    return RestoreDialog(
        parent=parent,
        user_id=user_id,
    )
