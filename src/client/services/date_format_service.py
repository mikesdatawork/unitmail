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
    # Date and time formats (24-hour)
    US_TIME = "MM/DD/YYYY HH:MM"          # 01/13/2026 14:30
    EUROPEAN_TIME = "DD/MM/YYYY HH:MM"    # 13/01/2026 14:30
    ISO_TIME = "YYYY-MM-DD HH:MM"         # 2026-01-13 14:30
    DAY_MONTH_YEAR_TIME = "DD MMM YYYY HH:MM"  # 13 Jan 2026 14:30
    MONTH_DAY_YEAR_TIME = "MMM DD, YYYY HH:MM"  # Jan 13, 2026 14:30
    # Date and time formats (12-hour am/pm)
    US_TIME_AMPM = "MM/DD/YYYY hh:mm am/pm"          # 01/13/2026 02:30 pm
    EUROPEAN_TIME_AMPM = "DD/MM/YYYY hh:mm am/pm"    # 13/01/2026 02:30 pm
    ISO_TIME_AMPM = "YYYY-MM-DD hh:mm am/pm"         # 2026-01-13 02:30 pm
    DAY_MONTH_YEAR_TIME_AMPM = "DD MMM YYYY hh:mm am/pm"  # 13 Jan 2026 02:30 pm
    MONTH_DAY_YEAR_TIME_AMPM = "MMM DD, YYYY hh:mm am/pm"  # Jan 13, 2026 02:30 pm


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
    DateFormat.US_TIME_AMPM: "%m/%d/%Y %I:%M %p",
    DateFormat.EUROPEAN_TIME_AMPM: "%d/%m/%Y %I:%M %p",
    DateFormat.ISO_TIME_AMPM: "%Y-%m-%d %I:%M %p",
    DateFormat.DAY_MONTH_YEAR_TIME_AMPM: "%d %b %Y %I:%M %p",
    DateFormat.MONTH_DAY_YEAR_TIME_AMPM: "%b %d, %Y %I:%M %p",
}

# Human-readable labels for the UI
DATE_FORMAT_LABELS = {
    DateFormat.US: "MM/DD/YYYY (US)",
    DateFormat.EUROPEAN: "DD/MM/YYYY (European)",
    DateFormat.ISO: "YYYY-MM-DD (ISO)",
    DateFormat.DAY_MONTH_YEAR: "DD MMM YYYY",
    DateFormat.MONTH_DAY_YEAR: "MMM DD, YYYY",
    DateFormat.US_TIME: "MM/DD/YYYY HH:MM (US 24-hour)",
    DateFormat.EUROPEAN_TIME: "DD/MM/YYYY HH:MM (European 24-hour)",
    DateFormat.ISO_TIME: "YYYY-MM-DD HH:MM (ISO 24-hour)",
    DateFormat.DAY_MONTH_YEAR_TIME: "DD MMM YYYY HH:MM (24-hour)",
    DateFormat.MONTH_DAY_YEAR_TIME: "MMM DD, YYYY HH:MM (24-hour)",
    DateFormat.US_TIME_AMPM: "MM/DD/YYYY hh:mm am/pm (US 12-hour)",
    DateFormat.EUROPEAN_TIME_AMPM: "DD/MM/YYYY hh:mm am/pm (European 12-hour)",
    DateFormat.ISO_TIME_AMPM: "YYYY-MM-DD hh:mm am/pm (ISO 12-hour)",
    DateFormat.DAY_MONTH_YEAR_TIME_AMPM: "DD MMM YYYY hh:mm am/pm (12-hour)",
    DateFormat.MONTH_DAY_YEAR_TIME_AMPM: "MMM DD, YYYY hh:mm am/pm (12-hour)",
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
    DateFormat.US_TIME_AMPM: "01/13/2026 02:30 pm",
    DateFormat.EUROPEAN_TIME_AMPM: "13/01/2026 02:30 pm",
    DateFormat.ISO_TIME_AMPM: "2026-01-13 02:30 pm",
    DateFormat.DAY_MONTH_YEAR_TIME_AMPM: "13 Jan 2026 02:30 pm",
    DateFormat.MONTH_DAY_YEAR_TIME_AMPM: "Jan 13, 2026 02:30 pm",
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
        # Date only formats
        "MM/DD/YYYY": DateFormat.US,
        "DD/MM/YYYY": DateFormat.EUROPEAN,
        "YYYY-MM-DD": DateFormat.ISO,
        "DD MMM YYYY": DateFormat.DAY_MONTH_YEAR,
        "MMM DD, YYYY": DateFormat.MONTH_DAY_YEAR,
        # Date and time formats (24-hour)
        "MM/DD/YYYY HH:MM": DateFormat.US_TIME,
        "DD/MM/YYYY HH:MM": DateFormat.EUROPEAN_TIME,
        "YYYY-MM-DD HH:MM": DateFormat.ISO_TIME,
        "DD MMM YYYY HH:MM": DateFormat.DAY_MONTH_YEAR_TIME,
        "MMM DD, YYYY HH:MM": DateFormat.MONTH_DAY_YEAR_TIME,
        # Date and time formats (12-hour am/pm)
        "MM/DD/YYYY hh:mm am/pm": DateFormat.US_TIME_AMPM,
        "DD/MM/YYYY hh:mm am/pm": DateFormat.EUROPEAN_TIME_AMPM,
        "YYYY-MM-DD hh:mm am/pm": DateFormat.ISO_TIME_AMPM,
        "DD MMM YYYY hh:mm am/pm": DateFormat.DAY_MONTH_YEAR_TIME_AMPM,
        "MMM DD, YYYY hh:mm am/pm": DateFormat.MONTH_DAY_YEAR_TIME_AMPM,
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
            result = date.strftime(pattern)
            # Convert AM/PM to lowercase am/pm
            if "%p" in pattern:
                result = result.replace("AM", "am").replace("PM", "pm")
            return result

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
        result = date.strftime(f"{pattern} at %H:%M")
        # Convert AM/PM to lowercase am/pm
        if "%p" in pattern:
            result = result.replace("AM", "am").replace("PM", "pm")
        return result

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
