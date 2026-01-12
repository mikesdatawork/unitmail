"""
Email Composer module for unitMail.

This module provides functionality to build properly formatted MIME messages
for outgoing email delivery.
"""

import base64
import logging
import mimetypes
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email import encoders
from email.headerregistry import Address
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import format_datetime, make_msgid
from pathlib import Path
from typing import Any, BinaryIO, Optional, Union

from ...common.exceptions import InvalidMessageError
from ...common.models import Message, MessagePriority

logger = logging.getLogger(__name__)


@dataclass
class Attachment:
    """Represents an email attachment."""

    filename: str
    content: bytes
    content_type: str = "application/octet-stream"
    content_id: Optional[str] = None  # For inline attachments

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "Attachment":
        """
        Create an Attachment from a file path.

        Args:
            path: Path to the file.

        Returns:
            Attachment instance.

        Raises:
            FileNotFoundError: If file does not exist.
            InvalidMessageError: If file cannot be read.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Attachment file not found: {path}")

        # Guess content type from extension
        content_type, _ = mimetypes.guess_type(str(path))
        if content_type is None:
            content_type = "application/octet-stream"

        try:
            content = path.read_bytes()
        except Exception as e:
            raise InvalidMessageError(
                f"Failed to read attachment {path}: {e}",
                {"path": str(path), "error": str(e)},
            )

        return cls(
            filename=path.name,
            content=content,
            content_type=content_type,
        )

    @classmethod
    def from_bytes(
        cls,
        content: bytes,
        filename: str,
        content_type: Optional[str] = None,
    ) -> "Attachment":
        """
        Create an Attachment from bytes.

        Args:
            content: File content as bytes.
            filename: The filename to use.
            content_type: Optional MIME type.

        Returns:
            Attachment instance.
        """
        if content_type is None:
            content_type, _ = mimetypes.guess_type(filename)
            if content_type is None:
                content_type = "application/octet-stream"

        return cls(
            filename=filename,
            content=content,
            content_type=content_type,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (without content for serialization)."""
        return {
            "filename": self.filename,
            "content_type": self.content_type,
            "size": len(self.content),
            "content_id": self.content_id,
        }


@dataclass
class EmailRecipient:
    """Represents an email recipient with display name."""

    email: str
    display_name: Optional[str] = None

    def to_address(self) -> Address:
        """Convert to email.headerregistry.Address."""
        if self.display_name:
            # Parse display name for Address
            return Address(display_name=self.display_name, addr_spec=self.email)
        return Address(addr_spec=self.email)

    def to_string(self) -> str:
        """Convert to string format."""
        if self.display_name:
            return f'"{self.display_name}" <{self.email}>'
        return self.email

    @classmethod
    def parse(cls, value: str) -> "EmailRecipient":
        """
        Parse an email address string.

        Handles formats like:
        - "user@example.com"
        - "Display Name <user@example.com>"
        - '"Display Name" <user@example.com>'

        Args:
            value: Email address string.

        Returns:
            EmailRecipient instance.
        """
        value = value.strip()

        # Check for "Display Name <email>" format
        if "<" in value and value.endswith(">"):
            parts = value.rsplit("<", 1)
            display_name = parts[0].strip().strip('"').strip("'").strip()
            email = parts[1].rstrip(">").strip()
            return cls(email=email, display_name=display_name if display_name else None)

        # Plain email address
        return cls(email=value)


@dataclass
class ComposedEmail:
    """Represents a composed email ready for sending."""

    message_id: str
    raw_data: str
    mime_message: MIMEMultipart
    sender: EmailRecipient
    recipients: list[EmailRecipient]
    subject: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def get_envelope_from(self) -> str:
        """Get the envelope FROM address."""
        return self.sender.email

    def get_envelope_to(self) -> list[str]:
        """Get the envelope TO addresses."""
        return [r.email for r in self.recipients]


class EmailComposer:
    """
    Composes properly formatted MIME email messages.

    This class handles:
    - Building MIME multipart messages
    - Adding headers (From, To, CC, BCC, Subject, Date, Message-ID)
    - Attaching files with proper MIME types
    - Supporting HTML and plain text bodies
    - Generating Message-IDs
    """

    def __init__(
        self,
        default_domain: str = "localhost",
        default_charset: str = "utf-8",
        organization: Optional[str] = None,
        x_mailer: Optional[str] = None,
    ) -> None:
        """
        Initialize the email composer.

        Args:
            default_domain: Domain to use for Message-ID generation.
            default_charset: Default character set for text content.
            organization: Optional Organization header value.
            x_mailer: Optional X-Mailer header value.
        """
        self.default_domain = default_domain
        self.default_charset = default_charset
        self.organization = organization
        self.x_mailer = x_mailer or "unitMail/1.0"

        logger.debug(
            "EmailComposer initialized with domain=%s, charset=%s",
            default_domain,
            default_charset,
        )

    def generate_message_id(self, domain: Optional[str] = None) -> str:
        """
        Generate a unique Message-ID.

        Args:
            domain: Optional domain to use (defaults to default_domain).

        Returns:
            Message-ID string in format <unique-id@domain>.
        """
        domain = domain or self.default_domain
        return make_msgid(domain=domain)

    def _parse_recipient(
        self, value: Union[str, EmailRecipient]
    ) -> EmailRecipient:
        """Parse a recipient value to EmailRecipient."""
        if isinstance(value, EmailRecipient):
            return value
        return EmailRecipient.parse(value)

    def _parse_recipients(
        self, values: list[Union[str, EmailRecipient]]
    ) -> list[EmailRecipient]:
        """Parse a list of recipients."""
        return [self._parse_recipient(v) for v in values]

    def _create_text_part(
        self, content: str, subtype: str = "plain"
    ) -> MIMEText:
        """Create a text MIME part."""
        return MIMEText(content, subtype, self.default_charset)

    def _create_attachment_part(self, attachment: Attachment) -> MIMEBase:
        """
        Create a MIME part for an attachment.

        Args:
            attachment: The Attachment object.

        Returns:
            MIMEBase part configured for the attachment.
        """
        # Parse content type
        maintype, subtype = attachment.content_type.split("/", 1)

        if maintype == "text":
            # Text attachments
            try:
                content_str = attachment.content.decode(self.default_charset)
                part = MIMEText(content_str, subtype, self.default_charset)
            except UnicodeDecodeError:
                # Fall back to base64 encoding for binary text
                part = MIMEBase(maintype, subtype)
                part.set_payload(attachment.content)
                encoders.encode_base64(part)
        else:
            # Binary attachments
            part = MIMEBase(maintype, subtype)
            part.set_payload(attachment.content)
            encoders.encode_base64(part)

        # Set Content-Disposition header
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=attachment.filename,
        )

        # Set Content-ID for inline attachments
        if attachment.content_id:
            part.add_header("Content-ID", f"<{attachment.content_id}>")

        return part

    def _get_priority_headers(
        self, priority: MessagePriority
    ) -> dict[str, str]:
        """
        Get priority-related headers.

        Args:
            priority: Message priority level.

        Returns:
            Dictionary of header names to values.
        """
        headers: dict[str, str] = {}

        if priority == MessagePriority.LOW:
            headers["X-Priority"] = "5"
            headers["X-MSMail-Priority"] = "Low"
            headers["Importance"] = "Low"
        elif priority == MessagePriority.HIGH:
            headers["X-Priority"] = "2"
            headers["X-MSMail-Priority"] = "High"
            headers["Importance"] = "High"
        elif priority == MessagePriority.URGENT:
            headers["X-Priority"] = "1"
            headers["X-MSMail-Priority"] = "High"
            headers["Importance"] = "High"
        # Normal priority doesn't need headers

        return headers

    def compose(
        self,
        sender: Union[str, EmailRecipient],
        to: list[Union[str, EmailRecipient]],
        subject: str,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        cc: Optional[list[Union[str, EmailRecipient]]] = None,
        bcc: Optional[list[Union[str, EmailRecipient]]] = None,
        attachments: Optional[list[Attachment]] = None,
        reply_to: Optional[Union[str, EmailRecipient]] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[list[str]] = None,
        message_id: Optional[str] = None,
        date: Optional[datetime] = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        custom_headers: Optional[dict[str, str]] = None,
    ) -> ComposedEmail:
        """
        Compose an email message.

        Args:
            sender: The sender's email address.
            to: List of recipient email addresses.
            subject: Email subject line.
            body_text: Plain text body content.
            body_html: HTML body content.
            cc: Optional list of CC recipients.
            bcc: Optional list of BCC recipients.
            attachments: Optional list of attachments.
            reply_to: Optional Reply-To address.
            in_reply_to: Optional In-Reply-To Message-ID.
            references: Optional list of Reference Message-IDs.
            message_id: Optional custom Message-ID.
            date: Optional custom date (defaults to now).
            priority: Message priority level.
            custom_headers: Optional custom headers to add.

        Returns:
            ComposedEmail instance.

        Raises:
            InvalidMessageError: If message is invalid.
        """
        # Validate inputs
        if not to:
            raise InvalidMessageError("At least one recipient is required")

        if not body_text and not body_html:
            raise InvalidMessageError("Message body (text or HTML) is required")

        # Parse addresses
        sender_recipient = self._parse_recipient(sender)
        to_recipients = self._parse_recipients(to)
        cc_recipients = self._parse_recipients(cc) if cc else []
        bcc_recipients = self._parse_recipients(bcc) if bcc else []
        all_recipients = to_recipients + cc_recipients + bcc_recipients

        # Generate Message-ID if not provided
        if message_id is None:
            # Try to get domain from sender email
            sender_domain = sender_recipient.email.split("@")[-1] if "@" in sender_recipient.email else None
            message_id = self.generate_message_id(sender_domain)

        # Create the message structure
        # Determine message type based on content
        has_attachments = attachments and len(attachments) > 0
        has_both_bodies = body_text and body_html

        if has_attachments:
            # Multipart/mixed for attachments
            msg = MIMEMultipart("mixed")

            if has_both_bodies:
                # Create alternative part for text/html
                alt_part = MIMEMultipart("alternative")
                alt_part.attach(self._create_text_part(body_text, "plain"))
                alt_part.attach(self._create_text_part(body_html, "html"))
                msg.attach(alt_part)
            elif body_html:
                msg.attach(self._create_text_part(body_html, "html"))
            else:
                msg.attach(self._create_text_part(body_text or "", "plain"))

            # Add attachments
            for attachment in attachments:
                msg.attach(self._create_attachment_part(attachment))

        elif has_both_bodies:
            # Multipart/alternative for text and HTML
            msg = MIMEMultipart("alternative")
            msg.attach(self._create_text_part(body_text, "plain"))
            msg.attach(self._create_text_part(body_html, "html"))

        else:
            # Simple message with single body
            if body_html:
                msg = MIMEMultipart()
                msg.attach(self._create_text_part(body_html, "html"))
            else:
                msg = MIMEMultipart()
                msg.attach(self._create_text_part(body_text or "", "plain"))

        # Set headers
        msg["From"] = sender_recipient.to_string()
        msg["To"] = ", ".join(r.to_string() for r in to_recipients)
        msg["Subject"] = subject
        msg["Date"] = format_datetime(date or datetime.now(timezone.utc))
        msg["Message-ID"] = message_id

        # Optional recipients
        if cc_recipients:
            msg["Cc"] = ", ".join(r.to_string() for r in cc_recipients)

        # Note: BCC is not added to headers (by design)

        # Reply-To
        if reply_to:
            reply_to_recipient = self._parse_recipient(reply_to)
            msg["Reply-To"] = reply_to_recipient.to_string()

        # Threading headers
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
        if references:
            msg["References"] = " ".join(references)

        # Priority headers
        priority_headers = self._get_priority_headers(priority)
        for header, value in priority_headers.items():
            msg[header] = value

        # Standard headers
        msg["MIME-Version"] = "1.0"

        if self.x_mailer:
            msg["X-Mailer"] = self.x_mailer

        if self.organization:
            msg["Organization"] = self.organization

        # Custom headers
        if custom_headers:
            for header, value in custom_headers.items():
                msg[header] = value

        # Generate raw message data
        raw_data = msg.as_string()

        logger.debug(
            "Composed email: message_id=%s, from=%s, to=%d recipients, size=%d bytes",
            message_id,
            sender_recipient.email,
            len(all_recipients),
            len(raw_data),
        )

        return ComposedEmail(
            message_id=message_id,
            raw_data=raw_data,
            mime_message=msg,
            sender=sender_recipient,
            recipients=all_recipients,
            subject=subject,
        )

    def compose_from_message(self, message: Message) -> str:
        """
        Compose raw email data from a Message model.

        Args:
            message: The Message model to compose.

        Returns:
            Raw email data as string.

        Raises:
            InvalidMessageError: If message is invalid.
        """
        # Convert attachment metadata to Attachment objects
        attachments = []
        for att_data in message.attachments:
            if "content" in att_data:
                # Content is base64 encoded
                content = base64.b64decode(att_data["content"])
            else:
                # No content, skip
                logger.warning("Attachment %s has no content", att_data.get("filename", "unknown"))
                continue

            attachments.append(
                Attachment(
                    filename=att_data.get("filename", "attachment"),
                    content=content,
                    content_type=att_data.get("content_type", "application/octet-stream"),
                    content_id=att_data.get("content_id"),
                )
            )

        # Compose the email
        composed = self.compose(
            sender=str(message.from_address),
            to=[str(addr) for addr in message.to_addresses],
            subject=message.subject,
            body_text=message.body_text,
            body_html=message.body_html,
            cc=[str(addr) for addr in message.cc_addresses],
            bcc=[str(addr) for addr in message.bcc_addresses],
            attachments=attachments if attachments else None,
            message_id=message.message_id,
            priority=message.priority,
            custom_headers=message.headers,
        )

        return composed.raw_data

    def compose_reply(
        self,
        original_message: Message,
        sender: Union[str, EmailRecipient],
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        reply_all: bool = False,
        include_attachments: bool = False,
    ) -> ComposedEmail:
        """
        Compose a reply to a message.

        Args:
            original_message: The message being replied to.
            sender: The sender's email address.
            body_text: Plain text body.
            body_html: HTML body.
            reply_all: Whether to reply to all recipients.
            include_attachments: Whether to include original attachments.

        Returns:
            ComposedEmail instance.
        """
        # Determine recipients
        to = [str(original_message.from_address)]

        cc = None
        if reply_all:
            # Add original To and CC, excluding sender
            sender_email = self._parse_recipient(sender).email.lower()
            additional = [
                str(addr)
                for addr in original_message.to_addresses + original_message.cc_addresses
                if str(addr).lower() != sender_email
                and str(addr).lower() != str(original_message.from_address).lower()
            ]
            if additional:
                cc = additional

        # Build subject with Re: prefix
        subject = original_message.subject
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"

        # Build references
        references = []
        if original_message.headers.get("References"):
            references.extend(original_message.headers["References"].split())
        if original_message.message_id:
            references.append(original_message.message_id)

        # Handle attachments
        attachments = None
        if include_attachments and original_message.attachments:
            attachments = []
            for att_data in original_message.attachments:
                if "content" in att_data:
                    content = base64.b64decode(att_data["content"])
                    attachments.append(
                        Attachment(
                            filename=att_data.get("filename", "attachment"),
                            content=content,
                            content_type=att_data.get("content_type", "application/octet-stream"),
                        )
                    )

        return self.compose(
            sender=sender,
            to=to,
            cc=cc,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
            in_reply_to=original_message.message_id,
            references=references if references else None,
        )

    def compose_forward(
        self,
        original_message: Message,
        sender: Union[str, EmailRecipient],
        to: list[Union[str, EmailRecipient]],
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        include_attachments: bool = True,
    ) -> ComposedEmail:
        """
        Compose a forwarded message.

        Args:
            original_message: The message being forwarded.
            sender: The sender's email address.
            to: List of recipient email addresses.
            body_text: Optional text to prepend.
            body_html: Optional HTML to prepend.
            include_attachments: Whether to include original attachments.

        Returns:
            ComposedEmail instance.
        """
        # Build subject with Fwd: prefix
        subject = original_message.subject
        if not subject.lower().startswith("fwd:"):
            subject = f"Fwd: {subject}"

        # Build forwarding header
        forward_header = self._build_forward_header(original_message)

        # Combine body content
        final_text = None
        if body_text or original_message.body_text:
            parts = []
            if body_text:
                parts.append(body_text)
            parts.append(forward_header)
            if original_message.body_text:
                parts.append(original_message.body_text)
            final_text = "\n\n".join(parts)

        final_html = None
        if body_html or original_message.body_html:
            parts = []
            if body_html:
                parts.append(body_html)
            parts.append(f"<hr><pre>{forward_header}</pre>")
            if original_message.body_html:
                parts.append(original_message.body_html)
            final_html = "\n".join(parts)

        # Handle attachments
        attachments = None
        if include_attachments and original_message.attachments:
            attachments = []
            for att_data in original_message.attachments:
                if "content" in att_data:
                    content = base64.b64decode(att_data["content"])
                    attachments.append(
                        Attachment(
                            filename=att_data.get("filename", "attachment"),
                            content=content,
                            content_type=att_data.get("content_type", "application/octet-stream"),
                        )
                    )

        return self.compose(
            sender=sender,
            to=to,
            subject=subject,
            body_text=final_text,
            body_html=final_html,
            attachments=attachments,
        )

    def _build_forward_header(self, message: Message) -> str:
        """Build the forwarding header text."""
        lines = [
            "---------- Forwarded message ----------",
            f"From: {message.from_address}",
            f"Date: {message.sent_at or message.created_at}",
            f"Subject: {message.subject}",
            f"To: {', '.join(str(a) for a in message.to_addresses)}",
        ]
        if message.cc_addresses:
            lines.append(f"Cc: {', '.join(str(a) for a in message.cc_addresses)}")
        lines.append("-" * 40)
        return "\n".join(lines)


# Factory function
def create_email_composer(
    domain: str = "localhost",
    charset: str = "utf-8",
    organization: Optional[str] = None,
    x_mailer: Optional[str] = None,
) -> EmailComposer:
    """
    Factory function to create an EmailComposer.

    Args:
        domain: Domain for Message-ID generation.
        charset: Default character set.
        organization: Optional Organization header.
        x_mailer: Optional X-Mailer header.

    Returns:
        Configured EmailComposer instance.
    """
    return EmailComposer(
        default_domain=domain,
        default_charset=charset,
        organization=organization,
        x_mailer=x_mailer,
    )
