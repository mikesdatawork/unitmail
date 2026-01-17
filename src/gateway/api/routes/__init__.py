"""
Blueprint registration for unitMail Gateway API routes.

This module provides the central registration point for all API blueprints,
organizing routes into logical groups.
"""

import logging
from datetime import datetime, timezone

from flask import Blueprint, Flask, jsonify

# Import blueprint factories from route modules
from .auth import create_auth_blueprint, require_auth
from .contacts import create_contacts_blueprint
from .folders import create_folders_blueprint
from .messages import create_messages_blueprint
from .queue import create_queue_blueprint

# Configure module logger
logger = logging.getLogger(__name__)

# API version prefix
API_V1_PREFIX = "/api/v1"


def create_api_v1_blueprint() -> Blueprint:
    """
    Create the main API v1 blueprint.

    Returns:
        Blueprint for API v1 routes.
    """
    bp = Blueprint("api_v1", __name__, url_prefix=API_V1_PREFIX)

    @bp.route("/", methods=["GET"])
    def api_root():
        """API v1 root endpoint."""
        return jsonify({
            "api": "unitmail-gateway",
            "version": "v1",
            "status": "operational",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoints": {
                "auth": f"{API_V1_PREFIX}/auth",
                "messages": f"{API_V1_PREFIX}/messages",
                "contacts": f"{API_V1_PREFIX}/contacts",
                "folders": f"{API_V1_PREFIX}/folders",
                "queue": f"{API_V1_PREFIX}/queue",
            },
        })

    @bp.route("/health", methods=["GET"])
    def health_check():
        """Health check endpoint."""
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return bp


def create_mailboxes_blueprint() -> Blueprint:
    """
    Create the mailboxes blueprint.

    Returns:
        Blueprint for mailbox-related routes.
    """
    bp = Blueprint("mailboxes", __name__, url_prefix="/mailboxes")

    # Placeholder routes - to be implemented
    @bp.route("/", methods=["GET"])
    def list_mailboxes():
        """List mailboxes endpoint."""
        return jsonify(
            {"message": "List mailboxes endpoint - to be implemented"}), 501

    @bp.route("/<mailbox_id>", methods=["GET"])
    def get_mailbox(mailbox_id: str):
        """Get single mailbox endpoint."""
        return jsonify(
            {"message": f"Get mailbox {mailbox_id} endpoint - to be implemented"}), 501

    @bp.route("/", methods=["POST"])
    def create_mailbox():
        """Create mailbox endpoint."""
        return jsonify(
            {"message": "Create mailbox endpoint - to be implemented"}), 501

    @bp.route("/<mailbox_id>", methods=["DELETE"])
    def delete_mailbox(mailbox_id: str):
        """Delete mailbox endpoint."""
        return jsonify(
            {"message": f"Delete mailbox {mailbox_id} endpoint - to be implemented"}), 501

    return bp


def create_users_blueprint() -> Blueprint:
    """
    Create the users blueprint.

    Returns:
        Blueprint for user-related routes.
    """
    bp = Blueprint("users", __name__, url_prefix="/users")

    # Placeholder routes - to be implemented
    @bp.route("/me", methods=["GET"])
    def get_current_user():
        """Get current user endpoint."""
        return jsonify(
            {"message": "Get current user endpoint - to be implemented"}), 501

    @bp.route("/me", methods=["PATCH"])
    def update_current_user():
        """Update current user endpoint."""
        return jsonify(
            {"message": "Update current user endpoint - to be implemented"}), 501

    @bp.route("/", methods=["GET"])
    def list_users():
        """List users endpoint (admin only)."""
        return jsonify(
            {"message": "List users endpoint - to be implemented"}), 501

    return bp


def create_domains_blueprint() -> Blueprint:
    """
    Create the domains blueprint.

    Returns:
        Blueprint for domain-related routes.
    """
    bp = Blueprint("domains", __name__, url_prefix="/domains")

    # Placeholder routes - to be implemented
    @bp.route("/", methods=["GET"])
    def list_domains():
        """List domains endpoint."""
        return jsonify(
            {"message": "List domains endpoint - to be implemented"}), 501

    @bp.route("/<domain_id>", methods=["GET"])
    def get_domain(domain_id: str):
        """Get single domain endpoint."""
        return jsonify(
            {"message": f"Get domain {domain_id} endpoint - to be implemented"}), 501

    @bp.route("/", methods=["POST"])
    def create_domain():
        """Create domain endpoint."""
        return jsonify(
            {"message": "Create domain endpoint - to be implemented"}), 501

    @bp.route("/<domain_id>/verify", methods=["POST"])
    def verify_domain(domain_id: str):
        """Verify domain endpoint."""
        return jsonify(
            {"message": f"Verify domain {domain_id} endpoint - to be implemented"}), 501

    return bp


def register_blueprints(app: Flask) -> None:
    """
    Register all blueprints with the Flask application.

    This function creates and registers all route blueprints,
    organizing them under the appropriate URL prefixes.

    Args:
        app: Flask application instance.
    """
    # Create API v1 blueprint
    api_v1 = create_api_v1_blueprint()

    # Create and nest sub-blueprints under API v1
    # Implemented blueprints
    auth_bp = create_auth_blueprint()
    messages_bp = create_messages_blueprint()
    contacts_bp = create_contacts_blueprint()
    folders_bp = create_folders_blueprint()
    queue_bp = create_queue_blueprint()

    # Placeholder blueprints (to be implemented)
    mailboxes_bp = create_mailboxes_blueprint()
    users_bp = create_users_blueprint()
    domains_bp = create_domains_blueprint()

    # Register sub-blueprints with API v1
    api_v1.register_blueprint(auth_bp)
    api_v1.register_blueprint(messages_bp)
    api_v1.register_blueprint(contacts_bp)
    api_v1.register_blueprint(folders_bp)
    api_v1.register_blueprint(queue_bp)
    api_v1.register_blueprint(mailboxes_bp)
    api_v1.register_blueprint(users_bp)
    api_v1.register_blueprint(domains_bp)

    # Register API v1 blueprint with app
    app.register_blueprint(api_v1)

    logger.info(
        "Blueprints registered",
        extra={
            "blueprints": [
                "api_v1",
                "auth",
                "messages",
                "contacts",
                "folders",
                "queue",
                "mailboxes",
                "users",
                "domains",
            ],
        },
    )


# Export public functions and components
__all__ = [
    # Registration
    "register_blueprints",
    # Blueprint factories
    "create_api_v1_blueprint",
    "create_auth_blueprint",
    "create_messages_blueprint",
    "create_contacts_blueprint",
    "create_folders_blueprint",
    "create_queue_blueprint",
    "create_mailboxes_blueprint",
    "create_users_blueprint",
    "create_domains_blueprint",
    # Auth utilities
    "require_auth",
    # Constants
    "API_V1_PREFIX",
]
