"""
PGP Key Manager widget for unitMail.

This module provides a widget for managing PGP keys including
key generation, import/export, viewing fingerprints, and setting
trust levels.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

logger = logging.getLogger(__name__)


class KeyTrustLevel(IntEnum):
    """PGP key trust levels."""

    UNKNOWN = 0
    NEVER = 1
    MARGINAL = 2
    FULL = 3
    ULTIMATE = 4

    def to_display_string(self) -> str:
        """Get display string for trust level."""
        return {
            KeyTrustLevel.UNKNOWN: "Unknown",
            KeyTrustLevel.NEVER: "Never Trust",
            KeyTrustLevel.MARGINAL: "Marginal",
            KeyTrustLevel.FULL: "Full",
            KeyTrustLevel.ULTIMATE: "Ultimate",
        }[self]


@dataclass
class PGPKey:
    """Represents a PGP key."""

    key_id: str
    fingerprint: str
    user_id: str
    email: str
    algorithm: str
    key_size: int
    created: datetime
    expires: Optional[datetime]
    is_private: bool
    trust_level: KeyTrustLevel
    is_revoked: bool = False
    is_expired: bool = False

    @property
    def short_key_id(self) -> str:
        """Get short key ID (last 8 characters)."""
        return self.key_id[-8:] if len(self.key_id) >= 8 else self.key_id

    @property
    def formatted_fingerprint(self) -> str:
        """Get fingerprint formatted in groups of 4."""
        fp = self.fingerprint.upper()
        return " ".join(fp[i : i + 4] for i in range(0, len(fp), 4))

    @property
    def status_text(self) -> str:
        """Get status text for the key."""
        if self.is_revoked:
            return "Revoked"
        if self.is_expired:
            return "Expired"
        return "Valid"


class PGPKeyRow(Gtk.ListBoxRow):
    """
    List row widget displaying a PGP key.
    """

    __gtype_name__ = "PGPKeyRow"

    __gsignals__ = {
        "key-selected": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }

    def __init__(self, key: PGPKey) -> None:
        """
        Initialize key row.

        Args:
            key: The PGP key to display.
        """
        super().__init__()

        self.key = key
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the row UI."""
        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_start=12,
            margin_end=12,
            margin_top=8,
            margin_bottom=8,
        )
        self.set_child(box)

        # Key icon
        icon_name = "dialog-password-symbolic" if self.key.is_private else "security-high-symbolic"
        icon = Gtk.Image(
            icon_name=icon_name,
            pixel_size=32,
        )

        # Apply status-based styling
        if self.key.is_revoked or self.key.is_expired:
            icon.add_css_class("dim-label")

        box.append(icon)

        # Key info
        info_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=2,
            hexpand=True,
        )

        # User ID / Email
        user_label = Gtk.Label(
            label=self.key.user_id or self.key.email,
            xalign=0,
            css_classes=["heading"],
        )
        user_label.set_ellipsize(True)
        info_box.append(user_label)

        # Key ID and algorithm
        details = f"{
            self.key.short_key_id} - {
            self.key.algorithm} {
            self.key.key_size}"
        details_label = Gtk.Label(
            label=details,
            xalign=0,
            css_classes=["dim-label", "caption"],
        )
        info_box.append(details_label)

        box.append(info_box)

        # Status badge
        status_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=2,
            valign=Gtk.Align.CENTER,
        )

        # Key type badge
        type_text = "Private" if self.key.is_private else "Public"
        type_label = Gtk.Label(
            label=type_text,
            css_classes=["caption"],
        )
        if self.key.is_private:
            type_label.add_css_class("accent")
        status_box.append(type_label)

        # Status label
        status_label = Gtk.Label(
            label=self.key.status_text,
            css_classes=["caption"],
        )
        if self.key.is_revoked or self.key.is_expired:
            status_label.add_css_class("error")
        else:
            status_label.add_css_class("success")
        status_box.append(status_label)

        box.append(status_box)


class KeyGenerationDialog(Adw.Window):
    """
    Dialog for generating a new PGP key pair.
    """

    __gtype_name__ = "KeyGenerationDialog"

    __gsignals__ = {
        "key-generated": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }

    def __init__(self, parent: Gtk.Window) -> None:
        """
        Initialize key generation dialog.

        Args:
            parent: Parent window.
        """
        super().__init__(
            title="Generate PGP Key",
            modal=True,
            transient_for=parent,
            default_width=450,
            default_height=500,
        )

        self._build_ui()

    def _build_ui(self) -> None:
        """Build dialog UI."""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar
        header = Adw.HeaderBar()
        header.add_css_class("flat")

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda _: self.close())
        header.pack_start(cancel_button)

        generate_button = Gtk.Button(label="Generate")
        generate_button.add_css_class("suggested-action")
        generate_button.connect("clicked", self._on_generate_clicked)
        self._generate_button = generate_button
        header.pack_end(generate_button)

        main_box.append(header)

        # Content
        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
            margin_start=24,
            margin_end=24,
            margin_top=24,
            margin_bottom=24,
        )

        # User info group
        user_group = Adw.PreferencesGroup(
            title="User Information",
            description="This information will be embedded in your key",
        )

        # Name entry
        self._name_row = Adw.EntryRow(title="Full Name")
        self._name_row.connect("changed", self._validate_form)
        user_group.add(self._name_row)

        # Email entry
        self._email_row = Adw.EntryRow(title="Email Address")
        self._email_row.connect("changed", self._validate_form)
        user_group.add(self._email_row)

        # Comment entry
        self._comment_row = Adw.EntryRow(title="Comment (optional)")
        user_group.add(self._comment_row)

        content.append(user_group)

        # Key settings group
        key_group = Adw.PreferencesGroup(
            title="Key Settings",
        )

        # Algorithm selection
        algorithm_items = ["RSA", "Ed25519", "ECDSA"]
        algorithm_model = Gtk.StringList.new(algorithm_items)
        self._algorithm_row = Adw.ComboRow(
            title="Algorithm",
            subtitle="Ed25519 is recommended for new keys",
            model=algorithm_model,
            selected=1,  # Default to Ed25519
        )
        self._algorithm_row.connect(
            "notify::selected", self._on_algorithm_changed)
        key_group.add(self._algorithm_row)

        # Key size (only for RSA)
        key_size_items = ["2048", "3072", "4096"]
        key_size_model = Gtk.StringList.new(key_size_items)
        self._key_size_row = Adw.ComboRow(
            title="Key Size",
            subtitle="Larger keys are more secure but slower",
            model=key_size_model,
            selected=2,  # Default to 4096
        )
        self._key_size_row.set_visible(False)  # Hidden by default (Ed25519)
        key_group.add(self._key_size_row)

        # Expiration
        expiry_items = ["Never", "1 Year", "2 Years", "5 Years"]
        expiry_model = Gtk.StringList.new(expiry_items)
        self._expiry_row = Adw.ComboRow(
            title="Expiration",
            subtitle="Keys can be extended before they expire",
            model=expiry_model,
            selected=2,  # Default to 2 years
        )
        key_group.add(self._expiry_row)

        content.append(key_group)

        # Passphrase group
        pass_group = Adw.PreferencesGroup(
            title="Passphrase",
            description="Choose a strong passphrase to protect your private key",
        )

        # Passphrase entry
        self._passphrase_row = Adw.PasswordEntryRow(title="Passphrase")
        self._passphrase_row.connect("changed", self._validate_form)
        pass_group.add(self._passphrase_row)

        # Confirm passphrase
        self._confirm_row = Adw.PasswordEntryRow(title="Confirm Passphrase")
        self._confirm_row.connect("changed", self._validate_form)
        pass_group.add(self._confirm_row)

        content.append(pass_group)

        # Progress section (hidden initially)
        self._progress_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            visible=False,
        )

        self._progress_bar = Gtk.ProgressBar(
            show_text=True,
            text="Generating key...",
        )
        self._progress_box.append(self._progress_bar)

        self._progress_label = Gtk.Label(
            label="This may take a moment...",
            css_classes=["dim-label"],
        )
        self._progress_box.append(self._progress_label)

        content.append(self._progress_box)

        main_box.append(content)

        # Initial validation
        self._validate_form()

    def _on_algorithm_changed(
        self,
        row: Adw.ComboRow,
        param: GObject.ParamSpec,
    ) -> None:
        """Handle algorithm selection change."""
        selected = row.get_selected()
        # Show key size only for RSA (index 0)
        self._key_size_row.set_visible(selected == 0)

    def _validate_form(self, *args) -> None:
        """Validate form and enable/disable generate button."""
        name = self._name_row.get_text().strip()
        email = self._email_row.get_text().strip()
        passphrase = self._passphrase_row.get_text()
        confirm = self._confirm_row.get_text()

        is_valid = (
            len(name) >= 2
            and "@" in email
            and "." in email
            and len(passphrase) >= 8
            and passphrase == confirm
        )

        self._generate_button.set_sensitive(is_valid)

    def _on_generate_clicked(self, button: Gtk.Button) -> None:
        """Handle generate button click."""
        # Show progress
        self._progress_box.set_visible(True)
        self._generate_button.set_sensitive(False)

        # Simulate key generation (in real implementation, call GPG)
        self._progress_bar.set_fraction(0.0)

        def update_progress() -> bool:
            current = self._progress_bar.get_fraction()
            if current < 1.0:
                self._progress_bar.set_fraction(current + 0.1)
                return True
            else:
                self._on_generation_complete()
                return False

        GLib.timeout_add(200, update_progress)

    def _on_generation_complete(self) -> None:
        """Handle key generation completion."""
        # Create mock key for demonstration
        key = PGPKey(
            key_id="ABCD1234EFGH5678",
            fingerprint="ABCD1234EFGH5678IJKL9012MNOP3456QRST7890",
            user_id=self._name_row.get_text(),
            email=self._email_row.get_text(),
            algorithm=["RSA", "Ed25519",
                       "ECDSA"][self._algorithm_row.get_selected()],
            key_size=[2048, 3072, 4096][self._key_size_row.get_selected()]
            if self._algorithm_row.get_selected() == 0
            else 256,
            created=datetime.now(),
            expires=None,  # Would calculate based on expiry selection
            is_private=True,
            trust_level=KeyTrustLevel.ULTIMATE,
        )

        self.emit("key-generated", key)
        self.close()


class KeyDetailsDialog(Adw.Window):
    """
    Dialog showing detailed information about a PGP key.
    """

    __gtype_name__ = "KeyDetailsDialog"

    def __init__(self, parent: Gtk.Window, key: PGPKey) -> None:
        """
        Initialize key details dialog.

        Args:
            parent: Parent window.
            key: The key to display.
        """
        super().__init__(
            title="Key Details",
            modal=True,
            transient_for=parent,
            default_width=500,
            default_height=550,
        )

        self.key = key
        self._build_ui()

    def _build_ui(self) -> None:
        """Build dialog UI."""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar
        header = Adw.HeaderBar()
        header.add_css_class("flat")

        close_button = Gtk.Button(label="Close")
        close_button.connect("clicked", lambda _: self.close())
        header.pack_start(close_button)

        main_box.append(header)

        # Scrollable content
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

        # Key header
        key_header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=16,
        )

        icon_name = "dialog-password-symbolic" if self.key.is_private else "security-high-symbolic"
        icon = Gtk.Image(
            icon_name=icon_name,
            pixel_size=48,
        )
        key_header.append(icon)

        header_info = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
        )
        header_info.append(
            Gtk.Label(
                label=self.key.user_id or self.key.email,
                xalign=0,
                css_classes=["title-2"],
            )
        )

        type_text = "Private Key" if self.key.is_private else "Public Key"
        header_info.append(
            Gtk.Label(
                label=f"{type_text} - {self.key.status_text}",
                xalign=0,
                css_classes=["dim-label"],
            )
        )
        key_header.append(header_info)

        content.append(key_header)

        # Fingerprint section
        fp_group = Adw.PreferencesGroup(
            title="Fingerprint",
            description="Verify this matches the owner's fingerprint",
        )

        fp_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )

        fp_label = Gtk.Label(
            label=self.key.formatted_fingerprint,
            selectable=True,
            css_classes=["monospace"],
            wrap=True,
            xalign=0,
            hexpand=True,
        )
        fp_box.append(fp_label)

        copy_button = Gtk.Button(
            icon_name="edit-copy-symbolic",
            tooltip_text="Copy fingerprint",
            valign=Gtk.Align.START,
        )
        copy_button.add_css_class("flat")
        copy_button.connect("clicked", self._on_copy_fingerprint)
        fp_box.append(copy_button)

        # Wrap in a container for the group
        fp_container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            margin_start=12,
            margin_end=12,
            margin_top=8,
            margin_bottom=8,
        )
        fp_container.append(fp_box)
        fp_group.add(fp_container)

        content.append(fp_group)

        # Key details group
        details_group = Adw.PreferencesGroup(
            title="Key Information",
        )

        details_group.add(self._create_info_row("Key ID", self.key.key_id))
        details_group.add(self._create_info_row(
            "Algorithm", self.key.algorithm))
        details_group.add(self._create_info_row(
            "Key Size", f"{self.key.key_size} bits"))
        details_group.add(
            self._create_info_row(
                "Created",
                self.key.created.strftime("%B %d, %Y"),
            )
        )
        details_group.add(
            self._create_info_row(
                "Expires",
                self.key.expires.strftime(
                    "%B %d, %Y") if self.key.expires else "Never",
            )
        )
        details_group.add(
            self._create_info_row(
                "Trust Level",
                self.key.trust_level.to_display_string(),
            )
        )

        content.append(details_group)

        # Trust level selection (only for public keys)
        if not self.key.is_private:
            trust_group = Adw.PreferencesGroup(
                title="Trust Settings",
                description="How much do you trust this key's owner?",
            )

            trust_items = ["Unknown", "Never Trust",
                           "Marginal", "Full", "Ultimate"]
            trust_model = Gtk.StringList.new(trust_items)
            trust_row = Adw.ComboRow(
                title="Trust Level",
                model=trust_model,
                selected=int(self.key.trust_level),
            )
            trust_row.connect("notify::selected", self._on_trust_changed)
            trust_group.add(trust_row)

            content.append(trust_group)

        # Actions
        actions_group = Adw.PreferencesGroup(
            title="Actions",
        )

        export_row = Adw.ActionRow(
            title="Export Key",
            subtitle="Export this key to a file",
            activatable=True,
        )
        export_row.add_suffix(
            Gtk.Image(icon_name="go-next-symbolic")
        )
        export_row.connect("activated", self._on_export_clicked)
        actions_group.add(export_row)

        if self.key.is_private:
            backup_row = Adw.ActionRow(
                title="Backup Private Key",
                subtitle="Create an encrypted backup",
                activatable=True,
            )
            backup_row.add_suffix(
                Gtk.Image(icon_name="go-next-symbolic")
            )
            backup_row.connect("activated", self._on_backup_clicked)
            actions_group.add(backup_row)

        delete_row = Adw.ActionRow(
            title="Delete Key",
            subtitle="Permanently remove this key",
            activatable=True,
            css_classes=["error"],
        )
        delete_row.add_suffix(
            Gtk.Image(icon_name="go-next-symbolic")
        )
        delete_row.connect("activated", self._on_delete_clicked)
        actions_group.add(delete_row)

        content.append(actions_group)

        scrolled.set_child(content)
        main_box.append(scrolled)

    def _create_info_row(self, title: str, value: str) -> Adw.ActionRow:
        """Create an info display row."""
        row = Adw.ActionRow(
            title=title,
        )
        label = Gtk.Label(
            label=value,
            selectable=True,
            css_classes=["dim-label"],
        )
        row.add_suffix(label)
        return row

    def _on_copy_fingerprint(self, button: Gtk.Button) -> None:
        """Copy fingerprint to clipboard."""
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(self.key.formatted_fingerprint)

        # Show feedback
        button.set_icon_name("emblem-ok-symbolic")
        GLib.timeout_add(1500, lambda: button.set_icon_name(
            "edit-copy-symbolic") or False)

    def _on_trust_changed(
        self,
        row: Adw.ComboRow,
        param: GObject.ParamSpec,
    ) -> None:
        """Handle trust level change."""
        self.key.trust_level = KeyTrustLevel(row.get_selected())
        logger.info(
            f"Trust level changed to: {self.key.trust_level.to_display_string()}")

    def _on_export_clicked(self, row: Adw.ActionRow) -> None:
        """Handle export button click."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Export Key")

        default_name = f"{self.key.short_key_id}_public.asc"
        if self.key.is_private:
            default_name = f"{self.key.short_key_id}_secret.asc"

        dialog.set_initial_name(default_name)

        dialog.save(self, None, self._on_export_response)

    def _on_export_response(
        self,
        dialog: Gtk.FileDialog,
        result: Gio.AsyncResult,
    ) -> None:
        """Handle export dialog response."""
        try:
            file = dialog.save_finish(result)
            if file:
                path = file.get_path()
                logger.info(f"Exporting key to: {path}")
                # In real implementation, export key to file
        except GLib.Error as e:
            if e.code != Gtk.DialogError.CANCELLED:
                logger.error(f"Export failed: {e.message}")

    def _on_backup_clicked(self, row: Adw.ActionRow) -> None:
        """Handle backup button click."""
        logger.info("Backup key clicked")
        # Would show backup dialog

    def _on_delete_clicked(self, row: Adw.ActionRow) -> None:
        """Handle delete button click."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Delete Key?",
            body="This action cannot be undone. Make sure you have a backup if needed.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance(
            "delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._on_delete_response)
        dialog.present()

    def _on_delete_response(
        self,
        dialog: Adw.MessageDialog,
        response: str,
    ) -> None:
        """Handle delete confirmation response."""
        if response == "delete":
            logger.info(f"Deleting key: {self.key.key_id}")
            self.close()


class PGPKeyManager(Gtk.Box):
    """
    Widget for managing PGP keys.

    Provides functionality to:
    - View list of keys
    - Generate new key pairs
    - Import/export keys
    - View key details and fingerprints
    - Set key trust levels
    """

    __gtype_name__ = "PGPKeyManager"

    __gsignals__ = {
        "key-selected": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "key-generated": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "key-imported": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "key-deleted": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self) -> None:
        """Initialize the PGP key manager widget."""
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )

        self._keys: list[PGPKey] = []
        self._selected_key: Optional[PGPKey] = None
        self._parent_window: Optional[Gtk.Window] = None

        self._build_ui()
        self._load_sample_keys()

    def _build_ui(self) -> None:
        """Build the widget UI."""
        # Toolbar
        toolbar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_start=12,
            margin_end=12,
            margin_top=8,
            margin_bottom=8,
        )

        # Generate button
        generate_button = Gtk.Button(
            icon_name="list-add-symbolic",
            tooltip_text="Generate new key pair",
        )
        generate_button.connect("clicked", self._on_generate_clicked)
        toolbar.append(generate_button)

        # Import button
        import_button = Gtk.Button(
            icon_name="document-open-symbolic",
            tooltip_text="Import key",
        )
        import_button.connect("clicked", self._on_import_clicked)
        toolbar.append(import_button)

        # Spacer
        toolbar.append(Gtk.Box(hexpand=True))

        # Search entry
        self._search_entry = Gtk.SearchEntry(
            placeholder_text="Search keys...",
        )
        self._search_entry.connect("search-changed", self._on_search_changed)
        toolbar.append(self._search_entry)

        # Filter dropdown
        filter_items = ["All Keys", "Private Keys", "Public Keys"]
        filter_model = Gtk.StringList.new(filter_items)
        self._filter_dropdown = Gtk.DropDown(
            model=filter_model,
            tooltip_text="Filter keys",
        )
        self._filter_dropdown.connect(
            "notify::selected", self._on_filter_changed)
        toolbar.append(self._filter_dropdown)

        self.append(toolbar)

        # Separator
        self.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Key list
        self._scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )

        self._list_box = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.SINGLE,
            css_classes=["boxed-list"],
        )
        self._list_box.connect("row-activated", self._on_row_activated)

        self._scrolled.set_child(self._list_box)
        self.append(self._scrolled)

        # Empty state (shown when no keys)
        self._empty_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            margin_top=48,
            margin_bottom=48,
        )

        empty_icon = Gtk.Image(
            icon_name="security-high-symbolic",
            pixel_size=64,
            css_classes=["dim-label"],
        )
        self._empty_box.append(empty_icon)

        empty_label = Gtk.Label(
            label="No PGP Keys",
            css_classes=["title-2"],
        )
        self._empty_box.append(empty_label)

        empty_sublabel = Gtk.Label(
            label="Generate or import a key to get started",
            css_classes=["dim-label"],
        )
        self._empty_box.append(empty_sublabel)

        generate_empty_button = Gtk.Button(
            label="Generate Key",
            css_classes=["suggested-action", "pill"],
        )
        generate_empty_button.connect("clicked", self._on_generate_clicked)
        self._empty_box.append(generate_empty_button)

        self._scrolled.set_child(self._empty_box)

    def _load_sample_keys(self) -> None:
        """Load sample keys for demonstration."""
        sample_keys = [
            PGPKey(
                key_id="ABCD1234EFGH5678",
                fingerprint="ABCD1234EFGH5678IJKL9012MNOP3456QRST7890",
                user_id="John Doe",
                email="john@example.com",
                algorithm="Ed25519",
                key_size=256,
                created=datetime(2025, 6, 15),
                expires=datetime(2028, 6, 15),
                is_private=True,
                trust_level=KeyTrustLevel.ULTIMATE,
            ),
            PGPKey(
                key_id="1234ABCD5678EFGH",
                fingerprint="1234ABCD5678EFGHIJKL9012MNOP3456QRST7890",
                user_id="Alice Smith",
                email="alice@example.com",
                algorithm="RSA",
                key_size=4096,
                created=datetime(2025, 1, 1),
                expires=datetime(2028, 1, 1),
                is_private=False,
                trust_level=KeyTrustLevel.FULL,
            ),
            PGPKey(
                key_id="5678EFGH1234ABCD",
                fingerprint="5678EFGH1234ABCDIJKL9012MNOP3456QRST7890",
                user_id="Bob Wilson",
                email="bob@example.com",
                algorithm="RSA",
                key_size=2048,
                created=datetime(2024, 3, 10),
                expires=datetime(2025, 3, 10),
                is_private=False,
                trust_level=KeyTrustLevel.MARGINAL,
                is_expired=True,  # Deliberately expired for demo purposes
            ),
        ]

        for key in sample_keys:
            self.add_key(key)

    def set_parent_window(self, window: Gtk.Window) -> None:
        """Set the parent window for dialogs."""
        self._parent_window = window

    def add_key(self, key: PGPKey) -> None:
        """Add a key to the manager."""
        self._keys.append(key)
        self._refresh_list()

    def remove_key(self, key_id: str) -> None:
        """Remove a key by ID."""
        self._keys = [k for k in self._keys if k.key_id != key_id]
        self._refresh_list()
        self.emit("key-deleted", key_id)

    def get_keys(self) -> list[PGPKey]:
        """Get all keys."""
        return self._keys.copy()

    def get_private_keys(self) -> list[PGPKey]:
        """Get only private keys."""
        return [k for k in self._keys if k.is_private]

    def get_public_keys(self) -> list[PGPKey]:
        """Get only public keys."""
        return [k for k in self._keys if not k.is_private]

    def _refresh_list(self) -> None:
        """Refresh the key list display."""
        # Clear existing rows
        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)

        # Get filtered keys
        search_text = self._search_entry.get_text().lower()
        filter_mode = self._filter_dropdown.get_selected()

        filtered_keys = []
        for key in self._keys:
            # Apply filter
            if filter_mode == 1 and not key.is_private:
                continue
            if filter_mode == 2 and key.is_private:
                continue

            # Apply search
            if search_text:
                searchable = f"{key.user_id} {key.email} {key.key_id}".lower()
                if search_text not in searchable:
                    continue

            filtered_keys.append(key)

        # Show empty state or list
        if not filtered_keys:
            self._scrolled.set_child(self._empty_box)
        else:
            self._scrolled.set_child(self._list_box)
            for key in filtered_keys:
                row = PGPKeyRow(key)
                self._list_box.append(row)

    def _on_generate_clicked(self, button: Gtk.Button) -> None:
        """Handle generate button click."""
        parent = self._parent_window or self.get_root()
        dialog = KeyGenerationDialog(parent)
        dialog.connect("key-generated", self._on_key_generated)
        dialog.present()

    def _on_key_generated(
        self,
        dialog: KeyGenerationDialog,
        key: PGPKey,
    ) -> None:
        """Handle key generation completion."""
        self.add_key(key)
        self.emit("key-generated", key)
        logger.info(f"Key generated: {key.key_id}")

    def _on_import_clicked(self, button: Gtk.Button) -> None:
        """Handle import button click."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Import PGP Key")

        # Set filter for key files
        filter_store = Gio.ListStore.new(Gtk.FileFilter)

        key_filter = Gtk.FileFilter()
        key_filter.set_name("PGP Keys")
        key_filter.add_pattern("*.asc")
        key_filter.add_pattern("*.gpg")
        key_filter.add_pattern("*.pgp")
        key_filter.add_pattern("*.key")
        filter_store.append(key_filter)

        all_filter = Gtk.FileFilter()
        all_filter.set_name("All Files")
        all_filter.add_pattern("*")
        filter_store.append(all_filter)

        dialog.set_filters(filter_store)

        parent = self._parent_window or self.get_root()
        dialog.open(parent, None, self._on_import_response)

    def _on_import_response(
        self,
        dialog: Gtk.FileDialog,
        result: Gio.AsyncResult,
    ) -> None:
        """Handle import dialog response."""
        try:
            file = dialog.open_finish(result)
            if file:
                path = file.get_path()
                logger.info(f"Importing key from: {path}")

                # In real implementation, parse and import the key
                # For now, create a mock imported key
                imported_key = PGPKey(
                    key_id="IMPORT12345678",
                    fingerprint="IMPORT12345678IJKL9012MNOP3456QRST7890",
                    user_id="Imported Key",
                    email="imported@example.com",
                    algorithm="RSA",
                    key_size=4096,
                    created=datetime.now(),
                    expires=None,
                    is_private=False,
                    trust_level=KeyTrustLevel.UNKNOWN,
                )

                self.add_key(imported_key)
                self.emit("key-imported", imported_key)

        except GLib.Error as e:
            if e.code != Gtk.DialogError.CANCELLED:
                logger.error(f"Import failed: {e.message}")

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Handle search text change."""
        self._refresh_list()

    def _on_filter_changed(
        self,
        dropdown: Gtk.DropDown,
        param: GObject.ParamSpec,
    ) -> None:
        """Handle filter selection change."""
        self._refresh_list()

    def _on_row_activated(
        self,
        list_box: Gtk.ListBox,
        row: PGPKeyRow,
    ) -> None:
        """Handle row activation (double-click or Enter)."""
        if row and hasattr(row, "key"):
            self._selected_key = row.key
            self.emit("key-selected", row.key)

            # Show details dialog
            parent = self._parent_window or self.get_root()
            dialog = KeyDetailsDialog(parent, row.key)
            dialog.present()
