"""
Folder creation dialog for unitMail.

This module provides a reusable dialog for creating new email folders
with input validation for empty names and duplicate detection.
"""

import logging
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, GObject, Gtk

from common.local_storage import get_local_storage

logger = logging.getLogger(__name__)


class FolderCreationDialog(Adw.Window):
    """
    Dialog for creating a new custom email folder.

    Features:
    - Input field for folder name
    - Real-time validation (empty names, duplicates)
    - Visual error feedback
    - Cancel/Create buttons

    This is a reusable component that can be instantiated from anywhere
    in the application that needs folder creation functionality.
    """

    __gtype_name__ = "FolderCreationDialog"

    __gsignals__ = {
        # Emitted when a folder is successfully created
        # Arguments: (folder_id: str, folder_name: str)
        "folder-created": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
    }

    DEFAULT_WIDTH = 400
    DEFAULT_HEIGHT = 200

    def __init__(
        self,
        parent: Optional[Gtk.Window] = None,
        on_folder_created: Optional[Callable[[dict], None]] = None,
    ) -> None:
        """
        Initialize the folder creation dialog.

        Args:
            parent: Parent window for the dialog (makes it modal).
            on_folder_created: Optional callback invoked with the created
                              folder dict when creation succeeds.
        """
        super().__init__(
            title="New Folder",
            modal=True,
            default_width=self.DEFAULT_WIDTH,
            default_height=self.DEFAULT_HEIGHT,
            resizable=False,
        )

        if parent:
            self.set_transient_for(parent)

        self._on_folder_created = on_folder_created
        self._validation_error: Optional[str] = None

        self._build_ui()
        self._connect_signals()

        logger.debug("FolderCreationDialog initialized")

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

        self._create_button = Gtk.Button(label="Create")
        self._create_button.add_css_class("suggested-action")
        self._create_button.set_sensitive(False)
        self._create_button.connect("clicked", self._on_create_clicked)
        header.pack_end(self._create_button)

        main_box.append(header)

        # Content area
        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            margin_start=24,
            margin_end=24,
            margin_top=16,
            margin_bottom=24,
        )

        # Instructions label
        instructions = Gtk.Label(
            label="Enter a name for the new folder:",
            xalign=0,
            css_classes=["dim-label"],
        )
        content.append(instructions)

        # Folder name entry
        self._name_entry = Gtk.Entry(
            placeholder_text="Folder name",
            activates_default=True,
        )
        self._name_entry.connect("changed", self._on_name_changed)
        self._name_entry.connect("activate", self._on_entry_activate)
        content.append(self._name_entry)

        # Error label (hidden by default)
        self._error_label = Gtk.Label(
            xalign=0,
            css_classes=["error"],
            visible=False,
        )
        content.append(self._error_label)

        main_box.append(content)

        # Focus the entry when dialog opens
        self._name_entry.grab_focus()

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self.connect("close-request", self._on_close_request)

    def _on_name_changed(self, entry: Gtk.Entry) -> None:
        """
        Handle folder name entry changes.

        Performs real-time validation and updates UI accordingly.
        """
        name = entry.get_text().strip()
        self._validate_name(name)

    def _validate_name(self, name: str) -> bool:
        """
        Validate the folder name.

        Args:
            name: The folder name to validate.

        Returns:
            True if the name is valid, False otherwise.
        """
        self._validation_error = None

        # Check for empty name
        if not name:
            self._validation_error = None  # No error shown for empty, just disable button
            self._update_validation_ui(is_valid=False)
            return False

        # Check for duplicate names
        storage = get_local_storage()
        existing = storage.get_folder_by_name(name)
        if existing:
            self._validation_error = f"A folder named '{name}' already exists"
            self._update_validation_ui(is_valid=False)
            return False

        # Name is valid
        self._update_validation_ui(is_valid=True)
        return True

    def _update_validation_ui(self, is_valid: bool) -> None:
        """
        Update UI to reflect validation state.

        Args:
            is_valid: Whether the current input is valid.
        """
        self._create_button.set_sensitive(is_valid)

        if self._validation_error:
            self._error_label.set_label(self._validation_error)
            self._error_label.set_visible(True)
            self._name_entry.add_css_class("error")
        else:
            self._error_label.set_visible(False)
            self._name_entry.remove_css_class("error")

    def _on_entry_activate(self, entry: Gtk.Entry) -> None:
        """Handle Enter key in the entry field."""
        if self._create_button.get_sensitive():
            self._on_create_clicked(None)

    def _on_cancel_clicked(self, button: Optional[Gtk.Button]) -> None:
        """Handle cancel button click."""
        self.close()

    def _on_create_clicked(self, button: Optional[Gtk.Button]) -> None:
        """Handle create button click."""
        name = self._name_entry.get_text().strip()

        if not self._validate_name(name):
            return

        try:
            # Create the folder using local storage
            storage = get_local_storage()
            folder = storage.create_folder(name)

            logger.info(f"Created folder via dialog: {name}")

            # Emit signal
            self.emit("folder-created", folder["id"], folder["name"])

            # Call callback if provided
            if self._on_folder_created:
                self._on_folder_created(folder)

            # Close the dialog
            self.close()

        except ValueError as e:
            # Handle validation errors from storage
            self._validation_error = str(e)
            self._update_validation_ui(is_valid=False)
            logger.warning(f"Folder creation failed: {e}")

        except Exception as e:
            # Handle unexpected errors
            self._validation_error = "An error occurred while creating the folder"
            self._update_validation_ui(is_valid=False)
            logger.error(f"Unexpected error creating folder: {e}")

    def _on_close_request(self, window: Gtk.Window) -> bool:
        """Handle window close request."""
        return False  # Allow close


def create_folder_creation_dialog(
    parent: Optional[Gtk.Window] = None,
    on_folder_created: Optional[Callable[[dict], None]] = None,
) -> FolderCreationDialog:
    """
    Create and return a folder creation dialog.

    This is a convenience factory function for creating the dialog.

    Args:
        parent: Optional parent window for the dialog.
        on_folder_created: Optional callback invoked with the created
                          folder dict when creation succeeds.

    Returns:
        New FolderCreationDialog instance.
    """
    return FolderCreationDialog(
        parent=parent,
        on_folder_created=on_folder_created,
    )


def show_folder_creation_dialog(
    parent: Optional[Gtk.Window] = None,
    on_folder_created: Optional[Callable[[dict], None]] = None,
) -> FolderCreationDialog:
    """
    Create, show, and return a folder creation dialog.

    This is a convenience function that creates and presents the dialog.

    Args:
        parent: Optional parent window for the dialog.
        on_folder_created: Optional callback invoked with the created
                          folder dict when creation succeeds.

    Returns:
        The presented FolderCreationDialog instance.
    """
    dialog = create_folder_creation_dialog(
        parent=parent,
        on_folder_created=on_folder_created,
    )
    dialog.present()
    return dialog
