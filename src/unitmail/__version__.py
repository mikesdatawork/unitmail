"""Version information for UnitMail."""

__version__ = "0.1.0"
__version_info__ = tuple(int(x) for x in __version__.split("."))

# Release information
__title__ = "unitmail"
__description__ = "A modern email client with encryption support"
__author__ = "UnitMail Team"
__license__ = "MIT"
__copyright__ = "Copyright 2024-2026 UnitMail Team"


def get_version() -> str:
    """Return the current version string."""
    return __version__


def get_version_info() -> tuple[int, ...]:
    """Return the version as a tuple of integers."""
    return __version_info__
