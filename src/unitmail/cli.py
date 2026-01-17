#!/usr/bin/env python3
"""
Command-line interface for unitMail.

This module provides the main entry point for the unitMail application
when installed as a package (via `pip install unitmail`).

Usage:
    unitmail [OPTIONS]

Options:
    --debug         Enable debug logging
    --no-sandbox    Disable sandboxing (development only)
    --version       Show version and exit
    --help          Show this message and exit
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from unitmail import __version__


def setup_logging(debug: bool = False) -> None:
    """
    Configure logging for the client application.

    Args:
        debug: Enable debug logging.
    """
    log_level = logging.DEBUG if debug else logging.INFO
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    if not debug:
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
        description="unitMail - Independent Email Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    Start with default settings:
        unitmail

    Start in debug mode:
        unitmail --debug

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
        version=f"unitMail {__version__}",
    )

    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the unitMail application.

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

    setup_logging(debug)
    logger = logging.getLogger(__name__)

    logger.info(f"Starting unitMail v{__version__}")

    if not check_dependencies():
        return 1

    try:
        if args.inspector or debug:
            os.environ["GTK_DEBUG"] = "interactive"

        # Add src directory to path for client imports
        src_dir = Path(__file__).resolve().parent.parent
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

        from client.ui.application import run_application

        logger.info("Launching GTK application")
        exit_code = run_application(sys.argv)

        logger.info(f"Application exited with code {exit_code}")
        return exit_code

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        return 0

    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        logger.error(
            "Make sure all dependencies are installed: pip install -e '.[dev]'"
        )
        return 1

    except Exception as e:
        logger.exception(f"Application failed to start: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
