"""
SQLite connection management for unitMail.

This module provides:
- Thread-safe connection pooling
- Context managers for transactions
- Connection configuration (WAL mode, foreign keys, etc.)
- Automatic connection cleanup

SQLite Best Practices Applied:
1. WAL (Write-Ahead Logging) mode for better concurrency
2. Foreign key enforcement enabled
3. Busy timeout for concurrent access
4. Memory-mapped I/O for performance
"""

import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

logger = logging.getLogger(__name__)


class ConnectionPool:
    """
    Thread-safe SQLite connection pool.

    Each thread gets its own connection to avoid SQLite's
    single-thread limitation while maintaining safety.
    """

    def __init__(self, db_path: str, max_connections: int = 10):
        """
        Initialize the connection pool.

        Args:
            db_path: Path to the SQLite database file.
            max_connections: Maximum number of pooled connections.
        """
        self._db_path = db_path
        self._max_connections = max_connections
        self._local = threading.local()
        self._lock = threading.Lock()
        self._connections: dict[int, sqlite3.Connection] = {}

        # Ensure directory exists
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """
        Get a connection for the current thread.

        Returns:
            SQLite connection configured for this application.
        """
        thread_id = threading.get_ident()

        # Check if this thread already has a connection
        if hasattr(self._local, "connection") and self._local.connection is not None:
            return self._local.connection

        # Create new connection
        with self._lock:
            if thread_id in self._connections:
                conn = self._connections[thread_id]
            else:
                conn = self._create_connection()
                self._connections[thread_id] = conn

        self._local.connection = conn
        return conn

    def _create_connection(self) -> sqlite3.Connection:
        """
        Create and configure a new SQLite connection.

        Returns:
            Configured SQLite connection.
        """
        conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,  # We manage thread safety ourselves
            isolation_level=None,  # Autocommit mode - explicit transactions via transaction()
            timeout=30.0,  # Wait up to 30 seconds for locks
        )

        # Configure connection for optimal email storage
        conn.row_factory = sqlite3.Row  # Enable dict-like row access

        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")

        # Use WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode = WAL")

        # Set busy timeout (milliseconds)
        conn.execute("PRAGMA busy_timeout = 30000")

        # Enable memory-mapped I/O (64MB)
        conn.execute("PRAGMA mmap_size = 67108864")

        # Set synchronous mode to NORMAL (good balance of safety/speed)
        conn.execute("PRAGMA synchronous = NORMAL")

        # Set cache size (negative = KB, positive = pages)
        conn.execute("PRAGMA cache_size = -32000")  # 32MB cache

        # Enable auto-vacuum in incremental mode
        conn.execute("PRAGMA auto_vacuum = INCREMENTAL")

        logger.debug(f"Created new SQLite connection for thread {threading.get_ident()}")
        return conn

    def close_all(self) -> None:
        """Close all connections in the pool."""
        with self._lock:
            for thread_id, conn in self._connections.items():
                try:
                    conn.close()
                    logger.debug(f"Closed connection for thread {thread_id}")
                except Exception as e:
                    logger.warning(f"Error closing connection: {e}")
            self._connections.clear()

        # Clear thread-local storage
        if hasattr(self._local, "connection"):
            self._local.connection = None

    def close_current_thread(self) -> None:
        """Close the connection for the current thread."""
        thread_id = threading.get_ident()
        with self._lock:
            if thread_id in self._connections:
                try:
                    self._connections[thread_id].close()
                    del self._connections[thread_id]
                except Exception as e:
                    logger.warning(f"Error closing thread connection: {e}")

        if hasattr(self._local, "connection"):
            self._local.connection = None


class DatabaseConnection:
    """
    High-level database connection manager.

    Provides context managers for connections and transactions,
    with automatic cleanup and error handling.
    """

    _instance: Optional["DatabaseConnection"] = None
    _pool: Optional[ConnectionPool] = None

    def __new__(cls, db_path: Optional[str] = None) -> "DatabaseConnection":
        """Singleton pattern for connection manager."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the database connection manager.

        Args:
            db_path: Path to database file. Defaults to ~/.unitmail/data/unitmail.db
        """
        if self._pool is not None:
            return  # Already initialized

        if db_path is None:
            db_path = os.path.expanduser("~/.unitmail/data/unitmail.db")

        self._db_path = db_path
        self._pool = ConnectionPool(db_path)
        logger.info(f"Database connection manager initialized: {db_path}")

    @property
    def db_path(self) -> str:
        """Get the database file path."""
        return self._db_path

    @property
    def connection(self) -> sqlite3.Connection:
        """Get a connection for the current thread."""
        return self._pool.get_connection()

    @contextmanager
    def cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """
        Context manager for database cursor.

        Yields:
            SQLite cursor for executing queries.
        """
        conn = self.connection
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for database transactions.

        Automatically commits on success, rolls back on exception.

        Yields:
            SQLite connection within a transaction.

        Example:
            with db.transaction() as conn:
                conn.execute("INSERT INTO ...")
                conn.execute("UPDATE ...")
            # Auto-commits here
        """
        conn = self.connection
        # Check if already in a transaction
        in_transaction = conn.in_transaction
        if not in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            if not in_transaction:
                conn.commit()
        except Exception:
            if not in_transaction:
                conn.rollback()
            raise

    def execute(
        self,
        sql: str,
        params: tuple = (),
    ) -> sqlite3.Cursor:
        """
        Execute a SQL statement.

        Args:
            sql: SQL statement to execute.
            params: Parameters for the statement.

        Returns:
            Cursor with results.
        """
        return self.connection.execute(sql, params)

    def executemany(
        self,
        sql: str,
        params_list: list[tuple],
    ) -> sqlite3.Cursor:
        """
        Execute a SQL statement with multiple parameter sets.

        Args:
            sql: SQL statement to execute.
            params_list: List of parameter tuples.

        Returns:
            Cursor with results.
        """
        return self.connection.executemany(sql, params_list)

    def fetchone(
        self,
        sql: str,
        params: tuple = (),
    ) -> Optional[sqlite3.Row]:
        """
        Execute and fetch one row.

        Args:
            sql: SQL query to execute.
            params: Query parameters.

        Returns:
            Single row or None.
        """
        cursor = self.execute(sql, params)
        return cursor.fetchone()

    def fetchall(
        self,
        sql: str,
        params: tuple = (),
    ) -> list[sqlite3.Row]:
        """
        Execute and fetch all rows.

        Args:
            sql: SQL query to execute.
            params: Query parameters.

        Returns:
            List of rows.
        """
        cursor = self.execute(sql, params)
        return cursor.fetchall()

    def close(self) -> None:
        """Close all database connections."""
        if self._pool:
            self._pool.close_all()
            logger.info("All database connections closed")

    def vacuum(self) -> None:
        """
        Run VACUUM to reclaim disk space.

        This should be run periodically, especially after
        deleting many messages.
        """
        self.connection.execute("VACUUM")
        logger.info("Database vacuumed")

    def optimize(self) -> None:
        """
        Run optimization routines.

        Includes analyzing tables and optimizing FTS index.
        """
        conn = self.connection
        conn.execute("ANALYZE")
        conn.execute("INSERT INTO messages_fts(messages_fts) VALUES('optimize')")
        logger.info("Database optimized")

    def integrity_check(self) -> bool:
        """
        Run integrity check on the database.

        Returns:
            True if database is healthy.
        """
        result = self.fetchone("PRAGMA integrity_check")
        is_ok = result and result[0] == "ok"
        if not is_ok:
            logger.error(f"Database integrity check failed: {result}")
        return is_ok

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (for testing)."""
        if cls._instance and cls._pool:
            cls._pool.close_all()
        cls._instance = None
        cls._pool = None


def get_db(db_path: Optional[str] = None) -> DatabaseConnection:
    """
    Get the database connection manager singleton.

    Args:
        db_path: Optional path to database file.

    Returns:
        DatabaseConnection instance.
    """
    return DatabaseConnection(db_path)
