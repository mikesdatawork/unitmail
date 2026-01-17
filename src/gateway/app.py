"""
Flask application factory for unitMail Gateway service.

This module provides the main application factory for creating and configuring
the Flask application with all necessary extensions, blueprints, and middleware.
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from flask import Flask, Response, g, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from .config import GatewaySettings, get_gateway_settings

# Configure module logger
logger = logging.getLogger(__name__)


def create_app(settings: Optional[GatewaySettings] = None) -> Flask:
    """
    Create and configure the Flask application.

    This factory function creates a Flask application with all necessary
    configuration, extensions, blueprints, and middleware.

    Args:
        settings: Optional GatewaySettings instance. If not provided,
                 settings will be loaded from environment variables.

    Returns:
        Configured Flask application instance.
    """
    if settings is None:
        settings = get_gateway_settings()

    # Create Flask application
    app = Flask(__name__)

    # Configure the application
    _configure_app(app, settings)

    # Initialize extensions
    _init_extensions(app, settings)

    # Register blueprints
    _register_blueprints(app)

    # Register error handlers
    _register_error_handlers(app)

    # Register middleware
    _register_middleware(app, settings)

    # Register health check endpoint
    _register_health_check(app)

    logger.info(
        "Gateway application created",
        extra={
            "host": settings.host,
            "port": settings.port,
            "debug": settings.debug,
        },
    )

    return app


def _configure_app(app: Flask, settings: GatewaySettings) -> None:
    """
    Configure Flask application settings.

    Args:
        app: Flask application instance.
        settings: Gateway settings.
    """
    app.config["DEBUG"] = settings.debug
    app.config["SECRET_KEY"] = settings.secret_key
    app.config["MAX_CONTENT_LENGTH"] = settings.max_content_length

    # Session cookie settings
    app.config["SESSION_COOKIE_SECURE"] = settings.session_cookie_secure
    app.config["SESSION_COOKIE_HTTPONLY"] = settings.session_cookie_httponly
    app.config["SESSION_COOKIE_SAMESITE"] = settings.session_cookie_samesite

    # Store settings in app config for access in routes
    app.config["GATEWAY_SETTINGS"] = settings

    # Configure JSON settings
    app.json.sort_keys = False
    app.json.ensure_ascii = False


def _init_extensions(app: Flask, settings: GatewaySettings) -> None:
    """
    Initialize Flask extensions.

    Args:
        app: Flask application instance.
        settings: Gateway settings.
    """
    # Initialize CORS if enabled
    if settings.cors_enabled:
        CORS(
            app,
            origins=settings.cors_origins,
            supports_credentials=settings.cors_allow_credentials,
            max_age=settings.cors_max_age,
            allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
            expose_headers=["X-Request-ID", "X-Response-Time"],
        )
        logger.debug(
            "CORS initialized",
            extra={"origins": settings.cors_origins},
        )


def _register_blueprints(app: Flask) -> None:
    """
    Register application blueprints.

    Args:
        app: Flask application instance.
    """
    # Import here to avoid circular imports
    from .api.routes import register_blueprints

    register_blueprints(app)
    logger.debug("Blueprints registered")


def _register_error_handlers(app: Flask) -> None:
    """
    Register error handlers for the application.

    Args:
        app: Flask application instance.
    """

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException) -> tuple[Response, int]:
        """Handle HTTP exceptions and return JSON response."""
        response = {
            "error": {
                "code": error.code,
                "name": error.name,
                "message": error.description,
            },
            "request_id": getattr(g, "request_id", None),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return jsonify(response), error.code

    @app.errorhandler(Exception)
    def handle_generic_exception(error: Exception) -> tuple[Response, int]:
        """Handle unhandled exceptions and return JSON response."""
        logger.exception(
            "Unhandled exception",
            extra={
                "request_id": getattr(g, "request_id", None),
                "error": str(error),
            },
        )

        # Don't expose internal error details in production
        settings: GatewaySettings = app.config.get("GATEWAY_SETTINGS")
        if settings and settings.debug:
            message = str(error)
        else:
            message = "An internal server error occurred"

        response = {
            "error": {
                "code": 500,
                "name": "Internal Server Error",
                "message": message,
            },
            "request_id": getattr(g, "request_id", None),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return jsonify(response), 500

    @app.errorhandler(400)
    def handle_bad_request(error: HTTPException) -> tuple[Response, int]:
        """Handle 400 Bad Request errors."""
        response = {
            "error": {
                "code": 400,
                "name": "Bad Request",
                "message": error.description or "The request was invalid or malformed",
            },
            "request_id": getattr(g, "request_id", None),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return jsonify(response), 400

    @app.errorhandler(401)
    def handle_unauthorized(error: HTTPException) -> tuple[Response, int]:
        """Handle 401 Unauthorized errors."""
        response = {
            "error": {
                "code": 401,
                "name": "Unauthorized",
                "message": error.description or "Authentication is required",
            },
            "request_id": getattr(g, "request_id", None),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return jsonify(response), 401

    @app.errorhandler(403)
    def handle_forbidden(error: HTTPException) -> tuple[Response, int]:
        """Handle 403 Forbidden errors."""
        response = {
            "error": {
                "code": 403,
                "name": "Forbidden",
                "message": error.description or "You do not have permission to access this resource",
            },
            "request_id": getattr(g, "request_id", None),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return jsonify(response), 403

    @app.errorhandler(404)
    def handle_not_found(error: HTTPException) -> tuple[Response, int]:
        """Handle 404 Not Found errors."""
        response = {
            "error": {
                "code": 404,
                "name": "Not Found",
                "message": error.description or "The requested resource was not found",
            },
            "request_id": getattr(g, "request_id", None),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return jsonify(response), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(
            error: HTTPException) -> tuple[Response, int]:
        """Handle 405 Method Not Allowed errors."""
        response = {
            "error": {
                "code": 405,
                "name": "Method Not Allowed",
                "message": error.description or "The method is not allowed for this resource",
            },
            "request_id": getattr(g, "request_id", None),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return jsonify(response), 405

    @app.errorhandler(429)
    def handle_too_many_requests(error: HTTPException) -> tuple[Response, int]:
        """Handle 429 Too Many Requests errors."""
        response = {
            "error": {
                "code": 429,
                "name": "Too Many Requests",
                "message": error.description or "Rate limit exceeded. Please try again later.",
            },
            "request_id": getattr(g, "request_id", None),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return jsonify(response), 429

    @app.errorhandler(500)
    def handle_internal_error(error: HTTPException) -> tuple[Response, int]:
        """Handle 500 Internal Server Error."""
        response = {
            "error": {
                "code": 500,
                "name": "Internal Server Error",
                "message": "An internal server error occurred",
            },
            "request_id": getattr(g, "request_id", None),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return jsonify(response), 500

    @app.errorhandler(503)
    def handle_service_unavailable(
            error: HTTPException) -> tuple[Response, int]:
        """Handle 503 Service Unavailable errors."""
        response = {
            "error": {
                "code": 503,
                "name": "Service Unavailable",
                "message": error.description or "The service is temporarily unavailable",
            },
            "request_id": getattr(g, "request_id", None),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return jsonify(response), 503

    logger.debug("Error handlers registered")


def _register_middleware(app: Flask, settings: GatewaySettings) -> None:
    """
    Register request/response middleware.

    Args:
        app: Flask application instance.
        settings: Gateway settings.
    """

    @app.before_request
    def before_request() -> None:
        """Execute before each request."""
        # Generate or extract request ID
        g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Record request start time
        g.request_start_time = time.perf_counter()

        # Log request if enabled
        if settings.log_requests:
            log_data = {
                "request_id": g.request_id,
                "method": request.method,
                "path": request.path,
                "remote_addr": request.remote_addr,
                "user_agent": request.headers.get("User-Agent"),
            }

            if settings.log_request_body and request.is_json:
                try:
                    log_data["body"] = request.get_json(silent=True)
                except Exception:
                    pass

            logger.info("Request received", extra=log_data)

    @app.after_request
    def after_request(response: Response) -> Response:
        """Execute after each request."""
        # Calculate response time
        request_start_time = getattr(g, "request_start_time", None)
        if request_start_time:
            response_time_ms = (time.perf_counter() -
                                request_start_time) * 1000
            response.headers["X-Response-Time"] = f"{response_time_ms:.2f}ms"
        else:
            response_time_ms = 0

        # Add request ID to response
        request_id = getattr(g, "request_id", None)
        if request_id:
            response.headers["X-Request-ID"] = request_id

        # Log response if enabled
        if settings.log_requests:
            log_data = {
                "request_id": request_id,
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "response_time_ms": round(response_time_ms, 2),
                "content_length": response.content_length,
            }

            if settings.log_response_body and response.is_json:
                try:
                    log_data["body"] = response.get_json(silent=True)
                except Exception:
                    pass

            # Use appropriate log level based on status code
            if response.status_code >= 500:
                logger.error("Request completed", extra=log_data)
            elif response.status_code >= 400:
                logger.warning("Request completed", extra=log_data)
            else:
                logger.info("Request completed", extra=log_data)

        return response

    logger.debug("Middleware registered")


def _register_health_check(app: Flask) -> None:
    """
    Register health check endpoint.

    Args:
        app: Flask application instance.
    """

    @app.route("/health", methods=["GET"])
    def health_check() -> tuple[Response, int]:
        """
        Health check endpoint.

        Returns basic health status of the gateway service.
        """
        response = {
            "status": "healthy",
            "service": "unitmail-gateway",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
        }
        return jsonify(response), 200

    @app.route("/health/ready", methods=["GET"])
    def readiness_check() -> tuple[Response, int]:
        """
        Readiness check endpoint.

        Returns whether the service is ready to accept traffic.
        Can be extended to check database connectivity, etc.
        """
        # TODO: Add checks for database, external services, etc.
        checks = {
            "gateway": True,
        }

        all_healthy = all(checks.values())
        status = "ready" if all_healthy else "not_ready"
        status_code = 200 if all_healthy else 503

        response = {
            "status": status,
            "checks": checks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return jsonify(response), status_code

    @app.route("/health/live", methods=["GET"])
    def liveness_check() -> tuple[Response, int]:
        """
        Liveness check endpoint.

        Returns whether the service is alive and should not be restarted.
        """
        response = {
            "status": "alive",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return jsonify(response), 200

    logger.debug("Health check endpoints registered")
