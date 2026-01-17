"""
unitMail Search Bar Widget.

This module provides a SearchBar widget for quick search functionality
with auto-suggest from search history, clear button, and advanced
search toggle.
"""

import logging
from typing import Callable, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

logger = logging.getLogger(__name__)


class SearchSuggestionItem(GObject.Object):
    """
    GObject wrapper for search suggestion data.

    Used in the suggestions list to represent a suggestion item.
    """

    __gtype_name__ = "SearchSuggestionItem"

    def __init__(
        self,
        text: str,
        description: Optional[str] = None,
        icon_name: str = "edit-find-symbolic",
        is_history: bool = True,
    ) -> None:
        """
        Initialize a suggestion item.

        Args:
            text: The suggestion text.
            description: Optional description (e.g., result count).
            icon_name: Icon to display.
            is_history: Whether this is from search history.
        """
        super().__init__()
        self._text = text
        self._description = description
        self._icon_name = icon_name
        self._is_history = is_history

    @GObject.Property(type=str)
    def text(self) -> str:
        """Get suggestion text."""
        return self._text

    @GObject.Property(type=str)
    def description(self) -> str:
        """Get description."""
        return self._description or ""

    @GObject.Property(type=str)
    def icon_name(self) -> str:
        """Get icon name."""
        return self._icon_name

    @GObject.Property(type=bool, default=True)
    def is_history(self) -> bool:
        """Check if from history."""
        return self._is_history


class SearchBar(Gtk.Box):
    """
    A search bar widget with auto-suggest, history, and advanced search toggle.

    Features:
    - Text entry for quick search queries
    - Auto-suggest dropdown from search history
    - Clear button to reset search
    - Advanced search toggle button
    - Keyboard shortcuts support
    - Search as-you-type with debouncing

    Signals:
        search-activated: Emitted when search is submitted.
            Signature: (query: str)
        search-changed: Emitted when search text changes (debounced).
            Signature: (query: str)
        advanced-search-requested: Emitted when advanced search is requested.
            Signature: ()
        search-cleared: Emitted when search is cleared.
            Signature: ()
    """

    __gtype_name__ = "UnitMailSearchBar"

    __gsignals__ = {
        "search-activated": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "search-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "advanced-search-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "search-cleared": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    # Debounce delay for search-as-you-type in milliseconds
    SEARCH_DEBOUNCE_MS = 300

    def __init__(
        self,
        placeholder: str = "Search messages...",
        show_advanced_button: bool = True,
        suggestions_provider: Optional[Callable[[str], List[str]]] = None,
    ) -> None:
        """
        Initialize the search bar.

        Args:
            placeholder: Placeholder text for the search entry.
            show_advanced_button: Whether to show the advanced search button.
            suggestions_provider: Callable that returns suggestions for a query.
        """
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
            css_classes=["search-bar-container"],
        )

        self._suggestions_provider = suggestions_provider
        self._debounce_timeout_id: Optional[int] = None
        self._suggestion_store: Gio.ListStore = Gio.ListStore.new(
            SearchSuggestionItem
        )
        self._is_selecting_suggestion = False

        # Build the UI
        self._build_ui(placeholder, show_advanced_button)

        # Apply styles
        self._apply_styles()

        logger.debug("SearchBar initialized")

    def _build_ui(self, placeholder: str, show_advanced_button: bool) -> None:
        """Build the search bar UI components."""
        # Main container box with border
        self._search_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4,
            css_classes=["search-bar-box"],
            hexpand=True,
        )

        # Search icon
        search_icon = Gtk.Image(
            icon_name="edit-find-symbolic",
            css_classes=["dim-label"],
            margin_start=8,
        )
        self._search_box.append(search_icon)

        # Search entry
        self._entry = Gtk.Entry(
            placeholder_text=placeholder,
            hexpand=True,
            has_frame=False,
            css_classes=["search-entry"],
        )
        self._entry.connect("activate", self._on_entry_activate)
        self._entry.connect("changed", self._on_entry_changed)
        self._entry.connect("icon-release", self._on_icon_release)

        # Key controller for escape and navigation
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self._entry.add_controller(key_controller)

        # Focus controller for showing/hiding suggestions
        focus_controller = Gtk.EventControllerFocus()
        focus_controller.connect("enter", self._on_focus_enter)
        focus_controller.connect("leave", self._on_focus_leave)
        self._entry.add_controller(focus_controller)

        self._search_box.append(self._entry)

        # Clear button (hidden initially)
        self._clear_button = Gtk.Button(
            icon_name="edit-clear-symbolic",
            css_classes=["flat", "circular", "clear-button"],
            tooltip_text="Clear search",
            visible=False,
        )
        self._clear_button.connect("clicked", self._on_clear_clicked)
        self._search_box.append(self._clear_button)

        self.append(self._search_box)

        # Advanced search button
        if show_advanced_button:
            self._advanced_button = Gtk.Button(
                icon_name="view-more-symbolic",
                css_classes=["flat", "circular"],
                tooltip_text="Advanced search (Ctrl+Shift+F)",
                margin_start=4,
            )
            self._advanced_button.connect("clicked", self._on_advanced_clicked)
            self.append(self._advanced_button)
        else:
            self._advanced_button = None

        # Create suggestions popover
        self._create_suggestions_popover()

    def _create_suggestions_popover(self) -> None:
        """Create the suggestions dropdown popover."""
        self._suggestions_popover = Gtk.Popover(
            autohide=False,
            has_arrow=False,
            css_classes=["suggestions-popover"],
        )
        self._suggestions_popover.set_parent(self._search_box)

        # Container for suggestions
        popover_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
            margin_top=4,
            margin_bottom=4,
        )

        # Header
        header_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            margin_start=12,
            margin_end=12,
            margin_top=8,
            margin_bottom=4,
        )

        header_label = Gtk.Label(
            label="Recent Searches",
            xalign=0,
            hexpand=True,
            css_classes=["dim-label", "caption"],
        )
        header_box.append(header_label)

        clear_history_button = Gtk.Button(
            label="Clear",
            css_classes=["flat", "caption"],
        )
        clear_history_button.connect("clicked", self._on_clear_history_clicked)
        header_box.append(clear_history_button)

        popover_box.append(header_box)

        # Scrolled window for suggestions list
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            min_content_height=100,
            max_content_height=300,
            min_content_width=300,
        )

        # Suggestions list
        selection_model = Gtk.SingleSelection(
            model=self._suggestion_store,
            autoselect=False,
        )
        selection_model.connect("selection-changed", self._on_suggestion_selected)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_suggestion_item_setup)
        factory.connect("bind", self._on_suggestion_item_bind)

        self._suggestions_list = Gtk.ListView(
            model=selection_model,
            factory=factory,
            css_classes=["navigation-sidebar"],
        )

        scrolled.set_child(self._suggestions_list)
        popover_box.append(scrolled)

        # Empty state
        self._empty_label = Gtk.Label(
            label="No recent searches",
            css_classes=["dim-label"],
            margin_top=16,
            margin_bottom=16,
            visible=False,
        )
        popover_box.append(self._empty_label)

        self._suggestions_popover.set_child(popover_box)

    def _on_suggestion_item_setup(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Set up a suggestion list item widget."""
        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_start=8,
            margin_end=8,
            margin_top=6,
            margin_bottom=6,
        )

        icon = Gtk.Image()
        box.append(icon)

        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=2,
            hexpand=True,
        )

        text_label = Gtk.Label(
            xalign=0,
            ellipsize=Pango.EllipsizeMode.END,
        )
        content_box.append(text_label)

        description_label = Gtk.Label(
            xalign=0,
            css_classes=["dim-label", "caption"],
            ellipsize=Pango.EllipsizeMode.END,
        )
        content_box.append(description_label)

        box.append(content_box)

        # Remove from history button
        remove_button = Gtk.Button(
            icon_name="edit-delete-symbolic",
            css_classes=["flat", "circular", "destructive-action"],
            tooltip_text="Remove from history",
            valign=Gtk.Align.CENTER,
        )
        box.append(remove_button)

        list_item.set_child(box)

    def _on_suggestion_item_bind(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Bind data to a suggestion list item widget."""
        item: SearchSuggestionItem = list_item.get_item()
        box: Gtk.Box = list_item.get_child()

        children = []
        child = box.get_first_child()
        while child:
            children.append(child)
            child = child.get_next_sibling()

        icon, content_box, remove_button = children[0], children[1], children[2]

        icon.set_from_icon_name(item.icon_name)

        content_children = []
        child = content_box.get_first_child()
        while child:
            content_children.append(child)
            child = child.get_next_sibling()

        text_label, description_label = content_children

        text_label.set_label(item.text)
        if item.description:
            description_label.set_label(item.description)
            description_label.set_visible(True)
        else:
            description_label.set_visible(False)

        # Show/hide remove button based on history status
        remove_button.set_visible(item.is_history)

        # Connect remove button
        remove_button.connect(
            "clicked",
            lambda btn: self._on_remove_suggestion(item.text),
        )

    def _apply_styles(self) -> None:
        """Apply CSS styles to the search bar."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(
            b"""
            .search-bar-container {
                margin: 4px;
            }

            .search-bar-box {
                background-color: alpha(@view_bg_color, 0.5);
                border: 1px solid @borders;
                border-radius: 6px;
                padding: 2px;
                min-height: 32px;
            }

            .search-bar-box:focus-within {
                border-color: @accent_bg_color;
                background-color: @view_bg_color;
            }

            .search-entry {
                border: none;
                background: transparent;
                box-shadow: none;
                min-height: 28px;
            }

            .search-entry:focus {
                box-shadow: none;
            }

            .clear-button {
                min-width: 24px;
                min-height: 24px;
                padding: 0;
                margin-end: 4px;
            }

            .suggestions-popover {
                padding: 0;
            }

            .suggestions-popover contents {
                border-radius: 8px;
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

    def _on_entry_activate(self, entry: Gtk.Entry) -> None:
        """Handle Enter key press."""
        text = entry.get_text().strip()
        if text:
            self._suggestions_popover.popdown()
            self.emit("search-activated", text)
            logger.debug(f"Search activated: {text}")

    def _on_entry_changed(self, entry: Gtk.Entry) -> None:
        """Handle text changes with debouncing."""
        text = entry.get_text()

        # Show/hide clear button
        self._clear_button.set_visible(bool(text))

        # Cancel previous debounce
        if self._debounce_timeout_id:
            GLib.source_remove(self._debounce_timeout_id)
            self._debounce_timeout_id = None

        # Update suggestions
        if not self._is_selecting_suggestion:
            self._update_suggestions(text)

        # Debounce search-changed signal
        if text:
            self._debounce_timeout_id = GLib.timeout_add(
                self.SEARCH_DEBOUNCE_MS,
                self._emit_search_changed,
                text,
            )

    def _emit_search_changed(self, text: str) -> bool:
        """Emit search-changed signal after debounce."""
        self._debounce_timeout_id = None
        self.emit("search-changed", text)
        return False  # Don't repeat

    def _on_icon_release(
        self,
        entry: Gtk.Entry,
        icon_pos: Gtk.EntryIconPosition,
    ) -> None:
        """Handle entry icon clicks."""
        pass  # Not using entry icons currently

    def _on_key_pressed(
        self,
        controller: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        """Handle key presses."""
        if keyval == Gdk.KEY_Escape:
            if self._suggestions_popover.get_visible():
                self._suggestions_popover.popdown()
                return True
            elif self._entry.get_text():
                self.clear()
                return True
        elif keyval == Gdk.KEY_Down:
            if not self._suggestions_popover.get_visible():
                self._show_suggestions()
            else:
                self._select_next_suggestion()
            return True
        elif keyval == Gdk.KEY_Up:
            if self._suggestions_popover.get_visible():
                self._select_previous_suggestion()
            return True

        return False

    def _on_focus_enter(self, controller: Gtk.EventControllerFocus) -> None:
        """Handle focus entering the entry."""
        text = self._entry.get_text()
        if not text:
            self._show_suggestions()

    def _on_focus_leave(self, controller: Gtk.EventControllerFocus) -> None:
        """Handle focus leaving the entry."""
        # Delay hiding to allow clicking on suggestions
        GLib.timeout_add(200, self._maybe_hide_suggestions)

    def _maybe_hide_suggestions(self) -> bool:
        """Hide suggestions if entry doesn't have focus."""
        if not self._entry.has_focus():
            self._suggestions_popover.popdown()
        return False

    def _on_clear_clicked(self, button: Gtk.Button) -> None:
        """Handle clear button click."""
        self.clear()
        self.emit("search-cleared")

    def _on_advanced_clicked(self, button: Gtk.Button) -> None:
        """Handle advanced search button click."""
        self._suggestions_popover.popdown()
        self.emit("advanced-search-requested")
        logger.debug("Advanced search requested")

    def _on_clear_history_clicked(self, button: Gtk.Button) -> None:
        """Handle clear history button click."""
        self._suggestion_store.remove_all()
        self._empty_label.set_visible(True)
        self.emit("search-cleared")

    def _on_suggestion_selected(
        self,
        selection: Gtk.SingleSelection,
        position: int,
        n_items: int,
    ) -> None:
        """Handle suggestion selection."""
        selected = selection.get_selected_item()
        if selected:
            self._is_selecting_suggestion = True
            self._entry.set_text(selected.text)
            self._entry.set_position(-1)  # Move cursor to end
            self._is_selecting_suggestion = False
            self._suggestions_popover.popdown()
            self.emit("search-activated", selected.text)

    def _on_remove_suggestion(self, text: str) -> None:
        """Handle remove suggestion from history."""
        for i in range(self._suggestion_store.get_n_items()):
            item = self._suggestion_store.get_item(i)
            if item and item.text == text:
                self._suggestion_store.remove(i)
                break

        if self._suggestion_store.get_n_items() == 0:
            self._empty_label.set_visible(True)

    # Suggestions Management

    def _show_suggestions(self) -> None:
        """Show the suggestions popover."""
        if self._suggestion_store.get_n_items() > 0:
            self._empty_label.set_visible(False)
        else:
            self._empty_label.set_visible(True)
        self._suggestions_popover.popup()

    def _update_suggestions(self, query: str) -> None:
        """Update suggestions based on current query."""
        if self._suggestions_provider:
            suggestions = self._suggestions_provider(query)
            self._suggestion_store.remove_all()

            for suggestion in suggestions:
                item = SearchSuggestionItem(
                    text=suggestion,
                    icon_name="document-open-recent-symbolic",
                    is_history=True,
                )
                self._suggestion_store.append(item)

            if suggestions:
                self._empty_label.set_visible(False)
            else:
                self._empty_label.set_visible(True)

    def _select_next_suggestion(self) -> None:
        """Select the next suggestion in the list."""
        model = self._suggestions_list.get_model()
        if isinstance(model, Gtk.SingleSelection):
            current = model.get_selected()
            n_items = self._suggestion_store.get_n_items()
            if current < n_items - 1:
                model.set_selected(current + 1)
            elif current == Gtk.INVALID_LIST_POSITION:
                model.set_selected(0)

    def _select_previous_suggestion(self) -> None:
        """Select the previous suggestion in the list."""
        model = self._suggestions_list.get_model()
        if isinstance(model, Gtk.SingleSelection):
            current = model.get_selected()
            if current > 0:
                model.set_selected(current - 1)

    # Public Methods

    def get_text(self) -> str:
        """
        Get the current search text.

        Returns:
            Current text in the search entry.
        """
        return self._entry.get_text()

    def set_text(self, text: str) -> None:
        """
        Set the search text.

        Args:
            text: Text to set in the search entry.
        """
        self._entry.set_text(text)

    def clear(self) -> None:
        """Clear the search entry."""
        self._entry.set_text("")
        self._clear_button.set_visible(False)
        self._suggestions_popover.popdown()

    def grab_focus(self) -> None:
        """Give focus to the search entry."""
        self._entry.grab_focus()

    def set_suggestions_provider(
        self,
        provider: Callable[[str], List[str]],
    ) -> None:
        """
        Set the suggestions provider.

        Args:
            provider: Callable that returns suggestions for a query.
        """
        self._suggestions_provider = provider

    def add_suggestion(
        self,
        text: str,
        description: Optional[str] = None,
        is_history: bool = True,
    ) -> None:
        """
        Add a suggestion to the list.

        Args:
            text: Suggestion text.
            description: Optional description.
            is_history: Whether this is from history.
        """
        # Check for duplicates
        for i in range(self._suggestion_store.get_n_items()):
            item = self._suggestion_store.get_item(i)
            if item and item.text == text:
                return

        item = SearchSuggestionItem(
            text=text,
            description=description,
            icon_name="document-open-recent-symbolic" if is_history else "edit-find-symbolic",
            is_history=is_history,
        )

        # Insert at beginning for history items
        if is_history:
            self._suggestion_store.insert(0, item)
        else:
            self._suggestion_store.append(item)

        self._empty_label.set_visible(False)

    def clear_suggestions(self) -> None:
        """Clear all suggestions."""
        self._suggestion_store.remove_all()
        self._empty_label.set_visible(True)

    def set_placeholder(self, text: str) -> None:
        """
        Set the placeholder text.

        Args:
            text: Placeholder text.
        """
        self._entry.set_placeholder_text(text)

    def set_sensitive(self, sensitive: bool) -> None:
        """
        Set the sensitivity of the search bar.

        Args:
            sensitive: Whether the search bar should be sensitive.
        """
        self._entry.set_sensitive(sensitive)
        if self._advanced_button:
            self._advanced_button.set_sensitive(sensitive)

    def show_loading(self, loading: bool = True) -> None:
        """
        Show or hide loading indicator.

        Args:
            loading: Whether to show loading state.
        """
        if loading:
            self._entry.set_progress_fraction(0.0)
            self._entry.start_progress_pulse()
        else:
            self._entry.set_progress_fraction(0.0)


class ExpandableSearchBar(Gtk.Revealer):
    """
    An expandable search bar that can collapse to an icon.

    Useful for header bars where space is limited.
    """

    __gtype_name__ = "UnitMailExpandableSearchBar"

    __gsignals__ = {
        "search-activated": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "search-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "advanced-search-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "search-cleared": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "expanded-changed": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
    }

    def __init__(
        self,
        placeholder: str = "Search messages...",
        show_advanced_button: bool = True,
        suggestions_provider: Optional[Callable[[str], List[str]]] = None,
    ) -> None:
        """
        Initialize the expandable search bar.

        Args:
            placeholder: Placeholder text for the search entry.
            show_advanced_button: Whether to show the advanced search button.
            suggestions_provider: Callable that returns suggestions.
        """
        super().__init__(
            transition_type=Gtk.RevealerTransitionType.SLIDE_LEFT,
            transition_duration=200,
        )

        self._search_bar = SearchBar(
            placeholder=placeholder,
            show_advanced_button=show_advanced_button,
            suggestions_provider=suggestions_provider,
        )

        # Forward signals
        self._search_bar.connect(
            "search-activated",
            lambda sb, q: self.emit("search-activated", q),
        )
        self._search_bar.connect(
            "search-changed",
            lambda sb, q: self.emit("search-changed", q),
        )
        self._search_bar.connect(
            "advanced-search-requested",
            lambda sb: self.emit("advanced-search-requested"),
        )
        self._search_bar.connect(
            "search-cleared",
            lambda sb: self.emit("search-cleared"),
        )

        self.set_child(self._search_bar)

    def expand(self) -> None:
        """Expand the search bar."""
        self.set_reveal_child(True)
        self._search_bar.grab_focus()
        self.emit("expanded-changed", True)

    def collapse(self) -> None:
        """Collapse the search bar."""
        self._search_bar.clear()
        self.set_reveal_child(False)
        self.emit("expanded-changed", False)

    def toggle(self) -> None:
        """Toggle the expanded state."""
        if self.get_reveal_child():
            self.collapse()
        else:
            self.expand()

    @property
    def is_expanded(self) -> bool:
        """Check if the search bar is expanded."""
        return self.get_reveal_child()

    @property
    def search_bar(self) -> SearchBar:
        """Get the underlying SearchBar widget."""
        return self._search_bar
