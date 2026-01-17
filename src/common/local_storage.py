"""
Local Email Storage for unitMail.

This module provides backward-compatible access to the SQLite-based
email storage system. All storage operations are delegated to the
new storage module.

For new code, prefer importing directly from common.storage:
    from common.storage import get_storage, EmailStorage

This module is maintained for backward compatibility with existing code.
"""

from .storage import (
    EmailStorage,
    get_storage,
    FolderType,
    MessageStatus,
    MessagePriority,
)

# Re-export everything for backward compatibility
__all__ = [
    "LocalEmailStorage",
    "get_local_storage",
    "FolderType",
    "MessageStatus",
    "MessagePriority",
]


# Backward-compatible aliases
LocalEmailStorage = EmailStorage


def get_local_storage() -> EmailStorage:
    """
    Get the local storage instance.

    This function is maintained for backward compatibility.
    New code should use `get_storage()` from `common.storage`.

    Returns:
        EmailStorage instance.
    """
    return get_storage()
