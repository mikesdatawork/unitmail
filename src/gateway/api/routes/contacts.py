"""
Contact routes for unitMail Gateway API.

This module provides endpoints for contact/address book management
including listing, creating, updating, and deleting contacts.
Uses SQLite for storage.
"""

import logging
from typing import Any, Optional

from flask import Blueprint, Response, g, jsonify, request
from pydantic import BaseModel, EmailStr, Field, ValidationError

from common.storage import get_storage
from common.exceptions import DuplicateRecordError
from ..middleware import rate_limit
from ..auth import require_auth

# Configure module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================


class CreateContactRequest(BaseModel):
    """Request model for creating a contact."""

    email: EmailStr = Field(..., description="Contact email address")
    name: Optional[str] = Field(None, max_length=200, description="Contact name")
    display_name: Optional[str] = Field(None, max_length=200, description="Display name")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    organization: Optional[str] = Field(
        None, max_length=200, description="Organization name"
    )
    notes: Optional[str] = Field(None, description="Additional notes")
    is_favorite: bool = Field(default=False, description="Mark as favorite")


class UpdateContactRequest(BaseModel):
    """Request model for updating a contact."""

    email: Optional[EmailStr] = Field(None, description="Contact email address")
    name: Optional[str] = Field(None, max_length=200, description="Contact name")
    display_name: Optional[str] = Field(None, max_length=200, description="Display name")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    organization: Optional[str] = Field(
        None, max_length=200, description="Organization name"
    )
    notes: Optional[str] = Field(None, description="Additional notes")
    is_favorite: Optional[bool] = Field(None, description="Favorite status")


# =============================================================================
# Helper Functions
# =============================================================================


def serialize_contact(contact: dict) -> dict[str, Any]:
    """Serialize a contact dict for JSON response."""
    return {
        "id": contact["id"],
        "user_id": contact["user_id"],
        "email": contact["email"],
        "name": contact.get("name"),
        "display_name": contact.get("display_name"),
        "phone": contact.get("phone"),
        "organization": contact.get("organization"),
        "notes": contact.get("notes"),
        "is_favorite": contact.get("is_favorite", False),
        "contact_frequency": contact.get("contact_frequency", 0),
        "created_at": contact.get("created_at"),
        "updated_at": contact.get("updated_at"),
    }


# =============================================================================
# Blueprint and Routes
# =============================================================================


def create_contacts_blueprint() -> Blueprint:
    """
    Create the contacts blueprint.

    Returns:
        Blueprint for contact-related routes.
    """
    bp = Blueprint("contacts", __name__, url_prefix="/contacts")

    @bp.route("", methods=["GET"])
    @bp.route("/", methods=["GET"])
    @require_auth
    @rate_limit()
    def list_contacts() -> tuple[Response, int]:
        """
        List contacts for the current user.

        Query Parameters:
            - page: Page number (default: 1)
            - per_page: Items per page (default: 50, max: 100)
            - search: Search in name and email
            - favorites: Filter to favorites only (true/false)

        Returns:
            Paginated list of contacts.
        """
        try:
            # Parse query parameters
            page = max(1, int(request.args.get("page", 1)))
            per_page = min(100, max(1, int(request.args.get("per_page", 50))))
            search = request.args.get("search", "").strip()
            favorites_only = request.args.get("favorites", "").lower() == "true"

            offset = (page - 1) * per_page

            storage = get_storage()
            user_id = getattr(g, "user_id", None)

            # Get contacts
            if search:
                contacts = storage.search_contacts(
                    query=search,
                    user_id=user_id,
                    limit=per_page,
                )
                # Apply favorites filter to search results if needed
                if favorites_only:
                    contacts = [c for c in contacts if c.get("is_favorite")]
            else:
                contacts = storage.get_contacts(
                    user_id=user_id,
                    limit=per_page,
                    offset=offset,
                    favorites_only=favorites_only,
                )

            # Get total count
            total = storage.count_contacts(user_id=user_id)

            return jsonify({
                "contacts": [serialize_contact(c) for c in contacts],
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
            logger.error(f"List contacts error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while fetching contacts",
            }), 500

    @bp.route("/<contact_id>", methods=["GET"])
    @require_auth
    def get_contact(contact_id: str) -> tuple[Response, int]:
        """
        Get a single contact by ID.

        Path Parameters:
            - contact_id: Contact UUID

        Returns:
            Contact details.
        """
        try:
            storage = get_storage()
            contact = storage.get_contact(contact_id)

            if not contact:
                return jsonify({
                    "error": "Not found",
                    "message": "Contact not found",
                }), 404

            # Check ownership
            user_id = getattr(g, "user_id", None)
            if contact.get("user_id") != user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Contact not found",
                }), 404

            return jsonify(serialize_contact(contact)), 200

        except Exception as e:
            logger.error(f"Get contact error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while fetching the contact",
            }), 500

    @bp.route("", methods=["POST"])
    @bp.route("/", methods=["POST"])
    @require_auth
    @rate_limit()
    def create_contact() -> tuple[Response, int]:
        """
        Create a new contact.

        Request Body:
            - email: Contact email address (required)
            - name: Contact name
            - display_name: Display name
            - phone: Phone number
            - organization: Organization name
            - notes: Additional notes
            - is_favorite: Mark as favorite

        Returns:
            Created contact details.
        """
        if not request.is_json:
            return jsonify({
                "error": "Invalid request",
                "message": "Request must be JSON",
            }), 400

        try:
            data = CreateContactRequest(**request.get_json())
        except ValidationError as e:
            return jsonify({
                "error": "Validation error",
                "message": "Invalid request data",
                "details": e.errors(),
            }), 400

        try:
            storage = get_storage()
            user_id = getattr(g, "user_id", None)

            # Check if contact with this email already exists for user
            existing = storage.get_contact_by_email(str(data.email), user_id)
            if existing:
                return jsonify({
                    "error": "Duplicate contact",
                    "message": f"A contact with email '{data.email}' already exists",
                }), 409

            # Create contact
            contact_data = {
                "user_id": user_id,
                "email": str(data.email),
                "name": data.name,
                "display_name": data.display_name or data.name,
                "phone": data.phone,
                "organization": data.organization,
                "notes": data.notes,
                "is_favorite": data.is_favorite,
            }

            contact = storage.create_contact(contact_data)

            logger.info(
                "Contact created",
                extra={
                    "user_id": user_id,
                    "contact_id": contact["id"],
                },
            )

            return jsonify(serialize_contact(contact)), 201

        except DuplicateRecordError:
            return jsonify({
                "error": "Duplicate contact",
                "message": "A contact with this email already exists",
            }), 409

        except Exception as e:
            logger.error(f"Create contact error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while creating the contact",
            }), 500

    @bp.route("/<contact_id>", methods=["PUT"])
    @require_auth
    def update_contact(contact_id: str) -> tuple[Response, int]:
        """
        Update a contact.

        Path Parameters:
            - contact_id: Contact UUID

        Request Body:
            - email: Contact email address
            - name: Contact name
            - display_name: Display name
            - phone: Phone number
            - organization: Organization name
            - notes: Additional notes
            - is_favorite: Favorite status

        Returns:
            Updated contact details.
        """
        try:
            if not request.is_json:
                return jsonify({
                    "error": "Invalid request",
                    "message": "Request must be JSON",
                }), 400

            try:
                data = UpdateContactRequest(**request.get_json())
            except ValidationError as e:
                return jsonify({
                    "error": "Validation error",
                    "message": "Invalid request data",
                    "details": e.errors(),
                }), 400

            storage = get_storage()
            user_id = getattr(g, "user_id", None)

            # Get existing contact
            contact = storage.get_contact(contact_id)

            if not contact:
                return jsonify({
                    "error": "Not found",
                    "message": "Contact not found",
                }), 404

            # Check ownership
            if contact.get("user_id") != user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Contact not found",
                }), 404

            # Check for email conflict if changing email
            if data.email and str(data.email) != contact.get("email"):
                existing = storage.get_contact_by_email(str(data.email), user_id)
                if existing and existing["id"] != contact_id:
                    return jsonify({
                        "error": "Duplicate contact",
                        "message": f"A contact with email '{data.email}' already exists",
                    }), 409

            # Build update data (only include non-None values)
            update_data = data.model_dump(exclude_unset=True)
            if "email" in update_data:
                update_data["email"] = str(update_data["email"])

            if not update_data:
                return jsonify({
                    "error": "Invalid request",
                    "message": "No valid fields to update",
                }), 400

            contact = storage.update_contact(contact_id, update_data)

            logger.info(
                "Contact updated",
                extra={
                    "user_id": user_id,
                    "contact_id": contact_id,
                },
            )

            return jsonify(serialize_contact(contact)), 200

        except Exception as e:
            logger.error(f"Update contact error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while updating the contact",
            }), 500

    @bp.route("/<contact_id>", methods=["DELETE"])
    @require_auth
    def delete_contact(contact_id: str) -> tuple[Response, int]:
        """
        Delete a contact.

        Path Parameters:
            - contact_id: Contact UUID

        Returns:
            Success message.
        """
        try:
            storage = get_storage()
            user_id = getattr(g, "user_id", None)

            # Get existing contact
            contact = storage.get_contact(contact_id)

            if not contact:
                return jsonify({
                    "error": "Not found",
                    "message": "Contact not found",
                }), 404

            # Check ownership
            if contact.get("user_id") != user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Contact not found",
                }), 404

            # Delete contact
            storage.delete_contact(contact_id)

            logger.info(
                "Contact deleted",
                extra={
                    "user_id": user_id,
                    "contact_id": contact_id,
                },
            )

            return jsonify({
                "message": "Contact deleted successfully",
            }), 200

        except Exception as e:
            logger.error(f"Delete contact error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while deleting the contact",
            }), 500

    return bp


# Export public components
__all__ = [
    "create_contacts_blueprint",
]
