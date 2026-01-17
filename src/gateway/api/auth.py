"""
JWT Authentication system for unitMail Gateway API.

This module provides JWT token management, password hashing, and authentication
decorators for securing API endpoints. Uses SQLite for token blacklist storage.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, Optional, TypeVar
from uuid import UUID

import bcrypt
import jwt
from flask import abort, g, request

from common.config import get_settings
from common.storage import EmailStorage, get_storage
from common.exceptions import (
    AuthenticationError,
    TokenExpiredError,
    TokenInvalidError,
)

# Configure module logger
logger = logging.getLogger(__name__)

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# JWT Token Manager
# =============================================================================


class JWTManager:
    """
    JWT token management class.

    Handles token generation, verification, and revocation with SQLite
    backend for blacklist storage.

    Attributes:
        secret: JWT signing secret.
        algorithm: JWT signing algorithm.
        access_token_expiry: Access token expiration time in seconds.
        refresh_token_expiry: Refresh token expiration time in seconds.
    """

    # Token type identifiers
    TOKEN_TYPE_ACCESS = "access"
    TOKEN_TYPE_REFRESH = "refresh"

    def __init__(
        self,
        secret: Optional[str] = None,
        algorithm: Optional[str] = None,
        access_token_expiry: Optional[int] = None,
        refresh_token_expiry: Optional[int] = None,
        storage: Optional[EmailStorage] = None,
    ) -> None:
        """
        Initialize the JWT manager.

        Args:
            secret: JWT signing secret. If not provided, loaded from settings.
            algorithm: JWT algorithm. If not provided, loaded from settings.
            access_token_expiry: Access token expiry in seconds.
            refresh_token_expiry: Refresh token expiry in seconds.
            storage: EmailStorage instance. If not provided, uses default.
        """
        settings = get_settings()

        self.secret = secret or settings.api.jwt_secret
        self.algorithm = algorithm or settings.api.jwt_algorithm
        self.access_token_expiry = access_token_expiry or settings.api.jwt_expiration
        # Refresh tokens last 7 days by default
        self.refresh_token_expiry = refresh_token_expiry or (7 * 24 * 3600)

        # SQLite storage for blacklist
        self._storage = storage or get_storage()

        # Validate secret in production
        if settings.environment == "production" and self.secret == "change-me-in-production":
            logger.warning("JWT secret is using default value in production!")

        logger.debug(
            "JWTManager initialized",
            extra={
                "algorithm": self.algorithm,
                "access_token_expiry": self.access_token_expiry,
                "refresh_token_expiry": self.refresh_token_expiry,
            },
        )

    def generate_token(
        self,
        user_id: str | UUID,
        expires_in: Optional[int] = None,
        additional_claims: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Generate a JWT access token.

        Args:
            user_id: The user's unique identifier.
            expires_in: Optional custom expiration time in seconds.
            additional_claims: Optional additional claims to include in the token.

        Returns:
            Encoded JWT access token string.
        """
        now = datetime.now(timezone.utc)
        expiry = expires_in or self.access_token_expiry

        payload = {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(seconds=expiry),
            "type": self.TOKEN_TYPE_ACCESS,
            "jti": secrets.token_hex(16),  # Unique token ID
        }

        # Add any additional claims
        if additional_claims:
            payload.update(additional_claims)

        token = jwt.encode(payload, self.secret, algorithm=self.algorithm)

        logger.debug(
            "Access token generated",
            extra={
                "user_id": str(user_id),
                "expires_in": expiry,
                "jti": payload["jti"],
            },
        )

        return token

    def generate_refresh_token(
        self,
        user_id: str | UUID,
        additional_claims: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Generate a JWT refresh token.

        Refresh tokens have a longer expiration and can be used to obtain
        new access tokens.

        Args:
            user_id: The user's unique identifier.
            additional_claims: Optional additional claims to include in the token.

        Returns:
            Encoded JWT refresh token string.
        """
        now = datetime.now(timezone.utc)

        payload = {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(seconds=self.refresh_token_expiry),
            "type": self.TOKEN_TYPE_REFRESH,
            "jti": secrets.token_hex(16),  # Unique token ID
        }

        # Add any additional claims
        if additional_claims:
            payload.update(additional_claims)

        token = jwt.encode(payload, self.secret, algorithm=self.algorithm)

        logger.debug(
            "Refresh token generated",
            extra={
                "user_id": str(user_id),
                "expires_in": self.refresh_token_expiry,
                "jti": payload["jti"],
            },
        )

        return token

    def verify_token(
        self,
        token: str,
        expected_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Verify and decode a JWT token.

        Args:
            token: The JWT token string to verify.
            expected_type: Optional expected token type (access/refresh).

        Returns:
            Decoded token payload as a dictionary.

        Raises:
            TokenExpiredError: If the token has expired.
            TokenInvalidError: If the token is invalid or tampered with.
        """
        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                options={"require": ["sub", "exp", "iat", "type", "jti"]},
            )

            # Check token type if specified
            if expected_type and payload.get("type") != expected_type:
                raise TokenInvalidError(
                    details={"reason": f"Expected {expected_type} token, got {payload.get('type')}"}
                )

            # Check if token is revoked
            if self.is_revoked(token):
                raise TokenInvalidError(details={"reason": "Token has been revoked"})

            logger.debug(
                "Token verified",
                extra={
                    "user_id": payload.get("sub"),
                    "type": payload.get("type"),
                    "jti": payload.get("jti"),
                },
            )

            return payload

        except jwt.ExpiredSignatureError:
            logger.debug("Token expired")
            raise TokenExpiredError()
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise TokenInvalidError(details={"reason": str(e)})

    def revoke_token(self, token: str) -> bool:
        """
        Revoke a token by adding it to the blacklist.

        The token's JTI (JWT ID) is stored in the database along with
        its expiration time for cleanup purposes.

        Args:
            token: The JWT token string to revoke.

        Returns:
            True if the token was successfully revoked.
        """
        try:
            # Decode without verification to get the jti (token might be expired)
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                options={"verify_exp": False},
            )

            jti = payload.get("jti")
            exp = payload.get("exp")
            user_id = payload.get("sub")

            if not jti:
                logger.warning("Cannot revoke token without jti")
                return False

            # Convert expiration timestamp to ISO format
            expires_at = None
            if exp:
                expires_at = datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()

            # Add to SQLite blacklist
            result = self._storage.add_to_blacklist(
                jti=jti,
                user_id=user_id,
                expires_at=expires_at,
            )

            if result:
                logger.info(
                    "Token revoked",
                    extra={
                        "jti": jti,
                        "user_id": user_id,
                    },
                )

            return result

        except jwt.InvalidTokenError as e:
            logger.warning(f"Cannot revoke invalid token: {e}")
            return False

    def is_revoked(self, token: str) -> bool:
        """
        Check if a token has been revoked.

        Args:
            token: The JWT token string to check.

        Returns:
            True if the token is in the blacklist, False otherwise.
        """
        try:
            # Decode without verification to get the jti
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                options={"verify_exp": False},
            )

            jti = payload.get("jti")
            if not jti:
                return False

            # Check SQLite blacklist
            return self._storage.is_token_blacklisted(jti)

        except jwt.InvalidTokenError:
            # Invalid tokens are effectively revoked
            return True

    def get_token_from_request(self) -> Optional[str]:
        """
        Extract JWT token from the current request.

        Checks the Authorization header for a Bearer token.

        Returns:
            The token string if found, None otherwise.
        """
        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove "Bearer " prefix

        return None

    def cleanup_expired_blacklist(self) -> int:
        """
        Remove expired tokens from the blacklist.

        This should be run periodically to prevent the blacklist from
        growing indefinitely.

        Returns:
            Number of expired entries removed.
        """
        count = self._storage.cleanup_expired_blacklist()

        if count > 0:
            logger.info(f"Cleaned up {count} expired blacklist entries")

        return count


# =============================================================================
# Password Hashing
# =============================================================================


def hash_password(password: str, rounds: int = 12) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: The plaintext password to hash.
        rounds: The bcrypt cost factor (default: 12).

    Returns:
        The bcrypt password hash as a string.

    Raises:
        ValueError: If the password is empty or too long.
    """
    if not password:
        raise ValueError("Password cannot be empty")

    # bcrypt has a max length of 72 bytes
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password exceeds maximum length of 72 bytes")

    # Generate salt and hash
    salt = bcrypt.gensalt(rounds=rounds)
    password_hash = bcrypt.hashpw(password.encode("utf-8"), salt)

    logger.debug("Password hashed successfully")

    return password_hash.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against a bcrypt hash.

    Args:
        password: The plaintext password to verify.
        password_hash: The bcrypt hash to verify against.

    Returns:
        True if the password matches, False otherwise.
    """
    if not password or not password_hash:
        return False

    try:
        result = bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )

        if result:
            logger.debug("Password verified successfully")
        else:
            logger.debug("Password verification failed")

        return result

    except (ValueError, TypeError) as e:
        logger.warning(f"Password verification error: {e}")
        return False


# =============================================================================
# Authentication Decorators
# =============================================================================


# Global JWT manager instance
_jwt_manager: Optional[JWTManager] = None


def get_jwt_manager() -> JWTManager:
    """
    Get or create the global JWT manager instance.

    Returns:
        JWTManager instance.
    """
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = JWTManager()
    return _jwt_manager


def require_auth(f: F) -> F:
    """
    Decorator that requires a valid JWT token for the endpoint.

    Extracts the token from the Authorization header, verifies it,
    and loads the user information into Flask's g object.

    Usage:
        @app.route("/protected")
        @require_auth
        def protected_route():
            user_id = g.user_id
            return f"Hello, user {user_id}!"

    Raises:
        401 Unauthorized: If no token is provided or token is invalid.
    """
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        jwt_manager = get_jwt_manager()
        token = jwt_manager.get_token_from_request()

        if not token:
            logger.debug("No authorization token provided")
            abort(401, description="Authorization token is required")

        try:
            payload = jwt_manager.verify_token(token, expected_type=JWTManager.TOKEN_TYPE_ACCESS)

            # Store user info in Flask's g object
            g.user_id = payload.get("sub")
            g.token_payload = payload
            g.is_admin = payload.get("is_admin", False)

            logger.debug(
                "Request authenticated",
                extra={
                    "user_id": g.user_id,
                    "request_id": getattr(g, "request_id", None),
                },
            )

            return f(*args, **kwargs)

        except TokenExpiredError:
            abort(401, description="Token has expired")
        except TokenInvalidError as e:
            abort(401, description=f"Invalid token: {e.details.get('reason', 'Unknown error')}")
        except AuthenticationError as e:
            abort(401, description=str(e.message))

    return wrapper  # type: ignore


def require_admin(f: F) -> F:
    """
    Decorator that requires admin role for the endpoint.

    Must be used after @require_auth decorator.

    Usage:
        @app.route("/admin")
        @require_auth
        @require_admin
        def admin_route():
            return "Admin only!"

    Raises:
        401 Unauthorized: If no valid token is provided.
        403 Forbidden: If user is not an admin.
    """
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Check if user is authenticated
        if not hasattr(g, "user_id") or not g.user_id:
            abort(401, description="Authentication required")

        # Check if user is admin
        is_admin = getattr(g, "is_admin", False)

        if not is_admin:
            logger.warning(
                "Non-admin user attempted admin action",
                extra={
                    "user_id": g.user_id,
                    "request_id": getattr(g, "request_id", None),
                    "path": request.path,
                },
            )
            abort(403, description="Admin access required")

        return f(*args, **kwargs)

    return wrapper  # type: ignore


def optional_auth(f: F) -> F:
    """
    Decorator that optionally loads user information if a token is present.

    Unlike @require_auth, this does not fail if no token is provided.
    The user info is loaded into g if available.

    Usage:
        @app.route("/public")
        @optional_auth
        def public_route():
            if g.user_id:
                return f"Hello, user {g.user_id}!"
            return "Hello, anonymous!"
    """
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Set defaults
        g.user_id = None
        g.token_payload = None
        g.is_admin = False

        jwt_manager = get_jwt_manager()
        token = jwt_manager.get_token_from_request()

        if token:
            try:
                payload = jwt_manager.verify_token(token, expected_type=JWTManager.TOKEN_TYPE_ACCESS)

                g.user_id = payload.get("sub")
                g.token_payload = payload
                g.is_admin = payload.get("is_admin", False)

                logger.debug(
                    "Optional auth: user authenticated",
                    extra={
                        "user_id": g.user_id,
                        "request_id": getattr(g, "request_id", None),
                    },
                )

            except (TokenExpiredError, TokenInvalidError, AuthenticationError) as e:
                # Log but don't fail - authentication is optional
                logger.debug(f"Optional auth: token invalid - {e}")

        return f(*args, **kwargs)

    return wrapper  # type: ignore


# =============================================================================
# Token Response Helpers
# =============================================================================


def create_token_response(
    user_id: str | UUID,
    include_refresh: bool = True,
    additional_claims: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Create a complete token response with access and optional refresh tokens.

    Args:
        user_id: The user's unique identifier.
        include_refresh: Whether to include a refresh token.
        additional_claims: Optional additional claims for the tokens.

    Returns:
        Dictionary with token response data.
    """
    jwt_manager = get_jwt_manager()

    access_token = jwt_manager.generate_token(user_id, additional_claims=additional_claims)

    response = {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": jwt_manager.access_token_expiry,
    }

    if include_refresh:
        refresh_token = jwt_manager.generate_refresh_token(user_id, additional_claims=additional_claims)
        response["refresh_token"] = refresh_token
        response["refresh_expires_in"] = jwt_manager.refresh_token_expiry

    return response


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    # JWT Manager
    "JWTManager",
    "get_jwt_manager",
    # Password hashing
    "hash_password",
    "verify_password",
    # Decorators
    "require_auth",
    "require_admin",
    "optional_auth",
    # Helpers
    "create_token_response",
]
