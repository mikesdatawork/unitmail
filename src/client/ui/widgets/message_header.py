"""
Message header widget for unitMail.

This module provides a widget for displaying email message headers
with expandable details to show all headers.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import cairo

from client.services.date_format_service import get_date_format_service

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
gi.require_version("Pango", "1.0")

from gi.repository import GLib, GObject, Gtk, Pango


def format_email_address(email: str, name: Optional[str] = None) -> str:
    """Format an email address with optional display name.

    Args:
        email: The email address.
        name: Optional display name.

    Returns:
        Formatted email string.
    """
    if name:
        return f"{name} <{email}>"
    return email


def format_date_time(dt: datetime | str | None) -> str:
    """Format a datetime for display using the centralized DateFormatService.

    Args:
        dt: The datetime to format.

    Returns:
        Formatted date/time string respecting user's date format preference.
    """
    if dt is None:
        return ""

    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return dt

    # Use centralized DateFormatService to respect user's format preference
    try:
        date_service = get_date_format_service()
        return date_service.format_date_with_time(dt)
    except Exception:
        # Fallback if service unavailable
        return dt.strftime("%Y-%m-%d %H:%M")


def get_initials(name: str) -> str:
    """Get initials from a name for avatar display.

    Args:
        name: The name to get initials from.

    Returns:
        Up to 2 initials.
    """
    if not name:
        return "?"

    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    elif parts:
        return parts[0][0].upper()
    return "?"


def get_avatar_color(email: str) -> str:
    """Generate a consistent color based on email address.

    Args:
        email: The email address.

    Returns:
        CSS color string.
    """
    # Simple hash-based color generation
    colors = [
        "#e91e63",  # Pink
        "#9c27b0",  # Purple
        "#673ab7",  # Deep Purple
        "#3f51b5",  # Indigo
        "#2196f3",  # Blue
        "#03a9f4",  # Light Blue
        "#00bcd4",  # Cyan
        "#009688",  # Teal
        "#4caf50",  # Green
        "#8bc34a",  # Light Green
        "#ff9800",  # Orange
        "#ff5722",  # Deep Orange
    ]

    hash_value = sum(ord(c) for c in email.lower())
    return colors[hash_value % len(colors)]


class AvatarWidget(Gtk.DrawingArea):
    """A circular avatar widget with initials."""

    __gtype_name__ = "AvatarWidget"

    def __init__(
        self,
        text: str = "?",
        color: str = "#3f51b5",
        size: int = 40,
    ) -> None:
        """Initialize the avatar widget.

        Args:
            text: Text to display (usually initials).
            color: Background color.
            size: Avatar size in pixels.
        """
        super().__init__()

        self._text = text[:2]  # Max 2 characters
        self._color = color
        self._size = size

        self.set_size_request(size, size)
        self.set_draw_func(self._draw)

    def _draw(
        self,
        area: Gtk.DrawingArea,
        cr: "cairo.Context",
        width: int,
        height: int,
    ) -> None:
        """Draw the avatar.

        Args:
            area: The drawing area.
            cr: Cairo context.
            width: Available width.
            height: Available height.
        """
        import cairo

        # Parse color
        color = self._parse_color(self._color)

        # Draw circle
        radius = min(width, height) / 2
        center_x = width / 2
        center_y = height / 2

        cr.arc(center_x, center_y, radius, 0, 2 * 3.14159)
        cr.set_source_rgb(*color)
        cr.fill()

        # Draw text
        cr.set_source_rgb(1, 1, 1)  # White text
        cr.select_font_face(
            "Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD
        )
        cr.set_font_size(radius * 0.8)

        # Center the text
        extents = cr.text_extents(self._text)
        x = center_x - (extents.width / 2 + extents.x_bearing)
        y = center_y - (extents.height / 2 + extents.y_bearing)

        cr.move_to(x, y)
        cr.show_text(self._text)

    def _parse_color(self, color: str) -> tuple[float, float, float]:
        """Parse a hex color string to RGB floats.

        Args:
            color: Hex color string (e.g., "#3f51b5").

        Returns:
            Tuple of RGB values (0-1).
        """
        color = color.lstrip("#")
        if len(color) == 6:
            r = int(color[0:2], 16) / 255
            g = int(color[2:4], 16) / 255
            b = int(color[4:6], 16) / 255
            return (r, g, b)
        return (0.5, 0.5, 0.5)  # Default gray

    def set_text(self, text: str) -> None:
        """Set the avatar text.

        Args:
            text: New text to display.
        """
        self._text = text[:2]
        self.queue_draw()

    def set_color(self, color: str) -> None:
        """Set the avatar color.

        Args:
            color: New color (hex string).
        """
        self._color = color
        self.queue_draw()


class RecipientChip(Gtk.Box):
    """A chip widget for displaying an email recipient."""

    __gtype_name__ = "RecipientChip"

    def __init__(self, email: str, name: Optional[str] = None) -> None:
        """Initialize the recipient chip.

        Args:
            email: The email address.
            name: Optional display name.
        """
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4,
        )

        self._email = email
        self._name = name

        self.add_css_class("recipient-chip")

        # Small avatar
        initials = get_initials(name or email.split("@")[0])
        color = get_avatar_color(email)

        avatar = AvatarWidget(text=initials, color=color, size=20)
        self.append(avatar)

        # Label
        display_text = name if name else email
        label = Gtk.Label(
            label=display_text,
            ellipsize=3,  # PANGO_ELLIPSIZE_END
            max_width_chars=25,
        )
        label.set_tooltip_text(email if name else None)
        self.append(label)

    @property
    def email(self) -> str:
        """Get the email address."""
        return self._email

    @property
    def name(self) -> Optional[str]:
        """Get the display name."""
        return self._name


class MessageHeader(Gtk.Box):
    """Widget for displaying email message headers."""

    __gtype_name__ = "MessageHeader"

    __gsignals__ = {
        "sender-clicked": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "recipient-clicked": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self) -> None:
        """Initialize the message header widget."""
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
        )

        self._from_address: str = ""
        self._from_name: Optional[str] = None
        self._to_addresses: list[str] = []
        self._cc_addresses: list[str] = []
        self._subject: str = ""
        self._date: Optional[datetime] = None
        self._attachment_count: int = 0
        self._headers: dict[str, str] = {}
        self._expanded: bool = False
        # Security status
        self._is_encrypted: bool = False
        self._is_signed: bool = False
        self._signature_valid: Optional[bool] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.add_css_class("message-header")

        # Main header area
        main_header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
        )
        main_header.add_css_class("message-header-main")

        # Avatar
        self._avatar = AvatarWidget(text="?", size=48)
        main_header.append(self._avatar)

        # Info container
        info_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            hexpand=True,
        )

        # From row
        from_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )

        self._from_label = Gtk.Label(
            label="",
            xalign=0,
            ellipsize=3,  # PANGO_ELLIPSIZE_END
            hexpand=True,
        )
        self._from_label.add_css_class("message-from")
        from_row.append(self._from_label)

        # Date label
        self._date_label = Gtk.Label(
            label="",
            xalign=1,
        )
        self._date_label.add_css_class("message-date")
        self._date_label.add_css_class("dim-label")
        from_row.append(self._date_label)

        info_box.append(from_row)

        # Subject
        self._subject_label = Gtk.Label(
            label="",
            xalign=0,
            ellipsize=3,  # PANGO_ELLIPSIZE_END
            selectable=True,
        )
        self._subject_label.add_css_class("message-subject")
        info_box.append(self._subject_label)

        # To row
        self._to_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4,
        )

        to_label = Gtk.Label(label="To:")
        to_label.add_css_class("dim-label")
        self._to_box.append(to_label)

        self._to_flow = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE,
            homogeneous=False,
            min_children_per_line=1,
            max_children_per_line=10,
            row_spacing=4,
            column_spacing=4,
            hexpand=True,
        )
        self._to_box.append(self._to_flow)

        info_box.append(self._to_box)

        # CC row (hidden by default)
        self._cc_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4,
        )
        self._cc_box.set_visible(False)

        cc_label = Gtk.Label(label="Cc:")
        cc_label.add_css_class("dim-label")
        self._cc_box.append(cc_label)

        self._cc_flow = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE,
            homogeneous=False,
            min_children_per_line=1,
            max_children_per_line=10,
            row_spacing=4,
            column_spacing=4,
            hexpand=True,
        )
        self._cc_box.append(self._cc_flow)

        info_box.append(self._cc_box)

        # Attachment indicator
        self._attachment_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4,
        )
        self._attachment_box.set_visible(False)

        attachment_icon = Gtk.Image.new_from_icon_name(
            "mail-attachment-symbolic"
        )
        attachment_icon.set_pixel_size(16)
        self._attachment_box.append(attachment_icon)

        self._attachment_label = Gtk.Label(label="")
        self._attachment_label.add_css_class("dim-label")
        self._attachment_box.append(self._attachment_label)

        info_box.append(self._attachment_box)

        # Security status indicators (encryption/signing)
        self._security_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
        )
        self._security_box.set_visible(False)

        # Encryption indicator
        self._encryption_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4,
        )
        self._encryption_box.set_visible(False)
        self._encryption_icon = Gtk.Image.new_from_icon_name(
            "channel-secure-symbolic"
        )
        self._encryption_icon.set_pixel_size(16)
        self._encryption_box.append(self._encryption_icon)
        self._encryption_label = Gtk.Label(label="Encrypted")
        self._encryption_label.add_css_class("security-indicator")
        self._encryption_label.add_css_class("encrypted")
        self._encryption_box.append(self._encryption_label)
        self._security_box.append(self._encryption_box)

        # Signature indicator
        self._signature_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4,
        )
        self._signature_box.set_visible(False)
        self._signature_icon = Gtk.Image.new_from_icon_name(
            "security-high-symbolic"
        )
        self._signature_icon.set_pixel_size(16)
        self._signature_box.append(self._signature_icon)
        self._signature_label = Gtk.Label(label="Signed")
        self._signature_label.add_css_class("security-indicator")
        self._signature_box.append(self._signature_label)
        self._security_box.append(self._signature_box)

        info_box.append(self._security_box)

        main_header.append(info_box)
        self.append(main_header)

        # Expand button for full headers
        self._expand_button = Gtk.Button.new_from_icon_name(
            "pan-down-symbolic"
        )
        self._expand_button.set_tooltip_text("Show all headers")
        self._expand_button.add_css_class("flat")
        self._expand_button.add_css_class("circular")
        self._expand_button.connect("clicked", self._on_expand_clicked)
        main_header.append(self._expand_button)

        # Expandable headers section
        self._headers_revealer = Gtk.Revealer(
            transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
            transition_duration=200,
        )

        self._headers_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            margin_start=60,
            margin_top=8,
        )
        self._headers_box.add_css_class("message-headers-expanded")

        self._headers_revealer.set_child(self._headers_box)
        self.append(self._headers_revealer)

    def set_message(
        self,
        from_address: str,
        to_addresses: list[str],
        subject: str,
        date: Optional[datetime | str] = None,
        cc_addresses: Optional[list[str]] = None,
        from_name: Optional[str] = None,
        attachment_count: int = 0,
        headers: Optional[dict[str, str]] = None,
        is_encrypted: bool = False,
        is_signed: bool = False,
        signature_valid: Optional[bool] = None,
    ) -> None:
        """Set the message data to display.

        Args:
            from_address: Sender email address.
            to_addresses: List of recipient email addresses.
            subject: Message subject.
            date: Message date/time.
            cc_addresses: Optional list of CC addresses.
            from_name: Optional sender display name.
            attachment_count: Number of attachments.
            headers: Optional dict of all headers.
            is_encrypted: Whether the message is encrypted.
            is_signed: Whether the message is digitally signed.
            signature_valid: Whether the signature is valid (None if not verified).
        """
        self._from_address = from_address
        self._from_name = from_name
        self._to_addresses = to_addresses
        self._cc_addresses = cc_addresses or []
        self._subject = subject
        self._attachment_count = attachment_count
        self._headers = headers or {}
        self._is_encrypted = is_encrypted
        self._is_signed = is_signed
        self._signature_valid = signature_valid

        if isinstance(date, str):
            try:
                self._date = datetime.fromisoformat(
                    date.replace("Z", "+00:00")
                )
            except ValueError:
                self._date = None
        else:
            self._date = date

        self._update_display()

    def set_from_message_model(self, message: Any) -> None:
        """Set header data from a Message model.

        Args:
            message: A Message model instance.
        """
        self.set_message(
            from_address=message.from_address,
            to_addresses=list(message.to_addresses),
            subject=message.subject,
            date=message.received_at or message.sent_at or message.created_at,
            cc_addresses=(
                list(message.cc_addresses) if message.cc_addresses else None
            ),
            attachment_count=(
                len(message.attachments) if message.attachments else 0
            ),
            headers=dict(message.headers) if message.headers else None,
        )

    def _update_display(self) -> None:
        """Update the display with current data."""
        # Update avatar
        initials = get_initials(
            self._from_name or self._from_address.split("@")[0]
        )
        color = get_avatar_color(self._from_address)
        self._avatar.set_text(initials)
        self._avatar.set_color(color)

        # Update from label
        if self._from_name:
            self._from_label.set_markup(
                f"<b>{GLib.markup_escape_text(self._from_name)}</b> "
                f"<span size='small'>&lt;{
                    GLib.markup_escape_text(
                        self._from_address)}&gt;</span>"
            )
        else:
            self._from_label.set_markup(
                f"<b>{GLib.markup_escape_text(self._from_address)}</b>"
            )

        # Update subject
        self._subject_label.set_label(self._subject or "(No subject)")

        # Update date
        if self._date:
            self._date_label.set_label(format_date_time(self._date))
        else:
            self._date_label.set_label("")

        # Update To recipients
        self._clear_flow_box(self._to_flow)
        for addr in self._to_addresses:
            chip = RecipientChip(email=addr)
            self._to_flow.append(chip)

        # Update CC recipients
        self._clear_flow_box(self._cc_flow)
        if self._cc_addresses:
            self._cc_box.set_visible(True)
            for addr in self._cc_addresses:
                chip = RecipientChip(email=addr)
                self._cc_flow.append(chip)
        else:
            self._cc_box.set_visible(False)

        # Update attachment indicator
        if self._attachment_count > 0:
            self._attachment_box.set_visible(True)
            attachment_text = (
                f"{self._attachment_count} attachment"
                if self._attachment_count == 1
                else f"{self._attachment_count} attachments"
            )
            self._attachment_label.set_label(attachment_text)
        else:
            self._attachment_box.set_visible(False)

        # Update security status indicators
        self._update_security_indicators()

        # Update expanded headers
        self._update_expanded_headers()

    def _update_security_indicators(self) -> None:
        """Update encryption and signature status indicators."""
        show_security = self._is_encrypted or self._is_signed

        if show_security:
            self._security_box.set_visible(True)

            # Encryption indicator
            if self._is_encrypted:
                self._encryption_box.set_visible(True)
                self._encryption_icon.set_from_icon_name(
                    "channel-secure-symbolic"
                )
                self._encryption_label.set_label("Encrypted")
                self._encryption_box.remove_css_class("security-warning")
                self._encryption_box.add_css_class("security-success")
            else:
                self._encryption_box.set_visible(False)

            # Signature indicator
            if self._is_signed:
                self._signature_box.set_visible(True)
                if self._signature_valid is True:
                    self._signature_icon.set_from_icon_name(
                        "security-high-symbolic"
                    )
                    self._signature_label.set_label("Verified signature")
                    self._signature_box.remove_css_class("security-warning")
                    self._signature_box.remove_css_class("security-error")
                    self._signature_box.add_css_class("security-success")
                elif self._signature_valid is False:
                    self._signature_icon.set_from_icon_name(
                        "security-low-symbolic"
                    )
                    self._signature_label.set_label("Invalid signature")
                    self._signature_box.remove_css_class("security-success")
                    self._signature_box.remove_css_class("security-warning")
                    self._signature_box.add_css_class("security-error")
                else:
                    self._signature_icon.set_from_icon_name(
                        "security-medium-symbolic"
                    )
                    self._signature_label.set_label("Signed (unverified)")
                    self._signature_box.remove_css_class("security-success")
                    self._signature_box.remove_css_class("security-error")
                    self._signature_box.add_css_class("security-warning")
            else:
                self._signature_box.set_visible(False)
        else:
            self._security_box.set_visible(False)

    def _clear_flow_box(self, flow_box: Gtk.FlowBox) -> None:
        """Clear all children from a flow box.

        Args:
            flow_box: The flow box to clear.
        """
        while True:
            child = flow_box.get_first_child()
            if child is None:
                break
            flow_box.remove(child)

    def _update_expanded_headers(self) -> None:
        """Update the expanded headers section."""
        # Clear existing headers
        while True:
            child = self._headers_box.get_first_child()
            if child is None:
                break
            self._headers_box.remove(child)

        # Add header rows
        for key, value in self._headers.items():
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=8,
            )

            key_label = Gtk.Label(
                label=f"{key}:",
                xalign=1,
                width_chars=15,
            )
            key_label.add_css_class("dim-label")
            row.append(key_label)

            value_label = Gtk.Label(
                label=value,
                xalign=0,
                selectable=True,
                wrap=True,
                wrap_mode=Pango.WrapMode.WORD_CHAR,
                hexpand=True,
            )
            row.append(value_label)

            self._headers_box.append(row)

    def _on_expand_clicked(self, button: Gtk.Button) -> None:
        """Handle expand button click."""
        self._expanded = not self._expanded
        self._headers_revealer.set_reveal_child(self._expanded)

        # Update button icon
        icon_name = (
            "pan-up-symbolic" if self._expanded else "pan-down-symbolic"
        )
        button.set_icon_name(icon_name)
        button.set_tooltip_text(
            "Hide headers" if self._expanded else "Show all headers"
        )

    @property
    def from_address(self) -> str:
        """Get the sender address."""
        return self._from_address

    @property
    def subject(self) -> str:
        """Get the subject."""
        return self._subject

    @property
    def is_expanded(self) -> bool:
        """Check if headers are expanded."""
        return self._expanded

    def expand(self) -> None:
        """Expand the headers section."""
        if not self._expanded:
            self._on_expand_clicked(self._expand_button)

    def collapse(self) -> None:
        """Collapse the headers section."""
        if self._expanded:
            self._on_expand_clicked(self._expand_button)

    def get_css(self) -> str:
        """Get CSS styles for the message header widget."""
        return """
        .message-header {
            padding: 16px;
            background-color: @card_bg_color;
            border-bottom: 1px solid @borders;
        }

        .message-from {
            font-size: 1.1em;
        }

        .message-subject {
            font-size: 1.3em;
            font-weight: bold;
        }

        .message-date {
            font-size: 0.9em;
        }

        .recipient-chip {
            background-color: alpha(@accent_bg_color, 0.1);
            border-radius: 12px;
            padding: 2px 8px 2px 2px;
        }

        .message-headers-expanded {
            padding: 8px;
            background-color: alpha(@view_bg_color, 0.5);
            border-radius: 4px;
        }
        """
