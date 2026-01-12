"""
unitMail client services.

This module provides service classes for client-side operations
including search, sync, settings, and data management.
"""

from .search_service import (
    SearchService,
    SearchCriteria,
    SearchResult,
    SearchResults,
    SearchSortOrder,
    SearchResultCache,
    SavedSearch,
    SearchHistoryEntry,
    SearchError,
)
from .settings_service import (
    SettingsService,
    Settings,
    AccountSettings,
    ServerSettings,
    SecuritySettings,
    AppearanceSettings,
    NotificationSettings,
    AdvancedSettings,
    ThemeMode,
    get_settings_service,
)

__all__ = [
    # Search service
    "SearchService",
    "SearchCriteria",
    "SearchResult",
    "SearchResults",
    "SearchSortOrder",
    "SearchResultCache",
    "SavedSearch",
    "SearchHistoryEntry",
    "SearchError",
    # Settings service
    "SettingsService",
    "Settings",
    "AccountSettings",
    "ServerSettings",
    "SecuritySettings",
    "AppearanceSettings",
    "NotificationSettings",
    "AdvancedSettings",
    "ThemeMode",
    "get_settings_service",
]
