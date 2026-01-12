"""
unitMail Search Service.

This module provides the SearchService class for executing searches
against the Supabase database, including full-text search, advanced
filtering, result caching, and search history management.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


class SearchSortOrder(Enum):
    """Sort order options for search results."""

    DATE_DESC = "date_desc"
    DATE_ASC = "date_asc"
    RELEVANCE = "relevance"
    FROM_ASC = "from_asc"
    FROM_DESC = "from_desc"
    SUBJECT_ASC = "subject_asc"
    SUBJECT_DESC = "subject_desc"


@dataclass
class SearchCriteria:
    """
    Search criteria for advanced message search.

    Attributes:
        query: Full-text search query string.
        from_address: Filter by sender address (partial match).
        to_address: Filter by recipient address (partial match).
        subject_contains: Filter by subject text (partial match).
        body_contains: Filter by body text (uses FTS).
        date_from: Filter messages received after this date.
        date_to: Filter messages received before this date.
        has_attachments: Filter by attachment presence.
        is_starred: Filter by starred status.
        is_unread: Filter by unread status.
        is_encrypted: Filter by encryption status.
        folder_id: Filter by specific folder.
        sort_order: Sort order for results.
        limit: Maximum number of results.
        offset: Offset for pagination.
    """

    query: Optional[str] = None
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    subject_contains: Optional[str] = None
    body_contains: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    has_attachments: Optional[bool] = None
    is_starred: Optional[bool] = None
    is_unread: Optional[bool] = None
    is_encrypted: Optional[bool] = None
    folder_id: Optional[str] = None
    sort_order: SearchSortOrder = SearchSortOrder.DATE_DESC
    limit: int = 50
    offset: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert criteria to dictionary for serialization."""
        return {
            "query": self.query,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "subject_contains": self.subject_contains,
            "body_contains": self.body_contains,
            "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "has_attachments": self.has_attachments,
            "is_starred": self.is_starred,
            "is_unread": self.is_unread,
            "is_encrypted": self.is_encrypted,
            "folder_id": self.folder_id,
            "sort_order": self.sort_order.value,
            "limit": self.limit,
            "offset": self.offset,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchCriteria":
        """Create criteria from dictionary."""
        return cls(
            query=data.get("query"),
            from_address=data.get("from_address"),
            to_address=data.get("to_address"),
            subject_contains=data.get("subject_contains"),
            body_contains=data.get("body_contains"),
            date_from=datetime.fromisoformat(data["date_from"])
            if data.get("date_from")
            else None,
            date_to=datetime.fromisoformat(data["date_to"])
            if data.get("date_to")
            else None,
            has_attachments=data.get("has_attachments"),
            is_starred=data.get("is_starred"),
            is_unread=data.get("is_unread"),
            is_encrypted=data.get("is_encrypted"),
            folder_id=data.get("folder_id"),
            sort_order=SearchSortOrder(data.get("sort_order", "date_desc")),
            limit=data.get("limit", 50),
            offset=data.get("offset", 0),
        )

    def get_cache_key(self) -> str:
        """Generate a cache key for these criteria."""
        data = self.to_dict()
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.md5(serialized.encode()).hexdigest()

    def is_empty(self) -> bool:
        """Check if all search criteria are empty."""
        return not any(
            [
                self.query,
                self.from_address,
                self.to_address,
                self.subject_contains,
                self.body_contains,
                self.date_from,
                self.date_to,
                self.has_attachments is not None,
                self.is_starred is not None,
                self.is_unread is not None,
                self.is_encrypted is not None,
                self.folder_id,
            ]
        )

    def get_description(self) -> str:
        """Get a human-readable description of the search criteria."""
        parts = []

        if self.query:
            parts.append(f'"{self.query}"')
        if self.from_address:
            parts.append(f"from:{self.from_address}")
        if self.to_address:
            parts.append(f"to:{self.to_address}")
        if self.subject_contains:
            parts.append(f"subject:{self.subject_contains}")
        if self.date_from and self.date_to:
            parts.append(
                f"date:{self.date_from.strftime('%Y-%m-%d')}"
                f"-{self.date_to.strftime('%Y-%m-%d')}"
            )
        elif self.date_from:
            parts.append(f"after:{self.date_from.strftime('%Y-%m-%d')}")
        elif self.date_to:
            parts.append(f"before:{self.date_to.strftime('%Y-%m-%d')}")
        if self.has_attachments:
            parts.append("has:attachment")
        if self.is_starred:
            parts.append("is:starred")
        if self.is_unread:
            parts.append("is:unread")
        if self.is_encrypted:
            parts.append("is:encrypted")

        return " ".join(parts) if parts else "All messages"


@dataclass
class SearchResult:
    """
    A single search result item.

    Attributes:
        id: Message UUID.
        message_id: RFC 5322 Message-ID.
        folder_id: Folder UUID.
        from_address: Sender email address.
        to_addresses: List of recipient addresses.
        subject: Message subject.
        body_preview: First 200 characters of body.
        received_at: Message received timestamp.
        flags: Message flags (read, starred, etc.).
        encrypted: Whether message is encrypted.
        rank: Relevance rank from FTS (if applicable).
        has_attachments: Whether message has attachments.
    """

    id: str
    message_id: str
    folder_id: Optional[str]
    from_address: str
    to_addresses: List[str]
    subject: Optional[str]
    body_preview: Optional[str]
    received_at: datetime
    flags: Dict[str, bool]
    encrypted: bool
    rank: Optional[float] = None
    has_attachments: bool = False

    @property
    def is_read(self) -> bool:
        """Check if message is read."""
        return self.flags.get("read", False)

    @property
    def is_starred(self) -> bool:
        """Check if message is starred."""
        return self.flags.get("starred", False)

    @classmethod
    def from_supabase_row(cls, row: Dict[str, Any]) -> "SearchResult":
        """Create SearchResult from Supabase query result row."""
        # Handle attachments - check if attachments field exists and is non-empty
        attachments = row.get("attachments", [])
        has_attachments = bool(attachments and len(attachments) > 0)

        return cls(
            id=str(row["id"]),
            message_id=row["message_id"],
            folder_id=str(row["folder"]) if row.get("folder") else None,
            from_address=row["from_addr"],
            to_addresses=row.get("to_addr", []),
            subject=row.get("subject"),
            body_preview=row.get("body_preview"),
            received_at=datetime.fromisoformat(row["received_at"].replace("Z", "+00:00"))
            if isinstance(row["received_at"], str)
            else row["received_at"],
            flags=row.get("flags", {"read": False, "starred": False}),
            encrypted=row.get("encrypted", False),
            rank=row.get("rank"),
            has_attachments=has_attachments,
        )


@dataclass
class SearchResults:
    """
    Collection of search results with metadata.

    Attributes:
        results: List of search result items.
        total_count: Total number of matching results (for pagination).
        criteria: The search criteria used.
        search_time_ms: Time taken to execute search in milliseconds.
        from_cache: Whether results were served from cache.
    """

    results: List[SearchResult]
    total_count: int
    criteria: SearchCriteria
    search_time_ms: float = 0.0
    from_cache: bool = False

    @property
    def has_more(self) -> bool:
        """Check if there are more results available."""
        return self.criteria.offset + len(self.results) < self.total_count


@dataclass
class SavedSearch:
    """
    A saved search configuration.

    Attributes:
        id: Unique identifier for the saved search.
        name: Display name for the search.
        criteria: The search criteria.
        created_at: When the search was saved.
        last_used: When the search was last executed.
        use_count: Number of times the search has been used.
    """

    id: str
    name: str
    criteria: SearchCriteria
    created_at: datetime
    last_used: Optional[datetime] = None
    use_count: int = 0


@dataclass
class SearchHistoryEntry:
    """
    An entry in the search history.

    Attributes:
        query: The search query or description.
        criteria: Full search criteria.
        timestamp: When the search was performed.
        result_count: Number of results returned.
    """

    query: str
    criteria: SearchCriteria
    timestamp: datetime
    result_count: int


class SearchResultCache:
    """
    In-memory cache for search results with TTL support.

    Attributes:
        max_size: Maximum number of cached results.
        ttl_seconds: Time-to-live for cache entries in seconds.
    """

    def __init__(self, max_size: int = 100, ttl_seconds: int = 300) -> None:
        """
        Initialize the cache.

        Args:
            max_size: Maximum number of entries to cache.
            ttl_seconds: Time-to-live for entries in seconds.
        """
        self._cache: Dict[str, Tuple[SearchResults, datetime]] = {}
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds

    def get(self, key: str) -> Optional[SearchResults]:
        """
        Get cached results if available and not expired.

        Args:
            key: Cache key.

        Returns:
            Cached search results or None if not found/expired.
        """
        if key not in self._cache:
            return None

        results, cached_at = self._cache[key]
        if datetime.now() - cached_at > timedelta(seconds=self._ttl_seconds):
            del self._cache[key]
            return None

        return results

    def set(self, key: str, results: SearchResults) -> None:
        """
        Store results in cache.

        Args:
            key: Cache key.
            results: Search results to cache.
        """
        # Evict oldest entries if at capacity
        if len(self._cache) >= self._max_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

        self._cache[key] = (results, datetime.now())

    def invalidate(self, key: Optional[str] = None) -> None:
        """
        Invalidate cache entries.

        Args:
            key: Specific key to invalidate, or None to clear all.
        """
        if key is None:
            self._cache.clear()
        elif key in self._cache:
            del self._cache[key]

    def invalidate_by_folder(self, folder_id: str) -> None:
        """
        Invalidate cache entries that include a specific folder.

        Args:
            folder_id: Folder ID to invalidate.
        """
        keys_to_remove = []
        for key, (results, _) in self._cache.items():
            if results.criteria.folder_id == folder_id or results.criteria.folder_id is None:
                keys_to_remove.append(key)
        for key in keys_to_remove:
            del self._cache[key]


class SearchService:
    """
    Service for executing message searches against Supabase.

    Provides methods for:
    - Quick search (simple text query)
    - Advanced search (multiple filters)
    - Search history management
    - Saved searches
    - Result caching
    """

    MAX_HISTORY_SIZE = 50
    MAX_SAVED_SEARCHES = 20

    def __init__(self, supabase_client: Any) -> None:
        """
        Initialize the search service.

        Args:
            supabase_client: Supabase client instance for database access.
        """
        self._client = supabase_client
        self._cache = SearchResultCache()
        self._history: List[SearchHistoryEntry] = []
        self._saved_searches: Dict[str, SavedSearch] = {}
        self._search_listeners: List[Callable[[SearchResults], None]] = []

        logger.info("SearchService initialized")

    def add_search_listener(
        self, callback: Callable[[SearchResults], None]
    ) -> None:
        """
        Add a listener for search result events.

        Args:
            callback: Function to call when search completes.
        """
        self._search_listeners.append(callback)

    def remove_search_listener(
        self, callback: Callable[[SearchResults], None]
    ) -> None:
        """
        Remove a search result listener.

        Args:
            callback: The callback to remove.
        """
        if callback in self._search_listeners:
            self._search_listeners.remove(callback)

    def _notify_listeners(self, results: SearchResults) -> None:
        """Notify all listeners of search results."""
        for callback in self._search_listeners:
            try:
                callback(results)
            except Exception as e:
                logger.error(f"Error in search listener: {e}")

    async def quick_search(
        self,
        query: str,
        folder_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> SearchResults:
        """
        Perform a quick full-text search.

        Uses the database search_messages function for efficient
        full-text search with relevance ranking.

        Args:
            query: Search query string.
            folder_id: Optional folder to search within.
            limit: Maximum results to return.
            offset: Pagination offset.

        Returns:
            SearchResults with matching messages.
        """
        criteria = SearchCriteria(
            query=query,
            folder_id=folder_id,
            sort_order=SearchSortOrder.RELEVANCE,
            limit=limit,
            offset=offset,
        )
        return await self.search(criteria)

    async def search(
        self,
        criteria: SearchCriteria,
        use_cache: bool = True,
    ) -> SearchResults:
        """
        Execute a search with the given criteria.

        Args:
            criteria: Search criteria to use.
            use_cache: Whether to use cached results if available.

        Returns:
            SearchResults with matching messages.
        """
        import time

        start_time = time.time()

        # Check cache
        cache_key = criteria.get_cache_key()
        if use_cache:
            cached = self._cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for search: {cache_key}")
                cached.from_cache = True
                return cached

        # Execute search based on criteria complexity
        if self._should_use_advanced_search(criteria):
            results = await self._execute_advanced_search(criteria)
        else:
            results = await self._execute_simple_search(criteria)

        # Calculate search time
        search_time_ms = (time.time() - start_time) * 1000
        results.search_time_ms = search_time_ms

        # Cache results
        self._cache.set(cache_key, results)

        # Add to history
        self._add_to_history(criteria, len(results.results))

        # Notify listeners
        self._notify_listeners(results)

        logger.info(
            f"Search completed in {search_time_ms:.2f}ms, "
            f"found {results.total_count} results"
        )

        return results

    def _should_use_advanced_search(self, criteria: SearchCriteria) -> bool:
        """Determine if advanced search function should be used."""
        return any(
            [
                criteria.from_address,
                criteria.to_address,
                criteria.date_from,
                criteria.date_to,
                criteria.is_starred is not None,
                criteria.is_unread is not None,
                criteria.is_encrypted is not None,
            ]
        )

    async def _execute_simple_search(
        self, criteria: SearchCriteria
    ) -> SearchResults:
        """
        Execute a simple full-text search using the database function.

        Args:
            criteria: Search criteria.

        Returns:
            SearchResults from the search.
        """
        try:
            # Call the search_messages database function
            response = await self._client.rpc(
                "search_messages",
                {
                    "search_query": criteria.query or "",
                    "folder_filter": criteria.folder_id,
                    "limit_count": criteria.limit,
                    "offset_count": criteria.offset,
                },
            ).execute()

            results = [
                SearchResult.from_supabase_row(row) for row in response.data
            ]

            # Get total count (approximate for performance)
            total_count = len(results)
            if len(results) == criteria.limit:
                # There might be more results
                total_count = criteria.offset + criteria.limit + 1

            return SearchResults(
                results=results,
                total_count=total_count,
                criteria=criteria,
            )

        except Exception as e:
            logger.error(f"Simple search failed: {e}")
            raise SearchError(f"Search failed: {e}") from e

    async def _execute_advanced_search(
        self, criteria: SearchCriteria
    ) -> SearchResults:
        """
        Execute an advanced search with multiple filters.

        Args:
            criteria: Search criteria with filters.

        Returns:
            SearchResults from the search.
        """
        try:
            # Build parameters for the advanced search function
            params = {
                "search_query": criteria.query if criteria.query else None,
                "folder_filter": criteria.folder_id,
                "from_filter": criteria.from_address,
                "to_filter": criteria.to_address,
                "date_from": criteria.date_from.isoformat()
                if criteria.date_from
                else None,
                "date_to": criteria.date_to.isoformat()
                if criteria.date_to
                else None,
                "is_read": not criteria.is_unread
                if criteria.is_unread is not None
                else None,
                "is_starred": criteria.is_starred,
                "is_encrypted": criteria.is_encrypted,
                "limit_count": criteria.limit,
                "offset_count": criteria.offset,
            }

            response = await self._client.rpc(
                "search_messages_advanced", params
            ).execute()

            results = [
                SearchResult.from_supabase_row(row) for row in response.data
            ]

            # Apply client-side filters for criteria not in the DB function
            if criteria.subject_contains:
                results = [
                    r
                    for r in results
                    if r.subject
                    and criteria.subject_contains.lower() in r.subject.lower()
                ]

            if criteria.has_attachments is not None:
                results = [
                    r for r in results if r.has_attachments == criteria.has_attachments
                ]

            # Apply sorting
            results = self._sort_results(results, criteria.sort_order)

            # Get total count
            total_count = len(results)
            if len(results) == criteria.limit:
                total_count = criteria.offset + criteria.limit + 1

            return SearchResults(
                results=results,
                total_count=total_count,
                criteria=criteria,
            )

        except Exception as e:
            logger.error(f"Advanced search failed: {e}")
            raise SearchError(f"Search failed: {e}") from e

    def _sort_results(
        self,
        results: List[SearchResult],
        sort_order: SearchSortOrder,
    ) -> List[SearchResult]:
        """
        Sort search results by the specified order.

        Args:
            results: List of search results.
            sort_order: Desired sort order.

        Returns:
            Sorted list of results.
        """
        if sort_order == SearchSortOrder.DATE_DESC:
            return sorted(results, key=lambda r: r.received_at, reverse=True)
        elif sort_order == SearchSortOrder.DATE_ASC:
            return sorted(results, key=lambda r: r.received_at)
        elif sort_order == SearchSortOrder.RELEVANCE:
            return sorted(
                results,
                key=lambda r: (r.rank or 0, r.received_at),
                reverse=True,
            )
        elif sort_order == SearchSortOrder.FROM_ASC:
            return sorted(results, key=lambda r: r.from_address.lower())
        elif sort_order == SearchSortOrder.FROM_DESC:
            return sorted(
                results, key=lambda r: r.from_address.lower(), reverse=True
            )
        elif sort_order == SearchSortOrder.SUBJECT_ASC:
            return sorted(results, key=lambda r: (r.subject or "").lower())
        elif sort_order == SearchSortOrder.SUBJECT_DESC:
            return sorted(
                results, key=lambda r: (r.subject or "").lower(), reverse=True
            )
        return results

    async def search_by_sender(
        self,
        sender: str,
        limit: int = 50,
    ) -> SearchResults:
        """
        Search for messages from a specific sender.

        Args:
            sender: Sender email address (partial match).
            limit: Maximum results.

        Returns:
            SearchResults with matching messages.
        """
        criteria = SearchCriteria(
            from_address=sender,
            limit=limit,
        )
        return await self.search(criteria)

    async def search_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        folder_id: Optional[str] = None,
        limit: int = 50,
    ) -> SearchResults:
        """
        Search for messages within a date range.

        Args:
            start_date: Start of date range.
            end_date: End of date range.
            folder_id: Optional folder to search within.
            limit: Maximum results.

        Returns:
            SearchResults with matching messages.
        """
        criteria = SearchCriteria(
            date_from=start_date,
            date_to=end_date,
            folder_id=folder_id,
            limit=limit,
        )
        return await self.search(criteria)

    async def search_unread(
        self,
        folder_id: Optional[str] = None,
        limit: int = 50,
    ) -> SearchResults:
        """
        Search for unread messages.

        Args:
            folder_id: Optional folder to search within.
            limit: Maximum results.

        Returns:
            SearchResults with unread messages.
        """
        criteria = SearchCriteria(
            is_unread=True,
            folder_id=folder_id,
            limit=limit,
        )
        return await self.search(criteria)

    async def search_starred(
        self,
        folder_id: Optional[str] = None,
        limit: int = 50,
    ) -> SearchResults:
        """
        Search for starred messages.

        Args:
            folder_id: Optional folder to search within.
            limit: Maximum results.

        Returns:
            SearchResults with starred messages.
        """
        criteria = SearchCriteria(
            is_starred=True,
            folder_id=folder_id,
            limit=limit,
        )
        return await self.search(criteria)

    async def search_with_attachments(
        self,
        folder_id: Optional[str] = None,
        limit: int = 50,
    ) -> SearchResults:
        """
        Search for messages with attachments.

        Args:
            folder_id: Optional folder to search within.
            limit: Maximum results.

        Returns:
            SearchResults with messages that have attachments.
        """
        criteria = SearchCriteria(
            has_attachments=True,
            folder_id=folder_id,
            limit=limit,
        )
        return await self.search(criteria)

    # Search History Management

    def _add_to_history(
        self, criteria: SearchCriteria, result_count: int
    ) -> None:
        """Add a search to the history."""
        if criteria.is_empty():
            return

        entry = SearchHistoryEntry(
            query=criteria.get_description(),
            criteria=criteria,
            timestamp=datetime.now(),
            result_count=result_count,
        )

        # Remove duplicate if exists
        self._history = [
            h
            for h in self._history
            if h.criteria.get_cache_key() != criteria.get_cache_key()
        ]

        # Add to front
        self._history.insert(0, entry)

        # Trim to max size
        if len(self._history) > self.MAX_HISTORY_SIZE:
            self._history = self._history[: self.MAX_HISTORY_SIZE]

    def get_search_history(
        self, limit: int = 10
    ) -> List[SearchHistoryEntry]:
        """
        Get recent search history.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of recent search history entries.
        """
        return self._history[:limit]

    def clear_search_history(self) -> None:
        """Clear all search history."""
        self._history.clear()
        logger.info("Search history cleared")

    def get_suggestions(self, partial_query: str) -> List[str]:
        """
        Get search suggestions based on history and partial query.

        Args:
            partial_query: Partial search query.

        Returns:
            List of suggested search queries.
        """
        suggestions = []
        partial_lower = partial_query.lower()

        for entry in self._history:
            if partial_lower in entry.query.lower():
                if entry.query not in suggestions:
                    suggestions.append(entry.query)
            if len(suggestions) >= 5:
                break

        return suggestions

    # Saved Searches

    def save_search(
        self,
        name: str,
        criteria: SearchCriteria,
    ) -> SavedSearch:
        """
        Save a search for later reuse.

        Args:
            name: Display name for the saved search.
            criteria: Search criteria to save.

        Returns:
            The saved search object.
        """
        import uuid

        search_id = str(uuid.uuid4())
        saved = SavedSearch(
            id=search_id,
            name=name,
            criteria=criteria,
            created_at=datetime.now(),
        )

        self._saved_searches[search_id] = saved
        logger.info(f"Saved search: {name}")

        return saved

    def get_saved_searches(self) -> List[SavedSearch]:
        """
        Get all saved searches.

        Returns:
            List of saved searches sorted by most recently used.
        """
        searches = list(self._saved_searches.values())
        return sorted(
            searches,
            key=lambda s: s.last_used or s.created_at,
            reverse=True,
        )

    def get_saved_search(self, search_id: str) -> Optional[SavedSearch]:
        """
        Get a saved search by ID.

        Args:
            search_id: The saved search ID.

        Returns:
            The saved search or None if not found.
        """
        return self._saved_searches.get(search_id)

    def delete_saved_search(self, search_id: str) -> bool:
        """
        Delete a saved search.

        Args:
            search_id: The saved search ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        if search_id in self._saved_searches:
            del self._saved_searches[search_id]
            logger.info(f"Deleted saved search: {search_id}")
            return True
        return False

    async def run_saved_search(self, search_id: str) -> Optional[SearchResults]:
        """
        Execute a saved search.

        Args:
            search_id: The saved search ID to run.

        Returns:
            SearchResults or None if saved search not found.
        """
        saved = self._saved_searches.get(search_id)
        if not saved:
            return None

        saved.last_used = datetime.now()
        saved.use_count += 1

        return await self.search(saved.criteria)

    # Cache Management

    def invalidate_cache(self, folder_id: Optional[str] = None) -> None:
        """
        Invalidate cached search results.

        Args:
            folder_id: Specific folder to invalidate, or None for all.
        """
        if folder_id:
            self._cache.invalidate_by_folder(folder_id)
        else:
            self._cache.invalidate()
        logger.debug(f"Cache invalidated for folder: {folder_id or 'all'}")

    # Persistence

    def export_saved_searches(self) -> str:
        """
        Export saved searches as JSON.

        Returns:
            JSON string of saved searches.
        """
        data = []
        for saved in self._saved_searches.values():
            data.append(
                {
                    "id": saved.id,
                    "name": saved.name,
                    "criteria": saved.criteria.to_dict(),
                    "created_at": saved.created_at.isoformat(),
                    "last_used": saved.last_used.isoformat()
                    if saved.last_used
                    else None,
                    "use_count": saved.use_count,
                }
            )
        return json.dumps(data, indent=2)

    def import_saved_searches(self, json_data: str) -> int:
        """
        Import saved searches from JSON.

        Args:
            json_data: JSON string of saved searches.

        Returns:
            Number of searches imported.
        """
        try:
            data = json.loads(json_data)
            count = 0

            for item in data:
                saved = SavedSearch(
                    id=item["id"],
                    name=item["name"],
                    criteria=SearchCriteria.from_dict(item["criteria"]),
                    created_at=datetime.fromisoformat(item["created_at"]),
                    last_used=datetime.fromisoformat(item["last_used"])
                    if item.get("last_used")
                    else None,
                    use_count=item.get("use_count", 0),
                )
                self._saved_searches[saved.id] = saved
                count += 1

            logger.info(f"Imported {count} saved searches")
            return count

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to import saved searches: {e}")
            raise SearchError(f"Invalid saved searches data: {e}") from e


class SearchError(Exception):
    """Exception raised for search-related errors."""

    pass
