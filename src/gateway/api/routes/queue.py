"""
Queue routes for unitMail Gateway API.

This module provides endpoints for message queue management
including listing queue items, viewing statistics, retrying
failed items, and removing items from the queue.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from flask import Blueprint, Response, g, jsonify, request

from ....common.database import get_db
from ....common.exceptions import RecordNotFoundError
from ..middleware import rate_limit
from .auth import require_auth

# Configure module logger
logger = logging.getLogger(__name__)


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


def serialize_queue_item(item) -> dict[str, Any]:
    """Serialize a queue item model to JSON-compatible dict."""
    status = item.status
    if hasattr(status, 'value'):
        status = status.value

    return {
        "id": str(item.id),
        "message_id": str(item.message_id),
        "user_id": str(item.user_id),
        "recipient": item.recipient,
        "status": status,
        "priority": item.priority,
        "attempts": item.attempts,
        "max_attempts": item.max_attempts,
        "last_attempt_at": item.last_attempt_at.isoformat() if item.last_attempt_at else None,
        "next_attempt_at": item.next_attempt_at.isoformat() if item.next_attempt_at else None,
        "error_message": item.error_message,
        "metadata": item.metadata,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
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
            - status: Filter by status (pending, processing, completed, failed, retrying)
            - message_id: Filter by message ID

        Returns:
            Paginated list of queue items.
        """
        try:
            # Parse query parameters
            page = max(1, int(request.args.get("page", 1)))
            per_page = min(100, max(1, int(request.args.get("per_page", 50))))
            status = request.args.get("status")
            message_id = request.args.get("message_id")

            offset = (page - 1) * per_page

            db = get_db()

            # Build filters
            filters = {"user_id": UUID(g.current_user_id)}

            if status:
                valid_statuses = ["pending", "processing", "completed", "failed", "retrying"]
                if status.lower() not in valid_statuses:
                    return jsonify({
                        "error": "Invalid parameter",
                        "message": f"status must be one of: {', '.join(valid_statuses)}",
                    }), 400
                filters["status"] = status.lower()

            if message_id:
                try:
                    filters["message_id"] = UUID(message_id)
                except ValueError:
                    return jsonify({
                        "error": "Invalid parameter",
                        "message": "message_id must be a valid UUID",
                    }), 400

            # Get queue items
            items = run_async(
                db.queue.get_all(
                    limit=per_page,
                    offset=offset,
                    order_by="created_at",
                    ascending=False,
                    filters=filters,
                )
            )

            # Get total count
            total = run_async(db.queue.count(filters=filters))

            return jsonify({
                "items": [serialize_queue_item(item) for item in items],
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
            logger.error(f"List queue items error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while fetching queue items",
            }), 500

    @bp.route("/stats", methods=["GET"])
    @require_auth
    @rate_limit()
    def get_queue_stats() -> tuple[Response, int]:
        """
        Get queue statistics for the current user.

        Returns:
            Queue statistics including counts by status.
        """
        try:
            db = get_db()
            user_id = UUID(g.current_user_id)

            # Get counts for each status
            pending_count = run_async(
                db.queue.count(filters={"user_id": user_id, "status": "pending"})
            )
            processing_count = run_async(
                db.queue.count(filters={"user_id": user_id, "status": "processing"})
            )
            completed_count = run_async(
                db.queue.count(filters={"user_id": user_id, "status": "completed"})
            )
            failed_count = run_async(
                db.queue.count(filters={"user_id": user_id, "status": "failed"})
            )
            retrying_count = run_async(
                db.queue.count(filters={"user_id": user_id, "status": "retrying"})
            )

            total_count = (
                pending_count + processing_count + completed_count +
                failed_count + retrying_count
            )

            # Get recent failed items for quick view
            failed_items = run_async(
                db.queue.get_all(
                    limit=5,
                    order_by="updated_at",
                    ascending=False,
                    filters={"user_id": user_id, "status": "failed"},
                )
            )

            return jsonify({
                "statistics": {
                    "total": total_count,
                    "pending": pending_count,
                    "processing": processing_count,
                    "completed": completed_count,
                    "failed": failed_count,
                    "retrying": retrying_count,
                    "success_rate": (
                        round(completed_count / total_count * 100, 2)
                        if total_count > 0 else 100.0
                    ),
                },
                "recent_failures": [
                    {
                        "id": str(item.id),
                        "recipient": item.recipient,
                        "error_message": item.error_message,
                        "attempts": item.attempts,
                        "last_attempt_at": (
                            item.last_attempt_at.isoformat()
                            if item.last_attempt_at else None
                        ),
                    }
                    for item in failed_items
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }), 200

        except Exception as e:
            logger.error(f"Get queue stats error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while fetching queue statistics",
            }), 500

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
            # Validate UUID
            try:
                item_uuid = UUID(item_id)
            except ValueError:
                return jsonify({
                    "error": "Invalid parameter",
                    "message": "item_id must be a valid UUID",
                }), 400

            db = get_db()
            item = run_async(db.queue.get_by_id(item_uuid))

            # Check ownership
            if str(item.user_id) != g.current_user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Queue item not found",
                }), 404

            return jsonify(serialize_queue_item(item)), 200

        except RecordNotFoundError:
            return jsonify({
                "error": "Not found",
                "message": "Queue item not found",
            }), 404

        except Exception as e:
            logger.error(f"Get queue item error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while fetching the queue item",
            }), 500

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
            # Validate UUID
            try:
                item_uuid = UUID(item_id)
            except ValueError:
                return jsonify({
                    "error": "Invalid parameter",
                    "message": "item_id must be a valid UUID",
                }), 400

            db = get_db()

            # Get existing item
            item = run_async(db.queue.get_by_id(item_uuid))

            # Check ownership
            if str(item.user_id) != g.current_user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Queue item not found",
                }), 404

            # Check if item can be retried
            status = item.status
            if hasattr(status, 'value'):
                status = status.value

            if status not in ["failed", "retrying"]:
                return jsonify({
                    "error": "Cannot retry",
                    "message": f"Queue item with status '{status}' cannot be retried",
                }), 400

            # Parse request body
            data = request.get_json(silent=True) or {}
            reset_attempts = data.get("reset_attempts", False)

            # Reset the item for retry
            update_data = {
                "status": "pending",
                "error_message": None,
                "next_attempt_at": datetime.now(timezone.utc),
            }

            if reset_attempts:
                update_data["attempts"] = 0

            item = run_async(db.queue.update(item_uuid, update_data))

            logger.info(
                "Queue item reset for retry",
                extra={
                    "user_id": g.current_user_id,
                    "item_id": item_id,
                    "reset_attempts": reset_attempts,
                },
            )

            return jsonify({
                "message": "Queue item reset for retry",
                "item": serialize_queue_item(item),
            }), 200

        except RecordNotFoundError:
            return jsonify({
                "error": "Not found",
                "message": "Queue item not found",
            }), 404

        except Exception as e:
            logger.error(f"Retry queue item error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while retrying the queue item",
            }), 500

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
            # Validate UUID
            try:
                item_uuid = UUID(item_id)
            except ValueError:
                return jsonify({
                    "error": "Invalid parameter",
                    "message": "item_id must be a valid UUID",
                }), 400

            force = request.args.get("force", "false").lower() == "true"

            db = get_db()

            # Get existing item
            item = run_async(db.queue.get_by_id(item_uuid))

            # Check ownership
            if str(item.user_id) != g.current_user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Queue item not found",
                }), 404

            # Check if item is processing
            status = item.status
            if hasattr(status, 'value'):
                status = status.value

            if status == "processing" and not force:
                return jsonify({
                    "error": "Cannot delete",
                    "message": "Queue item is currently being processed. "
                               "Use 'force=true' to delete anyway.",
                }), 400

            # Delete the item
            run_async(db.queue.delete(item_uuid))

            logger.info(
                "Queue item deleted",
                extra={
                    "user_id": g.current_user_id,
                    "item_id": item_id,
                },
            )

            return jsonify({
                "message": "Queue item deleted successfully",
            }), 200

        except RecordNotFoundError:
            return jsonify({
                "error": "Not found",
                "message": "Queue item not found",
            }), 404

        except Exception as e:
            logger.error(f"Delete queue item error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while deleting the queue item",
            }), 500

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
            return jsonify({
                "error": "Invalid request",
                "message": "Request must be JSON",
            }), 400

        data = request.get_json()
        item_ids = data.get("item_ids", [])
        all_failed = data.get("all_failed", False)
        reset_attempts = data.get("reset_attempts", False)

        try:
            db = get_db()
            user_id = UUID(g.current_user_id)

            retried_count = 0

            if all_failed:
                # Get all failed items for user
                failed_items = run_async(
                    db.queue.get_all(
                        limit=1000,
                        filters={"user_id": user_id, "status": "failed"},
                    )
                )
                item_uuids = [item.id for item in failed_items]
            else:
                # Validate provided IDs
                item_uuids = []
                for item_id in item_ids:
                    try:
                        item_uuids.append(UUID(item_id))
                    except ValueError:
                        pass

            # Reset each item
            for item_uuid in item_uuids:
                try:
                    item = run_async(db.queue.get_by_id(item_uuid))

                    # Check ownership
                    if str(item.user_id) != g.current_user_id:
                        continue

                    # Check status
                    status = item.status
                    if hasattr(status, 'value'):
                        status = status.value

                    if status not in ["failed", "retrying"]:
                        continue

                    # Reset for retry
                    update_data = {
                        "status": "pending",
                        "error_message": None,
                        "next_attempt_at": datetime.now(timezone.utc),
                    }

                    if reset_attempts:
                        update_data["attempts"] = 0

                    run_async(db.queue.update(item_uuid, update_data))
                    retried_count += 1

                except RecordNotFoundError:
                    continue

            logger.info(
                "Batch retry completed",
                extra={
                    "user_id": g.current_user_id,
                    "retried_count": retried_count,
                },
            )

            return jsonify({
                "message": f"Reset {retried_count} items for retry",
                "retried_count": retried_count,
            }), 200

        except Exception as e:
            logger.error(f"Batch retry error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred during batch retry",
            }), 500

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
            return jsonify({
                "error": "Invalid request",
                "message": "Request must be JSON",
            }), 400

        data = request.get_json()
        item_ids = data.get("item_ids", [])
        status_filter = data.get("status")

        try:
            db = get_db()
            user_id = UUID(g.current_user_id)

            deleted_count = 0

            if status_filter:
                # Validate status
                valid_statuses = ["pending", "processing", "completed", "failed", "retrying"]
                if status_filter.lower() not in valid_statuses:
                    return jsonify({
                        "error": "Invalid parameter",
                        "message": f"status must be one of: {', '.join(valid_statuses)}",
                    }), 400

                # Get all items with this status for user
                items = run_async(
                    db.queue.get_all(
                        limit=1000,
                        filters={"user_id": user_id, "status": status_filter.lower()},
                    )
                )
                item_uuids = [item.id for item in items]
            else:
                # Validate provided IDs
                item_uuids = []
                for item_id in item_ids:
                    try:
                        item_uuids.append(UUID(item_id))
                    except ValueError:
                        pass

            # Delete each item
            for item_uuid in item_uuids:
                try:
                    item = run_async(db.queue.get_by_id(item_uuid))

                    # Check ownership
                    if str(item.user_id) != g.current_user_id:
                        continue

                    run_async(db.queue.delete(item_uuid))
                    deleted_count += 1

                except RecordNotFoundError:
                    continue

            logger.info(
                "Batch delete completed",
                extra={
                    "user_id": g.current_user_id,
                    "deleted_count": deleted_count,
                },
            )

            return jsonify({
                "message": f"Deleted {deleted_count} items",
                "deleted_count": deleted_count,
            }), 200

        except Exception as e:
            logger.error(f"Batch delete error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred during batch delete",
            }), 500

    return bp


# Export public components
__all__ = [
    "create_queue_blueprint",
]
