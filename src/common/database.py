"""
Supabase client library for unitMail.

This module provides a wrapper around the supabase-py library with
connection management, singleton pattern, and CRUD operations for
all database tables.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Generic, Optional, TypeVar
from uuid import UUID

from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

from .config import get_settings
from .exceptions import (
    ConnectionError,
    DuplicateRecordError,
    QueryError,
    RecordNotFoundError,
    TransactionError,
)
from .models import (
    BaseDBModel,
    Config,
    Contact,
    ContactCreate,
    ContactUpdate,
    Folder,
    FolderCreate,
    FolderUpdate,
    Message,
    MessageCreate,
    MessageUpdate,
    MeshPeer,
    QueueItem,
    User,
)


T = TypeVar("T", bound=BaseDBModel)


class TableOperations(Generic[T]):
    """
    Generic CRUD operations for a database table.

    Provides async methods for Create, Read, Update, Delete operations
    with proper error handling and type safety.
    """

    def __init__(
        self,
        client: Client,
        table_name: str,
        model_class: type[T],
    ) -> None:
        """
        Initialize table operations.

        Args:
            client: Supabase client instance.
            table_name: Name of the database table.
            model_class: Pydantic model class for this table.
        """
        self._client = client
        self._table_name = table_name
        self._model_class = model_class

    @property
    def table(self):
        """Get the table reference."""
        return self._client.table(self._table_name)

    async def create(self, data: dict[str, Any]) -> T:
        """
        Create a new record in the table.

        Args:
            data: Dictionary of field values.

        Returns:
            The created record as a model instance.

        Raises:
            DuplicateRecordError: If a unique constraint is violated.
            QueryError: If the insert fails.
        """
        try:
            # Convert UUID to string if present
            processed_data = self._process_data_for_db(data)

            response = await asyncio.to_thread(
                lambda: self.table.insert(processed_data).execute()
            )

            if response.data:
                return self._model_class(**response.data[0])

            raise QueryError(
                f"Failed to create record in {self._table_name}",
                query="INSERT",
            )
        except Exception as e:
            error_str = str(e).lower()
            if "duplicate" in error_str or "unique" in error_str:
                raise DuplicateRecordError(
                    table=self._table_name,
                    field="unknown",
                    value="unknown",
                    details={"error": str(e)},
                )
            raise QueryError(
                f"Failed to create record in {self._table_name}: {e}",
                query="INSERT",
            )

    async def get_by_id(self, record_id: UUID | str) -> T:
        """
        Get a record by its ID.

        Args:
            record_id: The record's unique identifier.

        Returns:
            The record as a model instance.

        Raises:
            RecordNotFoundError: If the record doesn't exist.
            QueryError: If the query fails.
        """
        try:
            response = await asyncio.to_thread(
                lambda: self.table.select("*")
                .eq("id", str(record_id))
                .execute()
            )

            if response.data and len(response.data) > 0:
                return self._model_class(**response.data[0])

            raise RecordNotFoundError(
                table=self._table_name,
                record_id=str(record_id),
            )
        except RecordNotFoundError:
            raise
        except Exception as e:
            raise QueryError(
                f"Failed to get record from {self._table_name}: {e}",
                query="SELECT",
            )

    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: Optional[str] = None,
        ascending: bool = True,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[T]:
        """
        Get all records with optional filtering and pagination.

        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.
            order_by: Field to order by.
            ascending: Sort order (True for ascending).
            filters: Dictionary of field=value filters.

        Returns:
            List of records as model instances.

        Raises:
            QueryError: If the query fails.
        """
        try:
            query = self.table.select("*")

            # Apply filters
            if filters:
                for field, value in filters.items():
                    if value is not None:
                        query = query.eq(field, str(value) if isinstance(value, UUID) else value)

            # Apply ordering
            if order_by:
                query = query.order(order_by, desc=not ascending)

            # Apply pagination
            query = query.range(offset, offset + limit - 1)

            response = await asyncio.to_thread(lambda: query.execute())

            return [self._model_class(**item) for item in response.data]
        except Exception as e:
            raise QueryError(
                f"Failed to get records from {self._table_name}: {e}",
                query="SELECT",
            )

    async def update(
        self,
        record_id: UUID | str,
        data: dict[str, Any],
    ) -> T:
        """
        Update a record by its ID.

        Args:
            record_id: The record's unique identifier.
            data: Dictionary of fields to update.

        Returns:
            The updated record as a model instance.

        Raises:
            RecordNotFoundError: If the record doesn't exist.
            QueryError: If the update fails.
        """
        try:
            # Process data for database
            processed_data = self._process_data_for_db(data)

            response = await asyncio.to_thread(
                lambda: self.table.update(processed_data)
                .eq("id", str(record_id))
                .execute()
            )

            if response.data and len(response.data) > 0:
                return self._model_class(**response.data[0])

            raise RecordNotFoundError(
                table=self._table_name,
                record_id=str(record_id),
            )
        except RecordNotFoundError:
            raise
        except Exception as e:
            raise QueryError(
                f"Failed to update record in {self._table_name}: {e}",
                query="UPDATE",
            )

    async def delete(self, record_id: UUID | str) -> bool:
        """
        Delete a record by its ID.

        Args:
            record_id: The record's unique identifier.

        Returns:
            True if the record was deleted.

        Raises:
            RecordNotFoundError: If the record doesn't exist.
            QueryError: If the delete fails.
        """
        try:
            response = await asyncio.to_thread(
                lambda: self.table.delete()
                .eq("id", str(record_id))
                .execute()
            )

            if response.data and len(response.data) > 0:
                return True

            raise RecordNotFoundError(
                table=self._table_name,
                record_id=str(record_id),
            )
        except RecordNotFoundError:
            raise
        except Exception as e:
            raise QueryError(
                f"Failed to delete record from {self._table_name}: {e}",
                query="DELETE",
            )

    async def count(self, filters: Optional[dict[str, Any]] = None) -> int:
        """
        Count records in the table.

        Args:
            filters: Optional filters to apply.

        Returns:
            Number of matching records.

        Raises:
            QueryError: If the count fails.
        """
        try:
            query = self.table.select("*", count="exact")

            if filters:
                for field, value in filters.items():
                    if value is not None:
                        query = query.eq(field, str(value) if isinstance(value, UUID) else value)

            response = await asyncio.to_thread(lambda: query.execute())
            return response.count or 0
        except Exception as e:
            raise QueryError(
                f"Failed to count records in {self._table_name}: {e}",
                query="COUNT",
            )

    async def exists(self, record_id: UUID | str) -> bool:
        """
        Check if a record exists.

        Args:
            record_id: The record's unique identifier.

        Returns:
            True if the record exists.
        """
        try:
            response = await asyncio.to_thread(
                lambda: self.table.select("id")
                .eq("id", str(record_id))
                .execute()
            )
            return len(response.data) > 0
        except Exception:
            return False

    def _process_data_for_db(self, data: dict[str, Any]) -> dict[str, Any]:
        """Convert Python types to database-compatible types."""
        processed = {}
        for key, value in data.items():
            if isinstance(value, UUID):
                processed[key] = str(value)
            elif hasattr(value, "value"):  # Enum
                processed[key] = value.value
            elif value is not None:
                processed[key] = value
        return processed


class MessagesTable(TableOperations[Message]):
    """Operations specific to the messages table."""

    def __init__(self, client: Client) -> None:
        super().__init__(client, "messages", Message)

    async def create_message(self, user_id: UUID, data: MessageCreate) -> Message:
        """
        Create a new message.

        Args:
            user_id: The owner user's ID.
            data: Message creation data.

        Returns:
            The created message.
        """
        message_data = data.model_dump()
        message_data["user_id"] = user_id
        message_data["message_id"] = f"<{UUID()}@unitmail.local>"
        return await self.create(message_data)

    async def update_message(
        self,
        message_id: UUID,
        data: MessageUpdate,
    ) -> Message:
        """
        Update a message.

        Args:
            message_id: The message ID.
            data: Fields to update.

        Returns:
            The updated message.
        """
        update_data = data.model_dump(exclude_unset=True)
        return await self.update(message_id, update_data)

    async def get_by_user(
        self,
        user_id: UUID,
        folder_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Message]:
        """
        Get messages for a user, optionally filtered by folder.

        Args:
            user_id: The user's ID.
            folder_id: Optional folder to filter by.
            limit: Maximum number of messages.
            offset: Pagination offset.

        Returns:
            List of messages.
        """
        filters = {"user_id": user_id}
        if folder_id:
            filters["folder_id"] = folder_id

        return await self.get_all(
            limit=limit,
            offset=offset,
            order_by="created_at",
            ascending=False,
            filters=filters,
        )

    async def mark_as_read(self, message_id: UUID) -> Message:
        """Mark a message as read."""
        return await self.update(message_id, {"is_read": True})

    async def mark_as_unread(self, message_id: UUID) -> Message:
        """Mark a message as unread."""
        return await self.update(message_id, {"is_read": False})

    async def toggle_star(self, message_id: UUID) -> Message:
        """Toggle the starred status of a message."""
        message = await self.get_by_id(message_id)
        return await self.update(message_id, {"is_starred": not message.is_starred})


class ContactsTable(TableOperations[Contact]):
    """Operations specific to the contacts table."""

    def __init__(self, client: Client) -> None:
        super().__init__(client, "contacts", Contact)

    async def create_contact(self, user_id: UUID, data: ContactCreate) -> Contact:
        """
        Create a new contact.

        Args:
            user_id: The owner user's ID.
            data: Contact creation data.

        Returns:
            The created contact.
        """
        contact_data = data.model_dump()
        contact_data["user_id"] = user_id
        return await self.create(contact_data)

    async def update_contact(
        self,
        contact_id: UUID,
        data: ContactUpdate,
    ) -> Contact:
        """
        Update a contact.

        Args:
            contact_id: The contact ID.
            data: Fields to update.

        Returns:
            The updated contact.
        """
        update_data = data.model_dump(exclude_unset=True)
        return await self.update(contact_id, update_data)

    async def get_by_user(
        self,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Contact]:
        """
        Get contacts for a user.

        Args:
            user_id: The user's ID.
            limit: Maximum number of contacts.
            offset: Pagination offset.

        Returns:
            List of contacts.
        """
        return await self.get_all(
            limit=limit,
            offset=offset,
            order_by="name",
            ascending=True,
            filters={"user_id": user_id},
        )

    async def get_by_email(self, user_id: UUID, email: str) -> Optional[Contact]:
        """
        Get a contact by email address.

        Args:
            user_id: The user's ID.
            email: The email address to search for.

        Returns:
            The contact if found, None otherwise.
        """
        try:
            response = await asyncio.to_thread(
                lambda: self.table.select("*")
                .eq("user_id", str(user_id))
                .eq("email", email)
                .execute()
            )

            if response.data and len(response.data) > 0:
                return Contact(**response.data[0])
            return None
        except Exception:
            return None

    async def get_favorites(self, user_id: UUID) -> list[Contact]:
        """Get favorite contacts for a user."""
        return await self.get_all(
            filters={"user_id": user_id, "is_favorite": True},
            order_by="name",
        )


class QueueTable(TableOperations[QueueItem]):
    """Operations specific to the queue table."""

    def __init__(self, client: Client) -> None:
        super().__init__(client, "queue", QueueItem)

    async def get_pending(self, limit: int = 10) -> list[QueueItem]:
        """
        Get pending queue items for processing.

        Args:
            limit: Maximum number of items to fetch.

        Returns:
            List of pending queue items.
        """
        try:
            response = await asyncio.to_thread(
                lambda: self.table.select("*")
                .eq("status", "pending")
                .order("priority", desc=True)
                .order("created_at")
                .limit(limit)
                .execute()
            )
            return [QueueItem(**item) for item in response.data]
        except Exception as e:
            raise QueryError(f"Failed to get pending queue items: {e}")

    async def mark_processing(self, item_id: UUID) -> QueueItem:
        """Mark a queue item as processing."""
        return await self.update(item_id, {"status": "processing"})

    async def mark_completed(self, item_id: UUID) -> QueueItem:
        """Mark a queue item as completed."""
        return await self.update(item_id, {"status": "completed"})

    async def mark_failed(
        self,
        item_id: UUID,
        error_message: str,
    ) -> QueueItem:
        """
        Mark a queue item as failed.

        Args:
            item_id: The queue item ID.
            error_message: The error message.

        Returns:
            The updated queue item.
        """
        item = await self.get_by_id(item_id)
        new_attempts = item.attempts + 1

        if new_attempts >= item.max_attempts:
            status = "failed"
        else:
            status = "retrying"

        return await self.update(
            item_id,
            {
                "status": status,
                "attempts": new_attempts,
                "error_message": error_message,
            },
        )

    async def retry(self, item_id: UUID) -> QueueItem:
        """Reset a queue item for retry."""
        return await self.update(
            item_id,
            {
                "status": "pending",
                "error_message": None,
            },
        )


class ConfigTable(TableOperations[Config]):
    """Operations specific to the config table."""

    def __init__(self, client: Client) -> None:
        super().__init__(client, "config", Config)

    async def get_value(
        self,
        key: str,
        user_id: Optional[UUID] = None,
        default: Any = None,
    ) -> Any:
        """
        Get a configuration value.

        Args:
            key: The configuration key.
            user_id: Optional user ID for user-specific config.
            default: Default value if not found.

        Returns:
            The configuration value or default.
        """
        try:
            query = self.table.select("value").eq("key", key)

            if user_id:
                query = query.eq("user_id", str(user_id))
            else:
                query = query.is_("user_id", "null")

            response = await asyncio.to_thread(lambda: query.execute())

            if response.data and len(response.data) > 0:
                return response.data[0]["value"]
            return default
        except Exception:
            return default

    async def set_value(
        self,
        key: str,
        value: Any,
        user_id: Optional[UUID] = None,
        description: Optional[str] = None,
        is_secret: bool = False,
        category: str = "general",
    ) -> Config:
        """
        Set a configuration value (upsert).

        Args:
            key: The configuration key.
            value: The value to set.
            user_id: Optional user ID for user-specific config.
            description: Optional description.
            is_secret: Whether the value is secret.
            category: Configuration category.

        Returns:
            The configuration record.
        """
        try:
            data = {
                "key": key,
                "value": value,
                "user_id": str(user_id) if user_id else None,
                "description": description,
                "is_secret": is_secret,
                "category": category,
            }

            response = await asyncio.to_thread(
                lambda: self.table.upsert(
                    data,
                    on_conflict="key,user_id",
                ).execute()
            )

            if response.data:
                return Config(**response.data[0])

            raise QueryError("Failed to set configuration value")
        except Exception as e:
            raise QueryError(f"Failed to set configuration value: {e}")

    async def get_by_category(
        self,
        category: str,
        user_id: Optional[UUID] = None,
    ) -> list[Config]:
        """
        Get all configuration values in a category.

        Args:
            category: The configuration category.
            user_id: Optional user ID for user-specific config.

        Returns:
            List of configuration records.
        """
        filters = {"category": category}
        if user_id:
            filters["user_id"] = user_id

        return await self.get_all(filters=filters, order_by="key")

    async def delete_key(
        self,
        key: str,
        user_id: Optional[UUID] = None,
    ) -> bool:
        """
        Delete a configuration key.

        Args:
            key: The configuration key.
            user_id: Optional user ID for user-specific config.

        Returns:
            True if deleted.
        """
        try:
            query = self.table.delete().eq("key", key)

            if user_id:
                query = query.eq("user_id", str(user_id))
            else:
                query = query.is_("user_id", "null")

            response = await asyncio.to_thread(lambda: query.execute())
            return len(response.data) > 0
        except Exception:
            return False


class FoldersTable(TableOperations[Folder]):
    """Operations specific to the folders table."""

    def __init__(self, client: Client) -> None:
        super().__init__(client, "folders", Folder)

    async def create_folder(self, user_id: UUID, data: FolderCreate) -> Folder:
        """
        Create a new folder.

        Args:
            user_id: The owner user's ID.
            data: Folder creation data.

        Returns:
            The created folder.
        """
        folder_data = data.model_dump()
        folder_data["user_id"] = user_id
        return await self.create(folder_data)

    async def update_folder(
        self,
        folder_id: UUID,
        data: FolderUpdate,
    ) -> Folder:
        """
        Update a folder.

        Args:
            folder_id: The folder ID.
            data: Fields to update.

        Returns:
            The updated folder.
        """
        update_data = data.model_dump(exclude_unset=True)
        return await self.update(folder_id, update_data)

    async def get_by_user(self, user_id: UUID) -> list[Folder]:
        """
        Get all folders for a user.

        Args:
            user_id: The user's ID.

        Returns:
            List of folders.
        """
        return await self.get_all(
            filters={"user_id": user_id},
            order_by="sort_order",
        )

    async def get_system_folders(self, user_id: UUID) -> list[Folder]:
        """Get system folders for a user."""
        return await self.get_all(
            filters={"user_id": user_id, "is_system": True},
            order_by="sort_order",
        )

    async def increment_message_count(
        self,
        folder_id: UUID,
        unread: bool = False,
    ) -> None:
        """
        Increment message count for a folder.

        Args:
            folder_id: The folder ID.
            unread: Whether to also increment unread count.
        """
        folder = await self.get_by_id(folder_id)
        update_data = {"message_count": folder.message_count + 1}
        if unread:
            update_data["unread_count"] = folder.unread_count + 1
        await self.update(folder_id, update_data)

    async def decrement_message_count(
        self,
        folder_id: UUID,
        unread: bool = False,
    ) -> None:
        """
        Decrement message count for a folder.

        Args:
            folder_id: The folder ID.
            unread: Whether to also decrement unread count.
        """
        folder = await self.get_by_id(folder_id)
        update_data = {"message_count": max(0, folder.message_count - 1)}
        if unread:
            update_data["unread_count"] = max(0, folder.unread_count - 1)
        await self.update(folder_id, update_data)


class MeshPeersTable(TableOperations[MeshPeer]):
    """Operations specific to the mesh_peers table."""

    def __init__(self, client: Client) -> None:
        super().__init__(client, "mesh_peers", MeshPeer)

    async def get_by_peer_id(self, peer_id: str) -> Optional[MeshPeer]:
        """
        Get a peer by its peer ID.

        Args:
            peer_id: The peer's unique identifier.

        Returns:
            The peer if found, None otherwise.
        """
        try:
            response = await asyncio.to_thread(
                lambda: self.table.select("*")
                .eq("peer_id", peer_id)
                .execute()
            )

            if response.data and len(response.data) > 0:
                return MeshPeer(**response.data[0])
            return None
        except Exception:
            return None

    async def get_online_peers(self) -> list[MeshPeer]:
        """Get all online peers."""
        return await self.get_all(
            filters={"status": "online"},
            order_by="priority",
            ascending=False,
        )

    async def get_trusted_peers(self) -> list[MeshPeer]:
        """Get all trusted peers."""
        return await self.get_all(
            filters={"is_trusted": True},
            order_by="priority",
            ascending=False,
        )

    async def update_status(
        self,
        peer_id: str,
        status: str,
        error: Optional[str] = None,
    ) -> Optional[MeshPeer]:
        """
        Update a peer's status.

        Args:
            peer_id: The peer's unique identifier.
            status: The new status.
            error: Optional error message.

        Returns:
            The updated peer if found.
        """
        peer = await self.get_by_peer_id(peer_id)
        if peer:
            update_data = {"status": status}
            if status == "online":
                from datetime import datetime
                update_data["last_seen"] = datetime.utcnow().isoformat()
            if error:
                update_data["last_error"] = error
            return await self.update(peer.id, update_data)
        return None

    async def register_peer(
        self,
        peer_id: str,
        host: str,
        port: int,
        public_key: Optional[str] = None,
        capabilities: Optional[list[str]] = None,
    ) -> MeshPeer:
        """
        Register a new peer or update existing.

        Args:
            peer_id: The peer's unique identifier.
            host: The peer's hostname or IP.
            port: The peer's port.
            public_key: Optional public key.
            capabilities: Optional list of capabilities.

        Returns:
            The registered peer.
        """
        existing = await self.get_by_peer_id(peer_id)

        data = {
            "peer_id": peer_id,
            "host": host,
            "port": port,
            "public_key": public_key,
            "capabilities": capabilities or [],
            "status": "online",
        }

        if existing:
            return await self.update(existing.id, data)
        else:
            return await self.create(data)


class UsersTable(TableOperations[User]):
    """Operations specific to the users table."""

    def __init__(self, client: Client) -> None:
        super().__init__(client, "users", User)

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get a user by email address.

        Args:
            email: The email address.

        Returns:
            The user if found, None otherwise.
        """
        try:
            response = await asyncio.to_thread(
                lambda: self.table.select("*")
                .eq("email", email)
                .execute()
            )

            if response.data and len(response.data) > 0:
                return User(**response.data[0])
            return None
        except Exception:
            return None

    async def get_by_username(self, username: str) -> Optional[User]:
        """
        Get a user by username.

        Args:
            username: The username.

        Returns:
            The user if found, None otherwise.
        """
        try:
            response = await asyncio.to_thread(
                lambda: self.table.select("*")
                .eq("username", username.lower())
                .execute()
            )

            if response.data and len(response.data) > 0:
                return User(**response.data[0])
            return None
        except Exception:
            return None

    async def update_last_login(self, user_id: UUID) -> User:
        """Update the last login timestamp."""
        from datetime import datetime
        return await self.update(user_id, {"last_login": datetime.utcnow().isoformat()})


class SupabaseClient:
    """
    Singleton Supabase client wrapper for unitMail.

    Provides connection management and access to table-specific
    operations with proper typing and error handling.
    """

    _instance: Optional["SupabaseClient"] = None
    _client: Optional[Client] = None

    def __new__(cls) -> "SupabaseClient":
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the client if not already initialized."""
        if self._client is None:
            self._initialize_client()

    def _initialize_client(self) -> None:
        """
        Initialize the Supabase client from configuration.

        Raises:
            ConnectionError: If the client cannot be initialized.
        """
        try:
            settings = get_settings()

            options = ClientOptions(
                auto_refresh_token=True,
                persist_session=True,
            )

            self._client = create_client(
                settings.database.url,
                settings.database.key,
                options=options,
            )
        except Exception as e:
            raise ConnectionError(
                f"Failed to initialize Supabase client: {e}",
                details={"error": str(e)},
            )

    @property
    def client(self) -> Client:
        """Get the underlying Supabase client."""
        if self._client is None:
            self._initialize_client()
        return self._client  # type: ignore

    @property
    def messages(self) -> MessagesTable:
        """Get the messages table operations."""
        return MessagesTable(self.client)

    @property
    def contacts(self) -> ContactsTable:
        """Get the contacts table operations."""
        return ContactsTable(self.client)

    @property
    def queue(self) -> QueueTable:
        """Get the queue table operations."""
        return QueueTable(self.client)

    @property
    def config(self) -> ConfigTable:
        """Get the config table operations."""
        return ConfigTable(self.client)

    @property
    def folders(self) -> FoldersTable:
        """Get the folders table operations."""
        return FoldersTable(self.client)

    @property
    def mesh_peers(self) -> MeshPeersTable:
        """Get the mesh_peers table operations."""
        return MeshPeersTable(self.client)

    @property
    def users(self) -> UsersTable:
        """Get the users table operations."""
        return UsersTable(self.client)

    async def health_check(self) -> bool:
        """
        Check if the database connection is healthy.

        Returns:
            True if the connection is healthy.
        """
        try:
            # Try a simple query
            await asyncio.to_thread(
                lambda: self.client.table("config").select("key").limit(1).execute()
            )
            return True
        except Exception:
            return False

    @asynccontextmanager
    async def transaction(self):
        """
        Context manager for database transactions.

        Note: Supabase doesn't support transactions in the same way as
        traditional databases. This is a placeholder for future implementation
        using Supabase Edge Functions or direct PostgreSQL connections.

        Raises:
            TransactionError: If the transaction fails.
        """
        # TODO: Implement proper transaction support when available
        try:
            yield self
        except Exception as e:
            raise TransactionError(f"Transaction failed: {e}")

    def close(self) -> None:
        """Close the client connection."""
        # Supabase Python client doesn't require explicit closing,
        # but we reset the instance for clean re-initialization
        SupabaseClient._client = None
        SupabaseClient._instance = None


def get_db() -> SupabaseClient:
    """
    Get the database client instance.

    This is the primary entry point for database operations.

    Returns:
        SupabaseClient instance.
    """
    return SupabaseClient()
