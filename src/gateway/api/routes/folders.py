"""
Folder routes for unitMail Gateway API.

This module provides endpoints for email folder management
including listing, creating, renaming, and deleting folders.
Uses SQLite for storage.
"""

import logging
from typing import Any, Optional

from flask import Blueprint, Response, g, jsonify, request
from pydantic import BaseModel, Field, ValidationError, field_validator

from common.storage import get_storage
from ..middleware import rate_limit
from ..auth import require_auth

# Configure module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================


class CreateFolderRequest(BaseModel):
    """Request model for creating a folder."""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Folder name"
    )
    parent_id: Optional[str] = Field(
        None, description="Parent folder ID for nesting"
    )
    color: Optional[str] = Field(
        None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Folder color (hex)"
    )
    icon: Optional[str] = Field(
        None, max_length=50, description="Folder icon name"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate folder name."""
        forbidden = ["/", "\\", "<", ">", ":", '"', "|", "?", "*"]
        if any(c in v for c in forbidden):
            raise ValueError(
                f"Folder name cannot contain: {' '.join(forbidden)}"
            )
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
    icon: Optional[str] = Field(
        None, max_length=50, description="Folder icon name"
    )
    sort_order: Optional[int] = Field(None, ge=0, description="Sort order")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate folder name."""
        if v is None:
            return v
        forbidden = ["/", "\\", "<", ">", ":", '"', "|", "?", "*"]
        if any(c in v for c in forbidden):
            raise ValueError(
                f"Folder name cannot contain: {' '.join(forbidden)}"
            )
        return v.strip()


# =============================================================================
# Helper Functions
# =============================================================================


def serialize_folder(folder: dict) -> dict[str, Any]:
    """Serialize a folder dict for JSON response."""
    return {
        "id": folder["id"],
        "user_id": folder.get("user_id"),
        "name": folder["name"],
        "folder_type": folder.get("folder_type", "custom"),
        "parent_id": folder.get("parent_id"),
        "color": folder.get("color"),
        "icon": folder.get("icon"),
        "sort_order": folder.get("sort_order", 0),
        "is_system": folder.get("is_system", False),
        "message_count": folder.get("message_count", 0),
        "unread_count": folder.get("unread_count", 0),
        "created_at": folder.get("created_at"),
        "updated_at": folder.get("updated_at"),
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
            include_system = (
                request.args.get("include_system", "true").lower() == "true"
            )
            parent_id = request.args.get("parent_id")

            storage = get_storage()
            user_id = getattr(g, "user_id", None)

            # Get all folders
            if user_id:
                folders = storage.get_folders_by_user(user_id)
            else:
                folders = storage.get_folders()

            # Apply filters
            if not include_system:
                folders = [f for f in folders if not f.get("is_system")]

            if parent_id is not None:
                if parent_id == "" or parent_id.lower() == "null":
                    # Root level folders
                    folders = [
                        f for f in folders if f.get("parent_id") is None
                    ]
                else:
                    folders = [
                        f for f in folders if f.get("parent_id") == parent_id
                    ]

            # Calculate totals
            total_messages = sum(f.get("message_count", 0) for f in folders)
            total_unread = sum(f.get("unread_count", 0) for f in folders)

            return (
                jsonify(
                    {
                        "folders": [serialize_folder(f) for f in folders],
                        "summary": {
                            "total_folders": len(folders),
                            "total_messages": total_messages,
                            "total_unread": total_unread,
                        },
                    }
                ),
                200,
            )

        except Exception as e:
            logger.error(f"List folders error: {e}")
            return (
                jsonify(
                    {
                        "error": "Server error",
                        "message": "An error occurred while fetching folders",
                    }
                ),
                500,
            )

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
            storage = get_storage()
            folder = storage.get_folder_by_id(folder_id)

            if not folder:
                return (
                    jsonify(
                        {
                            "error": "Not found",
                            "message": "Folder not found",
                        }
                    ),
                    404,
                )

            # Check ownership
            user_id = getattr(g, "user_id", None)
            if folder.get("user_id") and folder.get("user_id") != user_id:
                return (
                    jsonify(
                        {
                            "error": "Not found",
                            "message": "Folder not found",
                        }
                    ),
                    404,
                )

            return jsonify(serialize_folder(folder)), 200

        except Exception as e:
            logger.error(f"Get folder error: {e}")
            return (
                jsonify(
                    {
                        "error": "Server error",
                        "message": "An error occurred while fetching the folder",
                    }
                ),
                500,
            )

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
            return (
                jsonify(
                    {
                        "error": "Invalid request",
                        "message": "Request must be JSON",
                    }
                ),
                400,
            )

        try:
            data = CreateFolderRequest(**request.get_json())
        except ValidationError as e:
            return (
                jsonify(
                    {
                        "error": "Validation error",
                        "message": "Invalid request data",
                        "details": e.errors(),
                    }
                ),
                400,
            )

        try:
            storage = get_storage()
            user_id = getattr(g, "user_id", None)

            # Validate parent folder if provided
            if data.parent_id:
                parent = storage.get_folder_by_id(data.parent_id)
                if not parent:
                    return (
                        jsonify(
                            {
                                "error": "Invalid parent",
                                "message": "Parent folder not found",
                            }
                        ),
                        400,
                    )
                # Check ownership of parent
                if parent.get("user_id") and parent.get("user_id") != user_id:
                    return (
                        jsonify(
                            {
                                "error": "Invalid parent",
                                "message": "Parent folder not found",
                            }
                        ),
                        400,
                    )

            # Check for duplicate folder name at same level
            if user_id:
                existing_folders = storage.get_folders_by_user(user_id)
            else:
                existing_folders = storage.get_folders()

            for f in existing_folders:
                if (
                    f["name"].lower() == data.name.lower()
                    and f.get("parent_id") == data.parent_id
                ):
                    return (
                        jsonify(
                            {
                                "error": "Duplicate folder",
                                "message": f"Folder '{data.name}' already exists",
                            }
                        ),
                        409,
                    )

            # Create folder
            try:
                folder = storage.create_folder(data.name, data.parent_id)
            except ValueError as e:
                return (
                    jsonify(
                        {
                            "error": "Invalid request",
                            "message": str(e),
                        }
                    ),
                    400,
                )

            # Update additional properties if provided
            if data.color or data.icon:
                updates = {}
                if data.color:
                    updates["color"] = data.color
                if data.icon:
                    updates["icon"] = data.icon
                if updates:
                    folder = storage.update_folder(folder["id"], updates)

            logger.info(
                "Folder created",
                extra={
                    "user_id": user_id,
                    "folder_id": folder["id"],
                },
            )

            return jsonify(serialize_folder(folder)), 201

        except Exception as e:
            logger.error(f"Create folder error: {e}")
            return (
                jsonify(
                    {
                        "error": "Server error",
                        "message": "An error occurred while creating the folder",
                    }
                ),
                500,
            )

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

            try:
                data = UpdateFolderRequest(**request.get_json())
            except ValidationError as e:
                return (
                    jsonify(
                        {
                            "error": "Validation error",
                            "message": "Invalid request data",
                            "details": e.errors(),
                        }
                    ),
                    400,
                )

            storage = get_storage()
            user_id = getattr(g, "user_id", None)

            # Get existing folder
            folder = storage.get_folder_by_id(folder_id)

            if not folder:
                return (
                    jsonify(
                        {
                            "error": "Not found",
                            "message": "Folder not found",
                        }
                    ),
                    404,
                )

            # Check ownership
            if folder.get("user_id") and folder.get("user_id") != user_id:
                return (
                    jsonify(
                        {
                            "error": "Not found",
                            "message": "Folder not found",
                        }
                    ),
                    404,
                )

            # Check if it's a system folder (cannot rename system folders)
            if (
                folder.get("is_system")
                and data.name
                and data.name != folder["name"]
            ):
                return (
                    jsonify(
                        {
                            "error": "Cannot modify",
                            "message": "System folders cannot be renamed",
                        }
                    ),
                    403,
                )

            # Build update data
            update_data = {}

            if data.name is not None:
                # Check for duplicate name
                if user_id:
                    existing_folders = storage.get_folders_by_user(user_id)
                else:
                    existing_folders = storage.get_folders()

                target_parent = (
                    data.parent_id
                    if data.parent_id is not None
                    else folder.get("parent_id")
                )
                for f in existing_folders:
                    if (
                        f["id"] != folder["id"]
                        and f["name"].lower() == data.name.lower()
                        and f.get("parent_id") == target_parent
                    ):
                        return (
                            jsonify(
                                {
                                    "error": "Duplicate folder",
                                    "message": f"Folder '{data.name}' already exists",
                                }
                            ),
                            409,
                        )
                update_data["name"] = data.name

            if data.parent_id is not None:
                # Cannot set folder as its own parent
                if data.parent_id == folder_id:
                    return (
                        jsonify(
                            {
                                "error": "Invalid parent",
                                "message": "Folder cannot be its own parent",
                            }
                        ),
                        400,
                    )

                # Verify parent exists
                parent = storage.get_folder_by_id(data.parent_id)
                if not parent:
                    return (
                        jsonify(
                            {
                                "error": "Invalid parent",
                                "message": "Parent folder not found",
                            }
                        ),
                        400,
                    )

                # Check ownership of parent
                if parent.get("user_id") and parent.get("user_id") != user_id:
                    return (
                        jsonify(
                            {
                                "error": "Invalid parent",
                                "message": "Parent folder not found",
                            }
                        ),
                        400,
                    )

                update_data["parent_id"] = data.parent_id

            if data.color is not None:
                update_data["color"] = data.color

            if data.icon is not None:
                update_data["icon"] = data.icon

            if data.sort_order is not None:
                update_data["sort_order"] = data.sort_order

            if not update_data:
                return (
                    jsonify(
                        {
                            "error": "Invalid request",
                            "message": "No valid fields to update",
                        }
                    ),
                    400,
                )

            # Update folder
            folder = storage.update_folder(folder_id, update_data)

            if not folder:
                return (
                    jsonify(
                        {
                            "error": "Cannot modify",
                            "message": "Folder could not be updated",
                        }
                    ),
                    400,
                )

            logger.info(
                "Folder updated",
                extra={
                    "user_id": user_id,
                    "folder_id": folder_id,
                },
            )

            return jsonify(serialize_folder(folder)), 200

        except Exception as e:
            logger.error(f"Update folder error: {e}")
            return (
                jsonify(
                    {
                        "error": "Server error",
                        "message": "An error occurred while updating the folder",
                    }
                ),
                500,
            )

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
            move_to = request.args.get("move_to")
            force = request.args.get("force", "false").lower() == "true"

            storage = get_storage()
            user_id = getattr(g, "user_id", None)

            # Get existing folder
            folder = storage.get_folder_by_id(folder_id)

            if not folder:
                return (
                    jsonify(
                        {
                            "error": "Not found",
                            "message": "Folder not found",
                        }
                    ),
                    404,
                )

            # Check ownership
            if folder.get("user_id") and folder.get("user_id") != user_id:
                return (
                    jsonify(
                        {
                            "error": "Not found",
                            "message": "Folder not found",
                        }
                    ),
                    404,
                )

            # Cannot delete system folders
            if folder.get("is_system"):
                return (
                    jsonify(
                        {
                            "error": "Cannot delete",
                            "message": "System folders cannot be deleted",
                        }
                    ),
                    403,
                )

            # Check if folder has messages
            message_count = folder.get("message_count", 0)
            if message_count > 0:
                if move_to:
                    # Verify target folder
                    target = storage.get_folder_by_id(move_to)
                    if not target:
                        return (
                            jsonify(
                                {
                                    "error": "Invalid target",
                                    "message": "Target folder not found",
                                }
                            ),
                            400,
                        )

                    # Check ownership of target
                    if (
                        target.get("user_id")
                        and target.get("user_id") != user_id
                    ):
                        return (
                            jsonify(
                                {
                                    "error": "Invalid target",
                                    "message": "Target folder not found",
                                }
                            ),
                            400,
                        )

                    # Move messages to target folder
                    messages = storage.get_messages(
                        folder_id=folder_id,
                        limit=1000,
                    )
                    for msg in messages:
                        storage.update_message(
                            msg["id"], {"folder_id": move_to}
                        )

                elif not force:
                    return (
                        jsonify(
                            {
                                "error": "Folder not empty",
                                "message": (
                                    f"Folder has {message_count} messages. "
                                    "Use 'move_to' or 'force=true'."
                                ),
                            }
                        ),
                        400,
                    )

            # Check for child folders
            if user_id:
                all_folders = storage.get_folders_by_user(user_id)
            else:
                all_folders = storage.get_folders()

            children = [
                f for f in all_folders if f.get("parent_id") == folder_id
            ]
            if children:
                return (
                    jsonify(
                        {
                            "error": "Folder has children",
                            "message": f"Folder has {len(children)} child folders. "
                            "Delete or move them first.",
                        }
                    ),
                    400,
                )

            # Delete folder
            storage.delete_folder(folder_id)

            logger.info(
                "Folder deleted",
                extra={
                    "user_id": user_id,
                    "folder_id": folder_id,
                },
            )

            return (
                jsonify(
                    {
                        "message": "Folder deleted successfully",
                    }
                ),
                200,
            )

        except Exception as e:
            logger.error(f"Delete folder error: {e}")
            return (
                jsonify(
                    {
                        "error": "Server error",
                        "message": "An error occurred while deleting the folder",
                    }
                ),
                500,
            )

    return bp


# Export public components
__all__ = [
    "create_folders_blueprint",
]
