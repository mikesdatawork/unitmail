"""
Authentication routes for unitMail Gateway API.

This module provides endpoints for user authentication including login,
logout, token refresh, current user info, and password management.
Uses SQLite for storage.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

import jwt
from flask import Blueprint, Response, g, jsonify, request
from pydantic import BaseModel, EmailStr, Field, ValidationError

from common.storage import get_storage
from common.exceptions import (
    TokenExpiredError,
    TokenInvalidError,
)
from ..middleware import rate_limit

# Configure module logger
logger = logging.getLogger(__name__)

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])

# JWT Configuration
JWT_SECRET_KEY = "change-me-in-production"  # Should be loaded from config
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)


# =============================================================================
# Request/Response Models
# =============================================================================


class LoginRequest(BaseModel):
    """Login request model."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")
    remember_me: bool = Field(default=False, description="Extended session")


class PasswordChangeRequest(BaseModel):
    """Password change request model."""

    current_password: str = Field(..., min_length=1,
                                  description="Current password")
    new_password: str = Field(
        ..., min_length=8, max_length=128, description="New password"
    )
    confirm_password: str = Field(..., description="Confirm new password")


class RefreshTokenRequest(BaseModel):
    """Token refresh request model."""

    refresh_token: str = Field(..., description="Refresh token")


# =============================================================================
# Authentication Helpers
# =============================================================================


def hash_password(
        password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """
    Hash a password using PBKDF2.

    Args:
        password: Plain text password.
        salt: Optional salt. If not provided, one will be generated.

    Returns:
        Tuple of (password_hash, salt).
    """
    if salt is None:
        salt = secrets.token_hex(32)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    ).hex()

    return password_hash, salt


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verify a password against a stored hash.

    The stored hash is expected to be in format: salt$hash

    Args:
        password: Plain text password to verify.
        stored_hash: Stored password hash.

    Returns:
        True if password matches.
    """
    try:
        if not stored_hash:
            return False

        if "$" in stored_hash:
            salt, hash_value = stored_hash.split("$", 1)
        else:
            # Legacy format - just the hash
            return False

        computed_hash, _ = hash_password(password, salt)
        return secrets.compare_digest(computed_hash, hash_value)
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: User's unique identifier.
        email: User's email address.

    Returns:
        JWT access token string.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "iat": now,
        "exp": now + JWT_ACCESS_TOKEN_EXPIRES,
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """
    Create a JWT refresh token.

    Args:
        user_id: User's unique identifier.

    Returns:
        JWT refresh token string.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + JWT_REFRESH_TOKEN_EXPIRES,
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str, token_type: str = "access") -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string.
        token_type: Expected token type (access or refresh).

    Returns:
        Decoded token payload.

    Raises:
        TokenExpiredError: If token has expired.
        TokenInvalidError: If token is invalid.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

        # Check token type
        if payload.get("type") != token_type:
            raise TokenInvalidError(details={"reason": "Invalid token type"})

        # Check if token is blacklisted (using SQLite storage)
        jti = payload.get("jti")
        if jti:
            storage = get_storage()
            if storage.is_token_blacklisted(jti):
                raise TokenInvalidError(
                    details={"reason": "Token has been revoked"})

        return payload

    except jwt.ExpiredSignatureError:
        raise TokenExpiredError()
    except jwt.InvalidTokenError as e:
        raise TokenInvalidError(details={"reason": str(e)})


def blacklist_token(token: str) -> None:
    """
    Add a token to the blacklist.

    Args:
        token: JWT token string.
    """
    try:
        payload = jwt.decode(
            token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM],
            options={"verify_exp": False}
        )
        jti = payload.get("jti")
        exp = payload.get("exp")

        if jti:
            storage = get_storage()
            # Convert exp timestamp to datetime
            expires_at = None
            if exp:
                expires_at = datetime.fromtimestamp(
                    exp, tz=timezone.utc).isoformat()
            storage.add_to_blacklist(jti, expires_at)
    except Exception:
        pass


def require_auth(f: F) -> F:
    """
    Decorator to require authentication for a route.

    Extracts and validates the JWT token from the Authorization header.
    Sets g.current_user_id, g.user_id, and g.current_user_email on success.

    Args:
        f: Function to decorate.

    Returns:
        Decorated function.
    """
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return jsonify({
                "error": "Authorization required",
                "message": "Missing Authorization header",
            }), 401

        # Extract token from "Bearer <token>" format
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({
                "error": "Invalid authorization",
                "message": "Authorization header must be 'Bearer <token>'",
            }), 401

        token = parts[1]

        try:
            payload = decode_token(token, "access")
            g.current_user_id = payload["sub"]
            g.user_id = payload["sub"]  # Also set user_id for consistency
            g.current_user_email = payload.get("email")
            g.token_jti = payload.get("jti")

        except TokenExpiredError:
            return jsonify({
                "error": "Token expired",
                "message": "Access token has expired. Please refresh or login again.",
            }), 401

        except TokenInvalidError as e:
            return jsonify({
                "error": "Invalid token",
                "message": str(e.message),
            }), 401

        return f(*args, **kwargs)

    return decorated  # type: ignore


# =============================================================================
# Blueprint and Routes
# =============================================================================


def create_auth_blueprint() -> Blueprint:
    """
    Create the authentication blueprint.

    Returns:
        Blueprint for authentication routes.
    """
    bp = Blueprint("auth", __name__, url_prefix="/auth")

    @bp.route("/login", methods=["POST"])
    # Stricter rate limit for login
    @rate_limit(max_requests=10, window_seconds=60)
    def login() -> tuple[Response, int]:
        """
        Authenticate user with email and password.

        Returns JWT access and refresh tokens on success.

        Request Body:
            - email: User's email address
            - password: User's password
            - remember_me: Optional, extend session duration

        Returns:
            JSON with access_token, refresh_token, and user info.
        """
        if not request.is_json:
            return jsonify({
                "error": "Invalid request",
                "message": "Request must be JSON",
            }), 400

        try:
            data = LoginRequest(**request.get_json())
        except ValidationError as e:
            return jsonify({
                "error": "Validation error",
                "message": "Invalid request data",
                "details": e.errors(),
            }), 400

        try:
            storage = get_storage()
            user = storage.get_user_by_email(str(data.email))

            if not user:
                logger.warning(
                    "Login attempt for non-existent user",
                    extra={"email": str(data.email)},
                )
                return jsonify({
                    "error": "Authentication failed",
                    "message": "Invalid email or password",
                }), 401

            # Verify password
            if not verify_password(
                    data.password, user.get("password_hash", "")):
                logger.warning(
                    "Login attempt with invalid password",
                    extra={"user_id": user["id"]},
                )
                return jsonify({
                    "error": "Authentication failed",
                    "message": "Invalid email or password",
                }), 401

            # Check if user is active
            if not user.get("is_active", True):
                return jsonify({
                    "error": "Account disabled",
                    "message": "Your account has been disabled. Please contact support.",
                }), 403

            # Create tokens
            access_token = create_access_token(user["id"], user["email"])
            refresh_token = create_refresh_token(user["id"])

            # Update last login
            storage.update_user_last_login(user["id"])

            logger.info(
                "User logged in successfully",
                extra={"user_id": user["id"]},
            )

            return jsonify({
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "expires_in": int(JWT_ACCESS_TOKEN_EXPIRES.total_seconds()),
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "username": user.get("username"),
                    "display_name": user.get("display_name"),
                    "is_verified": user.get("is_verified", False),
                },
            }), 200

        except Exception as e:
            logger.error(f"Login error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred during authentication",
            }), 500

    @bp.route("/logout", methods=["POST"])
    @require_auth
    def logout() -> tuple[Response, int]:
        """
        Invalidate the current access token.

        Optionally invalidate the refresh token as well.

        Request Body (optional):
            - refresh_token: Refresh token to invalidate

        Returns:
            Success message.
        """
        # Get the current token from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            access_token = auth_header[7:]
            blacklist_token(access_token)

        # Also blacklist refresh token if provided
        data = request.get_json(silent=True) or {}
        refresh_token = data.get("refresh_token")
        if refresh_token:
            blacklist_token(refresh_token)

        logger.info(
            "User logged out",
            extra={"user_id": g.current_user_id},
        )

        return jsonify({
            "message": "Successfully logged out",
        }), 200

    @bp.route("/refresh", methods=["POST"])
    @rate_limit(max_requests=20, window_seconds=60)
    def refresh_token() -> tuple[Response, int]:
        """
        Refresh the access token using a refresh token.

        Request Body:
            - refresh_token: Valid refresh token

        Returns:
            New access_token and refresh_token.
        """
        if not request.is_json:
            return jsonify({
                "error": "Invalid request",
                "message": "Request must be JSON",
            }), 400

        try:
            data = RefreshTokenRequest(**request.get_json())
        except ValidationError as e:
            return jsonify({
                "error": "Validation error",
                "message": "Invalid request data",
                "details": e.errors(),
            }), 400

        try:
            # Validate refresh token
            payload = decode_token(data.refresh_token, "refresh")
            user_id = payload["sub"]

            # Get user to verify they still exist and are active
            storage = get_storage()
            user = storage.get_user_by_id(user_id)

            if not user:
                return jsonify({
                    "error": "User not found",
                    "message": "User associated with token no longer exists.",
                }), 401

            if not user.get("is_active", True):
                return jsonify({
                    "error": "Account disabled",
                    "message": "Your account has been disabled.",
                }), 403

            # Blacklist old refresh token (rotation)
            blacklist_token(data.refresh_token)

            # Create new tokens
            access_token = create_access_token(user["id"], user["email"])
            new_refresh_token = create_refresh_token(user["id"])

            logger.info(
                "Token refreshed",
                extra={"user_id": user_id},
            )

            return jsonify({
                "access_token": access_token,
                "refresh_token": new_refresh_token,
                "token_type": "Bearer",
                "expires_in": int(JWT_ACCESS_TOKEN_EXPIRES.total_seconds()),
            }), 200

        except TokenExpiredError:
            return jsonify({
                "error": "Token expired",
                "message": "Refresh token has expired. Please login again.",
            }), 401

        except TokenInvalidError as e:
            return jsonify({
                "error": "Invalid token",
                "message": str(e.message),
            }), 401

        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred during token refresh",
            }), 500

    @bp.route("/me", methods=["GET"])
    @require_auth
    def get_current_user() -> tuple[Response, int]:
        """
        Get information about the currently authenticated user.

        Returns:
            User profile information.
        """
        try:
            storage = get_storage()
            user = storage.get_user_by_id(g.current_user_id)

            if not user:
                return jsonify({
                    "error": "User not found",
                    "message": "User no longer exists",
                }), 404

            return jsonify({
                "id": user["id"],
                "email": user["email"],
                "username": user.get("username"),
                "display_name": user.get("display_name"),
                "is_active": user.get("is_active", True),
                "is_verified": user.get("is_verified", False),
                "last_login": user.get("last_login"),
                "created_at": user.get("created_at"),
                "settings": user.get("settings", {}),
            }), 200

        except Exception as e:
            logger.error(f"Get current user error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while fetching user info",
            }), 500

    @bp.route("/password", methods=["POST"])
    @require_auth
    @rate_limit(max_requests=5, window_seconds=60)  # Very strict rate limit
    def change_password() -> tuple[Response, int]:
        """
        Change the current user's password.

        Request Body:
            - current_password: Current password for verification
            - new_password: New password (min 8 characters)
            - confirm_password: Must match new_password

        Returns:
            Success message.
        """
        if not request.is_json:
            return jsonify({
                "error": "Invalid request",
                "message": "Request must be JSON",
            }), 400

        try:
            data = PasswordChangeRequest(**request.get_json())
        except ValidationError as e:
            return jsonify({
                "error": "Validation error",
                "message": "Invalid request data",
                "details": e.errors(),
            }), 400

        # Verify passwords match
        if data.new_password != data.confirm_password:
            return jsonify({
                "error": "Validation error",
                "message": "New password and confirmation do not match",
            }), 400

        # Check password strength (basic check)
        if len(data.new_password) < 8:
            return jsonify({
                "error": "Validation error",
                "message": "Password must be at least 8 characters long",
            }), 400

        try:
            storage = get_storage()
            user = storage.get_user_by_id(g.current_user_id)

            if not user:
                return jsonify({
                    "error": "User not found",
                    "message": "User no longer exists",
                }), 404

            # Verify current password
            if not verify_password(data.current_password,
                                   user.get("password_hash", "")):
                return jsonify({
                    "error": "Authentication failed",
                    "message": "Current password is incorrect",
                }), 401

            # Hash new password
            new_hash, salt = hash_password(data.new_password)
            password_hash = f"{salt}${new_hash}"

            # Update password
            storage.update_user(user["id"], {"password_hash": password_hash})

            logger.info(
                "User changed password",
                extra={"user_id": user["id"]},
            )

            return jsonify({
                "message": "Password changed successfully",
            }), 200

        except Exception as e:
            logger.error(f"Password change error: {e}")
            return jsonify({
                "error": "Server error",
                "message": "An error occurred while changing password",
            }), 500

    return bp


# Export public components
__all__ = [
    "create_auth_blueprint",
    "require_auth",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_password",
    "verify_password",
]
