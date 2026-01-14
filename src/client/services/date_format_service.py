"""
Date formatting service for unitMail client.

This module provides a centralized, modular date formatting utility
that can be configured via settings and used across all components.
The service supports multiple date formats and emits signals when
the format changes to allow immediate UI updates.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

import gi

gi.require_version("GObject", "2.0")

from gi.repository import GObject

import logging

logger = logging.getLogger(__name__)


class DateFormat(Enum):
    """Supported date format options."""

    # Date only formats
    US = "MM/DD/YYYY"          # 01/13/2026
    EUROPEAN = "DD/MM/YYYY"    # 13/01/2026
    ISO = "YYYY-MM-DD"         # 2026-01-13
    DAY_MONTH_YEAR = "DD MMM YYYY"  # 13 Jan 2026
    MONTH_DAY_YEAR = "MMM DD, YYYY"  # Jan 13, 2026
    # Date and time formats
    US_TIME = "MM/DD/YYYY HH:MM"          # 01/13/2026 14:30
    EUROPEAN_TIME = "DD/MM/YYYY HH:MM"    # 13/01/2026 14:30
    ISO_TIME = "YYYY-MM-DD HH:MM"         # 2026-01-13 14:30
    DAY_MONTH_YEAR_TIME = "DD MMM YYYY HH:MM"  # 13 Jan 2026 14:30
    MONTH_DAY_YEAR_TIME = "MMM DD, YYYY HH:MM"  # Jan 13, 2026 14:30


# Format string mappings for strftime
DATE_FORMAT_PATTERNS = {
    DateFormat.US: "%m/%d/%Y",
    DateFormat.EUROPEAN: "%d/%m/%Y",
    DateFormat.ISO: "%Y-%m-%d",
    DateFormat.DAY_MONTH_YEAR: "%d %b %Y",
    DateFormat.MONTH_DAY_YEAR: "%b %d, %Y",
    DateFormat.US_TIME: "%m/%d/%Y %H:%M",
    DateFormat.EUROPEAN_TIME: "%d/%m/%Y %H:%M",
    DateFormat.ISO_TIME: "%Y-%m-%d %H:%M",
    DateFormat.DAY_MONTH_YEAR_TIME: "%d %b %Y %H:%M",
    DateFormat.MONTH_DAY_YEAR_TIME: "%b %d, %Y %H:%M",
}

# Human-readable labels for the UI
DATE_FORMAT_LABELS = {
    DateFormat.US: "MM/DD/YYYY (US)",
    DateFormat.EUROPEAN: "DD/MM/YYYY (European)",
    DateFormat.ISO: "YYYY-MM-DD (ISO)",
    DateFormat.DAY_MONTH_YEAR: "DD MMM YYYY",
    DateFormat.MONTH_DAY_YEAR: "MMM DD, YYYY",
    DateFormat.US_TIME: "MM/DD/YYYY HH:MM (US with time)",
    DateFormat.EUROPEAN_TIME: "DD/MM/YYYY HH:MM (European with time)",
    DateFormat.ISO_TIME: "YYYY-MM-DD HH:MM (ISO with time)",
    DateFormat.DAY_MONTH_YEAR_TIME: "DD MMM YYYY HH:MM",
    DateFormat.MONTH_DAY_YEAR_TIME: "MMM DD, YYYY HH:MM",
}

# Example dates for preview in settings
DATE_FORMAT_EXAMPLES = {
    DateFormat.US: "01/13/2026",
    DateFormat.EUROPEAN: "13/01/2026",
    DateFormat.ISO: "2026-01-13",
    DateFormat.DAY_MONTH_YEAR: "13 Jan 2026",
    DateFormat.MONTH_DAY_YEAR: "Jan 13, 2026",
    DateFormat.US_TIME: "01/13/2026 14:30",
    DateFormat.EUROPEAN_TIME: "13/01/2026 14:30",
    DateFormat.ISO_TIME: "2026-01-13 14:30",
    DateFormat.DAY_MONTH_YEAR_TIME: "13 Jan 2026 14:30",
    DateFormat.MONTH_DAY_YEAR_TIME: "Jan 13, 2026 14:30",
}


def get_date_format_from_string(format_str: str) -> DateFormat:
    """
    Convert a string representation to DateFormat enum.

    Args:
        format_str: String representation of the format.

    Returns:
        Corresponding DateFormat enum value.
    """
    format_map = {
        "MM/DD/YYYY": DateFormat.US,
        "DD/MM/YYYY": DateFormat.EUROPEAN,
        "YYYY-MM-DD": DateFormat.ISO,
        "DD MMM YYYY": DateFormat.DAY_MONTH_YEAR,
        "MMM DD, YYYY": DateFormat.MONTH_DAY_YEAR,
        "MM/DD/YYYY HH:MM": DateFormat.US_TIME,
        "DD/MM/YYYY HH:MM": DateFormat.EUROPEAN_TIME,
        "YYYY-MM-DD HH:MM": DateFormat.ISO_TIME,
        "DD MMM YYYY HH:MM": DateFormat.DAY_MONTH_YEAR_TIME,
        "MMM DD, YYYY HH:MM": DateFormat.MONTH_DAY_YEAR_TIME,
    }
    return format_map.get(format_str, DateFormat.ISO)


class DateFormatService(GObject.Object):
    """
    Service for formatting dates consistently across the application.

    This service provides centralized date formatting with support for
    multiple formats. It emits signals when the format changes to allow
    UI components to update immediately.

    Signals:
        format-changed: Emitted when the date format changes.
    """

    __gtype_name__ = "DateFormatService"

    __gsignals__ = {
        "format-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self) -> None:
        """Initialize the date format service."""
        super().__init__()
        self._current_format = DateFormat.ISO  # Default to ISO format
        logger.info("DateFormatService initialized with default format: ISO")

    @property
    def current_format(self) -> DateFormat:
        """Get the current date format."""
        return self._current_format

    @property
    def current_format_string(self) -> str:
        """Get the current date format as a string."""
        return self._current_format.value

    def set_format(self, format_value: DateFormat | str) -> None:
        """
        Set the date format.

        Args:
            format_value: DateFormat enum or string representation.
        """
        if isinstance(format_value, str):
            format_value = get_date_format_from_string(format_value)

        if format_value != self._current_format:
            old_format = self._current_format
            self._current_format = format_value
            logger.info(f"Date format changed from {old_format.value} to {format_value.value}")
            self.emit("format-changed", format_value.value)

    def format_date(self, date: datetime, show_time_for_today: bool = True) -> str:
        """
        Format a datetime using the current format setting.

        For today's dates, optionally shows time instead of date.
        For dates in the current year (but not today), shows date without year.

        Args:
            date: The datetime to format.
            show_time_for_today: If True, show time only for today's dates.

        Returns:
            Formatted date string.
        """
        now = datetime.now()
        pattern = DATE_FORMAT_PATTERNS[self._current_format]

        if show_time_for_today and date.date() == now.date():
            # Show time for today's messages
            return date.strftime("%H:%M")
        else:
            # Use the configured date format
            return date.strftime(pattern)

    def format_date_full(self, date: datetime) -> str:
        """
        Format a datetime with full date always (no time-only for today).

        Args:
            date: The datetime to format.

        Returns:
            Formatted date string.
        """
        return self.format_date(date, show_time_for_today=False)

    def format_date_with_time(self, date: datetime) -> str:
        """
        Format a datetime with both date and time.

        Args:
            date: The datetime to format.

        Returns:
            Formatted date and time string.
        """
        pattern = DATE_FORMAT_PATTERNS[self._current_format]
        return date.strftime(f"{pattern} at %H:%M")

    def get_format_label(self, format_value: Optional[DateFormat] = None) -> str:
        """
        Get the human-readable label for a format.

        Args:
            format_value: Format to get label for, or None for current format.

        Returns:
            Human-readable label.
        """
        if format_value is None:
            format_value = self._current_format
        return DATE_FORMAT_LABELS.get(format_value, format_value.value)

    def get_format_example(self, format_value: Optional[DateFormat] = None) -> str:
        """
        Get an example date string for a format.

        Args:
            format_value: Format to get example for, or None for current format.

        Returns:
            Example date string.
        """
        if format_value is None:
            format_value = self._current_format
        return DATE_FORMAT_EXAMPLES.get(format_value, "")

    @staticmethod
    def get_all_formats() -> list[tuple[DateFormat, str, str]]:
        """
        Get all available formats with labels and examples.

        Returns:
            List of (format, label, example) tuples.
        """
        return [
            (fmt, DATE_FORMAT_LABELS[fmt], DATE_FORMAT_EXAMPLES[fmt])
            for fmt in DateFormat
        ]


# Singleton instance
_date_format_service: Optional[DateFormatService] = None


def get_date_format_service() -> DateFormatService:
    """
    Get the global date format service instance.

    Returns:
        The singleton DateFormatService instance.
    """
    global _date_format_service

    if _date_format_service is None:
        _date_format_service = DateFormatService()

    return _date_format_service


def format_date(date: datetime, show_time_for_today: bool = True) -> str:
    """
    Convenience function to format a date using the global service.

    Args:
        date: The datetime to format.
        show_time_for_today: If True, show time only for today's dates.

    Returns:
        Formatted date string.
    """
    return get_date_format_service().format_date(date, show_time_for_today)


def format_date_with_time(date: datetime) -> str:
    """
    Convenience function to format a date with time using the global service.

    Args:
        date: The datetime to format.

    Returns:
        Formatted date and time string.
    """
    return get_date_format_service().format_date_with_time(date)
