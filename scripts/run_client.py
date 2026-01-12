#!/usr/bin/env python3
"""
CLI script to launch the unitMail GTK client application.

This script provides a command-line interface for starting the
desktop email client with configurable options.

Usage:
    python run_client.py [OPTIONS]

Options:
    --debug         Enable debug logging
    --no-sandbox    Disable sandboxing (development only)
    --version       Show version and exit
    --help          Show this message and exit

Examples:
    Start with default settings:
        python run_client.py

    Start in debug mode:
        python run_client.py --debug
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
    Configure logging for the client application.

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
        # Reduce noise from GTK in non-debug mode
        logging.getLogger("gi").setLevel(logging.WARNING)


def check_dependencies() -> bool:
    """
    Check that required dependencies are available.

    Returns:
        True if all dependencies are available, False otherwise.
    """
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")

        from gi.repository import Adw, Gtk  # noqa: F401

        return True
    except (ImportError, ValueError) as e:
        print(f"Error: Missing required dependencies: {e}", file=sys.stderr)
        print("\nPlease install the required packages:", file=sys.stderr)
        print("  - PyGObject", file=sys.stderr)
        print("  - GTK 4", file=sys.stderr)
        print("  - libadwaita", file=sys.stderr)
        print("\nOn Ubuntu/Debian:", file=sys.stderr)
        print(
            "  sudo apt install python3-gi gir1.2-gtk-4.0 libadwaita-1-dev gir1.2-adw-1",
            file=sys.stderr,
        )
        print("\nOn Fedora:", file=sys.stderr)
        print(
            "  sudo dnf install python3-gobject gtk4 libadwaita libadwaita-devel",
            file=sys.stderr,
        )
        print("\nOn Arch Linux:", file=sys.stderr)
        print("  sudo pacman -S python-gobject gtk4 libadwaita", file=sys.stderr)
        return False


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Launch the unitMail desktop email client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    Start with default settings:
        python run_client.py

    Start in debug mode:
        python run_client.py --debug

Environment Variables:
    UNITMAIL_DEBUG          Enable debug mode (true/false)
    UNITMAIL_CONFIG_DIR     Configuration directory path
    GTK_THEME               GTK theme to use
        """,
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        default=None,
        help="Enable debug logging",
    )

    parser.add_argument(
        "--no-debug",
        action="store_true",
        help="Explicitly disable debug mode",
    )

    parser.add_argument(
        "--no-sandbox",
        action="store_true",
        help="Disable sandboxing (development only)",
    )

    parser.add_argument(
        "--inspector",
        action="store_true",
        help="Enable GTK inspector",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="unitMail Client 1.0.0",
    )

    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the client application.

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
        debug = os.getenv("UNITMAIL_DEBUG", "").lower() in ("true", "1", "yes")

    # Setup logging
    setup_logging(debug)
    logger = logging.getLogger(__name__)

    logger.info("Starting unitMail client")

    # Check dependencies before importing GTK modules
    if not check_dependencies():
        return 1

    try:
        # Enable GTK inspector if requested
        if args.inspector or debug:
            os.environ["GTK_DEBUG"] = "interactive"

        # Import and run the application
        from client.ui.application import run_application

        logger.info("Launching GTK application")

        # Run the application
        exit_code = run_application(sys.argv)

        logger.info(f"Application exited with code {exit_code}")
        return exit_code

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        return 0

    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        logger.error(
            "Make sure all dependencies are installed: pip install -r requirements.txt"
        )
        return 1

    except Exception as e:
        logger.exception(f"Application failed to start: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
