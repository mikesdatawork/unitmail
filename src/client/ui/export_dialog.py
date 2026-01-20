"""
Export dialog for unitMail.

This module provides a dialog for exporting emails in various formats
including plain text, markdown, PDF, MBOX, and EML.
"""

import logging
from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from client.services.export_service import (
    ExportFormat,
    ExportProgress,
    ExportResult,
    ExportScope,
    ExportService,
    get_export_service,
)
from client.services.settings_service import get_settings_service
from common.storage import get_storage

logger = logging.getLogger(__name__)


class ExportDialog(Adw.Window):
    """
    Dialog for exporting emails.

    Provides options for:
    - Selecting export destination folder
    - Choosing export format (TXT, MD, PDF, MBOX, EML)
    - Selecting export scope (current, folder, all)
    - Progress display
    """

    __gtype_name__ = "ExportDialog"

    def __init__(
        self,
        parent: Optional[Gtk.Window] = None,
        export_service: Optional[ExportService] = None,
        current_message_id: Optional[str] = None,
        current_folder: Optional[str] = None,
    ) -> None:
        """
        Initialize the export dialog.

        Args:
            parent: Parent window.
            export_service: Export service instance.
            current_message_id: ID of currently selected message.
            current_folder: Name of currently selected folder.
        """
        super().__init__(
            title="Export Emails",
            modal=True,
            default_width=500,
            default_height=550,
        )

        if parent:
            self.set_transient_for(parent)

        self._export_service = export_service or get_export_service()
        self._settings_service = get_settings_service()
        self._current_message_id = current_message_id
        self._current_folder = current_folder or "Inbox"
        self._output_path: Optional[Path] = None
        self._is_running = False

        # Load saved export folder from settings
        saved_folder = self._settings_service.backup_export.export_folder
        if saved_folder and Path(saved_folder).exists():
            self._output_path = Path(saved_folder)

        self._build_ui()
        self._connect_signals()

        logger.info("ExportDialog initialized")

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar
        header = Adw.HeaderBar()
        header.add_css_class("flat")

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", self._on_cancel_clicked)
        header.pack_start(cancel_button)
        self._cancel_button = cancel_button

        export_button = Gtk.Button(label="Export")
        export_button.add_css_class("suggested-action")
        export_button.set_sensitive(False)
        export_button.connect("clicked", self._on_export_clicked)
        header.pack_end(export_button)
        self._export_button = export_button

        main_box.append(header)

        # Content area with scroll
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

        # Destination group
        dest_group = Adw.PreferencesGroup(
            title="Export Destination",
            description="Choose where to save the exported files",
        )

        # Show full path as subtitle, or prompt to select
        if self._output_path:
            subtitle_text = str(self._output_path)
        else:
            subtitle_text = "No folder selected"

        self._dest_row = Adw.ActionRow(
            title="Location",
            subtitle=subtitle_text,
        )

        # Open folder button (only visible when folder is selected)
        self._open_folder_button = Gtk.Button(
            label="Open",
            valign=Gtk.Align.CENTER,
            tooltip_text="Open folder in file manager",
            visible=self._output_path is not None,
        )
        self._open_folder_button.connect("clicked", self._on_open_folder_clicked)
        self._dest_row.add_suffix(self._open_folder_button)

        # Browse/Change button
        browse_button = Gtk.Button(
            label="Browse",
            valign=Gtk.Align.CENTER,
            tooltip_text="Select folder",
        )
        browse_button.connect("clicked", self._on_browse_clicked)
        self._dest_row.add_suffix(browse_button)

        dest_group.add(self._dest_row)

        # Filename
        self._filename_row = Adw.EntryRow(
            title="Filename",
        )
        self._filename_row.set_text(self._generate_default_filename())
        self._filename_row.connect("changed", self._validate_form)
        dest_group.add(self._filename_row)

        content.append(dest_group)

        # Format group
        format_group = Adw.PreferencesGroup(
            title="Export Format",
            description="Choose the output format",
        )

        self._format_combo = Adw.ComboRow(
            title="Format",
        )

        # Create format model
        format_model = Gtk.StringList()
        format_model.append("Plain Text (.txt)")
        format_model.append("Markdown (.md)")
        format_model.append("PDF (.pdf)")
        format_model.append("MBOX (.mbox) - Email Migration")
        format_model.append("EML (.eml) - Individual Files")

        self._format_combo.set_model(format_model)
        self._format_combo.set_selected(0)
        self._format_combo.connect("notify::selected", self._on_format_changed)
        format_group.add(self._format_combo)

        # Format description
        self._format_desc_row = Adw.ActionRow(
            title="Format Info",
            subtitle="Simple text format with email headers and body content",
        )
        format_group.add(self._format_desc_row)

        content.append(format_group)

        # Scope group
        scope_group = Adw.PreferencesGroup(
            title="Export Scope",
            description="Choose which messages to export",
        )

        self._scope_combo = Adw.ComboRow(
            title="Messages to Export",
        )

        # Create scope model
        scope_model = Gtk.StringList()
        scope_model.append(f"Current Folder ({self._current_folder})")
        scope_model.append("All Messages")

        self._scope_combo.set_model(scope_model)
        self._scope_combo.set_selected(0)
        scope_group.add(self._scope_combo)

        # Message count info
        storage = get_storage()
        folder_count = len(
            storage.get_messages_by_folder(self._current_folder, limit=10000)
        )
        total_count = storage.get_message_count()

        self._count_row = Adw.ActionRow(
            title="Messages",
            subtitle=f"{folder_count} messages in {self._current_folder}",
        )
        scope_group.add(self._count_row)

        self._scope_combo.connect("notify::selected", self._on_scope_changed)
        self._folder_count = folder_count
        self._total_count = total_count

        content.append(scope_group)

        # Progress group (hidden initially)
        self._progress_group = Adw.PreferencesGroup(
            title="Progress",
            visible=False,
        )

        progress_row = Adw.ActionRow(
            title="Exporting...",
        )
        self._progress_status = progress_row

        self._progress_bar = Gtk.ProgressBar(
            valign=Gtk.Align.CENTER,
            hexpand=True,
            show_text=True,
        )
        self._progress_bar.set_size_request(200, -1)
        progress_row.add_suffix(self._progress_bar)

        self._progress_group.add(progress_row)

        content.append(self._progress_group)

        scrolled.set_child(content)
        main_box.append(scrolled)

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self.connect("close-request", self._on_close_request)

    def _generate_default_filename(self) -> str:
        """Generate a default export filename."""
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"unitmail_export_{timestamp}"

    def _validate_form(self, *args) -> None:
        """Validate form and enable/disable export button."""
        is_valid = True

        # Check destination
        if self._output_path is None:
            is_valid = False

        # Check filename
        filename = self._filename_row.get_text().strip()
        if not filename:
            is_valid = False

        self._export_button.set_sensitive(is_valid and not self._is_running)

    def _on_format_changed(self, combo: Adw.ComboRow, param) -> None:
        """Handle format selection change."""
        selected = combo.get_selected()
        descriptions = [
            "Simple text format with email headers and body content",
            "Formatted text with tables and markdown structure",
            "Print-ready format that preserves the reading pane layout",
            "Standard mailbox format compatible with Thunderbird, Apple Mail, etc.",
            "Individual .eml files that can be opened by any email client",
        ]
        if selected < len(descriptions):
            self._format_desc_row.set_subtitle(descriptions[selected])

    def _on_scope_changed(self, combo: Adw.ComboRow, param) -> None:
        """Handle scope selection change."""
        selected = combo.get_selected()
        if selected == 0:
            self._count_row.set_subtitle(
                f"{self._folder_count} messages in {self._current_folder}"
            )
        else:
            self._count_row.set_subtitle(f"{self._total_count} total messages")

    def _on_browse_clicked(self, button: Gtk.Button) -> None:
        """Handle browse button click."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Select Export Destination")

        # Use saved folder if available, otherwise default to Documents/home
        if self._output_path and self._output_path.exists():
            initial_folder = Gio.File.new_for_path(str(self._output_path))
        else:
            initial_folder = Gio.File.new_for_path(str(Path.home() / "Documents"))
            if not initial_folder.query_exists(None):
                initial_folder = Gio.File.new_for_path(str(Path.home()))

        dialog.set_initial_folder(initial_folder)
        dialog.select_folder(self, None, self._on_folder_selected)

    def _on_folder_selected(
        self,
        dialog: Gtk.FileDialog,
        result: Gio.AsyncResult,
    ) -> None:
        """Handle folder selection response."""
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                self._output_path = Path(folder.get_path())
                self._dest_row.set_subtitle(str(self._output_path))
                self._open_folder_button.set_visible(True)

                # Save to settings
                self._settings_service.update_backup_export(
                    export_folder=str(self._output_path)
                )
                self._settings_service.save()

                self._validate_form()

        except GLib.Error as e:
            if e.code != Gtk.DialogError.DISMISSED:
                logger.error("Failed to select folder: %s", e.message)

    def _on_open_folder_clicked(self, button: Gtk.Button) -> None:
        """Handle open folder button click."""
        if self._output_path and self._output_path.exists():
            import subprocess

            try:
                subprocess.run(["xdg-open", str(self._output_path)], check=False)
            except Exception as e:
                logger.warning(f"Could not open folder: {e}")

    def _on_cancel_clicked(self, button: Gtk.Button) -> None:
        """Handle cancel button click."""
        if self._is_running:
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Cancel Export?",
                body="The export is still in progress. Are you sure?",
            )
            dialog.add_response("continue", "Continue Export")
            dialog.add_response("cancel", "Cancel Export")
            dialog.set_response_appearance(
                "cancel", Adw.ResponseAppearance.DESTRUCTIVE
            )
            dialog.connect("response", self._on_cancel_confirmed)
            dialog.present()
        else:
            self.close()

    def _on_cancel_confirmed(
        self,
        dialog: Adw.MessageDialog,
        response: str,
    ) -> None:
        """Handle cancel confirmation response."""
        if response == "cancel":
            self._is_running = False
            self.close()

    def _on_export_clicked(self, button: Gtk.Button) -> None:
        """Handle export button click."""
        self._start_export()

    def _get_selected_format(self) -> ExportFormat:
        """Get the selected export format."""
        selected = self._format_combo.get_selected()
        formats = [
            ExportFormat.PLAIN_TEXT,
            ExportFormat.MARKDOWN,
            ExportFormat.PDF,
            ExportFormat.MBOX,
            ExportFormat.EML,
        ]
        return formats[selected] if selected < len(formats) else ExportFormat.PLAIN_TEXT

    def _get_selected_scope(self) -> ExportScope:
        """Get the selected export scope."""
        selected = self._scope_combo.get_selected()
        if selected == 0:
            return ExportScope.SELECTED_FOLDER
        return ExportScope.ALL_MESSAGES

    def _start_export(self) -> None:
        """Start the export process."""
        self._is_running = True
        self._export_button.set_sensitive(False)
        self._progress_group.set_visible(True)

        # Get export parameters
        filename = self._filename_row.get_text().strip()
        export_path = self._output_path / filename
        export_format = self._get_selected_format()
        export_scope = self._get_selected_scope()

        # Handle PDF separately (uses GTK print)
        if export_format == ExportFormat.PDF:
            self._export_to_pdf(export_path)
            return

        # Set progress callback
        self._export_service.set_progress_callback(self._on_progress)

        # Run export in thread
        def run_export():
            return self._export_service.export_messages(
                output_path=export_path,
                format=export_format,
                scope=export_scope,
                folder_name=self._current_folder,
                message_id=self._current_message_id,
            )

        def on_complete(result: ExportResult):
            GLib.idle_add(self._on_export_complete, result)

        def on_error(error):
            GLib.idle_add(
                self._on_export_complete,
                ExportResult(
                    success=False,
                    output_path=export_path,
                    messages_exported=0,
                    format=export_format,
                    error_message=str(error),
                ),
            )

        # Run in thread
        import threading

        def thread_target():
            try:
                result = run_export()
                on_complete(result)
            except Exception as e:
                on_error(e)

        thread = threading.Thread(target=thread_target, daemon=True)
        thread.start()

    def _export_to_pdf(self, output_path: Path) -> None:
        """Export messages to PDF using GTK print."""
        # Get messages based on scope
        storage = get_storage()
        scope = self._get_selected_scope()

        if scope == ExportScope.SELECTED_FOLDER:
            messages = storage.get_messages_by_folder(
                self._current_folder, limit=10000
            )
        else:
            messages = storage.get_all_messages(limit=10000)

        if not messages:
            self._show_error("No messages to export")
            return

        # Create print operation for PDF
        print_op = Gtk.PrintOperation()
        print_op.set_n_pages(len(messages))
        print_op.set_export_filename(str(output_path.with_suffix(".pdf")))

        # Store messages for drawing
        self._pdf_messages = messages
        self._pdf_current_page = 0

        print_op.connect("draw-page", self._on_draw_pdf_page)
        print_op.connect("end-print", self._on_pdf_complete)

        try:
            result = print_op.run(
                Gtk.PrintOperationAction.EXPORT, self
            )
            if result == Gtk.PrintOperationResult.ERROR:
                self._show_error("PDF export failed")
        except Exception as e:
            self._show_error(f"PDF export failed: {e}")

    def _on_draw_pdf_page(
        self,
        operation: Gtk.PrintOperation,
        context: Gtk.PrintContext,
        page_nr: int,
    ) -> None:
        """Draw a page for PDF export."""
        if page_nr >= len(self._pdf_messages):
            return

        msg = self._pdf_messages[page_nr]
        cr = context.get_cairo_context()
        width = context.get_width()

        # Set up fonts
        cr.select_font_face("Sans", 0, 1)  # Normal, Bold

        y = 50

        # Draw header
        cr.set_font_size(14)
        subject = msg.get("subject", "(No Subject)")
        cr.move_to(50, y)
        cr.show_text(subject[:80])
        y += 30

        # Draw metadata
        cr.select_font_face("Sans", 0, 0)  # Normal weight
        cr.set_font_size(10)

        cr.move_to(50, y)
        cr.show_text(f"From: {msg.get('from_address', 'Unknown')}")
        y += 18

        cr.move_to(50, y)
        to_addrs = msg.get("to_addresses", [])
        if isinstance(to_addrs, list):
            to_str = ", ".join(to_addrs)
        else:
            to_str = str(to_addrs)
        cr.show_text(f"To: {to_str[:60]}")
        y += 18

        cr.move_to(50, y)
        cr.show_text(f"Date: {msg.get('received_at', '')[:19]}")
        y += 30

        # Draw separator line
        cr.set_line_width(0.5)
        cr.move_to(50, y)
        cr.line_to(width - 50, y)
        cr.stroke()
        y += 20

        # Draw body
        cr.set_font_size(10)
        body = msg.get("body_text") or msg.get("body_html", "")
        if msg.get("body_html") and not msg.get("body_text"):
            # Simple HTML stripping
            import re

            body = re.sub(r"<[^>]+>", "", body)
            body = body.replace("&nbsp;", " ")
            body = body.replace("&amp;", "&")

        # Word wrap and draw
        max_width = width - 100
        lines = body.split("\n")

        for line in lines:
            if y > context.get_height() - 50:
                break

            # Simple word wrapping
            words = line.split()
            current_line = ""

            for word in words:
                test_line = current_line + " " + word if current_line else word
                extents = cr.text_extents(test_line)

                if extents.width > max_width and current_line:
                    cr.move_to(50, y)
                    cr.show_text(current_line)
                    y += 14
                    current_line = word

                    if y > context.get_height() - 50:
                        break
                else:
                    current_line = test_line

            if current_line and y <= context.get_height() - 50:
                cr.move_to(50, y)
                cr.show_text(current_line)
                y += 14

        self._on_progress(
            ExportProgress(
                current_step=f"Exporting page {page_nr + 1}/{len(self._pdf_messages)}",
                items_processed=page_nr + 1,
                total_items=len(self._pdf_messages),
                percent_complete=(page_nr + 1) / len(self._pdf_messages) * 100,
            )
        )

    def _on_pdf_complete(
        self,
        operation: Gtk.PrintOperation,
    ) -> None:
        """Handle PDF export completion."""
        result = ExportResult(
            success=True,
            output_path=self._output_path,
            messages_exported=len(self._pdf_messages),
            format=ExportFormat.PDF,
        )
        self._on_export_complete(result)

    def _on_progress(self, progress: ExportProgress) -> None:
        """Handle progress update from export service."""
        GLib.idle_add(self._update_progress_ui, progress)

    def _update_progress_ui(self, progress: ExportProgress) -> None:
        """Update progress UI (must be called from main thread)."""
        self._progress_status.set_title(progress.current_step)
        self._progress_bar.set_fraction(progress.percent_complete / 100)
        self._progress_bar.set_text(f"{progress.percent_complete:.0f}%")
        return False

    def _on_export_complete(self, result: ExportResult) -> None:
        """Handle export completion."""
        self._is_running = False
        self._export_service.set_progress_callback(None)

        if not result.success:
            self._show_error(result.error_message or "Export failed")
            self._progress_group.set_visible(False)
            self._export_button.set_sensitive(True)
        else:
            self._show_success(result)

        return False

    def _show_error(self, message: str) -> None:
        """Show error dialog."""
        self._is_running = False
        self._progress_group.set_visible(False)
        self._export_button.set_sensitive(True)

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Export Failed",
            body=message,
        )
        dialog.add_response("ok", "OK")
        dialog.present()

    def _show_success(self, result: ExportResult) -> None:
        """Show success dialog."""
        format_names = {
            ExportFormat.PLAIN_TEXT: "Plain Text",
            ExportFormat.MARKDOWN: "Markdown",
            ExportFormat.PDF: "PDF",
            ExportFormat.MBOX: "MBOX",
            ExportFormat.EML: "EML",
        }

        body = (
            f"Successfully exported {result.messages_exported} message(s) "
            f"to {format_names.get(result.format, result.format.value)} format.\n\n"
            f"Location: {result.output_path}"
        )

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Export Complete",
            body=body,
        )
        dialog.add_response("ok", "OK")
        dialog.add_response("open", "Open Folder")
        dialog.set_response_appearance("open", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", self._on_success_response, result)
        dialog.present()

    def _on_success_response(
        self,
        dialog: Adw.MessageDialog,
        response: str,
        result: ExportResult,
    ) -> None:
        """Handle success dialog response."""
        if response == "open":
            # Open the export folder
            import subprocess

            folder_path = (
                result.output_path
                if result.output_path.is_dir()
                else result.output_path.parent
            )
            try:
                subprocess.run(["xdg-open", str(folder_path)], check=False)
            except Exception as e:
                logger.warning(f"Could not open folder: {e}")

        self.close()

    def _on_close_request(self, window: Gtk.Window) -> bool:
        """Handle window close request."""
        if self._is_running:
            self._on_cancel_clicked(None)
            return True
        return False


def create_export_dialog(
    parent: Optional[Gtk.Window] = None,
    current_message_id: Optional[str] = None,
    current_folder: Optional[str] = None,
) -> ExportDialog:
    """
    Create and return an export dialog.

    Args:
        parent: Optional parent window.
        current_message_id: ID of currently selected message.
        current_folder: Name of currently selected folder.

    Returns:
        New ExportDialog instance.
    """
    return ExportDialog(
        parent=parent,
        current_message_id=current_message_id,
        current_folder=current_folder,
    )
