"""
Folder management dialog for unitMail.

This module provides a dialog for managing email folders including
creating, renaming, deleting, and reordering folders with support
for nested folder hierarchies.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional
from uuid import uuid4

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")

from gi.repository import Adw, Gdk, Gio, GObject, Gtk, Pango

from .widgets.folder_tree import FolderData, FolderType

logger = logging.getLogger(__name__)


class FolderListItem(GObject.Object):
    """GObject wrapper for folder data in the management list."""

    __gtype_name__ = "FolderListItem"

    def __init__(
        self,
        folder_data: FolderData,
        depth: int = 0,
    ) -> None:
        """Initialize a folder list item.

        Args:
            folder_data: The folder data.
            depth: Nesting depth for indentation.
        """
        super().__init__()
        self._folder_data = folder_data
        self._depth = depth

    @GObject.Property(type=str)
    def folder_id(self) -> str:
        """Get folder ID."""
        return self._folder_data.folder_id

    @GObject.Property(type=str)
    def name(self) -> str:
        """Get folder name."""
        return self._folder_data.name

    @name.setter
    def name(self, value: str) -> None:
        """Set folder name."""
        self._folder_data.name = value

    @GObject.Property(type=str)
    def icon_name(self) -> str:
        """Get folder icon name."""
        return self._folder_data.icon_name

    @GObject.Property(type=int)
    def depth(self) -> int:
        """Get nesting depth."""
        return self._depth

    @GObject.Property(type=bool, default=False)
    def is_system_folder(self) -> bool:
        """Check if this is a system folder."""
        return self._folder_data.is_system_folder

    @GObject.Property(type=bool, default=True)
    def is_deletable(self) -> bool:
        """Check if folder can be deleted."""
        return not self._folder_data.is_system_folder

    @GObject.Property(type=bool, default=True)
    def is_renamable(self) -> bool:
        """Check if folder can be renamed."""
        return not self._folder_data.is_system_folder

    @property
    def data(self) -> FolderData:
        """Get the underlying folder data."""
        return self._folder_data


class FolderManagerDialog(Adw.Window):
    """
    Dialog for managing email folders.

    Provides functionality for creating, renaming, deleting, and
    reordering folders with drag-drop support and nested folder
    hierarchies.
    """

    __gtype_name__ = "FolderManagerDialog"

    __gsignals__ = {
        # Emitted when a folder is created
        "folder-created": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (str, str, str),
        ),
        # Emitted when a folder is renamed
        "folder-renamed": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
        # Emitted when a folder is deleted
        "folder-deleted": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        # Emitted when folders are reordered
        "folders-reordered": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        # Emitted when a folder is moved to a new parent
        "folder-moved": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
    }

    DEFAULT_WIDTH = 500
    DEFAULT_HEIGHT = 600

    def __init__(
        self,
        parent: Optional[Gtk.Window] = None,
        folders: Optional[list[FolderData]] = None,
    ) -> None:
        """Initialize the folder manager dialog.

        Args:
            parent: Parent window for the dialog.
            folders: Initial list of folders to display.
        """
        super().__init__(
            title="Manage Folders",
            default_width=self.DEFAULT_WIDTH,
            default_height=self.DEFAULT_HEIGHT,
            modal=True,
        )

        if parent:
            self.set_transient_for(parent)

        self._folders: list[FolderData] = folders or []
        self._folder_items: dict[str, FolderListItem] = {}
        self._folder_store: Gio.ListStore = Gio.ListStore.new(FolderListItem)
        self._selected_item: Optional[FolderListItem] = None
        self._drag_source_item: Optional[FolderListItem] = None

        self._on_folder_created: Optional[Callable[[str, str, str], None]] = (
            None
        )
        self._on_folder_renamed: Optional[Callable[[str, str], None]] = None
        self._on_folder_deleted: Optional[Callable[[str], None]] = None

        self._setup_ui()
        self._populate_folders()

        logger.debug("FolderManagerDialog initialized")

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        # Main container
        main_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )
        self.set_content(main_box)

        # Header bar
        header_bar = Adw.HeaderBar()

        # Close button
        close_button = Gtk.Button(label="Close")
        close_button.connect("clicked", lambda b: self.close())
        header_bar.pack_end(close_button)

        main_box.append(header_bar)

        # Content area
        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_start=16,
            margin_end=16,
            margin_top=16,
            margin_bottom=16,
            vexpand=True,
        )

        # Toolbar
        toolbar = self._create_toolbar()
        content_box.append(toolbar)

        # Folder list
        list_frame = self._create_folder_list()
        content_box.append(list_frame)

        main_box.append(content_box)

    def _create_toolbar(self) -> Gtk.Widget:
        """Create the toolbar with folder actions.

        Returns:
            Toolbar widget.
        """
        toolbar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )

        # New folder button
        new_button = Gtk.Button(
            icon_name="folder-new-symbolic",
            tooltip_text="Create new folder",
        )
        new_button.add_css_class("suggested-action")
        new_button.connect("clicked", self._on_new_folder_clicked)
        toolbar.append(new_button)

        # New subfolder button
        new_subfolder_button = Gtk.Button(
            icon_name="folder-symbolic",
            tooltip_text="Create subfolder",
        )
        new_subfolder_button.connect("clicked", self._on_new_subfolder_clicked)
        toolbar.append(new_subfolder_button)
        self._new_subfolder_button = new_subfolder_button

        # Spacer
        spacer = Gtk.Box(hexpand=True)
        toolbar.append(spacer)

        # Rename button
        rename_button = Gtk.Button(
            icon_name="document-edit-symbolic",
            tooltip_text="Rename folder",
        )
        rename_button.connect("clicked", self._on_rename_clicked)
        rename_button.set_sensitive(False)
        toolbar.append(rename_button)
        self._rename_button = rename_button

        # Delete button
        delete_button = Gtk.Button(
            icon_name="user-trash-symbolic",
            tooltip_text="Delete folder",
        )
        delete_button.add_css_class("destructive-action")
        delete_button.connect("clicked", self._on_delete_clicked)
        delete_button.set_sensitive(False)
        toolbar.append(delete_button)
        self._delete_button = delete_button

        return toolbar

    def _create_folder_list(self) -> Gtk.Widget:
        """Create the folder list widget.

        Returns:
            List widget container.
        """
        # Frame for the list
        frame = Gtk.Frame()
        frame.add_css_class("view")

        # Scrolled window
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )

        # Create factory
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_item_setup)
        factory.connect("bind", self._on_item_bind)

        # Selection model
        self._selection_model = Gtk.SingleSelection(model=self._folder_store)
        self._selection_model.connect(
            "selection-changed", self._on_selection_changed
        )

        # List view
        self._list_view = Gtk.ListView(
            model=self._selection_model,
            factory=factory,
        )
        self._list_view.add_css_class("folder-manager-list")

        # Set up drag-drop for reordering
        self._setup_drag_drop()

        scrolled.set_child(self._list_view)
        frame.set_child(scrolled)

        return frame

    def _setup_drag_drop(self) -> None:
        """Set up drag-drop for folder reordering."""
        # Drag source
        drag_source = Gtk.DragSource()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        drag_source.connect("prepare", self._on_drag_prepare)
        drag_source.connect("drag-begin", self._on_drag_begin)
        drag_source.connect("drag-end", self._on_drag_end)
        self._list_view.add_controller(drag_source)

        # Drop target
        drop_target = Gtk.DropTarget.new(
            type=GObject.TYPE_STRING,
            actions=Gdk.DragAction.MOVE,
        )
        drop_target.connect("drop", self._on_drop)
        drop_target.connect("enter", self._on_drop_enter)
        drop_target.connect("leave", self._on_drop_leave)
        self._list_view.add_controller(drop_target)

    def _on_item_setup(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Set up a folder list item widget."""
        row_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_start=8,
            margin_end=8,
            margin_top=8,
            margin_bottom=8,
        )

        # Drag handle
        drag_handle = Gtk.Image.new_from_icon_name("list-drag-handle-symbolic")
        drag_handle.add_css_class("dim-label")
        drag_handle.add_css_class("drag-handle")
        row_box.append(drag_handle)

        # Indent spacer
        indent_box = Gtk.Box()
        row_box.append(indent_box)

        # Folder icon
        icon = Gtk.Image()
        row_box.append(icon)

        # Folder name
        name_label = Gtk.Label(
            xalign=0,
            hexpand=True,
        )
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        row_box.append(name_label)

        # System folder indicator
        system_label = Gtk.Label(
            label="System",
            css_classes=["dim-label", "caption"],
        )
        row_box.append(system_label)

        list_item.set_child(row_box)

    def _on_item_bind(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Bind data to a folder list item widget."""
        item: FolderListItem = list_item.get_item()
        row_box: Gtk.Box = list_item.get_child()

        # Get child widgets
        children = self._get_box_children(row_box)
        drag_handle, indent_box, icon, name_label, system_label = children[:5]

        # Set indentation
        indent_box.set_size_request(item.depth * 20, -1)

        # Set icon
        icon.set_from_icon_name(item.icon_name)

        # Set name
        name_label.set_label(item.name)

        # Show/hide system indicator
        system_label.set_visible(item.is_system_folder)

        # Disable drag handle for system folders
        if item.is_system_folder:
            drag_handle.add_css_class("insensitive")
        else:
            drag_handle.remove_css_class("insensitive")

        # Store item reference
        row_box.set_data("folder-item", item)

    def _get_box_children(self, box: Gtk.Box) -> list[Gtk.Widget]:
        """Get all children of a box widget."""
        children = []
        child = box.get_first_child()
        while child:
            children.append(child)
            child = child.get_next_sibling()
        return children

    def _on_selection_changed(
        self,
        selection: Gtk.SingleSelection,
        position: int,
        n_items: int,
    ) -> None:
        """Handle folder selection change."""
        self._selected_item = selection.get_selected_item()

        if self._selected_item:
            is_system = self._selected_item.is_system_folder
            self._rename_button.set_sensitive(not is_system)
            self._delete_button.set_sensitive(not is_system)
            self._new_subfolder_button.set_sensitive(True)
        else:
            self._rename_button.set_sensitive(False)
            self._delete_button.set_sensitive(False)
            self._new_subfolder_button.set_sensitive(False)

    def _on_drag_prepare(
        self,
        source: Gtk.DragSource,
        x: float,
        y: float,
    ) -> Optional[Gdk.ContentProvider]:
        """Prepare for drag operation."""
        if self._selected_item and not self._selected_item.is_system_folder:
            self._drag_source_item = self._selected_item
            return Gdk.ContentProvider.new_for_value(
                self._selected_item.folder_id
            )
        return None

    def _on_drag_begin(
        self,
        source: Gtk.DragSource,
        drag: Gdk.Drag,
    ) -> None:
        """Handle drag begin."""
        if self._drag_source_item:
            # Create drag icon
            icon = Gtk.Label(label=self._drag_source_item.name)
            icon.add_css_class("drag-icon")
            source.set_icon(
                Gtk.WidgetPaintable.new(icon),
                0,
                0,
            )

    def _on_drag_end(
        self,
        source: Gtk.DragSource,
        drag: Gdk.Drag,
        delete_data: bool,
    ) -> None:
        """Handle drag end."""
        self._drag_source_item = None

    def _on_drop_enter(
        self,
        target: Gtk.DropTarget,
        x: float,
        y: float,
    ) -> Gdk.DragAction:
        """Handle drag enter."""
        return Gdk.DragAction.MOVE

    def _on_drop_leave(self, target: Gtk.DropTarget) -> None:
        """Handle drag leave."""

    def _on_drop(
        self,
        target: Gtk.DropTarget,
        value: GObject.Value,
        x: float,
        y: float,
    ) -> bool:
        """Handle drop for reordering."""
        folder_id = str(value)

        # Get drop target position
        # For simplicity, we'll move to after the selected item
        if self._selected_item and self._selected_item.folder_id != folder_id:
            target_id = self._selected_item.folder_id
            self._move_folder(folder_id, target_id)
            return True

        return False

    def _move_folder(self, folder_id: str, target_id: str) -> None:
        """Move a folder to a new position.

        Args:
            folder_id: ID of the folder to move.
            target_id: ID of the target folder (move after this).
        """
        source_folder = self._find_folder_by_id(folder_id)
        target_folder = self._find_folder_by_id(target_id)

        if not source_folder or not target_folder:
            return

        if source_folder.is_system_folder:
            logger.warning("Cannot move system folder")
            return

        # Remove from current position
        self._remove_folder_from_list(folder_id)

        # Add after target
        target_parent_id = target_folder.parent_id
        if target_parent_id:
            parent = self._find_folder_by_id(target_parent_id)
            if parent:
                source_folder.parent_id = target_parent_id
                target_idx = next(
                    (
                        i
                        for i, f in enumerate(parent.children)
                        if f.folder_id == target_id
                    ),
                    len(parent.children) - 1,
                )
                parent.children.insert(target_idx + 1, source_folder)
        else:
            source_folder.parent_id = None
            target_idx = next(
                (
                    i
                    for i, f in enumerate(self._folders)
                    if f.folder_id == target_id
                ),
                len(self._folders) - 1,
            )
            self._folders.insert(target_idx + 1, source_folder)

        self._populate_folders()
        self.emit("folders-reordered", self._folders)
        logger.info(f"Moved folder {source_folder.name}")

    def _on_new_folder_clicked(self, button: Gtk.Button) -> None:
        """Handle new folder button click."""
        self._show_folder_name_dialog(
            title="New Folder",
            message="Enter name for the new folder:",
            callback=self._create_folder,
        )

    def _on_new_subfolder_clicked(self, button: Gtk.Button) -> None:
        """Handle new subfolder button click."""
        if not self._selected_item:
            return

        self._show_folder_name_dialog(
            title="New Subfolder",
            message=f"Enter name for subfolder of '{
                self._selected_item.name}':",
            callback=lambda name: self._create_folder(
                name, self._selected_item.folder_id
            ),
        )

    def _on_rename_clicked(self, button: Gtk.Button) -> None:
        """Handle rename button click."""
        if not self._selected_item or self._selected_item.is_system_folder:
            return

        self._show_folder_name_dialog(
            title="Rename Folder",
            message="Enter new name for the folder:",
            initial_text=self._selected_item.name,
            callback=self._rename_folder,
        )

    def _on_delete_clicked(self, button: Gtk.Button) -> None:
        """Handle delete button click."""
        if not self._selected_item or self._selected_item.is_system_folder:
            return

        self._show_delete_confirmation()

    def _show_folder_name_dialog(
        self,
        title: str,
        message: str,
        callback: Callable[[str], None],
        initial_text: str = "",
    ) -> None:
        """Show a dialog for entering a folder name.

        Args:
            title: Dialog title.
            message: Message to display.
            callback: Function to call with the entered name.
            initial_text: Initial text for the entry.
        """
        dialog = Adw.MessageDialog(
            transient_for=self,
            modal=True,
            heading=title,
            body=message,
        )

        # Add entry
        entry = Gtk.Entry(
            text=initial_text,
            margin_start=16,
            margin_end=16,
            margin_top=8,
            margin_bottom=8,
        )
        entry.set_activates_default(True)
        dialog.set_extra_child(entry)

        # Add buttons
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("create", "OK")
        dialog.set_response_appearance(
            "create", Adw.ResponseAppearance.SUGGESTED
        )
        dialog.set_default_response("create")

        def on_response(dialog: Adw.MessageDialog, response: str) -> None:
            if response == "create":
                name = entry.get_text().strip()
                if name:
                    callback(name)
            dialog.close()

        dialog.connect("response", on_response)
        dialog.present()

    def _show_delete_confirmation(self) -> None:
        """Show delete confirmation dialog."""
        if not self._selected_item:
            return

        folder_name = self._selected_item.name
        has_children = len(self._selected_item.data.children) > 0

        message = f"Are you sure you want to delete '{folder_name}'?"
        if has_children:
            message += "\n\nThis folder contains subfolders that will also be deleted."

        dialog = Adw.MessageDialog(
            transient_for=self,
            modal=True,
            heading="Delete Folder",
            body=message,
        )

        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance(
            "delete", Adw.ResponseAppearance.DESTRUCTIVE
        )

        def on_response(dialog: Adw.MessageDialog, response: str) -> None:
            if response == "delete":
                self._delete_folder()
            dialog.close()

        dialog.connect("response", on_response)
        dialog.present()

    def _create_folder(
        self, name: str, parent_id: Optional[str] = None
    ) -> None:
        """Create a new folder.

        Args:
            name: Name for the new folder.
            parent_id: Parent folder ID, or None for root level.
        """
        folder_id = str(uuid4())

        new_folder = FolderData(
            folder_id=folder_id,
            name=name,
            folder_type=FolderType.CUSTOM,
            parent_id=parent_id,
        )

        if parent_id:
            parent = self._find_folder_by_id(parent_id)
            if parent:
                parent.children.append(new_folder)
        else:
            self._folders.append(new_folder)

        self._populate_folders()
        self.emit("folder-created", folder_id, name, parent_id or "")

        if self._on_folder_created:
            self._on_folder_created(folder_id, name, parent_id or "")

        logger.info(f"Created folder: {name}")

    def _rename_folder(self, new_name: str) -> None:
        """Rename the selected folder.

        Args:
            new_name: New name for the folder.
        """
        if not self._selected_item:
            return

        folder_id = self._selected_item.folder_id
        folder = self._find_folder_by_id(folder_id)

        if folder and not folder.is_system_folder:
            old_name = folder.name
            folder.name = new_name
            self._populate_folders()
            self.emit("folder-renamed", folder_id, new_name)

            if self._on_folder_renamed:
                self._on_folder_renamed(folder_id, new_name)

            logger.info(f"Renamed folder: {old_name} -> {new_name}")

    def _delete_folder(self) -> None:
        """Delete the selected folder."""
        if not self._selected_item:
            return

        folder_id = self._selected_item.folder_id
        folder = self._find_folder_by_id(folder_id)

        if folder and not folder.is_system_folder:
            folder_name = folder.name
            self._remove_folder_from_list(folder_id)
            self._populate_folders()
            self.emit("folder-deleted", folder_id)

            if self._on_folder_deleted:
                self._on_folder_deleted(folder_id)

            logger.info(f"Deleted folder: {folder_name}")

    def _remove_folder_from_list(self, folder_id: str) -> None:
        """Remove a folder from the folder list.

        Args:
            folder_id: ID of the folder to remove.
        """
        folder = self._find_folder_by_id(folder_id)
        if not folder:
            return

        if folder.parent_id:
            parent = self._find_folder_by_id(folder.parent_id)
            if parent:
                parent.children = [
                    c for c in parent.children if c.folder_id != folder_id
                ]
        else:
            self._folders = [
                f for f in self._folders if f.folder_id != folder_id
            ]

    def _find_folder_by_id(self, folder_id: str) -> Optional[FolderData]:
        """Find a folder by its ID.

        Args:
            folder_id: The folder ID to find.

        Returns:
            The folder data, or None if not found.
        """

        def search_recursive(
            folders: list[FolderData],
        ) -> Optional[FolderData]:
            for folder in folders:
                if folder.folder_id == folder_id:
                    return folder
                result = search_recursive(folder.children)
                if result:
                    return result
            return None

        return search_recursive(self._folders)

    def _populate_folders(self) -> None:
        """Populate the folder list from the folder hierarchy."""
        self._folder_store.remove_all()
        self._folder_items.clear()

        def add_folder_recursive(folder: FolderData, depth: int = 0) -> None:
            item = FolderListItem(folder, depth)
            self._folder_items[folder.folder_id] = item
            self._folder_store.append(item)

            for child in folder.children:
                add_folder_recursive(child, depth + 1)

        for folder in self._folders:
            add_folder_recursive(folder)

    def set_folders(self, folders: list[FolderData | dict[str, Any]]) -> None:
        """Set the folder hierarchy.

        Args:
            folders: List of FolderData objects or dicts.
        """
        self._folders = []

        for folder_data in folders:
            if isinstance(folder_data, dict):
                folder = FolderData.from_dict(folder_data)
            else:
                folder = folder_data
            self._folders.append(folder)

        self._populate_folders()

    def get_folders(self) -> list[FolderData]:
        """Get the current folder hierarchy.

        Returns:
            List of root folders with their children.
        """
        return self._folders.copy()

    def set_on_folder_created(
        self,
        callback: Callable[[str, str, str], None],
    ) -> None:
        """Set callback for folder creation.

        Args:
            callback: Function receiving (folder_id, name, parent_id).
        """
        self._on_folder_created = callback

    def set_on_folder_renamed(
        self,
        callback: Callable[[str, str], None],
    ) -> None:
        """Set callback for folder rename.

        Args:
            callback: Function receiving (folder_id, new_name).
        """
        self._on_folder_renamed = callback

    def set_on_folder_deleted(
        self,
        callback: Callable[[str], None],
    ) -> None:
        """Set callback for folder deletion.

        Args:
            callback: Function receiving (folder_id).
        """
        self._on_folder_deleted = callback

    @staticmethod
    def get_css() -> str:
        """Get CSS styles for the folder manager dialog."""
        return """
        .folder-manager-list {
            background-color: @card_bg_color;
        }

        .folder-manager-list row {
            padding: 4px;
        }

        .folder-manager-list row:hover {
            background-color: alpha(@accent_bg_color, 0.1);
        }

        .folder-manager-list row:selected {
            background-color: @accent_bg_color;
            color: @accent_fg_color;
        }

        .drag-handle {
            cursor: grab;
        }

        .drag-handle.insensitive {
            opacity: 0.3;
            cursor: not-allowed;
        }

        .drag-icon {
            background-color: @accent_bg_color;
            color: @accent_fg_color;
            padding: 8px 16px;
            border-radius: 6px;
        }
        """
