"""
Email composer window for unitMail.

Provides a full-featured email composition interface with:
- Recipient fields (To, CC, BCC) with auto-complete
- Subject line
- Rich text body editor with formatting
- Attachment management
- Signature insertion
- Reply/Forward modes
"""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GObject, Gdk, Pango, GLib
from typing import Optional, List, Callable
from enum import Enum
from dataclasses import dataclass

from .widgets.recipient_entry import RecipientEntry
from .widgets.attachment_panel import AttachmentPanel


class ComposerMode(Enum):
    """Mode of the composer window."""
    NEW = "new"
    REPLY = "reply"
    REPLY_ALL = "reply_all"
    FORWARD = "forward"
    EDIT = "edit"  # For editing existing drafts


@dataclass
class EmailMessage:
    """Represents an email message for reply/forward."""
    message_id: Optional[str] = None
    subject: str = ""
    sender: str = ""
    recipients: List[str] = None
    cc: List[str] = None
    date: str = ""
    body: str = ""
    html_body: Optional[str] = None

    def __post_init__(self):
        if self.recipients is None:
            self.recipients = []
        if self.cc is None:
            self.cc = []


class ComposerWindow(Gtk.Window):
    """
    Email composer window.

    Signals:
        send-requested: Emitted when user clicks Send
        save-draft-requested: Emitted when user clicks Save Draft
        discard-requested: Emitted when user clicks Discard
    """

    __gsignals__ = {
        'send-requested': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'save-draft-requested': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'discard-requested': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self,
                 mode: ComposerMode = ComposerMode.NEW,
                 original_message: Optional[EmailMessage] = None,
                 contacts_provider: Optional[Callable[[], List[dict]]] = None,
                 signature: str = "",
                 application: Optional[Gtk.Application] = None,
                 draft_message_id: Optional[str] = None):
        """
        Initialize the composer window.

        Args:
            mode: Composition mode (new, reply, reply_all, forward, edit)
            original_message: Original message for reply/forward
            contacts_provider: Callable returning contacts for auto-complete
            signature: Default signature to insert
            application: Parent application
            draft_message_id: Message ID when editing an existing draft (for update operations)
        """
        super().__init__(
            title=self._get_title(mode),
            default_width=700,
            default_height=600,
            application=application
        )

        self._mode = mode
        self._original_message = original_message
        self._contacts_provider = contacts_provider
        self._signature = signature
        self._is_modified = False
        self._draft_message_id = draft_message_id  # For editing existing drafts

        # Setup window
        self._setup_header_bar()
        self._setup_content()
        self._setup_actions()
        self._apply_styles()

        # Initialize based on mode
        if mode != ComposerMode.NEW and original_message:
            self._setup_reply_forward()
        elif signature:
            self._insert_signature()

        # Track modifications
        self._connect_modification_tracking()

    def _get_title(self, mode: ComposerMode) -> str:
        """Get window title based on mode."""
        titles = {
            ComposerMode.NEW: "New Message",
            ComposerMode.REPLY: "Reply",
            ComposerMode.REPLY_ALL: "Reply All",
            ComposerMode.FORWARD: "Forward",
            ComposerMode.EDIT: "Edit Draft",
        }
        return titles.get(mode, "Compose")

    def _setup_header_bar(self):
        """Setup the header bar with action buttons."""
        header = Gtk.HeaderBar()
        self.set_titlebar(header)

        # Send button (primary action)
        self.send_button = Gtk.Button(label="Send")
        self.send_button.add_css_class("suggested-action")
        self.send_button.set_tooltip_text("Send message (Ctrl+Return)")
        self.send_button.connect("clicked", self._on_send_clicked)
        header.pack_end(self.send_button)

        # Save draft button
        self.save_button = Gtk.Button()
        self.save_button.set_icon_name("document-save-symbolic")
        self.save_button.set_tooltip_text("Save as draft (Ctrl+S)")
        self.save_button.connect("clicked", self._on_save_clicked)
        header.pack_end(self.save_button)

        # Discard button
        self.discard_button = Gtk.Button()
        self.discard_button.set_icon_name("user-trash-symbolic")
        self.discard_button.set_tooltip_text("Discard message")
        self.discard_button.connect("clicked", self._on_discard_clicked)
        header.pack_start(self.discard_button)

        # Attachment button
        self.attach_button = Gtk.Button()
        self.attach_button.set_icon_name("mail-attachment-symbolic")
        self.attach_button.set_tooltip_text("Add attachment")
        self.attach_button.connect("clicked", self._on_attach_clicked)
        header.pack_start(self.attach_button)

    def _setup_content(self):
        """Setup the main content area."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(main_box)

        # Recipients and subject area
        fields_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        fields_box.set_margin_top(12)
        fields_box.set_margin_bottom(8)
        fields_box.set_margin_start(12)
        fields_box.set_margin_end(12)

        # To field
        to_row = self._create_field_row("To:")
        self.to_entry = RecipientEntry(
            placeholder="Recipients",
            contacts_provider=self._contacts_provider
        )
        self.to_entry.set_hexpand(True)
        to_row.append(self.to_entry)
        fields_box.append(to_row)

        # CC field (expandable)
        self.cc_revealer = Gtk.Revealer()
        self.cc_revealer.set_reveal_child(False)
        cc_row = self._create_field_row("CC:")
        self.cc_entry = RecipientEntry(
            placeholder="CC recipients",
            contacts_provider=self._contacts_provider
        )
        self.cc_entry.set_hexpand(True)
        cc_row.append(self.cc_entry)
        self.cc_revealer.set_child(cc_row)
        fields_box.append(self.cc_revealer)

        # BCC field (expandable)
        self.bcc_revealer = Gtk.Revealer()
        self.bcc_revealer.set_reveal_child(False)
        bcc_row = self._create_field_row("BCC:")
        self.bcc_entry = RecipientEntry(
            placeholder="BCC recipients",
            contacts_provider=self._contacts_provider
        )
        self.bcc_entry.set_hexpand(True)
        bcc_row.append(self.bcc_entry)
        self.bcc_revealer.set_child(bcc_row)
        fields_box.append(self.bcc_revealer)

        # CC/BCC toggle buttons
        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toggle_box.set_halign(Gtk.Align.END)

        self.cc_toggle = Gtk.ToggleButton(label="CC")
        self.cc_toggle.add_css_class("flat")
        self.cc_toggle.connect("toggled", self._on_cc_toggled)
        toggle_box.append(self.cc_toggle)

        self.bcc_toggle = Gtk.ToggleButton(label="BCC")
        self.bcc_toggle.add_css_class("flat")
        self.bcc_toggle.connect("toggled", self._on_bcc_toggled)
        toggle_box.append(self.bcc_toggle)

        fields_box.append(toggle_box)

        # Subject field
        subject_row = self._create_field_row("Subject:")
        self.subject_entry = Gtk.Entry()
        self.subject_entry.set_placeholder_text("Subject")
        self.subject_entry.set_hexpand(True)
        subject_row.append(self.subject_entry)
        fields_box.append(subject_row)

        main_box.append(fields_box)

        # Separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.append(separator)

        # Formatting toolbar
        self._create_formatting_toolbar(main_box)

        # Body editor
        self._create_body_editor(main_box)

        # Attachment panel (hidden by default)
        self.attachment_revealer = Gtk.Revealer()
        self.attachment_revealer.set_reveal_child(False)
        self.attachment_panel = AttachmentPanel()
        self.attachment_panel.set_parent_window(self)
        self.attachment_panel.set_margin_start(12)
        self.attachment_panel.set_margin_end(12)
        self.attachment_panel.set_margin_bottom(12)
        self.attachment_panel.connect('attachments-changed', self._on_attachments_changed)
        self.attachment_panel.connect('size-limit-exceeded', self._on_size_limit_exceeded)
        self.attachment_revealer.set_child(self.attachment_panel)
        main_box.append(self.attachment_revealer)

    def _create_field_row(self, label_text: str) -> Gtk.Box:
        """Create a labeled field row."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        label = Gtk.Label(label=label_text)
        label.set_width_chars(8)
        label.set_xalign(1.0)
        label.add_css_class("dim-label")
        row.append(label)

        return row

    def _create_formatting_toolbar(self, parent: Gtk.Box):
        """Create the formatting toolbar."""
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)
        toolbar.set_margin_top(8)
        toolbar.set_margin_bottom(8)

        # Bold button
        self.bold_button = Gtk.ToggleButton()
        self.bold_button.set_icon_name("format-text-bold-symbolic")
        self.bold_button.set_tooltip_text("Bold (Ctrl+B)")
        self.bold_button.connect("toggled", self._on_bold_toggled)
        toolbar.append(self.bold_button)

        # Italic button
        self.italic_button = Gtk.ToggleButton()
        self.italic_button.set_icon_name("format-text-italic-symbolic")
        self.italic_button.set_tooltip_text("Italic (Ctrl+I)")
        self.italic_button.connect("toggled", self._on_italic_toggled)
        toolbar.append(self.italic_button)

        # Underline button
        self.underline_button = Gtk.ToggleButton()
        self.underline_button.set_icon_name("format-text-underline-symbolic")
        self.underline_button.set_tooltip_text("Underline (Ctrl+U)")
        self.underline_button.connect("toggled", self._on_underline_toggled)
        toolbar.append(self.underline_button)

        # Strikethrough button
        self.strike_button = Gtk.ToggleButton()
        self.strike_button.set_icon_name("format-text-strikethrough-symbolic")
        self.strike_button.set_tooltip_text("Strikethrough")
        self.strike_button.connect("toggled", self._on_strike_toggled)
        toolbar.append(self.strike_button)

        # Separator
        toolbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        # Font selector
        self.font_button = Gtk.FontDialogButton()
        font_dialog = Gtk.FontDialog()
        font_dialog.set_title("Select Font")
        self.font_button.set_dialog(font_dialog)
        self.font_button.set_tooltip_text("Select font")
        self.font_button.connect("notify::font-desc", self._on_font_changed)
        toolbar.append(self.font_button)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        toolbar.append(spacer)

        # Signature button
        signature_button = Gtk.Button()
        signature_button.set_icon_name("contact-new-symbolic")
        signature_button.set_tooltip_text("Insert signature")
        signature_button.connect("clicked", self._on_signature_clicked)
        toolbar.append(signature_button)

        parent.append(toolbar)

    def _create_body_editor(self, parent: Gtk.Box):
        """Create the body text editor."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_margin_start(12)
        scrolled.set_margin_end(12)
        scrolled.set_margin_bottom(8)

        # Create text view
        self.body_view = Gtk.TextView()
        self.body_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.body_view.set_left_margin(8)
        self.body_view.set_right_margin(8)
        self.body_view.set_top_margin(8)
        self.body_view.set_bottom_margin(8)
        self.body_view.add_css_class("body-editor")

        # Get buffer
        self.body_buffer = self.body_view.get_buffer()

        # Create formatting tags
        self._create_text_tags()

        scrolled.set_child(self.body_view)
        parent.append(scrolled)

    def _create_text_tags(self):
        """Create text tags for formatting."""
        tag_table = self.body_buffer.get_tag_table()

        # Bold tag
        bold_tag = Gtk.TextTag(name="bold")
        bold_tag.set_property("weight", Pango.Weight.BOLD)
        tag_table.add(bold_tag)

        # Italic tag
        italic_tag = Gtk.TextTag(name="italic")
        italic_tag.set_property("style", Pango.Style.ITALIC)
        tag_table.add(italic_tag)

        # Underline tag
        underline_tag = Gtk.TextTag(name="underline")
        underline_tag.set_property("underline", Pango.Underline.SINGLE)
        tag_table.add(underline_tag)

        # Strikethrough tag
        strike_tag = Gtk.TextTag(name="strikethrough")
        strike_tag.set_property("strikethrough", True)
        tag_table.add(strike_tag)

        # Quote tag (for replies)
        quote_tag = Gtk.TextTag(name="quote")
        quote_tag.set_property("foreground", "#666666")
        quote_tag.set_property("left-margin", 20)
        quote_tag.set_property("style", Pango.Style.ITALIC)
        tag_table.add(quote_tag)

    def _setup_actions(self):
        """Setup keyboard shortcuts and actions."""
        # Key controller for shortcuts
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

    def _apply_styles(self):
        """Apply CSS styles."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            .body-editor {
                background-color: @view_bg_color;
                font-family: sans-serif;
                font-size: 11pt;
            }
            .body-editor text {
                background-color: @view_bg_color;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _connect_modification_tracking(self):
        """Connect signals to track modifications."""
        self.to_entry.connect('recipients-changed', self._on_content_modified)
        self.cc_entry.connect('recipients-changed', self._on_content_modified)
        self.bcc_entry.connect('recipients-changed', self._on_content_modified)
        self.subject_entry.connect('changed', self._on_content_modified)
        self.body_buffer.connect('changed', self._on_content_modified)

    def _on_content_modified(self, *args):
        """Handle content modification."""
        self._is_modified = True
        self._update_title()

    def _update_title(self):
        """Update window title to show modification state."""
        title = self._get_title(self._mode)
        subject = self.subject_entry.get_text().strip()
        if subject:
            title = f"{title}: {subject}"
        if self._is_modified:
            title = f"* {title}"
        self.set_title(title)

    # --- Reply/Forward Setup ---

    def _setup_reply_forward(self):
        """Setup the composer for reply/forward mode."""
        if not self._original_message:
            return

        msg = self._original_message

        # Set subject
        subject = msg.subject
        if self._mode == ComposerMode.FORWARD:
            if not subject.lower().startswith("fwd:"):
                subject = f"Fwd: {subject}"
        else:  # Reply modes
            if not subject.lower().startswith("re:"):
                subject = f"Re: {subject}"
        self.subject_entry.set_text(subject)

        # Set recipients
        if self._mode == ComposerMode.REPLY:
            self.to_entry.set_recipients([msg.sender])
        elif self._mode == ComposerMode.REPLY_ALL:
            self.to_entry.set_recipients([msg.sender] + msg.recipients)
            if msg.cc:
                self.cc_entry.set_recipients(msg.cc)
                self.cc_toggle.set_active(True)

        # Quote original message
        self._quote_original_message()

        # Insert signature before quote
        if self._signature:
            self._insert_signature()

        self._is_modified = False

    def _quote_original_message(self):
        """Quote the original message in the body."""
        if not self._original_message:
            return

        msg = self._original_message

        # Build quote header
        quote_header = f"\n\nOn {msg.date}, {msg.sender} wrote:\n"

        # Quote the body
        body_lines = msg.body.split('\n')
        quoted_body = '\n'.join(f"> {line}" for line in body_lines)

        # Insert with quote formatting
        end_iter = self.body_buffer.get_end_iter()
        self.body_buffer.insert(end_iter, quote_header)

        end_iter = self.body_buffer.get_end_iter()
        quote_start = self.body_buffer.create_mark(None, end_iter, True)

        self.body_buffer.insert(end_iter, quoted_body)

        # Apply quote tag
        start_iter = self.body_buffer.get_iter_at_mark(quote_start)
        end_iter = self.body_buffer.get_end_iter()
        self.body_buffer.apply_tag_by_name("quote", start_iter, end_iter)

        # Position cursor at the beginning
        start_iter = self.body_buffer.get_start_iter()
        self.body_buffer.place_cursor(start_iter)

    # --- Signature ---

    def _insert_signature(self):
        """Insert signature into the body."""
        if not self._signature:
            return

        # Get current cursor position
        cursor_mark = self.body_buffer.get_insert()
        cursor_iter = self.body_buffer.get_iter_at_mark(cursor_mark)

        # Insert signature separator and signature
        signature_text = f"\n\n--\n{self._signature}"

        # If we're in reply/forward mode, insert before the quote
        if self._mode != ComposerMode.NEW and self._original_message:
            # Insert at cursor (beginning)
            self.body_buffer.insert(cursor_iter, signature_text)
        else:
            # Insert at end for new messages
            end_iter = self.body_buffer.get_end_iter()
            self.body_buffer.insert(end_iter, signature_text)

    def _on_signature_clicked(self, button):
        """Handle signature button click."""
        self._insert_signature()

    # --- Formatting ---

    def _apply_tag(self, tag_name: str, apply: bool):
        """Apply or remove a tag from the selection."""
        bounds = self.body_buffer.get_selection_bounds()
        if bounds:
            start, end = bounds
            if apply:
                self.body_buffer.apply_tag_by_name(tag_name, start, end)
            else:
                self.body_buffer.remove_tag_by_name(tag_name, start, end)

    def _on_bold_toggled(self, button):
        """Handle bold button toggle."""
        self._apply_tag("bold", button.get_active())

    def _on_italic_toggled(self, button):
        """Handle italic button toggle."""
        self._apply_tag("italic", button.get_active())

    def _on_underline_toggled(self, button):
        """Handle underline button toggle."""
        self._apply_tag("underline", button.get_active())

    def _on_strike_toggled(self, button):
        """Handle strikethrough button toggle."""
        self._apply_tag("strikethrough", button.get_active())

    def _on_font_changed(self, button, pspec):
        """Handle font selection change."""
        font_desc = button.get_font_desc()
        if font_desc:
            # Apply to selection or set as default
            bounds = self.body_buffer.get_selection_bounds()
            if bounds:
                start, end = bounds
                # Create a font tag for this specific font
                tag_name = f"font-{font_desc.to_string()}"
                tag_table = self.body_buffer.get_tag_table()

                tag = tag_table.lookup(tag_name)
                if not tag:
                    tag = Gtk.TextTag(name=tag_name)
                    tag.set_property("font-desc", font_desc)
                    tag_table.add(tag)

                self.body_buffer.apply_tag(tag, start, end)
            else:
                # Set as default font for the view
                self.body_view.override_font(font_desc)

    # --- CC/BCC Toggles ---

    def _on_cc_toggled(self, button):
        """Handle CC toggle."""
        self.cc_revealer.set_reveal_child(button.get_active())

    def _on_bcc_toggled(self, button):
        """Handle BCC toggle."""
        self.bcc_revealer.set_reveal_child(button.get_active())

    # --- Attachments ---

    def _on_attach_clicked(self, button):
        """Handle attach button click."""
        # Show attachment panel if hidden
        if not self.attachment_revealer.get_reveal_child():
            self.attachment_revealer.set_reveal_child(True)

        # Show file chooser
        self.attachment_panel.show_file_chooser()

    def _on_attachments_changed(self, panel):
        """Handle attachments change."""
        has_attachments = panel.has_attachments()
        self.attachment_revealer.set_reveal_child(has_attachments)
        self._is_modified = True
        self._update_title()

    def _on_size_limit_exceeded(self, panel, message):
        """Handle attachment size limit exceeded."""
        dialog = Gtk.AlertDialog()
        dialog.set_message("Attachment Too Large")
        dialog.set_detail(message)
        dialog.set_buttons(["OK"])
        dialog.show(self)

    # --- Actions ---

    def _on_send_clicked(self, button):
        """Handle send button click."""
        if self._validate_for_send():
            self.emit('send-requested')

    def _on_save_clicked(self, button):
        """Handle save button click."""
        self.emit('save-draft-requested')
        self._is_modified = False
        self._update_title()

    def _on_discard_clicked(self, button):
        """Handle discard button click."""
        if self._is_modified:
            self._show_discard_confirmation()
        else:
            self.emit('discard-requested')
            self.close()

    def _show_discard_confirmation(self):
        """Show confirmation dialog for discarding changes."""
        dialog = Gtk.AlertDialog()
        dialog.set_message("Discard Message?")
        dialog.set_detail("You have unsaved changes. Are you sure you want to discard this message?")
        dialog.set_buttons(["Cancel", "Discard"])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)
        dialog.choose(self, None, self._on_discard_dialog_response)

    def _on_discard_dialog_response(self, dialog, result):
        """Handle discard confirmation response."""
        try:
            response = dialog.choose_finish(result)
            if response == 1:  # Discard
                self.emit('discard-requested')
                self.close()
        except GLib.Error:
            pass  # Cancelled

    def _validate_for_send(self) -> bool:
        """Validate the message before sending."""
        errors = []

        # Check recipients
        if not self.to_entry.has_recipients():
            errors.append("Please add at least one recipient.")
        elif not self.to_entry.is_valid():
            errors.append("Some recipient addresses are invalid.")

        # Check CC validation if visible
        if self.cc_revealer.get_reveal_child() and self.cc_entry.has_recipients():
            if not self.cc_entry.is_valid():
                errors.append("Some CC addresses are invalid.")

        # Check BCC validation if visible
        if self.bcc_revealer.get_reveal_child() and self.bcc_entry.has_recipients():
            if not self.bcc_entry.is_valid():
                errors.append("Some BCC addresses are invalid.")

        # Check subject (warning only)
        if not self.subject_entry.get_text().strip():
            # Could show warning but allow sending
            pass

        if errors:
            dialog = Gtk.AlertDialog()
            dialog.set_message("Cannot Send Message")
            dialog.set_detail("\n".join(errors))
            dialog.set_buttons(["OK"])
            dialog.show(self)
            return False

        return True

    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Handle keyboard shortcuts."""
        ctrl = state & Gdk.ModifierType.CONTROL_MASK

        if ctrl:
            if keyval == Gdk.KEY_Return:
                self._on_send_clicked(None)
                return True
            elif keyval == Gdk.KEY_s:
                self._on_save_clicked(None)
                return True
            elif keyval == Gdk.KEY_b:
                self.bold_button.set_active(not self.bold_button.get_active())
                return True
            elif keyval == Gdk.KEY_i:
                self.italic_button.set_active(not self.italic_button.get_active())
                return True
            elif keyval == Gdk.KEY_u:
                self.underline_button.set_active(not self.underline_button.get_active())
                return True

        return False

    # --- Public API ---

    def get_message_data(self) -> dict:
        """
        Get the composed message data.

        Returns:
            Dictionary with message fields
        """
        return {
            'to': self.to_entry.get_recipients(),
            'to_formatted': self.to_entry.get_recipients_formatted(),
            'cc': self.cc_entry.get_recipients() if self.cc_revealer.get_reveal_child() else [],
            'cc_formatted': self.cc_entry.get_recipients_formatted() if self.cc_revealer.get_reveal_child() else [],
            'bcc': self.bcc_entry.get_recipients() if self.bcc_revealer.get_reveal_child() else [],
            'bcc_formatted': self.bcc_entry.get_recipients_formatted() if self.bcc_revealer.get_reveal_child() else [],
            'subject': self.subject_entry.get_text(),
            'body': self._get_body_text(),
            'body_html': self._get_body_html(),
            'attachments': self.attachment_panel.get_attachment_paths(),
            'in_reply_to': self._original_message.message_id if self._original_message else None,
            'mode': self._mode.value,
        }

    def _get_body_text(self) -> str:
        """Get plain text body."""
        start = self.body_buffer.get_start_iter()
        end = self.body_buffer.get_end_iter()
        return self.body_buffer.get_text(start, end, True)

    def _get_body_html(self) -> str:
        """
        Get HTML formatted body.

        This is a simplified implementation that converts
        basic formatting to HTML tags.
        """
        # For a full implementation, you'd iterate through
        # the buffer and convert tags to HTML
        text = self._get_body_text()

        # Basic HTML escaping
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('\n', '<br>\n')

        return f"<html><body>{text}</body></html>"

    def set_to_recipients(self, recipients: List[str]):
        """Set To recipients."""
        self.to_entry.set_recipients(recipients)

    def set_cc_recipients(self, recipients: List[str]):
        """Set CC recipients."""
        if recipients:
            self.cc_toggle.set_active(True)
            self.cc_entry.set_recipients(recipients)

    def set_bcc_recipients(self, recipients: List[str]):
        """Set BCC recipients."""
        if recipients:
            self.bcc_toggle.set_active(True)
            self.bcc_entry.set_recipients(recipients)

    def set_subject(self, subject: str):
        """Set the subject."""
        self.subject_entry.set_text(subject)

    def set_body(self, body: str):
        """Set the body text."""
        self.body_buffer.set_text(body)

    def add_attachment(self, path: str) -> bool:
        """Add an attachment."""
        result = self.attachment_panel.add_attachment(path)
        if result:
            self.attachment_revealer.set_reveal_child(True)
        return result

    def set_signature(self, signature: str):
        """Set the signature for insertion."""
        self._signature = signature

    def is_modified(self) -> bool:
        """Check if the message has been modified."""
        return self._is_modified

    def set_contacts_provider(self, provider: Callable[[], List[dict]]):
        """Set the contacts provider for auto-complete."""
        self._contacts_provider = provider
        self.to_entry.set_contacts_provider(provider)
        self.cc_entry.set_contacts_provider(provider)
        self.bcc_entry.set_contacts_provider(provider)

    def get_draft_message_id(self) -> Optional[str]:
        """
        Get the draft message ID being edited.

        Returns:
            Message ID if editing an existing draft, None otherwise.
        """
        return self._draft_message_id

    def is_editing_draft(self) -> bool:
        """
        Check if this composer is editing an existing draft.

        Returns:
            True if editing an existing draft, False for new compositions.
        """
        return self._draft_message_id is not None


# Convenience function for creating composer windows
def create_composer(mode: str = "new",
                   original_message: Optional[EmailMessage] = None,
                   **kwargs) -> ComposerWindow:
    """
    Create a composer window.

    Args:
        mode: One of "new", "reply", "reply_all", "forward", "edit"
        original_message: Original message for reply/forward
        **kwargs: Additional arguments passed to ComposerWindow

    Returns:
        ComposerWindow instance
    """
    mode_map = {
        "new": ComposerMode.NEW,
        "reply": ComposerMode.REPLY,
        "reply_all": ComposerMode.REPLY_ALL,
        "forward": ComposerMode.FORWARD,
        "edit": ComposerMode.EDIT,
    }
    composer_mode = mode_map.get(mode, ComposerMode.NEW)
    return ComposerWindow(mode=composer_mode, original_message=original_message, **kwargs)
