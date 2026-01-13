"""
Folder tree widget for unitMail sidebar.

This module provides a tree widget for displaying and managing email folders
with support for drag-drop message operations, unread count badges, and
nested folder hierarchies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

logger = logging.getLogger(__name__)


class FolderType(Enum):
    """Types of email folders."""

    INBOX = "inbox"
    SENT = "sent"
    DRAFTS = "drafts"
    TRASH = "trash"
    SPAM = "spam"
    ARCHIVE = "archive"
    FAVORITES = "favorites"
    ALL_MAIL = "all_mail"
    CUSTOM = "custom"


# System folders that cannot be deleted or renamed
SYSTEM_FOLDERS = {
    FolderType.INBOX,
    FolderType.SENT,
    FolderType.DRAFTS,
    FolderType.TRASH,
    FolderType.SPAM,
}

# Icon names for each folder type
FOLDER_ICONS: dict[FolderType, str] = {
    FolderType.INBOX: "mail-inbox-symbolic",
    FolderType.SENT: "mail-send-symbolic",
    FolderType.DRAFTS: "mail-drafts-symbolic",
    FolderType.TRASH: "user-trash-symbolic",
    FolderType.SPAM: "mail-mark-junk-symbolic",
    FolderType.ARCHIVE: "folder-documents-symbolic",
    FolderType.FAVORITES: "starred-symbolic",
    FolderType.ALL_MAIL: "mail-read-symbolic",
    FolderType.CUSTOM: "folder-symbolic",
}


@dataclass
class FolderData:
    """Data class representing a folder."""

    folder_id: str
    name: str
    folder_type: FolderType
    unread_count: int = 0
    total_count: int = 0
    parent_id: Optional[str] = None
    children: list["FolderData"] = None
    expanded: bool = True
    order: int = 0

    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.children is None:
            self.children = []

    @property
    def icon_name(self) -> str:
        """Get the icon name for this folder type."""
        return FOLDER_ICONS.get(self.folder_type, FOLDER_ICONS[FolderType.CUSTOM])

    @property
    def is_system_folder(self) -> bool:
        """Check if this is a system folder that cannot be deleted."""
        return self.folder_type in SYSTEM_FOLDERS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FolderData":
        """Create a FolderData from a dictionary."""
        folder_type_str = data.get("folder_type", "custom")
        try:
            folder_type = FolderType(folder_type_str)
        except ValueError:
            folder_type = FolderType.CUSTOM

        children_data = data.get("children", [])
        children = [cls.from_dict(child) for child in children_data]

        return cls(
            folder_id=data.get("folder_id", ""),
            name=data.get("name", ""),
            folder_type=folder_type,
            unread_count=data.get("unread_count", 0),
            total_count=data.get("total_count", 0),
            parent_id=data.get("parent_id"),
            children=children,
            expanded=data.get("expanded", True),
            order=data.get("order", 0),
        )


class FolderTreeItem(GObject.Object):
    """GObject wrapper for folder data in tree model."""

    __gtype_name__ = "FolderTreeItem"

    def __init__(self, folder_data: FolderData, depth: int = 0) -> None:
        """Initialize a folder tree item.

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
    def unread_count(self) -> int:
        """Get unread message count."""
        return self._folder_data.unread_count

    @unread_count.setter
    def unread_count(self, value: int) -> None:
        """Set unread message count."""
        self._folder_data.unread_count = value

    @GObject.Property(type=int)
    def total_count(self) -> int:
        """Get total message count."""
        return self._folder_data.total_count

    @total_count.setter
    def total_count(self, value: int) -> None:
        """Set total message count."""
        self._folder_data.total_count = value

    @GObject.Property(type=int)
    def depth(self) -> int:
        """Get nesting depth."""
        return self._depth

    @GObject.Property(type=bool, default=False)
    def is_system_folder(self) -> bool:
        """Check if this is a system folder."""
        return self._folder_data.is_system_folder

    @GObject.Property(type=bool, default=True)
    def expanded(self) -> bool:
        """Get expanded state."""
        return self._folder_data.expanded

    @expanded.setter
    def expanded(self, value: bool) -> None:
        """Set expanded state."""
        self._folder_data.expanded = value

    @GObject.Property(type=str)
    def folder_type(self) -> str:
        """Get folder type string."""
        return self._folder_data.folder_type.value

    @property
    def data(self) -> FolderData:
        """Get the underlying folder data."""
        return self._folder_data

    @property
    def has_children(self) -> bool:
        """Check if folder has children."""
        return len(self._folder_data.children) > 0


class FolderTree(Gtk.Box):
    """
    Widget for displaying a hierarchical folder tree in the sidebar.

    Supports drag-drop for moving messages to folders, unread count badges,
    and nested folder hierarchies with expand/collapse.
    """

    __gtype_name__ = "FolderTree"

    __gsignals__ = {
        # Emitted when a folder is selected
        "folder-selected": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
        # Emitted when messages are dropped on a folder
        "messages-dropped": (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        # Emitted when a folder's expanded state changes
        "folder-expanded-changed": (GObject.SignalFlags.RUN_FIRST, None, (str, bool)),
        # Emitted when context menu is requested
        "context-menu-requested": (GObject.SignalFlags.RUN_FIRST, None, (str, float, float)),
    }

    def __init__(self) -> None:
        """Initialize the folder tree widget."""
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )

        self._folders: list[FolderData] = []
        self._folder_items: dict[str, FolderTreeItem] = {}
        self._selected_folder_id: Optional[str] = None
        self._folder_store: Gio.ListStore = Gio.ListStore.new(FolderTreeItem)

        self._setup_ui()
        self._setup_drag_drop()

        logger.debug("FolderTree widget initialized")

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.add_css_class("folder-tree")

        # Scrolled window for folder list
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )

        # Create list view with factory
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_item_setup)
        factory.connect("bind", self._on_item_bind)
        factory.connect("unbind", self._on_item_unbind)

        # Single selection model
        self._selection_model = Gtk.SingleSelection(model=self._folder_store)
        self._selection_model.connect("selection-changed", self._on_selection_changed)

        # Create list view
        self._list_view = Gtk.ListView(
            model=self._selection_model,
            factory=factory,
            css_classes=["navigation-sidebar"],
        )

        # Right-click handler for context menu
        click_controller = Gtk.GestureClick(button=3)
        click_controller.connect("pressed", self._on_right_click)
        self._list_view.add_controller(click_controller)

        scrolled.set_child(self._list_view)
        self.append(scrolled)

    def _setup_drag_drop(self) -> None:
        """Set up drag-drop handling for messages."""
        # Drop target for receiving messages
        drop_target = Gtk.DropTarget.new(
            type=GObject.TYPE_STRING,
            actions=Gdk.DragAction.MOVE | Gdk.DragAction.COPY,
        )
        drop_target.connect("accept", self._on_drop_accept)
        drop_target.connect("drop", self._on_drop)
        drop_target.connect("enter", self._on_drop_enter)
        drop_target.connect("leave", self._on_drop_leave)
        drop_target.connect("motion", self._on_drop_motion)

        self._list_view.add_controller(drop_target)

    def _on_item_setup(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Set up a folder list item widget."""
        # Main row container
        row_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
            margin_top=2,
            margin_bottom=2,
            margin_end=8,
        )
        row_box.add_css_class("folder-row")

        # Expander placeholder (for nested folders)
        expander_box = Gtk.Box(hexpand=False)
        expander_box.set_size_request(20, -1)
        row_box.append(expander_box)

        # Folder icon
        icon = Gtk.Image()
        icon.add_css_class("folder-icon")
        row_box.append(icon)

        # Folder name label
        name_label = Gtk.Label(
            xalign=0,
            hexpand=True,
        )
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.add_css_class("folder-name")
        row_box.append(name_label)

        # Unread count badge
        badge = Gtk.Label()
        badge.add_css_class("badge")
        badge.add_css_class("numeric")
        badge.add_css_class("unread-badge")
        row_box.append(badge)

        list_item.set_child(row_box)

    def _on_item_bind(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Bind data to a folder list item widget."""
        item: FolderTreeItem = list_item.get_item()
        row_box: Gtk.Box = list_item.get_child()

        # Get child widgets
        children = self._get_box_children(row_box)
        expander_box, icon, name_label, badge = children[:4]

        # Set indentation based on depth
        indent = item.depth * 16
        expander_box.set_margin_start(indent)

        # Handle expander for folders with children
        # Clear existing expander content
        child = expander_box.get_first_child()
        if child:
            expander_box.remove(child)

        if item.has_children:
            expander_icon = Gtk.Image.new_from_icon_name(
                "pan-down-symbolic" if item.expanded else "pan-end-symbolic"
            )
            expander_icon.add_css_class("expander-icon")

            expander_btn = Gtk.Button()
            expander_btn.set_child(expander_icon)
            expander_btn.add_css_class("flat")
            expander_btn.add_css_class("circular")
            expander_btn.add_css_class("expander-button")
            expander_btn.connect("clicked", self._on_expander_clicked, item)

            expander_box.append(expander_btn)

        # Set icon
        icon.set_from_icon_name(item.icon_name)

        # Set name
        name_label.set_label(item.name)

        # Set unread badge
        if item.unread_count > 0:
            badge.set_label(str(item.unread_count))
            badge.set_visible(True)
            name_label.add_css_class("has-unread")
        else:
            badge.set_visible(False)
            name_label.remove_css_class("has-unread")

        # Apply system folder styling
        if item.is_system_folder:
            row_box.add_css_class("system-folder")
        else:
            row_box.remove_css_class("system-folder")

        # Store item reference for drag-drop
        row_box.set_data("folder-item", item)

    def _on_item_unbind(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Unbind data from a folder list item widget."""
        pass

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
        selected = selection.get_selected_item()
        if selected:
            self._selected_folder_id = selected.folder_id
            self.emit("folder-selected", selected.folder_id, selected.folder_type)
            logger.info(f"Selected folder: {selected.name}")

    def _on_expander_clicked(self, button: Gtk.Button, item: FolderTreeItem) -> None:
        """Handle expander button click."""
        item.expanded = not item.expanded
        self.emit("folder-expanded-changed", item.folder_id, item.expanded)
        self._rebuild_flat_list()

    def _on_right_click(
        self,
        gesture: Gtk.GestureClick,
        n_press: int,
        x: float,
        y: float,
    ) -> None:
        """Handle right-click for context menu."""
        # Find which item was clicked
        # Get the row at the click position
        if self._selected_folder_id:
            self.emit("context-menu-requested", self._selected_folder_id, x, y)

    def _on_drop_accept(
        self,
        target: Gtk.DropTarget,
        drop: Gdk.Drop,
    ) -> bool:
        """Check if we can accept the drop."""
        formats = drop.get_formats()
        return formats.contain_mime_type("text/plain")

    def _on_drop_enter(
        self,
        target: Gtk.DropTarget,
        x: float,
        y: float,
    ) -> Gdk.DragAction:
        """Handle drag enter."""
        self._list_view.add_css_class("drop-target")
        return Gdk.DragAction.MOVE

    def _on_drop_leave(self, target: Gtk.DropTarget) -> None:
        """Handle drag leave."""
        self._list_view.remove_css_class("drop-target")

    def _on_drop_motion(
        self,
        target: Gtk.DropTarget,
        x: float,
        y: float,
    ) -> Gdk.DragAction:
        """Handle drag motion to highlight target folder."""
        # TODO: Implement row highlighting during drag
        return Gdk.DragAction.MOVE

    def _on_drop(
        self,
        target: Gtk.DropTarget,
        value: GObject.Value,
        x: float,
        y: float,
    ) -> bool:
        """Handle drop of messages."""
        self._list_view.remove_css_class("drop-target")

        # Get the target folder from the drop position
        # For now, use the selected folder
        if self._selected_folder_id:
            # Parse message IDs from dropped data
            message_ids = str(value).split(",")
            self.emit("messages-dropped", self._selected_folder_id, message_ids)
            logger.info(
                f"Dropped {len(message_ids)} messages to folder {self._selected_folder_id}"
            )
            return True

        return False

    def set_folders(self, folders: list[FolderData | dict[str, Any]]) -> None:
        """Set the folder hierarchy.

        Args:
            folders: List of FolderData objects or dicts.
        """
        self._folders = []
        self._folder_items = {}

        for folder_data in folders:
            if isinstance(folder_data, dict):
                folder = FolderData.from_dict(folder_data)
            else:
                folder = folder_data
            self._folders.append(folder)

        self._rebuild_flat_list()
        logger.debug(f"Set {len(self._folders)} root folders")

    def _rebuild_flat_list(self) -> None:
        """Rebuild the flat list from the folder hierarchy."""
        self._folder_store.remove_all()
        self._folder_items.clear()

        def add_folder_recursive(folder: FolderData, depth: int = 0) -> None:
            """Add a folder and its children recursively."""
            item = FolderTreeItem(folder, depth)
            self._folder_items[folder.folder_id] = item
            self._folder_store.append(item)

            if folder.expanded:
                for child in folder.children:
                    add_folder_recursive(child, depth + 1)

        for folder in self._folders:
            add_folder_recursive(folder)

    def add_folder(
        self,
        folder: FolderData | dict[str, Any],
        parent_id: Optional[str] = None,
    ) -> None:
        """Add a new folder.

        Args:
            folder: The folder to add.
            parent_id: ID of the parent folder, or None for root level.
        """
        if isinstance(folder, dict):
            folder = FolderData.from_dict(folder)

        if parent_id:
            # Find parent and add as child
            parent = self._find_folder_by_id(parent_id)
            if parent:
                folder.parent_id = parent_id
                parent.children.append(folder)
        else:
            self._folders.append(folder)

        self._rebuild_flat_list()
        logger.info(f"Added folder: {folder.name}")

    def remove_folder(self, folder_id: str) -> bool:
        """Remove a folder.

        Args:
            folder_id: ID of the folder to remove.

        Returns:
            True if folder was removed, False if it's a system folder.
        """
        folder = self._find_folder_by_id(folder_id)
        if not folder:
            return False

        if folder.is_system_folder:
            logger.warning(f"Cannot remove system folder: {folder.name}")
            return False

        # Remove from parent's children or root list
        if folder.parent_id:
            parent = self._find_folder_by_id(folder.parent_id)
            if parent:
                parent.children = [c for c in parent.children if c.folder_id != folder_id]
        else:
            self._folders = [f for f in self._folders if f.folder_id != folder_id]

        self._rebuild_flat_list()
        logger.info(f"Removed folder: {folder.name}")
        return True

    def rename_folder(self, folder_id: str, new_name: str) -> bool:
        """Rename a folder.

        Args:
            folder_id: ID of the folder to rename.
            new_name: New name for the folder.

        Returns:
            True if folder was renamed, False if it's a system folder.
        """
        folder = self._find_folder_by_id(folder_id)
        if not folder:
            return False

        if folder.is_system_folder:
            logger.warning(f"Cannot rename system folder: {folder.name}")
            return False

        old_name = folder.name
        folder.name = new_name

        # Update the item in the list
        item = self._folder_items.get(folder_id)
        if item:
            item.notify("name")

        logger.info(f"Renamed folder: {old_name} -> {new_name}")
        return True

    def _find_folder_by_id(self, folder_id: str) -> Optional[FolderData]:
        """Find a folder by its ID.

        Args:
            folder_id: The folder ID to find.

        Returns:
            The folder data, or None if not found.
        """

        def search_recursive(folders: list[FolderData]) -> Optional[FolderData]:
            for folder in folders:
                if folder.folder_id == folder_id:
                    return folder
                result = search_recursive(folder.children)
                if result:
                    return result
            return None

        return search_recursive(self._folders)

    def update_unread_count(self, folder_id: str, unread_count: int) -> None:
        """Update the unread count for a folder.

        Args:
            folder_id: The folder ID.
            unread_count: New unread count.
        """
        folder = self._find_folder_by_id(folder_id)
        if folder:
            folder.unread_count = unread_count

            item = self._folder_items.get(folder_id)
            if item:
                item.notify("unread-count")
                # Force rebind to update badge visibility
                self._rebuild_flat_list()

    def select_folder(self, folder_id: str) -> None:
        """Select a folder by ID.

        Args:
            folder_id: The folder ID to select.
        """
        for i in range(self._folder_store.get_n_items()):
            item = self._folder_store.get_item(i)
            if item.folder_id == folder_id:
                self._selection_model.set_selected(i)
                break

    def get_selected_folder_id(self) -> Optional[str]:
        """Get the currently selected folder ID.

        Returns:
            The selected folder ID, or None.
        """
        return self._selected_folder_id

    def expand_folder(self, folder_id: str) -> None:
        """Expand a folder to show its children.

        Args:
            folder_id: The folder ID to expand.
        """
        folder = self._find_folder_by_id(folder_id)
        if folder and not folder.expanded:
            folder.expanded = True
            self._rebuild_flat_list()

    def collapse_folder(self, folder_id: str) -> None:
        """Collapse a folder to hide its children.

        Args:
            folder_id: The folder ID to collapse.
        """
        folder = self._find_folder_by_id(folder_id)
        if folder and folder.expanded:
            folder.expanded = False
            self._rebuild_flat_list()

    def get_folder_data(self, folder_id: str) -> Optional[FolderData]:
        """Get the data for a folder.

        Args:
            folder_id: The folder ID.

        Returns:
            The folder data, or None if not found.
        """
        return self._find_folder_by_id(folder_id)

    @staticmethod
    def get_css() -> str:
        """Get CSS styles for the folder tree widget."""
        return """
        .folder-tree {
            background-color: @sidebar_bg_color;
        }

        .folder-row {
            padding: 6px 8px;
            border-radius: 6px;
            margin: 1px 4px;
        }

        .folder-row:hover {
            background-color: alpha(@accent_bg_color, 0.1);
        }

        .folder-row:selected {
            background-color: @accent_bg_color;
            color: @accent_fg_color;
        }

        .folder-icon {
            min-width: 16px;
            min-height: 16px;
        }

        .folder-name {
            font-weight: 400;
        }

        .folder-name.has-unread {
            font-weight: 600;
        }

        .unread-badge {
            background-color: @accent_bg_color;
            color: @accent_fg_color;
            border-radius: 10px;
            padding: 2px 8px;
            font-size: smaller;
            font-weight: bold;
            min-width: 16px;
        }

        .system-folder .folder-icon {
            color: @accent_color;
        }

        .expander-button {
            padding: 0;
            min-width: 16px;
            min-height: 16px;
        }

        .expander-icon {
            min-width: 12px;
            min-height: 12px;
        }

        .folder-tree.drop-target {
            background-color: alpha(@accent_bg_color, 0.1);
        }

        .folder-row.drop-hover {
            background-color: alpha(@accent_bg_color, 0.3);
            outline: 2px dashed @accent_color;
        }
        """
