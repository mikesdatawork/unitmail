"""
Main API server for unitMail Gateway service.

This module provides the main server class that manages the Flask application
lifecycle, including WebSocket support and graceful shutdown handling.
"""

import logging
import signal
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from flask import Flask
from flask_socketio import SocketIO, emit, join_room, leave_room

from ..app import create_app
from ..config import GatewaySettings, get_gateway_settings

# Configure module logger
logger = logging.getLogger(__name__)


class GatewayServer:
    """
    Main Gateway API server class.

    This class manages the Flask application lifecycle, including WebSocket
    support via Flask-SocketIO and graceful shutdown handling.

    Attributes:
        app: Flask application instance.
        socketio: SocketIO instance for WebSocket support.
        settings: Gateway configuration settings.
        is_running: Flag indicating if the server is running.
    """

    def __init__(
        self,
        settings: Optional[GatewaySettings] = None,
        app: Optional[Flask] = None,
    ) -> None:
        """
        Initialize the Gateway server.

        Args:
            settings: Optional GatewaySettings instance. If not provided,
                     settings will be loaded from environment variables.
            app: Optional Flask application instance. If not provided,
                 a new application will be created.
        """
        self.settings = settings or get_gateway_settings()
        self.app = app or create_app(self.settings)
        self.socketio: Optional[SocketIO] = None
        self.is_running = False
        self._shutdown_event = threading.Event()

        # Initialize WebSocket if enabled
        if self.settings.websocket_enabled:
            self._init_websocket()

        # Register signal handlers
        self._register_signal_handlers()

        logger.info(
            "Gateway server initialized",
            extra={
                "host": self.settings.host,
                "port": self.settings.port,
                "websocket_enabled": self.settings.websocket_enabled,
            },
        )

    def _init_websocket(self) -> None:
        """Initialize WebSocket support using Flask-SocketIO."""
        # Determine async mode based on available libraries
        async_mode = "threading"

        try:
            async_mode = "eventlet"
        except ImportError:
            try:
                async_mode = "gevent"
            except ImportError:
                pass

        self.socketio = SocketIO(
            self.app,
            cors_allowed_origins=self.settings.cors_origins if self.settings.cors_enabled else "*",
            ping_interval=self.settings.websocket_ping_interval,
            ping_timeout=self.settings.websocket_ping_timeout,
            async_mode=async_mode,
            logger=logger.isEnabledFor(logging.DEBUG),
            engineio_logger=logger.isEnabledFor(logging.DEBUG),
        )

        # Register WebSocket event handlers
        self._register_websocket_handlers()

        logger.debug(
            "WebSocket initialized",
            extra={"async_mode": async_mode},
        )

    def _register_websocket_handlers(self) -> None:
        """Register WebSocket event handlers."""
        if not self.socketio:
            return

        @self.socketio.on("connect")
        def handle_connect() -> None:
            """Handle client connection."""
            logger.debug("WebSocket client connected")
            emit("connected", {
                "status": "connected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        @self.socketio.on("disconnect")
        def handle_disconnect() -> None:
            """Handle client disconnection."""
            logger.debug("WebSocket client disconnected")

        @self.socketio.on("subscribe")
        def handle_subscribe(data: dict[str, Any]) -> None:
            """
            Handle subscription to a channel/room.

            Expected data format: {"channel": "channel_name"}
            """
            channel = data.get("channel")
            if channel:
                join_room(channel)
                logger.debug(f"Client subscribed to channel: {channel}")
                emit("subscribed", {
                    "channel": channel,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            else:
                emit("error", {
                    "message": "Channel name is required",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        @self.socketio.on("unsubscribe")
        def handle_unsubscribe(data: dict[str, Any]) -> None:
            """
            Handle unsubscription from a channel/room.

            Expected data format: {"channel": "channel_name"}
            """
            channel = data.get("channel")
            if channel:
                leave_room(channel)
                logger.debug(f"Client unsubscribed from channel: {channel}")
                emit("unsubscribed", {
                    "channel": channel,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            else:
                emit("error", {
                    "message": "Channel name is required",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        @self.socketio.on("ping")
        def handle_ping() -> None:
            """Handle ping message from client."""
            emit("pong", {
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        @self.socketio.on_error_default
        def handle_error(error: Exception) -> None:
            """Handle WebSocket errors."""
            logger.exception("WebSocket error", exc_info=error)
            emit("error", {
                "message": "An error occurred",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    def _register_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown."""
        # Only register signal handlers in the main thread
        if threading.current_thread() is not threading.main_thread():
            return

        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)

        logger.debug("Signal handlers registered")

    def _handle_shutdown_signal(self, signum: int, frame: Any) -> None:
        """
        Handle shutdown signals (SIGTERM, SIGINT).

        Args:
            signum: Signal number.
            frame: Current stack frame.
        """
        signal_name = signal.Signals(signum).name
        logger.info(f"Received shutdown signal: {signal_name}")
        self.shutdown()

    def emit_event(
        self,
        event: str,
        data: dict[str, Any],
        room: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> None:
        """
        Emit a WebSocket event to connected clients.

        Args:
            event: Event name.
            data: Event data to send.
            room: Optional room/channel to send to. If None, broadcasts to all.
            namespace: Optional namespace. Defaults to root namespace.
        """
        if not self.socketio:
            logger.warning("WebSocket not initialized, cannot emit event")
            return

        # Add timestamp to event data
        data["timestamp"] = datetime.now(timezone.utc).isoformat()

        if room:
            self.socketio.emit(event, data, room=room, namespace=namespace)
        else:
            self.socketio.emit(event, data, namespace=namespace)

        logger.debug(
            "Event emitted",
            extra={"event": event, "room": room},
        )

    def run(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        debug: Optional[bool] = None,
    ) -> None:
        """
        Start the Gateway server.

        Args:
            host: Override host from settings.
            port: Override port from settings.
            debug: Override debug mode from settings.
        """
        host = host or self.settings.host
        port = port or self.settings.port
        debug = debug if debug is not None else self.settings.debug

        self.is_running = True

        logger.info(
            "Starting Gateway server",
            extra={
                "host": host,
                "port": port,
                "debug": debug,
                "websocket_enabled": self.settings.websocket_enabled,
            },
        )

        try:
            if self.socketio:
                # Run with WebSocket support
                self.socketio.run(
                    self.app,
                    host=host,
                    port=port,
                    debug=debug,
                    use_reloader=debug,
                    log_output=debug,
                )
            else:
                # Run without WebSocket support
                self.app.run(
                    host=host,
                    port=port,
                    debug=debug,
                    use_reloader=debug,
                    threaded=True,
                )
        except Exception as e:
            logger.exception("Error running Gateway server", exc_info=e)
            raise
        finally:
            self.is_running = False

    def shutdown(self, timeout: float = 30.0) -> None:
        """
        Gracefully shutdown the server.

        Args:
            timeout: Maximum time to wait for shutdown in seconds.
        """
        if not self.is_running:
            logger.warning("Server is not running")
            return

        logger.info("Initiating graceful shutdown")

        # Set shutdown event
        self._shutdown_event.set()

        # Notify connected WebSocket clients
        if self.socketio:
            self.emit_event("server_shutdown", {
                "message": "Server is shutting down",
            })

        # Stop the SocketIO server if running
        if self.socketio:
            try:
                self.socketio.stop()
            except Exception as e:
                logger.warning(f"Error stopping SocketIO: {e}")

        self.is_running = False
        logger.info("Graceful shutdown completed")

    def wait_for_shutdown(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for the shutdown event.

        Args:
            timeout: Maximum time to wait in seconds. None means wait indefinitely.

        Returns:
            True if shutdown event was set, False if timeout occurred.
        """
        return self._shutdown_event.wait(timeout=timeout)


def create_server(
    settings: Optional[GatewaySettings] = None,
    app: Optional[Flask] = None,
) -> GatewayServer:
    """
    Factory function to create a Gateway server instance.

    Args:
        settings: Optional GatewaySettings instance.
        app: Optional Flask application instance.

    Returns:
        Configured GatewayServer instance.
    """
    return GatewayServer(settings=settings, app=app)
