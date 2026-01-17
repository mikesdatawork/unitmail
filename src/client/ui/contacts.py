"""
Contacts management window for unitMail.

This module provides a window for managing email contacts with support
for contact groups, PGP key management, and vCard import/export.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import uuid4

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")

from gi.repository import Adw, Gio, GLib, GObject, Gtk, Pango

logger = logging.getLogger(__name__)


@dataclass
class Contact:
    """Data class representing a contact."""

    contact_id: str
    name: str
    email: str
    notes: str = ""
    pgp_key_id: Optional[str] = None
    pgp_key_fingerprint: Optional[str] = None
    pgp_public_key: Optional[str] = None
    groups: list[str] = field(default_factory=list)
    organization: str = ""
    phone: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    @property
    def display_name(self) -> str:
        """Get display name (name or email if name is empty)."""
        return self.name if self.name else self.email

    @property
    def initials(self) -> str:
        """Get initials for avatar."""
        if self.name:
            parts = self.name.split()
            if len(parts) >= 2:
                return f"{parts[0][0]}{parts[-1][0]}".upper()
            elif parts:
                return parts[0][0].upper()
        return self.email[0].upper() if self.email else "?"

    @property
    def has_pgp_key(self) -> bool:
        """Check if contact has a PGP key."""
        return bool(self.pgp_public_key or self.pgp_key_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Contact":
        """Create a Contact from a dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        return cls(
            contact_id=data.get("contact_id", str(uuid4())),
            name=data.get("name", ""),
            email=data.get("email", ""),
            notes=data.get("notes", ""),
            pgp_key_id=data.get("pgp_key_id"),
            pgp_key_fingerprint=data.get("pgp_key_fingerprint"),
            pgp_public_key=data.get("pgp_public_key"),
            groups=data.get("groups", []),
            organization=data.get("organization", ""),
            phone=data.get("phone", ""),
            created_at=created_at,
            updated_at=updated_at,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "contact_id": self.contact_id,
            "name": self.name,
            "email": self.email,
            "notes": self.notes,
            "pgp_key_id": self.pgp_key_id,
            "pgp_key_fingerprint": self.pgp_key_fingerprint,
            "pgp_public_key": self.pgp_public_key,
            "groups": self.groups,
            "organization": self.organization,
            "phone": self.phone,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_vcard(self) -> str:
        """Export contact as vCard format."""
        lines = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"FN:{self.name}" if self.name else f"FN:{self.email}",
            f"EMAIL:{self.email}",
        ]

        if self.name:
            # Split name into parts
            parts = self.name.split()
            if len(parts) >= 2:
                lines.append(f"N:{parts[-1]};{parts[0]};;;")
            else:
                lines.append(f"N:{self.name};;;;")

        if self.organization:
            lines.append(f"ORG:{self.organization}")

        if self.phone:
            lines.append(f"TEL:{self.phone}")

        if self.notes:
            # Escape newlines for vCard
            escaped_notes = self.notes.replace("\n", "\\n")
            lines.append(f"NOTE:{escaped_notes}")

        if self.pgp_key_fingerprint:
            lines.append(f"X-PGP-FINGERPRINT:{self.pgp_key_fingerprint}")

        lines.append("END:VCARD")
        return "\r\n".join(lines)

    @classmethod
    def from_vcard(cls, vcard_text: str) -> Optional["Contact"]:
        """Parse a vCard and create a Contact.

        Args:
            vcard_text: vCard text content.

        Returns:
            Contact object, or None if parsing failed.
        """
        lines = vcard_text.strip().split("\n")
        data: dict[str, Any] = {
            "contact_id": str(uuid4()),
            "groups": [],
        }

        for line in lines:
            line = line.strip()
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.upper()

                if key == "FN":
                    data["name"] = value
                elif key == "EMAIL":
                    # Handle EMAIL;TYPE=...:value
                    if ";" in key:
                        key = key.split(";")[0]
                    data["email"] = value
                elif key == "ORG":
                    data["organization"] = value
                elif key == "TEL":
                    data["phone"] = value
                elif key == "NOTE":
                    data["notes"] = value.replace("\\n", "\n")
                elif key == "X-PGP-FINGERPRINT":
                    data["pgp_key_fingerprint"] = value

        if data.get("email"):
            return cls.from_dict(data)
        return None


@dataclass
class ContactGroup:
    """Data class representing a contact group/tag."""

    group_id: str
    name: str
    color: str = "#3584e4"  # Default Adwaita blue
    contact_count: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContactGroup":
        """Create a ContactGroup from a dictionary."""
        return cls(
            group_id=data.get("group_id", str(uuid4())),
            name=data.get("name", ""),
            color=data.get("color", "#3584e4"),
            contact_count=data.get("contact_count", 0),
        )


class ContactListItem(GObject.Object):
    """GObject wrapper for contact data in list view."""

    __gtype_name__ = "ContactListItem"

    def __init__(self, contact: Contact) -> None:
        """Initialize a contact list item.

        Args:
            contact: The contact data.
        """
        super().__init__()
        self._contact = contact

    @GObject.Property(type=str)
    def contact_id(self) -> str:
        """Get contact ID."""
        return self._contact.contact_id

    @GObject.Property(type=str)
    def name(self) -> str:
        """Get contact name."""
        return self._contact.name

    @GObject.Property(type=str)
    def email(self) -> str:
        """Get contact email."""
        return self._contact.email

    @GObject.Property(type=str)
    def display_name(self) -> str:
        """Get display name."""
        return self._contact.display_name

    @GObject.Property(type=str)
    def initials(self) -> str:
        """Get initials for avatar."""
        return self._contact.initials

    @GObject.Property(type=bool, default=False)
    def has_pgp_key(self) -> bool:
        """Check if contact has PGP key."""
        return self._contact.has_pgp_key

    @property
    def data(self) -> Contact:
        """Get the underlying contact data."""
        return self._contact


class ContactsWindow(Adw.Window):
    """
    Window for managing email contacts.

    Provides a list view with search and filter, contact detail panel,
    and support for contact groups and PGP key management.
    """

    __gtype_name__ = "ContactsWindow"

    __gsignals__ = {
        # Emitted when a contact is selected
        "contact-selected": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        # Emitted when a contact is created
        "contact-created": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        # Emitted when a contact is updated
        "contact-updated": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        # Emitted when a contact is deleted
        "contact-deleted": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        # Emitted when compose is requested for a contact
        "compose-to-contact": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    DEFAULT_WIDTH = 900
    DEFAULT_HEIGHT = 650

    def __init__(
        self,
        parent: Optional[Gtk.Window] = None,
        contacts: Optional[list[Contact]] = None,
        groups: Optional[list[ContactGroup]] = None,
    ) -> None:
        """Initialize the contacts window.

        Args:
            parent: Parent window.
            contacts: Initial list of contacts.
            groups: Initial list of contact groups.
        """
        super().__init__(
            title="Contacts",
            default_width=self.DEFAULT_WIDTH,
            default_height=self.DEFAULT_HEIGHT,
        )

        if parent:
            self.set_transient_for(parent)

        self._contacts: list[Contact] = contacts or []
        self._groups: list[ContactGroup] = groups or []
        self._contact_items: dict[str, ContactListItem] = {}
        self._contact_store: Gio.ListStore = Gio.ListStore.new(ContactListItem)
        self._filter_model: Optional[Gtk.FilterListModel] = None
        self._selected_contact: Optional[Contact] = None
        self._selected_group: Optional[str] = None
        self._search_text: str = ""

        self._on_contact_saved: Optional[Callable[[Contact], None]] = None
        self._on_contact_deleted: Optional[Callable[[str], None]] = None

        self._setup_ui()
        self._populate_contacts()

        logger.debug("ContactsWindow initialized")

    def _setup_ui(self) -> None:
        """Set up the window UI."""
        # Main container
        main_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )
        self.set_content(main_box)

        # Header bar
        header_bar = self._create_header_bar()
        main_box.append(header_bar)

        # Content paned layout
        paned = Gtk.Paned(
            orientation=Gtk.Orientation.HORIZONTAL,
            shrink_start_child=False,
            shrink_end_child=False,
        )
        paned.set_vexpand(True)

        # Left side: Sidebar with groups and contact list
        left_box = self._create_left_panel()
        paned.set_start_child(left_box)
        paned.set_position(320)

        # Right side: Contact detail panel
        right_box = self._create_detail_panel()
        paned.set_end_child(right_box)

        main_box.append(paned)

    def _create_header_bar(self) -> Adw.HeaderBar:
        """Create the header bar.

        Returns:
            Header bar widget.
        """
        header_bar = Adw.HeaderBar()

        # New contact button
        new_button = Gtk.Button(
            icon_name="contact-new-symbolic",
            tooltip_text="Add new contact",
        )
        new_button.add_css_class("suggested-action")
        new_button.connect("clicked", self._on_new_contact_clicked)
        header_bar.pack_start(new_button)

        # Import/Export menu
        import_export_button = Gtk.MenuButton(
            icon_name="document-open-symbolic",
            tooltip_text="Import/Export contacts",
        )

        menu = Gio.Menu()
        menu.append("Import from vCard...", "win.import-vcard")
        menu.append("Export to vCard...", "win.export-vcard")
        menu.append("Export all contacts...", "win.export-all")
        import_export_button.set_menu_model(menu)

        header_bar.pack_start(import_export_button)

        # Set up actions
        self._setup_actions()

        # Search entry in title
        self._search_entry = Gtk.SearchEntry(
            placeholder_text="Search contacts...",
            width_chars=30,
        )
        self._search_entry.connect("search-changed", self._on_search_changed)
        header_bar.set_title_widget(self._search_entry)

        # Close button
        close_button = Gtk.Button(label="Close")
        close_button.connect("clicked", lambda b: self.close())
        header_bar.pack_end(close_button)

        return header_bar

    def _setup_actions(self) -> None:
        """Set up window actions."""
        # Import vCard action
        import_action = Gio.SimpleAction.new("import-vcard", None)
        import_action.connect("activate", self._on_import_vcard)
        self.add_action(import_action)

        # Export vCard action
        export_action = Gio.SimpleAction.new("export-vcard", None)
        export_action.connect("activate", self._on_export_vcard)
        self.add_action(export_action)

        # Export all action
        export_all_action = Gio.SimpleAction.new("export-all", None)
        export_all_action.connect("activate", self._on_export_all)
        self.add_action(export_all_action)

    def _create_left_panel(self) -> Gtk.Widget:
        """Create the left panel with groups and contact list.

        Returns:
            Left panel widget.
        """
        left_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )
        left_box.add_css_class("sidebar")

        # Groups section
        groups_frame = self._create_groups_section()
        left_box.append(groups_frame)

        # Separator
        left_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Contact list
        contact_list_frame = self._create_contact_list()
        left_box.append(contact_list_frame)

        return left_box

    def _create_groups_section(self) -> Gtk.Widget:
        """Create the contact groups section.

        Returns:
            Groups section widget.
        """
        groups_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            margin_start=8,
            margin_end=8,
            margin_top=8,
            margin_bottom=8,
        )

        # Header
        header_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )

        header_label = Gtk.Label(
            label="Groups",
            xalign=0,
            hexpand=True,
            css_classes=["heading"],
        )
        header_box.append(header_label)

        # Add group button
        add_group_button = Gtk.Button(
            icon_name="list-add-symbolic",
            tooltip_text="Add group",
            css_classes=["flat", "circular"],
        )
        add_group_button.connect("clicked", self._on_add_group_clicked)
        header_box.append(add_group_button)

        groups_box.append(header_box)

        # All contacts button
        all_button = Gtk.Button(
            label="All Contacts",
            css_classes=["flat"],
        )
        all_button.set_halign(Gtk.Align.FILL)
        all_button.connect("clicked", self._on_all_contacts_clicked)
        groups_box.append(all_button)

        # Group list
        self._groups_list_box = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.SINGLE,
            css_classes=["navigation-sidebar"],
        )
        self._groups_list_box.connect("row-selected", self._on_group_selected)
        groups_box.append(self._groups_list_box)

        return groups_box

    def _create_contact_list(self) -> Gtk.Widget:
        """Create the contact list widget.

        Returns:
            Contact list container.
        """
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )

        # Create filter for search
        filter_func = Gtk.CustomFilter.new(self._filter_contact, None)
        self._filter_model = Gtk.FilterListModel(
            model=self._contact_store,
            filter=filter_func,
        )
        self._contact_filter = filter_func

        # Create factory
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_contact_item_setup)
        factory.connect("bind", self._on_contact_item_bind)

        # Selection model
        self._selection_model = Gtk.SingleSelection(model=self._filter_model)
        self._selection_model.connect("selection-changed", self._on_contact_selected)

        # List view
        self._contact_list = Gtk.ListView(
            model=self._selection_model,
            factory=factory,
            css_classes=["contact-list"],
        )

        scrolled.set_child(self._contact_list)
        return scrolled

    def _filter_contact(
        self,
        item: ContactListItem,
        user_data: Any,
    ) -> bool:
        """Filter function for contact search.

        Args:
            item: Contact list item to filter.
            user_data: User data (unused).

        Returns:
            True if contact should be shown.
        """
        if not self._search_text:
            # Check group filter
            if self._selected_group:
                return self._selected_group in item.data.groups
            return True

        search_lower = self._search_text.lower()
        name_match = search_lower in item.name.lower()
        email_match = search_lower in item.email.lower()

        # Also check group filter
        if self._selected_group:
            return (name_match or email_match) and self._selected_group in item.data.groups

        return name_match or email_match

    def _on_contact_item_setup(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Set up a contact list item widget."""
        row_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_start=12,
            margin_end=12,
            margin_top=8,
            margin_bottom=8,
        )

        # Avatar
        avatar_frame = Gtk.Frame(
            css_classes=["avatar-frame"],
        )
        avatar_label = Gtk.Label(
            css_classes=["avatar-label"],
        )
        avatar_label.set_size_request(40, 40)
        avatar_frame.set_child(avatar_label)
        row_box.append(avatar_frame)

        # Info container
        info_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=2,
            hexpand=True,
        )

        name_label = Gtk.Label(
            xalign=0,
            css_classes=["contact-name"],
        )
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        info_box.append(name_label)

        email_label = Gtk.Label(
            xalign=0,
            css_classes=["dim-label", "contact-email"],
        )
        email_label.set_ellipsize(Pango.EllipsizeMode.END)
        info_box.append(email_label)

        row_box.append(info_box)

        # PGP indicator
        pgp_icon = Gtk.Image.new_from_icon_name("channel-secure-symbolic")
        pgp_icon.add_css_class("pgp-indicator")
        pgp_icon.set_tooltip_text("Has PGP key")
        row_box.append(pgp_icon)

        list_item.set_child(row_box)

    def _on_contact_item_bind(
        self,
        factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Bind data to a contact list item widget."""
        item: ContactListItem = list_item.get_item()
        row_box: Gtk.Box = list_item.get_child()

        children = self._get_box_children(row_box)
        avatar_frame, info_box, pgp_icon = children[:3]

        # Set avatar
        avatar_label = avatar_frame.get_child()
        avatar_label.set_label(item.initials)

        # Set avatar color based on name/email
        color_idx = hash(item.email) % 8
        _colors = [  # noqa: F841 - colors defined in CSS, kept for reference
            "#e01b24", "#ff7800", "#f6d32d", "#33d17a",
            "#3584e4", "#9141ac", "#986a44", "#77767b"
        ]
        avatar_frame.set_css_classes(["avatar-frame"])
        # Apply color via inline style or CSS class
        avatar_label.set_css_classes(["avatar-label", f"avatar-color-{color_idx}"])

        # Set name and email
        info_children = self._get_box_children(info_box)
        name_label, email_label = info_children[:2]

        name_label.set_label(item.display_name)
        email_label.set_label(item.email)

        # Show/hide PGP indicator
        pgp_icon.set_visible(item.has_pgp_key)

    def _get_box_children(self, box: Gtk.Box) -> list[Gtk.Widget]:
        """Get all children of a box widget."""
        children = []
        child = box.get_first_child()
        while child:
            children.append(child)
            child = child.get_next_sibling()
        return children

    def _create_detail_panel(self) -> Gtk.Widget:
        """Create the contact detail panel.

        Returns:
            Detail panel widget.
        """
        self._detail_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
            css_classes=["detail-panel"],
        )

        # Show placeholder initially
        self._show_detail_placeholder()

        return self._detail_box

    def _show_detail_placeholder(self) -> None:
        """Show placeholder in detail panel."""
        # Clear existing content
        child = self._detail_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self._detail_box.remove(child)
            child = next_child

        # Add placeholder
        placeholder = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
            vexpand=True,
            hexpand=True,
        )

        icon = Gtk.Image.new_from_icon_name("avatar-default-symbolic")
        icon.set_pixel_size(64)
        icon.add_css_class("dim-label")
        placeholder.append(icon)

        label = Gtk.Label(
            label="Select a contact to view details",
            css_classes=["dim-label"],
        )
        placeholder.append(label)

        self._detail_box.append(placeholder)

    def _show_contact_details(self, contact: Contact) -> None:
        """Show details for a contact.

        Args:
            contact: The contact to display.
        """
        # Clear existing content
        child = self._detail_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self._detail_box.remove(child)
            child = next_child

        # Scrolled window for content
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )

        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
            margin_start=24,
            margin_end=24,
            margin_top=24,
            margin_bottom=24,
        )

        # Header with avatar and name
        header_box = self._create_contact_header(contact)
        content_box.append(header_box)

        # Action buttons
        actions_box = self._create_contact_actions(contact)
        content_box.append(actions_box)

        # Contact info sections
        info_section = self._create_info_section(contact)
        content_box.append(info_section)

        # PGP section
        if contact.has_pgp_key:
            pgp_section = self._create_pgp_section(contact)
            content_box.append(pgp_section)

        # Notes section
        notes_section = self._create_notes_section(contact)
        content_box.append(notes_section)

        # Groups/tags section
        groups_section = self._create_contact_groups_section(contact)
        content_box.append(groups_section)

        scrolled.set_child(content_box)
        self._detail_box.append(scrolled)

    def _create_contact_header(self, contact: Contact) -> Gtk.Widget:
        """Create the contact header with avatar and name.

        Args:
            contact: The contact.

        Returns:
            Header widget.
        """
        header_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            halign=Gtk.Align.CENTER,
        )

        # Large avatar
        avatar_frame = Gtk.Frame(
            css_classes=["avatar-frame", "avatar-large"],
        )
        avatar_label = Gtk.Label(
            label=contact.initials,
            css_classes=["avatar-label", "avatar-label-large"],
        )
        avatar_label.set_size_request(80, 80)
        avatar_frame.set_child(avatar_label)
        header_box.append(avatar_frame)

        # Name
        name_label = Gtk.Label(
            label=contact.display_name,
            css_classes=["title-1"],
        )
        header_box.append(name_label)

        # Email
        email_label = Gtk.Label(
            label=contact.email,
            css_classes=["dim-label"],
        )
        header_box.append(email_label)

        return header_box

    def _create_contact_actions(self, contact: Contact) -> Gtk.Widget:
        """Create action buttons for a contact.

        Args:
            contact: The contact.

        Returns:
            Actions widget.
        """
        actions_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            halign=Gtk.Align.CENTER,
        )

        # Compose button
        compose_button = Gtk.Button(
            icon_name="mail-message-new-symbolic",
            tooltip_text="Send email",
        )
        compose_button.add_css_class("suggested-action")
        compose_button.add_css_class("circular")
        compose_button.connect(
            "clicked",
            lambda b: self.emit("compose-to-contact", contact.email),
        )
        actions_box.append(compose_button)

        # Edit button
        edit_button = Gtk.Button(
            icon_name="document-edit-symbolic",
            tooltip_text="Edit contact",
        )
        edit_button.add_css_class("circular")
        edit_button.connect("clicked", lambda b: self._on_edit_contact_clicked(contact))
        actions_box.append(edit_button)

        # Delete button
        delete_button = Gtk.Button(
            icon_name="user-trash-symbolic",
            tooltip_text="Delete contact",
        )
        delete_button.add_css_class("destructive-action")
        delete_button.add_css_class("circular")
        delete_button.connect("clicked", lambda b: self._on_delete_contact_clicked(contact))
        actions_box.append(delete_button)

        return actions_box

    def _create_info_section(self, contact: Contact) -> Gtk.Widget:
        """Create the contact info section.

        Args:
            contact: The contact.

        Returns:
            Info section widget.
        """
        section = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
        )

        # Section header
        header = Gtk.Label(
            label="Contact Information",
            xalign=0,
            css_classes=["heading"],
        )
        section.append(header)

        # Info grid
        grid = Gtk.Grid(
            row_spacing=8,
            column_spacing=16,
        )

        row = 0

        # Email
        grid.attach(
            Gtk.Label(label="Email:", xalign=1, css_classes=["dim-label"]),
            0, row, 1, 1
        )
        email_label = Gtk.Label(label=contact.email, xalign=0, selectable=True)
        grid.attach(email_label, 1, row, 1, 1)
        row += 1

        # Organization
        if contact.organization:
            grid.attach(
                Gtk.Label(label="Organization:", xalign=1, css_classes=["dim-label"]),
                0, row, 1, 1
            )
            grid.attach(
                Gtk.Label(label=contact.organization, xalign=0, selectable=True),
                1, row, 1, 1
            )
            row += 1

        # Phone
        if contact.phone:
            grid.attach(
                Gtk.Label(label="Phone:", xalign=1, css_classes=["dim-label"]),
                0, row, 1, 1
            )
            grid.attach(
                Gtk.Label(label=contact.phone, xalign=0, selectable=True),
                1, row, 1, 1
            )
            row += 1

        section.append(grid)
        return section

    def _create_pgp_section(self, contact: Contact) -> Gtk.Widget:
        """Create the PGP key section.

        Args:
            contact: The contact.

        Returns:
            PGP section widget.
        """
        section = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
        )

        # Section header
        header_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )

        header = Gtk.Label(
            label="PGP Key",
            xalign=0,
            hexpand=True,
            css_classes=["heading"],
        )
        header_box.append(header)

        # Verified indicator
        verified_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        verified_icon.add_css_class("success")
        verified_icon.set_tooltip_text("Key verified")
        header_box.append(verified_icon)

        section.append(header_box)

        # Key info
        info_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            css_classes=["card"],
            margin_top=8,
        )
        info_box.set_margin_start(12)
        info_box.set_margin_end(12)
        info_box.set_margin_top(12)
        info_box.set_margin_bottom(12)

        if contact.pgp_key_id:
            key_id_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=8,
            )
            key_id_box.append(
                Gtk.Label(label="Key ID:", css_classes=["dim-label"])
            )
            key_id_box.append(
                Gtk.Label(label=contact.pgp_key_id, selectable=True, css_classes=["monospace"])
            )
            info_box.append(key_id_box)

        if contact.pgp_key_fingerprint:
            fingerprint_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=4,
            )
            fingerprint_box.append(
                Gtk.Label(label="Fingerprint:", xalign=0, css_classes=["dim-label"])
            )
            # Format fingerprint in groups of 4
            fp = contact.pgp_key_fingerprint.replace(" ", "")
            formatted_fp = " ".join([fp[i:i+4] for i in range(0, len(fp), 4)])
            fingerprint_box.append(
                Gtk.Label(
                    label=formatted_fp,
                    xalign=0,
                    selectable=True,
                    css_classes=["monospace", "caption"],
                    wrap=True,
                )
            )
            info_box.append(fingerprint_box)

        section.append(info_box)
        return section

    def _create_notes_section(self, contact: Contact) -> Gtk.Widget:
        """Create the notes section.

        Args:
            contact: The contact.

        Returns:
            Notes section widget.
        """
        section = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
        )

        # Section header
        header = Gtk.Label(
            label="Notes",
            xalign=0,
            css_classes=["heading"],
        )
        section.append(header)

        # Notes content
        if contact.notes:
            notes_label = Gtk.Label(
                label=contact.notes,
                xalign=0,
                wrap=True,
                selectable=True,
            )
            section.append(notes_label)
        else:
            notes_label = Gtk.Label(
                label="No notes",
                xalign=0,
                css_classes=["dim-label"],
            )
            section.append(notes_label)

        return section

    def _create_contact_groups_section(self, contact: Contact) -> Gtk.Widget:
        """Create the groups/tags section for a contact.

        Args:
            contact: The contact.

        Returns:
            Groups section widget.
        """
        section = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
        )

        # Section header
        header_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )

        header = Gtk.Label(
            label="Groups",
            xalign=0,
            hexpand=True,
            css_classes=["heading"],
        )
        header_box.append(header)

        # Add to group button
        add_button = Gtk.Button(
            icon_name="list-add-symbolic",
            tooltip_text="Add to group",
            css_classes=["flat", "circular"],
        )
        add_button.connect("clicked", lambda b: self._on_add_to_group_clicked(contact))
        header_box.append(add_button)

        section.append(header_box)

        # Group tags
        tags_box = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE,
            max_children_per_line=10,
            row_spacing=4,
            column_spacing=4,
        )

        if contact.groups:
            for group_id in contact.groups:
                group = self._find_group_by_id(group_id)
                if group:
                    tag = self._create_group_tag(group, contact)
                    tags_box.append(tag)
        else:
            no_groups_label = Gtk.Label(
                label="Not in any groups",
                css_classes=["dim-label"],
            )
            tags_box.append(no_groups_label)

        section.append(tags_box)
        return section

    def _create_group_tag(self, group: ContactGroup, contact: Contact) -> Gtk.Widget:
        """Create a group tag widget.

        Args:
            group: The group.
            contact: The contact.

        Returns:
            Tag widget.
        """
        tag_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4,
            css_classes=["tag"],
        )

        label = Gtk.Label(label=group.name)
        tag_box.append(label)

        # Remove button
        remove_button = Gtk.Button(
            icon_name="window-close-symbolic",
            css_classes=["flat", "circular", "small"],
        )
        remove_button.connect(
            "clicked",
            lambda b: self._on_remove_from_group_clicked(contact, group.group_id),
        )
        tag_box.append(remove_button)

        return tag_box

    def _find_group_by_id(self, group_id: str) -> Optional[ContactGroup]:
        """Find a group by its ID.

        Args:
            group_id: The group ID.

        Returns:
            The group, or None if not found.
        """
        for group in self._groups:
            if group.group_id == group_id:
                return group
        return None

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Handle search text change."""
        self._search_text = entry.get_text()
        self._contact_filter.changed(Gtk.FilterChange.DIFFERENT)

    def _on_contact_selected(
        self,
        selection: Gtk.SingleSelection,
        position: int,
        n_items: int,
    ) -> None:
        """Handle contact selection."""
        selected = selection.get_selected_item()
        if selected:
            self._selected_contact = selected.data
            self._show_contact_details(self._selected_contact)
            self.emit("contact-selected", selected.contact_id)
        else:
            self._selected_contact = None
            self._show_detail_placeholder()

    def _on_group_selected(
        self,
        list_box: Gtk.ListBox,
        row: Optional[Gtk.ListBoxRow],
    ) -> None:
        """Handle group selection for filtering."""
        if row:
            self._selected_group = row.get_name()
        else:
            self._selected_group = None
        self._contact_filter.changed(Gtk.FilterChange.DIFFERENT)

    def _on_all_contacts_clicked(self, button: Gtk.Button) -> None:
        """Handle 'All Contacts' button click."""
        self._groups_list_box.unselect_all()
        self._selected_group = None
        self._contact_filter.changed(Gtk.FilterChange.DIFFERENT)

    def _on_new_contact_clicked(self, button: Gtk.Button) -> None:
        """Handle new contact button click."""
        self._show_contact_editor(None)

    def _on_edit_contact_clicked(self, contact: Contact) -> None:
        """Handle edit contact button click."""
        self._show_contact_editor(contact)

    def _on_delete_contact_clicked(self, contact: Contact) -> None:
        """Handle delete contact button click."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            modal=True,
            heading="Delete Contact",
            body=f"Are you sure you want to delete '{contact.display_name}'?",
        )

        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(dialog: Adw.MessageDialog, response: str) -> None:
            if response == "delete":
                self._delete_contact(contact.contact_id)
            dialog.close()

        dialog.connect("response", on_response)
        dialog.present()

    def _on_add_group_clicked(self, button: Gtk.Button) -> None:
        """Handle add group button click."""
        self._show_group_editor(None)

    def _on_add_to_group_clicked(self, contact: Contact) -> None:
        """Handle add to group button click."""
        # Show group selection dialog
        dialog = Adw.MessageDialog(
            transient_for=self,
            modal=True,
            heading="Add to Group",
            body="Select a group:",
        )

        # Group dropdown
        group_names = [g.name for g in self._groups if g.group_id not in contact.groups]
        if not group_names:
            dialog.set_body("No groups available. Create a group first.")
            dialog.add_response("ok", "OK")
            dialog.present()
            return

        dropdown = Gtk.DropDown.new_from_strings(group_names)
        dropdown.set_margin_start(16)
        dropdown.set_margin_end(16)
        dialog.set_extra_child(dropdown)

        dialog.add_response("cancel", "Cancel")
        dialog.add_response("add", "Add")
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dialog: Adw.MessageDialog, response: str) -> None:
            if response == "add":
                selected_idx = dropdown.get_selected()
                available_groups = [g for g in self._groups if g.group_id not in contact.groups]
                if 0 <= selected_idx < len(available_groups):
                    group = available_groups[selected_idx]
                    contact.groups.append(group.group_id)
                    contact.updated_at = datetime.now()
                    self._show_contact_details(contact)
                    self.emit("contact-updated", contact.contact_id)
            dialog.close()

        dialog.connect("response", on_response)
        dialog.present()

    def _on_remove_from_group_clicked(self, contact: Contact, group_id: str) -> None:
        """Handle remove from group button click."""
        if group_id in contact.groups:
            contact.groups.remove(group_id)
            contact.updated_at = datetime.now()
            self._show_contact_details(contact)
            self.emit("contact-updated", contact.contact_id)

    def _show_contact_editor(self, contact: Optional[Contact]) -> None:
        """Show the contact editor dialog.

        Args:
            contact: Contact to edit, or None for new contact.
        """
        is_new = contact is None
        if is_new:
            contact = Contact(
                contact_id=str(uuid4()),
                name="",
                email="",
            )

        dialog = Adw.Window(
            title="Edit Contact" if not is_new else "New Contact",
            default_width=450,
            default_height=550,
            modal=True,
            transient_for=self,
        )

        # Main container
        main_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )

        # Header bar
        header = Adw.HeaderBar()

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda b: dialog.close())
        header.pack_start(cancel_button)

        save_button = Gtk.Button(label="Save")
        save_button.add_css_class("suggested-action")
        header.pack_end(save_button)

        main_box.append(header)

        # Content
        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            margin_start=16,
            margin_end=16,
            margin_top=16,
            margin_bottom=16,
        )

        # Name entry
        name_group = Adw.PreferencesGroup(title="Name")
        name_row = Adw.EntryRow(title="Full Name", text=contact.name)
        name_group.add(name_row)
        content_box.append(name_group)

        # Email entry
        email_group = Adw.PreferencesGroup(title="Email")
        email_row = Adw.EntryRow(title="Email Address", text=contact.email)
        email_group.add(email_row)
        content_box.append(email_group)

        # Organization entry
        org_group = Adw.PreferencesGroup(title="Organization")
        org_row = Adw.EntryRow(title="Company/Organization", text=contact.organization)
        org_group.add(org_row)
        content_box.append(org_group)

        # Phone entry
        phone_group = Adw.PreferencesGroup(title="Phone")
        phone_row = Adw.EntryRow(title="Phone Number", text=contact.phone)
        phone_group.add(phone_row)
        content_box.append(phone_group)

        # Notes entry
        notes_group = Adw.PreferencesGroup(title="Notes")
        notes_view = Gtk.TextView(
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            left_margin=8,
            right_margin=8,
            top_margin=8,
            bottom_margin=8,
        )
        notes_view.get_buffer().set_text(contact.notes)
        notes_frame = Gtk.Frame()
        notes_frame.set_child(notes_view)
        notes_group.add(notes_frame)
        content_box.append(notes_group)

        # PGP key entry
        pgp_group = Adw.PreferencesGroup(title="PGP Key")
        pgp_row = Adw.EntryRow(
            title="PGP Key ID or Fingerprint",
            text=contact.pgp_key_fingerprint or contact.pgp_key_id or "",
        )
        pgp_group.add(pgp_row)
        content_box.append(pgp_group)

        scrolled = Gtk.ScrolledWindow(
            vexpand=True,
        )
        scrolled.set_child(content_box)
        main_box.append(scrolled)

        def on_save_clicked(button: Gtk.Button) -> None:
            # Validate email
            email = email_row.get_text().strip()
            if not email or "@" not in email:
                # Show error
                email_row.add_css_class("error")
                return

            # Update contact
            contact.name = name_row.get_text().strip()
            contact.email = email
            contact.organization = org_row.get_text().strip()
            contact.phone = phone_row.get_text().strip()

            buffer = notes_view.get_buffer()
            start, end = buffer.get_bounds()
            contact.notes = buffer.get_text(start, end, False)

            pgp_text = pgp_row.get_text().strip()
            if pgp_text:
                # Determine if it's a key ID or fingerprint based on length
                if len(pgp_text.replace(" ", "")) > 16:
                    contact.pgp_key_fingerprint = pgp_text
                else:
                    contact.pgp_key_id = pgp_text

            contact.updated_at = datetime.now()

            if is_new:
                self._contacts.append(contact)
                self._contact_items[contact.contact_id] = ContactListItem(contact)
                self._contact_store.append(self._contact_items[contact.contact_id])
                self.emit("contact-created", contact.contact_id)
            else:
                self.emit("contact-updated", contact.contact_id)

            if self._on_contact_saved:
                self._on_contact_saved(contact)

            # Refresh display
            self._show_contact_details(contact)
            dialog.close()

        save_button.connect("clicked", on_save_clicked)

        dialog.set_content(main_box)
        dialog.present()

    def _show_group_editor(self, group: Optional[ContactGroup]) -> None:
        """Show the group editor dialog.

        Args:
            group: Group to edit, or None for new group.
        """
        is_new = group is None
        if is_new:
            group = ContactGroup(
                group_id=str(uuid4()),
                name="",
            )

        dialog = Adw.MessageDialog(
            transient_for=self,
            modal=True,
            heading="New Group" if is_new else "Edit Group",
            body="Enter a name for the group:",
        )

        entry = Gtk.Entry(
            text=group.name,
            margin_start=16,
            margin_end=16,
        )
        entry.set_activates_default(True)
        dialog.set_extra_child(entry)

        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("save")

        def on_response(dialog: Adw.MessageDialog, response: str) -> None:
            if response == "save":
                name = entry.get_text().strip()
                if name:
                    group.name = name
                    if is_new:
                        self._groups.append(group)
                    self._update_groups_list()
            dialog.close()

        dialog.connect("response", on_response)
        dialog.present()

    def _update_groups_list(self) -> None:
        """Update the groups list in the sidebar."""
        # Clear existing rows
        child = self._groups_list_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self._groups_list_box.remove(child)
            child = next_child

        # Add group rows
        for group in self._groups:
            row = Gtk.ListBoxRow()
            row.set_name(group.group_id)

            box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=8,
                margin_start=8,
                margin_end=8,
                margin_top=4,
                margin_bottom=4,
            )

            # Color indicator
            color_box = Gtk.Box()
            color_box.set_size_request(8, 8)
            color_box.add_css_class("group-color")
            # TODO: Apply actual color
            box.append(color_box)

            # Name
            label = Gtk.Label(
                label=group.name,
                xalign=0,
                hexpand=True,
            )
            box.append(label)

            # Count
            count_label = Gtk.Label(
                label=str(group.contact_count),
                css_classes=["dim-label"],
            )
            box.append(count_label)

            row.set_child(box)
            self._groups_list_box.append(row)

    def _delete_contact(self, contact_id: str) -> None:
        """Delete a contact.

        Args:
            contact_id: ID of the contact to delete.
        """
        # Remove from list
        self._contacts = [c for c in self._contacts if c.contact_id != contact_id]

        # Remove from store
        item = self._contact_items.get(contact_id)
        if item:
            for i in range(self._contact_store.get_n_items()):
                if self._contact_store.get_item(i).contact_id == contact_id:
                    self._contact_store.remove(i)
                    break
            del self._contact_items[contact_id]

        self._selected_contact = None
        self._show_detail_placeholder()

        self.emit("contact-deleted", contact_id)
        if self._on_contact_deleted:
            self._on_contact_deleted(contact_id)

        logger.info(f"Deleted contact: {contact_id}")

    def _populate_contacts(self) -> None:
        """Populate the contact list."""
        self._contact_store.remove_all()
        self._contact_items.clear()

        for contact in self._contacts:
            item = ContactListItem(contact)
            self._contact_items[contact.contact_id] = item
            self._contact_store.append(item)

        self._update_groups_list()

    def _on_import_vcard(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle import vCard action."""
        dialog = Gtk.FileDialog(
            title="Import vCard",
            modal=True,
        )

        # Set filter for vCard files
        filter_store = Gio.ListStore.new(Gtk.FileFilter)
        vcard_filter = Gtk.FileFilter()
        vcard_filter.set_name("vCard files")
        vcard_filter.add_pattern("*.vcf")
        vcard_filter.add_pattern("*.vcard")
        filter_store.append(vcard_filter)
        dialog.set_filters(filter_store)

        def on_open_finish(dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
            try:
                file = dialog.open_finish(result)
                if file:
                    path = file.get_path()
                    self._import_vcard_file(path)
            except GLib.Error as e:
                if e.code != Gtk.DialogError.DISMISSED:
                    logger.error(f"Error opening file: {e}")

        dialog.open(self, None, on_open_finish)

    def _import_vcard_file(self, path: str) -> None:
        """Import contacts from a vCard file.

        Args:
            path: Path to the vCard file.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # Split into individual vCards
            vcards = re.split(r"(?=BEGIN:VCARD)", content)

            imported_count = 0
            for vcard_text in vcards:
                vcard_text = vcard_text.strip()
                if vcard_text:
                    contact = Contact.from_vcard(vcard_text)
                    if contact:
                        self._contacts.append(contact)
                        imported_count += 1

            self._populate_contacts()
            logger.info(f"Imported {imported_count} contacts from {path}")

            # Show success message
            dialog = Adw.MessageDialog(
                transient_for=self,
                modal=True,
                heading="Import Complete",
                body=f"Successfully imported {imported_count} contact(s).",
            )
            dialog.add_response("ok", "OK")
            dialog.present()

        except Exception as e:
            logger.error(f"Error importing vCard: {e}")
            dialog = Adw.MessageDialog(
                transient_for=self,
                modal=True,
                heading="Import Failed",
                body=f"Error importing contacts: {e}",
            )
            dialog.add_response("ok", "OK")
            dialog.present()

    def _on_export_vcard(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle export vCard action for selected contact."""
        if not self._selected_contact:
            return

        dialog = Gtk.FileDialog(
            title="Export vCard",
            modal=True,
            initial_name=f"{self._selected_contact.display_name}.vcf",
        )

        def on_save_finish(dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
            try:
                file = dialog.save_finish(result)
                if file:
                    path = file.get_path()
                    vcard = self._selected_contact.to_vcard()
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(vcard)
                    logger.info(f"Exported contact to {path}")
            except GLib.Error as e:
                if e.code != Gtk.DialogError.DISMISSED:
                    logger.error(f"Error saving file: {e}")

        dialog.save(self, None, on_save_finish)

    def _on_export_all(
        self,
        action: Gio.SimpleAction,
        param: Optional[GLib.Variant],
    ) -> None:
        """Handle export all contacts action."""
        if not self._contacts:
            return

        dialog = Gtk.FileDialog(
            title="Export All Contacts",
            modal=True,
            initial_name="contacts.vcf",
        )

        def on_save_finish(dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
            try:
                file = dialog.save_finish(result)
                if file:
                    path = file.get_path()
                    vcards = "\r\n".join(c.to_vcard() for c in self._contacts)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(vcards)
                    logger.info(f"Exported {len(self._contacts)} contacts to {path}")
            except GLib.Error as e:
                if e.code != Gtk.DialogError.DISMISSED:
                    logger.error(f"Error saving file: {e}")

        dialog.save(self, None, on_save_finish)

    def set_contacts(self, contacts: list[Contact | dict[str, Any]]) -> None:
        """Set the contact list.

        Args:
            contacts: List of Contact objects or dicts.
        """
        self._contacts = []
        for contact_data in contacts:
            if isinstance(contact_data, dict):
                contact = Contact.from_dict(contact_data)
            else:
                contact = contact_data
            self._contacts.append(contact)

        self._populate_contacts()

    def set_groups(self, groups: list[ContactGroup | dict[str, Any]]) -> None:
        """Set the contact groups.

        Args:
            groups: List of ContactGroup objects or dicts.
        """
        self._groups = []
        for group_data in groups:
            if isinstance(group_data, dict):
                group = ContactGroup.from_dict(group_data)
            else:
                group = group_data
            self._groups.append(group)

        self._update_groups_list()

    def get_contacts(self) -> list[Contact]:
        """Get all contacts.

        Returns:
            List of contacts.
        """
        return self._contacts.copy()

    def get_groups(self) -> list[ContactGroup]:
        """Get all contact groups.

        Returns:
            List of contact groups.
        """
        return self._groups.copy()

    def set_on_contact_saved(self, callback: Callable[[Contact], None]) -> None:
        """Set callback for contact save.

        Args:
            callback: Function receiving the saved contact.
        """
        self._on_contact_saved = callback

    def set_on_contact_deleted(self, callback: Callable[[str], None]) -> None:
        """Set callback for contact deletion.

        Args:
            callback: Function receiving the contact ID.
        """
        self._on_contact_deleted = callback

    @staticmethod
    def get_css() -> str:
        """Get CSS styles for the contacts window."""
        return """
        .contact-list {
            background-color: @card_bg_color;
        }

        .contact-list row {
            padding: 4px;
        }

        .contact-list row:hover {
            background-color: alpha(@accent_bg_color, 0.1);
        }

        .contact-list row:selected {
            background-color: @accent_bg_color;
            color: @accent_fg_color;
        }

        .contact-name {
            font-weight: 500;
        }

        .contact-email {
            font-size: smaller;
        }

        .avatar-frame {
            border-radius: 50%;
            background-color: @accent_bg_color;
        }

        .avatar-label {
            font-weight: bold;
            color: @accent_fg_color;
        }

        .avatar-large {
            min-width: 80px;
            min-height: 80px;
        }

        .avatar-label-large {
            font-size: 24px;
        }

        .avatar-color-0 { background-color: #e01b24; }
        .avatar-color-1 { background-color: #ff7800; }
        .avatar-color-2 { background-color: #f6d32d; }
        .avatar-color-3 { background-color: #33d17a; }
        .avatar-color-4 { background-color: #3584e4; }
        .avatar-color-5 { background-color: #9141ac; }
        .avatar-color-6 { background-color: #986a44; }
        .avatar-color-7 { background-color: #77767b; }

        .pgp-indicator {
            color: @success_color;
        }

        .detail-panel {
            background-color: @view_bg_color;
        }

        .tag {
            background-color: alpha(@accent_bg_color, 0.2);
            border-radius: 4px;
            padding: 4px 8px;
        }

        .group-color {
            border-radius: 50%;
            background-color: @accent_color;
        }

        .monospace {
            font-family: monospace;
        }

        .success {
            color: @success_color;
        }
        """
