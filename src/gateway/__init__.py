"""
unitMail Gateway service.

This package provides the HTTP/WebSocket gateway for the unitMail application,
handling API requests, authentication, and real-time updates.
"""

from .app import create_app
from .config import GatewaySettings, get_gateway_settings, reload_gateway_settings

__all__ = [
    "create_app",
    "GatewaySettings",
    "get_gateway_settings",
    "reload_gateway_settings",
]

__version__ = "1.0.0"
