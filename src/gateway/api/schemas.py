"""
Pydantic schemas for unitMail Gateway API request/response validation.

This module provides Pydantic models for validating API requests and
serializing responses, ensuring type safety and consistent data structures.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Generic, Optional, TypeVar
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


# =============================================================================
# Base Schemas
# =============================================================================


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class TimestampMixin(BaseModel):
    """Mixin for models with timestamp fields."""

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# =============================================================================
# Authentication Schemas
# =============================================================================


class LoginRequest(BaseSchema):
    """Schema for user login request."""

    email: EmailStr = Field(
        ...,
        description="User's email address",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="User's password",
        examples=["SecurePassword123!"],
    )
    remember_me: bool = Field(
        default=False,
        description="Whether to extend token expiration",
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password is not empty after stripping."""
        if not v.strip():
            raise ValueError("Password cannot be empty or whitespace")
        return v


class LoginResponse(BaseSchema):
    """Schema for successful login response."""

    access_token: str = Field(
        ...,
        description="JWT access token for API authentication",
    )
    token_type: str = Field(
        default="Bearer",
        description="Token type (always 'Bearer')",
    )
    expires_in: int = Field(
        ...,
        description="Access token expiration time in seconds",
        examples=[3600],
    )
    refresh_token: Optional[str] = Field(
        None,
        description="JWT refresh token for obtaining new access tokens",
    )
    refresh_expires_in: Optional[int] = Field(
        None,
        description="Refresh token expiration time in seconds",
        examples=[604800],
    )
    user: Optional["UserResponse"] = Field(
        None,
        description="Authenticated user information",
    )


class RefreshRequest(BaseSchema):
    """Schema for token refresh request."""

    refresh_token: str = Field(
        ...,
        min_length=10,
        description="Valid refresh token",
    )


class RefreshResponse(BaseSchema):
    """Schema for token refresh response."""

    access_token: str = Field(
        ...,
        description="New JWT access token",
    )
    token_type: str = Field(
        default="Bearer",
        description="Token type (always 'Bearer')",
    )
    expires_in: int = Field(
        ...,
        description="Access token expiration time in seconds",
    )
    refresh_token: Optional[str] = Field(
        None,
        description="New refresh token (if rotated)",
    )
    refresh_expires_in: Optional[int] = Field(
        None,
        description="Refresh token expiration time in seconds",
    )


class LogoutRequest(BaseSchema):
    """Schema for logout request."""

    refresh_token: Optional[str] = Field(
        None,
        description="Refresh token to revoke (optional)",
    )
    all_devices: bool = Field(
        default=False,
        description="Whether to logout from all devices",
    )


# =============================================================================
# User Schemas
# =============================================================================


class UserResponse(BaseSchema, TimestampMixin):
    """Schema for user information response."""

    id: UUID = Field(..., description="User's unique identifier")
    email: EmailStr = Field(..., description="User's email address")
    username: str = Field(..., description="User's username")
    display_name: Optional[str] = Field(
        None, description="User's display name"
    )
    is_active: bool = Field(
        default=True, description="Whether the user is active"
    )
    is_verified: bool = Field(
        default=False, description="Whether email is verified"
    )
    is_admin: bool = Field(
        default=False, description="Whether user has admin privileges"
    )
    last_login: Optional[datetime] = Field(
        None, description="Last login timestamp"
    )
    settings: dict[str, Any] = Field(
        default_factory=dict, description="User settings"
    )


class UserCreateRequest(BaseSchema):
    """Schema for user registration request."""

    email: EmailStr = Field(..., description="User's email address")
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Username (alphanumeric, underscores, hyphens)",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="User's password",
    )
    display_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Display name",
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets strength requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError(
                "Password must contain at least one uppercase letter"
            )
        if not any(c.islower() for c in v):
            raise ValueError(
                "Password must contain at least one lowercase letter"
            )
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Normalize username to lowercase."""
        return v.lower()


class UserUpdateRequest(BaseSchema):
    """Schema for updating user information."""

    display_name: Optional[str] = Field(None, max_length=100)
    settings: Optional[dict[str, Any]] = None


class PasswordChangeRequest(BaseSchema):
    """Schema for password change request."""

    current_password: str = Field(
        ...,
        min_length=1,
        description="Current password",
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password",
    )

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Validate new password meets strength requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError(
                "Password must contain at least one uppercase letter"
            )
        if not any(c.islower() for c in v):
            raise ValueError(
                "Password must contain at least one lowercase letter"
            )
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v

    @model_validator(mode="after")
    def validate_passwords_different(self) -> "PasswordChangeRequest":
        """Ensure new password is different from current."""
        if self.current_password == self.new_password:
            raise ValueError(
                "New password must be different from current password"
            )
        return self


# =============================================================================
# Message Schemas
# =============================================================================


class MessagePriority(str, Enum):
    """Message priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MessageStatus(str, Enum):
    """Message status values."""

    DRAFT = "draft"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RECEIVED = "received"


class MessageListRequest(BaseSchema):
    """Schema for message list request parameters."""

    folder_id: Optional[UUID] = Field(None, description="Filter by folder ID")
    status: Optional[MessageStatus] = Field(
        None, description="Filter by status"
    )
    is_read: Optional[bool] = Field(None, description="Filter by read status")
    is_starred: Optional[bool] = Field(
        None, description="Filter by starred status"
    )
    search: Optional[str] = Field(
        None,
        max_length=200,
        description="Search term for subject/body",
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of messages to return",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of messages to skip",
    )
    order_by: str = Field(
        default="created_at",
        pattern=r"^(created_at|updated_at|subject)$",
        description="Field to order by",
    )
    order_dir: str = Field(
        default="desc",
        pattern=r"^(asc|desc)$",
        description="Order direction (asc or desc)",
    )


class MessageResponse(BaseSchema, TimestampMixin):
    """Schema for message response."""

    id: UUID = Field(..., description="Message unique identifier")
    folder_id: Optional[UUID] = Field(None, description="Folder ID")
    message_id: str = Field(..., description="RFC 5322 Message-ID")
    from_address: EmailStr = Field(..., description="Sender email address")
    to_addresses: list[EmailStr] = Field(
        default_factory=list,
        description="Recipient email addresses",
    )
    cc_addresses: list[EmailStr] = Field(
        default_factory=list,
        description="CC email addresses",
    )
    bcc_addresses: list[EmailStr] = Field(
        default_factory=list,
        description="BCC email addresses",
    )
    subject: str = Field(default="", description="Message subject")
    body_text: Optional[str] = Field(None, description="Plain text body")
    body_html: Optional[str] = Field(None, description="HTML body")
    status: MessageStatus = Field(
        default=MessageStatus.RECEIVED,
        description="Message status",
    )
    priority: MessagePriority = Field(
        default=MessagePriority.NORMAL,
        description="Message priority",
    )
    is_read: bool = Field(default=False, description="Whether message is read")
    is_starred: bool = Field(
        default=False, description="Whether message is starred"
    )
    is_encrypted: bool = Field(
        default=False, description="Whether message is encrypted"
    )
    attachments: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Attachment metadata",
    )
    received_at: Optional[datetime] = Field(None, description="When received")
    sent_at: Optional[datetime] = Field(None, description="When sent")


class MessageCreateRequest(BaseSchema):
    """Schema for creating a new message."""

    to_addresses: list[EmailStr] = Field(
        ...,
        min_length=1,
        description="Recipient email addresses",
    )
    cc_addresses: list[EmailStr] = Field(
        default_factory=list,
        description="CC email addresses",
    )
    bcc_addresses: list[EmailStr] = Field(
        default_factory=list,
        description="BCC email addresses",
    )
    subject: str = Field(
        default="",
        max_length=998,
        description="Message subject",
    )
    body_text: Optional[str] = Field(None, description="Plain text body")
    body_html: Optional[str] = Field(None, description="HTML body")
    priority: MessagePriority = Field(
        default=MessagePriority.NORMAL,
        description="Message priority",
    )

    @model_validator(mode="after")
    def validate_body(self) -> "MessageCreateRequest":
        """Ensure at least one body type is provided."""
        if not self.body_text and not self.body_html:
            raise ValueError(
                "At least one of body_text or body_html is required"
            )
        return self


class MessageUpdateRequest(BaseSchema):
    """Schema for updating a message."""

    folder_id: Optional[UUID] = Field(None, description="Move to folder")
    is_read: Optional[bool] = Field(None, description="Mark as read/unread")
    is_starred: Optional[bool] = Field(None, description="Star/unstar")


# =============================================================================
# Contact Schemas
# =============================================================================


class ContactRequest(BaseSchema):
    """Schema for creating or updating a contact."""

    email: EmailStr = Field(..., description="Contact email address")
    name: Optional[str] = Field(
        None,
        max_length=200,
        description="Contact name",
    )
    nickname: Optional[str] = Field(
        None,
        max_length=50,
        description="Contact nickname",
    )
    phone: Optional[str] = Field(
        None,
        max_length=20,
        pattern=r"^[\d\s\-\+\(\)]+$",
        description="Phone number",
    )
    organization: Optional[str] = Field(
        None,
        max_length=200,
        description="Organization name",
    )
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Additional notes",
    )
    is_favorite: bool = Field(
        default=False,
        description="Whether contact is a favorite",
    )
    tags: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Contact tags",
    )

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Validate and normalize tags."""
        return [tag.strip().lower() for tag in v if tag.strip()]


class ContactResponse(BaseSchema, TimestampMixin):
    """Schema for contact response."""

    id: UUID = Field(..., description="Contact unique identifier")
    email: EmailStr = Field(..., description="Contact email address")
    name: Optional[str] = Field(None, description="Contact name")
    nickname: Optional[str] = Field(None, description="Contact nickname")
    phone: Optional[str] = Field(None, description="Phone number")
    organization: Optional[str] = Field(None, description="Organization name")
    notes: Optional[str] = Field(None, description="Additional notes")
    is_favorite: bool = Field(
        default=False, description="Whether contact is a favorite"
    )
    tags: list[str] = Field(default_factory=list, description="Contact tags")


class ContactListRequest(BaseSchema):
    """Schema for contact list request parameters."""

    search: Optional[str] = Field(
        None,
        max_length=100,
        description="Search term for name/email",
    )
    is_favorite: Optional[bool] = Field(
        None, description="Filter by favorite status"
    )
    tag: Optional[str] = Field(
        None, max_length=50, description="Filter by tag"
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Maximum number of contacts to return",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of contacts to skip",
    )


# =============================================================================
# Folder Schemas
# =============================================================================


class FolderType(str, Enum):
    """Folder type values."""

    INBOX = "inbox"
    SENT = "sent"
    DRAFTS = "drafts"
    TRASH = "trash"
    SPAM = "spam"
    ARCHIVE = "archive"
    CUSTOM = "custom"


class FolderRequest(BaseSchema):
    """Schema for creating or updating a folder."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Folder name",
    )
    folder_type: FolderType = Field(
        default=FolderType.CUSTOM,
        description="Folder type",
    )
    parent_id: Optional[UUID] = Field(
        None,
        description="Parent folder ID for nesting",
    )
    color: Optional[str] = Field(
        None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Folder color (hex, e.g., #FF5733)",
    )
    icon: Optional[str] = Field(
        None,
        max_length=50,
        description="Folder icon name",
    )

    @field_validator("name")
    @classmethod
    def validate_folder_name(cls, v: str) -> str:
        """Validate folder name doesn't contain forbidden characters."""
        forbidden = ["/", "\\", "<", ">", ":", '"', "|", "?", "*"]
        if any(c in v for c in forbidden):
            raise ValueError(
                f"Folder name cannot contain: {' '.join(forbidden)}"
            )
        return v.strip()


class FolderResponse(BaseSchema, TimestampMixin):
    """Schema for folder response."""

    id: UUID = Field(..., description="Folder unique identifier")
    name: str = Field(..., description="Folder name")
    folder_type: FolderType = Field(..., description="Folder type")
    parent_id: Optional[UUID] = Field(None, description="Parent folder ID")
    color: Optional[str] = Field(None, description="Folder color")
    icon: Optional[str] = Field(None, description="Folder icon")
    sort_order: int = Field(default=0, description="Sort order")
    is_system: bool = Field(
        default=False, description="Whether this is a system folder"
    )
    message_count: int = Field(default=0, description="Number of messages")
    unread_count: int = Field(
        default=0, description="Number of unread messages"
    )


class FolderUpdateRequest(BaseSchema):
    """Schema for updating a folder."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    parent_id: Optional[UUID] = None
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    icon: Optional[str] = Field(None, max_length=50)
    sort_order: Optional[int] = Field(None, ge=0)

    @field_validator("name")
    @classmethod
    def validate_folder_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate folder name if provided."""
        if v is None:
            return v
        forbidden = ["/", "\\", "<", ">", ":", '"', "|", "?", "*"]
        if any(c in v for c in forbidden):
            raise ValueError(
                f"Folder name cannot contain: {' '.join(forbidden)}"
            )
        return v.strip()


# =============================================================================
# Error Response Schemas
# =============================================================================


class ErrorDetail(BaseSchema):
    """Schema for error detail information."""

    field: Optional[str] = Field(
        None, description="Field that caused the error"
    )
    message: str = Field(..., description="Error message")
    code: Optional[str] = Field(None, description="Error code")


class ErrorResponse(BaseSchema):
    """Schema for API error response."""

    error: dict[str, Any] = Field(
        ...,
        description="Error information",
    )
    request_id: Optional[str] = Field(
        None,
        description="Request ID for debugging",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="Error timestamp",
    )

    @classmethod
    def create(
        cls,
        code: int,
        name: str,
        message: str,
        request_id: Optional[str] = None,
        details: Optional[list[ErrorDetail]] = None,
    ) -> "ErrorResponse":
        """
        Create an error response.

        Args:
            code: HTTP status code.
            name: Error name.
            message: Error message.
            request_id: Optional request ID.
            details: Optional list of error details.

        Returns:
            ErrorResponse instance.
        """
        error_data = {
            "code": code,
            "name": name,
            "message": message,
        }

        if details:
            error_data["details"] = [d.model_dump() for d in details]

        return cls(
            error=error_data,
            request_id=request_id,
        )


# =============================================================================
# Pagination Schemas
# =============================================================================


T = TypeVar("T")


class PaginatedResponse(BaseSchema, Generic[T]):
    """Generic schema for paginated responses."""

    items: list[T] = Field(..., description="List of items")
    total: int = Field(..., ge=0, description="Total number of items")
    limit: int = Field(..., ge=1, description="Items per page")
    offset: int = Field(..., ge=0, description="Current offset")
    has_more: bool = Field(..., description="Whether there are more items")

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        limit: int,
        offset: int,
    ) -> "PaginatedResponse[T]":
        """
        Create a paginated response.

        Args:
            items: List of items for the current page.
            total: Total number of items.
            limit: Items per page.
            offset: Current offset.

        Returns:
            PaginatedResponse instance.
        """
        return cls(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + len(items) < total,
        )


# =============================================================================
# Success Response Schemas
# =============================================================================


class SuccessResponse(BaseSchema):
    """Schema for generic success response."""

    success: bool = Field(
        default=True, description="Whether the operation succeeded"
    )
    message: Optional[str] = Field(None, description="Success message")
    data: Optional[dict[str, Any]] = Field(None, description="Additional data")


class HealthResponse(BaseSchema):
    """Schema for health check response."""

    status: str = Field(..., description="Health status")
    service: str = Field(
        default="unitmail-gateway", description="Service name"
    )
    version: str = Field(default="1.0.0", description="Service version")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="Check timestamp",
    )
    checks: Optional[dict[str, bool]] = Field(
        None,
        description="Individual health check results",
    )


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    # Base
    "BaseSchema",
    "TimestampMixin",
    # Auth
    "LoginRequest",
    "LoginResponse",
    "RefreshRequest",
    "RefreshResponse",
    "LogoutRequest",
    # User
    "UserResponse",
    "UserCreateRequest",
    "UserUpdateRequest",
    "PasswordChangeRequest",
    # Message
    "MessagePriority",
    "MessageStatus",
    "MessageListRequest",
    "MessageResponse",
    "MessageCreateRequest",
    "MessageUpdateRequest",
    # Contact
    "ContactRequest",
    "ContactResponse",
    "ContactListRequest",
    # Folder
    "FolderType",
    "FolderRequest",
    "FolderResponse",
    "FolderUpdateRequest",
    # Error
    "ErrorDetail",
    "ErrorResponse",
    # Pagination
    "PaginatedResponse",
    # Success
    "SuccessResponse",
    "HealthResponse",
]
