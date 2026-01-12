"""
Playwright configuration for unitMail E2E tests.

This module provides configuration settings for running Playwright tests
with pytest-playwright. It defines browser settings, timeouts, base URL,
screenshot behavior, and other test configuration options.

Usage:
    pytest tests/e2e/ --browser chromium
    pytest tests/e2e/ --browser firefox
    pytest tests/e2e/ --browser webkit
    pytest tests/e2e/ --browser-channel chrome
    pytest tests/e2e/ --headed
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path


# =============================================================================
# Environment Configuration
# =============================================================================

# Base URL for the application under test
BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8080")

# API URL for backend calls
API_URL = os.environ.get("E2E_API_URL", f"{BASE_URL}/api")

# Headless mode (set to "false" for debugging)
HEADLESS = os.environ.get("E2E_HEADLESS", "true").lower() == "true"

# Slow motion delay in milliseconds (useful for debugging)
SLOW_MO = int(os.environ.get("E2E_SLOW_MO", "0"))

# Default timeout in milliseconds
DEFAULT_TIMEOUT = int(os.environ.get("E2E_TIMEOUT", "30000"))

# Navigation timeout in milliseconds
NAVIGATION_TIMEOUT = int(os.environ.get("E2E_NAVIGATION_TIMEOUT", "30000"))

# Record video for all tests
RECORD_VIDEO = os.environ.get("E2E_RECORD_VIDEO", "false").lower() == "true"

# Record trace for all tests
RECORD_TRACE = os.environ.get("E2E_RECORD_TRACE", "false").lower() == "true"

# Screenshot on failure
SCREENSHOT_ON_FAILURE = os.environ.get("E2E_SCREENSHOT_ON_FAILURE", "true").lower() == "true"

# Test results directory
TEST_RESULTS_DIR = Path(os.environ.get("E2E_RESULTS_DIR", "test-results"))

# Screenshots directory
SCREENSHOTS_DIR = TEST_RESULTS_DIR / "screenshots"

# Videos directory
VIDEOS_DIR = TEST_RESULTS_DIR / "videos"

# Traces directory
TRACES_DIR = TEST_RESULTS_DIR / "traces"


# =============================================================================
# Browser Configuration
# =============================================================================

@dataclass
class BrowserConfig:
    """Configuration for a browser instance."""

    # Browser name: chromium, firefox, webkit
    name: str = "chromium"

    # Browser channel: chrome, chrome-beta, msedge, msedge-beta, msedge-dev
    channel: Optional[str] = None

    # Run in headless mode
    headless: bool = HEADLESS

    # Slow down operations by specified milliseconds
    slow_mo: int = SLOW_MO

    # Viewport dimensions
    viewport_width: int = 1280
    viewport_height: int = 720

    # Device scale factor
    device_scale_factor: float = 1.0

    # Mobile device emulation
    is_mobile: bool = False
    has_touch: bool = False

    # Locale for the browser
    locale: str = "en-US"

    # Timezone
    timezone_id: str = "America/New_York"

    # Geolocation
    geolocation: Optional[Dict[str, float]] = None

    # Permissions to grant
    permissions: List[str] = field(default_factory=list)

    # Color scheme: light, dark, no-preference
    color_scheme: str = "light"

    # Reduced motion preference
    reduced_motion: str = "no-preference"

    # HTTP credentials for basic auth
    http_credentials: Optional[Dict[str, str]] = None

    # Extra HTTP headers
    extra_http_headers: Dict[str, str] = field(default_factory=dict)

    # Ignore HTTPS errors
    ignore_https_errors: bool = False

    # User agent string
    user_agent: Optional[str] = None

    # Download directory
    downloads_path: Optional[str] = None

    # Accept downloads
    accept_downloads: bool = True

    def to_launch_options(self) -> Dict[str, Any]:
        """Convert to Playwright browser launch options."""
        options = {
            "headless": self.headless,
            "slow_mo": self.slow_mo,
        }
        if self.channel:
            options["channel"] = self.channel
        return options

    def to_context_options(self) -> Dict[str, Any]:
        """Convert to Playwright browser context options."""
        options = {
            "viewport": {
                "width": self.viewport_width,
                "height": self.viewport_height,
            },
            "device_scale_factor": self.device_scale_factor,
            "is_mobile": self.is_mobile,
            "has_touch": self.has_touch,
            "locale": self.locale,
            "timezone_id": self.timezone_id,
            "color_scheme": self.color_scheme,
            "reduced_motion": self.reduced_motion,
            "ignore_https_errors": self.ignore_https_errors,
            "accept_downloads": self.accept_downloads,
            "base_url": BASE_URL,
        }

        if self.geolocation:
            options["geolocation"] = self.geolocation
        if self.permissions:
            options["permissions"] = self.permissions
        if self.http_credentials:
            options["http_credentials"] = self.http_credentials
        if self.extra_http_headers:
            options["extra_http_headers"] = self.extra_http_headers
        if self.user_agent:
            options["user_agent"] = self.user_agent
        if self.downloads_path:
            options["downloads_path"] = self.downloads_path

        return options


# =============================================================================
# Predefined Browser Configurations
# =============================================================================

# Default desktop browsers
CHROMIUM_CONFIG = BrowserConfig(name="chromium")
FIREFOX_CONFIG = BrowserConfig(name="firefox")
WEBKIT_CONFIG = BrowserConfig(name="webkit")

# Chrome browser (requires Chrome installed)
CHROME_CONFIG = BrowserConfig(name="chromium", channel="chrome")

# Edge browser (requires Edge installed)
EDGE_CONFIG = BrowserConfig(name="chromium", channel="msedge")

# Mobile device configurations
IPHONE_12_CONFIG = BrowserConfig(
    name="webkit",
    viewport_width=390,
    viewport_height=844,
    device_scale_factor=3,
    is_mobile=True,
    has_touch=True,
    user_agent=(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_4 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 "
        "Mobile/15E148 Safari/604.1"
    ),
)

PIXEL_5_CONFIG = BrowserConfig(
    name="chromium",
    viewport_width=393,
    viewport_height=851,
    device_scale_factor=2.75,
    is_mobile=True,
    has_touch=True,
    user_agent=(
        "Mozilla/5.0 (Linux; Android 11; Pixel 5) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.91 Mobile Safari/537.36"
    ),
)

# Tablet configurations
IPAD_CONFIG = BrowserConfig(
    name="webkit",
    viewport_width=768,
    viewport_height=1024,
    device_scale_factor=2,
    is_mobile=True,
    has_touch=True,
)

# Dark mode configuration
DARK_MODE_CONFIG = BrowserConfig(
    name="chromium",
    color_scheme="dark",
)


# =============================================================================
# Test Configuration
# =============================================================================

@dataclass
class TestConfig:
    """Configuration for test execution."""

    # Base URL for the application
    base_url: str = BASE_URL

    # API URL for backend calls
    api_url: str = API_URL

    # Default timeout for operations (ms)
    timeout: int = DEFAULT_TIMEOUT

    # Navigation timeout (ms)
    navigation_timeout: int = NAVIGATION_TIMEOUT

    # Take screenshot on failure
    screenshot_on_failure: bool = SCREENSHOT_ON_FAILURE

    # Screenshot mode: on, off, only-on-failure
    screenshot_mode: str = "only-on-failure"

    # Video recording mode: on, off, on-first-retry, retain-on-failure
    video_mode: str = "retain-on-failure" if RECORD_VIDEO else "off"

    # Trace recording mode: on, off, on-first-retry, retain-on-failure
    trace_mode: str = "retain-on-failure" if RECORD_TRACE else "off"

    # Output directory for test artifacts
    output_dir: Path = TEST_RESULTS_DIR

    # Number of retries for failed tests
    retries: int = 0

    # Number of workers for parallel execution
    workers: int = 1

    # Test timeout (ms)
    test_timeout: int = 60000

    # Expect timeout (ms)
    expect_timeout: int = 5000

    # Full page screenshot
    full_page_screenshot: bool = True

    def ensure_directories(self) -> None:
        """Ensure output directories exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        TRACES_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Global Configuration Instance
# =============================================================================

# Default test configuration
config = TestConfig()

# Ensure directories exist
config.ensure_directories()


# =============================================================================
# Pytest-Playwright Configuration (conftest.py compatible)
# =============================================================================

def pytest_configure_playwright():
    """
    Return pytest-playwright configuration options.

    This can be used in conftest.py to configure pytest-playwright.
    """
    return {
        "browser": "chromium",
        "headed": not HEADLESS,
        "slowmo": SLOW_MO,
        "screenshot": config.screenshot_mode,
        "video": config.video_mode,
        "tracing": config.trace_mode,
        "output": str(config.output_dir),
    }


# =============================================================================
# Utility Functions
# =============================================================================

def get_browser_config(browser_name: str) -> BrowserConfig:
    """
    Get browser configuration by name.

    Args:
        browser_name: Name of the browser (chromium, firefox, webkit, chrome, edge)

    Returns:
        BrowserConfig instance for the specified browser
    """
    configs = {
        "chromium": CHROMIUM_CONFIG,
        "firefox": FIREFOX_CONFIG,
        "webkit": WEBKIT_CONFIG,
        "chrome": CHROME_CONFIG,
        "edge": EDGE_CONFIG,
        "iphone": IPHONE_12_CONFIG,
        "pixel": PIXEL_5_CONFIG,
        "ipad": IPAD_CONFIG,
        "dark": DARK_MODE_CONFIG,
    }
    return configs.get(browser_name.lower(), CHROMIUM_CONFIG)


def get_screenshot_path(test_name: str) -> Path:
    """
    Get the screenshot path for a test.

    Args:
        test_name: Name of the test

    Returns:
        Path where screenshot should be saved
    """
    # Sanitize test name for filesystem
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in test_name)
    return SCREENSHOTS_DIR / f"{safe_name}.png"


def get_video_path(test_name: str) -> Path:
    """
    Get the video path for a test.

    Args:
        test_name: Name of the test

    Returns:
        Path where video should be saved
    """
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in test_name)
    return VIDEOS_DIR / f"{safe_name}.webm"


def get_trace_path(test_name: str) -> Path:
    """
    Get the trace path for a test.

    Args:
        test_name: Name of the test

    Returns:
        Path where trace should be saved
    """
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in test_name)
    return TRACES_DIR / f"{safe_name}.zip"


# =============================================================================
# Environment Variable Summary
# =============================================================================

ENV_VARS = """
Environment Variables:
----------------------
E2E_BASE_URL          - Base URL for the application (default: http://localhost:8080)
E2E_API_URL           - API URL for backend calls (default: {BASE_URL}/api)
E2E_HEADLESS          - Run in headless mode (default: true)
E2E_SLOW_MO           - Slow motion delay in ms (default: 0)
E2E_TIMEOUT           - Default timeout in ms (default: 30000)
E2E_NAVIGATION_TIMEOUT - Navigation timeout in ms (default: 30000)
E2E_RECORD_VIDEO      - Record video for tests (default: false)
E2E_RECORD_TRACE      - Record trace for tests (default: false)
E2E_SCREENSHOT_ON_FAILURE - Screenshot on failure (default: true)
E2E_RESULTS_DIR       - Test results directory (default: test-results)
E2E_TEST_USER_EMAIL   - Test user email for authentication
E2E_TEST_USER_PASSWORD - Test user password for authentication
"""


if __name__ == "__main__":
    # Print configuration when run directly
    print("Playwright Configuration for unitMail E2E Tests")
    print("=" * 50)
    print(f"Base URL: {BASE_URL}")
    print(f"API URL: {API_URL}")
    print(f"Headless: {HEADLESS}")
    print(f"Slow Motion: {SLOW_MO}ms")
    print(f"Default Timeout: {DEFAULT_TIMEOUT}ms")
    print(f"Navigation Timeout: {NAVIGATION_TIMEOUT}ms")
    print(f"Screenshot on Failure: {SCREENSHOT_ON_FAILURE}")
    print(f"Record Video: {RECORD_VIDEO}")
    print(f"Record Trace: {RECORD_TRACE}")
    print(f"Results Directory: {TEST_RESULTS_DIR}")
    print("\n" + ENV_VARS)
