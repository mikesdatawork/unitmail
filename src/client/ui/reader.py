"""
Email reader/viewer component for unitMail.

This module provides the main message viewer widget that displays
email content including headers, body, and attachments.
"""

from __future__ import annotations

import html
import re
import subprocess
import webbrowser
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import UUID

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")

from gi.repository import Gio, GLib, GObject, Gtk

# Try to import WebKit for HTML rendering
try:
    gi.require_version("WebKit", "6.0")
    from gi.repository import WebKit
    HAS_WEBKIT = True
except (ValueError, ImportError):
    try:
        gi.require_version("WebKit2", "5.0")
        from gi.repository import WebKit2 as WebKit
        HAS_WEBKIT = True
    except (ValueError, ImportError):
        HAS_WEBKIT = False

from .widgets.attachment_list import Attachment, AttachmentList
from .widgets.message_header import MessageHeader


# HTML sanitization patterns
SCRIPT_PATTERN = re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
STYLE_PATTERN = re.compile(r"<style[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
EVENT_HANDLER_PATTERN = re.compile(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', re.IGNORECASE)
JAVASCRIPT_URL_PATTERN = re.compile(r'href\s*=\s*["\']javascript:[^"\']*["\']', re.IGNORECASE)
DATA_URL_PATTERN = re.compile(r'src\s*=\s*["\']data:[^"\']*["\']', re.IGNORECASE)
IFRAME_PATTERN = re.compile(r"<iframe[^>]*>.*?</iframe>", re.IGNORECASE | re.DOTALL)
OBJECT_PATTERN = re.compile(r"<object[^>]*>.*?</object>", re.IGNORECASE | re.DOTALL)
EMBED_PATTERN = re.compile(r"<embed[^>]*>.*?</embed>", re.IGNORECASE | re.DOTALL)
FORM_PATTERN = re.compile(r"<form[^>]*>.*?</form>", re.IGNORECASE | re.DOTALL)
META_REFRESH_PATTERN = re.compile(r'<meta[^>]+http-equiv\s*=\s*["\']refresh["\'][^>]*>', re.IGNORECASE)


def sanitize_html(html_content: str) -> str:
    """Sanitize HTML content by removing potentially dangerous elements.

    Args:
        html_content: Raw HTML content.

    Returns:
        Sanitized HTML content.
    """
    if not html_content:
        return ""

    # Remove script tags and content
    html_content = SCRIPT_PATTERN.sub("", html_content)

    # Remove style tags and content (optional, can be kept for styling)
    # html_content = STYLE_PATTERN.sub("", html_content)

    # Remove event handlers (onclick, onload, etc.)
    html_content = EVENT_HANDLER_PATTERN.sub("", html_content)

    # Remove javascript: URLs
    html_content = JAVASCRIPT_URL_PATTERN.sub('href="#"', html_content)

    # Remove data: URLs in src attributes (can be used for XSS)
    # Note: This may break inline images, so we're lenient here
    # html_content = DATA_URL_PATTERN.sub('src=""', html_content)

    # Remove iframes
    html_content = IFRAME_PATTERN.sub("", html_content)

    # Remove object tags
    html_content = OBJECT_PATTERN.sub("", html_content)

    # Remove embed tags
    html_content = EMBED_PATTERN.sub("", html_content)

    # Remove form tags
    html_content = FORM_PATTERN.sub("", html_content)

    # Remove meta refresh
    html_content = META_REFRESH_PATTERN.sub("", html_content)

    return html_content


def plain_text_to_html(text: str) -> str:
    """Convert plain text to simple HTML for display.

    Args:
        text: Plain text content.

    Returns:
        HTML-formatted text.
    """
    if not text:
        return ""

    # Escape HTML entities
    text = html.escape(text)

    # Convert URLs to links
    url_pattern = re.compile(
        r'(https?://[^\s<>"{}|\\^`\[\]]+)',
        re.IGNORECASE
    )
    text = url_pattern.sub(r'<a href="\1">\1</a>', text)

    # Convert email addresses to mailto links
    email_pattern = re.compile(
        r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
    )
    text = email_pattern.sub(r'<a href="mailto:\1">\1</a>', text)

    # Convert newlines to <br>
    text = text.replace("\n", "<br>\n")

    # Wrap in basic HTML structure
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: system-ui, -apple-system, sans-serif;
                font-size: 14px;
                line-height: 1.5;
                color: #333;
                margin: 16px;
                word-wrap: break-word;
            }}
            a {{
                color: #0066cc;
            }}
        </style>
    </head>
    <body>
        <pre style="font-family: inherit; white-space: pre-wrap;">{text}</pre>
    </body>
    </html>
    """


def wrap_html_content(html_content: str) -> str:
    """Wrap HTML content with necessary styles for proper display.

    Args:
        html_content: HTML content to wrap.

    Returns:
        Wrapped HTML content.
    """
    # Check if it's a complete HTML document
    if "<html" in html_content.lower():
        return html_content

    # Wrap partial HTML
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: system-ui, -apple-system, sans-serif;
                font-size: 14px;
                line-height: 1.5;
                color: #333;
                margin: 16px;
                word-wrap: break-word;
            }}
            a {{
                color: #0066cc;
            }}
            img {{
                max-width: 100%;
                height: auto;
            }}
            blockquote {{
                border-left: 3px solid #ccc;
                margin: 8px 0;
                padding-left: 12px;
                color: #666;
            }}
            pre {{
                background-color: #f5f5f5;
                padding: 8px;
                border-radius: 4px;
                overflow-x: auto;
            }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """


class MessageBodyView(Gtk.Box):
    """Widget for displaying email message body content."""

    __gtype_name__ = "MessageBodyView"

    __gsignals__ = {
        "link-clicked": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self) -> None:
        """Initialize the message body view."""
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )

        self._html_content: str = ""
        self._text_content: str = ""
        self._use_html: bool = True
        self._external_content_blocked: bool = True

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.add_css_class("message-body")

        # External content warning bar
        self._external_warning = Gtk.InfoBar(
            message_type=Gtk.MessageType.WARNING,
            show_close_button=False,
        )
        self._external_warning.set_visible(False)

        warning_label = Gtk.Label(
            label="External images and content are blocked for your privacy.",
            wrap=True,
        )
        self._external_warning.add_child(warning_label)

        load_button = Gtk.Button.new_with_label("Load External Content")
        load_button.connect("clicked", self._on_load_external_clicked)
        self._external_warning.add_action_widget(load_button, Gtk.ResponseType.OK)

        self.append(self._external_warning)

        # View mode toggle
        self._mode_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_start=8,
            margin_end=8,
            margin_top=4,
            margin_bottom=4,
        )

        mode_label = Gtk.Label(label="View:")
        mode_label.add_css_class("dim-label")
        self._mode_box.append(mode_label)

        self._html_toggle = Gtk.ToggleButton(label="HTML")
        self._html_toggle.set_active(True)
        self._html_toggle.connect("toggled", self._on_html_toggled)
        self._mode_box.append(self._html_toggle)

        self._text_toggle = Gtk.ToggleButton(label="Plain Text")
        self._text_toggle.connect("toggled", self._on_text_toggled)
        self._mode_box.append(self._text_toggle)

        # Hide mode toggle initially
        self._mode_box.set_visible(False)
        self.append(self._mode_box)

        # Content area
        self._content_stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE,
            transition_duration=150,
            vexpand=True,
            hexpand=True,
        )

        # WebKit view for HTML
        if HAS_WEBKIT:
            self._web_view = WebKit.WebView()
            self._web_view.set_vexpand(True)
            self._web_view.set_hexpand(True)

            # Configure WebKit settings for security
            settings = self._web_view.get_settings()
            settings.set_enable_javascript(False)
            settings.set_enable_plugins(False)
            if hasattr(settings, "set_enable_java"):
                settings.set_enable_java(False)
            if hasattr(settings, "set_auto_load_images"):
                settings.set_auto_load_images(False)  # Block external images initially

            # Connect to navigation signals
            self._web_view.connect("decide-policy", self._on_decide_policy)

            self._content_stack.add_named(self._web_view, "html")
        else:
            # Fallback: use a text view for HTML
            html_fallback_scroll = Gtk.ScrolledWindow(
                hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                vexpand=True,
            )

            self._html_fallback_view = Gtk.TextView(
                editable=False,
                wrap_mode=Gtk.WrapMode.WORD_CHAR,
                cursor_visible=False,
            )
            self._html_fallback_view.add_css_class("monospace")
            html_fallback_scroll.set_child(self._html_fallback_view)

            self._content_stack.add_named(html_fallback_scroll, "html")

        # Plain text view
        text_scroll = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )

        self._text_view = Gtk.TextView(
            editable=False,
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            cursor_visible=False,
            left_margin=16,
            right_margin=16,
            top_margin=16,
            bottom_margin=16,
        )
        text_scroll.set_child(self._text_view)

        self._content_stack.add_named(text_scroll, "text")

        # Empty state
        empty_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )

        empty_icon = Gtk.Image.new_from_icon_name("mail-read-symbolic")
        empty_icon.set_pixel_size(64)
        empty_icon.add_css_class("dim-label")
        empty_box.append(empty_icon)

        empty_label = Gtk.Label(label="No message content")
        empty_label.add_css_class("dim-label")
        empty_box.append(empty_label)

        self._content_stack.add_named(empty_box, "empty")
        self._content_stack.set_visible_child_name("empty")

        self.append(self._content_stack)

    def set_content(
        self,
        html_content: Optional[str] = None,
        text_content: Optional[str] = None,
    ) -> None:
        """Set the message body content.

        Args:
            html_content: HTML body content.
            text_content: Plain text body content.
        """
        self._html_content = html_content or ""
        self._text_content = text_content or ""

        # Determine what to show
        has_html = bool(self._html_content.strip())
        has_text = bool(self._text_content.strip())

        # Show mode toggle if both are available
        self._mode_box.set_visible(has_html and has_text)

        if has_html:
            self._load_html_content()
            self._html_toggle.set_active(True)
            self._text_toggle.set_active(False)
            self._content_stack.set_visible_child_name("html")
        elif has_text:
            self._load_text_content()
            self._html_toggle.set_active(False)
            self._text_toggle.set_active(True)
            self._content_stack.set_visible_child_name("text")
        else:
            self._content_stack.set_visible_child_name("empty")

        # Check for external content in HTML
        if has_html and self._has_external_content(self._html_content):
            self._external_warning.set_visible(True)

    def _load_html_content(self) -> None:
        """Load HTML content into the viewer."""
        if not self._html_content:
            return

        # Sanitize the HTML
        safe_html = sanitize_html(self._html_content)

        # Wrap if needed
        safe_html = wrap_html_content(safe_html)

        if HAS_WEBKIT:
            self._web_view.load_html(safe_html, "about:blank")
        else:
            # Fallback: show raw HTML in text view
            buffer = self._html_fallback_view.get_buffer()
            buffer.set_text(safe_html)

    def _load_text_content(self) -> None:
        """Load plain text content into the viewer."""
        buffer = self._text_view.get_buffer()
        buffer.set_text(self._text_content or "")

    def _has_external_content(self, html_content: str) -> bool:
        """Check if HTML contains external content (images, etc.).

        Args:
            html_content: HTML content to check.

        Returns:
            True if external content is detected.
        """
        # Check for external image sources
        external_patterns = [
            r'src\s*=\s*["\']https?://',
            r'background\s*=\s*["\']https?://',
            r'url\s*\(\s*["\']?https?://',
        ]

        for pattern in external_patterns:
            if re.search(pattern, html_content, re.IGNORECASE):
                return True

        return False

    def _on_load_external_clicked(self, button: Gtk.Button) -> None:
        """Handle load external content button click."""
        self._external_content_blocked = False
        self._external_warning.set_visible(False)

        if HAS_WEBKIT:
            # Enable image loading
            settings = self._web_view.get_settings()
            if hasattr(settings, "set_auto_load_images"):
                settings.set_auto_load_images(True)

            # Reload content
            self._load_html_content()

    def _on_html_toggled(self, button: Gtk.ToggleButton) -> None:
        """Handle HTML toggle button."""
        if button.get_active():
            self._text_toggle.set_active(False)
            self._content_stack.set_visible_child_name("html")

    def _on_text_toggled(self, button: Gtk.ToggleButton) -> None:
        """Handle plain text toggle button."""
        if button.get_active():
            self._html_toggle.set_active(False)
            self._load_text_content()
            self._content_stack.set_visible_child_name("text")

    def _on_decide_policy(
        self,
        web_view: "WebKit.WebView",
        decision: "WebKit.PolicyDecision",
        decision_type: "WebKit.PolicyDecisionType",
    ) -> bool:
        """Handle navigation policy decisions.

        Args:
            web_view: The WebView widget.
            decision: The policy decision.
            decision_type: Type of decision.

        Returns:
            True if decision was handled.
        """
        if not HAS_WEBKIT:
            return False

        if decision_type == WebKit.PolicyDecisionType.NAVIGATION_ACTION:
            navigation_decision = decision
            action = navigation_decision.get_navigation_action()
            request = action.get_request()
            uri = request.get_uri()

            # Allow about:blank for initial load
            if uri == "about:blank":
                decision.use()
                return True

            # Open external links in browser
            if uri.startswith(("http://", "https://", "mailto:")):
                decision.ignore()
                self.emit("link-clicked", uri)
                self._open_link(uri)
                return True

        return False

    def _open_link(self, uri: str) -> None:
        """Open a link in the default browser.

        Args:
            uri: The URI to open.
        """
        try:
            webbrowser.open(uri)
        except Exception as e:
            print(f"Failed to open link: {e}")

    def show_raw_source(self) -> None:
        """Show the raw message source."""
        if self._html_content:
            buffer = self._text_view.get_buffer()
            buffer.set_text(self._html_content)
            self._content_stack.set_visible_child_name("text")

    def print_message(self) -> None:
        """Print the current message."""
        if HAS_WEBKIT:
            print_operation = WebKit.PrintOperation.new(self._web_view)
            print_operation.run_dialog()


class MessageViewer(Gtk.Box):
    """Main email message viewer component."""

    __gtype_name__ = "MessageViewer"

    __gsignals__ = {
        "reply": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "reply-all": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "forward": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "star-toggled": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
        "delete": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "move-to-folder": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "attachment-download": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "attachment-download-all": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self) -> None:
        """Initialize the message viewer."""
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )

        self._message: Optional[Any] = None
        self._is_starred: bool = False
        self._folders: list[tuple[str, str]] = []  # (id, name) pairs

        self._reply_callback: Optional[Callable[[], None]] = None
        self._reply_all_callback: Optional[Callable[[], None]] = None
        self._forward_callback: Optional[Callable[[], None]] = None
        self._delete_callback: Optional[Callable[[], None]] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.add_css_class("message-viewer")

        # Action toolbar
        self._toolbar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4,
            margin_start=8,
            margin_end=8,
            margin_top=8,
            margin_bottom=4,
        )
        self._toolbar.add_css_class("message-toolbar")

        # Reply button
        self._reply_button = Gtk.Button.new_from_icon_name("mail-reply-sender-symbolic")
        self._reply_button.set_tooltip_text("Reply")
        self._reply_button.add_css_class("flat")
        self._reply_button.connect("clicked", self._on_reply_clicked)
        self._toolbar.append(self._reply_button)

        # Reply All button
        self._reply_all_button = Gtk.Button.new_from_icon_name("mail-reply-all-symbolic")
        self._reply_all_button.set_tooltip_text("Reply All")
        self._reply_all_button.add_css_class("flat")
        self._reply_all_button.connect("clicked", self._on_reply_all_clicked)
        self._toolbar.append(self._reply_all_button)

        # Forward button
        self._forward_button = Gtk.Button.new_from_icon_name("mail-forward-symbolic")
        self._forward_button.set_tooltip_text("Forward")
        self._forward_button.add_css_class("flat")
        self._forward_button.connect("clicked", self._on_forward_clicked)
        self._toolbar.append(self._forward_button)

        # Separator
        separator1 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        separator1.set_margin_start(8)
        separator1.set_margin_end(8)
        self._toolbar.append(separator1)

        # Star button
        self._star_button = Gtk.ToggleButton()
        self._star_button.set_icon_name("non-starred-symbolic")
        self._star_button.set_tooltip_text("Star")
        self._star_button.add_css_class("flat")
        self._star_button.connect("toggled", self._on_star_toggled)
        self._toolbar.append(self._star_button)

        # Move to folder button
        self._move_button = Gtk.MenuButton()
        self._move_button.set_icon_name("folder-symbolic")
        self._move_button.set_tooltip_text("Move to folder")
        self._move_button.add_css_class("flat")
        self._setup_folder_menu()
        self._toolbar.append(self._move_button)

        # Spacer
        spacer = Gtk.Box(hexpand=True)
        self._toolbar.append(spacer)

        # Delete button
        self._delete_button = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        self._delete_button.set_tooltip_text("Delete")
        self._delete_button.add_css_class("flat")
        self._delete_button.add_css_class("destructive-action")
        self._delete_button.connect("clicked", self._on_delete_clicked)
        self._toolbar.append(self._delete_button)

        # More menu
        self._more_button = Gtk.MenuButton()
        self._more_button.set_icon_name("view-more-symbolic")
        self._more_button.set_tooltip_text("More actions")
        self._more_button.add_css_class("flat")
        self._setup_more_menu()
        self._toolbar.append(self._more_button)

        self.append(self._toolbar)

        # Scrolled content area
        self._scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )

        # Content container
        self._content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )

        # Message header
        self._header = MessageHeader()
        self._content_box.append(self._header)

        # Message body
        self._body = MessageBodyView()
        self._body.connect("link-clicked", self._on_link_clicked)
        self._content_box.append(self._body)

        # Attachment list
        self._attachments = AttachmentList()
        self._attachments.connect("attachment-download", self._on_attachment_download)
        self._attachments.connect("attachment-preview", self._on_attachment_preview)
        self._attachments.connect("attachment-open", self._on_attachment_open)
        self._attachments.connect("download-all", self._on_download_all)
        self._attachments.set_visible(False)
        self._content_box.append(self._attachments)

        self._scrolled.set_child(self._content_box)
        self.append(self._scrolled)

        # Empty state (when no message is loaded)
        self._empty_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            vexpand=True,
        )

        empty_icon = Gtk.Image.new_from_icon_name("mail-unread-symbolic")
        empty_icon.set_pixel_size(96)
        empty_icon.add_css_class("dim-label")
        self._empty_box.append(empty_icon)

        empty_label = Gtk.Label(label="Select a message to read")
        empty_label.add_css_class("title-2")
        empty_label.add_css_class("dim-label")
        self._empty_box.append(empty_label)

        self.append(self._empty_box)

        # Initially show empty state
        self._scrolled.set_visible(False)
        self._toolbar.set_visible(False)

    def _setup_folder_menu(self) -> None:
        """Set up the folder move menu."""
        self._folder_menu = Gio.Menu()

        # Default folders
        self._folder_menu.append("Inbox", "message.move-inbox")
        self._folder_menu.append("Archive", "message.move-archive")
        self._folder_menu.append("Spam", "message.move-spam")
        self._folder_menu.append("Trash", "message.move-trash")

        popover = Gtk.PopoverMenu.new_from_model(self._folder_menu)
        self._move_button.set_popover(popover)

        # Set up actions
        action_group = Gio.SimpleActionGroup()

        move_inbox_action = Gio.SimpleAction.new("move-inbox", None)
        move_inbox_action.connect("activate", lambda a, p: self._on_move_to_folder("inbox"))
        action_group.add_action(move_inbox_action)

        move_archive_action = Gio.SimpleAction.new("move-archive", None)
        move_archive_action.connect("activate", lambda a, p: self._on_move_to_folder("archive"))
        action_group.add_action(move_archive_action)

        move_spam_action = Gio.SimpleAction.new("move-spam", None)
        move_spam_action.connect("activate", lambda a, p: self._on_move_to_folder("spam"))
        action_group.add_action(move_spam_action)

        move_trash_action = Gio.SimpleAction.new("move-trash", None)
        move_trash_action.connect("activate", lambda a, p: self._on_move_to_folder("trash"))
        action_group.add_action(move_trash_action)

        self.insert_action_group("message", action_group)

    def _setup_more_menu(self) -> None:
        """Set up the more actions menu."""
        more_menu = Gio.Menu()

        more_menu.append("Print", "message.print")
        more_menu.append("View Raw Source", "message.view-source")
        more_menu.append("Mark as Unread", "message.mark-unread")

        popover = Gtk.PopoverMenu.new_from_model(more_menu)
        self._more_button.set_popover(popover)

        # Set up actions
        action_group = self.get_action_group("message")
        if action_group is None:
            action_group = Gio.SimpleActionGroup()
            self.insert_action_group("message", action_group)

        print_action = Gio.SimpleAction.new("print", None)
        print_action.connect("activate", lambda a, p: self._on_print())
        action_group.add_action(print_action)

        view_source_action = Gio.SimpleAction.new("view-source", None)
        view_source_action.connect("activate", lambda a, p: self._on_view_source())
        action_group.add_action(view_source_action)

        mark_unread_action = Gio.SimpleAction.new("mark-unread", None)
        mark_unread_action.connect("activate", lambda a, p: self._on_mark_unread())
        action_group.add_action(mark_unread_action)

    def set_message(self, message: Any) -> None:
        """Set the message to display.

        Args:
            message: Message model object or dict with message data.
        """
        self._message = message

        if message is None:
            self._show_empty_state()
            return

        # Show content
        self._empty_box.set_visible(False)
        self._scrolled.set_visible(True)
        self._toolbar.set_visible(True)

        # Update header
        if hasattr(message, "from_address"):
            # It's a Message model
            self._header.set_from_message_model(message)
            self._is_starred = message.is_starred
            self._star_button.set_active(self._is_starred)

            # Update body
            self._body.set_content(
                html_content=message.body_html,
                text_content=message.body_text,
            )

            # Update attachments
            if message.attachments:
                attachments = [
                    Attachment.from_dict(att) if isinstance(att, dict) else att
                    for att in message.attachments
                ]
                self._attachments.set_attachments(attachments)
                self._attachments.set_visible(True)
            else:
                self._attachments.clear()
                self._attachments.set_visible(False)
        else:
            # It's a dict
            self._header.set_message(
                from_address=message.get("from_address", ""),
                to_addresses=message.get("to_addresses", []),
                subject=message.get("subject", ""),
                date=message.get("received_at") or message.get("sent_at"),
                cc_addresses=message.get("cc_addresses"),
                attachment_count=len(message.get("attachments", [])),
                headers=message.get("headers"),
            )

            self._is_starred = message.get("is_starred", False)
            self._star_button.set_active(self._is_starred)

            self._body.set_content(
                html_content=message.get("body_html"),
                text_content=message.get("body_text"),
            )

            if message.get("attachments"):
                self._attachments.set_attachments(message["attachments"])
                self._attachments.set_visible(True)
            else:
                self._attachments.clear()
                self._attachments.set_visible(False)

        self._update_star_button()

    def _show_empty_state(self) -> None:
        """Show the empty state."""
        self._scrolled.set_visible(False)
        self._toolbar.set_visible(False)
        self._empty_box.set_visible(True)

    def _update_star_button(self) -> None:
        """Update the star button appearance."""
        if self._is_starred:
            self._star_button.set_icon_name("starred-symbolic")
            self._star_button.set_tooltip_text("Unstar")
        else:
            self._star_button.set_icon_name("non-starred-symbolic")
            self._star_button.set_tooltip_text("Star")

    def set_folders(self, folders: list[tuple[str, str]]) -> None:
        """Set the available folders for move menu.

        Args:
            folders: List of (folder_id, folder_name) tuples.
        """
        self._folders = folders

        # Rebuild folder menu
        self._folder_menu.remove_all()

        for folder_id, folder_name in folders:
            self._folder_menu.append(folder_name, f"message.move-{folder_id}")

            # Add action
            action_group = self.get_action_group("message")
            action = Gio.SimpleAction.new(f"move-{folder_id}", None)
            action.connect("activate", lambda a, p, fid=folder_id: self._on_move_to_folder(fid))
            action_group.add_action(action)

    def set_reply_callback(self, callback: Callable[[], None]) -> None:
        """Set the callback for reply action."""
        self._reply_callback = callback

    def set_reply_all_callback(self, callback: Callable[[], None]) -> None:
        """Set the callback for reply all action."""
        self._reply_all_callback = callback

    def set_forward_callback(self, callback: Callable[[], None]) -> None:
        """Set the callback for forward action."""
        self._forward_callback = callback

    def set_delete_callback(self, callback: Callable[[], None]) -> None:
        """Set the callback for delete action."""
        self._delete_callback = callback

    # Signal handlers

    def _on_reply_clicked(self, button: Gtk.Button) -> None:
        """Handle reply button click."""
        self.emit("reply")
        if self._reply_callback:
            self._reply_callback()

    def _on_reply_all_clicked(self, button: Gtk.Button) -> None:
        """Handle reply all button click."""
        self.emit("reply-all")
        if self._reply_all_callback:
            self._reply_all_callback()

    def _on_forward_clicked(self, button: Gtk.Button) -> None:
        """Handle forward button click."""
        self.emit("forward")
        if self._forward_callback:
            self._forward_callback()

    def _on_star_toggled(self, button: Gtk.ToggleButton) -> None:
        """Handle star button toggle."""
        self._is_starred = button.get_active()
        self._update_star_button()
        self.emit("star-toggled", self._is_starred)

    def _on_delete_clicked(self, button: Gtk.Button) -> None:
        """Handle delete button click."""
        self.emit("delete")
        if self._delete_callback:
            self._delete_callback()

    def _on_move_to_folder(self, folder_id: str) -> None:
        """Handle move to folder action."""
        self.emit("move-to-folder", folder_id)

    def _on_print(self) -> None:
        """Handle print action."""
        self._body.print_message()

    def _on_view_source(self) -> None:
        """Handle view source action."""
        self._body.show_raw_source()

    def _on_mark_unread(self) -> None:
        """Handle mark as unread action."""
        if self._message and hasattr(self._message, "is_read"):
            self._message.is_read = False

    def _on_link_clicked(self, body_view: MessageBodyView, uri: str) -> None:
        """Handle link click in message body."""
        # Links are already opened in browser by MessageBodyView
        pass

    def _on_attachment_download(
        self,
        attachment_list: AttachmentList,
        attachment: Attachment,
    ) -> None:
        """Handle attachment download request."""
        self.emit("attachment-download", attachment)

    def _on_attachment_preview(
        self,
        attachment_list: AttachmentList,
        attachment: Attachment,
    ) -> None:
        """Handle attachment preview request."""
        from .widgets.attachment_list import AttachmentPreviewDialog

        dialog = AttachmentPreviewDialog(
            parent=self.get_root(),
            attachment=attachment,
        )
        dialog.present()

    def _on_attachment_open(
        self,
        attachment_list: AttachmentList,
        attachment: Attachment,
    ) -> None:
        """Handle attachment open request."""
        if attachment.file_path:
            try:
                if hasattr(Gtk, "show_uri"):
                    Gtk.show_uri(None, f"file://{attachment.file_path}", 0)
                else:
                    subprocess.run(["xdg-open", attachment.file_path], check=False)
            except Exception as e:
                print(f"Failed to open attachment: {e}")

    def _on_download_all(self, attachment_list: AttachmentList) -> None:
        """Handle download all attachments request."""
        self.emit("attachment-download-all")

    @property
    def message(self) -> Optional[Any]:
        """Get the current message."""
        return self._message

    @property
    def is_starred(self) -> bool:
        """Check if the current message is starred."""
        return self._is_starred

    def clear(self) -> None:
        """Clear the current message."""
        self.set_message(None)

    def get_css(self) -> str:
        """Get CSS styles for the message viewer widget."""
        return """
        .message-viewer {
            background-color: @view_bg_color;
        }

        .message-toolbar {
            background-color: @headerbar_bg_color;
            padding: 4px 8px;
            border-bottom: 1px solid @borders;
        }

        .message-body {
            min-height: 200px;
        }
        """


# Export all classes
__all__ = [
    "MessageViewer",
    "MessageBodyView",
    "sanitize_html",
    "plain_text_to_html",
]
