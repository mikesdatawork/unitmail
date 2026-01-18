"""
unitMail Search Service.

This module provides the SearchService class for executing searches
against the SQLite database, including full-text search using FTS5,
advanced filtering, result caching, and search history management.
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from common.storage import EmailStorage, get_storage

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
            "date_from": (
                self.date_from.isoformat() if self.date_from else None
            ),
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
            date_from=(
                datetime.fromisoformat(data["date_from"])
                if data.get("date_from")
                else None
            ),
            date_to=(
                datetime.fromisoformat(data["date_to"])
                if data.get("date_to")
                else None
            ),
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
        id: Message ID.
        message_id: RFC 5322 Message-ID.
        folder_id: Folder ID.
        from_address: Sender email address.
        to_addresses: List of recipient addresses.
        subject: Message subject.
        body_preview: First 200 characters of body.
        received_at: Message received timestamp.
        is_read: Whether message is read.
        is_starred: Whether message is starred.
        encrypted: Whether message is encrypted.
        rank: Relevance rank from FTS (if applicable).
        has_attachments: Whether message has attachments.
    """

    id: int
    message_id: str
    folder_id: Optional[int]
    from_address: str
    to_addresses: List[str]
    subject: Optional[str]
    body_preview: Optional[str]
    received_at: datetime
    is_read: bool
    is_starred: bool
    encrypted: bool
    rank: Optional[float] = None
    has_attachments: bool = False

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "SearchResult":
        """Create SearchResult from SQLite query result row."""
        # Handle to_addresses - may be JSON string or list
        to_addresses = row.get("to_addresses", [])
        if isinstance(to_addresses, str):
            try:
                to_addresses = json.loads(to_addresses)
            except json.JSONDecodeError:
                to_addresses = [to_addresses] if to_addresses else []

        # Parse received_at
        received_at = row.get("received_at")
        if isinstance(received_at, str):
            received_at = datetime.fromisoformat(
                received_at.replace("Z", "+00:00")
            )
        elif received_at is None:
            received_at = datetime.now()

        # Get body preview
        body_text = row.get("body_text", "") or ""
        body_preview = body_text[:200] if body_text else None

        return cls(
            id=row["id"],
            message_id=row.get("message_id", ""),
            folder_id=row.get("folder_id"),
            from_address=row.get("from_address", ""),
            to_addresses=(
                to_addresses if isinstance(to_addresses, list) else []
            ),
            subject=row.get("subject"),
            body_preview=body_preview,
            received_at=received_at,
            is_read=bool(row.get("is_read", False)),
            is_starred=bool(row.get("is_starred", False)),
            encrypted=bool(row.get("is_encrypted", False)),
            rank=row.get("rank"),
            has_attachments=bool(row.get("has_attachments", False)),
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
            oldest_key = min(
                self._cache.keys(), key=lambda k: self._cache[k][1]
            )
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
            if (
                results.criteria.folder_id == folder_id
                or results.criteria.folder_id is None
            ):
                keys_to_remove.append(key)
        for key in keys_to_remove:
            del self._cache[key]


class SearchService:
    """
    Service for executing message searches against SQLite using FTS5.

    Provides methods for:
    - Quick search (simple text query)
    - Advanced search (multiple filters)
    - Search history management
    - Saved searches
    - Result caching
    """

    MAX_HISTORY_SIZE = 50
    MAX_SAVED_SEARCHES = 20

    def __init__(self, storage: Optional[EmailStorage] = None) -> None:
        """
        Initialize the search service.

        Args:
            storage: EmailStorage instance for database access.
        """
        self._storage = storage or get_storage()
        self._cache = SearchResultCache()
        self._history: List[SearchHistoryEntry] = []
        self._saved_searches: Dict[str, SavedSearch] = {}
        self._search_listeners: List[Callable[[SearchResults], None]] = []

        logger.info("SearchService initialized with SQLite FTS5")

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

    def quick_search(
        self,
        query: str,
        folder_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> SearchResults:
        """
        Perform a quick full-text search using FTS5.

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
            folder_id=str(folder_id) if folder_id else None,
            sort_order=SearchSortOrder.RELEVANCE,
            limit=limit,
            offset=offset,
        )
        return self.search(criteria)

    def search(
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
        if criteria.query:
            results = self._execute_fts_search(criteria)
        else:
            results = self._execute_filter_search(criteria)

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

    def _execute_fts_search(self, criteria: SearchCriteria) -> SearchResults:
        """
        Execute a full-text search using SQLite FTS5.

        Args:
            criteria: Search criteria.

        Returns:
            SearchResults from the search.
        """
        try:
            # Get folder name if folder_id provided
            folder_name = None
            if criteria.folder_id:
                try:
                    folder_id = int(criteria.folder_id)
                    folders = self._storage.get_folders()
                    for f in folders:
                        if f["id"] == folder_id:
                            folder_name = f["name"]
                            break
                except (ValueError, TypeError):
                    pass

            # Use storage's FTS5 search method
            rows = self._storage.search_messages(
                query=criteria.query or "",
                folder_name=folder_name,
                limit=criteria.limit,
            )

            results = [SearchResult.from_sqlite_row(dict(row)) for row in rows]

            # Apply additional filters
            results = self._apply_filters(results, criteria)

            # Apply sorting
            results = self._sort_results(results, criteria.sort_order)

            # Apply offset
            if criteria.offset > 0:
                results = results[criteria.offset :]

            # Get total count
            total_count = len(results)
            if len(results) == criteria.limit:
                total_count = criteria.offset + criteria.limit + 1

            return SearchResults(
                results=results[: criteria.limit],
                total_count=total_count,
                criteria=criteria,
            )

        except Exception as e:
            logger.error(f"FTS search failed: {e}")
            raise SearchError(f"Search failed: {e}") from e

    def _execute_filter_search(
        self, criteria: SearchCriteria
    ) -> SearchResults:
        """
        Execute a search using filters without FTS.

        Args:
            criteria: Search criteria with filters.

        Returns:
            SearchResults from the search.
        """
        try:
            # Get all messages from the folder or all folders
            folder_name = None
            if criteria.folder_id:
                try:
                    folder_id = int(criteria.folder_id)
                    folders = self._storage.get_folders()
                    for f in folders:
                        if f["id"] == folder_id:
                            folder_name = f["name"]
                            break
                except (ValueError, TypeError):
                    pass

            if folder_name:
                rows = self._storage.get_messages_by_folder(folder_name)
            else:
                # Get messages from all folders
                rows = []
                for folder in self._storage.get_folders():
                    rows.extend(
                        self._storage.get_messages_by_folder(folder["name"])
                    )

            results = [SearchResult.from_sqlite_row(dict(row)) for row in rows]

            # Apply filters
            results = self._apply_filters(results, criteria)

            # Apply sorting
            results = self._sort_results(results, criteria.sort_order)

            # Apply pagination
            total_count = len(results)
            results = results[
                criteria.offset : criteria.offset + criteria.limit
            ]

            return SearchResults(
                results=results,
                total_count=total_count,
                criteria=criteria,
            )

        except Exception as e:
            logger.error(f"Filter search failed: {e}")
            raise SearchError(f"Search failed: {e}") from e

    def _apply_filters(
        self,
        results: List[SearchResult],
        criteria: SearchCriteria,
    ) -> List[SearchResult]:
        """Apply additional filters to search results."""
        filtered = results

        if criteria.from_address:
            filtered = [
                r
                for r in filtered
                if criteria.from_address.lower() in r.from_address.lower()
            ]

        if criteria.to_address:
            filtered = [
                r
                for r in filtered
                if any(
                    criteria.to_address.lower() in addr.lower()
                    for addr in r.to_addresses
                )
            ]

        if criteria.subject_contains:
            filtered = [
                r
                for r in filtered
                if r.subject
                and criteria.subject_contains.lower() in r.subject.lower()
            ]

        if criteria.date_from:
            filtered = [
                r for r in filtered if r.received_at >= criteria.date_from
            ]

        if criteria.date_to:
            filtered = [
                r for r in filtered if r.received_at <= criteria.date_to
            ]

        if criteria.is_starred is not None:
            filtered = [
                r for r in filtered if r.is_starred == criteria.is_starred
            ]

        if criteria.is_unread is not None:
            filtered = [r for r in filtered if r.is_read != criteria.is_unread]

        if criteria.is_encrypted is not None:
            filtered = [
                r for r in filtered if r.encrypted == criteria.is_encrypted
            ]

        if criteria.has_attachments is not None:
            filtered = [
                r
                for r in filtered
                if r.has_attachments == criteria.has_attachments
            ]

        return filtered

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

    def search_by_sender(
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
        return self.search(criteria)

    def search_by_date_range(
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
        return self.search(criteria)

    def search_unread(
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
        return self.search(criteria)

    def search_starred(
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
        return self.search(criteria)

    def search_with_attachments(
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
        return self.search(criteria)

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

    def get_search_history(self, limit: int = 10) -> List[SearchHistoryEntry]:
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

    def run_saved_search(self, search_id: str) -> Optional[SearchResults]:
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

        return self.search(saved.criteria)

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
                    "last_used": (
                        saved.last_used.isoformat()
                        if saved.last_used
                        else None
                    ),
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
                    last_used=(
                        datetime.fromisoformat(item["last_used"])
                        if item.get("last_used")
                        else None
                    ),
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


# Singleton instance
_search_service: Optional[SearchService] = None


def get_search_service() -> SearchService:
    """
    Get the global search service instance.

    Returns:
        The singleton SearchService instance.
    """
    global _search_service

    if _search_service is None:
        _search_service = SearchService()

    return _search_service
