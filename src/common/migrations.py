"""
Database migrations management for unitMail.

This module provides a MigrationRunner class that handles database schema
migrations with support for applying, rolling back, and tracking migration
status. It reads SQL files from the database/migrations directory and
maintains a migrations table to track applied migrations.
"""

import asyncio
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from supabase import Client

from .config import get_settings
from .database import get_db
from .exceptions import DatabaseError, QueryError


class MigrationDirection(Enum):
    """Direction of migration execution."""
    UP = "up"
    DOWN = "down"


@dataclass
class Migration:
    """
    Represents a single database migration.

    Attributes:
        name: Migration filename (e.g., "001_initial_schema.sql")
        version: Numeric version extracted from filename
        up_sql: SQL statements for applying the migration
        down_sql: SQL statements for rolling back the migration
        checksum: MD5 hash of the migration file content
        applied_at: Timestamp when migration was applied (None if not applied)
    """
    name: str
    version: int
    up_sql: str
    down_sql: str
    checksum: str
    applied_at: Optional[datetime] = None

    @property
    def is_applied(self) -> bool:
        """Check if the migration has been applied."""
        return self.applied_at is not None


@dataclass
class MigrationStatus:
    """
    Status information for a migration.

    Attributes:
        name: Migration filename
        version: Numeric version
        applied: Whether the migration has been applied
        applied_at: When the migration was applied
        checksum_match: Whether the file checksum matches the applied checksum
    """
    name: str
    version: int
    applied: bool
    applied_at: Optional[datetime]
    checksum_match: bool


class MigrationError(DatabaseError):
    """Raised when a migration operation fails."""

    def __init__(
        self,
        message: str,
        migration_name: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialize migration error.

        Args:
            message: Human-readable error message.
            migration_name: Name of the migration that failed.
            details: Optional dictionary with additional error details.
        """
        super().__init__(message, details)
        self.migration_name = migration_name


class MigrationRunner:
    """
    Manages database migrations for unitMail.

    This class handles:
    - Loading migration files from the migrations directory
    - Tracking applied migrations in the database
    - Applying and rolling back migrations
    - Validating migration checksums

    Migration files should follow the naming convention:
    NNN_description.sql (e.g., 001_initial_schema.sql)

    Migration files can contain UP and DOWN sections:
    ```sql
    -- UP
    CREATE TABLE example (...);

    -- DOWN
    DROP TABLE example;
    ```

    If no sections are specified, the entire file is treated as UP migration.
    """

    MIGRATIONS_TABLE = "_migrations"
    MIGRATION_PATTERN = re.compile(r"^(\d{3})_.*\.sql$")
    SECTION_PATTERN = re.compile(r"--\s*(UP|DOWN)\s*\n", re.IGNORECASE)

    def __init__(
        self,
        migrations_dir: Optional[Path] = None,
        client: Optional[Client] = None,
    ) -> None:
        """
        Initialize the migration runner.

        Args:
            migrations_dir: Path to directory containing migration files.
                           Defaults to project's database/migrations directory.
            client: Supabase client instance. If not provided, uses the
                   default client from get_db().
        """
        if migrations_dir is None:
            # Default to project's database/migrations directory
            project_root = Path(__file__).parent.parent.parent
            self._migrations_dir = project_root / "database" / "migrations"
        else:
            self._migrations_dir = Path(migrations_dir)

        self._client = client
        self._migrations: dict[int, Migration] = {}

    @property
    def client(self) -> Client:
        """Get the Supabase client."""
        if self._client is None:
            self._client = get_db().client
        return self._client

    def _compute_checksum(self, content: str) -> str:
        """
        Compute MD5 checksum of migration content.

        Args:
            content: The SQL content to hash.

        Returns:
            MD5 hexdigest of the content.
        """
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def _parse_migration_file(self, filepath: Path) -> tuple[str, str]:
        """
        Parse a migration file into UP and DOWN SQL sections.

        Args:
            filepath: Path to the migration file.

        Returns:
            Tuple of (up_sql, down_sql). down_sql may be empty.
        """
        content = filepath.read_text(encoding="utf-8")

        # Look for UP and DOWN sections
        sections = self.SECTION_PATTERN.split(content)

        if len(sections) == 1:
            # No sections found, treat entire file as UP migration
            return content.strip(), ""

        up_sql = ""
        down_sql = ""

        # Parse sections: sections will be [before, 'UP'/'DOWN', content, ...]
        i = 0
        while i < len(sections):
            section = sections[i].strip()
            if section.upper() == "UP" and i + 1 < len(sections):
                up_sql = sections[i + 1].strip()
                i += 2
            elif section.upper() == "DOWN" and i + 1 < len(sections):
                down_sql = sections[i + 1].strip()
                i += 2
            else:
                i += 1

        return up_sql, down_sql

    def _load_migrations(self) -> None:
        """
        Load all migration files from the migrations directory.

        Raises:
            MigrationError: If the migrations directory doesn't exist or
                           contains invalid migration files.
        """
        if not self._migrations_dir.exists():
            raise MigrationError(
                f"Migrations directory not found: {self._migrations_dir}"
            )

        self._migrations.clear()

        for filepath in sorted(self._migrations_dir.glob("*.sql")):
            match = self.MIGRATION_PATTERN.match(filepath.name)
            if not match:
                continue  # Skip files that don't match the pattern

            version = int(match.group(1))

            if version in self._migrations:
                raise MigrationError(
                    f"Duplicate migration version: {version}",
                    migration_name=filepath.name,
                )

            content = filepath.read_text(encoding="utf-8")
            up_sql, down_sql = self._parse_migration_file(filepath)
            checksum = self._compute_checksum(content)

            self._migrations[version] = Migration(
                name=filepath.name,
                version=version,
                up_sql=up_sql,
                down_sql=down_sql,
                checksum=checksum,
            )

    async def _execute_sql(self, sql: str, description: str = "query") -> None:
        """
        Execute raw SQL using Supabase's RPC or direct query.

        Args:
            sql: SQL statements to execute.
            description: Description of the query for error messages.

        Raises:
            QueryError: If the SQL execution fails.
        """
        try:
            # Use Supabase's RPC to execute raw SQL
            # Note: This requires a custom SQL function in Supabase
            # For direct SQL execution, we'll use the REST API
            await asyncio.to_thread(
                lambda: self.client.rpc("exec_sql", {"sql": sql}).execute()
            )
        except Exception as e:
            raise QueryError(
                f"Failed to execute {description}: {e}",
                query=sql[:200] + "..." if len(sql) > 200 else sql,
            )

    async def _ensure_migrations_table(self) -> None:
        """
        Ensure the migrations tracking table exists.

        Creates the _migrations table if it doesn't exist.
        """
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.MIGRATIONS_TABLE} (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            checksum VARCHAR(32) NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
        await self._execute_sql(create_table_sql, "create migrations table")

    async def _get_applied_migrations(self) -> dict[str, tuple[datetime, str]]:
        """
        Get all applied migrations from the database.

        Returns:
            Dictionary mapping migration name to (applied_at, checksum) tuple.
        """
        try:
            response = await asyncio.to_thread(
                lambda: self.client.table(self.MIGRATIONS_TABLE)
                .select("name, applied_at, checksum")
                .execute()
            )

            return {
                row["name"]: (
                    datetime.fromisoformat(row["applied_at"].replace("Z", "+00:00")),
                    row["checksum"],
                )
                for row in response.data
            }
        except Exception:
            # Table might not exist yet
            return {}

    async def _record_migration(self, migration: Migration) -> None:
        """
        Record a migration as applied in the database.

        Args:
            migration: The migration that was applied.
        """
        await asyncio.to_thread(
            lambda: self.client.table(self.MIGRATIONS_TABLE)
            .insert({
                "name": migration.name,
                "checksum": migration.checksum,
            })
            .execute()
        )

    async def _remove_migration_record(self, migration: Migration) -> None:
        """
        Remove a migration record from the database.

        Args:
            migration: The migration to remove.
        """
        await asyncio.to_thread(
            lambda: self.client.table(self.MIGRATIONS_TABLE)
            .delete()
            .eq("name", migration.name)
            .execute()
        )

    async def get_status(self) -> list[MigrationStatus]:
        """
        Get the status of all migrations.

        Returns a list of MigrationStatus objects showing which migrations
        have been applied and whether their checksums match.

        Returns:
            List of MigrationStatus objects sorted by version.
        """
        self._load_migrations()

        await self._ensure_migrations_table()
        applied = await self._get_applied_migrations()

        statuses = []
        for version in sorted(self._migrations.keys()):
            migration = self._migrations[version]

            if migration.name in applied:
                applied_at, db_checksum = applied[migration.name]
                statuses.append(MigrationStatus(
                    name=migration.name,
                    version=migration.version,
                    applied=True,
                    applied_at=applied_at,
                    checksum_match=db_checksum == migration.checksum,
                ))
            else:
                statuses.append(MigrationStatus(
                    name=migration.name,
                    version=migration.version,
                    applied=False,
                    applied_at=None,
                    checksum_match=True,
                ))

        return statuses

    async def apply_one(
        self,
        version: Optional[int] = None,
        dry_run: bool = False,
    ) -> Optional[Migration]:
        """
        Apply a single migration.

        If no version is specified, applies the next pending migration.

        Args:
            version: Specific migration version to apply. If None, applies
                    the next pending migration.
            dry_run: If True, only show what would be done without executing.

        Returns:
            The applied migration, or None if no migrations to apply.

        Raises:
            MigrationError: If the migration fails or version not found.
        """
        self._load_migrations()

        if not dry_run:
            await self._ensure_migrations_table()

        applied = await self._get_applied_migrations()

        # Find the migration to apply
        migration: Optional[Migration] = None

        if version is not None:
            if version not in self._migrations:
                raise MigrationError(f"Migration version {version} not found")
            migration = self._migrations[version]
            if migration.name in applied:
                raise MigrationError(
                    f"Migration {migration.name} is already applied",
                    migration_name=migration.name,
                )
        else:
            # Find next pending migration
            for v in sorted(self._migrations.keys()):
                m = self._migrations[v]
                if m.name not in applied:
                    migration = m
                    break

        if migration is None:
            return None

        if not migration.up_sql:
            raise MigrationError(
                f"Migration {migration.name} has no UP SQL",
                migration_name=migration.name,
            )

        if dry_run:
            return migration

        # Apply the migration
        try:
            await self._execute_sql(
                migration.up_sql,
                f"migration {migration.name}",
            )
            await self._record_migration(migration)
            migration.applied_at = datetime.utcnow()
            return migration
        except Exception as e:
            raise MigrationError(
                f"Failed to apply migration {migration.name}: {e}",
                migration_name=migration.name,
                details={"error": str(e)},
            )

    async def apply_all(self, dry_run: bool = False) -> list[Migration]:
        """
        Apply all pending migrations in order.

        Args:
            dry_run: If True, only show what would be done without executing.

        Returns:
            List of applied migrations.

        Raises:
            MigrationError: If any migration fails.
        """
        self._load_migrations()

        if not dry_run:
            await self._ensure_migrations_table()

        applied = await self._get_applied_migrations()

        # Find all pending migrations
        pending = [
            self._migrations[v]
            for v in sorted(self._migrations.keys())
            if self._migrations[v].name not in applied
        ]

        if dry_run:
            return pending

        applied_migrations = []
        for migration in pending:
            if not migration.up_sql:
                raise MigrationError(
                    f"Migration {migration.name} has no UP SQL",
                    migration_name=migration.name,
                )

            try:
                await self._execute_sql(
                    migration.up_sql,
                    f"migration {migration.name}",
                )
                await self._record_migration(migration)
                migration.applied_at = datetime.utcnow()
                applied_migrations.append(migration)
            except Exception as e:
                raise MigrationError(
                    f"Failed to apply migration {migration.name}: {e}",
                    migration_name=migration.name,
                    details={
                        "error": str(e),
                        "applied_so_far": [m.name for m in applied_migrations],
                    },
                )

        return applied_migrations

    async def rollback(
        self,
        steps: int = 1,
        dry_run: bool = False,
    ) -> list[Migration]:
        """
        Rollback the most recently applied migrations.

        Args:
            steps: Number of migrations to rollback. Default is 1.
            dry_run: If True, only show what would be done without executing.

        Returns:
            List of rolled back migrations.

        Raises:
            MigrationError: If rollback fails or no migrations to rollback.
        """
        self._load_migrations()

        if not dry_run:
            await self._ensure_migrations_table()

        applied = await self._get_applied_migrations()

        # Get applied migrations sorted by version descending
        applied_versions = [
            v for v in sorted(self._migrations.keys(), reverse=True)
            if self._migrations[v].name in applied
        ]

        if not applied_versions:
            return []

        # Limit to requested steps
        to_rollback = applied_versions[:steps]

        rollback_migrations = [self._migrations[v] for v in to_rollback]

        if dry_run:
            return rollback_migrations

        rolled_back = []
        for migration in rollback_migrations:
            if not migration.down_sql:
                raise MigrationError(
                    f"Migration {migration.name} has no DOWN SQL for rollback",
                    migration_name=migration.name,
                )

            try:
                await self._execute_sql(
                    migration.down_sql,
                    f"rollback {migration.name}",
                )
                await self._remove_migration_record(migration)
                rolled_back.append(migration)
            except Exception as e:
                raise MigrationError(
                    f"Failed to rollback migration {migration.name}: {e}",
                    migration_name=migration.name,
                    details={
                        "error": str(e),
                        "rolled_back_so_far": [m.name for m in rolled_back],
                    },
                )

        return rolled_back

    async def reset(self, dry_run: bool = False) -> list[Migration]:
        """
        Rollback all applied migrations.

        This is a destructive operation that will rollback all migrations
        in reverse order.

        Args:
            dry_run: If True, only show what would be done without executing.

        Returns:
            List of rolled back migrations.

        Raises:
            MigrationError: If reset fails.
        """
        self._load_migrations()

        applied = await self._get_applied_migrations()
        total_applied = len(applied)

        if total_applied == 0:
            return []

        return await self.rollback(steps=total_applied, dry_run=dry_run)

    def get_pending_count(self) -> int:
        """
        Get the number of pending migrations.

        Note: This is a synchronous method that only checks local files.
        For accurate status including applied migrations, use get_status().

        Returns:
            Number of migration files in the migrations directory.
        """
        self._load_migrations()
        return len(self._migrations)


async def run_migrations(
    direction: MigrationDirection = MigrationDirection.UP,
    steps: int = 0,
    dry_run: bool = False,
    migrations_dir: Optional[Path] = None,
) -> list[Migration]:
    """
    Convenience function to run migrations.

    Args:
        direction: UP to apply migrations, DOWN to rollback.
        steps: Number of migrations to apply/rollback. 0 means all pending (UP)
               or 1 (DOWN).
        dry_run: If True, only show what would be done.
        migrations_dir: Optional path to migrations directory.

    Returns:
        List of affected migrations.
    """
    runner = MigrationRunner(migrations_dir=migrations_dir)

    if direction == MigrationDirection.UP:
        if steps == 0:
            return await runner.apply_all(dry_run=dry_run)
        else:
            migrations = []
            for _ in range(steps):
                migration = await runner.apply_one(dry_run=dry_run)
                if migration is None:
                    break
                migrations.append(migration)
            return migrations
    else:
        return await runner.rollback(steps=steps or 1, dry_run=dry_run)
