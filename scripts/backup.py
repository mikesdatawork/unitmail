#!/usr/bin/env python3
"""
Backup CLI script for unitMail.

This script provides a command-line interface for creating automated backups
of unitMail data. It is designed to be cron-friendly with proper exit codes
and supports both full and incremental backups.

Usage:
    python scripts/backup.py --output /path/to/backup --password <password>
    python scripts/backup.py --output /backups --password <password> --incremental
    python scripts/backup.py --output /backups --password-file /path/to/password.txt

Exit Codes:
    0 - Success
    1 - General error
    2 - Configuration error
    3 - Authentication error
    4 - Backup creation error
    5 - File system error

Examples:
    # Create a full backup
    python scripts/backup.py \\
        --output /home/user/backups/unitmail \\
        --password "secure_password" \\
        --user-id "550e8400-e29b-41d4-a716-446655440000"

    # Create an incremental backup
    python scripts/backup.py \\
        --output /home/user/backups \\
        --password-file /etc/unitmail/backup-password \\
        --incremental \\
        --last-backup "2024-01-01T00:00:00"

    # Cron job (daily at 2 AM)
    0 2 * * * /usr/bin/python3 /opt/unitmail/scripts/backup.py \\
        --output /backups/unitmail \\
        --password-file /etc/unitmail/backup-password \\
        >> /var/log/unitmail-backup.log 2>&1
"""

import argparse
import asyncio
import getpass
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from client.services.backup_service import (
    BackupContents,
    BackupError,
    BackupMetadata,
    BackupProgress,
    BackupService,
)
from common.database import get_db


# Exit codes
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_AUTH_ERROR = 3
EXIT_BACKUP_ERROR = 4
EXIT_FS_ERROR = 5


class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    @classmethod
    def disable(cls) -> None:
        """Disable colors (for non-TTY output)."""
        cls.RESET = ""
        cls.RED = ""
        cls.GREEN = ""
        cls.YELLOW = ""
        cls.BLUE = ""
        cls.BOLD = ""
        cls.DIM = ""


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== {text} ==={Colors.RESET}\n")


def print_success(text: str) -> None:
    """Print a success message."""
    print(f"{Colors.GREEN}[OK]{Colors.RESET} {text}")


def print_warning(text: str) -> None:
    """Print a warning message."""
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {text}")


def print_error(text: str) -> None:
    """Print an error message."""
    print(f"{Colors.RED}[ERROR]{Colors.RESET} {text}", file=sys.stderr)


def print_info(text: str) -> None:
    """Print an info message."""
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {text}")


def print_progress(progress: BackupProgress) -> None:
    """Print progress update."""
    if progress.is_complete:
        print_success(progress.current_step)
    else:
        print(f"  {Colors.DIM}[{progress.percent_complete:.0f}%]{Colors.RESET} {progress.current_step}")


def format_size(size: int) -> str:
    """Format size in bytes to human-readable string."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"


def get_password(args: argparse.Namespace) -> Optional[str]:
    """
    Get the backup password from arguments or file.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Password string or None if not provided.
    """
    if args.password:
        return args.password

    if args.password_file:
        try:
            with open(args.password_file, "r") as f:
                return f.read().strip()
        except Exception as e:
            print_error(f"Failed to read password file: {e}")
            return None

    if args.password_env:
        password = os.environ.get(args.password_env)
        if not password:
            print_error(f"Environment variable {args.password_env} not set")
            return None
        return password

    # Interactive mode
    if sys.stdin.isatty():
        try:
            password = getpass.getpass("Backup password: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print_error("Passwords do not match")
                return None
            return password
        except KeyboardInterrupt:
            print("\nCancelled")
            return None

    print_error("No password provided. Use --password, --password-file, or --password-env")
    return None


def parse_datetime(value: str) -> Optional[datetime]:
    """Parse a datetime string."""
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    return None


async def run_backup(args: argparse.Namespace) -> int:
    """
    Execute the backup operation.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    print_header("unitMail Backup")

    # Validate user ID
    try:
        user_id = UUID(args.user_id)
    except (ValueError, TypeError):
        print_error(f"Invalid user ID: {args.user_id}")
        return EXIT_CONFIG_ERROR

    # Get password
    password = get_password(args)
    if not password:
        return EXIT_CONFIG_ERROR

    if len(password) < 8:
        print_error("Password must be at least 8 characters")
        return EXIT_CONFIG_ERROR

    # Validate output path
    output_path = Path(args.output)

    if output_path.is_dir():
        # Generate filename if directory provided
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_type = "incr" if args.incremental else "full"
        filename = f"unitmail_backup_{backup_type}_{timestamp}.unitmail-backup"
        output_path = output_path / filename

    # Ensure parent directory exists
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print_error(f"Failed to create output directory: {e}")
        return EXIT_FS_ERROR

    # Parse last backup timestamp for incremental
    last_backup_timestamp = None
    if args.incremental and args.last_backup:
        last_backup_timestamp = parse_datetime(args.last_backup)
        if last_backup_timestamp is None:
            print_error(f"Invalid last backup timestamp: {args.last_backup}")
            return EXIT_CONFIG_ERROR

    # Configure backup contents
    contents = BackupContents(
        messages=not args.skip_messages,
        contacts=not args.skip_contacts,
        folders=not args.skip_folders,
        configuration=not args.skip_config,
        dkim_keys=not args.skip_dkim,
        pgp_keys=not args.skip_pgp,
    )

    # Show configuration
    print_info(f"Output: {output_path}")
    print_info(f"Backup type: {'Incremental' if args.incremental else 'Full'}")
    print_info(f"User ID: {user_id}")

    if args.verbose:
        print_info("Contents:")
        print(f"  Messages:      {'Yes' if contents.messages else 'No'}")
        print(f"  Contacts:      {'Yes' if contents.contacts else 'No'}")
        print(f"  Folders:       {'Yes' if contents.folders else 'No'}")
        print(f"  Configuration: {'Yes' if contents.configuration else 'No'}")
        print(f"  DKIM Keys:     {'Yes' if contents.dkim_keys else 'No'}")
        print(f"  PGP Keys:      {'Yes' if contents.pgp_keys else 'No'}")

    # Create backup service
    backup_service = BackupService()

    if not args.quiet:
        backup_service.set_progress_callback(print_progress)

    # Run backup
    print()
    print_info("Starting backup...")

    try:
        start_time = datetime.now()

        metadata = await backup_service.create_backup(
            output_path=output_path,
            password=password,
            user_id=user_id,
            user_email=args.user_email or "",
            contents=contents,
            incremental=args.incremental,
            last_backup_timestamp=last_backup_timestamp,
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Get file size
        file_size = output_path.stat().st_size

        print()
        print_header("Backup Complete")

        print_success(f"Backup created: {output_path}")
        print_info(f"Size: {format_size(file_size)}")
        print_info(f"Duration: {duration:.1f} seconds")
        print_info(f"Checksum: {metadata.checksum[:16]}...")

        if args.verbose:
            print()
            print_info("Items backed up:")
            for key, count in metadata.contents.items():
                if count > 0:
                    print(f"  {key}: {count}")

        return EXIT_SUCCESS

    except BackupError as e:
        print_error(f"Backup failed: {e}")
        return EXIT_BACKUP_ERROR

    except Exception as e:
        print_error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return EXIT_ERROR


def create_parser() -> argparse.ArgumentParser:
    """
    Create the argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="unitMail Backup Tool - Create encrypted backups of your email data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Codes:
  0 - Success
  1 - General error
  2 - Configuration error
  3 - Authentication error
  4 - Backup creation error
  5 - File system error

Examples:
  # Full backup with password
  %(prog)s --output /backups/unitmail.backup --password "secret" --user-id "..."

  # Incremental backup with password file
  %(prog)s --output /backups --password-file /etc/unitmail/pass --incremental

  # Skip certain content types
  %(prog)s --output /backups --password "secret" --skip-pgp --skip-dkim

Environment Variables:
  SUPABASE_URL - Database URL (required)
  SUPABASE_KEY - Database API key (required)
        """,
    )

    # Required arguments
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output path for backup file (or directory)",
    )

    parser.add_argument(
        "--user-id", "-u",
        required=True,
        help="UUID of the user to backup",
    )

    # Password options (one required)
    password_group = parser.add_mutually_exclusive_group()
    password_group.add_argument(
        "--password", "-p",
        help="Encryption password (use --password-file for better security)",
    )
    password_group.add_argument(
        "--password-file",
        help="Path to file containing encryption password",
    )
    password_group.add_argument(
        "--password-env",
        default="UNITMAIL_BACKUP_PASSWORD",
        help="Environment variable containing password (default: UNITMAIL_BACKUP_PASSWORD)",
    )

    # Backup type
    parser.add_argument(
        "--incremental", "-i",
        action="store_true",
        help="Create incremental backup (only changes since last backup)",
    )

    parser.add_argument(
        "--last-backup",
        metavar="TIMESTAMP",
        help="Timestamp of last backup for incremental mode (ISO format)",
    )

    # Content selection
    parser.add_argument(
        "--skip-messages",
        action="store_true",
        help="Skip messages in backup",
    )
    parser.add_argument(
        "--skip-contacts",
        action="store_true",
        help="Skip contacts in backup",
    )
    parser.add_argument(
        "--skip-folders",
        action="store_true",
        help="Skip folders in backup",
    )
    parser.add_argument(
        "--skip-config",
        action="store_true",
        help="Skip configuration in backup",
    )
    parser.add_argument(
        "--skip-dkim",
        action="store_true",
        help="Skip DKIM keys in backup",
    )
    parser.add_argument(
        "--skip-pgp",
        action="store_true",
        help="Skip PGP keys in backup",
    )

    # Optional arguments
    parser.add_argument(
        "--user-email",
        help="User email for backup metadata",
    )

    # Output control
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Quiet mode (no progress output)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )

    return parser


def main() -> int:
    """
    Main entry point for the backup CLI.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    parser = create_parser()
    args = parser.parse_args()

    # Disable colors if requested or not a TTY
    if args.no_color or not sys.stdout.isatty():
        Colors.disable()

    # Quiet mode implies no color
    if args.quiet:
        Colors.disable()

    try:
        return asyncio.run(run_backup(args))

    except KeyboardInterrupt:
        print("\nBackup cancelled.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
