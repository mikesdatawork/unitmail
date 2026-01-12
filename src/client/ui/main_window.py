"""
unitMail Main Window.

This module provides the main application window with a three-pane layout
for folder navigation, message list, and message preview.
"""

import logging
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import UUID

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Pango

logger = logging.getLogger(__name__)


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
        has_attachments: bool = False,
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
            has_attachments: Whether the message has attachments.
        """
        super().__init__()
        self._message_id = message_id
        self._from_address = from_address
        self._subject = subject
        self._preview = preview
        self._date = date
        self._is_read = is_read
        self._is_starred = is_starred
        self._has_attachments = has_attachments

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
        """Get formatted date string."""
        now = datetime.now()
        if self._date.date() == now.date():
            return self._date.strftime("%H:%M")
        elif self._date.year == now.year:
            return self._date.strftime("%b %d")
        else:
            return self._date.strftime("%Y-%m-%d")

    @GObject.Property(type=bool, default=False)
    def is_read(self) -> bool:
        """Get read status."""
        return self._is_read

    @is_read.setter
    def is_read(self, value: bool) -> None:
        """Set read status."""
        self._is_read = value

    @GObject.Property(type=bool, default=False)
    def is_starred(self) -> bool:
        """Get starred status."""
        return self._is_starred

    @is_starred.setter
    def is_starred(self, value: bool) -> None:
        """Set starred status."""
        self._is_starred = value

    @GObject.Property(type=bool, default=False)
    def has_attachments(self) -> bool:
        """Get attachments status."""
        return self._has_attachments


class MainWindow(Adw.ApplicationWindow):
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
    DEFAULT_LEFT_PANE_WIDTH = 200
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
            saved_density = getattr(settings.appearance, 'view_density', 'standard')

            theme_map = {
                "standard": ViewTheme.STANDARD,
                "minimal": ViewTheme.MINIMAL,
            }

            if saved_density in theme_map:
                target_theme = theme_map[saved_density]
                manager = get_view_theme_manager()

                # If saved density differs from current, apply it
                if manager.current_theme != target_theme:
                    manager.set_theme(target_theme)
                    logger.info(f"Applied saved view density: {saved_density}")
                else:
                    logger.info(f"View density already set to: {saved_density}")
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
            "search": self._on_search_focus,
            "next-message": self._on_next_message,
            "previous-message": self._on_previous_message,
            "move-to-archive": self._on_move_to_archive,
            "move-to-spam": self._on_move_to_spam,
            "move-to-trash": self._on_move_to_trash,
            "folder-mark-all-read": self._on_folder_mark_all_read,
            "folder-refresh": self._on_folder_refresh,
            "folder-empty": self._on_folder_empty,
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
            placeholder_text="Search messages...",
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
        outer_paned = Gtk.Paned(
            orientation=Gtk.Orientation.HORIZONTAL,
            shrink_start_child=False,
            shrink_end_child=False,
        )
        outer_paned.set_vexpand(True)

        # Left pane: Folder tree
        folder_pane = self._create_folder_pane()
        outer_paned.set_start_child(folder_pane)
        outer_paned.set_position(self.DEFAULT_LEFT_PANE_WIDTH)

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

        outer_paned.set_end_child(inner_paned)

        return outer_paned

    def _create_folder_pane(self) -> Gtk.Widget:
        """
        Create the folder tree pane.

        Returns:
            Folder pane widget.
        """
        # Container
        folder_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["folder-pane"],
        )

        # Header
        folder_header = Gtk.Label(
            label="Folders",
            xalign=0,
            css_classes=["heading"],
            margin_start=12,
            margin_top=8,
            margin_bottom=8,
        )
        folder_box.append(folder_header)

        # Scrolled window for folder list
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )

        # Create folder list view
        self._folder_list = self._create_folder_list()
        scrolled.set_child(self._folder_list)

        folder_box.append(scrolled)

        return folder_box

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

        # Toolbar with sort/filter options
        toolbar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
            margin_start=8,
            margin_end=8,
            margin_top=6,
            margin_bottom=6,
            css_classes=["toolbar"],
        )

        # Select all checkbox
        self._select_all_check = Gtk.CheckButton(
            tooltip_text="Select all messages",
        )
        self._select_all_check.connect("toggled", self._on_select_all_toggled)
        toolbar.append(self._select_all_check)

        # Message count label
        self._message_count_label = Gtk.Label(
            label="0 messages",
            xalign=0,
            hexpand=True,
            css_classes=["dim-label"],
        )
        toolbar.append(self._message_count_label)

        # Sort dropdown
        sort_items = ["Date", "From", "Subject", "Size"]
        sort_store = Gtk.StringList.new(sort_items)
        self._sort_dropdown = Gtk.DropDown(
            model=sort_store,
            tooltip_text="Sort messages by",
        )
        self._sort_dropdown.connect("notify::selected", self._on_sort_changed)
        toolbar.append(self._sort_dropdown)

        message_box.append(toolbar)

        # Separator
        message_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Column headers for minimal view (hidden by default)
        self._column_headers = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
            margin_start=8,
            margin_end=8,
            margin_top=4,
            margin_bottom=4,
            css_classes=["column-headers"],
        )
        self._column_headers.set_visible(False)

        # Checkbox spacer
        header_spacer = Gtk.Box()
        header_spacer.set_size_request(24, -1)
        self._column_headers.append(header_spacer)

        # Star spacer
        star_spacer = Gtk.Box()
        star_spacer.set_size_request(20, -1)
        self._column_headers.append(star_spacer)

        # Track current sort column and direction
        self._sort_column = "date"
        self._sort_ascending = False

        # Received column header (sortable)
        self._received_header_btn = Gtk.Button(
            css_classes=["flat", "column-header-btn"],
        )
        received_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        received_box.append(Gtk.Label(label="Received", xalign=0))
        self._received_sort_icon = Gtk.Image(icon_name="pan-down-symbolic")
        received_box.append(self._received_sort_icon)
        self._received_header_btn.set_child(received_box)
        self._received_header_btn.set_size_request(120, -1)
        self._received_header_btn.connect("clicked", self._on_column_header_clicked, "date")
        self._column_headers.append(self._received_header_btn)

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
        self._from_header_btn.set_size_request(250, -1)
        self._from_header_btn.connect("clicked", self._on_column_header_clicked, "from")
        self._column_headers.append(self._from_header_btn)

        # Subject column header (sortable)
        self._subject_header_btn = Gtk.Button(
            css_classes=["flat", "column-header-btn"],
            hexpand=True,
        )
        subject_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        subject_box.append(Gtk.Label(label="Subject", xalign=0, hexpand=True))
        self._subject_sort_icon = Gtk.Image(icon_name="pan-down-symbolic")
        self._subject_sort_icon.set_visible(False)
        subject_box.append(self._subject_sort_icon)
        self._subject_header_btn.set_child(subject_box)
        self._subject_header_btn.connect("clicked", self._on_column_header_clicked, "subject")
        self._column_headers.append(self._subject_header_btn)

        message_box.append(self._column_headers)

        # Scrolled window for message list
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )

        # Create message list view
        self._message_list = self._create_message_list()
        scrolled.set_child(self._message_list)

        message_box.append(scrolled)

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
        """Handle view theme change - refresh message list."""
        logger.info(f"View theme changed to: {theme_name}, refreshing message list")

        # Show/hide column headers for minimal view
        if hasattr(self, '_column_headers'):
            self._column_headers.set_visible(theme_name == "minimal")

        # Force complete rebind by temporarily replacing the model
        if hasattr(self, '_message_list') and self._message_list:
            selection_model = self._message_list.get_model()
            if selection_model and hasattr(selection_model, 'get_model'):
                # Get the current store
                store = selection_model.get_model()
                if store and store.get_n_items() > 0:
                    # Save current selection
                    selected_idx = selection_model.get_selected()

                    # Collect all items
                    items = []
                    for i in range(store.get_n_items()):
                        items.append(store.get_item(i))

                    # Clear and re-add to force complete rebind
                    store.remove_all()
                    for item in items:
                        store.append(item)

                    # Restore selection if valid
                    if selected_idx < len(items):
                        selection_model.set_selected(selected_idx)

    def _on_column_header_clicked(self, button: Gtk.Button, column: str) -> None:
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
        icon_name = "pan-up-symbolic" if self._sort_ascending else "pan-down-symbolic"
        if column == "date":
            self._received_sort_icon.set_from_icon_name(icon_name)
        elif column == "from":
            self._from_sort_icon.set_from_icon_name(icon_name)
        elif column == "subject":
            self._subject_sort_icon.set_from_icon_name(icon_name)

        # Sort the message store
        self._sort_messages(column, self._sort_ascending)

    def _sort_messages(self, column: str, ascending: bool) -> None:
        """Sort messages by the specified column."""
        if not hasattr(self, '_message_store') or not self._message_store:
            return

        # Get all items
        items = []
        for i in range(self._message_store.get_n_items()):
            items.append(self._message_store.get_item(i))

        # Sort based on column
        if column == "date":
            items.sort(key=lambda x: x._date, reverse=not ascending)
        elif column == "from":
            items.sort(key=lambda x: x.from_address.lower(), reverse=not ascending)
        elif column == "subject":
            items.sort(key=lambda x: (x.subject or "").lower(), reverse=not ascending)

        # Clear and repopulate store
        self._message_store.remove_all()
        for item in items:
            self._message_store.append(item)

        logger.info(f"Sorted {len(items)} messages by {column} ({'asc' if ascending else 'desc'})")

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

    def _setup_message_context_menu(self, list_view: Gtk.ListView) -> None:
        """Set up right-click context menu for messages."""
        # Create menu model
        menu = Gio.Menu()

        # Read/unread section
        read_section = Gio.Menu()
        read_section.append("Mark as Read", "win.mark-read")
        read_section.append("Mark as Unread", "win.mark-unread")
        menu.append_section(None, read_section)

        # Star section
        star_section = Gio.Menu()
        star_section.append("Star Message", "win.mark-starred")
        star_section.append("Remove Star", "win.unstar-message")
        menu.append_section(None, star_section)

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
        move_section.append_submenu("Move to...", move_submenu)
        menu.append_section(None, move_section)

        # Delete section
        delete_section = Gio.Menu()
        delete_section.append("Delete", "win.delete-message")
        menu.append_section(None, delete_section)

        # Create popover menu
        self._message_context_menu = Gtk.PopoverMenu(
            menu_model=menu,
            has_arrow=False,
        )
        self._message_context_menu.set_parent(list_view)

        # Add right-click gesture
        click_gesture = Gtk.GestureClick(button=3)  # Right click
        click_gesture.connect("pressed", self._on_message_right_click)
        list_view.add_controller(click_gesture)

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

        # Star button
        star_button = Gtk.ToggleButton(
            icon_name="starred-symbolic",
            css_classes=["flat", "star-button"],
            tooltip_text="Star message",
        )
        row_box.append(star_button)

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

        # Attachment icon
        attachment_icon = Gtk.Image(
            icon_name="mail-attachment-symbolic",
            css_classes=["dim-label"],
        )
        row_box.append(attachment_icon)

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

        check, star_button, content_box, attachment_icon = (
            children[0],
            children[1],
            children[2],
            children[3],
        )

        # Star button
        star_button.set_active(item.is_starred)

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

        # Check current view theme
        try:
            from .view_theme import ViewTheme, get_view_theme_manager
            theme_manager = get_view_theme_manager()
            current_theme = theme_manager.current_theme
        except ImportError:
            current_theme = None

        if current_theme == ViewTheme.MINIMAL:
            # Minimal view: columnar layout - date | from | subject
            # Format date with fixed width padding
            date_str = f"{item.date_string:<12}"
            from_str = item.from_address
            # Truncate from address if too long
            if len(from_str) > 35:
                from_str = from_str[:32] + "..."
            from_str = f"{from_str:<38}"
            subj_str = item.subject or "(No subject)"

            from_label.set_label(f"{date_str}{from_str}{subj_str}")
            date_label.set_visible(False)
            subject_label.set_visible(False)
            preview_label.set_visible(False)
            # Reduce row padding for minimal
            row_box.set_margin_top(2)
            row_box.set_margin_bottom(2)
        else:
            # Standard view: normal layout with preview
            from_label.set_label(item.from_address)
            date_label.set_label(item.date_string)
            date_label.set_visible(True)
            subject_label.set_label(item.subject or "(No subject)")
            subject_label.set_visible(True)
            preview_label.set_label(item.preview or "")
            preview_label.set_visible(True)
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

        # Apply starred styling (left border in minimal view via CSS)
        if item.is_starred:
            row_box.add_css_class("starred")
        else:
            row_box.remove_css_class("starred")

        # Show/hide attachment icon
        attachment_icon.set_visible(item.has_attachments)

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
        preview_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

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

        # Star button
        star_button = Gtk.Button(
            icon_name="starred-symbolic",
            tooltip_text="Star/Unstar message",
        )
        star_button.set_action_name("win.mark-starred")
        action_bar.append(star_button)

        action_bar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        delete_button = Gtk.Button(
            icon_name="user-trash-symbolic",
            tooltip_text="Delete (Delete)",
            css_classes=["destructive-action"],
        )
        delete_button.set_action_name("win.delete-message")
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

    def _load_sample_data(self) -> None:
        """Load sample data for development/testing."""
        # Sample folders
        folders = [
            FolderItem("inbox", "Inbox", "mail-inbox-symbolic", 5, "inbox"),
            FolderItem("sent", "Sent", "mail-send-symbolic", 0, "sent"),
            FolderItem("drafts", "Drafts", "mail-drafts-symbolic", 2, "drafts"),
            FolderItem("trash", "Trash", "user-trash-symbolic", 0, "trash"),
            FolderItem("spam", "Spam", "mail-mark-junk-symbolic", 1, "spam"),
            FolderItem("archive", "Archive", "folder-symbolic", 0, "archive"),
        ]

        for folder in folders:
            self._folder_store.append(folder)

        # Sample messages
        messages = [
            MessageItem(
                "msg1",
                "alice@example.com",
                "Meeting tomorrow",
                "Hi, just wanted to confirm our meeting tomorrow at 2pm...",
                datetime(2026, 1, 11, 14, 30),
                is_read=False,
                has_attachments=True,
            ),
            MessageItem(
                "msg2",
                "bob@example.com",
                "Re: Project update",
                "Thanks for the update. I've reviewed the changes and...",
                datetime(2026, 1, 11, 10, 15),
                is_read=True,
            ),
            MessageItem(
                "msg3",
                "newsletter@company.com",
                "Weekly Newsletter",
                "This week's highlights include new features and...",
                datetime(2026, 1, 10, 9, 0),
                is_read=False,
            ),
            MessageItem(
                "msg4",
                "support@service.com",
                "Your ticket has been updated",
                "We've made progress on your support ticket #12345...",
                datetime(2026, 1, 9, 16, 45),
                is_read=True,
                is_starred=True,
            ),
        ]

        for message in messages:
            self._message_store.append(message)

        self._update_message_count()

    def _update_message_count(self) -> None:
        """Update the message count label."""
        count = self._message_store.get_n_items()
        text = f"{count} message{'s' if count != 1 else ''}"
        self._message_count_label.set_label(text)

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
        """Load messages for a specific folder."""
        self._message_store.remove_all()

        # Sample data for each folder type
        folder_messages = {
            "Inbox": [
                MessageItem(
                    "msg1", "alice@example.com", "Meeting tomorrow",
                    "Hi, just wanted to confirm our meeting tomorrow at 2pm...",
                    datetime(2026, 1, 11, 14, 30), is_read=False, has_attachments=True,
                ),
                MessageItem(
                    "msg2", "bob@example.com", "Re: Project update",
                    "Thanks for the update. I've reviewed the changes and...",
                    datetime(2026, 1, 11, 10, 15), is_read=True,
                ),
                MessageItem(
                    "msg3", "newsletter@company.com", "Weekly Newsletter",
                    "This week's highlights include new features and...",
                    datetime(2026, 1, 10, 9, 0), is_read=False,
                ),
                MessageItem(
                    "msg4", "support@service.com", "Your ticket has been updated",
                    "We've made progress on your support ticket #12345...",
                    datetime(2026, 1, 9, 16, 45), is_read=True, is_starred=True,
                ),
            ],
            "Sent": [
                MessageItem(
                    "sent1", "me@example.com → alice@example.com", "Re: Meeting tomorrow",
                    "Yes, 2pm works for me. See you then!",
                    datetime(2026, 1, 11, 15, 0), is_read=True,
                ),
                MessageItem(
                    "sent2", "me@example.com → team@company.com", "Weekly Report",
                    "Here's my weekly progress report...",
                    datetime(2026, 1, 10, 17, 30), is_read=True,
                ),
            ],
            "Drafts": [
                MessageItem(
                    "draft1", "me@example.com", "[Draft] Proposal",
                    "I wanted to propose a new approach to...",
                    datetime(2026, 1, 11, 12, 0), is_read=True,
                ),
                MessageItem(
                    "draft2", "me@example.com", "[Draft] Follow-up",
                    "Following up on our discussion...",
                    datetime(2026, 1, 10, 14, 0), is_read=True,
                ),
            ],
            "Trash": [
                MessageItem(
                    "trash1", "spam@marketing.com", "Limited time offer!",
                    "Don't miss out on this amazing deal...",
                    datetime(2026, 1, 8, 10, 0), is_read=True,
                ),
                MessageItem(
                    "trash2", "old@contact.com", "Old message",
                    "This is an old message that was deleted...",
                    datetime(2026, 1, 5, 9, 0), is_read=True,
                ),
            ],
            "Spam": [
                MessageItem(
                    "spam1", "winner@lottery.fake", "You've won $1,000,000!!!",
                    "Congratulations! Click here to claim your prize...",
                    datetime(2026, 1, 11, 8, 0), is_read=False,
                ),
                MessageItem(
                    "spam2", "prince@nigeria.fake", "Urgent business proposal",
                    "I am a Nigerian prince seeking your assistance...",
                    datetime(2026, 1, 10, 6, 0), is_read=False,
                ),
            ],
            "Archive": [
                MessageItem(
                    "arch1", "hr@company.com", "Welcome to the team!",
                    "We're excited to have you join our team...",
                    datetime(2025, 6, 1, 9, 0), is_read=True,
                ),
                MessageItem(
                    "arch2", "project@client.com", "Project Complete",
                    "Thank you for completing the project successfully...",
                    datetime(2025, 8, 15, 14, 0), is_read=True, is_starred=True,
                ),
            ],
        }

        messages = folder_messages.get(folder_name, [])
        for message in messages:
            self._message_store.append(message)

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
        self._preview_to.set_label("me@example.com")  # TODO: Get actual recipient
        self._preview_date.set_label(message._date.strftime("%B %d, %Y at %H:%M"))

        # Set preview content
        buffer = self._preview_text.get_buffer()
        buffer.set_text(message.preview or "")

        # Mark as read
        if not message.is_read:
            message.is_read = True
            # TODO: Notify model of change

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Handle search text change."""
        text = entry.get_text()
        logger.debug(f"Search text: {text}")
        # TODO: Implement filtering

    def _on_search_activated(self, entry: Gtk.SearchEntry) -> None:
        """Handle search activation (Enter pressed)."""
        text = entry.get_text()
        logger.info(f"Search activated: {text}")
        # TODO: Implement search

    def _on_sort_changed(
        self,
        dropdown: Gtk.DropDown,
        param: GObject.ParamSpec,
    ) -> None:
        """Handle sort option change."""
        selected = dropdown.get_selected()
        sort_options = ["date", "from", "subject", "size"]
        if 0 <= selected < len(sort_options):
            logger.info(f"Sort by: {sort_options[selected]}")
            # TODO: Implement sorting

    def _on_select_all_toggled(self, button: Gtk.CheckButton) -> None:
        """Handle select all toggle."""
        active = button.get_active()
        logger.debug(f"Select all: {active}")
        # TODO: Implement select all

    def _on_delete_message(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle delete message action."""
        if self._selected_message_id:
            logger.info(f"Delete message: {self._selected_message_id}")
            # TODO: Implement delete

    def _on_reply(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle reply action."""
        if self._selected_message_id:
            logger.info(f"Reply to message: {self._selected_message_id}")
            # TODO: Open compose dialog with reply

    def _on_reply_all(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle reply all action."""
        if self._selected_message_id:
            logger.info(f"Reply all to message: {self._selected_message_id}")
            # TODO: Open compose dialog with reply all

    def _on_forward(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle forward action."""
        if self._selected_message_id:
            logger.info(f"Forward message: {self._selected_message_id}")
            # TODO: Open compose dialog with forward

    def _on_mark_read(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle mark read/unread action."""
        if self._selected_message_id:
            logger.info(f"Toggle read status: {self._selected_message_id}")
            # TODO: Implement mark read toggle

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

    def _on_message_right_click(
        self,
        gesture: Gtk.GestureClick,
        n_press: int,
        x: float,
        y: float,
    ) -> None:
        """Handle right-click on message list."""
        # Position and show the context menu
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        self._message_context_menu.set_pointing_to(rect)
        self._message_context_menu.popup()

    def _set_message_starred(self, message_id: str, starred: bool) -> None:
        """Set starred status for a message."""
        for i in range(self._message_store.get_n_items()):
            item = self._message_store.get_item(i)
            if item.message_id == message_id:
                item.is_starred = starred
                # Force refresh
                self._message_store.items_changed(i, 1, 1)
                break

    def _set_message_read(self, message_id: str, is_read: bool) -> None:
        """Set read status for a message."""
        for i in range(self._message_store.get_n_items()):
            item = self._message_store.get_item(i)
            if item.message_id == message_id:
                item.is_read = is_read
                # Force refresh
                self._message_store.items_changed(i, 1, 1)
                break

    def _move_message_to_folder(self, message_id: str, folder: str) -> None:
        """Move a message to a folder."""
        # Remove from current list (in real app, would update database)
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
        self._message_store.items_changed(0, self._message_store.get_n_items(), self._message_store.get_n_items())

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
        """Handle empty folder (for Trash/Spam)."""
        folder = self._get_selected_folder_name()
        if folder in ("Trash", "Spam"):
            logger.info(f"Empty folder: {folder}")
            self._message_store.remove_all()
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
        # TODO: Create and show compose dialog

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
            self._connection_icon.set_from_icon_name("network-transmit-receive-symbolic")
            self._connection_label.set_label(f"Connected to {server or 'server'}")
        else:
            self._connection_icon.set_from_icon_name("network-offline-symbolic")
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
