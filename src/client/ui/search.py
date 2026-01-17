"""
unitMail Search Dialog.

This module provides the SearchDialog class for advanced search functionality
with multiple filters, search history, and saved searches management.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GObject, Gtk, Pango

logger = logging.getLogger(__name__)


class FolderItem(GObject.Object):
    """GObject wrapper for folder selection."""

    __gtype_name__ = "SearchFolderItem"

    def __init__(self, folder_id: Optional[str], name: str) -> None:
        super().__init__()
        self._folder_id = folder_id
        self._name = name

    @GObject.Property(type=str)
    def folder_id(self) -> str:
        return self._folder_id or ""

    @GObject.Property(type=str)
    def name(self) -> str:
        return self._name


class SavedSearchItem(GObject.Object):
    """GObject wrapper for saved search display."""

    __gtype_name__ = "SavedSearchItem"

    def __init__(
        self,
        search_id: str,
        name: str,
        description: str,
        use_count: int = 0,
    ) -> None:
        super().__init__()
        self._search_id = search_id
        self._name = name
        self._description = description
        self._use_count = use_count

    @GObject.Property(type=str)
    def search_id(self) -> str:
        return self._search_id

    @GObject.Property(type=str)
    def name(self) -> str:
        return self._name

    @GObject.Property(type=str)
    def description(self) -> str:
        return self._description

    @GObject.Property(type=int)
    def use_count(self) -> int:
        return self._use_count


class SearchDialog(Adw.Window):
    """
    Advanced search dialog with multiple filter options.

    Provides UI for:
    - Full-text search query
    - From/To address filters
    - Subject and body text filters
    - Date range selection
    - Attachment, starred, unread filters
    - Folder selection
    - Search history display
    - Saved searches management

    Signals:
        search-requested: Emitted when user initiates search.
            Signature: (criteria: dict)
        search-saved: Emitted when user saves a search.
            Signature: (name: str, criteria: dict)
        closed: Emitted when dialog is closed.
            Signature: ()
    """

    __gtype_name__ = "UnitMailSearchDialog"

    __gsignals__ = {
        "search-requested": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "search-saved": (GObject.SignalFlags.RUN_FIRST, None, (str, object)),
        "saved-search-selected": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "closed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(
        self,
        parent: Optional[Gtk.Window] = None,
        folders: Optional[List[Dict[str, str]]] = None,
        saved_searches: Optional[List[Dict[str, Any]]] = None,
        search_history: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Initialize the search dialog.

        Args:
            parent: Parent window.
            folders: List of folders with 'id' and 'name' keys.
            saved_searches: List of saved searches to display.
            search_history: List of recent search history entries.
        """
        super().__init__(
            title="Advanced Search",
            default_width=600,
            default_height=700,
            modal=True,
            transient_for=parent,
        )

        self._folders = folders or []
        self._saved_searches = saved_searches or []
        self._search_history = search_history or []

        # Data stores
        self._folder_store: Gio.ListStore = Gio.ListStore.new(FolderItem)
        self._saved_search_store: Gio.ListStore = Gio.ListStore.new(SavedSearchItem)

        # Build UI
        self._build_ui()
        self._populate_data()
        self._apply_styles()

        # Connect close
        self.connect("close-request", self._on_close_request)

        logger.debug("SearchDialog initialized")

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar
        header_bar = Adw.HeaderBar()
        header_bar.add_css_class("flat")

        # Cancel button
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", self._on_cancel_clicked)
        header_bar.pack_start(cancel_button)

        # Search button
        self._search_button = Gtk.Button(
            label="Search",
            css_classes=["suggested-action"],
        )
        self._search_button.connect("clicked", self._on_search_clicked)
        header_bar.pack_end(self._search_button)

        main_box.append(header_bar)

        # Content with tabs
        self._stack = Adw.ViewStack()

        # Search filters page
        filters_page = self._create_filters_page()
        self._stack.add_titled(filters_page, "filters", "Search Filters")

        # Saved searches page
        saved_page = self._create_saved_searches_page()
        self._stack.add_titled(saved_page, "saved", "Saved Searches")

        # History page
        history_page = self._create_history_page()
        self._stack.add_titled(history_page, "history", "History")

        # View switcher
        switcher = Adw.ViewSwitcher(
            stack=self._stack,
            policy=Adw.ViewSwitcherPolicy.WIDE,
        )
        header_bar.set_title_widget(switcher)

        main_box.append(self._stack)

    def _create_filters_page(self) -> Gtk.Widget:
        """Create the search filters page."""
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )

        # Main content box
        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_start=16,
            margin_end=16,
            margin_top=16,
            margin_bottom=16,
        )

        # Query field
        query_group = Adw.PreferencesGroup(title="Search Query")
        self._query_entry = Adw.EntryRow(
            title="Contains text",
        )
        self._query_entry.connect("entry-activated", self._on_entry_activated)
        query_group.add(self._query_entry)
        content_box.append(query_group)

        # Address filters
        address_group = Adw.PreferencesGroup(title="Addresses")

        self._from_entry = Adw.EntryRow(
            title="From",
        )
        self._from_entry.connect("entry-activated", self._on_entry_activated)
        address_group.add(self._from_entry)

        self._to_entry = Adw.EntryRow(
            title="To",
        )
        self._to_entry.connect("entry-activated", self._on_entry_activated)
        address_group.add(self._to_entry)

        content_box.append(address_group)

        # Content filters
        content_group = Adw.PreferencesGroup(title="Content")

        self._subject_entry = Adw.EntryRow(
            title="Subject contains",
        )
        self._subject_entry.connect("entry-activated", self._on_entry_activated)
        content_group.add(self._subject_entry)

        self._body_entry = Adw.EntryRow(
            title="Body contains",
        )
        self._body_entry.connect("entry-activated", self._on_entry_activated)
        content_group.add(self._body_entry)

        content_box.append(content_group)

        # Date filters
        date_group = Adw.PreferencesGroup(title="Date Range")

        # Date from row
        date_from_row = Adw.ActionRow(
            title="From date",
            subtitle="Search messages after this date",
        )
        self._date_from_button = Gtk.Button(
            label="Select date",
            valign=Gtk.Align.CENTER,
        )
        self._date_from_button.connect("clicked", self._on_date_from_clicked)
        self._date_from_clear = Gtk.Button(
            icon_name="edit-clear-symbolic",
            valign=Gtk.Align.CENTER,
            css_classes=["flat", "circular"],
            tooltip_text="Clear date",
            visible=False,
        )
        self._date_from_clear.connect("clicked", self._on_date_from_clear)
        date_from_row.add_suffix(self._date_from_clear)
        date_from_row.add_suffix(self._date_from_button)
        date_group.add(date_from_row)

        # Date to row
        date_to_row = Adw.ActionRow(
            title="To date",
            subtitle="Search messages before this date",
        )
        self._date_to_button = Gtk.Button(
            label="Select date",
            valign=Gtk.Align.CENTER,
        )
        self._date_to_button.connect("clicked", self._on_date_to_clicked)
        self._date_to_clear = Gtk.Button(
            icon_name="edit-clear-symbolic",
            valign=Gtk.Align.CENTER,
            css_classes=["flat", "circular"],
            tooltip_text="Clear date",
            visible=False,
        )
        self._date_to_clear.connect("clicked", self._on_date_to_clear)
        date_to_row.add_suffix(self._date_to_clear)
        date_to_row.add_suffix(self._date_to_button)
        date_group.add(date_to_row)

        # Quick date presets
        presets_row = Adw.ActionRow(
            title="Quick presets",
        )
        presets_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            valign=Gtk.Align.CENTER,
        )
        for label, days in [("Today", 0), ("Week", 7), ("Month", 30), ("Year", 365)]:
            btn = Gtk.Button(
                label=label,
                css_classes=["flat"],
            )
            btn.connect("clicked", self._on_date_preset_clicked, days)
            presets_box.append(btn)
        presets_row.add_suffix(presets_box)
        date_group.add(presets_row)

        content_box.append(date_group)

        # Status filters
        status_group = Adw.PreferencesGroup(title="Status")

        # Has attachments
        self._attachments_row = Adw.SwitchRow(
            title="Has attachments",
            subtitle="Only messages with attachments",
        )
        status_group.add(self._attachments_row)

        # Is favorite
        self._starred_row = Adw.SwitchRow(
            title="Favorites",
            subtitle="Only favorite messages",
        )
        status_group.add(self._starred_row)

        # Is unread
        self._unread_row = Adw.SwitchRow(
            title="Unread",
            subtitle="Only unread messages",
        )
        status_group.add(self._unread_row)

        # Is encrypted
        self._encrypted_row = Adw.SwitchRow(
            title="Encrypted",
            subtitle="Only encrypted messages",
        )
        status_group.add(self._encrypted_row)

        content_box.append(status_group)

        # Folder selection
        folder_group = Adw.PreferencesGroup(title="Folder")

        self._folder_row = Adw.ComboRow(
            title="Search in folder",
            subtitle="Leave empty to search all folders",
        )

        # Setup folder dropdown
        folder_factory = Gtk.SignalListItemFactory()
        folder_factory.connect("setup", self._on_folder_item_setup)
        folder_factory.connect("bind", self._on_folder_item_bind)
        self._folder_row.set_factory(folder_factory)
        self._folder_row.set_model(self._folder_store)

        folder_group.add(self._folder_row)
        content_box.append(folder_group)

        # Save search section
        save_group = Adw.PreferencesGroup(title="Save Search")

        save_row = Adw.ActionRow(
            title="Save as",
            subtitle="Save these filters for later use",
        )
        self._save_name_entry = Gtk.Entry(
            placeholder_text="Search name",
            valign=Gtk.Align.CENTER,
            width_chars=20,
        )
        save_row.add_suffix(self._save_name_entry)

        self._save_button = Gtk.Button(
            label="Save",
            valign=Gtk.Align.CENTER,
            css_classes=["suggested-action"],
        )
        self._save_button.connect("clicked", self._on_save_clicked)
        save_row.add_suffix(self._save_button)

        save_group.add(save_row)
        content_box.append(save_group)

        scrolled.set_child(content_box)
        return scrolled

    def _on_folder_item_setup(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Set up folder dropdown item."""
        label = Gtk.Label(xalign=0)
        list_item.set_child(label)

    def _on_folder_item_bind(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Bind data to folder dropdown item."""
        item: FolderItem = list_item.get_item()
        label: Gtk.Label = list_item.get_child()
        label.set_label(item.name)

    def _create_saved_searches_page(self) -> Gtk.Widget:
        """Create the saved searches page."""
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )

        # Toolbar
        toolbar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_start=16,
            margin_end=16,
            margin_top=12,
            margin_bottom=12,
        )

        label = Gtk.Label(
            label="Your saved searches",
            xalign=0,
            hexpand=True,
            css_classes=["heading"],
        )
        toolbar.append(label)

        delete_all_button = Gtk.Button(
            label="Delete All",
            css_classes=["destructive-action"],
        )
        delete_all_button.connect("clicked", self._on_delete_all_saved_clicked)
        toolbar.append(delete_all_button)

        box.append(toolbar)
        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Saved searches list
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )

        selection_model = Gtk.SingleSelection(model=self._saved_search_store)
        selection_model.connect("selection-changed", self._on_saved_search_selected)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_saved_search_item_setup)
        factory.connect("bind", self._on_saved_search_item_bind)

        self._saved_list = Gtk.ListView(
            model=selection_model,
            factory=factory,
        )

        scrolled.set_child(self._saved_list)
        box.append(scrolled)

        # Empty state
        self._saved_empty = Adw.StatusPage(
            icon_name="edit-find-symbolic",
            title="No Saved Searches",
            description="Save your searches from the filters tab",
            visible=False,
        )
        box.append(self._saved_empty)

        return box

    def _on_saved_search_item_setup(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Set up saved search list item."""
        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_start=16,
            margin_end=16,
            margin_top=12,
            margin_bottom=12,
        )

        icon = Gtk.Image(
            icon_name="folder-saved-search-symbolic",
            icon_size=Gtk.IconSize.LARGE,
        )
        box.append(icon)

        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            hexpand=True,
        )

        name_label = Gtk.Label(
            xalign=0,
            css_classes=["heading"],
        )
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        content_box.append(name_label)

        desc_label = Gtk.Label(
            xalign=0,
            css_classes=["dim-label"],
        )
        desc_label.set_ellipsize(Pango.EllipsizeMode.END)
        content_box.append(desc_label)

        box.append(content_box)

        delete_button = Gtk.Button(
            icon_name="edit-delete-symbolic",
            css_classes=["flat", "circular", "destructive-action"],
            tooltip_text="Delete saved search",
            valign=Gtk.Align.CENTER,
        )
        box.append(delete_button)

        list_item.set_child(box)

    def _on_saved_search_item_bind(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Bind data to saved search list item."""
        item: SavedSearchItem = list_item.get_item()
        box: Gtk.Box = list_item.get_child()

        children = []
        child = box.get_first_child()
        while child:
            children.append(child)
            child = child.get_next_sibling()

        _icon, content_box, delete_button = children[0], children[1], children[2]  # noqa: F841

        content_children = []
        child = content_box.get_first_child()
        while child:
            content_children.append(child)
            child = child.get_next_sibling()

        name_label, desc_label = content_children

        name_label.set_label(item.name)
        desc_label.set_label(item.description)

        delete_button.connect(
            "clicked",
            lambda btn: self._on_delete_saved_search(item.search_id),
        )

    def _create_history_page(self) -> Gtk.Widget:
        """Create the search history page."""
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )

        # Toolbar
        toolbar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_start=16,
            margin_end=16,
            margin_top=12,
            margin_bottom=12,
        )

        label = Gtk.Label(
            label="Recent searches",
            xalign=0,
            hexpand=True,
            css_classes=["heading"],
        )
        toolbar.append(label)

        clear_button = Gtk.Button(
            label="Clear History",
            css_classes=["destructive-action"],
        )
        clear_button.connect("clicked", self._on_clear_history_clicked)
        toolbar.append(clear_button)

        box.append(toolbar)
        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # History list
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )

        self._history_list = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.SINGLE,
            css_classes=["boxed-list"],
        )
        self._history_list.connect("row-activated", self._on_history_row_activated)

        scrolled.set_child(self._history_list)
        box.append(scrolled)

        # Empty state
        self._history_empty = Adw.StatusPage(
            icon_name="document-open-recent-symbolic",
            title="No Search History",
            description="Your recent searches will appear here",
            visible=False,
        )
        box.append(self._history_empty)

        return box

    def _populate_data(self) -> None:
        """Populate data stores with provided data."""
        # Folders
        self._folder_store.append(FolderItem(None, "All Folders"))
        for folder in self._folders:
            self._folder_store.append(
                FolderItem(folder.get("id"), folder.get("name", "Unknown"))
            )

        # Saved searches
        for saved in self._saved_searches:
            self._saved_search_store.append(
                SavedSearchItem(
                    search_id=saved.get("id", ""),
                    name=saved.get("name", "Unnamed"),
                    description=saved.get("description", ""),
                    use_count=saved.get("use_count", 0),
                )
            )

        # Update empty states
        self._saved_empty.set_visible(len(self._saved_searches) == 0)

        # History
        for entry in self._search_history:
            self._add_history_row(entry)

        self._history_empty.set_visible(len(self._search_history) == 0)

    def _add_history_row(self, entry: Dict[str, Any]) -> None:
        """Add a row to the history list."""
        row = Adw.ActionRow(
            title=entry.get("query", "Unknown search"),
            subtitle=f"{entry.get('result_count', 0)} results",
        )

        # Timestamp
        timestamp = entry.get("timestamp")
        if timestamp:
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            time_label = Gtk.Label(
                label=self._format_relative_time(timestamp),
                css_classes=["dim-label"],
                valign=Gtk.Align.CENTER,
            )
            row.add_suffix(time_label)

        # Use button
        use_button = Gtk.Button(
            icon_name="go-next-symbolic",
            css_classes=["flat", "circular"],
            tooltip_text="Use this search",
            valign=Gtk.Align.CENTER,
        )
        use_button.connect(
            "clicked",
            lambda btn: self._on_use_history_entry(entry),
        )
        row.add_suffix(use_button)

        self._history_list.append(row)

    def _format_relative_time(self, dt: datetime) -> str:
        """Format a datetime as relative time."""
        now = datetime.now()
        diff = now - dt

        if diff < timedelta(minutes=1):
            return "Just now"
        elif diff < timedelta(hours=1):
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes}m ago"
        elif diff < timedelta(days=1):
            hours = int(diff.total_seconds() / 3600)
            return f"{hours}h ago"
        elif diff < timedelta(days=7):
            days = diff.days
            return f"{days}d ago"
        else:
            return dt.strftime("%b %d")

    def _apply_styles(self) -> None:
        """Apply CSS styles."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(
            b"""
            .date-button {
                min-width: 120px;
            }
        """
        )

        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    # Event Handlers

    def _on_close_request(self, window: Gtk.Window) -> bool:
        """Handle window close."""
        self.emit("closed")
        return False

    def _on_cancel_clicked(self, button: Gtk.Button) -> None:
        """Handle cancel button click."""
        self.close()

    def _on_search_clicked(self, button: Gtk.Button) -> None:
        """Handle search button click."""
        criteria = self.get_search_criteria()
        self.emit("search-requested", criteria)
        self.close()

    def _on_entry_activated(self, entry: Adw.EntryRow) -> None:
        """Handle Enter key in entry rows."""
        self._on_search_clicked(self._search_button)

    def _on_date_from_clicked(self, button: Gtk.Button) -> None:
        """Show date picker for from date."""
        self._show_date_picker(button, self._set_date_from)

    def _on_date_to_clicked(self, button: Gtk.Button) -> None:
        """Show date picker for to date."""
        self._show_date_picker(button, self._set_date_to)

    def _show_date_picker(
        self,
        button: Gtk.Button,
        callback: Callable[[datetime], None],
    ) -> None:
        """Show a date picker popover."""
        popover = Gtk.Popover()
        popover.set_parent(button)

        calendar = Gtk.Calendar()
        calendar.connect(
            "day-selected",
            lambda cal: self._on_calendar_date_selected(cal, popover, callback),
        )

        popover.set_child(calendar)
        popover.popup()

    def _on_calendar_date_selected(
        self,
        calendar: Gtk.Calendar,
        popover: Gtk.Popover,
        callback: Callable[[datetime], None],
    ) -> None:
        """Handle calendar date selection."""
        date = calendar.get_date()
        selected_date = datetime(date.get_year(), date.get_month(), date.get_day_of_month())
        callback(selected_date)
        popover.popdown()

    def _set_date_from(self, date: datetime) -> None:
        """Set the from date."""
        self._date_from = date
        self._date_from_button.set_label(date.strftime("%Y-%m-%d"))
        self._date_from_clear.set_visible(True)

    def _set_date_to(self, date: datetime) -> None:
        """Set the to date."""
        self._date_to = date
        self._date_to_button.set_label(date.strftime("%Y-%m-%d"))
        self._date_to_clear.set_visible(True)

    def _on_date_from_clear(self, button: Gtk.Button) -> None:
        """Clear from date."""
        self._date_from = None
        self._date_from_button.set_label("Select date")
        self._date_from_clear.set_visible(False)

    def _on_date_to_clear(self, button: Gtk.Button) -> None:
        """Clear to date."""
        self._date_to = None
        self._date_to_button.set_label("Select date")
        self._date_to_clear.set_visible(False)

    def _on_date_preset_clicked(self, button: Gtk.Button, days: int) -> None:
        """Handle date preset button click."""
        now = datetime.now()
        if days == 0:
            # Today
            self._set_date_from(now.replace(hour=0, minute=0, second=0, microsecond=0))
            self._set_date_to(now)
        else:
            # Past N days
            self._set_date_from(now - timedelta(days=days))
            self._set_date_to(now)

    def _on_save_clicked(self, button: Gtk.Button) -> None:
        """Handle save search button click."""
        name = self._save_name_entry.get_text().strip()
        if not name:
            # Show error or focus on entry
            self._save_name_entry.grab_focus()
            return

        criteria = self.get_search_criteria()
        self.emit("search-saved", name, criteria)

        # Add to saved searches display
        self._saved_search_store.append(
            SavedSearchItem(
                search_id="",  # Will be assigned by service
                name=name,
                description=self._get_criteria_description(criteria),
            )
        )
        self._saved_empty.set_visible(False)
        self._save_name_entry.set_text("")

        # Show toast
        toast = Adw.Toast(
            title=f"Search '{name}' saved",
            timeout=2,
        )
        self.get_root().add_toast(toast) if hasattr(self.get_root(), 'add_toast') else None

    def _on_saved_search_selected(
        self,
        selection: Gtk.SingleSelection,
        position: int,
        n_items: int,
    ) -> None:
        """Handle saved search selection."""
        selected = selection.get_selected_item()
        if selected:
            self.emit("saved-search-selected", selected.search_id)
            self.close()

    def _on_delete_saved_search(self, search_id: str) -> None:
        """Handle delete saved search."""
        for i in range(self._saved_search_store.get_n_items()):
            item = self._saved_search_store.get_item(i)
            if item and item.search_id == search_id:
                self._saved_search_store.remove(i)
                break

        self._saved_empty.set_visible(
            self._saved_search_store.get_n_items() == 0
        )

    def _on_delete_all_saved_clicked(self, button: Gtk.Button) -> None:
        """Handle delete all saved searches."""
        self._saved_search_store.remove_all()
        self._saved_empty.set_visible(True)

    def _on_clear_history_clicked(self, button: Gtk.Button) -> None:
        """Handle clear history button click."""
        # Remove all rows from history list
        while True:
            row = self._history_list.get_row_at_index(0)
            if row is None:
                break
            self._history_list.remove(row)

        self._history_empty.set_visible(True)

    def _on_history_row_activated(
        self,
        list_box: Gtk.ListBox,
        row: Gtk.ListBoxRow,
    ) -> None:
        """Handle history row activation."""
        # The row data was stored during creation

    def _on_use_history_entry(self, entry: Dict[str, Any]) -> None:
        """Use a history entry to populate filters."""
        criteria = entry.get("criteria", {})
        self.set_search_criteria(criteria)
        self._stack.set_visible_child_name("filters")

    # Public Methods

    def get_search_criteria(self) -> Dict[str, Any]:
        """
        Get the current search criteria from the form.

        Returns:
            Dictionary of search criteria.
        """
        # Get selected folder
        folder_id = None
        selected = self._folder_row.get_selected()
        if selected > 0:  # 0 is "All Folders"
            item = self._folder_store.get_item(selected)
            if item:
                folder_id = item.folder_id

        # Build criteria dictionary
        criteria = {
            "query": self._query_entry.get_text().strip() or None,
            "from_address": self._from_entry.get_text().strip() or None,
            "to_address": self._to_entry.get_text().strip() or None,
            "subject_contains": self._subject_entry.get_text().strip() or None,
            "body_contains": self._body_entry.get_text().strip() or None,
            "date_from": getattr(self, "_date_from", None),
            "date_to": getattr(self, "_date_to", None),
            "has_attachments": self._attachments_row.get_active() or None,
            "is_starred": self._starred_row.get_active() or None,
            "is_unread": self._unread_row.get_active() or None,
            "is_encrypted": self._encrypted_row.get_active() or None,
            "folder_id": folder_id,
        }

        # Remove None values for cleaner output
        return {k: v for k, v in criteria.items() if v is not None}

    def set_search_criteria(self, criteria: Dict[str, Any]) -> None:
        """
        Set the search criteria form values.

        Args:
            criteria: Dictionary of search criteria.
        """
        self._query_entry.set_text(criteria.get("query", ""))
        self._from_entry.set_text(criteria.get("from_address", ""))
        self._to_entry.set_text(criteria.get("to_address", ""))
        self._subject_entry.set_text(criteria.get("subject_contains", ""))
        self._body_entry.set_text(criteria.get("body_contains", ""))

        # Date fields
        if criteria.get("date_from"):
            date_from = criteria["date_from"]
            if isinstance(date_from, str):
                date_from = datetime.fromisoformat(date_from)
            self._set_date_from(date_from)
        else:
            self._on_date_from_clear(self._date_from_clear)

        if criteria.get("date_to"):
            date_to = criteria["date_to"]
            if isinstance(date_to, str):
                date_to = datetime.fromisoformat(date_to)
            self._set_date_to(date_to)
        else:
            self._on_date_to_clear(self._date_to_clear)

        # Status switches
        self._attachments_row.set_active(criteria.get("has_attachments", False))
        self._starred_row.set_active(criteria.get("is_starred", False))
        self._unread_row.set_active(criteria.get("is_unread", False))
        self._encrypted_row.set_active(criteria.get("is_encrypted", False))

        # Folder selection
        folder_id = criteria.get("folder_id")
        if folder_id:
            for i in range(self._folder_store.get_n_items()):
                item = self._folder_store.get_item(i)
                if item and item.folder_id == folder_id:
                    self._folder_row.set_selected(i)
                    break
        else:
            self._folder_row.set_selected(0)

    def clear_form(self) -> None:
        """Clear all form fields."""
        self._query_entry.set_text("")
        self._from_entry.set_text("")
        self._to_entry.set_text("")
        self._subject_entry.set_text("")
        self._body_entry.set_text("")
        self._on_date_from_clear(self._date_from_clear)
        self._on_date_to_clear(self._date_to_clear)
        self._attachments_row.set_active(False)
        self._starred_row.set_active(False)
        self._unread_row.set_active(False)
        self._encrypted_row.set_active(False)
        self._folder_row.set_selected(0)

    def set_folders(self, folders: List[Dict[str, str]]) -> None:
        """
        Update the available folders.

        Args:
            folders: List of folders with 'id' and 'name' keys.
        """
        self._folder_store.remove_all()
        self._folder_store.append(FolderItem(None, "All Folders"))
        for folder in folders:
            self._folder_store.append(
                FolderItem(folder.get("id"), folder.get("name", "Unknown"))
            )

    def add_saved_search(
        self,
        search_id: str,
        name: str,
        description: str,
    ) -> None:
        """
        Add a saved search to the list.

        Args:
            search_id: Unique search ID.
            name: Display name.
            description: Search description.
        """
        self._saved_search_store.append(
            SavedSearchItem(
                search_id=search_id,
                name=name,
                description=description,
            )
        )
        self._saved_empty.set_visible(False)

    def add_history_entry(self, entry: Dict[str, Any]) -> None:
        """
        Add an entry to the search history.

        Args:
            entry: History entry with 'query', 'result_count', etc.
        """
        self._add_history_row(entry)
        self._history_empty.set_visible(False)

    def _get_criteria_description(self, criteria: Dict[str, Any]) -> str:
        """Generate a description string from criteria."""
        parts = []

        if criteria.get("query"):
            parts.append(f'"{criteria["query"]}"')
        if criteria.get("from_address"):
            parts.append(f"from:{criteria['from_address']}")
        if criteria.get("to_address"):
            parts.append(f"to:{criteria['to_address']}")
        if criteria.get("date_from") or criteria.get("date_to"):
            date_from = criteria.get("date_from")
            date_to = criteria.get("date_to")
            if isinstance(date_from, datetime):
                date_from = date_from.strftime("%Y-%m-%d")
            if isinstance(date_to, datetime):
                date_to = date_to.strftime("%Y-%m-%d")
            if date_from and date_to:
                parts.append(f"date:{date_from} to {date_to}")
            elif date_from:
                parts.append(f"after:{date_from}")
            elif date_to:
                parts.append(f"before:{date_to}")
        if criteria.get("has_attachments"):
            parts.append("has:attachment")
        if criteria.get("is_starred"):
            parts.append("is:favorite")
        if criteria.get("is_unread"):
            parts.append("is:unread")

        return " ".join(parts) if parts else "All messages"


class SearchPopover(Gtk.Popover):
    """
    A compact search popover for quick access to search functionality.

    Can be attached to a search button for a lightweight search experience.
    """

    __gtype_name__ = "UnitMailSearchPopover"

    __gsignals__ = {
        "search-activated": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "advanced-search-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(
        self,
        suggestions_provider: Optional[Callable[[str], List[str]]] = None,
    ) -> None:
        """
        Initialize the search popover.

        Args:
            suggestions_provider: Callable that returns suggestions.
        """
        super().__init__(
            has_arrow=True,
            css_classes=["search-popover"],
        )

        self._suggestions_provider = suggestions_provider
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the popover UI."""
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_start=12,
            margin_end=12,
            margin_top=12,
            margin_bottom=12,
        )

        # Search entry
        self._entry = Gtk.SearchEntry(
            placeholder_text="Search messages...",
            width_chars=30,
        )
        self._entry.connect("activate", self._on_search_activated)
        self._entry.connect("changed", self._on_search_changed)
        box.append(self._entry)

        # Quick filters
        filters_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4,
            homogeneous=True,
        )

        self._unread_btn = Gtk.ToggleButton(
            label="Unread",
            css_classes=["flat"],
        )
        filters_box.append(self._unread_btn)

        self._starred_btn = Gtk.ToggleButton(
            label="Favorites",
            css_classes=["flat"],
        )
        filters_box.append(self._starred_btn)

        self._attachments_btn = Gtk.ToggleButton(
            label="Attachments",
            css_classes=["flat"],
        )
        filters_box.append(self._attachments_btn)

        box.append(filters_box)

        # Separator
        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Advanced search link
        advanced_btn = Gtk.Button(
            label="Advanced Search...",
            css_classes=["flat"],
        )
        advanced_btn.connect("clicked", self._on_advanced_clicked)
        box.append(advanced_btn)

        self.set_child(box)

    def _on_search_activated(self, entry: Gtk.SearchEntry) -> None:
        """Handle search activation."""
        text = entry.get_text().strip()
        if text:
            self.emit("search-activated", text)
            self.popdown()

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Handle search text change."""

    def _on_advanced_clicked(self, button: Gtk.Button) -> None:
        """Handle advanced search click."""
        self.emit("advanced-search-requested")
        self.popdown()

    def get_quick_filters(self) -> Dict[str, bool]:
        """Get the state of quick filter toggles."""
        return {
            "is_unread": self._unread_btn.get_active(),
            "is_starred": self._starred_btn.get_active(),
            "has_attachments": self._attachments_btn.get_active(),
        }

    def clear(self) -> None:
        """Clear the search entry and filters."""
        self._entry.set_text("")
        self._unread_btn.set_active(False)
        self._starred_btn.set_active(False)
        self._attachments_btn.set_active(False)
