"""
unitMail Main Window.

This module provides the main application window with a three-pane layout
for folder navigation, message list, and message preview.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import gi

if TYPE_CHECKING:
    from .application import UnitMailApplication

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Pango

from common.storage import get_storage
from common.sample_data import generate_sample_messages
from .composer import ComposerWindow, ComposerMode, EmailMessage
from .column_resize_mixin import ColumnResizeMixin

logger = logging.getLogger(__name__)


class EmptyStateWidget(Gtk.Box):
    """Empty state widget with icon, title, description, and optional CTA button."""

    __gtype_name__ = "EmptyStateWidget"

    def __init__(
        self,
        icon_name: str,
        title: str,
        description: str,
        cta_label: Optional[str] = None,
        cta_action: Optional[str] = None,
    ) -> None:
        """Initialize the empty state widget.

        Args:
            icon_name: Icon name to display.
            title: Main title text.
            description: Descriptive text below the title.
            cta_label: Optional label for the CTA button.
            cta_action: Optional action name for the CTA button.
        """
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
            vexpand=True,
            hexpand=True,
            css_classes=["empty-state"],
        )

        # Icon
        icon = Gtk.Image(
            icon_name=icon_name,
            pixel_size=64,
            css_classes=["empty-state-icon"],
        )
        self.append(icon)

        # Title
        title_label = Gtk.Label(
            label=title,
            css_classes=["empty-state-title", "title-2"],
        )
        self.append(title_label)

        # Description
        desc_label = Gtk.Label(
            label=description,
            css_classes=["empty-state-description", "dim-label"],
            wrap=True,
            max_width_chars=40,
            justify=Gtk.Justification.CENTER,
        )
        self.append(desc_label)

        # CTA Button (optional)
        if cta_label and cta_action:
            cta_button = Gtk.Button(
                label=cta_label,
                css_classes=["suggested-action", "pill"],
            )
            cta_button.set_action_name(cta_action)
            self.append(cta_button)


class FolderSelectionDialog(Adw.MessageDialog):
    """
    Reusable dialog for selecting a destination folder.

    This dialog displays a list of available folders and allows the user
    to select one as a destination for moving messages. It can be configured
    to exclude certain folders (e.g., exclude Trash when restoring from Trash).

    Usage:
        dialog = FolderSelectionDialog(
            parent=self,
            title="Move to Folder",
            exclude_folders=["Trash", "Spam"],
        )
        dialog.connect("response", self._on_folder_dialog_response)
        dialog.present()
    """

    __gtype_name__ = "FolderSelectionDialog"

    def __init__(
        self,
        parent: Gtk.Window,
        title: str = "Select Folder",
        exclude_folders: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize the folder selection dialog.

        Args:
            parent: Parent window.
            title: Dialog title.
            exclude_folders: List of folder names to exclude from the list.
        """
        super().__init__(
            transient_for=parent,
            heading=title,
            body="Choose a destination folder:",
        )

        self._selected_folder: Optional[str] = None
        self._exclude_folders = exclude_folders or []

        self.add_response("cancel", "Cancel")
        self.add_response("move", "Move")
        self.set_response_appearance("move", Adw.ResponseAppearance.SUGGESTED)
        self.set_default_response("move")
        self.set_close_response("cancel")

        # Disable the move button initially until a folder is selected
        self.set_response_enabled("move", False)

        # Build the folder list
        self._build_folder_list()

    def _build_folder_list(self) -> None:
        """Build the scrollable folder list."""
        # Scrolled container for folder list
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            min_content_height=200,
            max_content_height=300,
        )

        # List box for folders
        self._folder_listbox = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.SINGLE,
            css_classes=["boxed-list"],
        )
        self._folder_listbox.connect(
            "row-selected", self._on_folder_row_selected
        )

        # Populate with folders
        storage = get_storage()
        folders = storage.get_folders()

        for folder in folders:
            folder_name = folder["name"]
            # Skip excluded folders
            if folder_name in self._exclude_folders:
                continue

            row = Adw.ActionRow(
                title=folder_name,
                icon_name=folder.get("icon", "folder-symbolic"),
            )
            row.folder_name = folder_name  # Store folder name for retrieval
            self._folder_listbox.append(row)

        scrolled.set_child(self._folder_listbox)
        self.set_extra_child(scrolled)

    def _on_folder_row_selected(
        self,
        listbox: Gtk.ListBox,
        row: Optional[Gtk.ListBoxRow],
    ) -> None:
        """Handle folder row selection."""
        if row is not None:
            action_row = row.get_child() if hasattr(row, "get_child") else row
            if hasattr(action_row, "folder_name"):
                self._selected_folder = action_row.folder_name
            else:
                # For Adw.ActionRow, the row itself has the folder_name
                self._selected_folder = getattr(row, "folder_name", None)
            self.set_response_enabled(
                "move", self._selected_folder is not None
            )
        else:
            self._selected_folder = None
            self.set_response_enabled("move", False)

    def get_selected_folder(self) -> Optional[str]:
        """Get the selected folder name."""
        return self._selected_folder


# Empty state configurations for different contexts
EMPTY_STATES = {
    "inbox": {
        "icon": "mail-inbox-symbolic",
        "title": "Your inbox is empty",
        "description": "New messages will appear here. Check back soon!",
        "cta_label": "Compose New Email",
        "cta_action": "app.compose",
    },
    "search_no_results": {
        "icon": "edit-find-symbolic",
        "title": "No messages found",
        "description": "Try different search terms or check your spelling",
        "cta_label": "Clear Search",
        "cta_action": "win.clear-search",
    },
    "folder_empty": {
        "icon": "folder-symbolic",
        "title": "This folder is empty",
        "description": "Messages moved here will appear in this folder",
        "cta_label": None,
        "cta_action": None,
    },
    "drafts_empty": {
        "icon": "mail-drafts-symbolic",
        "title": "No drafts",
        "description": "Draft messages will be saved here automatically",
        "cta_label": "Compose New Email",
        "cta_action": "app.compose",
    },
    "sent_empty": {
        "icon": "mail-send-symbolic",
        "title": "No sent messages",
        "description": "Messages you send will appear here",
        "cta_label": "Compose New Email",
        "cta_action": "app.compose",
    },
    "trash_empty": {
        "icon": "user-trash-symbolic",
        "title": "Trash is empty",
        "description": "Deleted messages will appear here",
        "cta_label": None,
        "cta_action": None,
    },
    "spam_empty": {
        "icon": "mail-mark-junk-symbolic",
        "title": "No spam",
        "description": "Messages marked as spam will appear here",
        "cta_label": None,
        "cta_action": None,
    },
}


class FolderItem(GObject.Object):
    """
    GObject wrapper for folder data.

    Used in Gtk.TreeView/ListView to represent folder items.
    """

    __gtype_name__ = "FolderItem"

    def __init__(
        self,
        folder_id: str,
        name: str,
        icon_name: str,
        unread_count: int = 0,
        folder_type: str = "custom",
        parent_id: Optional[str] = None,
    ) -> None:
        """
        Initialize a folder item.

        Args:
            folder_id: Unique folder identifier.
            name: Display name of the folder.
            icon_name: Icon name for the folder.
            unread_count: Number of unread messages.
            folder_type: Type of folder (inbox, sent, etc.).
            parent_id: Parent folder ID for nested folders.
        """
        super().__init__()
        self._folder_id = folder_id
        self._name = name
        self._icon_name = icon_name
        self._unread_count = unread_count
        self._folder_type = folder_type
        self._parent_id = parent_id

    @GObject.Property(type=str)
    def folder_id(self) -> str:
        """Get folder ID."""
        return self._folder_id

    @GObject.Property(type=str)
    def name(self) -> str:
        """Get folder name."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Set folder name."""
        self._name = value

    @GObject.Property(type=str)
    def icon_name(self) -> str:
        """Get folder icon name."""
        return self._icon_name

    @GObject.Property(type=int)
    def unread_count(self) -> int:
        """Get unread message count."""
        return self._unread_count

    @unread_count.setter
    def unread_count(self, value: int) -> None:
        """Set unread message count."""
        self._unread_count = value

    @GObject.Property(type=str)
    def folder_type(self) -> str:
        """Get folder type."""
        return self._folder_type


class MessageItem(GObject.Object):
    """
    GObject wrapper for message data.

    Used in Gtk.ListView to represent message list items.
    """

    __gtype_name__ = "MessageItem"

    def __init__(
        self,
        message_id: str,
        from_address: str,
        subject: str,
        preview: str,
        date: datetime,
        is_read: bool = False,
        is_starred: bool = False,
        is_important: bool = False,
        has_attachments: bool = False,
        attachment_count: int = 0,
    ) -> None:
        """
        Initialize a message item.

        Args:
            message_id: Unique message identifier.
            from_address: Sender email address.
            subject: Message subject.
            preview: Short preview of message body.
            date: Message date/time.
            is_read: Whether the message has been read.
            is_starred: Whether the message is starred.
            is_important: Whether the message is marked important.
            has_attachments: Whether the message has attachments.
            attachment_count: Number of attachments.
        """
        super().__init__()
        self._message_id = message_id
        self._from_address = from_address
        self._subject = subject
        self._preview = preview
        self._date = date
        self._is_read = is_read
        self._is_starred = is_starred
        self._is_important = is_important
        self._has_attachments = has_attachments
        self._attachment_count = attachment_count

    @GObject.Property(type=str)
    def message_id(self) -> str:
        """Get message ID."""
        return self._message_id

    @GObject.Property(type=str)
    def from_address(self) -> str:
        """Get sender address."""
        return self._from_address

    @GObject.Property(type=str)
    def subject(self) -> str:
        """Get message subject."""
        return self._subject

    @GObject.Property(type=str)
    def preview(self) -> str:
        """Get message preview."""
        return self._preview

    @GObject.Property(type=str)
    def date_string(self) -> str:
        """Get formatted date string using centralized formatter."""
        try:
            from client.services.date_format_service import format_date

            return format_date(self._date, show_time_for_today=True)
        except ImportError:
            # Fallback if date format service is not available
            now = datetime.now()
            if self._date.date() == now.date():
                return self._date.strftime("%H:%M")
            else:
                return self._date.strftime("%Y-%m-%d")

    @GObject.Property(type=bool, default=False)
    def is_read(self) -> bool:
        """Get read status."""
        return self._is_read

    @is_read.setter
    def is_read(self, value: bool) -> None:
        """Set read status."""
        if self._is_read != value:
            self._is_read = value
            self.notify("is-read")

    @GObject.Property(type=bool, default=False)
    def is_starred(self) -> bool:
        """Get starred status."""
        return self._is_starred

    @is_starred.setter
    def is_starred(self, value: bool) -> None:
        """Set starred status."""
        if self._is_starred != value:
            self._is_starred = value
            self.notify("is-starred")

    @GObject.Property(type=bool, default=False)
    def is_important(self) -> bool:
        """Get important status."""
        return self._is_important

    @is_important.setter
    def is_important(self, value: bool) -> None:
        """Set important status."""
        if self._is_important != value:
            self._is_important = value
            self.notify("is-important")

    @GObject.Property(type=bool, default=False)
    def has_attachments(self) -> bool:
        """Get attachments status."""
        return self._has_attachments

    @GObject.Property(type=int, default=0)
    def attachment_count(self) -> int:
        """Get number of attachments."""
        return self._attachment_count


class MainWindow(ColumnResizeMixin, Adw.ApplicationWindow):
    """
    Main application window for unitMail.

    Provides a three-pane layout with folder tree, message list,
    and message preview. Includes header bar with actions and
    status bar with connection information.
    """

    __gtype_name__ = "UnitMailMainWindow"

    # Window state settings
    DEFAULT_WIDTH = 1200
    DEFAULT_HEIGHT = 800
    DEFAULT_LEFT_PANE_WIDTH = 140  # Minimal width for folder names
    DEFAULT_CENTER_PANE_WIDTH = 350

    def __init__(self, application: "UnitMailApplication") -> None:
        """
        Initialize the main window.

        Args:
            application: The parent application instance.
        """
        super().__init__(
            application=application,
            title="unitMail",
            default_width=self.DEFAULT_WIDTH,
            default_height=self.DEFAULT_HEIGHT,
        )

        self._application = application
        self._selected_folder_id: Optional[str] = None
        self._selected_message_id: Optional[str] = None

        # Data stores
        self._folder_store: Gio.ListStore = Gio.ListStore.new(FolderItem)
        self._message_store: Gio.ListStore = Gio.ListStore.new(MessageItem)
        # Unfiltered messages for search
        self._all_messages: list[MessageItem] = []
        # Selected message IDs for bulk operations
        self._selected_messages: set[str] = set()

        # Multi-selection state tracking
        # For SHIFT+Click range selection
        self._last_selected_index: Optional[int] = None
        # Debounce for triple-click prevention
        self._awaiting_double_click: bool = False

        # Set up the window
        self._setup_window_actions()
        self._build_ui()
        self._connect_signals()
        self._load_sample_data()
        self._apply_saved_view_density()

        # Apply CSS after window is realized
        self.connect("realize", self._on_realize)

        logger.info("Main window initialized")

    def _apply_saved_view_density(self) -> None:
        """Apply the saved view density from settings."""
        try:
            from client.services.settings_service import get_settings_service
            from .view_theme import ViewTheme, get_view_theme_manager

            settings = get_settings_service()
            saved_density = getattr(
                settings.appearance, "view_density", "standard"
            )

            theme_map = {
                "standard": ViewTheme.STANDARD,
                "minimal": ViewTheme.MINIMAL,
            }

            if saved_density in theme_map:
                target_theme = theme_map[saved_density]
                manager = get_view_theme_manager()

                # Set the correct view stack based on saved density
                if hasattr(self, "_view_type_stack"):
                    if saved_density == "minimal":
                        self._view_type_stack.set_visible_child_name(
                            "minimal-view"
                        )
                    else:
                        self._view_type_stack.set_visible_child_name(
                            "standard-view"
                        )

                # If saved density differs from current, apply it
                if manager.current_theme != target_theme:
                    manager.set_theme(target_theme)
                    logger.info(f"Applied saved view density: {saved_density}")
                else:
                    logger.info(
                        f"View density already set to: {saved_density}"
                    )
        except Exception as e:
            logger.warning(f"Could not apply saved view density: {e}")

    def _on_realize(self, widget: Gtk.Widget) -> None:
        """Handle window realization."""
        # Apply CSS styles
        if hasattr(self._application, "apply_css_to_display"):
            display = self.get_display()
            if display:
                self._application.apply_css_to_display(display)

    def _setup_window_actions(self) -> None:
        """Set up window-level actions."""
        actions = {
            "delete-message": self._on_delete_message,
            "reply": self._on_reply,
            "reply-all": self._on_reply_all,
            "forward": self._on_forward,
            "mark-read": self._on_mark_read,
            "mark-unread": self._on_mark_unread,
            "mark-starred": self._on_mark_starred,
            "unstar-message": self._on_unstar_message,
            "toggle-favorite": self._on_toggle_favorite,
            "mark-important": self._on_mark_important,
            "unmark-important": self._on_unmark_important,
            "search": self._on_search_focus,
            "next-message": self._on_next_message,
            "previous-message": self._on_previous_message,
            "move-to-archive": self._on_move_to_archive,
            "move-to-spam": self._on_move_to_spam,
            "move-to-trash": self._on_move_to_trash,
            "move-to-folder-dialog": self._on_move_to_folder_dialog,
            "folder-mark-all-read": self._on_folder_mark_all_read,
            "folder-refresh": self._on_folder_refresh,
            "folder-empty": self._on_folder_empty,
            "bulk-delete": self._on_bulk_delete,
            "bulk-mark-read": self._on_bulk_mark_read,
            "bulk-mark-unread": self._on_bulk_mark_unread,
            "bulk-favorite": self._on_bulk_favorite,
            "bulk-unfavorite": self._on_bulk_unfavorite,
            # Trash-specific actions
            "restore-to-inbox": self._on_restore_to_inbox,
            "restore-to-folder": self._on_restore_to_folder,
            "permanent-delete": self._on_permanent_delete,
        }

        for name, callback in actions.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

        logger.debug("Window actions set up")

    def _build_ui(self) -> None:
        """Build the main window UI."""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar
        self._header_bar = self._create_header_bar()
        main_box.append(self._header_bar)

        # Main content area with panes
        self._main_paned = self._create_main_paned()
        main_box.append(self._main_paned)

        # Status bar
        self._status_bar = self._create_status_bar()
        main_box.append(self._status_bar)

    def _create_header_bar(self) -> Adw.HeaderBar:
        """
        Create the header bar with actions.

        Returns:
            Configured header bar widget.
        """
        header_bar = Adw.HeaderBar()
        header_bar.add_css_class("flat")

        # Left side: Compose button
        compose_button = Gtk.Button(
            icon_name="mail-message-new-symbolic",
            tooltip_text="Compose new message (Ctrl+N)",
        )
        compose_button.add_css_class("suggested-action")
        compose_button.set_action_name("app.compose")
        header_bar.pack_start(compose_button)

        # Left side: Refresh button
        refresh_button = Gtk.Button(
            icon_name="view-refresh-symbolic",
            tooltip_text="Refresh messages (Ctrl+R)",
        )
        refresh_button.set_action_name("app.refresh")
        header_bar.pack_start(refresh_button)

        # Center: Search entry
        self._search_entry = Gtk.SearchEntry(
            placeholder_text="Search by sender, subject, or content...",
            width_chars=40,
        )
        self._search_entry.connect("search-changed", self._on_search_changed)
        self._search_entry.connect("activate", self._on_search_activated)
        header_bar.set_title_widget(self._search_entry)

        # Right side: Settings button (direct access)
        settings_button = Gtk.Button(
            icon_name="emblem-system-symbolic",
            tooltip_text="Settings (Ctrl+,)",
        )
        settings_button.set_action_name("app.settings")
        header_bar.pack_end(settings_button)

        return header_bar

    def _create_menu_button(self) -> Gtk.MenuButton:
        """
        Create the settings/menu button.

        Returns:
            Configured menu button widget.
        """
        menu_button = Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            tooltip_text="Menu",
        )

        # Create menu model
        menu = Gio.Menu()

        # View section
        view_section = Gio.Menu()
        view_section.append("Dark Mode", "app.dark-mode")
        menu.append_section("View", view_section)

        # Actions section
        actions_section = Gio.Menu()
        actions_section.append("About unitMail", "app.about")
        menu.append_section(None, actions_section)

        # Quit section
        quit_section = Gio.Menu()
        quit_section.append("Quit", "app.quit")
        menu.append_section(None, quit_section)

        menu_button.set_menu_model(menu)

        return menu_button

    def _create_main_paned(self) -> Gtk.Widget:
        """
        Create the main three-pane layout.

        Returns:
            Container widget with three panes.
        """
        # Outer paned: left (folders) | right (messages + preview)
        # resize_start_child=False ensures sidebar width persists on window
        # resize
        self._outer_paned = Gtk.Paned(
            orientation=Gtk.Orientation.HORIZONTAL,
            shrink_start_child=False,
            shrink_end_child=False,
            resize_start_child=False,
            resize_end_child=True,
        )
        self._outer_paned.set_vexpand(True)

        # Left pane: Folder tree
        folder_pane = self._create_folder_pane()
        self._outer_paned.set_start_child(folder_pane)
        self._outer_paned.set_position(self.DEFAULT_LEFT_PANE_WIDTH)

        # Inner paned: message list | preview
        inner_paned = Gtk.Paned(
            orientation=Gtk.Orientation.HORIZONTAL,
            shrink_start_child=False,
            shrink_end_child=False,
        )

        # Center pane: Message list
        message_pane = self._create_message_list_pane()
        inner_paned.set_start_child(message_pane)
        inner_paned.set_position(self.DEFAULT_CENTER_PANE_WIDTH)

        # Right pane: Message preview
        preview_pane = self._create_preview_pane()
        inner_paned.set_end_child(preview_pane)

        self._outer_paned.set_end_child(inner_paned)

        return self._outer_paned

    def _create_folder_pane(self) -> Gtk.Widget:
        """
        Create the folder tree pane.

        Returns:
            Folder pane widget.
        """
        # Container - store reference for width adjustments
        self._folder_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["folder-pane"],
        )

        # Header with title and add button
        header_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            margin_start=12,
            margin_end=8,
            margin_top=8,
            margin_bottom=8,
        )

        folder_header = Gtk.Label(
            label="Folders",
            xalign=0,
            css_classes=["heading"],
            hexpand=True,
        )
        header_box.append(folder_header)

        # New folder button (+ icon)
        self._new_folder_button = Gtk.Button(
            icon_name="folder-new-symbolic",
            tooltip_text="Create new folder",
            css_classes=["flat", "circular"],
        )
        self._new_folder_button.connect("clicked", self._on_new_folder_clicked)
        header_box.append(self._new_folder_button)

        self._folder_box.append(header_box)

        # Scrolled window for folder list
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )

        # Create folder list view
        self._folder_list = self._create_folder_list()
        scrolled.set_child(self._folder_list)

        self._folder_box.append(scrolled)

        return self._folder_box

    def _create_folder_list(self) -> Gtk.ListView:
        """
        Create the folder list view.

        Returns:
            Configured folder list view.
        """
        # Create selection model
        selection_model = Gtk.SingleSelection(model=self._folder_store)
        selection_model.connect("selection-changed", self._on_folder_selected)

        # Create factory for folder items
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_folder_item_setup)
        factory.connect("bind", self._on_folder_item_bind)

        # Create list view
        list_view = Gtk.ListView(
            model=selection_model,
            factory=factory,
            css_classes=["navigation-sidebar"],
        )

        # Add right-click context menu for folders
        self._setup_folder_context_menu(list_view)

        return list_view

    def _setup_folder_context_menu(self, list_view: Gtk.ListView) -> None:
        """Set up right-click context menu for folders."""
        # Create menu model
        menu = Gio.Menu()

        # Folder actions section
        folder_section = Gio.Menu()
        folder_section.append("Mark All as Read", "win.folder-mark-all-read")
        folder_section.append("Refresh", "win.folder-refresh")
        menu.append_section(None, folder_section)

        # Empty folder section (for Trash/Spam)
        empty_section = Gio.Menu()
        empty_section.append("Empty Folder", "win.folder-empty")
        menu.append_section(None, empty_section)

        # Create popover menu
        self._folder_context_menu = Gtk.PopoverMenu(
            menu_model=menu,
            has_arrow=False,
        )
        self._folder_context_menu.set_parent(list_view)

        # Add right-click gesture
        click_gesture = Gtk.GestureClick(button=3)  # Right click
        click_gesture.connect("pressed", self._on_folder_right_click)
        list_view.add_controller(click_gesture)

    def _on_folder_item_setup(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Set up a folder list item widget."""
        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_start=8,
            margin_end=8,
            margin_top=4,
            margin_bottom=4,
        )

        icon = Gtk.Image()
        box.append(icon)

        label = Gtk.Label(xalign=0, hexpand=True)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        box.append(label)

        badge = Gtk.Label(css_classes=["badge", "numeric"])
        box.append(badge)

        list_item.set_child(box)

    def _on_folder_item_bind(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Bind data to a folder list item widget."""
        item: FolderItem = list_item.get_item()
        box: Gtk.Box = list_item.get_child()

        children = []
        child = box.get_first_child()
        while child:
            children.append(child)
            child = child.get_next_sibling()

        icon, label, badge = children[0], children[1], children[2]

        icon.set_from_icon_name(item.icon_name)
        label.set_label(item.name)

        if item.unread_count > 0:
            badge.set_label(str(item.unread_count))
            badge.set_visible(True)
        else:
            badge.set_visible(False)

    def _create_message_list_pane(self) -> Gtk.Widget:
        """
        Create the message list pane.

        Returns:
            Message list pane widget.
        """
        # Container
        message_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["message-list-pane"],
        )

        # Note: Sort toolbar removed - column headers now provide sorting
        # functionality

        # Bulk actions toolbar (hidden by default, shown when messages are
        # selected)
        self._bulk_actions_bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4,
            margin_start=8,
            margin_end=8,
            margin_top=4,
            margin_bottom=4,
            css_classes=["bulk-actions-bar"],
        )
        self._bulk_actions_bar.set_visible(False)

        # Bulk delete button
        bulk_delete_btn = Gtk.Button(
            icon_name="user-trash-symbolic",
            tooltip_text="Delete selected messages",
        )
        bulk_delete_btn.set_action_name("win.bulk-delete")
        self._bulk_actions_bar.append(bulk_delete_btn)

        # Bulk mark read button
        bulk_read_btn = Gtk.Button(
            icon_name="mail-read-symbolic",
            tooltip_text="Mark selected as read",
        )
        bulk_read_btn.set_action_name("win.bulk-mark-read")
        self._bulk_actions_bar.append(bulk_read_btn)

        # Bulk mark unread button
        bulk_unread_btn = Gtk.Button(
            icon_name="mail-unread-symbolic",
            tooltip_text="Mark selected as unread",
        )
        bulk_unread_btn.set_action_name("win.bulk-mark-unread")
        self._bulk_actions_bar.append(bulk_unread_btn)

        # Separator
        self._bulk_actions_bar.append(
            Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        )

        # Bulk favorite button
        bulk_fav_btn = Gtk.Button(
            icon_name="starred-symbolic",
            tooltip_text="Add selected to favorites",
        )
        bulk_fav_btn.set_action_name("win.bulk-favorite")
        self._bulk_actions_bar.append(bulk_fav_btn)

        # Bulk unfavorite button
        bulk_unfav_btn = Gtk.Button(
            icon_name="non-starred-symbolic",
            tooltip_text="Remove selected from favorites",
        )
        bulk_unfav_btn.set_action_name("win.bulk-unfavorite")
        self._bulk_actions_bar.append(bulk_unfav_btn)

        # Spacer
        spacer = Gtk.Box(hexpand=True)
        self._bulk_actions_bar.append(spacer)

        # Selected count label
        self._bulk_selected_label = Gtk.Label(
            label="0 selected",
            css_classes=["dim-label"],
        )
        self._bulk_actions_bar.append(self._bulk_selected_label)

        message_box.append(self._bulk_actions_bar)

        # Separator
        message_box.append(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        )

        # Column headers for minimal view (hidden by default)
        # Alignment: margin_start matches message row box, CSS handles
        # margin-left/border-left/padding
        self._column_headers = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
            margin_start=8,  # Match message row box margin_start
            margin_end=8,
            margin_top=4,
            margin_bottom=4,
            css_classes=["column-headers"],
        )
        # Track current sort column and direction
        self._column_headers.set_visible(False)
        self._sort_column = "date"
        self._sort_ascending = False

        # Track column resize state (required by mixin)
        self._resizing_column = None
        self._resize_start_x = 0
        self._resize_start_width = 0

        # Load saved column widths from settings
        self._load_column_widths()

        # Received column header (sortable)
        self._received_header_btn = Gtk.Button(
            css_classes=["flat", "column-header-btn"],
        )
        received_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=4
        )
        received_box.append(Gtk.Label(label="Received", xalign=0))
        self._received_sort_icon = Gtk.Image(icon_name="pan-down-symbolic")
        received_box.append(self._received_sort_icon)
        self._received_header_btn.set_child(received_box)
        self._received_header_btn.set_size_request(
            self._column_width_received, -1
        )
        self._received_header_btn.connect(
            "clicked", self._on_column_header_clicked, "date"
        )
        self._column_headers.append(self._received_header_btn)

        # Resize handle for received column
        self._received_resize_handle = self._create_resize_handle("received")
        self._column_headers.append(self._received_resize_handle)

        # From column header (sortable)
        self._from_header_btn = Gtk.Button(
            css_classes=["flat", "column-header-btn"],
        )
        from_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        from_box.append(Gtk.Label(label="From", xalign=0, hexpand=True))
        self._from_sort_icon = Gtk.Image(icon_name="pan-down-symbolic")
        self._from_sort_icon.set_visible(False)
        from_box.append(self._from_sort_icon)
        self._from_header_btn.set_child(from_box)
        self._from_header_btn.set_size_request(self._column_width_from, -1)
        self._from_header_btn.connect(
            "clicked", self._on_column_header_clicked, "from"
        )
        self._column_headers.append(self._from_header_btn)

        # Resize handle for from column
        self._from_resize_handle = self._create_resize_handle("from")
        self._column_headers.append(self._from_resize_handle)

        # Subject column header (sortable)
        self._subject_header_btn = Gtk.Button(
            css_classes=["flat", "column-header-btn"],
            hexpand=True,
        )
        subject_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=4
        )
        subject_box.append(Gtk.Label(label="Subject", xalign=0, hexpand=True))
        self._subject_sort_icon = Gtk.Image(icon_name="pan-down-symbolic")
        self._subject_sort_icon.set_visible(False)
        subject_box.append(self._subject_sort_icon)
        self._subject_header_btn.set_child(subject_box)
        self._subject_header_btn.connect(
            "clicked", self._on_column_header_clicked, "subject"
        )
        self._column_headers.append(self._subject_header_btn)

        message_box.append(self._column_headers)

        # Stack for switching between message list and empty state
        self._message_list_stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE,
            transition_duration=200,
            vexpand=True,
        )

        # Inner stack to switch between standard ListView and minimal
        # ColumnView
        self._view_type_stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE,
            transition_duration=150,
            vexpand=True,
        )

        # === Standard ListView (for standard view) ===
        standard_scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )
        self._message_list = self._create_message_list()
        standard_scrolled.set_child(self._message_list)
        self._view_type_stack.add_named(standard_scrolled, "standard-view")

        # === Minimal ColumnView (for minimal/columnar view) ===
        minimal_scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )
        self._column_view = self._create_column_view()
        minimal_scrolled.set_child(self._column_view)
        self._view_type_stack.add_named(minimal_scrolled, "minimal-view")

        self._message_list_stack.add_named(
            self._view_type_stack, "message-list"
        )

        # Create default empty state (inbox)
        self._empty_state = EmptyStateWidget(
            icon_name=EMPTY_STATES["inbox"]["icon"],
            title=EMPTY_STATES["inbox"]["title"],
            description=EMPTY_STATES["inbox"]["description"],
            cta_label=EMPTY_STATES["inbox"]["cta_label"],
            cta_action=EMPTY_STATES["inbox"]["cta_action"],
        )
        self._message_list_stack.add_named(self._empty_state, "empty-state")

        message_box.append(self._message_list_stack)

        # Register with view theme manager for density changes
        try:
            from .view_theme import get_view_theme_manager

            theme_manager = get_view_theme_manager()
            theme_manager.register_widget(message_box)
            # Refresh message list when theme changes
            theme_manager.connect("theme-changed", self._on_view_theme_changed)
        except ImportError:
            pass

        return message_box

    def _on_view_theme_changed(self, manager, theme_name: str) -> None:
        """Handle view theme change - switch between standard and minimal views."""
        logger.info(f"View theme changed to: {theme_name}, switching views")

        # Hide column headers (ColumnView has its own headers now)
        if hasattr(self, "_column_headers"):
            self._column_headers.set_visible(False)

        # Switch between standard ListView and minimal ColumnView
        if hasattr(self, "_view_type_stack"):
            if theme_name == "minimal":
                self._view_type_stack.set_visible_child_name("minimal-view")
                logger.info("Switched to minimal ColumnView")
            else:
                self._view_type_stack.set_visible_child_name("standard-view")
                logger.info("Switched to standard ListView")

        # Force refresh of both views to ensure proper data binding
        self._refresh_message_list()
        if hasattr(self, "_column_view") and self._column_view:
            # Refresh the ColumnView's selection model
            cv_selection = self._column_view.get_model()
            if cv_selection and isinstance(cv_selection, Gtk.SingleSelection):
                store = cv_selection.get_model()
                if store and store.get_n_items() > 0:
                    store.items_changed(
                        0, store.get_n_items(), store.get_n_items()
                    )

    def _on_column_header_clicked(
        self, button: Gtk.Button, column: str
    ) -> None:
        """Handle column header click for sorting."""
        logger.info(f"Sort by column: {column}")

        # Toggle direction if same column, otherwise set new column
        if self._sort_column == column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = column
            self._sort_ascending = True

        # Update sort icons
        self._received_sort_icon.set_visible(column == "date")
        self._from_sort_icon.set_visible(column == "from")
        self._subject_sort_icon.set_visible(column == "subject")

        # Update icon direction
        icon_name = (
            "pan-up-symbolic" if self._sort_ascending else "pan-down-symbolic"
        )
        if column == "date":
            self._received_sort_icon.set_from_icon_name(icon_name)
        elif column == "from":
            self._from_sort_icon.set_from_icon_name(icon_name)
        elif column == "subject":
            self._subject_sort_icon.set_from_icon_name(icon_name)

        # Sort the message store
        self._sort_messages(column, self._sort_ascending)

    def _get_sort_key(self, column: str):
        """Get the sort key function for a column."""
        if column == "date":
            return lambda x: x._date
        elif column == "from":
            return lambda x: x.from_address.lower()
        elif column == "subject":
            return lambda x: (x.subject or "").lower()
        elif column == "size":
            # Use preview length as proxy for message size
            return lambda x: len(x.preview or "")
        elif column == "favorite":
            # Sort by starred status (starred first)
            return lambda x: (not x.is_starred, x._date)
        elif column == "important":
            # Sort by important status (important first)
            return lambda x: (not x.is_important, x._date)
        else:
            return lambda x: x._date  # Default to date

    def _sort_messages(self, column: str, ascending: bool) -> None:
        """Sort messages in the display store by the specified column."""
        if not hasattr(self, "_message_store") or not self._message_store:
            return

        # Get all items
        items = []
        for i in range(self._message_store.get_n_items()):
            items.append(self._message_store.get_item(i))

        # Sort based on column
        sort_key = self._get_sort_key(column)
        items.sort(key=sort_key, reverse=not ascending)

        # Clear and repopulate store
        self._message_store.remove_all()
        for item in items:
            self._message_store.append(item)

        order = "asc" if ascending else "desc"
        logger.info(f"Sorted {len(items)} messages by {column} ({order})")

    def _sort_all_messages(self, column: str, ascending: bool) -> None:
        """Sort the full message list to maintain order when search is cleared."""
        if not self._all_messages:
            return
        sort_key = self._get_sort_key(column)
        self._all_messages.sort(key=sort_key, reverse=not ascending)

    def _create_message_list(self) -> Gtk.ListView:
        """
        Create the message list view.

        Returns:
            Configured message list view.
        """
        # Create selection model
        selection_model = Gtk.SingleSelection(model=self._message_store)
        selection_model.connect("selection-changed", self._on_message_selected)

        # Create factory for message items
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_message_item_setup)
        factory.connect("bind", self._on_message_item_bind)

        # Create list view
        list_view = Gtk.ListView(
            model=selection_model,
            factory=factory,
            css_classes=["message-list"],
        )

        # Add right-click context menu
        self._setup_message_context_menu(list_view)

        return list_view

    # === ColumnView Implementation for Minimal View ===

    def _create_column_view(self) -> Gtk.ColumnView:
        """
        Create a GtkColumnView for the minimal/columnar view.

        The ColumnView provides native column resizing, proper column separators,
        and uses the activate signal for double-click handling (avoiding
        triple-click issues). Column headers are clickable for sorting.

        Returns:
            Configured ColumnView with Date, From, and Subject columns.
        """
        # Create sorters for each column
        date_sorter = Gtk.CustomSorter.new(self._compare_by_date, None)
        from_sorter = Gtk.CustomSorter.new(self._compare_by_from, None)
        favorite_sorter = Gtk.CustomSorter.new(self._compare_by_favorite, None)
        important_sorter = Gtk.CustomSorter.new(
            self._compare_by_important, None
        )
        subject_sorter = Gtk.CustomSorter.new(self._compare_by_subject, None)

        # Store sorters for later updates
        self._cv_date_sorter = date_sorter
        self._cv_from_sorter = from_sorter
        self._cv_favorite_sorter = favorite_sorter
        self._cv_important_sorter = important_sorter
        self._cv_subject_sorter = subject_sorter

        # Create sort list model wrapping the message store
        self._sort_list_model = Gtk.SortListModel(model=self._message_store)

        # Create selection model on top of the sort model
        self._column_view_selection = Gtk.SingleSelection(
            model=self._sort_list_model
        )
        self._column_view_selection.connect(
            "selection-changed", self._on_column_view_selection_changed
        )

        # Create the ColumnView
        column_view = Gtk.ColumnView(
            model=self._column_view_selection,
            reorderable=False,
            show_column_separators=True,
            show_row_separators=False,
            css_classes=["message-column-view"],
        )

        # Use 'activate' signal for double-click - avoids triple-click issues
        column_view.connect("activate", self._on_column_view_activated)

        # Favorite column - narrow, fixed width, sortable (star icon)
        favorite_factory = self._create_favorite_column_factory()
        favorite_column = Gtk.ColumnViewColumn(
            title="★",
            factory=favorite_factory,
            resizable=False,
            fixed_width=24,
        )
        favorite_column.set_sorter(favorite_sorter)
        column_view.append_column(favorite_column)
        self._cv_favorite_column = favorite_column

        # Important column - narrow, fixed width, sortable (exclamation icon)
        important_factory = self._create_important_column_factory()
        important_column = Gtk.ColumnViewColumn(
            title="!",
            factory=important_factory,
            resizable=False,
            fixed_width=24,
        )
        important_column.set_sorter(important_sorter)
        column_view.append_column(important_column)
        self._cv_important_column = important_column

        # Date/Received column - fixed width, resizable, sortable
        date_factory = self._create_date_column_factory()
        date_column = Gtk.ColumnViewColumn(
            title="Received ↓",
            factory=date_factory,
            resizable=True,
            fixed_width=self._column_width_received,
        )
        date_column.set_sorter(date_sorter)
        column_view.append_column(date_column)
        self._cv_date_column = date_column

        # From column - fixed width, resizable, sortable
        from_factory = self._create_from_column_factory()
        from_column = Gtk.ColumnViewColumn(
            title="From",
            factory=from_factory,
            resizable=True,
            fixed_width=self._column_width_from,
        )
        from_column.set_sorter(from_sorter)
        column_view.append_column(from_column)
        self._cv_from_column = from_column

        # Subject column - expands to fill remaining space, sortable
        subject_factory = self._create_subject_column_factory()
        subject_column = Gtk.ColumnViewColumn(
            title="Subject",
            factory=subject_factory,
            resizable=True,
            expand=True,
        )
        subject_column.set_sorter(subject_sorter)
        column_view.append_column(subject_column)
        self._cv_subject_column = subject_column

        # Connect to the ColumnView's sorter to detect header clicks
        cv_sorter = column_view.get_sorter()
        if cv_sorter:
            self._sort_list_model.set_sorter(cv_sorter)
            cv_sorter.connect("changed", self._on_column_sorter_changed)

        # Set up context menus for ColumnView
        self._setup_column_view_context_menu(column_view)

        logger.info(
            "Created ColumnView for minimal view with resizable columns"
        )
        return column_view

    def _compare_by_date(
        self, a: "MessageItem", b: "MessageItem", user_data
    ) -> int:
        """Compare two messages by date for sorting."""
        if a._date < b._date:
            return -1
        elif a._date > b._date:
            return 1
        return 0

    def _compare_by_from(
        self, a: "MessageItem", b: "MessageItem", user_data
    ) -> int:
        """Compare two messages by sender for sorting."""
        from_a = a.from_address.lower()
        from_b = b.from_address.lower()
        if from_a < from_b:
            return -1
        elif from_a > from_b:
            return 1
        return 0

    def _compare_by_subject(
        self, a: "MessageItem", b: "MessageItem", user_data
    ) -> int:
        """Compare two messages by subject for sorting."""
        subj_a = (a.subject or "").lower()
        subj_b = (b.subject or "").lower()
        if subj_a < subj_b:
            return -1
        elif subj_a > subj_b:
            return 1
        return 0

    def _compare_by_favorite(
        self, a: "MessageItem", b: "MessageItem", user_data
    ) -> int:
        """Compare two messages by favorite/starred status for sorting."""
        # Starred messages come first (True > False, so negate for ascending)
        if a.is_starred and not b.is_starred:
            return -1
        elif not a.is_starred and b.is_starred:
            return 1
        return 0

    def _compare_by_important(
        self, a: "MessageItem", b: "MessageItem", user_data
    ) -> int:
        """Compare two messages by important status for sorting."""
        # Important messages come first
        if a.is_important and not b.is_important:
            return -1
        elif not a.is_important and b.is_important:
            return 1
        return 0

    def _on_column_sorter_changed(
        self, sorter: Gtk.Sorter, change: Gtk.SorterChange
    ) -> None:
        """Handle column header click for sorting - sync with dropdown and direction."""
        # Get the primary sort column from the ColumnView sorter
        if (
            hasattr(self, "_cv_date_column")
            and hasattr(self, "_cv_from_column")
            and hasattr(self, "_cv_subject_column")
        ):
            # Check which column is being sorted by looking at sort order
            date_order = (
                self._cv_date_column.get_sorter().get_order()
                if self._cv_date_column.get_sorter()
                else Gtk.SorterOrder.NONE
            )
            from_order = (
                self._cv_from_column.get_sorter().get_order()
                if self._cv_from_column.get_sorter()
                else Gtk.SorterOrder.NONE
            )
            favorite_order = (
                self._cv_favorite_column.get_sorter().get_order()
                if hasattr(self, "_cv_favorite_column")
                and self._cv_favorite_column.get_sorter()
                else Gtk.SorterOrder.NONE
            )
            important_order = (
                self._cv_important_column.get_sorter().get_order()
                if hasattr(self, "_cv_important_column")
                and self._cv_important_column.get_sorter()
                else Gtk.SorterOrder.NONE
            )
            subject_order = (
                self._cv_subject_column.get_sorter().get_order()
                if self._cv_subject_column.get_sorter()
                else Gtk.SorterOrder.NONE
            )

            # Update column titles to show sort direction
            self._cv_date_column.set_title(
                "Received ↓"
                if date_order == Gtk.SorterOrder.TOTAL
                else "Received"
            )
            self._cv_from_column.set_title(
                "From ↓" if from_order == Gtk.SorterOrder.TOTAL else "From"
            )
            if hasattr(self, "_cv_favorite_column"):
                self._cv_favorite_column.set_title(
                    "★ ↓" if favorite_order == Gtk.SorterOrder.TOTAL else "★"
                )
            if hasattr(self, "_cv_important_column"):
                self._cv_important_column.set_title(
                    "! ↓" if important_order == Gtk.SorterOrder.TOTAL else "!"
                )
            self._cv_subject_column.set_title(
                "Subject ↓"
                if subject_order == Gtk.SorterOrder.TOTAL
                else "Subject"
            )

            logger.info(
                f"Column sorter changed: date={date_order}, from={from_order}, "
                f"favorite={favorite_order}, important={important_order}, "
                f"subject={subject_order}"
            )

    def _create_date_column_factory(self) -> Gtk.SignalListItemFactory:
        """
        Create factory for the Date column in ColumnView.

        Returns:
            Factory that creates date labels for each row.
        """
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_date_cell_setup)
        factory.connect("bind", self._on_date_cell_bind)
        factory.connect("unbind", self._on_date_cell_unbind)
        return factory

    def _on_date_cell_setup(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Set up a date cell widget."""
        label = Gtk.Label(
            xalign=0,
            css_classes=["message-date-cell"],
        )
        label.set_margin_start(8)
        label.set_margin_end(8)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        list_item.set_child(label)

    def _on_date_cell_bind(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Bind data to a date cell widget."""
        item: MessageItem = list_item.get_item()
        label: Gtk.Label = list_item.get_child()
        label.set_label(item.date_string)

        # Apply unread styling
        if not item.is_read:
            label.add_css_class("bold")
        else:
            label.remove_css_class("bold")

        # Connect to date-string property changes for immediate updates
        def on_date_string_changed(obj, pspec, lbl=label):
            lbl.set_label(obj.date_string)

        # Disconnect any previous handler
        if hasattr(label, "_date_handler_id") and label._date_handler_id:
            try:
                item.disconnect(label._date_handler_id)
            except Exception:
                pass
        label._date_handler_id = item.connect(
            "notify::date-string", on_date_string_changed
        )
        label._date_item = item  # Store reference to disconnect later

    def _on_date_cell_unbind(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Unbind date cell widget - disconnect signal handlers."""
        label: Gtk.Label = list_item.get_child()
        if hasattr(label, "_date_handler_id") and label._date_handler_id:
            try:
                if hasattr(label, "_date_item") and label._date_item:
                    label._date_item.disconnect(label._date_handler_id)
            except Exception:
                pass
            label._date_handler_id = None
            label._date_item = None

    def _create_from_column_factory(self) -> Gtk.SignalListItemFactory:
        """
        Create factory for the From column in ColumnView.

        Returns:
            Factory that creates sender labels for each row.
        """
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_from_cell_setup)
        factory.connect("bind", self._on_from_cell_bind)
        return factory

    def _on_from_cell_setup(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Set up a from cell widget."""
        label = Gtk.Label(
            xalign=0,
            css_classes=["message-from-cell"],
        )
        label.set_margin_start(8)
        label.set_margin_end(8)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        list_item.set_child(label)

    def _on_from_cell_bind(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Bind data to a from cell widget."""
        item: MessageItem = list_item.get_item()
        label: Gtk.Label = list_item.get_child()
        label.set_label(item.from_address)

        # Apply unread styling
        if not item.is_read:
            label.add_css_class("bold")
        else:
            label.remove_css_class("bold")

    def _create_subject_column_factory(self) -> Gtk.SignalListItemFactory:
        """
        Create factory for the Subject column in ColumnView.

        Returns:
            Factory that creates subject labels for each row.
        """
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_subject_cell_setup)
        factory.connect("bind", self._on_subject_cell_bind)
        return factory

    def _on_subject_cell_setup(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Set up a subject cell widget."""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(8)
        box.set_margin_end(8)

        # Subject label
        label = Gtk.Label(
            xalign=0,
            hexpand=True,
            css_classes=["message-subject-cell"],
        )
        label.set_ellipsize(Pango.EllipsizeMode.END)
        box.append(label)

        # Attachment indicator
        attachment_icon = Gtk.Image(
            icon_name="mail-attachment-symbolic",
            css_classes=["attachment-indicator", "dim-label"],
        )
        attachment_icon.set_visible(False)
        box.append(attachment_icon)

        list_item.set_child(box)

    def _on_subject_cell_bind(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Bind data to a subject cell widget."""
        item: MessageItem = list_item.get_item()
        box: Gtk.Box = list_item.get_child()

        # Get child widgets
        children = []
        child = box.get_first_child()
        while child:
            children.append(child)
            child = child.get_next_sibling()

        label, attachment_icon = children

        # Set subject
        label.set_label(item.subject or "(No subject)")

        # Show/hide attachment indicator
        attachment_icon.set_visible(item.has_attachments)

        # Apply unread styling
        if not item.is_read:
            label.add_css_class("bold")
        else:
            label.remove_css_class("bold")

    def _create_favorite_column_factory(self) -> Gtk.SignalListItemFactory:
        """
        Create factory for the Favorite (star) column in ColumnView.

        Returns:
            Factory that creates star icons for each row.
        """
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_favorite_cell_setup)
        factory.connect("bind", self._on_favorite_cell_bind)
        return factory

    def _on_favorite_cell_setup(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Set up a favorite cell widget with clickable icon."""
        icon = Gtk.Image(
            icon_name="non-starred-symbolic",
            css_classes=["favorite-indicator"],
        )
        icon.set_margin_start(0)
        icon.set_margin_end(0)

        # Add click gesture for toggling
        click_gesture = Gtk.GestureClick()
        icon.add_controller(click_gesture)
        icon._click_gesture = click_gesture

        list_item.set_child(icon)

    def _on_favorite_cell_bind(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Bind data to a favorite cell widget."""
        item: MessageItem = list_item.get_item()
        icon: Gtk.Image = list_item.get_child()

        # Always show star icon, use CSS class for active/inactive state
        icon.set_from_icon_name("starred-symbolic")
        if item.is_starred:
            icon.add_css_class("favorite-active")
            icon.remove_css_class("favorite-inactive")
        else:
            icon.add_css_class("favorite-inactive")
            icon.remove_css_class("favorite-active")

        # Disconnect any existing handler
        if hasattr(icon, "_click_handler_id") and icon._click_handler_id:
            icon._click_gesture.disconnect(icon._click_handler_id)

        # Connect click handler with the message item
        def on_click(gesture, n_press, x, y, img=icon, msg_item=item):
            new_state = not msg_item.is_starred
            self._set_message_starred(msg_item.message_id, new_state)
            if new_state:
                img.add_css_class("favorite-active")
                img.remove_css_class("favorite-inactive")
            else:
                img.add_css_class("favorite-inactive")
                img.remove_css_class("favorite-active")

        icon._click_handler_id = icon._click_gesture.connect(
            "pressed", on_click
        )

    def _create_important_column_factory(self) -> Gtk.SignalListItemFactory:
        """
        Create factory for the Important column in ColumnView.

        Returns:
            Factory that creates important icons for each row.
        """
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_important_cell_setup)
        factory.connect("bind", self._on_important_cell_bind)
        return factory

    def _on_important_cell_setup(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Set up an important cell widget with clickable icon."""
        icon = Gtk.Image(
            icon_name="dialog-warning-symbolic",
            css_classes=["important-indicator"],
        )
        icon.set_margin_start(0)
        icon.set_margin_end(0)

        # Add click gesture for toggling
        click_gesture = Gtk.GestureClick()
        icon.add_controller(click_gesture)
        icon._click_gesture = click_gesture

        list_item.set_child(icon)

    def _on_important_cell_bind(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Bind data to an important cell widget."""
        item: MessageItem = list_item.get_item()
        icon: Gtk.Image = list_item.get_child()

        # Always show warning icon, use CSS class for active/inactive state
        icon.set_from_icon_name("dialog-warning-symbolic")
        if item.is_important:
            icon.add_css_class("important-active")
            icon.remove_css_class("important-inactive")
        else:
            icon.add_css_class("important-inactive")
            icon.remove_css_class("important-active")

        # Disconnect any existing handler
        if hasattr(icon, "_click_handler_id") and icon._click_handler_id:
            icon._click_gesture.disconnect(icon._click_handler_id)

        # Connect click handler with the message item
        def on_click(gesture, n_press, x, y, img=icon, msg_item=item):
            new_state = not msg_item.is_important
            self._set_message_important(msg_item.message_id, new_state)
            if new_state:
                img.add_css_class("important-active")
                img.remove_css_class("important-inactive")
            else:
                img.add_css_class("important-inactive")
                img.remove_css_class("important-active")

        icon._click_handler_id = icon._click_gesture.connect(
            "pressed", on_click
        )

    def _on_column_view_selection_changed(
        self,
        selection: Gtk.SingleSelection,
        position: int,
        n_items: int,
    ) -> None:
        """Handle selection change in the ColumnView."""
        selected = selection.get_selected_item()
        if selected:
            self._selected_message_id = selected.message_id
            self._show_message_preview(selected)
            logger.info(f"ColumnView selected: {selected.subject}")

    def _on_column_view_activated(
        self,
        column_view: Gtk.ColumnView,
        position: int,
    ) -> None:
        """
        Handle item activation (double-click) in the ColumnView.

        The 'activate' signal fires on double-click by default, which
        avoids the triple-click detection issues present in gesture-based
        approaches.

        Args:
            column_view: The ColumnView widget.
            position: Index of the activated item.
        """
        item = self._message_store.get_item(position)
        if not item:
            return

        self._selected_message_id = item.message_id
        logger.info(f"ColumnView activated (double-click): {item.subject}")

        # Check if we're in the Drafts folder - open for editing if so
        if self._is_drafts_folder():
            self._open_draft_for_editing(item)
        else:
            self._open_message_popout(item)

    def _setup_column_view_context_menu(
        self, column_view: Gtk.ColumnView
    ) -> None:
        """Set up right-click context menus for the ColumnView."""
        # Create context menus (reuse same menu models as ListView)
        self._cv_message_context_menu = self._create_regular_context_menu()
        self._cv_message_context_menu.set_parent(column_view)

        self._cv_trash_context_menu = self._create_trash_context_menu()
        self._cv_trash_context_menu.set_parent(column_view)

        # Add right-click gesture
        click_gesture = Gtk.GestureClick(button=3)  # Right click
        click_gesture.connect("pressed", self._on_column_view_right_click)
        column_view.add_controller(click_gesture)

    def _on_column_view_right_click(
        self,
        gesture: Gtk.GestureClick,
        n_press: int,
        x: float,
        y: float,
    ) -> None:
        """Handle right-click on ColumnView."""
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1

        current_folder = self._get_selected_folder_name()
        if current_folder.lower() == "trash":
            self._cv_trash_context_menu.set_pointing_to(rect)
            self._cv_trash_context_menu.popup()
        else:
            self._cv_message_context_menu.set_pointing_to(rect)
            self._cv_message_context_menu.popup()

    # === End ColumnView Implementation ===

    def _setup_message_context_menu(self, list_view: Gtk.ListView) -> None:
        """Set up right-click context menus for messages.

        Creates two context menus:
        - Regular context menu for normal folders
        - Trash context menu with restore and permanent delete options
        """
        # Create regular context menu
        self._message_context_menu = self._create_regular_context_menu()
        self._message_context_menu.set_parent(list_view)

        # Create Trash-specific context menu
        self._trash_context_menu = self._create_trash_context_menu()
        self._trash_context_menu.set_parent(list_view)

        # Add right-click gesture
        click_gesture = Gtk.GestureClick(button=3)  # Right click
        click_gesture.connect("pressed", self._on_message_right_click)
        list_view.add_controller(click_gesture)

        # Add left-click gesture for multi-selection (CTRL+Click, SHIFT+Click)
        # and double-click for message pop-out
        left_click_gesture = Gtk.GestureClick(button=1)  # Left click
        left_click_gesture.connect("pressed", self._on_message_left_click)
        list_view.add_controller(left_click_gesture)

    def _create_regular_context_menu(self) -> Gtk.PopoverMenu:
        """Create the regular context menu for non-Trash folders.

        Returns:
            Configured PopoverMenu for regular message actions.
        """
        menu = Gio.Menu()

        # Read/unread section
        read_section = Gio.Menu()
        read_section.append("Mark as Read", "win.mark-read")
        read_section.append("Mark as Unread", "win.mark-unread")
        menu.append_section(None, read_section)

        # Favorite section
        favorite_section = Gio.Menu()
        favorite_section.append("Add to Favorites", "win.mark-starred")
        favorite_section.append("Remove from Favorites", "win.unstar-message")
        menu.append_section(None, favorite_section)

        # Important section
        important_section = Gio.Menu()
        important_section.append("Mark as Important", "win.mark-important")
        important_section.append("Remove Important", "win.unmark-important")
        menu.append_section(None, important_section)

        # Actions section
        action_section = Gio.Menu()
        action_section.append("Reply", "win.reply")
        action_section.append("Reply All", "win.reply-all")
        action_section.append("Forward", "win.forward")
        menu.append_section(None, action_section)

        # Move section
        move_section = Gio.Menu()
        move_submenu = Gio.Menu()
        move_submenu.append("Archive", "win.move-to-archive")
        move_submenu.append("Spam", "win.move-to-spam")
        move_submenu.append("Trash", "win.move-to-trash")
        # Add separator and option to choose any folder
        move_submenu.append("Choose Folder...", "win.move-to-folder-dialog")
        move_section.append_submenu("Move to...", move_submenu)
        menu.append_section(None, move_section)

        # Delete section
        delete_section = Gio.Menu()
        delete_section.append("Delete", "win.delete-message")
        menu.append_section(None, delete_section)

        return Gtk.PopoverMenu(
            menu_model=menu,
            has_arrow=False,
        )

    def _create_trash_context_menu(self) -> Gtk.PopoverMenu:
        """Create the Trash-specific context menu with restore options.

        Returns:
            Configured PopoverMenu for Trash message actions.
        """
        menu = Gio.Menu()

        # Restore section
        restore_section = Gio.Menu()
        restore_section.append("Restore to Inbox", "win.restore-to-inbox")
        restore_section.append("Move to...", "win.restore-to-folder")
        menu.append_section(None, restore_section)

        # Read/unread section
        read_section = Gio.Menu()
        read_section.append("Mark as Read", "win.mark-read")
        read_section.append("Mark as Unread", "win.mark-unread")
        menu.append_section(None, read_section)

        # Delete section (permanent)
        delete_section = Gio.Menu()
        delete_section.append("Delete Permanently", "win.permanent-delete")
        menu.append_section(None, delete_section)

        return Gtk.PopoverMenu(
            menu_model=menu,
            has_arrow=False,
        )

    def _on_message_item_setup(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Set up a message list item widget."""
        # Main container
        row_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_start=8,
            margin_end=8,
            margin_top=8,
            margin_bottom=8,
            css_classes=["message-row"],
        )

        # Checkbox for selection
        check = Gtk.CheckButton()
        row_box.append(check)

        # Favorite button
        favorite_button = Gtk.ToggleButton(
            icon_name="starred-symbolic",
            css_classes=["flat", "favorite-button"],
            tooltip_text="Toggle favorite",
        )
        row_box.append(favorite_button)

        # Content container
        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=2,
            hexpand=True,
        )

        # Header row (from + date)
        header_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )

        from_label = Gtk.Label(
            xalign=0,
            hexpand=True,
            css_classes=["message-from"],
        )
        from_label.set_ellipsize(Pango.EllipsizeMode.END)
        header_box.append(from_label)

        date_label = Gtk.Label(
            xalign=1,
            css_classes=["dim-label", "message-date"],
        )
        header_box.append(date_label)

        content_box.append(header_box)

        # Subject row
        subject_label = Gtk.Label(
            xalign=0,
            css_classes=["message-subject"],
        )
        subject_label.set_ellipsize(Pango.EllipsizeMode.END)
        content_box.append(subject_label)

        # Preview row
        preview_label = Gtk.Label(
            xalign=0,
            css_classes=["dim-label", "message-preview"],
        )
        preview_label.set_ellipsize(Pango.EllipsizeMode.END)
        content_box.append(preview_label)

        row_box.append(content_box)

        # Attachment indicator (icon + count)
        attachment_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=2,
            css_classes=["attachment-indicator"],
        )
        attachment_icon = Gtk.Image(
            icon_name="mail-attachment-symbolic",
            css_classes=["dim-label"],
        )
        attachment_box.append(attachment_icon)
        attachment_count_label = Gtk.Label(
            css_classes=["dim-label", "attachment-count"],
        )
        attachment_box.append(attachment_count_label)
        row_box.append(attachment_box)

        list_item.set_child(row_box)

    def _on_message_item_bind(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Bind data to a message list item widget."""
        item: MessageItem = list_item.get_item()
        row_box: Gtk.Box = list_item.get_child()

        # Get child widgets
        children = []
        child = row_box.get_first_child()
        while child:
            children.append(child)
            child = child.get_next_sibling()

        check, favorite_button, content_box, attachment_box = (
            children[0],
            children[1],
            children[2],
            children[3],
        )

        # Checkbox for selection
        check.set_active(item.message_id in self._selected_messages)
        # Disconnect any previous handler to avoid duplicates
        try:
            check.disconnect_by_func(self._on_message_check_toggled)
        except TypeError:
            pass  # No previous handler
        check.connect(
            "toggled", self._on_message_check_toggled, item.message_id
        )

        # Favorite button
        favorite_button.set_active(item.is_starred)

        # Get content children
        content_children = []
        child = content_box.get_first_child()
        while child:
            content_children.append(child)
            child = child.get_next_sibling()

        header_box, subject_label, preview_label = content_children

        # Header children
        header_children = []
        child = header_box.get_first_child()
        while child:
            header_children.append(child)
            child = child.get_next_sibling()

        from_label, date_label = header_children

        # Standard view: normal layout with preview
        # Note: Minimal view now uses ColumnView, not this ListView
        from_label.set_label(item.from_address)
        date_label.set_label(item.date_string)
        date_label.set_visible(True)
        subject_label.set_label(item.subject or "(No subject)")
        subject_label.set_visible(True)
        preview_label.set_label(item.preview or "")
        preview_label.set_visible(True)
        # Show checkbox and favorite button in standard view
        check.set_visible(True)
        favorite_button.set_visible(True)
        # Normal row padding
        row_box.set_margin_top(8)
        row_box.set_margin_bottom(8)

        # Apply unread styling
        if not item.is_read:
            row_box.add_css_class("unread")
            from_label.add_css_class("bold")
            subject_label.add_css_class("bold")
        else:
            row_box.remove_css_class("unread")
            from_label.remove_css_class("bold")
            subject_label.remove_css_class("bold")

        # Apply favorite styling (left border in minimal view via CSS)
        if item.is_starred:
            row_box.add_css_class("favorite")
        else:
            row_box.remove_css_class("favorite")

        # Show/hide attachment indicator with count
        if item.has_attachments:
            attachment_box.set_visible(True)
            # Get the count label (second child of attachment_box)
            count_label = attachment_box.get_first_child().get_next_sibling()
            if count_label and item.attachment_count > 1:
                count_label.set_label(str(item.attachment_count))
                count_label.set_visible(True)
            elif count_label:
                count_label.set_visible(False)
        else:
            attachment_box.set_visible(False)

    def _create_preview_pane(self) -> Gtk.Widget:
        """
        Create the message preview pane.

        Returns:
            Preview pane widget.
        """
        # Container with header and content
        preview_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["preview-pane"],
        )

        # Preview header
        self._preview_header = self._create_preview_header()
        preview_box.append(self._preview_header)

        # Separator
        preview_box.append(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        )

        # Message content
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )

        # Use a text view for now (could use WebKit for HTML)
        self._preview_text = Gtk.TextView(
            editable=False,
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            left_margin=16,
            right_margin=16,
            top_margin=16,
            bottom_margin=16,
            css_classes=["preview-content"],
        )
        scrolled.set_child(self._preview_text)

        preview_box.append(scrolled)

        # Show placeholder initially
        self._show_preview_placeholder()

        return preview_box

    def _create_preview_header(self) -> Gtk.Widget:
        """
        Create the preview header with message actions.

        Returns:
            Preview header widget.
        """
        header_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_start=16,
            margin_end=16,
            margin_top=12,
            margin_bottom=12,
        )

        # Action bar
        action_bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4,
        )

        reply_button = Gtk.Button(
            icon_name="mail-reply-sender-symbolic",
            tooltip_text="Reply (Ctrl+Shift+R)",
        )
        reply_button.set_action_name("win.reply")
        action_bar.append(reply_button)

        reply_all_button = Gtk.Button(
            icon_name="mail-reply-all-symbolic",
            tooltip_text="Reply All (Ctrl+Shift+A)",
        )
        reply_all_button.set_action_name("win.reply-all")
        action_bar.append(reply_all_button)

        forward_button = Gtk.Button(
            icon_name="mail-forward-symbolic",
            tooltip_text="Forward (Ctrl+Shift+F)",
        )
        forward_button.set_action_name("win.forward")
        action_bar.append(forward_button)

        action_bar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        # Favorite toggle button for reading pane
        self._preview_favorite_button = Gtk.ToggleButton(
            icon_name="non-starred-symbolic",
            tooltip_text="Add/Remove favorite",
            css_classes=["flat", "favorite-toggle"],
        )
        self._preview_favorite_button.connect(
            "toggled", self._on_preview_favorite_toggled
        )
        action_bar.append(self._preview_favorite_button)

        # Important toggle button for reading pane
        self._preview_important_button = Gtk.ToggleButton(
            icon_name="dialog-warning-symbolic",
            tooltip_text="Mark as Important",
            css_classes=["flat", "important-toggle"],
        )
        self._preview_important_button.connect(
            "toggled", self._on_preview_important_toggled
        )
        action_bar.append(self._preview_important_button)

        action_bar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        delete_button = Gtk.Button(
            icon_name="user-trash-symbolic",
            tooltip_text="Move to Trash (Delete)",
            css_classes=["destructive-action"],
        )
        delete_button.set_action_name("win.move-to-trash")
        action_bar.append(delete_button)

        # Spacer
        spacer = Gtk.Box(hexpand=True)
        action_bar.append(spacer)

        # More actions menu
        more_menu = Gio.Menu()

        # Read/unread section
        read_section = Gio.Menu()
        read_section.append("Mark as Read", "win.mark-read")
        read_section.append("Mark as Unread", "win.mark-unread")
        more_menu.append_section(None, read_section)

        # Move section
        move_section = Gio.Menu()
        move_submenu = Gio.Menu()
        move_submenu.append("Archive", "win.move-to-archive")
        move_submenu.append("Spam", "win.move-to-spam")
        move_submenu.append("Trash", "win.move-to-trash")
        move_submenu.append("Choose Folder...", "win.move-to-folder-dialog")
        move_section.append_submenu("Move to...", move_submenu)
        more_menu.append_section(None, move_section)

        more_button = Gtk.MenuButton(
            icon_name="view-more-symbolic",
            tooltip_text="More actions",
            menu_model=more_menu,
        )
        action_bar.append(more_button)

        header_box.append(action_bar)

        # Subject line
        self._preview_subject = Gtk.Label(
            xalign=0,
            css_classes=["title-2"],
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
        )
        header_box.append(self._preview_subject)

        # From/To/Date info
        info_grid = Gtk.Grid(
            row_spacing=4,
            column_spacing=8,
        )

        # From row
        from_label = Gtk.Label(
            label="From:",
            xalign=1,
            css_classes=["dim-label"],
        )
        info_grid.attach(from_label, 0, 0, 1, 1)

        self._preview_from = Gtk.Label(xalign=0, hexpand=True)
        info_grid.attach(self._preview_from, 1, 0, 1, 1)

        # To row
        to_label = Gtk.Label(
            label="To:",
            xalign=1,
            css_classes=["dim-label"],
        )
        info_grid.attach(to_label, 0, 1, 1, 1)

        self._preview_to = Gtk.Label(xalign=0, hexpand=True)
        info_grid.attach(self._preview_to, 1, 1, 1, 1)

        # Date row
        date_label = Gtk.Label(
            label="Date:",
            xalign=1,
            css_classes=["dim-label"],
        )
        info_grid.attach(date_label, 0, 2, 1, 1)

        self._preview_date = Gtk.Label(xalign=0, hexpand=True)
        info_grid.attach(self._preview_date, 1, 2, 1, 1)

        header_box.append(info_grid)

        return header_box

    def _show_preview_placeholder(self) -> None:
        """Show placeholder content in preview pane."""
        self._preview_subject.set_label("")
        self._preview_from.set_label("")
        self._preview_to.set_label("")
        self._preview_date.set_label("")

        buffer = self._preview_text.get_buffer()
        buffer.set_text("Select a message to view")

    def _create_status_bar(self) -> Gtk.Widget:
        """
        Create the status bar.

        Returns:
            Status bar widget.
        """
        status_bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=16,
            margin_start=12,
            margin_end=12,
            margin_top=4,
            margin_bottom=4,
            css_classes=["statusbar"],
        )

        # Connection status
        self._connection_icon = Gtk.Image(
            icon_name="network-offline-symbolic",
            css_classes=["dim-label"],
        )
        status_bar.append(self._connection_icon)

        self._connection_label = Gtk.Label(
            label="Disconnected",
            css_classes=["dim-label"],
        )
        status_bar.append(self._connection_label)

        # Separator
        status_bar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        # Queue depth
        queue_icon = Gtk.Image(
            icon_name="mail-send-symbolic",
            css_classes=["dim-label"],
        )
        status_bar.append(queue_icon)

        self._queue_label = Gtk.Label(
            label="Queue: 0",
            css_classes=["dim-label"],
        )
        status_bar.append(self._queue_label)

        # Separator
        status_bar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        # Unread count
        unread_icon = Gtk.Image(
            icon_name="mail-unread-symbolic",
            css_classes=["dim-label"],
        )
        status_bar.append(unread_icon)

        self._unread_label = Gtk.Label(
            label="Unread: 0",
            css_classes=["dim-label"],
        )
        status_bar.append(self._unread_label)

        # Spacer
        spacer = Gtk.Box(hexpand=True)
        status_bar.append(spacer)

        # Last sync time
        self._sync_label = Gtk.Label(
            label="Never synced",
            css_classes=["dim-label"],
        )
        status_bar.append(self._sync_label)

        return status_bar

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        # Window close
        self.connect("close-request", self._on_close_request)

        # Connect to date format change signal for immediate refresh
        try:
            from client.services.date_format_service import (
                get_date_format_service,
            )

            date_service = get_date_format_service()
            date_service.connect(
                "format-changed", self._on_date_format_changed
            )
            logger.debug("Connected to date format change signal")
        except Exception as e:
            logger.warning(f"Could not connect to date format service: {e}")

    def _on_date_format_changed(self, service, format_str: str) -> None:
        """Handle date format change - refresh message list immediately."""
        logger.info(
            f"Date format changed to: {format_str}, refreshing message list"
        )
        # Notify all MessageItems that their date-string property has changed
        # This forces GTK to re-read the property value from each item
        for i in range(self._message_store.get_n_items()):
            item = self._message_store.get_item(i)
            if item:
                item.notify("date-string")
        self._refresh_message_list()

    def _load_sample_data(self) -> None:
        """Load sample data from local storage for development/testing."""
        # Initialize sample data in the database if not already present
        try:
            count = generate_sample_messages()
            logger.info(f"Database initialized with {count} messages")
        except Exception as e:
            logger.warning(f"Could not generate sample messages: {e}")

        # Get storage instance
        storage = get_storage()

        # Load folders from database
        db_folders = storage.get_folders()
        for db_folder in db_folders:
            folder_name = db_folder["name"]
            folder_type = db_folder.get("folder_type", "custom")

            # Map folder types to icons
            icon_map = {
                "inbox": "mail-inbox-symbolic",
                "sent": "mail-send-symbolic",
                "drafts": "mail-drafts-symbolic",
                "trash": "user-trash-symbolic",
                "spam": "mail-mark-junk-symbolic",
                "archive": "folder-symbolic",
                "custom": "folder-symbolic",
            }
            icon = icon_map.get(folder_type, "folder-symbolic")

            folder_item = FolderItem(
                db_folder["id"],
                folder_name,
                icon,
                db_folder.get("unread_count", 0),
                folder_type,
            )
            self._folder_store.append(folder_item)

        # Adjust sidebar width based on longest folder name
        self._adjust_sidebar_width()

        # Load inbox messages by default
        self._load_folder_messages("Inbox")
        self._update_message_count()

    def _adjust_sidebar_width(self) -> None:
        """Adjust sidebar width based on the longest folder name."""
        if not hasattr(self, "_outer_paned") or not self._outer_paned:
            return

        # Find the longest folder name
        max_length = 0
        for i in range(self._folder_store.get_n_items()):
            folder = self._folder_store.get_item(i)
            if folder and len(folder.name) > max_length:
                max_length = len(folder.name)

        # Calculate width: icon (20px) + text (~7px per char) +
        # padding (12px) + unread badge (20px). Min 90px, max 200px.
        char_width = 7  # Approximate pixels per character
        icon_width = 20
        padding = 12
        badge_width = 20

        calculated_width = (
            icon_width + (max_length * char_width) + padding + badge_width
        )
        sidebar_width = max(90, min(200, calculated_width))

        # Set paned position and enforce minimum width on folder box
        self._outer_paned.set_position(sidebar_width)
        if hasattr(self, "_folder_box") and self._folder_box:
            self._folder_box.set_size_request(sidebar_width, -1)

        logger.debug(
            f"Sidebar width set to {sidebar_width}px "
            f"(longest folder: {max_length} chars)"
        )

    def _update_message_count(self) -> None:
        """Update the bulk actions bar visibility based on selection."""
        count = self._message_store.get_n_items()
        selected = len(self._selected_messages)

        # Show/hide bulk actions bar based on selection
        if hasattr(self, "_bulk_actions_bar"):
            self._bulk_actions_bar.set_visible(selected > 0)
            if selected > 0:
                self._bulk_selected_label.set_label(f"{selected} selected")

        # Update empty state visibility
        self._update_empty_state_visibility(count)

    def _update_empty_state_visibility(self, message_count: int) -> None:
        """Update the empty state visibility based on message count.

        Args:
            message_count: Number of messages in the current folder.
        """
        if not hasattr(self, "_message_list_stack"):
            return

        if message_count == 0:
            # Show empty state
            self._message_list_stack.set_visible_child_name("empty-state")
            # Update empty state content based on current folder
            self._update_empty_state_content()
        else:
            # Show message list
            self._message_list_stack.set_visible_child_name("message-list")

    def _update_empty_state_content(self) -> None:
        """Update the empty state content based on the current folder."""
        if not hasattr(self, "_empty_state"):
            return

        # Determine empty state type based on folder
        folder_id = getattr(self, "_selected_folder_id", "inbox")
        folder_name = (folder_id or "inbox").lower()

        # Map folder names to empty state configs
        folder_to_state = {
            "inbox": "inbox",
            "drafts": "drafts_empty",
            "sent": "sent_empty",
            "trash": "trash_empty",
            "spam": "spam_empty",
            "junk": "spam_empty",
        }

        state_key = folder_to_state.get(folder_name, "folder_empty")
        state_config = EMPTY_STATES.get(
            state_key, EMPTY_STATES["folder_empty"]
        )

        # Remove old empty state and create new one
        self._message_list_stack.remove(self._empty_state)

        self._empty_state = EmptyStateWidget(
            icon_name=state_config["icon"],
            title=state_config["title"],
            description=state_config["description"],
            cta_label=state_config.get("cta_label"),
            cta_action=state_config.get("cta_action"),
        )
        self._message_list_stack.add_named(self._empty_state, "empty-state")
        self._message_list_stack.set_visible_child_name("empty-state")

    # Event handlers

    def _on_close_request(self, window: Gtk.Window) -> bool:
        """Handle window close request."""
        self.save_window_state()
        return False  # Allow close

    def _on_folder_selected(
        self,
        selection: Gtk.SingleSelection,
        position: int,
        n_items: int,
    ) -> None:
        """Handle folder selection change."""
        selected = selection.get_selected_item()
        if selected:
            self._selected_folder_id = selected.folder_id
            logger.info(f"Selected folder: {selected.name}")
            # Load messages for this folder
            self._load_folder_messages(selected.name)

    def _load_folder_messages(self, folder_name: str) -> None:
        """Load messages for a specific folder from database."""
        self._message_store.remove_all()

        # Get messages from local storage
        storage = get_storage()
        db_messages = storage.get_messages_by_folder(folder_name)

        # Convert database messages to MessageItem objects
        messages = []
        for db_msg in db_messages:
            # Parse the received_at datetime
            received_at = db_msg.get("received_at")
            if isinstance(received_at, str):
                try:
                    msg_date = datetime.fromisoformat(
                        received_at.replace("Z", "+00:00")
                    )
                except ValueError:
                    msg_date = datetime.now()
            else:
                msg_date = datetime.now()

            # Get sender display - use header or from_address
            from_addr = db_msg.get("from_address", "unknown@example.com")
            headers = db_msg.get("headers", {})
            from_display = headers.get("From", from_addr)

            # For sent messages, show "me → recipient"
            if folder_name.lower() == "sent":
                to_addresses = db_msg.get("to_addresses", [])
                to_display = headers.get(
                    "To", ", ".join(to_addresses) if to_addresses else ""
                )
                from_display = f"me@unitmail.local → {
                    to_display.split('<')[0].strip()}"

            # Get preview from body_text
            body_text = db_msg.get("body_text", "")
            preview = (
                body_text[:100] + "..." if len(body_text) > 100 else body_text
            )
            preview = preview.replace("\n", " ").strip()

            # Check for attachments
            attachments = db_msg.get("attachments", [])
            has_attachments = len(attachments) > 0
            attachment_count = len(attachments)

            message_item = MessageItem(
                message_id=db_msg.get("id", ""),
                from_address=from_display,
                subject=db_msg.get("subject", "(No subject)"),
                preview=preview,
                date=msg_date,
                is_read=db_msg.get("is_read", False),
                is_starred=db_msg.get("is_starred", False),
                is_important=db_msg.get("is_important", False),
                has_attachments=has_attachments,
                attachment_count=attachment_count,
            )
            messages.append(message_item)

        self._all_messages = (
            messages.copy()
        )  # Store unfiltered list for search
        for message in messages:
            self._message_store.append(message)

        # Clear search and selection when switching folders
        self._search_entry.set_text("")
        self._selected_messages.clear()
        self._last_selected_index = None  # Reset for SHIFT+Click in new folder
        self._update_select_all_state()

        self._update_message_count()
        self._show_preview_placeholder()

    def _on_message_selected(
        self,
        selection: Gtk.SingleSelection,
        position: int,
        n_items: int,
    ) -> None:
        """Handle message selection change."""
        selected = selection.get_selected_item()
        if selected:
            self._selected_message_id = selected.message_id
            self._show_message_preview(selected)
            logger.info(f"Selected message: {selected.subject}")

    def _show_message_preview(self, message: MessageItem) -> None:
        """
        Show message in preview pane.

        Args:
            message: The message to display.
        """
        self._preview_subject.set_label(message.subject or "(No subject)")
        self._preview_from.set_label(message.from_address)
        self._preview_to.set_label("me@unitmail.local")

        # Use centralized date formatter for preview pane
        try:
            from client.services.date_format_service import (
                format_date_with_time,
            )

            self._preview_date.set_label(format_date_with_time(message._date))
        except ImportError:
            self._preview_date.set_label(
                message._date.strftime("%B %d, %Y at %H:%M")
            )

        # Update favorite button state in reading pane
        if hasattr(self, "_preview_favorite_button"):
            # Block signal to avoid triggering toggle during update
            self._preview_favorite_button.handler_block_by_func(
                self._on_preview_favorite_toggled
            )
            self._preview_favorite_button.set_active(message.is_starred)
            # Update icon based on state
            icon_name = (
                "starred-symbolic"
                if message.is_starred
                else "non-starred-symbolic"
            )
            self._preview_favorite_button.set_icon_name(icon_name)
            self._preview_favorite_button.handler_unblock_by_func(
                self._on_preview_favorite_toggled
            )

        # Update important button state in reading pane
        if hasattr(self, "_preview_important_button"):
            # Block signal to avoid triggering toggle during update
            self._preview_important_button.handler_block_by_func(
                self._on_preview_important_toggled
            )
            self._preview_important_button.set_active(message.is_important)
            self._preview_important_button.handler_unblock_by_func(
                self._on_preview_important_toggled
            )

        # Get full message body from database
        storage = get_storage()
        db_message = storage.get_message(message.message_id)

        if db_message:
            body_text = db_message.get("body_text", message.preview) or ""
            buffer = self._preview_text.get_buffer()
            buffer.set_text(body_text)

            # Update recipient display
            to_addresses = db_message.get("to_addresses", [])
            if to_addresses:
                self._preview_to.set_label(", ".join(to_addresses))
        else:
            # Fallback to preview
            buffer = self._preview_text.get_buffer()
            buffer.set_text(message.preview or "")

        # Mark as read in database
        if not message.is_read:
            message.is_read = True
            storage.mark_as_read(message.message_id)

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Handle search text change."""
        text = entry.get_text().strip().lower()
        logger.debug(f"Search text: {text}")
        self._filter_messages(text)

    def _on_search_activated(self, entry: Gtk.SearchEntry) -> None:
        """Handle search activation (Enter pressed)."""
        text = entry.get_text().strip().lower()
        logger.info(f"Search activated: {text}")
        self._filter_messages(text)

    def _filter_messages(self, search_text: str) -> None:
        """Filter messages based on search text."""
        self._message_store.remove_all()

        if not search_text:
            # No search text - show all messages
            for message in self._all_messages:
                self._message_store.append(message)
        else:
            # Filter messages by from, subject, and preview
            for message in self._all_messages:
                if (
                    search_text in message.from_address.lower()
                    or search_text in message.subject.lower()
                    or search_text in message.preview.lower()
                ):
                    self._message_store.append(message)

        self._update_message_count()
        self._show_preview_placeholder()

    def _on_sort_changed(
        self,
        dropdown: Gtk.DropDown,
        param: GObject.ParamSpec,
    ) -> None:
        """Handle sort option change."""
        selected = dropdown.get_selected()
        sort_options = [
            "date",
            "from",
            "subject",
            "size",
            "favorite",
            "important",
        ]
        logger.info(f"Sort dropdown changed: selected index={selected}")
        if 0 <= selected < len(sort_options):
            column = sort_options[selected]
            self._sort_column = column
            logger.info(f"Sort by: {column}")
            # Sort the displayed messages
            self._sort_messages(column, self._sort_ascending)
            # Also sort the full list to maintain order when search is cleared
            self._sort_all_messages(column, self._sort_ascending)

    def _on_sort_direction_toggled(self, button: Gtk.Button) -> None:
        """Handle sort direction toggle button click."""
        # Toggle the sort direction
        self._sort_ascending = not self._sort_ascending

        # Update button icon and tooltip
        if self._sort_ascending:
            button.set_icon_name("pan-up-symbolic")
            button.set_tooltip_text(
                "Toggle sort direction (currently: oldest first)"
            )
        else:
            button.set_icon_name("pan-down-symbolic")
            button.set_tooltip_text(
                "Toggle sort direction (currently: newest first)"
            )

        logger.info(
            f"Sort direction toggled: ascending={self._sort_ascending}"
        )

        # Re-sort with the new direction
        self._sort_messages(self._sort_column, self._sort_ascending)
        self._sort_all_messages(self._sort_column, self._sort_ascending)

    def _on_message_check_toggled(
        self, check: Gtk.CheckButton, message_id: str
    ) -> None:
        """Handle individual message checkbox toggle."""
        if check.get_active():
            self._selected_messages.add(message_id)
        else:
            self._selected_messages.discard(message_id)
        self._update_message_count()
        self._update_select_all_state()

    def _on_select_all_toggled(self, button: Gtk.CheckButton) -> None:
        """Handle select all toggle."""
        active = button.get_active()
        logger.debug(f"Select all: {active}")

        if active:
            # Select all messages in current view
            for i in range(self._message_store.get_n_items()):
                item = self._message_store.get_item(i)
                self._selected_messages.add(item.message_id)
        else:
            # Deselect all
            self._selected_messages.clear()

        # Refresh the list to update checkboxes
        self._refresh_message_list()
        self._update_message_count()

    def _update_select_all_state(self) -> None:
        """Update select all checkbox state based on current selection."""
        # Select all checkbox removed - function kept for compatibility

    def _refresh_message_list(self) -> None:
        """Refresh the message list to update all item widgets."""
        # Trigger a refresh by emitting items-changed
        n_items = self._message_store.get_n_items()
        if n_items > 0:
            self._message_store.items_changed(0, n_items, n_items)

    def _on_delete_message(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle delete message action.

        If the message is not in Trash, it moves to Trash.
        If the message is already in Trash, it is permanently deleted.
        """
        if self._selected_message_id:
            storage = get_storage()

            # Check if we're currently viewing the Trash folder
            current_folder = self._get_selected_folder_name()
            is_in_trash = current_folder.lower() == "trash"

            if is_in_trash:
                # Permanently delete the message
                logger.info(
                    f"Permanently deleting message: {self._selected_message_id}"
                )
                storage.permanent_delete(self._selected_message_id)
            else:
                # Move to Trash instead of permanent delete
                logger.info(
                    f"Moving message to Trash: {self._selected_message_id}"
                )
                storage.move_to_trash(self._selected_message_id)

            # Remove the message from the current view
            for i in range(self._message_store.get_n_items()):
                item = self._message_store.get_item(i)
                if item.message_id == self._selected_message_id:
                    self._message_store.remove(i)
                    # Also remove from _all_messages
                    self._all_messages = [
                        m
                        for m in self._all_messages
                        if m.message_id != self._selected_message_id
                    ]
                    # Clear selection and preview
                    self._selected_message_id = None
                    self._show_preview_placeholder()
                    if is_in_trash:
                        logger.info(
                            f"Permanently deleted message at index {i}"
                        )
                    else:
                        logger.info(f"Moved message to Trash at index {i}")
                    break

            # Update message count
            self._update_message_count()

    def _get_selected_message(self) -> Optional[MessageItem]:
        """Get the currently selected message item."""
        if not self._selected_message_id:
            return None
        for i in range(self._message_store.get_n_items()):
            item = self._message_store.get_item(i)
            if item.message_id == self._selected_message_id:
                return item
        return None

    def _create_email_message_from_item(
        self, item: MessageItem
    ) -> EmailMessage:
        """Create an EmailMessage from a MessageItem for reply/forward."""
        return EmailMessage(
            message_id=item.message_id,
            subject=item.subject,
            sender=item.from_address,
            recipients=[],
            cc=[],
            date=item.date_string,
            body=item.preview,  # In real app, would fetch full body
        )

    def _open_composer(self, mode: ComposerMode) -> None:
        """Open the composer window with the specified mode."""
        message = self._get_selected_message()
        if not message:
            logger.warning("No message selected for compose action")
            return

        email_msg = self._create_email_message_from_item(message)
        composer = ComposerWindow(
            mode=mode,
            original_message=email_msg,
            application=self._application,
        )
        # Connect signals for draft saving and sending
        composer.connect("save-draft-requested", self._on_save_draft)
        composer.connect("send-requested", self._on_send_message)
        composer.present()
        logger.info(
            f"Opened composer in {mode.value} mode for message: {message.message_id}"
        )

    def _on_reply(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle reply action."""
        if self._selected_message_id:
            logger.info(f"Reply to message: {self._selected_message_id}")
            self._open_composer(ComposerMode.REPLY)

    def _on_reply_all(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle reply all action."""
        if self._selected_message_id:
            logger.info(f"Reply all to message: {self._selected_message_id}")
            self._open_composer(ComposerMode.REPLY_ALL)

    def _on_forward(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle forward action."""
        if self._selected_message_id:
            logger.info(f"Forward message: {self._selected_message_id}")
            self._open_composer(ComposerMode.FORWARD)

    def _on_mark_read(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle mark read action."""
        if self._selected_message_id:
            logger.info(f"Mark as read: {self._selected_message_id}")
            self._set_message_read(self._selected_message_id, True)

    def _on_mark_starred(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle mark starred action."""
        if self._selected_message_id:
            logger.info(f"Star message: {self._selected_message_id}")
            self._set_message_starred(self._selected_message_id, True)

    def _on_unstar_message(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle unstar message action."""
        if self._selected_message_id:
            logger.info(f"Unstar message: {self._selected_message_id}")
            self._set_message_starred(self._selected_message_id, False)

    def _on_mark_important(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle mark important action."""
        if self._selected_message_id:
            logger.info(f"Mark important: {self._selected_message_id}")
            self._set_message_important(self._selected_message_id, True)

    def _on_unmark_important(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle unmark important action."""
        if self._selected_message_id:
            logger.info(f"Unmark important: {self._selected_message_id}")
            self._set_message_important(self._selected_message_id, False)

    def _on_mark_unread(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle mark unread action."""
        if self._selected_message_id:
            logger.info(f"Mark unread: {self._selected_message_id}")
            self._set_message_read(self._selected_message_id, False)

    def _on_move_to_archive(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle move to archive action."""
        if self._selected_message_id:
            logger.info(f"Move to archive: {self._selected_message_id}")
            self._move_message_to_folder(self._selected_message_id, "Archive")

    def _on_move_to_spam(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle move to spam action."""
        if self._selected_message_id:
            logger.info(f"Move to spam: {self._selected_message_id}")
            self._move_message_to_folder(self._selected_message_id, "Spam")

    def _on_move_to_trash(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle move to trash action."""
        if self._selected_message_id:
            logger.info(f"Move to trash: {self._selected_message_id}")
            self._move_message_to_folder(self._selected_message_id, "Trash")
            # Clear preview after moving to trash
            self._selected_message_id = None
            self._show_preview_placeholder()

    def _on_move_to_folder_dialog(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Show folder selection dialog to move message to any folder.

        Opens a dialog showing all available folders including user-created
        custom folders, allowing the user to select the destination folder.
        """
        if not self._selected_message_id:
            return

        # Create folder selection dialog
        dialog = FolderSelectionDialog(
            parent=self,
            title="Move to Folder",
            exclude_folders=[],  # Show all folders
        )

        # Store message ID for use in response handler
        dialog._message_id = self._selected_message_id

        dialog.connect("response", self._on_move_folder_dialog_response)
        dialog.present()

    def _on_move_folder_dialog_response(
        self,
        dialog: "FolderSelectionDialog",
        response: str,
    ) -> None:
        """Handle folder selection dialog response for move action."""
        if response == "move":
            selected_folder = dialog.get_selected_folder()
            message_id = dialog._message_id

            if selected_folder and message_id:
                storage = get_storage()
                result = storage.move_to_folder(message_id, selected_folder)

                if result:
                    logger.info(
                        f"Moved message {message_id} to {selected_folder}"
                    )
                    # Remove from current view
                    self._remove_message_from_view(message_id)
                    self._selected_message_id = None
                    self._show_preview_placeholder()
                    self._update_message_count()
                else:
                    logger.warning(
                        f"Failed to move message {message_id} to {selected_folder}"
                    )

        dialog.destroy()

    def _on_restore_to_inbox(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Restore a message from Trash to its original folder (or Inbox).

        Uses the restore_from_trash method which automatically restores
        to the original folder, or Inbox if the original is not available.
        """
        if not self._selected_message_id:
            return

        storage = get_storage()
        result = storage.restore_from_trash(self._selected_message_id)

        if result:
            logger.info(
                f"Restored message {self._selected_message_id} from Trash"
            )
            # Remove from current view
            self._remove_message_from_view(self._selected_message_id)
            self._selected_message_id = None
            self._show_preview_placeholder()
            self._update_message_count()
        else:
            logger.warning(
                f"Failed to restore message {self._selected_message_id}"
            )

    def _on_restore_to_folder(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Show folder selection dialog to move message from Trash to chosen folder."""
        if not self._selected_message_id:
            return

        # Create folder selection dialog, excluding Trash
        dialog = FolderSelectionDialog(
            parent=self,
            title="Move to Folder",
            exclude_folders=["Trash"],
        )

        # Store message ID for use in response handler
        dialog._message_id = self._selected_message_id

        dialog.connect("response", self._on_folder_selection_response)
        dialog.present()

    def _on_folder_selection_response(
        self,
        dialog: FolderSelectionDialog,
        response: str,
    ) -> None:
        """Handle folder selection dialog response."""
        if response == "move":
            selected_folder = dialog.get_selected_folder()
            message_id = getattr(dialog, "_message_id", None)

            if selected_folder and message_id:
                storage = get_storage()
                result = storage.move_to_folder(message_id, selected_folder)

                if result:
                    logger.info(
                        f"Moved message {message_id} to {selected_folder}"
                    )
                    # Remove from current view
                    self._remove_message_from_view(message_id)
                    self._selected_message_id = None
                    self._show_preview_placeholder()
                    self._update_message_count()
                else:
                    logger.warning(
                        f"Failed to move message {message_id} to {selected_folder}"
                    )

        dialog.destroy()

    def _on_permanent_delete(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Permanently delete a message with confirmation dialog."""
        if not self._selected_message_id:
            return

        # Show confirmation dialog
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Delete Permanently?",
            body=(
                "This message will be permanently deleted. "
                "This action cannot be undone."
            ),
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete Permanently")
        dialog.set_response_appearance(
            "delete", Adw.ResponseAppearance.DESTRUCTIVE
        )
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        # Store message ID for use in response handler
        dialog._message_id = self._selected_message_id

        dialog.connect("response", self._on_permanent_delete_response)
        dialog.present()

    def _on_permanent_delete_response(
        self,
        dialog: Adw.MessageDialog,
        response: str,
    ) -> None:
        """Handle permanent delete confirmation response."""
        if response == "delete":
            message_id = getattr(dialog, "_message_id", None)
            if message_id:
                storage = get_storage()
                if storage.permanent_delete(message_id):
                    logger.info(f"Permanently deleted message: {message_id}")
                    # Remove from current view
                    self._remove_message_from_view(message_id)
                    self._selected_message_id = None
                    self._show_preview_placeholder()
                    self._update_message_count()
                else:
                    logger.warning(
                        f"Failed to permanently delete message: {message_id}"
                    )

        dialog.destroy()

    def _remove_message_from_view(self, message_id: str) -> None:
        """Remove a message from the current view by its ID.

        This is a helper method that removes a message from both the
        visible message store and the all_messages list.

        Args:
            message_id: The ID of the message to remove.
        """
        for i in range(self._message_store.get_n_items()):
            item = self._message_store.get_item(i)
            if item.message_id == message_id:
                self._message_store.remove(i)
                break
        # Also remove from _all_messages
        self._all_messages = [
            m for m in self._all_messages if m.message_id != message_id
        ]

    def _on_toggle_favorite(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle toggle favorite action - toggles starred state of current message."""
        if self._selected_message_id:
            # Find current state
            for i in range(self._message_store.get_n_items()):
                item = self._message_store.get_item(i)
                if item.message_id == self._selected_message_id:
                    new_state = not item.is_starred
                    logger.info(
                        f"Toggle favorite for {self._selected_message_id}: {new_state}"
                    )
                    self._set_message_starred(
                        self._selected_message_id, new_state
                    )
                    # Update preview pane button
                    if hasattr(self, "_preview_favorite_button"):
                        self._preview_favorite_button.handler_block_by_func(
                            self._on_preview_favorite_toggled
                        )
                        self._preview_favorite_button.set_active(new_state)
                        icon_name = (
                            "starred-symbolic"
                            if new_state
                            else "non-starred-symbolic"
                        )
                        self._preview_favorite_button.set_icon_name(icon_name)
                        self._preview_favorite_button.handler_unblock_by_func(
                            self._on_preview_favorite_toggled
                        )
                    break

    def _on_preview_favorite_toggled(self, button: Gtk.ToggleButton) -> None:
        """Handle favorite toggle button click in reading pane."""
        if not self._selected_message_id:
            return

        is_starred = button.get_active()
        logger.info(
            f"Preview favorite toggled for {self._selected_message_id}: {is_starred}"
        )

        # Update icon
        icon_name = (
            "starred-symbolic" if is_starred else "non-starred-symbolic"
        )
        button.set_icon_name(icon_name)

        # Update message in store and database
        self._set_message_starred(self._selected_message_id, is_starred)

    def _on_preview_important_toggled(self, button: Gtk.ToggleButton) -> None:
        """Handle important toggle button click in reading pane."""
        if not self._selected_message_id:
            return

        is_important = button.get_active()
        logger.info(
            f"Preview important toggled for {self._selected_message_id}: {is_important}"
        )

        # Update message in store and database
        self._set_message_important(self._selected_message_id, is_important)

    def _on_bulk_delete(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle bulk delete action - moves selected messages to Trash."""
        if not self._selected_messages:
            return

        logger.info(f"Bulk delete {len(self._selected_messages)} messages")
        message_ids = list(self._selected_messages)

        for message_id in message_ids:
            self._move_message_to_folder(message_id, "Trash")
            self._selected_messages.discard(message_id)

        # Also remove from _all_messages
        self._all_messages = [
            m for m in self._all_messages if m.message_id not in message_ids
        ]

        self._update_message_count()
        self._show_preview_placeholder()
        self._selected_message_id = None

    def _on_bulk_mark_read(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle bulk mark as read action."""
        if not self._selected_messages:
            return

        logger.info(f"Bulk mark read {len(self._selected_messages)} messages")
        for message_id in self._selected_messages:
            self._set_message_read(message_id, True)

    def _on_bulk_mark_unread(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle bulk mark as unread action."""
        if not self._selected_messages:
            return

        logger.info(
            f"Bulk mark unread {len(self._selected_messages)} messages"
        )
        for message_id in self._selected_messages:
            self._set_message_read(message_id, False)

    def _on_bulk_favorite(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle bulk add to favorites action."""
        if not self._selected_messages:
            return

        logger.info(f"Bulk favorite {len(self._selected_messages)} messages")
        for message_id in self._selected_messages:
            self._set_message_starred(message_id, True)

    def _on_bulk_unfavorite(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle bulk remove from favorites action."""
        if not self._selected_messages:
            return

        logger.info(f"Bulk unfavorite {len(self._selected_messages)} messages")
        for message_id in self._selected_messages:
            self._set_message_starred(message_id, False)

    def _on_message_right_click(
        self,
        gesture: Gtk.GestureClick,
        n_press: int,
        x: float,
        y: float,
    ) -> None:
        """Handle right-click on message list.

        Shows the appropriate context menu based on the current folder:
        - Trash folder: Shows restore and permanent delete options
        - Other folders: Shows regular message actions
        """
        # Position the context menu
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1

        # Choose the appropriate context menu based on current folder
        current_folder = self._get_selected_folder_name()
        if current_folder.lower() == "trash":
            self._trash_context_menu.set_pointing_to(rect)
            self._trash_context_menu.popup()
        else:
            self._message_context_menu.set_pointing_to(rect)
            self._message_context_menu.popup()

    def _on_message_left_click(
        self,
        gesture: Gtk.GestureClick,
        n_press: int,
        x: float,
        y: float,
    ) -> None:
        """
        Unified left-click handler for message list.

        Handles:
        - Single click: normal selection (updates _last_selected_index)
        - CTRL+Click: toggle selection of individual items
        - SHIFT+Click: range selection from last selected to current
        - Double-click (n_press == 2): open message pop-out window
        - Triple-click or more (n_press >= 3): ignored to prevent extra actions
        """
        # Prevent triple-click and higher from triggering any action
        if n_press >= 3:
            logger.debug(
                f"Ignoring click with n_press={n_press} (triple-click or more)"
            )
            return

        # Handle double-click for pop-out
        if n_press == 2:
            self._handle_double_click_popout()
            return

        # Single click handling with modifier keys
        self._handle_single_click_selection(gesture)

    def _handle_double_click_popout(self) -> None:
        """
        Handle double-click to open message in pop-out window or draft editor.

        This is a modular method that delegates to the appropriate handler:
        - For drafts: opens the composer in edit mode
        - For other messages: opens a read-only pop-out window

        This separation ensures draft editing logic is independent of message viewing.
        """
        if not self._selected_message_id:
            return

        # Find the selected message
        message_item = None
        for i in range(self._message_store.get_n_items()):
            item = self._message_store.get_item(i)
            if item.message_id == self._selected_message_id:
                message_item = item
                break

        if message_item:
            # Check if we're in the Drafts folder - open for editing if so
            if self._is_drafts_folder():
                self._open_draft_for_editing(message_item)
            else:
                self._open_message_popout(message_item)

    def _handle_single_click_selection(
        self, gesture: Gtk.GestureClick
    ) -> None:
        """
        Handle single-click with optional modifier keys for multi-selection.

        - No modifiers: regular selection, updates last selected index
        - CTRL+Click: toggle individual item selection
        - SHIFT+Click: select range from last selected to current

        This is a modular method for selection handling.
        """
        # Get current modifier state
        state = gesture.get_current_event_state()
        ctrl_pressed = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift_pressed = bool(state & Gdk.ModifierType.SHIFT_MASK)

        # Get the currently focused/selected item from the list view
        selection_model = self._message_list.get_model()
        if not isinstance(selection_model, Gtk.SingleSelection):
            return

        current_index = selection_model.get_selected()
        if current_index == Gtk.INVALID_LIST_POSITION:
            return

        current_item = self._message_store.get_item(current_index)
        if not current_item:
            return

        message_id = current_item.message_id

        if ctrl_pressed:
            # CTRL+Click: toggle selection of this item
            self._handle_ctrl_click_selection(message_id, current_index)
        elif shift_pressed:
            # SHIFT+Click: range selection
            self._handle_shift_click_selection(current_index)
        else:
            # Regular click: update last selected index for future SHIFT+Click
            self._last_selected_index = current_index
            logger.debug(f"Updated last_selected_index to {current_index}")

    def _handle_ctrl_click_selection(
        self, message_id: str, current_index: int
    ) -> None:
        """
        Handle CTRL+Click to toggle selection of individual item.

        Args:
            message_id: The message ID to toggle selection for.
            current_index: The index of the item in the message store.
        """
        if message_id in self._selected_messages:
            self._selected_messages.discard(message_id)
            logger.debug(f"CTRL+Click: deselected message {message_id}")
        else:
            self._selected_messages.add(message_id)
            logger.debug(f"CTRL+Click: selected message {message_id}")

        # Update last selected index for future SHIFT+Click
        self._last_selected_index = current_index

        # Refresh UI
        self._refresh_message_list()
        self._update_message_count()
        self._update_select_all_state()

    def _handle_shift_click_selection(self, current_index: int) -> None:
        """
        Handle SHIFT+Click to select a range of items.

        Selects all items from _last_selected_index to current_index (inclusive).

        Args:
            current_index: The current click target index.
        """
        # If no previous selection, start from first item
        start_index = (
            self._last_selected_index
            if self._last_selected_index is not None
            else 0
        )

        # Determine range (handle both directions)
        range_start = min(start_index, current_index)
        range_end = max(start_index, current_index)

        logger.debug(
            f"SHIFT+Click: selecting range [{range_start}, {range_end}]"
        )

        # Select all items in the range
        for i in range(range_start, range_end + 1):
            item = self._message_store.get_item(i)
            if item:
                self._selected_messages.add(item.message_id)

        # Refresh UI
        self._refresh_message_list()
        self._update_message_count()
        self._update_select_all_state()

    def _open_message_popout(self, message_item: "MessageItem") -> None:
        """Open a message in a separate pop-out window."""
        # Create a new window for the message
        popout_window = Adw.Window(
            title=message_item.subject or "(No subject)",
            default_width=700,
            default_height=600,
            transient_for=self,
        )

        # Main content box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Header bar
        header_bar = Adw.HeaderBar()
        header_bar.set_title_widget(
            Gtk.Label(
                label=message_item.subject or "(No subject)",
                ellipsize=Pango.EllipsizeMode.END,
            )
        )
        main_box.append(header_bar)

        # Message info box
        info_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            margin_start=16,
            margin_end=16,
            margin_top=12,
            margin_bottom=12,
        )

        from_label = Gtk.Label(
            label=f"From: {message_item.from_address}",
            xalign=0,
            css_classes=["heading"],
        )
        info_box.append(from_label)

        date_label = Gtk.Label(
            label=f"Date: {message_item.date_string}",
            xalign=0,
            css_classes=["dim-label"],
        )
        info_box.append(date_label)

        main_box.append(info_box)
        main_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Scrollable message body
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )

        body_label = Gtk.Label(
            label=message_item.preview or "(No content)",
            xalign=0,
            yalign=0,
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
            margin_start=16,
            margin_end=16,
            margin_top=12,
            margin_bottom=12,
            selectable=True,
        )
        scrolled.set_child(body_label)
        main_box.append(scrolled)

        popout_window.set_content(main_box)
        popout_window.present()
        logger.info(f"Opened message pop-out for: {message_item.message_id}")

    def _open_draft_for_editing(self, message_item: "MessageItem") -> None:
        """
        Open a draft message in the composer for editing.

        This is a dedicated method for draft editing, separate from the message
        pop-out viewer. It:
        - Opens the composer in EDIT mode
        - Pre-fills all fields from the draft
        - Tracks the draft message ID for update operations

        Args:
            message_item: The draft message item to edit.
        """
        logger.info(f"Opening draft for editing: {message_item.message_id}")

        # Get the full message data from storage
        storage = get_storage()
        db_message = storage.get_message(message_item.message_id)

        if not db_message:
            logger.error(
                f"Draft message not found in storage: {message_item.message_id}"
            )
            return

        # Create composer in EDIT mode with draft_message_id
        composer = ComposerWindow(
            mode=ComposerMode.EDIT,
            application=self._application,
            draft_message_id=message_item.message_id,
        )

        # Pre-fill the composer fields from the draft
        # Recipients
        to_addresses = db_message.get("to_addresses", [])
        if to_addresses:
            composer.set_to_recipients(to_addresses)

        cc_addresses = db_message.get("cc_addresses", [])
        if cc_addresses:
            composer.set_cc_recipients(cc_addresses)

        bcc_addresses = db_message.get("bcc_addresses", [])
        if bcc_addresses:
            composer.set_bcc_recipients(bcc_addresses)

        # Subject
        subject = db_message.get("subject", "")
        if subject:
            composer.set_subject(subject)

        # Body
        body = db_message.get("body_text", "")
        if body:
            composer.set_body(body)

        # Connect signals for draft saving and sending
        composer.connect("save-draft-requested", self._on_save_draft)
        composer.connect("send-requested", self._on_send_message)

        # Mark the draft as no longer modified (it was just loaded)
        composer._is_modified = False

        composer.present()
        logger.info(
            f"Opened composer for draft editing: {message_item.message_id}"
        )

    def _set_message_starred(self, message_id: str, starred: bool) -> None:
        """Set starred status for a message."""
        # Update database
        storage = get_storage()
        storage.update_message(message_id, {"is_starred": starred})

        for i in range(self._message_store.get_n_items()):
            item = self._message_store.get_item(i)
            if item.message_id == message_id:
                item.is_starred = starred
                # Force refresh
                self._message_store.items_changed(i, 1, 1)
                break

    def _set_message_important(self, message_id: str, important: bool) -> None:
        """Set important status for a message."""
        # Update database
        storage = get_storage()
        storage.update_message(message_id, {"is_important": important})

        for i in range(self._message_store.get_n_items()):
            item = self._message_store.get_item(i)
            if item.message_id == message_id:
                item.is_important = important
                # Force refresh
                self._message_store.items_changed(i, 1, 1)
                break

    def _set_message_read(self, message_id: str, is_read: bool) -> None:
        """Set read status for a message."""
        # Update database
        storage = get_storage()
        if is_read:
            storage.mark_as_read(message_id)
        else:
            storage.mark_as_unread(message_id)

        for i in range(self._message_store.get_n_items()):
            item = self._message_store.get_item(i)
            if item.message_id == message_id:
                item.is_read = is_read
                # Force refresh
                self._message_store.items_changed(i, 1, 1)
                break

    def _move_message_to_folder(self, message_id: str, folder: str) -> None:
        """Move a message to a folder."""
        # Update database
        storage = get_storage()
        storage.move_to_folder(message_id, folder)

        # Remove from current list
        for i in range(self._message_store.get_n_items()):
            item = self._message_store.get_item(i)
            if item.message_id == message_id:
                self._message_store.remove(i)
                logger.info(f"Moved message {message_id} to {folder}")
                break

    def _on_folder_right_click(
        self,
        gesture: Gtk.GestureClick,
        n_press: int,
        x: float,
        y: float,
    ) -> None:
        """Handle right-click on folder list."""
        # Position and show the context menu
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        self._folder_context_menu.set_pointing_to(rect)
        self._folder_context_menu.popup()

    def _on_folder_mark_all_read(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle mark all as read for current folder."""
        folder = self._get_selected_folder_name()
        logger.info(f"Mark all as read in folder: {folder}")
        for i in range(self._message_store.get_n_items()):
            item = self._message_store.get_item(i)
            item.is_read = True
        self._message_store.items_changed(
            0,
            self._message_store.get_n_items(),
            self._message_store.get_n_items(),
        )

    def _on_folder_refresh(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle folder refresh."""
        folder = self._get_selected_folder_name()
        logger.info(f"Refresh folder: {folder}")
        # In real app, would re-fetch from server

    def _on_folder_empty(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle empty folder (for Trash/Spam).

        Permanently deletes all messages in the Trash or Spam folder.
        """
        folder = self._get_selected_folder_name()
        if folder in ("Trash", "Spam"):
            logger.info(f"Empty folder: {folder}")

            # Permanently delete all messages in the folder from storage
            storage = get_storage()
            if folder == "Trash":
                deleted_count = storage.empty_trash()
                logger.info(
                    f"Emptied Trash: permanently deleted {deleted_count} messages"
                )
            else:
                # For Spam, get all spam messages and delete them
                spam_messages = storage.get_messages_by_folder("Spam")
                deleted_count = 0
                for msg in spam_messages:
                    if storage.permanent_delete(msg["id"]):
                        deleted_count += 1
                logger.info(
                    f"Emptied Spam: permanently deleted {deleted_count} messages"
                )

            # Clear the UI message list
            self._message_store.remove_all()
            self._all_messages.clear()
            self._update_message_count()
        else:
            logger.warning(f"Cannot empty folder: {folder}")

    def _get_selected_folder_name(self) -> str:
        """Get the name of the currently selected folder."""
        selection = self._folder_list.get_model()
        if isinstance(selection, Gtk.SingleSelection):
            idx = selection.get_selected()
            if idx < self._folder_store.get_n_items():
                item = self._folder_store.get_item(idx)
                return item.name
        return "Inbox"

    def _is_drafts_folder(self) -> bool:
        """
        Check if the currently selected folder is the Drafts folder.

        This is a modular helper method for determining draft-specific behavior.

        Returns:
            True if the current folder is Drafts, False otherwise.
        """
        folder_name = self._get_selected_folder_name()
        return folder_name.lower() == "drafts"

    # --- Folder Creation Methods ---

    def _on_new_folder_clicked(self, button: Gtk.Button) -> None:
        """
        Handle click on the new folder button.

        Opens the FolderCreationDialog to allow user to create a new custom folder.
        """
        from .folder_creation_dialog import show_folder_creation_dialog

        show_folder_creation_dialog(
            parent=self,
            on_folder_created=self._on_folder_created_callback,
        )

    def _on_folder_created_callback(self, folder: dict) -> None:
        """
        Handle successful folder creation from the dialog.

        This callback is invoked when a new folder is created via
        the FolderCreationDialog. It refreshes the sidebar folder list.

        Args:
            folder: The created folder dict from storage.
        """
        logger.info(f"Folder created callback: {folder.get('name')}")
        self._refresh_folder_list()

    def _refresh_folder_list(self) -> None:
        """
        Refresh the sidebar folder list from storage.

        This method reloads all folders from the local storage and
        updates the folder list UI. It preserves the currently selected
        folder if possible.

        This is a modular method that can be called independently
        whenever the folder list needs to be updated.
        """
        # Remember current selection
        current_selection_name: Optional[str] = None
        selection = self._folder_list.get_model()
        if isinstance(selection, Gtk.SingleSelection):
            idx = selection.get_selected()
            if (
                idx != Gtk.INVALID_LIST_POSITION
                and idx < self._folder_store.get_n_items()
            ):
                item = self._folder_store.get_item(idx)
                current_selection_name = item.name

        # Clear and reload folders
        self._folder_store.remove_all()

        storage = get_storage()
        db_folders = storage.get_folders()

        # Icon mapping for folder types
        icon_map = {
            "inbox": "mail-inbox-symbolic",
            "sent": "mail-send-symbolic",
            "drafts": "mail-drafts-symbolic",
            "trash": "user-trash-symbolic",
            "spam": "mail-mark-junk-symbolic",
            "archive": "folder-symbolic",
            "custom": "folder-symbolic",
        }

        new_selection_idx: Optional[int] = None

        for i, db_folder in enumerate(db_folders):
            folder_name = db_folder["name"]
            folder_type = db_folder.get("folder_type", "custom")
            icon = icon_map.get(folder_type, "folder-symbolic")

            folder_item = FolderItem(
                db_folder["id"],
                folder_name,
                icon,
                db_folder.get("unread_count", 0),
                folder_type,
            )
            self._folder_store.append(folder_item)

            # Track if this matches previous selection
            if (
                current_selection_name
                and folder_name == current_selection_name
            ):
                new_selection_idx = i

        # Restore selection if possible
        if new_selection_idx is not None and isinstance(
            selection, Gtk.SingleSelection
        ):
            selection.set_selected(new_selection_idx)

        # Adjust sidebar width for any new/renamed folders
        self._adjust_sidebar_width()

        logger.debug(f"Refreshed folder list with {len(db_folders)} folders")

    def _on_search_focus(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle search focus action."""
        self._search_entry.grab_focus()

    def _on_next_message(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle next message action."""
        selection = self._message_list.get_model()
        if isinstance(selection, Gtk.SingleSelection):
            current = selection.get_selected()
            if current < self._message_store.get_n_items() - 1:
                selection.set_selected(current + 1)

    def _on_previous_message(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle previous message action."""
        selection = self._message_list.get_model()
        if isinstance(selection, Gtk.SingleSelection):
            current = selection.get_selected()
            if current > 0:
                selection.set_selected(current - 1)

    # Public methods

    def save_window_state(self) -> None:
        """Save window state for restoration."""
        # TODO: Save to settings
        width = self.get_width()
        height = self.get_height()
        logger.debug(f"Saving window state: {width}x{height}")

    def show_compose_dialog(self) -> None:
        """Show the compose message dialog."""
        logger.info("Opening compose dialog")
        composer = ComposerWindow(
            mode=ComposerMode.NEW,
            application=self._application,
        )
        # Connect signals for draft saving
        composer.connect("save-draft-requested", self._on_save_draft)
        composer.connect("send-requested", self._on_send_message)
        composer.present()

    def _on_save_draft(self, composer: ComposerWindow) -> None:
        """
        Handle save draft request from composer.

        This method supports both creating new drafts and updating existing ones:
        - If composer has a draft_message_id, it updates the existing draft
        - Otherwise, it creates a new draft message

        This modular approach keeps draft save logic independent and reusable.
        """
        storage = get_storage()

        # Get message data from composer
        email_msg = composer.get_message_data()

        # Check if we're editing an existing draft
        draft_message_id = composer.get_draft_message_id()

        if draft_message_id:
            # Update existing draft
            logger.info(f"Updating existing draft: {draft_message_id}")
            update_data = {
                "to_addresses": email_msg.get("to", []),
                "cc_addresses": email_msg.get("cc", []),
                "subject": email_msg.get("subject") or "(No subject)",
                "body_text": email_msg.get("body") or "",
            }
            result = storage.update_message(draft_message_id, update_data)
            if result:
                logger.info(f"Draft updated successfully: {draft_message_id}")
                # Refresh the message list if we're viewing the Drafts folder
                if self._is_drafts_folder():
                    self._load_folder_messages("Drafts")
            else:
                logger.error(f"Failed to update draft: {draft_message_id}")
        else:
            # Create new draft
            logger.info("Creating new draft message")

            # Get draft folder
            drafts_folder = storage.get_folder_by_name("Drafts")
            if not drafts_folder:
                logger.error("Drafts folder not found")
                return

            storage.create_message(
                {
                    "folder_id": drafts_folder["id"],
                    "from_address": "me@unitmail.local",
                    "to_addresses": email_msg.get("to", []),
                    "cc_addresses": email_msg.get("cc", []),
                    "subject": email_msg.get("subject") or "(No subject)",
                    "body_text": email_msg.get("body") or "",
                    "is_read": True,
                    "status": "draft",
                }
            )
            logger.info("New draft saved successfully")

    def _on_send_message(self, composer: ComposerWindow) -> None:
        """
        Handle send message request from composer.

        If the composer was editing a draft, the draft is deleted upon sending.
        """
        logger.info("Send message requested (gateway not configured)")
        # For now, save to Sent folder since gateway isn't available
        storage = get_storage()
        sent_folder = storage.get_folder_by_name("Sent")
        if not sent_folder:
            logger.error("Sent folder not found")
            return

        email_msg = composer.get_message_data()

        # Check if we're sending an edited draft - delete the draft after
        # sending
        draft_message_id = composer.get_draft_message_id()

        storage.create_message(
            {
                "folder_id": sent_folder["id"],
                "from_address": "me@unitmail.local",
                "to_addresses": email_msg.get("to", []),
                "cc_addresses": email_msg.get("cc", []),
                "subject": email_msg.get("subject") or "(No subject)",
                "body_text": email_msg.get("body") or "",
                "is_read": True,
                "status": "sent",
                "sent_at": datetime.now().isoformat(),
            }
        )
        logger.info("Message saved to Sent (gateway not available)")

        # If we were editing a draft, delete it now that it's been sent
        if draft_message_id:
            storage.delete_message(draft_message_id)
            logger.info(f"Deleted draft after sending: {draft_message_id}")
            # Refresh the Drafts folder if we're viewing it
            if self._is_drafts_folder():
                self._load_folder_messages("Drafts")

        composer.close()

    def show_settings_dialog(self) -> None:
        """Show the settings dialog."""
        logger.info("Opening settings dialog")
        from .settings import SettingsWindow

        settings_window = SettingsWindow(parent=self)
        settings_window.present()

    def refresh_messages(self) -> None:
        """Refresh the message list from server."""
        logger.info("Refreshing messages")
        self._sync_label.set_label("Syncing...")
        # TODO: Implement actual refresh
        GLib.timeout_add(
            1000,
            lambda: self._sync_label.set_label(
                f"Last sync: {datetime.now().strftime('%H:%M')}"
            )
            or False,
        )

    def update_connection_status(
        self,
        connected: bool,
        server: Optional[str] = None,
    ) -> None:
        """
        Update the connection status display.

        Args:
            connected: Whether connected to server.
            server: Server name/address if connected.
        """
        if connected:
            self._connection_icon.set_from_icon_name(
                "network-transmit-receive-symbolic"
            )
            self._connection_label.set_label(
                f"Connected to {server or 'server'}"
            )
        else:
            self._connection_icon.set_from_icon_name(
                "network-offline-symbolic"
            )
            self._connection_label.set_label("Disconnected")

    def update_queue_depth(self, depth: int) -> None:
        """
        Update the queue depth display.

        Args:
            depth: Number of messages in queue.
        """
        self._queue_label.set_label(f"Queue: {depth}")

    def update_unread_count(self, count: int) -> None:
        """
        Update the unread count display.

        Args:
            count: Number of unread messages.
        """
        self._unread_label.set_label(f"Unread: {count}")
