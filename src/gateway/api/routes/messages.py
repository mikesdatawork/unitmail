"""
Message routes for unitMail Gateway API.

This module provides endpoints for message management including listing,
reading, sending, updating, deleting, and managing message flags.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from flask import Blueprint, Response, g, jsonify, request
from pydantic import BaseModel, EmailStr, Field, ValidationError

from ....common.database import get_db
from ....common.exceptions import RecordNotFoundError
from ....common.models import MessageCreate, MessagePriority, MessageStatus, MessageUpdate
from ..middleware import rate_limit
from .auth import require_auth

# Configure module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================


class SendMessageRequest(BaseModel):
    """Request model for sending a new message."""

    to: list[EmailStr] = Field(..., min_length=1, description="Recipient addresses")
    cc: list[EmailStr] = Field(default_factory=list, description="CC addresses")
    bcc: list[EmailStr] = Field(default_factory=list, description="BCC addresses")
    subject: str = Field(default="", max_length=998, description="Message subject")
    body_text: Optional[str] = Field(None, description="Plain text body")
    body_html: Optional[str] = Field(None, description="HTML body")
    priority: str = Field(default="normal", description="Message priority")
    attachments: list[dict[str, Any]] = Field(
        default_factory=list, description="Attachment metadata"
    )
    save_draft: bool = Field(default=False, description="Save as draft instead of sending")


class UpdateMessageRequest(BaseModel):
    """Request model for updating a message."""

    folder_id: Optional[str] = Field(None, description="Move to folder")
    is_read: Optional[bool] = Field(None, description="Read status")
    is_starred: Optional[bool] = Field(None, description="Starred status")


class ToggleStarRequest(BaseModel):
    """Request model for toggling star status."""

    starred: Optional[bool] = Field(None, description="Set specific star state")


class MarkReadRequest(BaseModel):
    """Request model for marking message as read/unread."""

    is_read: bool = Field(..., description="Read status to set")


# =============================================================================
# Helper Functions
# =============================================================================


def run_async(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def serialize_message(message) -> dict[str, Any]:
    """Serialize a message model to JSON-compatible dict."""
    return {
        "id": str(message.id),
        "user_id": str(message.user_id),
        "folder_id": str(message.folder_id) if message.folder_id else None,
        "message_id": message.message_id,
        "from_address": message.from_address,
        "to_addresses": message.to_addresses,
        "cc_addresses": message.cc_addresses,
        "bcc_addresses": message.bcc_addresses,
        "subject": message.subject,
        "body_text": message.body_text,
        "body_html": message.body_html,
        "headers": message.headers,
        "attachments": message.attachments,
        "status": message.status if isinstance(message.status, str) else message.status.value,
        "priority": message.priority if isinstance(message.priority, str) else message.priority.value,
        "is_read": message.is_read,
        "is_starred": message.is_starred,
        "is_encrypted": message.is_encrypted,
        "received_at": message.received_at.isoformat() if message.received_at else None,
        "sent_at": message.sent_at.isoformat() if message.sent_at else None,
        "created_at": message.created_at.isoformat(),
        "updated_at": message.updated_at.isoformat(),
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
            is_read = request.args.get("is_read")
            is_starred = request.args.get("is_starred")

            offset = (page - 1) * per_page

            db = get_db()

            # Build filters
            filters = {"user_id": UUID(g.current_user_id)}

            if folder_id:
                try:
                    filters["folder_id"] = UUID(folder_id)
                except ValueError:
                    return jsonify({
                        "error": "Invalid parameter",
                        "message": "folder_id must be a valid UUID",
                    }), 400

            if status:
                filters["status"] = status

            if is_read is not None:
                filters["is_read"] = is_read.lower() == "true"

            if is_starred is not None:
                filters["is_starred"] = is_starred.lower() == "true"

            # Get messages
            messages = run_async(
                db.messages.get_all(
                    limit=per_page,
                    offset=offset,
                    order_by="created_at",
                    ascending=False,
                    filters=filters,
                )
            )

            # Get total count
            total = run_async(db.messages.count(filters=filters))

            return jsonify({
                "messages": [serialize_message(m) for m in messages],
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": (total + per_page - 1) // per_page,
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
            # Validate UUID
            try:
                msg_uuid = UUID(message_id)
            except ValueError:
                return jsonify({
                    "error": "Invalid parameter",
                    "message": "message_id must be a valid UUID",
                }), 400

            db = get_db()
            message = run_async(db.messages.get_by_id(msg_uuid))

            # Check ownership
            if str(message.user_id) != g.current_user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Message not found",
                }), 404

            return jsonify(serialize_message(message)), 200

        except RecordNotFoundError:
            return jsonify({
                "error": "Not found",
                "message": "Message not found",
            }), 404

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
            db = get_db()

            # Get user info for from_address
            user = run_async(db.users.get_by_id(g.current_user_id))

            # Validate priority
            try:
                priority = MessagePriority(data.priority)
            except ValueError:
                priority = MessagePriority.NORMAL

            # Create message
            message_create = MessageCreate(
                to_addresses=data.to,
                cc_addresses=data.cc,
                bcc_addresses=data.bcc,
                subject=data.subject,
                body_text=data.body_text,
                body_html=data.body_html,
                priority=priority,
                attachments=data.attachments,
            )

            # Set status based on save_draft flag
            message = run_async(
                db.messages.create_message(UUID(g.current_user_id), message_create)
            )

            # Update from_address and status
            status = MessageStatus.DRAFT if data.save_draft else MessageStatus.QUEUED
            message = run_async(
                db.messages.update(
                    message.id,
                    {
                        "from_address": user.email,
                        "status": status.value,
                        "sent_at": None if data.save_draft else datetime.now(timezone.utc),
                    }
                )
            )

            # If not a draft, add to queue for sending
            if not data.save_draft:
                # Queue message for each recipient
                for recipient in data.to + data.cc + data.bcc:
                    run_async(
                        db.queue.create({
                            "message_id": message.id,
                            "user_id": UUID(g.current_user_id),
                            "recipient": recipient,
                            "status": "pending",
                            "priority": 50 if priority == MessagePriority.HIGH else
                                       100 if priority == MessagePriority.URGENT else 0,
                        })
                    )

            logger.info(
                "Message created",
                extra={
                    "user_id": g.current_user_id,
                    "message_id": str(message.id),
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
            # Validate UUID
            try:
                msg_uuid = UUID(message_id)
            except ValueError:
                return jsonify({
                    "error": "Invalid parameter",
                    "message": "message_id must be a valid UUID",
                }), 400

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

            db = get_db()

            # Get existing message
            message = run_async(db.messages.get_by_id(msg_uuid))

            # Check ownership
            if str(message.user_id) != g.current_user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Message not found",
                }), 404

            # Build update data
            update_data = {}

            if data.folder_id is not None:
                try:
                    folder_uuid = UUID(data.folder_id)
                    # Verify folder exists and belongs to user
                    folder = run_async(db.folders.get_by_id(folder_uuid))
                    if str(folder.user_id) != g.current_user_id:
                        return jsonify({
                            "error": "Invalid folder",
                            "message": "Folder not found",
                        }), 400
                    update_data["folder_id"] = folder_uuid
                except ValueError:
                    return jsonify({
                        "error": "Invalid parameter",
                        "message": "folder_id must be a valid UUID",
                    }), 400

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
            message_update = MessageUpdate(**update_data)
            message = run_async(db.messages.update_message(msg_uuid, message_update))

            return jsonify(serialize_message(message)), 200

        except RecordNotFoundError:
            return jsonify({
                "error": "Not found",
                "message": "Message not found",
            }), 404

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
            # Validate UUID
            try:
                msg_uuid = UUID(message_id)
            except ValueError:
                return jsonify({
                    "error": "Invalid parameter",
                    "message": "message_id must be a valid UUID",
                }), 400

            permanent = request.args.get("permanent", "false").lower() == "true"

            db = get_db()

            # Get existing message
            message = run_async(db.messages.get_by_id(msg_uuid))

            # Check ownership
            if str(message.user_id) != g.current_user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Message not found",
                }), 404

            if permanent:
                # Permanently delete
                run_async(db.messages.delete(msg_uuid))
                logger.info(
                    "Message permanently deleted",
                    extra={"user_id": g.current_user_id, "message_id": message_id},
                )
            else:
                # Move to trash folder
                # Find trash folder for user
                folders = run_async(db.folders.get_by_user(UUID(g.current_user_id)))
                trash_folder = next(
                    (f for f in folders if f.folder_type == "trash"),
                    None
                )

                if trash_folder:
                    run_async(db.messages.update(msg_uuid, {"folder_id": trash_folder.id}))
                    logger.info(
                        "Message moved to trash",
                        extra={"user_id": g.current_user_id, "message_id": message_id},
                    )
                else:
                    # No trash folder, permanently delete
                    run_async(db.messages.delete(msg_uuid))

            return jsonify({
                "message": "Message deleted successfully",
                "permanent": permanent,
            }), 200

        except RecordNotFoundError:
            return jsonify({
                "error": "Not found",
                "message": "Message not found",
            }), 404

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
            # Validate UUID
            try:
                msg_uuid = UUID(message_id)
            except ValueError:
                return jsonify({
                    "error": "Invalid parameter",
                    "message": "message_id must be a valid UUID",
                }), 400

            db = get_db()

            # Get existing message
            message = run_async(db.messages.get_by_id(msg_uuid))

            # Check ownership
            if str(message.user_id) != g.current_user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Message not found",
                }), 404

            # Check if specific value was provided
            data = request.get_json(silent=True) or {}
            if "starred" in data:
                new_starred = bool(data["starred"])
                message = run_async(
                    db.messages.update(msg_uuid, {"is_starred": new_starred})
                )
            else:
                # Toggle
                message = run_async(db.messages.toggle_star(msg_uuid))

            return jsonify({
                "id": str(message.id),
                "is_starred": message.is_starred,
            }), 200

        except RecordNotFoundError:
            return jsonify({
                "error": "Not found",
                "message": "Message not found",
            }), 404

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
            # Validate UUID
            try:
                msg_uuid = UUID(message_id)
            except ValueError:
                return jsonify({
                    "error": "Invalid parameter",
                    "message": "message_id must be a valid UUID",
                }), 400

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

            db = get_db()

            # Get existing message
            message = run_async(db.messages.get_by_id(msg_uuid))

            # Check ownership
            if str(message.user_id) != g.current_user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Message not found",
                }), 404

            # Update read status
            if data.is_read:
                message = run_async(db.messages.mark_as_read(msg_uuid))
            else:
                message = run_async(db.messages.mark_as_unread(msg_uuid))

            return jsonify({
                "id": str(message.id),
                "is_read": message.is_read,
            }), 200

        except RecordNotFoundError:
            return jsonify({
                "error": "Not found",
                "message": "Message not found",
            }), 404

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
