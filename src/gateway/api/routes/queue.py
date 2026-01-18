"""
Queue routes for unitMail Gateway API.

This module provides endpoints for message queue management
including listing queue items, viewing statistics, retrying
failed items, and removing items from the queue.
Uses SQLite for storage.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, Response, g, jsonify, request

from common.storage import get_storage
from ..middleware import rate_limit
from ..auth import require_auth

# Configure module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================


def serialize_queue_item(item: dict) -> dict[str, Any]:
    """Serialize a queue item dict for JSON response."""
    return {
        "id": item["id"],
        "message_id": item["message_id"],
        "user_id": item.get("user_id"),
        "recipient": item.get("recipient"),
        "status": item["status"],
        "priority": item["priority"],
        "attempts": item["attempts"],
        "max_attempts": item["max_attempts"],
        "last_attempt_at": item.get("last_attempt_at")
        or item.get("last_attempt"),
        "next_attempt_at": item.get("next_attempt_at"),
        "error_message": item.get("error_message"),
        "metadata": item.get("metadata", {}),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }


# =============================================================================
# Blueprint and Routes
# =============================================================================


def create_queue_blueprint() -> Blueprint:
    """
    Create the queue blueprint.

    Returns:
        Blueprint for queue-related routes.
    """
    bp = Blueprint("queue", __name__, url_prefix="/queue")

    @bp.route("", methods=["GET"])
    @bp.route("/", methods=["GET"])
    @require_auth
    @rate_limit()
    def list_queue_items() -> tuple[Response, int]:
        """
        List queue items for the current user.

        Query Parameters:
            - page: Page number (default: 1)
            - per_page: Items per page (default: 50, max: 100)
            - status: Filter by status (pending, processing, etc.)

        Returns:
            Paginated list of queue items.
        """
        try:
            # Parse query parameters
            page = max(1, int(request.args.get("page", 1)))
            per_page = min(100, max(1, int(request.args.get("per_page", 50))))
            status = request.args.get("status")

            _offset = (  # noqa: F841 - TODO: implement offset pagination
                page - 1
            ) * per_page

            storage = get_storage()

            # Build items based on status filter
            if status:
                valid_statuses = [
                    "pending",
                    "processing",
                    "completed",
                    "failed",
                    "retrying",
                ]
                if status.lower() not in valid_statuses:
                    return (
                        jsonify(
                            {
                                "error": "Invalid parameter",
                                "message": f"Invalid status: {status}",
                            }
                        ),
                        400,
                    )
                items = storage.get_queue_items_by_status(
                    status.lower(), limit=per_page
                )
            else:
                items = storage.get_pending_queue_items(limit=per_page)

            # Get total count
            total = storage.count_queue_items(
                status.lower() if status else None
            )

            return (
                jsonify(
                    {
                        "items": [
                            serialize_queue_item(item) for item in items
                        ],
                        "pagination": {
                            "page": page,
                            "per_page": per_page,
                            "total": total,
                            "total_pages": (
                                (total + per_page - 1) // per_page
                                if total > 0
                                else 1
                            ),
                            "has_next": page * per_page < total,
                            "has_prev": page > 1,
                        },
                    }
                ),
                200,
            )

        except Exception as e:
            logger.error(f"List queue items error: {e}")
            return (
                jsonify(
                    {
                        "error": "Server error",
                        "message": "An error occurred while fetching queue items",
                    }
                ),
                500,
            )

    @bp.route("/stats", methods=["GET"])
    @require_auth
    @rate_limit()
    def get_queue_stats() -> tuple[Response, int]:
        """
        Get queue statistics.

        Returns:
            Queue statistics including counts by status.
        """
        try:
            storage = get_storage()

            # Get counts for each status
            stats = storage.get_queue_stats()
            pending_count = stats.get("pending", 0)
            processing_count = stats.get("processing", 0)
            completed_count = stats.get("completed", 0)
            failed_count = stats.get("failed", 0)
            retrying_count = stats.get("retrying", 0)

            total_count = (
                pending_count
                + processing_count
                + completed_count
                + failed_count
                + retrying_count
            )

            # Get recent failed items for quick view
            failed_items = storage.get_queue_items_by_status("failed", limit=5)

            return (
                jsonify(
                    {
                        "statistics": {
                            "total": total_count,
                            "pending": pending_count,
                            "processing": processing_count,
                            "completed": completed_count,
                            "failed": failed_count,
                            "retrying": retrying_count,
                            "success_rate": (
                                round(completed_count / total_count * 100, 2)
                                if total_count > 0
                                else 100.0
                            ),
                        },
                        "recent_failures": [
                            {
                                "id": item["id"],
                                "recipient": item.get("recipient"),
                                "error_message": item.get("error_message"),
                                "attempts": item["attempts"],
                                "last_attempt_at": item.get("last_attempt_at")
                                or item.get("last_attempt"),
                            }
                            for item in failed_items
                        ],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                ),
                200,
            )

        except Exception as e:
            logger.error(f"Get queue stats error: {e}")
            return (
                jsonify(
                    {
                        "error": "Server error",
                        "message": "An error occurred while fetching queue statistics",
                    }
                ),
                500,
            )

    @bp.route("/<item_id>", methods=["GET"])
    @require_auth
    def get_queue_item(item_id: str) -> tuple[Response, int]:
        """
        Get a single queue item by ID.

        Path Parameters:
            - item_id: Queue item UUID

        Returns:
            Queue item details.
        """
        try:
            storage = get_storage()
            item = storage.get_queue_item(item_id)

            if not item:
                return (
                    jsonify(
                        {
                            "error": "Not found",
                            "message": "Queue item not found",
                        }
                    ),
                    404,
                )

            return jsonify(serialize_queue_item(item)), 200

        except Exception as e:
            logger.error(f"Get queue item error: {e}")
            return (
                jsonify(
                    {
                        "error": "Server error",
                        "message": "An error occurred while fetching the queue item",
                    }
                ),
                500,
            )

    @bp.route("/<item_id>/retry", methods=["POST"])
    @require_auth
    @rate_limit(max_requests=20, window_seconds=60)
    def retry_queue_item(item_id: str) -> tuple[Response, int]:
        """
        Retry a failed queue item.

        Path Parameters:
            - item_id: Queue item UUID

        Request Body (optional):
            - reset_attempts: Reset attempt counter (default: false)

        Returns:
            Updated queue item.
        """
        try:
            storage = get_storage()

            # Get existing item
            item = storage.get_queue_item(item_id)

            if not item:
                return (
                    jsonify(
                        {
                            "error": "Not found",
                            "message": "Queue item not found",
                        }
                    ),
                    404,
                )

            # Check if item can be retried
            status = item["status"]
            if status not in ["failed", "retrying"]:
                return (
                    jsonify(
                        {
                            "error": "Cannot retry",
                            "message": f"Item with status '{status}' cannot be retried",
                        }
                    ),
                    400,
                )

            # Parse request body
            data = request.get_json(silent=True) or {}
            reset_attempts = data.get("reset_attempts", False)

            if reset_attempts:
                # Full retry reset
                item = storage.retry_queue_item(item_id)
            else:
                # Just reset status
                item = storage.update_queue_item(
                    item_id,
                    {
                        "status": "pending",
                        "error_message": None,
                        "next_attempt_at": datetime.now(
                            timezone.utc
                        ).isoformat(),
                    },
                )

            logger.info(
                "Queue item reset for retry",
                extra={
                    "user_id": getattr(g, "user_id", None),
                    "item_id": item_id,
                    "reset_attempts": reset_attempts,
                },
            )

            return (
                jsonify(
                    {
                        "message": "Queue item reset for retry",
                        "item": serialize_queue_item(item),
                    }
                ),
                200,
            )

        except Exception as e:
            logger.error(f"Retry queue item error: {e}")
            return (
                jsonify(
                    {
                        "error": "Server error",
                        "message": "An error occurred while retrying the queue item",
                    }
                ),
                500,
            )

    @bp.route("/<item_id>", methods=["DELETE"])
    @require_auth
    def delete_queue_item(item_id: str) -> tuple[Response, int]:
        """
        Remove a queue item.

        Path Parameters:
            - item_id: Queue item UUID

        Query Parameters:
            - force: If true, delete even if processing (default: false)

        Returns:
            Success message.
        """
        try:
            force = request.args.get("force", "false").lower() == "true"

            storage = get_storage()

            # Get existing item
            item = storage.get_queue_item(item_id)

            if not item:
                return (
                    jsonify(
                        {
                            "error": "Not found",
                            "message": "Queue item not found",
                        }
                    ),
                    404,
                )

            # Check if item is processing
            status = item["status"]
            if status == "processing" and not force:
                return (
                    jsonify(
                        {
                            "error": "Cannot delete",
                            "message": "Queue item is currently being processed. "
                            "Use 'force=true' to delete anyway.",
                        }
                    ),
                    400,
                )

            # Delete the item
            storage.delete_queue_item(item_id)

            logger.info(
                "Queue item deleted",
                extra={
                    "user_id": getattr(g, "user_id", None),
                    "item_id": item_id,
                },
            )

            return (
                jsonify(
                    {
                        "message": "Queue item deleted successfully",
                    }
                ),
                200,
            )

        except Exception as e:
            logger.error(f"Delete queue item error: {e}")
            return (
                jsonify(
                    {
                        "error": "Server error",
                        "message": "An error occurred while deleting the queue item",
                    }
                ),
                500,
            )

    @bp.route("/batch/retry", methods=["POST"])
    @require_auth
    @rate_limit(max_requests=10, window_seconds=60)
    def batch_retry() -> tuple[Response, int]:
        """
        Retry multiple failed queue items at once.

        Request Body:
            - item_ids: List of queue item UUIDs to retry
            - all_failed: If true, retry all failed items (ignores item_ids)
            - reset_attempts: Reset attempt counters (default: false)

        Returns:
            Number of items reset for retry.
        """
        if not request.is_json:
            return (
                jsonify(
                    {
                        "error": "Invalid request",
                        "message": "Request must be JSON",
                    }
                ),
                400,
            )

        data = request.get_json()
        item_ids = data.get("item_ids", [])
        all_failed = data.get("all_failed", False)
        reset_attempts = data.get("reset_attempts", False)

        try:
            storage = get_storage()
            retried_count = 0

            if all_failed:
                # Get all failed items
                failed_items = storage.get_queue_items_by_status(
                    "failed", limit=1000
                )
                item_ids = [item["id"] for item in failed_items]

            # Reset each item
            for item_id in item_ids:
                try:
                    item = storage.get_queue_item(item_id)
                    if not item:
                        continue

                    # Check status
                    if item["status"] not in ["failed", "retrying"]:
                        continue

                    if reset_attempts:
                        storage.retry_queue_item(item_id)
                    else:
                        storage.update_queue_item(
                            item_id,
                            {
                                "status": "pending",
                                "error_message": None,
                                "next_attempt_at": datetime.now(
                                    timezone.utc
                                ).isoformat(),
                            },
                        )
                    retried_count += 1

                except Exception:
                    continue

            logger.info(
                "Batch retry completed",
                extra={
                    "user_id": getattr(g, "user_id", None),
                    "retried_count": retried_count,
                },
            )

            return (
                jsonify(
                    {
                        "message": f"Reset {retried_count} items for retry",
                        "retried_count": retried_count,
                    }
                ),
                200,
            )

        except Exception as e:
            logger.error(f"Batch retry error: {e}")
            return (
                jsonify(
                    {
                        "error": "Server error",
                        "message": "An error occurred during batch retry",
                    }
                ),
                500,
            )

    @bp.route("/batch/delete", methods=["POST"])
    @require_auth
    @rate_limit(max_requests=10, window_seconds=60)
    def batch_delete() -> tuple[Response, int]:
        """
        Delete multiple queue items at once.

        Request Body:
            - item_ids: List of queue item UUIDs to delete
            - status: Delete all items with this status (ignores item_ids)

        Returns:
            Number of items deleted.
        """
        if not request.is_json:
            return (
                jsonify(
                    {
                        "error": "Invalid request",
                        "message": "Request must be JSON",
                    }
                ),
                400,
            )

        data = request.get_json()
        item_ids = data.get("item_ids", [])
        status_filter = data.get("status")

        try:
            storage = get_storage()
            deleted_count = 0

            if status_filter:
                # Validate status
                valid_statuses = [
                    "pending",
                    "processing",
                    "completed",
                    "failed",
                    "retrying",
                ]
                if status_filter.lower() not in valid_statuses:
                    return (
                        jsonify(
                            {
                                "error": "Invalid parameter",
                                "message": f"Invalid status: {status_filter}",
                            }
                        ),
                        400,
                    )

                # Get all items with this status
                items = storage.get_queue_items_by_status(
                    status_filter.lower(), limit=1000
                )
                item_ids = [item["id"] for item in items]

            # Delete each item
            for item_id in item_ids:
                try:
                    if storage.delete_queue_item(item_id):
                        deleted_count += 1
                except Exception:
                    continue

            logger.info(
                "Batch delete completed",
                extra={
                    "user_id": getattr(g, "user_id", None),
                    "deleted_count": deleted_count,
                },
            )

            return (
                jsonify(
                    {
                        "message": f"Deleted {deleted_count} items",
                        "deleted_count": deleted_count,
                    }
                ),
                200,
            )

        except Exception as e:
            logger.error(f"Batch delete error: {e}")
            return (
                jsonify(
                    {
                        "error": "Server error",
                        "message": "An error occurred during batch delete",
                    }
                ),
                500,
            )

    return bp


# Export public components
__all__ = [
    "create_queue_blueprint",
]
