"""
Export service for unitMail.

This module provides functionality for exporting emails in various formats:
- Plain Text (.txt)
- Markdown (.md)
- MBOX (.mbox) - Standard mailbox format for email migration
- EML (.eml) - Individual email files (RFC 5322)
- PDF (.pdf) - Via GTK print-to-PDF
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from common.storage import get_storage

logger = logging.getLogger(__name__)


class ExportFormat(str, Enum):
    """Supported export formats."""

    PLAIN_TEXT = "txt"
    MARKDOWN = "md"
    MBOX = "mbox"
    EML = "eml"
    PDF = "pdf"


class ExportScope(str, Enum):
    """Scope of export operation."""

    CURRENT_MESSAGE = "current"
    SELECTED_FOLDER = "folder"
    ALL_MESSAGES = "all"


@dataclass
class ExportProgress:
    """Progress information for export operation."""

    current_step: str
    items_processed: int
    total_items: int
    percent_complete: float


@dataclass
class ExportResult:
    """Result of export operation."""

    success: bool
    output_path: Path
    messages_exported: int
    format: ExportFormat
    error_message: Optional[str] = None


class ExportService:
    """
    Service for exporting emails in various formats.

    Supports:
    - Plain text export with headers and body
    - Markdown export with formatted structure
    - MBOX format for email client migration
    - EML format for individual message files
    - PDF export (via GTK PrintOperation)
    """

    def __init__(self) -> None:
        """Initialize the export service."""
        self._progress_callback: Optional[Callable[[ExportProgress], None]] = None
        self._storage = get_storage()
        logger.info("ExportService initialized")

    def set_progress_callback(
        self, callback: Optional[Callable[[ExportProgress], None]]
    ) -> None:
        """Set callback for progress updates."""
        self._progress_callback = callback

    def _report_progress(
        self,
        step: str,
        processed: int,
        total: int,
    ) -> None:
        """Report progress to callback."""
        if self._progress_callback:
            percent = (processed / total * 100) if total > 0 else 0
            progress = ExportProgress(
                current_step=step,
                items_processed=processed,
                total_items=total,
                percent_complete=percent,
            )
            self._progress_callback(progress)

    def export_messages(
        self,
        output_path: Path,
        format: ExportFormat,
        scope: ExportScope,
        folder_name: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> ExportResult:
        """
        Export messages in the specified format.

        Args:
            output_path: Destination path for export.
            format: Export format (txt, md, mbox, eml, pdf).
            scope: Export scope (current, folder, all).
            folder_name: Folder name for folder scope.
            message_id: Message ID for current message scope.

        Returns:
            ExportResult with success status and details.
        """
        try:
            # Gather messages based on scope
            messages = self._get_messages_for_scope(scope, folder_name, message_id)

            if not messages:
                return ExportResult(
                    success=False,
                    output_path=output_path,
                    messages_exported=0,
                    format=format,
                    error_message="No messages to export",
                )

            # Export based on format
            if format == ExportFormat.PLAIN_TEXT:
                return self._export_to_text(output_path, messages)
            elif format == ExportFormat.MARKDOWN:
                return self._export_to_markdown(output_path, messages)
            elif format == ExportFormat.MBOX:
                return self._export_to_mbox(output_path, messages)
            elif format == ExportFormat.EML:
                return self._export_to_eml(output_path, messages)
            else:
                return ExportResult(
                    success=False,
                    output_path=output_path,
                    messages_exported=0,
                    format=format,
                    error_message=f"Unsupported format: {format}",
                )

        except Exception as e:
            logger.error(f"Export failed: {e}")
            return ExportResult(
                success=False,
                output_path=output_path,
                messages_exported=0,
                format=format,
                error_message=str(e),
            )

    def _get_messages_for_scope(
        self,
        scope: ExportScope,
        folder_name: Optional[str],
        message_id: Optional[str],
    ) -> list[dict]:
        """Get messages based on export scope."""
        if scope == ExportScope.CURRENT_MESSAGE and message_id:
            message = self._storage.get_message(message_id)
            return [message] if message else []

        elif scope == ExportScope.SELECTED_FOLDER and folder_name:
            # Get all messages from folder (no limit for export)
            return self._storage.get_messages_by_folder(
                folder_name, limit=10000, offset=0
            )

        elif scope == ExportScope.ALL_MESSAGES:
            return self._storage.get_all_messages(limit=10000, offset=0)

        return []

    def _export_to_text(
        self, output_path: Path, messages: list[dict]
    ) -> ExportResult:
        """Export messages to plain text format."""
        output_path = output_path.with_suffix(".txt")
        total = len(messages)

        with open(output_path, "w", encoding="utf-8") as f:
            for i, msg in enumerate(messages):
                self._report_progress(f"Exporting message {i + 1}/{total}", i, total)

                # Write message header
                f.write("=" * 70 + "\n")
                f.write(f"From: {msg.get('from_address', 'Unknown')}\n")
                f.write(f"To: {self._format_recipients(msg.get('to_addresses', []))}\n")

                if msg.get("cc_addresses"):
                    f.write(f"CC: {self._format_recipients(msg['cc_addresses'])}\n")

                f.write(f"Subject: {msg.get('subject', '(No Subject)')}\n")
                f.write(f"Date: {self._format_date(msg.get('received_at', ''))}\n")
                f.write("=" * 70 + "\n\n")

                # Write body
                body = msg.get("body_text") or msg.get("body_html", "")
                if msg.get("body_html") and not msg.get("body_text"):
                    body = self._html_to_text(body)
                f.write(body + "\n\n")

        self._report_progress("Export complete", total, total)

        return ExportResult(
            success=True,
            output_path=output_path,
            messages_exported=total,
            format=ExportFormat.PLAIN_TEXT,
        )

    def _export_to_markdown(
        self, output_path: Path, messages: list[dict]
    ) -> ExportResult:
        """Export messages to Markdown format."""
        output_path = output_path.with_suffix(".md")
        total = len(messages)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# Exported Emails\n\n")
            f.write(f"*Exported on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
            f.write(f"**Total messages:** {total}\n\n")
            f.write("---\n\n")

            for i, msg in enumerate(messages):
                self._report_progress(f"Exporting message {i + 1}/{total}", i, total)

                subject = msg.get("subject", "(No Subject)")
                f.write(f"## {subject}\n\n")

                # Metadata table
                f.write("| Field | Value |\n")
                f.write("|-------|-------|\n")
                f.write(f"| **From** | {msg.get('from_address', 'Unknown')} |\n")
                f.write(f"| **To** | {self._format_recipients(msg.get('to_addresses', []))} |\n")

                if msg.get("cc_addresses"):
                    f.write(f"| **CC** | {self._format_recipients(msg['cc_addresses'])} |\n")

                f.write(f"| **Date** | {self._format_date(msg.get('received_at', ''))} |\n")

                if msg.get("is_starred"):
                    f.write("| **Starred** | ⭐ Yes |\n")
                if msg.get("is_important"):
                    f.write("| **Important** | ❗ Yes |\n")

                f.write("\n### Content\n\n")

                # Write body
                body = msg.get("body_text") or msg.get("body_html", "")
                if msg.get("body_html") and not msg.get("body_text"):
                    body = self._html_to_text(body)

                # Escape markdown special characters in body
                f.write(body + "\n\n")
                f.write("---\n\n")

        self._report_progress("Export complete", total, total)

        return ExportResult(
            success=True,
            output_path=output_path,
            messages_exported=total,
            format=ExportFormat.MARKDOWN,
        )

    def _export_to_mbox(
        self, output_path: Path, messages: list[dict]
    ) -> ExportResult:
        """
        Export messages to MBOX format (RFC 4155).

        MBOX is a standard format for storing email messages in a single file,
        widely supported by email clients like Thunderbird, Apple Mail, etc.
        """
        output_path = output_path.with_suffix(".mbox")
        total = len(messages)

        with open(output_path, "w", encoding="utf-8") as f:
            for i, msg in enumerate(messages):
                self._report_progress(f"Exporting message {i + 1}/{total}", i, total)

                # MBOX format: each message starts with "From " line
                from_addr = msg.get("from_address", "unknown@unknown.com")
                # Extract just the email address if it contains a name
                if "<" in from_addr and ">" in from_addr:
                    from_addr = from_addr.split("<")[1].split(">")[0]

                received_at = msg.get("received_at", "")
                try:
                    dt = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
                    mbox_date = dt.strftime("%a %b %d %H:%M:%S %Y")
                except (ValueError, AttributeError):
                    mbox_date = datetime.now().strftime("%a %b %d %H:%M:%S %Y")

                f.write(f"From {from_addr} {mbox_date}\n")

                # Write headers
                f.write(f"From: {msg.get('from_address', 'Unknown')}\n")
                f.write(f"To: {self._format_recipients(msg.get('to_addresses', []))}\n")

                if msg.get("cc_addresses"):
                    f.write(f"Cc: {self._format_recipients(msg['cc_addresses'])}\n")

                f.write(f"Subject: {msg.get('subject', '')}\n")
                f.write(f"Date: {self._format_rfc2822_date(msg.get('received_at', ''))}\n")

                if msg.get("message_id"):
                    f.write(f"Message-ID: {msg['message_id']}\n")
                else:
                    f.write(f"Message-ID: {make_msgid()}\n")

                if msg.get("in_reply_to"):
                    f.write(f"In-Reply-To: {msg['in_reply_to']}\n")

                f.write("MIME-Version: 1.0\n")
                f.write("Content-Type: text/plain; charset=utf-8\n")
                f.write("Content-Transfer-Encoding: 8bit\n")
                f.write("\n")  # End of headers

                # Write body (escape "From " lines at start of lines)
                body = msg.get("body_text") or ""
                if not body and msg.get("body_html"):
                    body = self._html_to_text(msg["body_html"])

                # MBOX requires escaping lines starting with "From "
                lines = body.split("\n")
                for line in lines:
                    if line.startswith("From "):
                        f.write(">" + line + "\n")
                    else:
                        f.write(line + "\n")

                f.write("\n")  # Blank line between messages

        self._report_progress("Export complete", total, total)

        return ExportResult(
            success=True,
            output_path=output_path,
            messages_exported=total,
            format=ExportFormat.MBOX,
        )

    def _export_to_eml(
        self, output_path: Path, messages: list[dict]
    ) -> ExportResult:
        """
        Export messages to individual EML files (RFC 5322).

        Each message is saved as a separate .eml file that can be
        opened by most email clients.
        """
        # Create directory for EML files
        output_dir = output_path.with_suffix("")
        if output_dir.suffix:
            output_dir = output_path.parent / output_path.stem

        output_dir.mkdir(parents=True, exist_ok=True)
        total = len(messages)

        for i, msg in enumerate(messages):
            self._report_progress(f"Exporting message {i + 1}/{total}", i, total)

            # Create email message
            email_msg = MIMEMultipart("alternative")

            # Set headers
            email_msg["From"] = msg.get("from_address", "unknown@unknown.com")
            email_msg["To"] = self._format_recipients(msg.get("to_addresses", []))

            if msg.get("cc_addresses"):
                email_msg["Cc"] = self._format_recipients(msg["cc_addresses"])

            email_msg["Subject"] = msg.get("subject", "")
            email_msg["Date"] = self._format_rfc2822_date(msg.get("received_at", ""))

            if msg.get("message_id"):
                email_msg["Message-ID"] = msg["message_id"]
            else:
                email_msg["Message-ID"] = make_msgid()

            if msg.get("in_reply_to"):
                email_msg["In-Reply-To"] = msg["in_reply_to"]

            # Add body parts
            if msg.get("body_text"):
                text_part = MIMEText(msg["body_text"], "plain", "utf-8")
                email_msg.attach(text_part)

            if msg.get("body_html"):
                html_part = MIMEText(msg["body_html"], "html", "utf-8")
                email_msg.attach(html_part)

            # Generate safe filename
            subject = msg.get("subject", "no_subject")[:50]
            safe_subject = "".join(
                c if c.isalnum() or c in " -_" else "_" for c in subject
            )
            timestamp = msg.get("received_at", "")[:10].replace("-", "")
            filename = f"{timestamp}_{safe_subject}_{i + 1}.eml"

            eml_path = output_dir / filename
            with open(eml_path, "w", encoding="utf-8") as f:
                f.write(email_msg.as_string())

        self._report_progress("Export complete", total, total)

        return ExportResult(
            success=True,
            output_path=output_dir,
            messages_exported=total,
            format=ExportFormat.EML,
        )

    def _format_recipients(self, recipients: list | str) -> str:
        """Format recipient list as string."""
        if isinstance(recipients, str):
            try:
                recipients = json.loads(recipients)
            except (json.JSONDecodeError, TypeError):
                return recipients

        if isinstance(recipients, list):
            return ", ".join(recipients)
        return str(recipients)

    def _format_date(self, date_str: str) -> str:
        """Format date string for display."""
        if not date_str:
            return "Unknown"
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, AttributeError):
            return date_str

    def _format_rfc2822_date(self, date_str: str) -> str:
        """Format date string to RFC 2822 format for email headers."""
        if not date_str:
            return formatdate(localtime=True)
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return formatdate(dt.timestamp(), localtime=True)
        except (ValueError, AttributeError):
            return formatdate(localtime=True)

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text."""
        import re

        # Remove script and style elements
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)

        # Replace common HTML entities
        text = text.replace("&nbsp;", " ")
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')

        # Replace <br> and <p> with newlines
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)

        # Remove all other HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Clean up whitespace
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = text.strip()

        return text

    def get_message_for_print(self, message_id: str) -> Optional[dict]:
        """Get a message formatted for printing."""
        return self._storage.get_message(message_id)


# Singleton instance
_export_service: Optional[ExportService] = None


def get_export_service() -> ExportService:
    """Get the singleton export service instance."""
    global _export_service
    if _export_service is None:
        _export_service = ExportService()
    return _export_service
