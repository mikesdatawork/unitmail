"""
unitMail Gateway API package.

This package contains the API server, routes, middleware, and authentication
for the Gateway service.
"""

from .server import GatewayServer, create_server
from .middleware import (
    InMemoryRateLimiter,
    RedisRateLimiter,
    RequestValidator,
    MetricsCollector,
    get_rate_limiter,
    get_metrics_collector,
    rate_limit,
    validate_content_type,
    register_middleware,
)
from .auth import (
    JWTManager,
    get_jwt_manager,
    hash_password,
    verify_password,
    require_auth,
    require_admin,
    optional_auth,
    create_token_response,
)
from .schemas import (
    # Auth schemas
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    # User schemas
    UserResponse,
    UserCreateRequest,
    UserUpdateRequest,
    # Message schemas
    MessageListRequest,
    MessageResponse,
    MessageCreateRequest,
    MessageUpdateRequest,
    # Contact schemas
    ContactRequest,
    ContactResponse,
    ContactListRequest,
    # Folder schemas
    FolderRequest,
    FolderResponse,
    FolderUpdateRequest,
    # Error schemas
    ErrorResponse,
    ErrorDetail,
    # Pagination
    PaginatedResponse,
    # Success
    SuccessResponse,
)

__all__ = [
    # Server
    "GatewayServer",
    "create_server",
    # Rate limiting
    "InMemoryRateLimiter",
    "RedisRateLimiter",
    "get_rate_limiter",
    "rate_limit",
    # Validation
    "RequestValidator",
    "validate_content_type",
    # Metrics
    "MetricsCollector",
    "get_metrics_collector",
    # Registration
    "register_middleware",
    # Authentication
    "JWTManager",
    "get_jwt_manager",
    "hash_password",
    "verify_password",
    "require_auth",
    "require_admin",
    "optional_auth",
    "create_token_response",
    # Schemas - Auth
    "LoginRequest",
    "LoginResponse",
    "RefreshRequest",
    "RefreshResponse",
    # Schemas - User
    "UserResponse",
    "UserCreateRequest",
    "UserUpdateRequest",
    # Schemas - Message
    "MessageListRequest",
    "MessageResponse",
    "MessageCreateRequest",
    "MessageUpdateRequest",
    # Schemas - Contact
    "ContactRequest",
    "ContactResponse",
    "ContactListRequest",
    # Schemas - Folder
    "FolderRequest",
    "FolderResponse",
    "FolderUpdateRequest",
    # Schemas - Error
    "ErrorResponse",
    "ErrorDetail",
    # Schemas - Pagination
    "PaginatedResponse",
    # Schemas - Success
    "SuccessResponse",
]
