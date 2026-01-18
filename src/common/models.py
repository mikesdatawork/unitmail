"""
Pydantic models for unitMail database entities.

This module defines all data models used throughout the application,
providing validation, serialization, and type safety.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class MessageStatus(str, Enum):
    """Status of an email message."""

    DRAFT = "draft"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RECEIVED = "received"


class MessagePriority(str, Enum):
    """Priority level for messages."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class QueueItemStatus(str, Enum):
    """Status of a queue item."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class MeshPeerStatus(str, Enum):
    """Status of a mesh network peer."""

    ONLINE = "online"
    OFFLINE = "offline"
    CONNECTING = "connecting"
    ERROR = "error"


class FolderType(str, Enum):
    """Type of email folder."""

    INBOX = "inbox"
    SENT = "sent"
    DRAFTS = "drafts"
    TRASH = "trash"
    SPAM = "spam"
    ARCHIVE = "archive"
    CUSTOM = "custom"


class BaseDBModel(BaseModel):
    """Base model for all database entities."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True,
    )

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary for database operations."""
        data = self.model_dump(mode="json")
        # Convert UUID to string for database
        if "id" in data and isinstance(data["id"], str):
            pass  # Already serialized
        return data


class User(BaseDBModel):
    """User account model."""

    email: EmailStr = Field(..., description="User's email address")
    username: str = Field(
        ..., min_length=3, max_length=50, description="User's username"
    )
    display_name: Optional[str] = Field(
        None, max_length=100, description="Display name"
    )
    password_hash: str = Field(..., description="Hashed password")
    is_active: bool = Field(
        default=True, description="Whether the user is active"
    )
    is_verified: bool = Field(
        default=False, description="Whether the email is verified"
    )
    last_login: Optional[datetime] = Field(
        None, description="Last login timestamp"
    )
    settings: dict[str, Any] = Field(
        default_factory=dict, description="User settings JSON"
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format."""
        if not v.isalnum() and "-" not in v and "_" not in v:
            raise ValueError(
                "Username must be alphanumeric (hyphens and underscores allowed)"
            )
        return v.lower()


class Message(BaseDBModel):
    """Email message model."""

    user_id: UUID = Field(..., description="Owner user ID")
    folder_id: Optional[UUID] = Field(None, description="Folder ID")
    message_id: str = Field(..., description="RFC 5322 Message-ID")
    from_address: EmailStr = Field(..., description="Sender email address")
    to_addresses: list[EmailStr] = Field(
        default_factory=list, description="Recipient email addresses"
    )
    cc_addresses: list[EmailStr] = Field(
        default_factory=list, description="CC email addresses"
    )
    bcc_addresses: list[EmailStr] = Field(
        default_factory=list, description="BCC email addresses"
    )
    subject: str = Field(
        default="", max_length=998, description="Message subject"
    )
    body_text: Optional[str] = Field(None, description="Plain text body")
    body_html: Optional[str] = Field(None, description="HTML body")
    headers: dict[str, str] = Field(
        default_factory=dict, description="Email headers"
    )
    attachments: list[dict[str, Any]] = Field(
        default_factory=list, description="Attachment metadata"
    )
    status: MessageStatus = Field(
        default=MessageStatus.RECEIVED, description="Message status"
    )
    priority: MessagePriority = Field(
        default=MessagePriority.NORMAL, description="Message priority"
    )
    is_read: bool = Field(
        default=False, description="Whether the message is read"
    )
    is_starred: bool = Field(
        default=False, description="Whether the message is starred"
    )
    is_encrypted: bool = Field(
        default=False, description="Whether the message is encrypted"
    )
    received_at: Optional[datetime] = Field(
        None, description="When message was received"
    )
    sent_at: Optional[datetime] = Field(
        None, description="When message was sent"
    )

    @field_validator(
        "to_addresses", "cc_addresses", "bcc_addresses", mode="before"
    )
    @classmethod
    def ensure_list(cls, v: Any) -> list:
        """Ensure address fields are lists."""
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return list(v)


class Contact(BaseDBModel):
    """Contact/address book entry model."""

    user_id: UUID = Field(..., description="Owner user ID")
    email: EmailStr = Field(..., description="Contact email address")
    name: Optional[str] = Field(
        None, max_length=200, description="Contact name"
    )
    nickname: Optional[str] = Field(
        None, max_length=50, description="Contact nickname"
    )
    phone: Optional[str] = Field(
        None, max_length=20, description="Phone number"
    )
    organization: Optional[str] = Field(
        None, max_length=200, description="Organization name"
    )
    notes: Optional[str] = Field(None, description="Additional notes")
    is_favorite: bool = Field(
        default=False, description="Whether contact is favorited"
    )
    tags: list[str] = Field(default_factory=list, description="Contact tags")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    @field_validator("tags", mode="before")
    @classmethod
    def ensure_tags_list(cls, v: Any) -> list:
        """Ensure tags is a list."""
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return list(v)


class QueueItem(BaseDBModel):
    """Message queue item model."""

    message_id: UUID = Field(..., description="Associated message ID")
    user_id: UUID = Field(..., description="Owner user ID")
    recipient: EmailStr = Field(..., description="Target recipient")
    status: QueueItemStatus = Field(
        default=QueueItemStatus.PENDING, description="Queue item status"
    )
    priority: int = Field(
        default=0, ge=0, le=100, description="Priority (higher = more urgent)"
    )
    attempts: int = Field(
        default=0, ge=0, description="Number of delivery attempts"
    )
    max_attempts: int = Field(
        default=5, ge=1, description="Maximum delivery attempts"
    )
    last_attempt_at: Optional[datetime] = Field(
        None, description="Last attempt timestamp"
    )
    next_attempt_at: Optional[datetime] = Field(
        None, description="Next scheduled attempt"
    )
    error_message: Optional[str] = Field(
        None, description="Last error message"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class Config(BaseDBModel):
    """Application configuration model."""

    user_id: Optional[UUID] = Field(
        None, description="User ID for user-specific config, None for global"
    )
    key: str = Field(
        ..., min_length=1, max_length=255, description="Configuration key"
    )
    value: Any = Field(..., description="Configuration value")
    description: Optional[str] = Field(
        None, description="Description of the setting"
    )
    is_secret: bool = Field(
        default=False, description="Whether value should be hidden in UI"
    )
    category: str = Field(
        default="general", description="Configuration category"
    )

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        """Validate configuration key format."""
        # Allow alphanumeric, dots, underscores, hyphens
        if not all(c.isalnum() or c in "._-" for c in v):
            raise ValueError(
                "Key must contain only alphanumeric characters, "
                "dots, underscores, or hyphens"
            )
        return v.lower()


class MeshPeer(BaseDBModel):
    """Mesh network peer model."""

    peer_id: str = Field(..., description="Unique peer identifier")
    host: str = Field(..., description="Peer hostname or IP")
    port: int = Field(..., ge=1, le=65535, description="Peer port")
    public_key: Optional[str] = Field(
        None, description="Peer's public key (PEM)"
    )
    status: MeshPeerStatus = Field(
        default=MeshPeerStatus.OFFLINE, description="Peer status"
    )
    last_seen: Optional[datetime] = Field(
        None, description="Last seen timestamp"
    )
    last_error: Optional[str] = Field(None, description="Last error message")
    capabilities: list[str] = Field(
        default_factory=list, description="Peer capabilities"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    is_trusted: bool = Field(
        default=False, description="Whether peer is trusted"
    )
    priority: int = Field(
        default=0, ge=0, le=100, description="Routing priority"
    )

    @property
    def address(self) -> str:
        """Get the full peer address."""
        return f"{self.host}:{self.port}"


class Folder(BaseDBModel):
    """Email folder model."""

    user_id: UUID = Field(..., description="Owner user ID")
    name: str = Field(
        ..., min_length=1, max_length=100, description="Folder name"
    )
    folder_type: FolderType = Field(
        default=FolderType.CUSTOM, description="Folder type"
    )
    parent_id: Optional[UUID] = Field(
        None, description="Parent folder ID for nesting"
    )
    color: Optional[str] = Field(
        None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Folder color (hex)"
    )
    icon: Optional[str] = Field(
        None, max_length=50, description="Folder icon name"
    )
    sort_order: int = Field(default=0, description="Sort order for display")
    is_system: bool = Field(
        default=False, description="Whether this is a system folder"
    )
    message_count: int = Field(
        default=0, ge=0, description="Number of messages"
    )
    unread_count: int = Field(
        default=0, ge=0, description="Number of unread messages"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate folder name."""
        # Don't allow certain special characters
        forbidden = ["/", "\\", "<", ">", ":", '"', "|", "?", "*"]
        if any(c in v for c in forbidden):
            raise ValueError(
                f"Folder name cannot contain: {' '.join(forbidden)}"
            )
        return v.strip()


# Request/Response models for API operations
class MessageCreate(BaseModel):
    """Model for creating a new message."""

    model_config = ConfigDict(use_enum_values=True)

    to_addresses: list[EmailStr]
    cc_addresses: list[EmailStr] = Field(default_factory=list)
    bcc_addresses: list[EmailStr] = Field(default_factory=list)
    subject: str = Field(default="", max_length=998)
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    priority: MessagePriority = MessagePriority.NORMAL
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class MessageUpdate(BaseModel):
    """Model for updating a message."""

    model_config = ConfigDict(use_enum_values=True)

    folder_id: Optional[UUID] = None
    is_read: Optional[bool] = None
    is_starred: Optional[bool] = None
    status: Optional[MessageStatus] = None


class ContactCreate(BaseModel):
    """Model for creating a new contact."""

    email: EmailStr
    name: Optional[str] = None
    nickname: Optional[str] = None
    phone: Optional[str] = None
    organization: Optional[str] = None
    notes: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class ContactUpdate(BaseModel):
    """Model for updating a contact."""

    email: Optional[EmailStr] = None
    name: Optional[str] = None
    nickname: Optional[str] = None
    phone: Optional[str] = None
    organization: Optional[str] = None
    notes: Optional[str] = None
    is_favorite: Optional[bool] = None
    tags: Optional[list[str]] = None


class FolderCreate(BaseModel):
    """Model for creating a new folder."""

    model_config = ConfigDict(use_enum_values=True)

    name: str = Field(..., min_length=1, max_length=100)
    folder_type: FolderType = FolderType.CUSTOM
    parent_id: Optional[UUID] = None
    color: Optional[str] = None
    icon: Optional[str] = None


class FolderUpdate(BaseModel):
    """Model for updating a folder."""

    name: Optional[str] = None
    parent_id: Optional[UUID] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
