"""
Folder routes for unitMail Gateway API.

This module provides endpoints for email folder management
including listing, creating, renaming, and deleting folders.
"""

import asyncio
import logging
from typing import Any, Optional
from uuid import UUID

from flask import Blueprint, Response, g, jsonify, request
from pydantic import BaseModel, Field, ValidationError, field_validator

from ....common.database import get_db
from ....common.exceptions import RecordNotFoundError
from ....common.models import FolderCreate, FolderType, FolderUpdate
from ..middleware import rate_limit
from .auth import require_auth

# Configure module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================


class CreateFolderRequest(BaseModel):
    """Request model for creating a folder."""

    name: str = Field(..., min_length=1, max_length=100, description="Folder name")
    parent_id: Optional[str] = Field(None, description="Parent folder ID for nesting")
    color: Optional[str] = Field(
        None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Folder color (hex)"
    )
    icon: Optional[str] = Field(None, max_length=50, description="Folder icon name")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate folder name."""
        forbidden = ['/', '\\', '<', '>', ':', '"', '|', '?', '*']
        if any(c in v for c in forbidden):
            raise ValueError(f"Folder name cannot contain: {' '.join(forbidden)}")
        return v.strip()


class UpdateFolderRequest(BaseModel):
    """Request model for updating a folder."""

    name: Optional[str] = Field(
        None, min_length=1, max_length=100, description="Folder name"
    )
    parent_id: Optional[str] = Field(None, description="Parent folder ID")
    color: Optional[str] = Field(
        None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Folder color (hex)"
    )
    icon: Optional[str] = Field(None, max_length=50, description="Folder icon name")
    sort_order: Optional[int] = Field(None, ge=0, description="Sort order")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate folder name."""
        if v is None:
            return v
        forbidden = ['/', '\\', '<', '>', ':', '"', '|', '?', '*']
        if any(c in v for c in forbidden):
            raise ValueError(f"Folder name cannot contain: {' '.join(forbidden)}")
        return v.strip()


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


def serialize_folder(folder) -> dict[str, Any]:
    """Serialize a folder model to JSON-compatible dict."""
    folder_type = folder.folder_type
    if hasattr(folder_type, 'value'):
        folder_type = folder_type.value

    return {
        "id": str(folder.id),
        "user_id": str(folder.user_id),
        "name": folder.name,
        "folder_type": folder_type,
        "parent_id": str(folder.parent_id) if folder.parent_id else None,
        "color": folder.color,
        "icon": folder.icon,
        "sort_order": folder.sort_order,
        "is_system": folder.is_system,
        "message_count": folder.message_count,
        "unread_count": folder.unread_count,
        "created_at": folder.created_at.isoformat(),
        "updated_at": folder.updated_at.isoformat(),
    }


# =============================================================================
# Blueprint and Routes
# =============================================================================


def create_folders_blueprint() -> Blueprint:
    """
    Create the folders blueprint.

    Returns:
        Blueprint for folder-related routes.
    """
    bp = Blueprint("folders", __name__, url_prefix="/folders")

    @bp.route("", methods=["GET"])
    @bp.route("/", methods=["GET"])
    @require_auth
    @rate_limit()
    def list_folders() -> tuple[Response, int]:
        """
        List folders for the current user with message counts.

        Query Parameters:
            - include_system: Include system folders (default: true)
            - parent_id: Filter by parent folder (null for root folders)

        Returns:
            List of folders with message counts.
        """
        try:
            include_system = request.args.get("include_system", "true").lower() == "true"
            parent_id = request.args.get("parent_id")

            db = get_db()

            # Get all folders for user
            folders = run_async(db.folders.get_by_user(UUID(g.current_user_id)))

            # Apply filters
            if not include_system:
                folders = [f for f in folders if not f.is_system]

            if parent_id is not None:
                if parent_id == "" or parent_id.lower() == "null":
                    # Root level folders
                    folders = [f for f in folders if f.parent_id is None]
                else:
                    try:
                        parent_uuid = UUID(parent_id)
                        folders = [f for f in folders if f.parent_id == parent_uuid]
                    except ValueError:
                        return jsonify({
                            "error": "Invalid parameter",
                            "message": "parent_id must be a valid UUID or 'null'",
                        }), 400

            # Calculate totals
            total_messages = sum(f.message_count for f in folders)
            total_unread = sum(f.unread_count for f in folders)

            return jsonify({
                "folders": [serialize_folder(f) for f in folders],
                "summary": {
                    "total_folders": len(folders),
                    "total_messages": total_messages,
                    "total_unread": total_unread,
                },
            }), 200

        except Exception as e:
            logger.error(f"List folders error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while fetching folders",
            }), 500

    @bp.route("/<folder_id>", methods=["GET"])
    @require_auth
    def get_folder(folder_id: str) -> tuple[Response, int]:
        """
        Get a single folder by ID.

        Path Parameters:
            - folder_id: Folder UUID

        Returns:
            Folder details with message counts.
        """
        try:
            # Validate UUID
            try:
                folder_uuid = UUID(folder_id)
            except ValueError:
                return jsonify({
                    "error": "Invalid parameter",
                    "message": "folder_id must be a valid UUID",
                }), 400

            db = get_db()
            folder = run_async(db.folders.get_by_id(folder_uuid))

            # Check ownership
            if str(folder.user_id) != g.current_user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Folder not found",
                }), 404

            return jsonify(serialize_folder(folder)), 200

        except RecordNotFoundError:
            return jsonify({
                "error": "Not found",
                "message": "Folder not found",
            }), 404

        except Exception as e:
            logger.error(f"Get folder error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while fetching the folder",
            }), 500

    @bp.route("", methods=["POST"])
    @bp.route("/", methods=["POST"])
    @require_auth
    @rate_limit()
    def create_folder() -> tuple[Response, int]:
        """
        Create a new folder.

        Request Body:
            - name: Folder name (required)
            - parent_id: Parent folder ID for nesting
            - color: Folder color in hex format (#RRGGBB)
            - icon: Folder icon name

        Returns:
            Created folder details.
        """
        if not request.is_json:
            return jsonify({
                "error": "Invalid request",
                "message": "Request must be JSON",
            }), 400

        try:
            data = CreateFolderRequest(**request.get_json())
        except ValidationError as e:
            return jsonify({
                "error": "Validation error",
                "message": "Invalid request data",
                "details": e.errors(),
            }), 400

        try:
            db = get_db()

            # Validate parent folder if provided
            parent_uuid = None
            if data.parent_id:
                try:
                    parent_uuid = UUID(data.parent_id)
                    parent = run_async(db.folders.get_by_id(parent_uuid))
                    if str(parent.user_id) != g.current_user_id:
                        return jsonify({
                            "error": "Invalid parent",
                            "message": "Parent folder not found",
                        }), 400
                except (ValueError, RecordNotFoundError):
                    return jsonify({
                        "error": "Invalid parent",
                        "message": "Parent folder not found",
                    }), 400

            # Check for duplicate folder name at same level
            existing_folders = run_async(
                db.folders.get_by_user(UUID(g.current_user_id))
            )
            for f in existing_folders:
                if f.name.lower() == data.name.lower() and f.parent_id == parent_uuid:
                    return jsonify({
                        "error": "Duplicate folder",
                        "message": f"A folder named '{data.name}' already exists",
                    }), 409

            # Create folder
            folder_create = FolderCreate(
                name=data.name,
                folder_type=FolderType.CUSTOM,
                parent_id=parent_uuid,
                color=data.color,
                icon=data.icon,
            )

            folder = run_async(
                db.folders.create_folder(UUID(g.current_user_id), folder_create)
            )

            logger.info(
                "Folder created",
                extra={
                    "user_id": g.current_user_id,
                    "folder_id": str(folder.id),
                },
            )

            return jsonify(serialize_folder(folder)), 201

        except Exception as e:
            logger.error(f"Create folder error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while creating the folder",
            }), 500

    @bp.route("/<folder_id>", methods=["PUT"])
    @require_auth
    def update_folder(folder_id: str) -> tuple[Response, int]:
        """
        Update a folder (rename, move, change appearance).

        Path Parameters:
            - folder_id: Folder UUID

        Request Body:
            - name: New folder name
            - parent_id: New parent folder ID
            - color: Folder color in hex format
            - icon: Folder icon name
            - sort_order: Display order

        Returns:
            Updated folder details.
        """
        try:
            # Validate UUID
            try:
                folder_uuid = UUID(folder_id)
            except ValueError:
                return jsonify({
                    "error": "Invalid parameter",
                    "message": "folder_id must be a valid UUID",
                }), 400

            if not request.is_json:
                return jsonify({
                    "error": "Invalid request",
                    "message": "Request must be JSON",
                }), 400

            try:
                data = UpdateFolderRequest(**request.get_json())
            except ValidationError as e:
                return jsonify({
                    "error": "Validation error",
                    "message": "Invalid request data",
                    "details": e.errors(),
                }), 400

            db = get_db()

            # Get existing folder
            folder = run_async(db.folders.get_by_id(folder_uuid))

            # Check ownership
            if str(folder.user_id) != g.current_user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Folder not found",
                }), 404

            # Check if it's a system folder (cannot rename system folders)
            if folder.is_system and data.name and data.name != folder.name:
                return jsonify({
                    "error": "Cannot modify",
                    "message": "System folders cannot be renamed",
                }), 403

            # Build update data
            update_data = {}

            if data.name is not None:
                # Check for duplicate name
                existing_folders = run_async(
                    db.folders.get_by_user(UUID(g.current_user_id))
                )
                target_parent = UUID(data.parent_id) if data.parent_id else folder.parent_id
                for f in existing_folders:
                    if (f.id != folder.id and
                        f.name.lower() == data.name.lower() and
                        f.parent_id == target_parent):
                        return jsonify({
                            "error": "Duplicate folder",
                            "message": f"A folder named '{data.name}' already exists",
                        }), 409
                update_data["name"] = data.name

            if data.parent_id is not None:
                # Validate new parent
                try:
                    new_parent_uuid = UUID(data.parent_id)

                    # Cannot set folder as its own parent
                    if new_parent_uuid == folder_uuid:
                        return jsonify({
                            "error": "Invalid parent",
                            "message": "Folder cannot be its own parent",
                        }), 400

                    # Verify parent exists and belongs to user
                    parent = run_async(db.folders.get_by_id(new_parent_uuid))
                    if str(parent.user_id) != g.current_user_id:
                        return jsonify({
                            "error": "Invalid parent",
                            "message": "Parent folder not found",
                        }), 400

                    update_data["parent_id"] = new_parent_uuid
                except ValueError:
                    return jsonify({
                        "error": "Invalid parameter",
                        "message": "parent_id must be a valid UUID",
                    }), 400
                except RecordNotFoundError:
                    return jsonify({
                        "error": "Invalid parent",
                        "message": "Parent folder not found",
                    }), 400

            if data.color is not None:
                update_data["color"] = data.color

            if data.icon is not None:
                update_data["icon"] = data.icon

            if data.sort_order is not None:
                update_data["sort_order"] = data.sort_order

            if not update_data:
                return jsonify({
                    "error": "Invalid request",
                    "message": "No valid fields to update",
                }), 400

            # Update folder
            folder_update = FolderUpdate(**update_data)
            folder = run_async(db.folders.update_folder(folder_uuid, folder_update))

            logger.info(
                "Folder updated",
                extra={
                    "user_id": g.current_user_id,
                    "folder_id": folder_id,
                },
            )

            return jsonify(serialize_folder(folder)), 200

        except RecordNotFoundError:
            return jsonify({
                "error": "Not found",
                "message": "Folder not found",
            }), 404

        except Exception as e:
            logger.error(f"Update folder error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while updating the folder",
            }), 500

    @bp.route("/<folder_id>", methods=["DELETE"])
    @require_auth
    def delete_folder(folder_id: str) -> tuple[Response, int]:
        """
        Delete a folder.

        Path Parameters:
            - folder_id: Folder UUID

        Query Parameters:
            - move_to: Folder ID to move messages to before deletion
            - force: If true, delete even if folder has messages (default: false)

        Returns:
            Success message.
        """
        try:
            # Validate UUID
            try:
                folder_uuid = UUID(folder_id)
            except ValueError:
                return jsonify({
                    "error": "Invalid parameter",
                    "message": "folder_id must be a valid UUID",
                }), 400

            move_to = request.args.get("move_to")
            force = request.args.get("force", "false").lower() == "true"

            db = get_db()

            # Get existing folder
            folder = run_async(db.folders.get_by_id(folder_uuid))

            # Check ownership
            if str(folder.user_id) != g.current_user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Folder not found",
                }), 404

            # Cannot delete system folders
            if folder.is_system:
                return jsonify({
                    "error": "Cannot delete",
                    "message": "System folders cannot be deleted",
                }), 403

            # Check if folder has messages
            if folder.message_count > 0:
                if move_to:
                    # Move messages to specified folder
                    try:
                        target_uuid = UUID(move_to)
                        target = run_async(db.folders.get_by_id(target_uuid))
                        if str(target.user_id) != g.current_user_id:
                            return jsonify({
                                "error": "Invalid target",
                                "message": "Target folder not found",
                            }), 400

                        # Move messages (this would need batch update)
                        messages = run_async(
                            db.messages.get_by_user(
                                UUID(g.current_user_id),
                                folder_id=folder_uuid,
                                limit=1000,
                            )
                        )
                        for msg in messages:
                            run_async(
                                db.messages.update(msg.id, {"folder_id": target_uuid})
                            )

                    except (ValueError, RecordNotFoundError):
                        return jsonify({
                            "error": "Invalid target",
                            "message": "Target folder not found",
                        }), 400
                elif not force:
                    return jsonify({
                        "error": "Folder not empty",
                        "message": f"Folder contains {folder.message_count} messages. "
                                   "Use 'move_to' to move messages or 'force=true' to delete anyway.",
                    }), 400

            # Check for child folders
            all_folders = run_async(db.folders.get_by_user(UUID(g.current_user_id)))
            children = [f for f in all_folders if f.parent_id == folder_uuid]
            if children:
                return jsonify({
                    "error": "Folder has children",
                    "message": f"Folder has {len(children)} child folders. "
                               "Delete or move them first.",
                }), 400

            # Delete folder
            run_async(db.folders.delete(folder_uuid))

            logger.info(
                "Folder deleted",
                extra={
                    "user_id": g.current_user_id,
                    "folder_id": folder_id,
                },
            )

            return jsonify({
                "message": "Folder deleted successfully",
            }), 200

        except RecordNotFoundError:
            return jsonify({
                "error": "Not found",
                "message": "Folder not found",
            }), 404

        except Exception as e:
            logger.error(f"Delete folder error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while deleting the folder",
            }), 500

    return bp


# Export public components
__all__ = [
    "create_folders_blueprint",
]
