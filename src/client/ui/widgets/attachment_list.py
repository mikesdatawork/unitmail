"""
Attachment list widget for unitMail.

This module provides a widget for displaying and interacting with
email attachments, including download and preview functionality.
"""

from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
gi.require_version("Gdk", "4.0")

from gi.repository import GObject, Gtk


class AttachmentType(Enum):
    """Types of attachments for icon selection."""

    IMAGE = "image"
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    ARCHIVE = "archive"
    AUDIO = "audio"
    VIDEO = "video"
    CODE = "code"
    PDF = "pdf"
    TEXT = "text"
    UNKNOWN = "unknown"


# Mapping of MIME types to attachment types
MIME_TYPE_MAP: dict[str, AttachmentType] = {
    # Images
    "image/jpeg": AttachmentType.IMAGE,
    "image/png": AttachmentType.IMAGE,
    "image/gif": AttachmentType.IMAGE,
    "image/webp": AttachmentType.IMAGE,
    "image/svg+xml": AttachmentType.IMAGE,
    "image/bmp": AttachmentType.IMAGE,
    "image/tiff": AttachmentType.IMAGE,
    # Documents
    "application/msword": AttachmentType.DOCUMENT,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": AttachmentType.DOCUMENT,
    "application/vnd.oasis.opendocument.text": AttachmentType.DOCUMENT,
    "application/rtf": AttachmentType.DOCUMENT,
    # Spreadsheets
    "application/vnd.ms-excel": AttachmentType.SPREADSHEET,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": AttachmentType.SPREADSHEET,
    "application/vnd.oasis.opendocument.spreadsheet": AttachmentType.SPREADSHEET,
    "text/csv": AttachmentType.SPREADSHEET,
    # Presentations
    "application/vnd.ms-powerpoint": AttachmentType.PRESENTATION,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": AttachmentType.PRESENTATION,
    "application/vnd.oasis.opendocument.presentation": AttachmentType.PRESENTATION,
    # Archives
    "application/zip": AttachmentType.ARCHIVE,
    "application/x-rar-compressed": AttachmentType.ARCHIVE,
    "application/x-7z-compressed": AttachmentType.ARCHIVE,
    "application/gzip": AttachmentType.ARCHIVE,
    "application/x-tar": AttachmentType.ARCHIVE,
    "application/x-bzip2": AttachmentType.ARCHIVE,
    # Audio
    "audio/mpeg": AttachmentType.AUDIO,
    "audio/wav": AttachmentType.AUDIO,
    "audio/ogg": AttachmentType.AUDIO,
    "audio/flac": AttachmentType.AUDIO,
    "audio/aac": AttachmentType.AUDIO,
    # Video
    "video/mp4": AttachmentType.VIDEO,
    "video/mpeg": AttachmentType.VIDEO,
    "video/webm": AttachmentType.VIDEO,
    "video/x-msvideo": AttachmentType.VIDEO,
    "video/quicktime": AttachmentType.VIDEO,
    # Code
    "text/x-python": AttachmentType.CODE,
    "text/javascript": AttachmentType.CODE,
    "application/javascript": AttachmentType.CODE,
    "text/x-java-source": AttachmentType.CODE,
    "text/x-c": AttachmentType.CODE,
    "text/x-c++": AttachmentType.CODE,
    "application/json": AttachmentType.CODE,
    "application/xml": AttachmentType.CODE,
    "text/xml": AttachmentType.CODE,
    "text/html": AttachmentType.CODE,
    "text/css": AttachmentType.CODE,
    # PDF
    "application/pdf": AttachmentType.PDF,
    # Text
    "text/plain": AttachmentType.TEXT,
    "text/markdown": AttachmentType.TEXT,
}

# Icon names for each attachment type
ATTACHMENT_ICONS: dict[AttachmentType, str] = {
    AttachmentType.IMAGE: "image-x-generic-symbolic",
    AttachmentType.DOCUMENT: "x-office-document-symbolic",
    AttachmentType.SPREADSHEET: "x-office-spreadsheet-symbolic",
    AttachmentType.PRESENTATION: "x-office-presentation-symbolic",
    AttachmentType.ARCHIVE: "package-x-generic-symbolic",
    AttachmentType.AUDIO: "audio-x-generic-symbolic",
    AttachmentType.VIDEO: "video-x-generic-symbolic",
    AttachmentType.CODE: "text-x-script-symbolic",
    AttachmentType.PDF: "application-pdf-symbolic",
    AttachmentType.TEXT: "text-x-generic-symbolic",
    AttachmentType.UNKNOWN: "application-x-generic-symbolic",
}


@dataclass
class Attachment:
    """Represents an email attachment."""

    filename: str
    content_type: str
    size: int
    content_id: Optional[str] = None
    data: Optional[bytes] = None
    file_path: Optional[str] = None

    @property
    def attachment_type(self) -> AttachmentType:
        """Get the attachment type based on MIME type."""
        return MIME_TYPE_MAP.get(self.content_type, AttachmentType.UNKNOWN)

    @property
    def icon_name(self) -> str:
        """Get the icon name for this attachment type."""
        return ATTACHMENT_ICONS.get(
            self.attachment_type, ATTACHMENT_ICONS[AttachmentType.UNKNOWN])

    @property
    def size_display(self) -> str:
        """Get human-readable size string."""
        return format_file_size(self.size)

    @property
    def is_previewable(self) -> bool:
        """Check if attachment can be previewed."""
        return self.attachment_type == AttachmentType.IMAGE

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Attachment":
        """Create an Attachment from a dictionary."""
        return cls(
            filename=data.get("filename", "unknown"),
            content_type=data.get("content_type", "application/octet-stream"),
            size=data.get("size", 0),
            content_id=data.get("content_id"),
            data=data.get("data"),
            file_path=data.get("file_path"),
        )


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def get_attachment_type_from_filename(filename: str) -> AttachmentType:
    """Guess attachment type from filename."""
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type:
        return MIME_TYPE_MAP.get(mime_type, AttachmentType.UNKNOWN)
    return AttachmentType.UNKNOWN


class AttachmentRow(Gtk.Box):
    """A single attachment row widget."""

    __gtype_name__ = "AttachmentRow"

    __gsignals__ = {
        "download-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "preview-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "open-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, attachment: Attachment) -> None:
        """Initialize the attachment row.

        Args:
            attachment: The attachment data to display.
        """
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_start=8,
            margin_end=8,
            margin_top=4,
            margin_bottom=4,
        )

        self._attachment = attachment
        self._setup_ui()

    @property
    def attachment(self) -> Attachment:
        """Get the attachment data."""
        return self._attachment

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        # Add CSS class for styling
        self.add_css_class("attachment-row")

        # Icon
        icon = Gtk.Image.new_from_icon_name(self._attachment.icon_name)
        icon.set_pixel_size(24)
        icon.add_css_class("attachment-icon")
        self.append(icon)

        # File info container
        info_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=2,
            hexpand=True,
        )

        # Filename
        filename_label = Gtk.Label(
            label=self._attachment.filename,
            xalign=0,
            ellipsize=3,  # PANGO_ELLIPSIZE_END
            max_width_chars=40,
        )
        filename_label.add_css_class("attachment-filename")
        info_box.append(filename_label)

        # Size and type
        details_label = Gtk.Label(
            label=f"{self._attachment.size_display} - {self._attachment.content_type}",
            xalign=0,
        )
        details_label.add_css_class("attachment-details")
        details_label.add_css_class("dim-label")
        info_box.append(details_label)

        self.append(info_box)

        # Action buttons container
        actions_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4,
        )

        # Preview button (only for previewable types)
        if self._attachment.is_previewable:
            preview_button = Gtk.Button.new_from_icon_name("eye-open-symbolic")
            preview_button.set_tooltip_text("Preview")
            preview_button.add_css_class("flat")
            preview_button.add_css_class("circular")
            preview_button.connect("clicked", self._on_preview_clicked)
            actions_box.append(preview_button)

        # Download button
        download_button = Gtk.Button.new_from_icon_name(
            "folder-download-symbolic")
        download_button.set_tooltip_text("Download")
        download_button.add_css_class("flat")
        download_button.add_css_class("circular")
        download_button.connect("clicked", self._on_download_clicked)
        actions_box.append(download_button)

        # Open button
        open_button = Gtk.Button.new_from_icon_name("external-link-symbolic")
        open_button.set_tooltip_text("Open with default application")
        open_button.add_css_class("flat")
        open_button.add_css_class("circular")
        open_button.connect("clicked", self._on_open_clicked)
        actions_box.append(open_button)

        self.append(actions_box)

    def _on_download_clicked(self, button: Gtk.Button) -> None:
        """Handle download button click."""
        self.emit("download-requested")

    def _on_preview_clicked(self, button: Gtk.Button) -> None:
        """Handle preview button click."""
        self.emit("preview-requested")

    def _on_open_clicked(self, button: Gtk.Button) -> None:
        """Handle open button click."""
        self.emit("open-requested")


class AttachmentList(Gtk.Box):
    """Widget for displaying a list of email attachments."""

    __gtype_name__ = "AttachmentList"

    __gsignals__ = {
        "attachment-download": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "attachment-preview": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "attachment-open": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "download-all": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self) -> None:
        """Initialize the attachment list widget."""
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )

        self._attachments: list[Attachment] = []
        self._attachment_rows: list[AttachmentRow] = []
        self._download_callback: Optional[Callable[[Attachment], None]] = None
        self._preview_callback: Optional[Callable[[Attachment], None]] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.add_css_class("attachment-list")

        # Header with count and download all button
        self._header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_start=8,
            margin_end=8,
            margin_top=8,
            margin_bottom=4,
        )
        self._header.add_css_class("attachment-list-header")

        # Attachment icon
        header_icon = Gtk.Image.new_from_icon_name("mail-attachment-symbolic")
        header_icon.set_pixel_size(16)
        self._header.append(header_icon)

        # Count label
        self._count_label = Gtk.Label(
            label="No attachments",
            xalign=0,
            hexpand=True,
        )
        self._count_label.add_css_class("attachment-count")
        self._header.append(self._count_label)

        # Total size label
        self._size_label = Gtk.Label(
            label="",
            xalign=1,
        )
        self._size_label.add_css_class("dim-label")
        self._header.append(self._size_label)

        # Download all button
        self._download_all_button = Gtk.Button.new_with_label("Download All")
        self._download_all_button.add_css_class("flat")
        self._download_all_button.connect(
            "clicked", self._on_download_all_clicked)
        self._download_all_button.set_sensitive(False)
        self._header.append(self._download_all_button)

        self.append(self._header)

        # Separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.set_margin_start(8)
        separator.set_margin_end(8)
        self.append(separator)

        # Scrolled container for attachments
        self._scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            min_content_height=50,
            max_content_height=200,
        )

        # List container
        self._list_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )
        self._list_box.add_css_class("attachment-list-content")

        self._scrolled.set_child(self._list_box)
        self.append(self._scrolled)

        # Empty state label
        self._empty_label = Gtk.Label(
            label="No attachments",
            margin_top=16,
            margin_bottom=16,
        )
        self._empty_label.add_css_class("dim-label")
        self._list_box.append(self._empty_label)

    @property
    def attachments(self) -> list[Attachment]:
        """Get the list of attachments."""
        return self._attachments.copy()

    @property
    def attachment_count(self) -> int:
        """Get the number of attachments."""
        return len(self._attachments)

    @property
    def total_size(self) -> int:
        """Get the total size of all attachments."""
        return sum(a.size for a in self._attachments)

    def set_attachments(
            self, attachments: list[Attachment | dict[str, Any]]) -> None:
        """Set the list of attachments to display.

        Args:
            attachments: List of Attachment objects or dicts with attachment data.
        """
        self.clear()

        for attachment_data in attachments:
            if isinstance(attachment_data, dict):
                attachment = Attachment.from_dict(attachment_data)
            else:
                attachment = attachment_data
            self._add_attachment(attachment)

        self._update_header()

    def add_attachment(self, attachment: Attachment | dict[str, Any]) -> None:
        """Add a single attachment to the list.

        Args:
            attachment: Attachment object or dict with attachment data.
        """
        if isinstance(attachment, dict):
            attachment = Attachment.from_dict(attachment)

        self._add_attachment(attachment)
        self._update_header()

    def _add_attachment(self, attachment: Attachment) -> None:
        """Internal method to add an attachment row.

        Args:
            attachment: The attachment to add.
        """
        # Hide empty label if visible
        self._empty_label.set_visible(False)

        self._attachments.append(attachment)

        # Create row
        row = AttachmentRow(attachment)
        row.connect("download-requested", self._on_row_download, attachment)
        row.connect("preview-requested", self._on_row_preview, attachment)
        row.connect("open-requested", self._on_row_open, attachment)

        self._attachment_rows.append(row)
        self._list_box.append(row)

    def clear(self) -> None:
        """Clear all attachments from the list."""
        for row in self._attachment_rows:
            self._list_box.remove(row)

        self._attachments.clear()
        self._attachment_rows.clear()

        self._empty_label.set_visible(True)
        self._update_header()

    def _update_header(self) -> None:
        """Update the header labels."""
        count = len(self._attachments)

        if count == 0:
            self._count_label.set_label("No attachments")
            self._size_label.set_label("")
            self._download_all_button.set_sensitive(False)
        else:
            attachment_text = "attachment" if count == 1 else "attachments"
            self._count_label.set_label(f"{count} {attachment_text}")
            self._size_label.set_label(format_file_size(self.total_size))
            self._download_all_button.set_sensitive(True)

    def set_download_callback(
            self, callback: Callable[[Attachment], None]) -> None:
        """Set the callback for download requests.

        Args:
            callback: Function to call when download is requested.
        """
        self._download_callback = callback

    def set_preview_callback(
            self, callback: Callable[[Attachment], None]) -> None:
        """Set the callback for preview requests.

        Args:
            callback: Function to call when preview is requested.
        """
        self._preview_callback = callback

    def _on_row_download(self, row: AttachmentRow,
                         attachment: Attachment) -> None:
        """Handle download request from a row."""
        self.emit("attachment-download", attachment)
        if self._download_callback:
            self._download_callback(attachment)

    def _on_row_preview(self, row: AttachmentRow,
                        attachment: Attachment) -> None:
        """Handle preview request from a row."""
        self.emit("attachment-preview", attachment)
        if self._preview_callback:
            self._preview_callback(attachment)

    def _on_row_open(self, row: AttachmentRow, attachment: Attachment) -> None:
        """Handle open request from a row."""
        self.emit("attachment-open", attachment)

    def _on_download_all_clicked(self, button: Gtk.Button) -> None:
        """Handle download all button click."""
        self.emit("download-all")

    def get_css(self) -> str:
        """Get CSS styles for the attachment list widget."""
        return """
        .attachment-list {
            background-color: @card_bg_color;
            border-radius: 8px;
            border: 1px solid @borders;
        }

        .attachment-list-header {
            padding: 8px;
        }

        .attachment-count {
            font-weight: bold;
        }

        .attachment-row {
            padding: 8px;
            border-radius: 4px;
        }

        .attachment-row:hover {
            background-color: alpha(@accent_bg_color, 0.1);
        }

        .attachment-filename {
            font-weight: 500;
        }

        .attachment-details {
            font-size: smaller;
        }

        .attachment-icon {
            color: @accent_color;
        }
        """


class AttachmentPreviewDialog(Gtk.Dialog):
    """Dialog for previewing image attachments."""

    def __init__(
        self,
        parent: Optional[Gtk.Window],
        attachment: Attachment,
    ) -> None:
        """Initialize the preview dialog.

        Args:
            parent: Parent window for the dialog.
            attachment: The attachment to preview.
        """
        super().__init__(
            title=f"Preview: {attachment.filename}",
            transient_for=parent,
            modal=True,
            default_width=800,
            default_height=600,
        )

        self._attachment = attachment
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        content_area = self.get_content_area()
        content_area.set_spacing(8)
        content_area.set_margin_start(16)
        content_area.set_margin_end(16)
        content_area.set_margin_top(16)
        content_area.set_margin_bottom(16)

        # Scrolled window for image
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            hexpand=True,
            vexpand=True,
        )

        # Image
        if self._attachment.data:
            try:
                # Load image from bytes
                loader = GdkPixbuf.PixbufLoader()
                loader.write(self._attachment.data)
                loader.close()
                pixbuf = loader.get_pixbuf()

                if pixbuf:
                    image = Gtk.Picture.new_for_pixbuf(pixbuf)
                    image.set_can_shrink(True)
                    scrolled.set_child(image)
                else:
                    self._show_error(scrolled, "Could not load image")
            except Exception as e:
                self._show_error(scrolled, f"Error loading image: {e}")
        elif self._attachment.file_path and os.path.exists(self._attachment.file_path):
            try:
                image = Gtk.Picture.new_for_filename(
                    self._attachment.file_path)
                image.set_can_shrink(True)
                scrolled.set_child(image)
            except Exception as e:
                self._show_error(scrolled, f"Error loading image: {e}")
        else:
            self._show_error(scrolled, "No image data available")

        content_area.append(scrolled)

        # Close button
        self.add_button("Close", Gtk.ResponseType.CLOSE)
        self.connect("response", lambda d, r: d.close())

    def _show_error(self, container: Gtk.Widget, message: str) -> None:
        """Show an error message in the container."""
        label = Gtk.Label(label=message)
        label.add_css_class("dim-label")
        container.set_child(label)


# Try to import GdkPixbuf for image preview functionality
try:
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    HAS_GDKPIXBUF = True
except (ValueError, ImportError):
    HAS_GDKPIXBUF = False
