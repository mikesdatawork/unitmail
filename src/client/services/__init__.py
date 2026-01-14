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
from .date_format_service import (
    DateFormatService,
    DateFormat,
    get_date_format_service,
    format_date,
    format_date_with_time,
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
    # Date format service
    "DateFormatService",
    "DateFormat",
    "get_date_format_service",
    "format_date",
    "format_date_with_time",
]
