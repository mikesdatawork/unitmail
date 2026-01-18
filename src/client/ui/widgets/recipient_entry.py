"""
Custom recipient entry widget with auto-complete and chip/tag support.
"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject, Gdk, Pango
import re
from typing import List, Optional, Callable


class RecipientChip(Gtk.Box):
    """
    A chip/tag widget representing a single recipient.
    """

    __gsignals__ = {
        "remove-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, email: str, display_name: Optional[str] = None):
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4,
            css_classes=["recipient-chip"],
        )

        self.email = email
        self.display_name = display_name
        self._is_valid = True

        # Display text
        display_text = display_name if display_name else email
        self.label = Gtk.Label(label=display_text)
        self.label.set_ellipsize(Pango.EllipsizeMode.END)
        self.label.set_max_width_chars(25)
        self.label.set_tooltip_text(
            f"{display_name} <{email}>" if display_name else email
        )
        self.append(self.label)

        # Remove button
        remove_button = Gtk.Button()
        remove_button.set_icon_name("window-close-symbolic")
        remove_button.add_css_class("flat")
        remove_button.add_css_class("circular")
        remove_button.set_tooltip_text("Remove recipient")
        remove_button.connect("clicked", self._on_remove_clicked)
        self.append(remove_button)

        self._apply_styles()

    def _apply_styles(self):
        """Apply CSS styles to the chip."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(
            b"""
            .recipient-chip {
                background-color: alpha(@accent_bg_color, 0.3);
                border-radius: 12px;
                padding: 2px 8px;
                margin: 2px;
            }
            .recipient-chip.invalid {
                background-color: alpha(@error_color, 0.3);
            }
            .recipient-chip button {
                min-width: 16px;
                min-height: 16px;
                padding: 0;
            }
        """
        )
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _on_remove_clicked(self, button):
        """Handle remove button click."""
        self.emit("remove-requested")

    def set_valid(self, valid: bool):
        """Set validation state of the chip."""
        self._is_valid = valid
        if valid:
            self.remove_css_class("invalid")
        else:
            self.add_css_class("invalid")

    def is_valid(self) -> bool:
        """Return whether the recipient is valid."""
        return self._is_valid


class RecipientEntry(Gtk.Box):
    """
    Custom entry widget for email recipients with auto-complete,
    multiple recipients as chips/tags, and validation feedback.
    """

    __gsignals__ = {
        "recipients-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "validation-changed": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
    }

    # Email validation pattern
    EMAIL_PATTERN = re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    )

    def __init__(
        self,
        placeholder: str = "Enter recipients...",
        contacts_provider: Optional[Callable[[], List[dict]]] = None,
    ):
        """
        Initialize the recipient entry.

        Args:
            placeholder: Placeholder text for the entry
            contacts_provider: Callable that returns list of contacts
                for auto-complete. Each contact should be dict with
                'email' and optional 'name'
        """
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
            css_classes=["recipient-entry-container"],
        )

        self._recipients: List[dict] = []
        self._contacts_provider = contacts_provider
        self._completion_model: Optional[Gtk.ListStore] = None

        # Scrollable container for chips
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER
        )
        self.scrolled.set_hexpand(True)
        self.scrolled.set_min_content_height(36)

        # Flow box for chips + entry
        self.flow_box = Gtk.FlowBox()
        self.flow_box.set_homogeneous(False)
        self.flow_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flow_box.set_min_children_per_line(1)
        self.flow_box.set_max_children_per_line(100)

        # Entry for typing
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text(placeholder)
        self.entry.set_hexpand(True)
        self.entry.set_width_chars(20)
        self.entry.connect("activate", self._on_entry_activate)
        self.entry.connect("changed", self._on_entry_changed)

        # Key controller for handling special keys
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.entry.add_controller(key_controller)

        # Focus controller for handling focus out
        focus_controller = Gtk.EventControllerFocus()
        focus_controller.connect("leave", self._on_focus_out)
        self.entry.add_controller(focus_controller)

        # Entry wrapper for flow box
        self.entry_child = Gtk.FlowBoxChild()
        self.entry_child.set_child(self.entry)
        self.flow_box.append(self.entry_child)

        self.scrolled.set_child(self.flow_box)
        self.append(self.scrolled)

        # Setup auto-complete
        self._setup_autocomplete()

        # Apply styles
        self._apply_styles()

        # Validation feedback label (hidden by default)
        self.validation_label = Gtk.Label()
        self.validation_label.add_css_class("error")
        self.validation_label.set_visible(False)

    def _apply_styles(self):
        """Apply CSS styles."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(
            b"""
            .recipient-entry-container {
                background-color: @view_bg_color;
                border: 1px solid @borders;
                border-radius: 6px;
                padding: 4px;
                min-height: 32px;
            }
            .recipient-entry-container:focus-within {
                border-color: @accent_bg_color;
            }
            .recipient-entry-container entry {
                border: none;
                background: transparent;
                box-shadow: none;
                min-height: 28px;
            }
        """
        )
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _setup_autocomplete(self):
        """Setup auto-complete for the entry."""
        # Create completion model
        self._completion_model = Gtk.ListStore(str, str)  # email, display_name

        # Create entry completion
        completion = Gtk.EntryCompletion()
        completion.set_model(self._completion_model)
        completion.set_text_column(0)
        completion.set_minimum_key_length(1)
        completion.set_popup_completion(True)
        completion.set_inline_completion(False)

        # Custom match function
        completion.set_match_func(self._match_func, None)

        # Custom cell rendering
        renderer = Gtk.CellRendererText()
        completion.pack_start(renderer, True)
        completion.add_attribute(renderer, "text", 1)

        completion.connect("match-selected", self._on_match_selected)

        self.entry.set_completion(completion)

        # Populate with contacts if provider available
        self._refresh_contacts()

    def _refresh_contacts(self):
        """Refresh the contacts list from the provider."""
        if self._completion_model is None:
            return

        self._completion_model.clear()

        if self._contacts_provider:
            contacts = self._contacts_provider()
            for contact in contacts:
                email = contact.get("email", "")
                name = contact.get("name", "")
                display = f"{name} <{email}>" if name else email
                self._completion_model.append([email, display])

    def _match_func(self, completion, key, iter, data):
        """Custom match function for auto-complete."""
        model = completion.get_model()
        email = model.get_value(iter, 0).lower()
        display = model.get_value(iter, 1).lower()
        key = key.lower()
        return key in email or key in display

    def _on_match_selected(self, completion, model, iter):
        """Handle selection from auto-complete."""
        email = model.get_value(iter, 0)
        display = model.get_value(iter, 1)

        # Extract name from display if present
        name = None
        if "<" in display and ">" in display:
            name = display.split("<")[0].strip()

        self._add_recipient(email, name)
        self.entry.set_text("")
        return True

    def _on_entry_activate(self, entry):
        """Handle Enter key in entry."""
        text = entry.get_text().strip()
        if text:
            self._process_input(text)
            entry.set_text("")

    def _on_entry_changed(self, entry):
        """Handle text changes in entry."""
        text = entry.get_text()

        # Check for comma or semicolon separators
        if "," in text or ";" in text:
            parts = re.split(r"[,;]", text)
            for part in parts[:-1]:
                part = part.strip()
                if part:
                    self._process_input(part)
            # Keep the last part in the entry
            entry.set_text(parts[-1].strip())

    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key presses."""
        if keyval == Gdk.KEY_BackSpace:
            text = self.entry.get_text()
            if not text and self._recipients:
                # Remove last recipient
                self._remove_recipient_at(-1)
                return True
        elif keyval == Gdk.KEY_Tab:
            text = self.entry.get_text().strip()
            if text:
                self._process_input(text)
                self.entry.set_text("")
                return True
        return False

    def _on_focus_out(self, controller):
        """Handle focus leaving the entry."""
        text = self.entry.get_text().strip()
        if text:
            self._process_input(text)
            self.entry.set_text("")

    def _process_input(self, text: str):
        """Process input text and add as recipient."""
        # Extract email from "Name <email>" format
        email = text
        name = None

        match = re.match(r"^(.+?)\s*<([^>]+)>$", text)
        if match:
            name = match.group(1).strip()
            email = match.group(2).strip()

        self._add_recipient(email, name)

    def _add_recipient(self, email: str, name: Optional[str] = None):
        """Add a recipient."""
        # Check for duplicates
        for recipient in self._recipients:
            if recipient["email"].lower() == email.lower():
                return

        # Validate email
        is_valid = bool(self.EMAIL_PATTERN.match(email))

        # Create chip
        chip = RecipientChip(email, name)
        chip.set_valid(is_valid)
        chip.connect("remove-requested", self._on_chip_remove_requested)

        # Add to flow box before the entry
        chip_child = Gtk.FlowBoxChild()
        chip_child.set_child(chip)

        # Insert before entry
        position = len(self._recipients)
        self.flow_box.insert(chip_child, position)

        # Store recipient
        self._recipients.append(
            {
                "email": email,
                "name": name,
                "chip": chip,
                "child": chip_child,
                "valid": is_valid,
            }
        )

        self.emit("recipients-changed")
        self._emit_validation_status()

    def _on_chip_remove_requested(self, chip):
        """Handle chip removal request."""
        for i, recipient in enumerate(self._recipients):
            if recipient["chip"] == chip:
                self._remove_recipient_at(i)
                break

    def _remove_recipient_at(self, index: int):
        """Remove recipient at index."""
        if not self._recipients:
            return

        recipient = self._recipients.pop(index)
        self.flow_box.remove(recipient["child"])

        self.emit("recipients-changed")
        self._emit_validation_status()

    def _emit_validation_status(self):
        """Emit validation status."""
        all_valid = all(r["valid"] for r in self._recipients)
        self.emit("validation-changed", all_valid)

    def get_recipients(self) -> List[str]:
        """Get list of recipient email addresses."""
        return [r["email"] for r in self._recipients]

    def get_recipients_formatted(self) -> List[str]:
        """Get list of formatted recipient strings."""
        result = []
        for r in self._recipients:
            if r["name"]:
                result.append(f"{r['name']} <{r['email']}>")
            else:
                result.append(r["email"])
        return result

    def set_recipients(self, recipients: List[str]):
        """Set recipients from list of email strings."""
        # Clear existing
        self.clear()

        # Add new recipients
        for recipient in recipients:
            self._process_input(recipient)

    def clear(self):
        """Clear all recipients."""
        while self._recipients:
            self._remove_recipient_at(0)
        self.entry.set_text("")

    def is_valid(self) -> bool:
        """Check if all recipients are valid."""
        return all(r["valid"] for r in self._recipients)

    def has_recipients(self) -> bool:
        """Check if there are any recipients."""
        return len(self._recipients) > 0

    def set_contacts_provider(self, provider: Callable[[], List[dict]]):
        """Set the contacts provider for auto-complete."""
        self._contacts_provider = provider
        self._refresh_contacts()

    def refresh_autocomplete(self):
        """Refresh auto-complete suggestions."""
        self._refresh_contacts()
