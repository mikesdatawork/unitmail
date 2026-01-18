"""
Email message parser for unitMail SMTP gateway.

This module provides parsing functionality for raw SMTP messages,
extracting headers, body content, and attachments with proper
handling of MIME multipart messages and various encodings.
"""

import email
import email.header
import email.utils
import logging
import mimetypes
import re
from dataclasses import dataclass, field
from datetime import datetime
from email.message import Message
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class Attachment:
    """Represents an email attachment with metadata."""

    id: str = field(default_factory=lambda: str(uuid4()))
    filename: str = ""
    content_type: str = "application/octet-stream"
    content: bytes = b""
    size: int = 0
    content_id: Optional[str] = None
    content_disposition: str = "attachment"
    encoding: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert attachment to dictionary for database storage."""
        return {
            "id": self.id,
            "filename": self.filename,
            "content_type": self.content_type,
            "size": self.size,
            "content_id": self.content_id,
            "content_disposition": self.content_disposition,
            "encoding": self.encoding,
            # Note: content bytes are stored separately in object storage
        }


@dataclass
class ParsedEmail:
    """Represents a fully parsed email message."""

    message_id: str = ""
    from_address: str = ""
    to_addresses: list[str] = field(default_factory=list)
    cc_addresses: list[str] = field(default_factory=list)
    bcc_addresses: list[str] = field(default_factory=list)
    reply_to: Optional[str] = None
    subject: str = ""
    date: Optional[datetime] = None
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    headers: dict[str, str] = field(default_factory=dict)
    attachments: list[Attachment] = field(default_factory=list)
    raw_size: int = 0
    is_multipart: bool = False
    content_type: str = "text/plain"
    charset: str = "utf-8"

    def to_dict(self) -> dict[str, Any]:
        """Convert parsed email to dictionary for database storage."""
        return {
            "message_id": self.message_id,
            "from_address": self.from_address,
            "to_addresses": self.to_addresses,
            "cc_addresses": self.cc_addresses,
            "bcc_addresses": self.bcc_addresses,
            "reply_to": self.reply_to,
            "subject": self.subject,
            "date": self.date.isoformat() if self.date else None,
            "body_text": self.body_text,
            "body_html": self.body_html,
            "headers": self.headers,
            "attachments": [att.to_dict() for att in self.attachments],
            "raw_size": self.raw_size,
            "is_multipart": self.is_multipart,
            "content_type": self.content_type,
            "charset": self.charset,
        }


class EmailParser:
    """
    Parser for raw SMTP email messages.

    Handles MIME multipart messages, various encodings (UTF-8, quoted-printable,
    base64), and extracts all relevant headers and attachments.
    """

    # Common header names we want to preserve
    PRESERVED_HEADERS = {
        "message-id",
        "from",
        "to",
        "cc",
        "bcc",
        "reply-to",
        "subject",
        "date",
        "content-type",
        "content-transfer-encoding",
        "mime-version",
        "x-mailer",
        "x-priority",
        "x-spam-status",
        "x-spam-score",
        "received",
        "dkim-signature",
        "arc-seal",
        "arc-message-signature",
        "arc-authentication-results",
        "authentication-results",
        "return-path",
        "sender",
        "in-reply-to",
        "references",
        "list-unsubscribe",
        "list-id",
        "precedence",
        "auto-submitted",
    }

    def __init__(self, max_attachment_size: int = 50 * 1024 * 1024) -> None:
        """
        Initialize the email parser.

        Args:
            max_attachment_size: Maximum size for individual attachments in bytes.
        """
        self.max_attachment_size = max_attachment_size

    def parse(self, raw_message: bytes | str) -> ParsedEmail:
        """
        Parse a raw email message.

        Args:
            raw_message: The raw email message as bytes or string.

        Returns:
            ParsedEmail object containing all extracted data.

        Raises:
            ValueError: If the message cannot be parsed.
        """
        try:
            if isinstance(raw_message, str):
                raw_bytes = raw_message.encode("utf-8", errors="replace")
            else:
                raw_bytes = raw_message

            # Parse the email message
            msg = email.message_from_bytes(raw_bytes)

            parsed = ParsedEmail(raw_size=len(raw_bytes))

            # Extract headers
            self._extract_headers(msg, parsed)

            # Extract body and attachments
            self._extract_content(msg, parsed)

            logger.debug(
                "Parsed email: message_id=%s, from=%s, to=%s, attachments=%d",
                parsed.message_id,
                parsed.from_address,
                parsed.to_addresses,
                len(parsed.attachments),
            )

            return parsed

        except Exception as e:
            logger.error("Failed to parse email: %s", str(e))
            raise ValueError(f"Failed to parse email message: {e}") from e

    def _extract_headers(self, msg: Message, parsed: ParsedEmail) -> None:
        """Extract and decode email headers."""
        # Message-ID
        parsed.message_id = self._decode_header(msg.get("Message-ID", ""))
        if not parsed.message_id:
            # Generate a Message-ID if missing
            parsed.message_id = f"<{uuid4()}@unitmail.local>"

        # From address
        parsed.from_address = self._extract_email_address(
            self._decode_header(msg.get("From", ""))
        )

        # To addresses
        to_header = msg.get("To", "")
        parsed.to_addresses = self._extract_email_addresses(
            self._decode_header(to_header)
        )

        # CC addresses
        cc_header = msg.get("Cc", "")
        parsed.cc_addresses = self._extract_email_addresses(
            self._decode_header(cc_header)
        )

        # BCC addresses
        bcc_header = msg.get("Bcc", "")
        parsed.bcc_addresses = self._extract_email_addresses(
            self._decode_header(bcc_header)
        )

        # Reply-To
        reply_to = msg.get("Reply-To", "")
        if reply_to:
            parsed.reply_to = self._extract_email_address(
                self._decode_header(reply_to)
            )

        # Subject
        parsed.subject = self._decode_header(msg.get("Subject", ""))

        # Date
        date_header = msg.get("Date", "")
        if date_header:
            parsed.date = self._parse_date(date_header)

        # Content-Type
        content_type = msg.get_content_type()
        parsed.content_type = content_type or "text/plain"
        parsed.is_multipart = msg.is_multipart()

        # Charset
        charset = msg.get_content_charset()
        parsed.charset = charset or "utf-8"

        # Store all preserved headers
        for header_name in self.PRESERVED_HEADERS:
            header_value = msg.get(header_name)
            if header_value:
                # Handle multiple headers with same name (like Received)
                all_values = msg.get_all(header_name, [])
                if len(all_values) > 1:
                    # Join multiple values with newline for storage
                    parsed.headers[header_name] = "\n".join(
                        self._decode_header(v) for v in all_values
                    )
                else:
                    parsed.headers[header_name] = self._decode_header(
                        header_value
                    )

    def _extract_content(self, msg: Message, parsed: ParsedEmail) -> None:
        """Extract body content and attachments from the message."""
        if msg.is_multipart():
            self._extract_multipart_content(msg, parsed)
        else:
            # Single part message
            content_type = msg.get_content_type()
            payload = self._get_payload_decoded(msg)

            if content_type == "text/plain":
                parsed.body_text = payload
            elif content_type == "text/html":
                parsed.body_html = payload
            else:
                # Treat as attachment
                attachment = self._create_attachment(msg, payload)
                if attachment:
                    parsed.attachments.append(attachment)

    def _extract_multipart_content(
        self, msg: Message, parsed: ParsedEmail
    ) -> None:
        """Extract content from multipart message."""
        for part in msg.walk():
            # Skip the container parts
            if part.is_multipart():
                continue

            content_type = part.get_content_type()
            content_disposition = part.get_content_disposition()

            # Check if this is an attachment
            is_attachment = content_disposition == "attachment" or (
                content_disposition == "inline" and part.get_filename()
            )

            if is_attachment:
                payload = self._get_payload_bytes(part)
                attachment = self._create_attachment(part, payload)
                if attachment:
                    parsed.attachments.append(attachment)
            elif content_type == "text/plain" and not parsed.body_text:
                parsed.body_text = self._get_payload_decoded(part)
            elif content_type == "text/html" and not parsed.body_html:
                parsed.body_html = self._get_payload_decoded(part)
            elif content_disposition == "inline":
                # Inline content that's not text - treat as inline attachment
                payload = self._get_payload_bytes(part)
                attachment = self._create_attachment(part, payload)
                if attachment:
                    attachment.content_disposition = "inline"
                    parsed.attachments.append(attachment)

    def _create_attachment(
        self, part: Message, payload: bytes | str
    ) -> Optional[Attachment]:
        """Create an Attachment object from a message part."""
        if isinstance(payload, str):
            content = payload.encode("utf-8", errors="replace")
        else:
            content = payload

        # Check size limit
        if len(content) > self.max_attachment_size:
            logger.warning(
                "Attachment exceeds size limit: %d > %d",
                len(content),
                self.max_attachment_size,
            )
            return None

        filename = part.get_filename()
        if filename:
            filename = self._decode_header(filename)
        else:
            # Generate filename from content type
            content_type = part.get_content_type()
            ext = mimetypes.guess_extension(content_type) or ".bin"
            filename = f"attachment_{uuid4().hex[:8]}{ext}"

        content_type = part.get_content_type()
        content_id = part.get("Content-ID")
        if content_id:
            # Remove angle brackets from Content-ID
            content_id = content_id.strip("<>")

        encoding = part.get("Content-Transfer-Encoding")

        return Attachment(
            filename=filename,
            content_type=content_type,
            content=content,
            size=len(content),
            content_id=content_id,
            content_disposition=part.get_content_disposition() or "attachment",
            encoding=encoding,
        )

    def _get_payload_decoded(self, part: Message) -> str:
        """Get decoded text payload from message part."""
        try:
            payload = part.get_payload(decode=True)
            if payload is None:
                return ""

            # Try to decode with the specified charset
            charset = part.get_content_charset() or "utf-8"
            try:
                return payload.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                # Fallback to utf-8 with error replacement
                return payload.decode("utf-8", errors="replace")

        except Exception as e:
            logger.warning("Failed to decode payload: %s", str(e))
            return ""

    def _get_payload_bytes(self, part: Message) -> bytes:
        """Get raw bytes payload from message part."""
        try:
            payload = part.get_payload(decode=True)
            if payload is None:
                return b""
            return payload
        except Exception as e:
            logger.warning("Failed to get payload bytes: %s", str(e))
            return b""

    def _decode_header(self, header_value: str) -> str:
        """Decode an email header value, handling encoded words."""
        if not header_value:
            return ""

        try:
            decoded_parts = email.header.decode_header(header_value)
            result_parts = []

            for content, charset in decoded_parts:
                if isinstance(content, bytes):
                    try:
                        charset = charset or "utf-8"
                        result_parts.append(
                            content.decode(charset, errors="replace")
                        )
                    except (LookupError, UnicodeDecodeError):
                        result_parts.append(
                            content.decode("utf-8", errors="replace")
                        )
                else:
                    result_parts.append(content)

            return "".join(result_parts).strip()

        except Exception as e:
            logger.warning("Failed to decode header: %s", str(e))
            return str(header_value).strip()

    def _extract_email_address(self, header_value: str) -> str:
        """Extract a single email address from a header value."""
        if not header_value:
            return ""

        # Try to parse the address
        parsed = email.utils.parseaddr(header_value)
        if parsed[1]:
            return parsed[1].lower()

        # Fallback: try to extract email with regex
        match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", header_value)
        if match:
            return match.group(0).lower()

        return header_value.strip().lower()

    def _extract_email_addresses(self, header_value: str) -> list[str]:
        """Extract multiple email addresses from a header value."""
        if not header_value:
            return []

        addresses = []
        # Parse the address list
        parsed_list = email.utils.getaddresses([header_value])

        for _, addr in parsed_list:
            if addr:
                addresses.append(addr.lower())

        # If no addresses found, try regex extraction
        if not addresses:
            matches = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", header_value)
            addresses = [m.lower() for m in matches]

        return addresses

    def _parse_date(self, date_string: str) -> Optional[datetime]:
        """Parse an email date header into a datetime object."""
        try:
            # Use email.utils to parse the date
            parsed = email.utils.parsedate_to_datetime(date_string)
            return parsed
        except (ValueError, TypeError):
            pass

        # Try alternative formats
        alternative_formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S",
            "%d %b %Y %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        ]

        # Remove parenthetical timezone name if present
        date_string = re.sub(r"\s*\([^)]+\)\s*$", "", date_string)

        for fmt in alternative_formats:
            try:
                return datetime.strptime(date_string.strip(), fmt)
            except ValueError:
                continue

        logger.warning("Failed to parse date: %s", date_string)
        return None

    def validate_message(self, parsed: ParsedEmail) -> list[str]:
        """
        Validate a parsed email message.

        Args:
            parsed: The parsed email to validate.

        Returns:
            List of validation error messages (empty if valid).
        """
        errors = []

        if not parsed.from_address:
            errors.append("Missing From address")

        if (
            not parsed.to_addresses
            and not parsed.cc_addresses
            and not parsed.bcc_addresses
        ):
            errors.append("No recipients specified")

        # Validate email address format
        email_pattern = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")

        if parsed.from_address and not email_pattern.match(
            parsed.from_address
        ):
            errors.append(
                f"Invalid From address format: {parsed.from_address}"
            )

        for addr in parsed.to_addresses:
            if not email_pattern.match(addr):
                errors.append(f"Invalid To address format: {addr}")

        for addr in parsed.cc_addresses:
            if not email_pattern.match(addr):
                errors.append(f"Invalid CC address format: {addr}")

        for addr in parsed.bcc_addresses:
            if not email_pattern.match(addr):
                errors.append(f"Invalid BCC address format: {addr}")

        return errors
