"""
Attachment panel widget for email composer.
"""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GObject, Gio, Gdk, GLib
import os
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class AttachmentInfo:
    """Information about an attached file."""
    path: str
    name: str
    size: int
    mime_type: str


class AttachmentRow(Gtk.Box):
    """
    A row widget displaying a single attachment.
    """

    __gsignals__ = {
        'remove-requested': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, attachment: AttachmentInfo):
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            css_classes=['attachment-row']
        )

        self.attachment = attachment

        # File icon
        icon = Gtk.Image()
        icon.set_from_icon_name(self._get_icon_name(attachment.mime_type))
        icon.set_pixel_size(24)
        self.append(icon)

        # File info box
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info_box.set_hexpand(True)

        # File name
        name_label = Gtk.Label(label=attachment.name)
        name_label.set_halign(Gtk.Align.START)
        name_label.set_ellipsize(True)
        name_label.add_css_class("heading")
        info_box.append(name_label)

        # File size
        size_label = Gtk.Label(label=self._format_size(attachment.size))
        size_label.set_halign(Gtk.Align.START)
        size_label.add_css_class("dim-label")
        size_label.add_css_class("caption")
        info_box.append(size_label)

        self.append(info_box)

        # Remove button
        remove_button = Gtk.Button()
        remove_button.set_icon_name("user-trash-symbolic")
        remove_button.add_css_class("flat")
        remove_button.set_tooltip_text("Remove attachment")
        remove_button.connect("clicked", self._on_remove_clicked)
        self.append(remove_button)

        self._apply_styles()

    def _apply_styles(self):
        """Apply CSS styles."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            .attachment-row {
                padding: 8px 12px;
                background-color: alpha(@view_bg_color, 0.5);
                border-radius: 6px;
                margin: 2px 0;
            }
            .attachment-row:hover {
                background-color: alpha(@view_bg_color, 0.8);
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _get_icon_name(self, mime_type: str) -> str:
        """Get appropriate icon name for mime type."""
        if mime_type.startswith('image/'):
            return 'image-x-generic-symbolic'
        elif mime_type.startswith('video/'):
            return 'video-x-generic-symbolic'
        elif mime_type.startswith('audio/'):
            return 'audio-x-generic-symbolic'
        elif mime_type.startswith('text/'):
            return 'text-x-generic-symbolic'
        elif 'pdf' in mime_type:
            return 'x-office-document-symbolic'
        elif 'zip' in mime_type or 'archive' in mime_type or 'compressed' in mime_type:
            return 'package-x-generic-symbolic'
        elif 'spreadsheet' in mime_type or 'excel' in mime_type:
            return 'x-office-spreadsheet-symbolic'
        elif 'presentation' in mime_type or 'powerpoint' in mime_type:
            return 'x-office-presentation-symbolic'
        elif 'document' in mime_type or 'word' in mime_type:
            return 'x-office-document-symbolic'
        else:
            return 'text-x-generic-symbolic'

    def _format_size(self, size: int) -> str:
        """Format file size for display."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"

    def _on_remove_clicked(self, button):
        """Handle remove button click."""
        self.emit('remove-requested')


class AttachmentPanel(Gtk.Box):
    """
    Panel widget for managing email attachments.

    Features:
    - Add attachment button with file chooser
    - List of attached files with size display
    - Remove attachment functionality
    - Drag and drop support
    - Size limits enforcement
    """

    __gsignals__ = {
        'attachments-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'size-limit-exceeded': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    # Default size limit: 25 MB
    DEFAULT_SIZE_LIMIT = 25 * 1024 * 1024

    def __init__(self,
                 size_limit: int = DEFAULT_SIZE_LIMIT,
                 show_header: bool = True):
        """
        Initialize the attachment panel.

        Args:
            size_limit: Maximum total size of attachments in bytes
            show_header: Whether to show the header with add button
        """
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            css_classes=['attachment-panel']
        )

        self._attachments: List[AttachmentInfo] = []
        self._attachment_rows: dict = {}  # path -> AttachmentRow
        self._size_limit = size_limit
        self._parent_window: Optional[Gtk.Window] = None

        # Header with add button
        if show_header:
            self._create_header()

        # Attachments list
        self.list_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.append(self.list_box)

        # Empty state label
        self.empty_label = Gtk.Label(label="No attachments")
        self.empty_label.add_css_class("dim-label")
        self.empty_label.set_visible(True)
        self.list_box.append(self.empty_label)

        # Total size label
        self.size_label = Gtk.Label()
        self.size_label.set_halign(Gtk.Align.END)
        self.size_label.add_css_class("dim-label")
        self.size_label.add_css_class("caption")
        self.size_label.set_visible(False)
        self.append(self.size_label)

        # Setup drag and drop
        self._setup_drag_drop()

        self._apply_styles()

    def _apply_styles(self):
        """Apply CSS styles."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            .attachment-panel {
                padding: 8px;
                background-color: @view_bg_color;
                border: 1px solid @borders;
                border-radius: 6px;
            }
            .attachment-panel.drag-hover {
                border-color: @accent_bg_color;
                border-width: 2px;
                background-color: alpha(@accent_bg_color, 0.1);
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _create_header(self):
        """Create the header with add button."""
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        # Label
        label = Gtk.Label(label="Attachments")
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)
        label.add_css_class("heading")
        header.append(label)

        # Add button
        add_button = Gtk.Button()
        add_button.set_icon_name("list-add-symbolic")
        add_button.add_css_class("flat")
        add_button.set_tooltip_text("Add attachment")
        add_button.connect("clicked", self._on_add_clicked)
        header.append(add_button)

        self.append(header)

    def _setup_drag_drop(self):
        """Setup drag and drop support."""
        # Drop target for files
        drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_drop)
        drop_target.connect("enter", self._on_drag_enter)
        drop_target.connect("leave", self._on_drag_leave)
        self.add_controller(drop_target)

    def _on_drag_enter(self, drop_target, x, y):
        """Handle drag enter."""
        self.add_css_class("drag-hover")
        return Gdk.DragAction.COPY

    def _on_drag_leave(self, drop_target):
        """Handle drag leave."""
        self.remove_css_class("drag-hover")

    def _on_drop(self, drop_target, value, x, y):
        """Handle file drop."""
        self.remove_css_class("drag-hover")

        if isinstance(value, Gio.File):
            self.add_attachment_from_file(value)
            return True
        return False

    def _on_add_clicked(self, button):
        """Handle add button click."""
        self.show_file_chooser()

    def set_parent_window(self, window: Gtk.Window):
        """Set the parent window for dialogs."""
        self._parent_window = window

    def show_file_chooser(self):
        """Show file chooser dialog to add attachments."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Add Attachment")
        dialog.set_modal(True)

        # Allow multiple files
        dialog.open_multiple(
            self._parent_window,
            None,
            self._on_file_chooser_response
        )

    def _on_file_chooser_response(self, dialog, result):
        """Handle file chooser response."""
        try:
            files = dialog.open_multiple_finish(result)
            if files:
                for i in range(files.get_n_items()):
                    file = files.get_item(i)
                    self.add_attachment_from_file(file)
        except GLib.Error as e:
            # User cancelled or error
            if e.code != Gtk.DialogError.CANCELLED:
                print(f"File chooser error: {e.message}")

    def add_attachment_from_file(self, file: Gio.File) -> bool:
        """
        Add an attachment from a Gio.File.

        Args:
            file: The file to attach

        Returns:
            True if attachment was added successfully
        """
        path = file.get_path()
        if not path:
            return False

        return self.add_attachment(path)

    def add_attachment(self, path: str) -> bool:
        """
        Add an attachment from a file path.

        Args:
            path: Path to the file

        Returns:
            True if attachment was added successfully
        """
        # Check if already attached
        for attachment in self._attachments:
            if attachment.path == path:
                return False

        # Get file info
        try:
            stat = os.stat(path)
            size = stat.st_size
        except OSError:
            return False

        # Check size limit
        total_size = sum(a.size for a in self._attachments) + size
        if total_size > self._size_limit:
            self.emit('size-limit-exceeded',
                      f"Total attachment size would exceed limit of {self._format_size(self._size_limit)}")
            return False

        # Get mime type
        file = Gio.File.new_for_path(path)
        try:
            info = file.query_info(
                Gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE,
                Gio.FileQueryInfoFlags.NONE,
                None
            )
            mime_type = info.get_content_type() or 'application/octet-stream'
        except GLib.Error:
            mime_type = 'application/octet-stream'

        # Create attachment info
        attachment = AttachmentInfo(
            path=path,
            name=os.path.basename(path),
            size=size,
            mime_type=mime_type
        )

        # Create row
        row = AttachmentRow(attachment)
        row.connect('remove-requested', self._on_row_remove_requested)

        # Hide empty label
        self.empty_label.set_visible(False)

        # Add to list
        self._attachments.append(attachment)
        self._attachment_rows[path] = row
        self.list_box.append(row)

        # Update size label
        self._update_size_label()

        self.emit('attachments-changed')
        return True

    def _on_row_remove_requested(self, row):
        """Handle row removal request."""
        self.remove_attachment(row.attachment.path)

    def remove_attachment(self, path: str):
        """Remove an attachment by path."""
        # Find and remove attachment
        for i, attachment in enumerate(self._attachments):
            if attachment.path == path:
                self._attachments.pop(i)
                break
        else:
            return

        # Remove row
        if path in self._attachment_rows:
            row = self._attachment_rows.pop(path)
            self.list_box.remove(row)

        # Show empty label if no attachments
        if not self._attachments:
            self.empty_label.set_visible(True)
            self.size_label.set_visible(False)
        else:
            self._update_size_label()

        self.emit('attachments-changed')

    def _update_size_label(self):
        """Update the total size label."""
        total_size = sum(a.size for a in self._attachments)
        limit_text = f" / {self._format_size(self._size_limit)}"
        self.size_label.set_text(
            f"Total: {self._format_size(total_size)}{limit_text}")
        self.size_label.set_visible(True)

    def _format_size(self, size: int) -> str:
        """Format file size for display."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"

    def get_attachments(self) -> List[AttachmentInfo]:
        """Get list of attachments."""
        return self._attachments.copy()

    def get_attachment_paths(self) -> List[str]:
        """Get list of attachment file paths."""
        return [a.path for a in self._attachments]

    def get_total_size(self) -> int:
        """Get total size of all attachments."""
        return sum(a.size for a in self._attachments)

    def clear(self):
        """Clear all attachments."""
        paths = list(self._attachment_rows.keys())
        for path in paths:
            self.remove_attachment(path)

    def set_size_limit(self, limit: int):
        """Set the size limit for attachments."""
        self._size_limit = limit
        self._update_size_label()

    def get_size_limit(self) -> int:
        """Get the size limit."""
        return self._size_limit

    def has_attachments(self) -> bool:
        """Check if there are any attachments."""
        return len(self._attachments) > 0
