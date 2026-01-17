"""
Message routes for unitMail Gateway API.

This module provides endpoints for message management including listing,
reading, sending, updating, deleting, and managing message flags.
Uses SQLite for storage.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from flask import Blueprint, Response, g, jsonify, request
from pydantic import BaseModel, EmailStr, Field, ValidationError

from common.storage import get_storage
from ..middleware import rate_limit
from ..auth import require_auth

# Configure module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================


class SendMessageRequest(BaseModel):
    """Request model for sending a new message."""

    to: list[EmailStr] = Field(..., min_length=1,
                               description="Recipient addresses")
    cc: list[EmailStr] = Field(
        default_factory=list, description="CC addresses")
    bcc: list[EmailStr] = Field(
        default_factory=list, description="BCC addresses")
    subject: str = Field(default="", max_length=998,
                         description="Message subject")
    body_text: Optional[str] = Field(None, description="Plain text body")
    body_html: Optional[str] = Field(None, description="HTML body")
    priority: str = Field(default="normal", description="Message priority")
    attachments: list[dict[str, Any]] = Field(
        default_factory=list, description="Attachment metadata"
    )
    save_draft: bool = Field(
        default=False, description="Save as draft instead of sending")


class UpdateMessageRequest(BaseModel):
    """Request model for updating a message."""

    folder_id: Optional[str] = Field(None, description="Move to folder")
    is_read: Optional[bool] = Field(None, description="Read status")
    is_starred: Optional[bool] = Field(None, description="Starred status")


class ToggleStarRequest(BaseModel):
    """Request model for toggling star status."""

    starred: Optional[bool] = Field(
        None, description="Set specific star state")


class MarkReadRequest(BaseModel):
    """Request model for marking message as read/unread."""

    is_read: bool = Field(..., description="Read status to set")


# =============================================================================
# Helper Functions
# =============================================================================


def serialize_message(message: dict) -> dict[str, Any]:
    """Serialize a message dict for JSON response."""
    return {
        "id": message["id"],
        "user_id": message.get("user_id"),
        "folder_id": message.get("folder_id"),
        "message_id": message.get("message_id"),
        "from_address": message.get("from_address"),
        "to_addresses": message.get("to_addresses", []),
        "cc_addresses": message.get("cc_addresses", []),
        "bcc_addresses": message.get("bcc_addresses", []),
        "subject": message.get("subject", ""),
        "body_text": message.get("body_text"),
        "body_html": message.get("body_html"),
        "headers": message.get("headers", {}),
        "attachments": message.get("attachments", []),
        "status": message.get("status", "received"),
        "priority": message.get("priority", "normal"),
        "is_read": message.get("is_read", False),
        "is_starred": message.get("is_starred", False),
        "is_encrypted": message.get("is_encrypted", False),
        "received_at": message.get("received_at"),
        "sent_at": message.get("sent_at"),
        "created_at": message.get("created_at"),
        "updated_at": message.get("updated_at"),
    }


# =============================================================================
# Blueprint and Routes
# =============================================================================


def create_messages_blueprint() -> Blueprint:
    """
    Create the messages blueprint.

    Returns:
        Blueprint for message-related routes.
    """
    bp = Blueprint("messages", __name__, url_prefix="/messages")

    @bp.route("", methods=["GET"])
    @bp.route("/", methods=["GET"])
    @require_auth
    @rate_limit()
    def list_messages() -> tuple[Response, int]:
        """
        List messages for the current user.

        Query Parameters:
            - folder_id: Filter by folder ID
            - page: Page number (default: 1)
            - per_page: Items per page (default: 50, max: 100)
            - status: Filter by message status
            - is_read: Filter by read status (true/false)
            - is_starred: Filter by starred status (true/false)
            - search: Search in subject and body

        Returns:
            Paginated list of messages.
        """
        try:
            # Parse query parameters
            folder_id = request.args.get("folder_id")
            page = max(1, int(request.args.get("page", 1)))
            per_page = min(100, max(1, int(request.args.get("per_page", 50))))
            status = request.args.get("status")
            is_read_param = request.args.get("is_read")
            is_starred_param = request.args.get("is_starred")
            search = request.args.get("search", "").strip()

            offset = (page - 1) * per_page
            user_id = getattr(g, "user_id", None)

            storage = get_storage()

            # Parse boolean filters
            is_read = None
            if is_read_param is not None:
                is_read = is_read_param.lower() == "true"

            is_starred = None
            if is_starred_param is not None:
                is_starred = is_starred_param.lower() == "true"

            # Search or filter
            if search:
                messages = storage.search_messages(
                    query=search, limit=per_page)
                # Apply additional filters to search results
                if user_id:
                    messages = [m for m in messages if m.get(
                        "user_id") == user_id]
                if folder_id:
                    messages = [m for m in messages if m.get(
                        "folder_id") == folder_id]
                if is_read is not None:
                    messages = [m for m in messages if m.get(
                        "is_read") == is_read]
                if is_starred is not None:
                    messages = [m for m in messages if m.get(
                        "is_starred") == is_starred]
                total = len(messages)
            else:
                # Get messages with filters
                messages = storage.get_messages(
                    user_id=user_id,
                    folder_id=folder_id,
                    status=status,
                    is_read=is_read,
                    is_starred=is_starred,
                    limit=per_page,
                    offset=offset,
                )

                # Get total count
                total = storage.count_messages(
                    user_id=user_id,
                    folder_id=folder_id,
                    status=status,
                    is_read=is_read,
                    is_starred=is_starred,
                )

            return jsonify({
                "messages": [serialize_message(m) for m in messages],
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": (total + per_page - 1) // per_page if total > 0 else 1,
                    "has_next": page * per_page < total,
                    "has_prev": page > 1,
                },
            }), 200

        except Exception as e:
            logger.error(f"List messages error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while fetching messages",
            }), 500

    @bp.route("/<message_id>", methods=["GET"])
    @require_auth
    def get_message(message_id: str) -> tuple[Response, int]:
        """
        Get a single message by ID.

        Path Parameters:
            - message_id: Message UUID

        Returns:
            Message details.
        """
        try:
            storage = get_storage()
            message = storage.get_message(message_id)

            if not message:
                return jsonify({
                    "error": "Not found",
                    "message": "Message not found",
                }), 404

            # Check ownership
            user_id = getattr(g, "user_id", None)
            if message.get("user_id") and message.get("user_id") != user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Message not found",
                }), 404

            return jsonify(serialize_message(message)), 200

        except Exception as e:
            logger.error(f"Get message error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while fetching the message",
            }), 500

    @bp.route("", methods=["POST"])
    @bp.route("/", methods=["POST"])
    @require_auth
    @rate_limit(max_requests=30, window_seconds=60)
    def send_message() -> tuple[Response, int]:
        """
        Send a new message or save as draft.

        Request Body:
            - to: List of recipient email addresses (required)
            - cc: List of CC addresses
            - bcc: List of BCC addresses
            - subject: Message subject
            - body_text: Plain text body
            - body_html: HTML body
            - priority: Message priority (low, normal, high, urgent)
            - attachments: List of attachment metadata
            - save_draft: If true, save as draft instead of sending

        Returns:
            Created message details.
        """
        if not request.is_json:
            return jsonify({
                "error": "Invalid request",
                "message": "Request must be JSON",
            }), 400

        try:
            data = SendMessageRequest(**request.get_json())
        except ValidationError as e:
            return jsonify({
                "error": "Validation error",
                "message": "Invalid request data",
                "details": e.errors(),
            }), 400

        try:
            storage = get_storage()
            user_id = getattr(g, "user_id", None)

            # Get user info for from_address
            user = storage.get_user_by_id(user_id) if user_id else None
            from_address = user.get("email") if user else "noreply@localhost"

            # Validate priority
            valid_priorities = ["low", "normal", "high", "urgent"]
            priority = data.priority.lower() if data.priority.lower(
            ) in valid_priorities else "normal"

            # Determine folder and status
            if data.save_draft:
                folder = storage.get_folder_by_name("Drafts")
                status = "draft"
                sent_at = None
            else:
                folder = storage.get_folder_by_name("Sent")
                status = "queued"
                sent_at = datetime.now(timezone.utc).isoformat()

            # Generate message ID
            msg_uuid = str(uuid4())
            rfc_message_id = f"<{msg_uuid}@unitmail>"

            # Create message
            message_data = {
                "id": msg_uuid,
                "user_id": user_id,
                "folder_id": folder["id"] if folder else None,
                "message_id": rfc_message_id,
                "from_address": from_address,
                "to_addresses": [str(addr) for addr in data.to],
                "cc_addresses": [str(addr) for addr in data.cc],
                "bcc_addresses": [str(addr) for addr in data.bcc],
                "subject": data.subject,
                "body_text": data.body_text,
                "body_html": data.body_html,
                "status": status,
                "priority": priority,
                "attachments": data.attachments,
                "sent_at": sent_at,
                "received_at": datetime.now(timezone.utc).isoformat(),
            }

            message = storage.create_message(message_data)

            # If not a draft, add to queue for sending
            if not data.save_draft:
                all_recipients = (
                    [str(addr) for addr in data.to] +
                    [str(addr) for addr in data.cc] +
                    [str(addr) for addr in data.bcc]
                )
                for recipient in all_recipients:
                    queue_priority = 50 if priority == "high" else (
                        100 if priority == "urgent" else 0)
                    storage.create_queue_item({
                        "message_id": message["id"],
                        "user_id": user_id,
                        "recipient": recipient,
                        "status": "pending",
                        "priority": queue_priority,
                    })

            logger.info(
                "Message created",
                extra={
                    "user_id": user_id,
                    "message_id": message["id"],
                    "is_draft": data.save_draft,
                },
            )

            return jsonify({
                "message": serialize_message(message),
                "queued": not data.save_draft,
            }), 201

        except Exception as e:
            logger.error(f"Send message error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while sending the message",
            }), 500

    @bp.route("/<message_id>", methods=["PUT"])
    @require_auth
    def update_message(message_id: str) -> tuple[Response, int]:
        """
        Update a message (move to folder, change flags).

        Path Parameters:
            - message_id: Message UUID

        Request Body:
            - folder_id: Move to this folder
            - is_read: Set read status
            - is_starred: Set starred status

        Returns:
            Updated message details.
        """
        try:
            if not request.is_json:
                return jsonify({
                    "error": "Invalid request",
                    "message": "Request must be JSON",
                }), 400

            try:
                data = UpdateMessageRequest(**request.get_json())
            except ValidationError as e:
                return jsonify({
                    "error": "Validation error",
                    "message": "Invalid request data",
                    "details": e.errors(),
                }), 400

            storage = get_storage()
            user_id = getattr(g, "user_id", None)

            # Get existing message
            message = storage.get_message(message_id)

            if not message:
                return jsonify({
                    "error": "Not found",
                    "message": "Message not found",
                }), 404

            # Check ownership
            if message.get("user_id") and message.get("user_id") != user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Message not found",
                }), 404

            # Build update data
            update_data = {}

            if data.folder_id is not None:
                # Verify folder exists
                folder = storage.get_folder_by_id(data.folder_id)
                if not folder:
                    return jsonify({
                        "error": "Invalid folder",
                        "message": "Folder not found",
                    }), 400
                update_data["folder_id"] = data.folder_id

            if data.is_read is not None:
                update_data["is_read"] = data.is_read

            if data.is_starred is not None:
                update_data["is_starred"] = data.is_starred

            if not update_data:
                return jsonify({
                    "error": "Invalid request",
                    "message": "No valid fields to update",
                }), 400

            # Update message
            message = storage.update_message(message_id, update_data)

            return jsonify(serialize_message(message)), 200

        except Exception as e:
            logger.error(f"Update message error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while updating the message",
            }), 500

    @bp.route("/<message_id>", methods=["DELETE"])
    @require_auth
    def delete_message(message_id: str) -> tuple[Response, int]:
        """
        Delete a message.

        Path Parameters:
            - message_id: Message UUID

        Query Parameters:
            - permanent: If true, permanently delete. Otherwise move to trash.

        Returns:
            Success message.
        """
        try:
            permanent = request.args.get(
                "permanent", "false").lower() == "true"

            storage = get_storage()
            user_id = getattr(g, "user_id", None)

            # Get existing message
            message = storage.get_message(message_id)

            if not message:
                return jsonify({
                    "error": "Not found",
                    "message": "Message not found",
                }), 404

            # Check ownership
            if message.get("user_id") and message.get("user_id") != user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Message not found",
                }), 404

            if permanent:
                # Permanently delete
                storage.delete_message(message_id)
                logger.info(
                    "Message permanently deleted",
                    extra={"user_id": user_id, "message_id": message_id},
                )
            else:
                # Move to trash folder
                result = storage.move_to_trash(message_id)
                if result:
                    logger.info(
                        "Message moved to trash",
                        extra={"user_id": user_id, "message_id": message_id},
                    )
                else:
                    # No trash folder or error, permanently delete
                    storage.delete_message(message_id)

            return jsonify({
                "message": "Message deleted successfully",
                "permanent": permanent,
            }), 200

        except Exception as e:
            logger.error(f"Delete message error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while deleting the message",
            }), 500

    @bp.route("/<message_id>/star", methods=["POST"])
    @require_auth
    def toggle_star(message_id: str) -> tuple[Response, int]:
        """
        Toggle or set the starred status of a message.

        Path Parameters:
            - message_id: Message UUID

        Request Body (optional):
            - starred: Set specific star state (true/false)

        Returns:
            Updated starred status.
        """
        try:
            storage = get_storage()
            user_id = getattr(g, "user_id", None)

            # Get existing message
            message = storage.get_message(message_id)

            if not message:
                return jsonify({
                    "error": "Not found",
                    "message": "Message not found",
                }), 404

            # Check ownership
            if message.get("user_id") and message.get("user_id") != user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Message not found",
                }), 404

            # Check if specific value was provided
            data = request.get_json(silent=True) or {}
            if "starred" in data:
                new_starred = bool(data["starred"])
                message = storage.update_message(
                    message_id, {"is_starred": new_starred})
            else:
                # Toggle
                message = storage.toggle_starred(message_id)

            return jsonify({
                "id": message["id"],
                "is_starred": message.get("is_starred", False),
            }), 200

        except Exception as e:
            logger.error(f"Toggle star error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while updating starred status",
            }), 500

    @bp.route("/<message_id>/read", methods=["POST"])
    @require_auth
    def mark_read(message_id: str) -> tuple[Response, int]:
        """
        Mark a message as read or unread.

        Path Parameters:
            - message_id: Message UUID

        Request Body:
            - is_read: Read status to set (true/false)

        Returns:
            Updated read status.
        """
        try:
            if not request.is_json:
                return jsonify({
                    "error": "Invalid request",
                    "message": "Request must be JSON",
                }), 400

            try:
                data = MarkReadRequest(**request.get_json())
            except ValidationError as e:
                return jsonify({
                    "error": "Validation error",
                    "message": "Invalid request data",
                    "details": e.errors(),
                }), 400

            storage = get_storage()
            user_id = getattr(g, "user_id", None)

            # Get existing message
            message = storage.get_message(message_id)

            if not message:
                return jsonify({
                    "error": "Not found",
                    "message": "Message not found",
                }), 404

            # Check ownership
            if message.get("user_id") and message.get("user_id") != user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Message not found",
                }), 404

            # Update read status
            if data.is_read:
                message = storage.mark_as_read(message_id)
            else:
                message = storage.mark_as_unread(message_id)

            return jsonify({
                "id": message["id"],
                "is_read": message.get("is_read", False),
            }), 200

        except Exception as e:
            logger.error(f"Mark read error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while updating read status",
            }), 500

    return bp


# Export public components
__all__ = [
    "create_messages_blueprint",
]
