"""
Contact routes for unitMail Gateway API.

This module provides endpoints for contact/address book management
including listing, creating, updating, and deleting contacts.
"""

import asyncio
import logging
from typing import Any, Optional
from uuid import UUID

from flask import Blueprint, Response, g, jsonify, request
from pydantic import BaseModel, EmailStr, Field, ValidationError

from ....common.database import get_db
from ....common.exceptions import DuplicateRecordError, RecordNotFoundError
from ....common.models import ContactCreate, ContactUpdate
from ..middleware import rate_limit
from .auth import require_auth

# Configure module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================


class CreateContactRequest(BaseModel):
    """Request model for creating a contact."""

    email: EmailStr = Field(..., description="Contact email address")
    name: Optional[str] = Field(None, max_length=200, description="Contact name")
    nickname: Optional[str] = Field(None, max_length=50, description="Contact nickname")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    organization: Optional[str] = Field(
        None, max_length=200, description="Organization name"
    )
    notes: Optional[str] = Field(None, description="Additional notes")
    tags: list[str] = Field(default_factory=list, description="Contact tags")
    is_favorite: bool = Field(default=False, description="Mark as favorite")


class UpdateContactRequest(BaseModel):
    """Request model for updating a contact."""

    email: Optional[EmailStr] = Field(None, description="Contact email address")
    name: Optional[str] = Field(None, max_length=200, description="Contact name")
    nickname: Optional[str] = Field(None, max_length=50, description="Contact nickname")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    organization: Optional[str] = Field(
        None, max_length=200, description="Organization name"
    )
    notes: Optional[str] = Field(None, description="Additional notes")
    tags: Optional[list[str]] = Field(None, description="Contact tags")
    is_favorite: Optional[bool] = Field(None, description="Favorite status")


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


def serialize_contact(contact) -> dict[str, Any]:
    """Serialize a contact model to JSON-compatible dict."""
    return {
        "id": str(contact.id),
        "user_id": str(contact.user_id),
        "email": contact.email,
        "name": contact.name,
        "nickname": contact.nickname,
        "phone": contact.phone,
        "organization": contact.organization,
        "notes": contact.notes,
        "is_favorite": contact.is_favorite,
        "tags": contact.tags,
        "metadata": contact.metadata,
        "created_at": contact.created_at.isoformat(),
        "updated_at": contact.updated_at.isoformat(),
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
            - tag: Filter by tag

        Returns:
            Paginated list of contacts.
        """
        try:
            # Parse query parameters
            page = max(1, int(request.args.get("page", 1)))
            per_page = min(100, max(1, int(request.args.get("per_page", 50))))
            search = request.args.get("search", "").strip()
            favorites_only = request.args.get("favorites", "").lower() == "true"
            tag_filter = request.args.get("tag", "").strip()

            offset = (page - 1) * per_page

            db = get_db()

            # Build filters
            filters = {"user_id": UUID(g.current_user_id)}

            if favorites_only:
                filters["is_favorite"] = True

            # Get contacts
            contacts = run_async(
                db.contacts.get_all(
                    limit=per_page,
                    offset=offset,
                    order_by="name",
                    ascending=True,
                    filters=filters,
                )
            )

            # Apply additional filters that may need post-processing
            if search:
                search_lower = search.lower()
                contacts = [
                    c for c in contacts
                    if (c.name and search_lower in c.name.lower()) or
                       search_lower in c.email.lower() or
                       (c.nickname and search_lower in c.nickname.lower())
                ]

            if tag_filter:
                contacts = [
                    c for c in contacts
                    if tag_filter in c.tags
                ]

            # Get total count (approximate for filtered results)
            total = run_async(db.contacts.count(filters={"user_id": UUID(g.current_user_id)}))

            return jsonify({
                "contacts": [serialize_contact(c) for c in contacts],
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
            # Validate UUID
            try:
                contact_uuid = UUID(contact_id)
            except ValueError:
                return jsonify({
                    "error": "Invalid parameter",
                    "message": "contact_id must be a valid UUID",
                }), 400

            db = get_db()
            contact = run_async(db.contacts.get_by_id(contact_uuid))

            # Check ownership
            if str(contact.user_id) != g.current_user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Contact not found",
                }), 404

            return jsonify(serialize_contact(contact)), 200

        except RecordNotFoundError:
            return jsonify({
                "error": "Not found",
                "message": "Contact not found",
            }), 404

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
            - nickname: Contact nickname
            - phone: Phone number
            - organization: Organization name
            - notes: Additional notes
            - tags: List of tags
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
            db = get_db()

            # Check if contact with this email already exists for user
            existing = run_async(
                db.contacts.get_by_email(UUID(g.current_user_id), data.email)
            )
            if existing:
                return jsonify({
                    "error": "Duplicate contact",
                    "message": f"A contact with email '{data.email}' already exists",
                }), 409

            # Create contact
            contact_create = ContactCreate(
                email=data.email,
                name=data.name,
                nickname=data.nickname,
                phone=data.phone,
                organization=data.organization,
                notes=data.notes,
                tags=data.tags,
            )

            contact = run_async(
                db.contacts.create_contact(UUID(g.current_user_id), contact_create)
            )

            # Update is_favorite if set
            if data.is_favorite:
                contact = run_async(
                    db.contacts.update(contact.id, {"is_favorite": True})
                )

            logger.info(
                "Contact created",
                extra={
                    "user_id": g.current_user_id,
                    "contact_id": str(contact.id),
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
            - nickname: Contact nickname
            - phone: Phone number
            - organization: Organization name
            - notes: Additional notes
            - tags: List of tags
            - is_favorite: Favorite status

        Returns:
            Updated contact details.
        """
        try:
            # Validate UUID
            try:
                contact_uuid = UUID(contact_id)
            except ValueError:
                return jsonify({
                    "error": "Invalid parameter",
                    "message": "contact_id must be a valid UUID",
                }), 400

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

            db = get_db()

            # Get existing contact
            contact = run_async(db.contacts.get_by_id(contact_uuid))

            # Check ownership
            if str(contact.user_id) != g.current_user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Contact not found",
                }), 404

            # Check for email conflict if changing email
            if data.email and data.email != contact.email:
                existing = run_async(
                    db.contacts.get_by_email(UUID(g.current_user_id), data.email)
                )
                if existing and existing.id != contact.id:
                    return jsonify({
                        "error": "Duplicate contact",
                        "message": f"A contact with email '{data.email}' already exists",
                    }), 409

            # Build update data (only include non-None values)
            update_data = data.model_dump(exclude_unset=True)

            if not update_data:
                return jsonify({
                    "error": "Invalid request",
                    "message": "No valid fields to update",
                }), 400

            # Create update model
            contact_update = ContactUpdate(**update_data)
            contact = run_async(db.contacts.update_contact(contact_uuid, contact_update))

            logger.info(
                "Contact updated",
                extra={
                    "user_id": g.current_user_id,
                    "contact_id": contact_id,
                },
            )

            return jsonify(serialize_contact(contact)), 200

        except RecordNotFoundError:
            return jsonify({
                "error": "Not found",
                "message": "Contact not found",
            }), 404

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
            # Validate UUID
            try:
                contact_uuid = UUID(contact_id)
            except ValueError:
                return jsonify({
                    "error": "Invalid parameter",
                    "message": "contact_id must be a valid UUID",
                }), 400

            db = get_db()

            # Get existing contact
            contact = run_async(db.contacts.get_by_id(contact_uuid))

            # Check ownership
            if str(contact.user_id) != g.current_user_id:
                return jsonify({
                    "error": "Not found",
                    "message": "Contact not found",
                }), 404

            # Delete contact
            run_async(db.contacts.delete(contact_uuid))

            logger.info(
                "Contact deleted",
                extra={
                    "user_id": g.current_user_id,
                    "contact_id": contact_id,
                },
            )

            return jsonify({
                "message": "Contact deleted successfully",
            }), 200

        except RecordNotFoundError:
            return jsonify({
                "error": "Not found",
                "message": "Contact not found",
            }), 404

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
