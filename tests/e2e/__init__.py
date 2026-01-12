"""
unitMail E2E Tests Package.

This package contains end-to-end tests for the unitMail application
using Playwright and pytest-playwright.

Test Modules:
    - test_auth: Authentication flow tests (login, logout, session)
    - test_compose: Email composition tests
    - test_inbox: Inbox functionality tests
    - test_contacts: Contact management tests

Page Objects:
    - pages/: Page Object Model classes for reusable selectors

Configuration:
    - conftest.py: Pytest fixtures and configuration
    - playwright.config.py: Playwright settings (in project root)

Running Tests:
    # Run all E2E tests
    pytest tests/e2e/

    # Run specific test file
    pytest tests/e2e/test_auth.py

    # Run with specific browser
    pytest tests/e2e/ --browser firefox

    # Run in headed mode (visible browser)
    pytest tests/e2e/ --headed

    # Run with slow motion
    E2E_SLOW_MO=500 pytest tests/e2e/

    # Run with video recording
    E2E_RECORD_VIDEO=true pytest tests/e2e/

Environment Variables:
    E2E_BASE_URL: Base URL for the application (default: http://localhost:8080)
    E2E_HEADLESS: Run in headless mode (default: true)
    E2E_SLOW_MO: Slow motion delay in ms (default: 0)
    E2E_TIMEOUT: Default timeout in ms (default: 30000)
    E2E_RECORD_VIDEO: Record video (default: false)
    E2E_TEST_USER_EMAIL: Test user email
    E2E_TEST_USER_PASSWORD: Test user password
"""

__version__ = "1.0.0"
__all__ = [
    "pages",
]
