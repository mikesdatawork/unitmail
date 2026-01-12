#!/usr/bin/env python3
"""
Database migration CLI for unitMail.

This script provides a command-line interface for managing database migrations.
It supports applying, rolling back, and checking the status of migrations.

Usage:
    python scripts/migrate.py up [--dry-run] [--steps N]
    python scripts/migrate.py down [--dry-run] [--steps N]
    python scripts/migrate.py status
    python scripts/migrate.py reset [--dry-run] [--force]

Commands:
    up      Apply pending migrations
    down    Rollback migrations
    status  Show migration status
    reset   Rollback all migrations (dangerous!)

Examples:
    # Apply all pending migrations
    python scripts/migrate.py up

    # Preview what migrations would be applied
    python scripts/migrate.py up --dry-run

    # Apply only the next 2 migrations
    python scripts/migrate.py up --steps 2

    # Rollback the last migration
    python scripts/migrate.py down

    # Rollback the last 3 migrations
    python scripts/migrate.py down --steps 3

    # Show current migration status
    python scripts/migrate.py status

    # Reset all migrations (requires --force)
    python scripts/migrate.py reset --force
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from common.migrations import (
    Migration,
    MigrationDirection,
    MigrationError,
    MigrationRunner,
    MigrationStatus,
)


class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
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
        cls.MAGENTA = ""
        cls.CYAN = ""
        cls.BOLD = ""
        cls.DIM = ""


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}=== {text} ==={Colors.RESET}\n")


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


def print_migration(migration: Migration, action: str = "Applied") -> None:
    """Print migration application/rollback info."""
    print(f"  {Colors.GREEN}{action}:{Colors.RESET} {migration.name}")


def print_status_row(status: MigrationStatus) -> None:
    """Print a migration status row."""
    if status.applied:
        state = f"{Colors.GREEN}[APPLIED]{Colors.RESET}"
        time_str = status.applied_at.strftime("%Y-%m-%d %H:%M:%S") if status.applied_at else "unknown"

        if not status.checksum_match:
            state += f" {Colors.YELLOW}[MODIFIED]{Colors.RESET}"
    else:
        state = f"{Colors.YELLOW}[PENDING]{Colors.RESET}"
        time_str = "-"

    print(f"  {status.version:03d}  {state}  {status.name}")
    if status.applied:
        print(f"       {Colors.DIM}Applied at: {time_str}{Colors.RESET}")


async def cmd_up(args: argparse.Namespace) -> int:
    """
    Apply pending migrations.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    runner = MigrationRunner()

    if args.dry_run:
        print_header("Dry Run - Migrations to Apply")
    else:
        print_header("Applying Migrations")

    try:
        if args.steps:
            # Apply specific number of migrations
            migrations = []
            for _ in range(args.steps):
                migration = await runner.apply_one(dry_run=args.dry_run)
                if migration is None:
                    break
                migrations.append(migration)
        else:
            # Apply all pending migrations
            migrations = await runner.apply_all(dry_run=args.dry_run)

        if not migrations:
            print_info("No pending migrations to apply.")
            return 0

        for migration in migrations:
            if args.dry_run:
                print_migration(migration, "Would apply")
            else:
                print_migration(migration, "Applied")

        if args.dry_run:
            print(f"\n{Colors.DIM}(Dry run - no changes made){Colors.RESET}")
        else:
            print_success(f"Applied {len(migrations)} migration(s).")

        return 0

    except MigrationError as e:
        print_error(str(e))
        if e.details:
            for key, value in e.details.items():
                print(f"  {key}: {value}")
        return 1


async def cmd_down(args: argparse.Namespace) -> int:
    """
    Rollback migrations.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    runner = MigrationRunner()

    steps = args.steps or 1

    if args.dry_run:
        print_header(f"Dry Run - Rolling Back {steps} Migration(s)")
    else:
        print_header(f"Rolling Back {steps} Migration(s)")

    try:
        migrations = await runner.rollback(steps=steps, dry_run=args.dry_run)

        if not migrations:
            print_info("No migrations to rollback.")
            return 0

        for migration in migrations:
            if args.dry_run:
                print_migration(migration, "Would rollback")
            else:
                print_migration(migration, "Rolled back")

        if args.dry_run:
            print(f"\n{Colors.DIM}(Dry run - no changes made){Colors.RESET}")
        else:
            print_success(f"Rolled back {len(migrations)} migration(s).")

        return 0

    except MigrationError as e:
        print_error(str(e))
        if e.details:
            for key, value in e.details.items():
                print(f"  {key}: {value}")
        return 1


async def cmd_status(args: argparse.Namespace) -> int:
    """
    Show migration status.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    runner = MigrationRunner()

    print_header("Migration Status")

    try:
        statuses = await runner.get_status()

        if not statuses:
            print_info("No migrations found.")
            return 0

        applied_count = sum(1 for s in statuses if s.applied)
        pending_count = sum(1 for s in statuses if not s.applied)
        modified_count = sum(1 for s in statuses if s.applied and not s.checksum_match)

        for status in statuses:
            print_status_row(status)
            print()

        # Summary
        print(f"\n{Colors.BOLD}Summary:{Colors.RESET}")
        print(f"  Total:    {len(statuses)}")
        print(f"  Applied:  {Colors.GREEN}{applied_count}{Colors.RESET}")
        print(f"  Pending:  {Colors.YELLOW}{pending_count}{Colors.RESET}")

        if modified_count > 0:
            print(f"  Modified: {Colors.RED}{modified_count}{Colors.RESET}")
            print_warning(
                "Some applied migrations have been modified since application. "
                "Consider reviewing and reapplying."
            )

        return 0

    except MigrationError as e:
        print_error(str(e))
        return 1


async def cmd_reset(args: argparse.Namespace) -> int:
    """
    Reset all migrations.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    runner = MigrationRunner()

    if not args.force and not args.dry_run:
        print_error("Reset is a destructive operation!")
        print("Use --force to confirm, or --dry-run to preview.")
        return 1

    if args.dry_run:
        print_header("Dry Run - Reset All Migrations")
    else:
        print_header("Resetting All Migrations")
        print_warning("This will rollback ALL applied migrations!")

    try:
        migrations = await runner.reset(dry_run=args.dry_run)

        if not migrations:
            print_info("No migrations to rollback.")
            return 0

        for migration in migrations:
            if args.dry_run:
                print_migration(migration, "Would rollback")
            else:
                print_migration(migration, "Rolled back")

        if args.dry_run:
            print(f"\n{Colors.DIM}(Dry run - no changes made){Colors.RESET}")
        else:
            print_success(f"Reset complete. Rolled back {len(migrations)} migration(s).")

        return 0

    except MigrationError as e:
        print_error(str(e))
        if e.details:
            for key, value in e.details.items():
                print(f"  {key}: {value}")
        return 1


def create_parser() -> argparse.ArgumentParser:
    """
    Create the argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="unitMail Database Migration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s up                 Apply all pending migrations
  %(prog)s up --dry-run       Preview migrations without applying
  %(prog)s up --steps 2       Apply only the next 2 migrations
  %(prog)s down               Rollback the last migration
  %(prog)s down --steps 3     Rollback the last 3 migrations
  %(prog)s status             Show migration status
  %(prog)s reset --force      Reset all migrations (dangerous!)
        """,
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        description="Available migration commands",
    )

    # UP command
    up_parser = subparsers.add_parser(
        "up",
        help="Apply pending migrations",
        description="Apply pending database migrations in order.",
    )
    up_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migrations without applying them",
    )
    up_parser.add_argument(
        "--steps",
        type=int,
        metavar="N",
        help="Number of migrations to apply (default: all pending)",
    )

    # DOWN command
    down_parser = subparsers.add_parser(
        "down",
        help="Rollback migrations",
        description="Rollback applied database migrations.",
    )
    down_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview rollback without executing",
    )
    down_parser.add_argument(
        "--steps",
        type=int,
        metavar="N",
        default=1,
        help="Number of migrations to rollback (default: 1)",
    )

    # STATUS command
    subparsers.add_parser(
        "status",
        help="Show migration status",
        description="Display the status of all migrations.",
    )

    # RESET command
    reset_parser = subparsers.add_parser(
        "reset",
        help="Rollback all migrations",
        description="Rollback all applied migrations. This is a destructive operation!",
    )
    reset_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview reset without executing",
    )
    reset_parser.add_argument(
        "--force",
        action="store_true",
        help="Confirm reset operation (required unless --dry-run)",
    )

    return parser


async def main() -> int:
    """
    Main entry point for the migration CLI.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    parser = create_parser()
    args = parser.parse_args()

    # Disable colors if requested or not a TTY
    if args.no_color or not sys.stdout.isatty():
        Colors.disable()

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch to command handler
    handlers = {
        "up": cmd_up,
        "down": cmd_down,
        "status": cmd_status,
        "reset": cmd_reset,
    }

    handler = handlers.get(args.command)
    if handler:
        return await handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        sys.exit(130)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
