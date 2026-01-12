#!/usr/bin/env python3
"""
CLI script to start the unitMail Gateway service.

This script provides a command-line interface for starting the Gateway
server with configurable options for host, port, and debug mode.

Usage:
    python run_gateway.py [OPTIONS]

Options:
    --host TEXT     Host address to bind (default: 0.0.0.0)
    --port INTEGER  Port to bind (default: 8080)
    --debug         Enable debug mode
    --no-websocket  Disable WebSocket support
    --config FILE   Path to configuration file
    --help          Show this message and exit
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add the src directory to the Python path
src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))


def setup_logging(debug: bool = False) -> None:
    """
    Configure logging for the Gateway service.

    Args:
        debug: Enable debug logging.
    """
    log_level = logging.DEBUG if debug else logging.INFO
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Set specific loggers
    if not debug:
        # Reduce noise from third-party libraries in non-debug mode
        logging.getLogger("werkzeug").setLevel(logging.WARNING)
        logging.getLogger("engineio").setLevel(logging.WARNING)
        logging.getLogger("socketio").setLevel(logging.WARNING)


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Start the unitMail Gateway service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Start with default settings:
    python run_gateway.py

  Start in debug mode on a custom port:
    python run_gateway.py --debug --port 5000

  Start with a configuration file:
    python run_gateway.py --config /path/to/config.toml

Environment Variables:
  GATEWAY_HOST          Host address to bind
  GATEWAY_PORT          Port to bind
  GATEWAY_DEBUG         Enable debug mode (true/false)
  GATEWAY_SECRET_KEY    Flask secret key
  GATEWAY_REDIS_URL     Redis URL for rate limiting
        """,
    )

    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host address to bind (default: 0.0.0.0 or GATEWAY_HOST)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind (default: 8080 or GATEWAY_PORT)",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        default=None,
        help="Enable debug mode",
    )

    parser.add_argument(
        "--no-debug",
        action="store_true",
        help="Explicitly disable debug mode",
    )

    parser.add_argument(
        "--no-websocket",
        action="store_true",
        help="Disable WebSocket support",
    )

    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to configuration file (TOML format)",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (only for production mode)",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="unitMail Gateway 1.0.0",
    )

    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the Gateway service.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    args = parse_args()

    # Determine debug mode
    if args.no_debug:
        debug = False
    elif args.debug:
        debug = True
    else:
        debug = os.getenv("GATEWAY_DEBUG", "").lower() in ("true", "1", "yes")

    # Setup logging
    setup_logging(debug)
    logger = logging.getLogger(__name__)

    logger.info("Starting unitMail Gateway service")

    try:
        # Set config file path if provided
        if args.config:
            config_path = Path(args.config)
            if not config_path.exists():
                logger.error(f"Configuration file not found: {args.config}")
                return 1
            os.environ["UNITMAIL_CONFIG_FILE"] = str(config_path)
            logger.info(f"Using configuration file: {args.config}")

        # Import gateway modules after path setup
        from gateway.config import GatewaySettings, get_gateway_settings
        from gateway.api.server import GatewayServer

        # Get settings and apply overrides
        settings = get_gateway_settings()

        # Apply CLI overrides
        if args.host:
            settings.host = args.host
        if args.port:
            settings.port = args.port
        if debug is not None:
            settings.debug = debug
        if args.no_websocket:
            settings.websocket_enabled = False

        # Log configuration
        logger.info(
            "Gateway configuration",
            extra={
                "host": settings.host,
                "port": settings.port,
                "debug": settings.debug,
                "websocket_enabled": settings.websocket_enabled,
                "cors_enabled": settings.cors_enabled,
                "rate_limit_enabled": settings.rate_limit_enabled,
            },
        )

        # Create and run server
        server = GatewayServer(settings=settings)

        logger.info(
            f"Gateway server starting on http://{settings.host}:{settings.port}"
        )

        if settings.websocket_enabled:
            logger.info("WebSocket support enabled")

        server.run(
            host=settings.host,
            port=settings.port,
            debug=settings.debug,
        )

        return 0

    except KeyboardInterrupt:
        logger.info("Gateway service interrupted by user")
        return 0

    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        logger.error("Make sure all dependencies are installed: pip install -r requirements.txt")
        return 1

    except Exception as e:
        logger.exception(f"Gateway service failed to start: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
