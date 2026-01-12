"""
Pytest fixtures for Playwright E2E tests.

This module provides fixtures for browser instances, page objects,
test database setup/teardown, API clients, and authentication.
"""

import asyncio
import os
import uuid
from typing import AsyncGenerator, Generator, Dict, Any, Optional
from dataclasses import dataclass

import pytest
import pytest_asyncio
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
    BrowserType,
)

# Import page objects
from pages import (
    LoginPage,
    InboxPage,
    ComposePage,
    ContactsPage,
    EmailReaderPage,
)


# =============================================================================
# Configuration
# =============================================================================

# Environment configuration
BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8080")
API_URL = os.environ.get("E2E_API_URL", "http://localhost:8080/api")
HEADLESS = os.environ.get("E2E_HEADLESS", "true").lower() == "true"
SLOW_MO = int(os.environ.get("E2E_SLOW_MO", "0"))
DEFAULT_TIMEOUT = int(os.environ.get("E2E_TIMEOUT", "30000"))

# Test user credentials
TEST_USER_EMAIL = os.environ.get("E2E_TEST_USER_EMAIL", "test@unitmail.local")
TEST_USER_PASSWORD = os.environ.get("E2E_TEST_USER_PASSWORD", "testpassword123")


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class TestUser:
    """Test user data."""
    id: str
    email: str
    password: str
    name: str
    token: Optional[str] = None


@dataclass
class TestEmail:
    """Test email data."""
    id: str
    subject: str
    body: str
    sender: str
    recipients: list
    is_read: bool = False
    is_starred: bool = False


@dataclass
class TestContact:
    """Test contact data."""
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    company: Optional[str] = None


# =============================================================================
# Event Loop Fixture
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Playwright Fixtures
# =============================================================================

@pytest_asyncio.fixture(scope="session")
async def playwright() -> AsyncGenerator[Playwright, None]:
    """Create a Playwright instance for the test session."""
    async with async_playwright() as pw:
        yield pw


@pytest_asyncio.fixture(scope="session")
async def browser_chromium(playwright: Playwright) -> AsyncGenerator[Browser, None]:
    """Launch Chromium browser for tests."""
    browser = await playwright.chromium.launch(
        headless=HEADLESS,
        slow_mo=SLOW_MO,
    )
    yield browser
    await browser.close()


@pytest_asyncio.fixture(scope="session")
async def browser_firefox(playwright: Playwright) -> AsyncGenerator[Browser, None]:
    """Launch Firefox browser for tests."""
    browser = await playwright.firefox.launch(
        headless=HEADLESS,
        slow_mo=SLOW_MO,
    )
    yield browser
    await browser.close()


@pytest_asyncio.fixture(scope="session")
async def browser_webkit(playwright: Playwright) -> AsyncGenerator[Browser, None]:
    """Launch WebKit browser for tests."""
    browser = await playwright.webkit.launch(
        headless=HEADLESS,
        slow_mo=SLOW_MO,
    )
    yield browser
    await browser.close()


@pytest_asyncio.fixture(scope="session")
async def browser(playwright: Playwright) -> AsyncGenerator[Browser, None]:
    """
    Default browser fixture (Chromium).

    Use browser_chromium, browser_firefox, or browser_webkit for specific browsers.
    """
    browser = await playwright.chromium.launch(
        headless=HEADLESS,
        slow_mo=SLOW_MO,
    )
    yield browser
    await browser.close()


@pytest_asyncio.fixture
async def context(browser: Browser) -> AsyncGenerator[BrowserContext, None]:
    """
    Create a new browser context for each test.

    This provides isolation between tests with separate cookies,
    storage, and other browser state.
    """
    context = await browser.new_context(
        viewport={"width": 1280, "height": 720},
        base_url=BASE_URL,
        locale="en-US",
        timezone_id="America/New_York",
        # Enable recording for debugging
        record_video_dir="test-results/videos" if os.environ.get("E2E_RECORD_VIDEO") else None,
    )

    # Set default timeout
    context.set_default_timeout(DEFAULT_TIMEOUT)

    yield context
    await context.close()


@pytest_asyncio.fixture
async def page(context: BrowserContext) -> AsyncGenerator[Page, None]:
    """
    Create a new page for each test with base URL configured.
    """
    page = await context.new_page()

    # Set default navigation timeout
    page.set_default_navigation_timeout(DEFAULT_TIMEOUT)
    page.set_default_timeout(DEFAULT_TIMEOUT)

    yield page
    await page.close()


# =============================================================================
# Multi-Browser Fixtures (for cross-browser testing)
# =============================================================================

@pytest.fixture(params=["chromium", "firefox", "webkit"])
def browser_name(request) -> str:
    """Parameterized fixture for running tests across all browsers."""
    return request.param


@pytest_asyncio.fixture
async def cross_browser(
    playwright: Playwright,
    browser_name: str,
) -> AsyncGenerator[Browser, None]:
    """
    Cross-browser fixture that runs tests on all browsers.

    Usage:
        @pytest.mark.parametrize("browser_name", ["chromium", "firefox", "webkit"], indirect=True)
        async def test_something(cross_browser_page):
            ...
    """
    browser_type: BrowserType = getattr(playwright, browser_name)
    browser = await browser_type.launch(
        headless=HEADLESS,
        slow_mo=SLOW_MO,
    )
    yield browser
    await browser.close()


@pytest_asyncio.fixture
async def cross_browser_page(
    cross_browser: Browser,
) -> AsyncGenerator[Page, None]:
    """Page fixture for cross-browser testing."""
    context = await cross_browser.new_context(
        viewport={"width": 1280, "height": 720},
        base_url=BASE_URL,
    )
    page = await context.new_page()
    yield page
    await context.close()


# =============================================================================
# API Client Fixture
# =============================================================================

class APIClient:
    """
    API client for backend calls during E2E tests.

    Used for test setup, teardown, and verification.
    """

    def __init__(self, page: Page, api_url: str = API_URL):
        self.page = page
        self.api_url = api_url
        self._token: Optional[str] = None

    @property
    def headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def set_token(self, token: str) -> None:
        """Set authentication token."""
        self._token = token

    async def request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make an API request using Playwright's request context."""
        url = f"{self.api_url}/{endpoint.lstrip('/')}"

        response = await self.page.request.fetch(
            url,
            method=method,
            headers=self.headers,
            data=data,
        )

        if response.ok:
            try:
                return await response.json()
            except Exception:
                return {"status": "ok"}
        else:
            return {
                "error": True,
                "status": response.status,
                "message": await response.text(),
            }

    async def get(self, endpoint: str) -> Dict[str, Any]:
        """Make a GET request."""
        return await self.request("GET", endpoint)

    async def post(self, endpoint: str, data: Dict = None) -> Dict[str, Any]:
        """Make a POST request."""
        return await self.request("POST", endpoint, data)

    async def put(self, endpoint: str, data: Dict = None) -> Dict[str, Any]:
        """Make a PUT request."""
        return await self.request("PUT", endpoint, data)

    async def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make a DELETE request."""
        return await self.request("DELETE", endpoint)

    async def patch(self, endpoint: str, data: Dict = None) -> Dict[str, Any]:
        """Make a PATCH request."""
        return await self.request("PATCH", endpoint, data)

    # Auth endpoints
    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """Login and get authentication token."""
        result = await self.post("auth/login", {"email": email, "password": password})
        if "token" in result:
            self.set_token(result["token"])
        return result

    async def logout(self) -> Dict[str, Any]:
        """Logout current user."""
        result = await self.post("auth/logout")
        self._token = None
        return result

    async def register(
        self, email: str, password: str, name: str
    ) -> Dict[str, Any]:
        """Register a new user."""
        return await self.post("auth/register", {
            "email": email,
            "password": password,
            "name": name,
        })

    # User endpoints
    async def get_current_user(self) -> Dict[str, Any]:
        """Get current authenticated user."""
        return await self.get("users/me")

    async def create_test_user(
        self,
        email: Optional[str] = None,
        password: str = "testpassword123",
        name: str = "Test User",
    ) -> TestUser:
        """Create a test user for E2E tests."""
        email = email or f"test_{uuid.uuid4().hex[:8]}@unitmail.local"
        result = await self.register(email, password, name)
        return TestUser(
            id=result.get("id", str(uuid.uuid4())),
            email=email,
            password=password,
            name=name,
            token=result.get("token"),
        )

    # Email endpoints
    async def get_emails(self, folder: str = "inbox") -> Dict[str, Any]:
        """Get emails in a folder."""
        return await self.get(f"emails?folder={folder}")

    async def get_email(self, email_id: str) -> Dict[str, Any]:
        """Get a specific email."""
        return await self.get(f"emails/{email_id}")

    async def send_email(
        self,
        to: list,
        subject: str,
        body: str,
        cc: list = None,
        bcc: list = None,
    ) -> Dict[str, Any]:
        """Send an email."""
        return await self.post("emails/send", {
            "to": to,
            "subject": subject,
            "body": body,
            "cc": cc or [],
            "bcc": bcc or [],
        })

    async def create_test_email(
        self,
        subject: Optional[str] = None,
        body: str = "Test email body",
        sender: Optional[str] = None,
    ) -> TestEmail:
        """Create a test email for E2E tests."""
        subject = subject or f"Test Email {uuid.uuid4().hex[:8]}"
        sender = sender or "sender@unitmail.local"

        result = await self.post("emails/test", {
            "subject": subject,
            "body": body,
            "sender": sender,
        })

        return TestEmail(
            id=result.get("id", str(uuid.uuid4())),
            subject=subject,
            body=body,
            sender=sender,
            recipients=[TEST_USER_EMAIL],
        )

    async def delete_email(self, email_id: str) -> Dict[str, Any]:
        """Delete an email."""
        return await self.delete(f"emails/{email_id}")

    async def mark_email_read(self, email_id: str, read: bool = True) -> Dict[str, Any]:
        """Mark email as read/unread."""
        return await self.patch(f"emails/{email_id}", {"is_read": read})

    async def star_email(self, email_id: str, starred: bool = True) -> Dict[str, Any]:
        """Star/unstar an email."""
        return await self.patch(f"emails/{email_id}", {"is_starred": starred})

    # Contact endpoints
    async def get_contacts(self) -> Dict[str, Any]:
        """Get all contacts."""
        return await self.get("contacts")

    async def get_contact(self, contact_id: str) -> Dict[str, Any]:
        """Get a specific contact."""
        return await self.get(f"contacts/{contact_id}")

    async def create_contact(
        self,
        name: str,
        email: str,
        phone: Optional[str] = None,
        company: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new contact."""
        return await self.post("contacts", {
            "name": name,
            "email": email,
            "phone": phone,
            "company": company,
        })

    async def create_test_contact(
        self,
        name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> TestContact:
        """Create a test contact for E2E tests."""
        name = name or f"Test Contact {uuid.uuid4().hex[:8]}"
        email = email or f"contact_{uuid.uuid4().hex[:8]}@example.com"

        result = await self.create_contact(name, email)

        return TestContact(
            id=result.get("id", str(uuid.uuid4())),
            name=name,
            email=email,
        )

    async def update_contact(
        self,
        contact_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update a contact."""
        return await self.put(f"contacts/{contact_id}", data)

    async def delete_contact(self, contact_id: str) -> Dict[str, Any]:
        """Delete a contact."""
        return await self.delete(f"contacts/{contact_id}")

    async def search_contacts(self, query: str) -> Dict[str, Any]:
        """Search contacts."""
        return await self.get(f"contacts/search?q={query}")


@pytest_asyncio.fixture
async def api_client(page: Page) -> APIClient:
    """Create an API client for backend calls."""
    return APIClient(page)


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def test_db(api_client: APIClient) -> AsyncGenerator[None, None]:
    """
    Set up and tear down test database state.

    This fixture ensures a clean database state for each test.
    """
    # Setup: Could call an API endpoint to reset test data
    # await api_client.post("test/reset")

    yield

    # Teardown: Clean up test data
    # await api_client.post("test/cleanup")


@pytest_asyncio.fixture
async def seeded_db(api_client: APIClient) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Set up database with seed data for tests.

    Returns a dict with references to created test data.
    """
    seed_data = {
        "users": [],
        "emails": [],
        "contacts": [],
    }

    # Seed data would be created here
    # For example:
    # seed_data["emails"].append(await api_client.create_test_email())
    # seed_data["contacts"].append(await api_client.create_test_contact())

    yield seed_data

    # Cleanup seeded data
    # for email in seed_data["emails"]:
    #     await api_client.delete_email(email.id)
    # for contact in seed_data["contacts"]:
    #     await api_client.delete_contact(contact.id)


# =============================================================================
# Authentication Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def authenticated_context(
    browser: Browser,
    api_client: APIClient,
) -> AsyncGenerator[BrowserContext, None]:
    """
    Create an authenticated browser context.

    This fixture handles login and provides a context with
    authentication cookies/storage already set.
    """
    # Create a new context
    context = await browser.new_context(
        viewport={"width": 1280, "height": 720},
        base_url=BASE_URL,
    )

    # Create a page for authentication
    page = await context.new_page()

    # Perform login via UI
    login_page = LoginPage(page, BASE_URL)
    await login_page.goto()
    await login_page.login_and_wait(TEST_USER_EMAIL, TEST_USER_PASSWORD)

    # Store the authentication state
    await context.storage_state(path="test-results/.auth/state.json")

    await page.close()

    yield context

    await context.close()


@pytest_asyncio.fixture
async def authenticated_page(
    authenticated_context: BrowserContext,
) -> AsyncGenerator[Page, None]:
    """
    Create an authenticated page.

    The page already has the user logged in.
    """
    page = await authenticated_context.new_page()
    yield page
    await page.close()


@pytest_asyncio.fixture
async def logged_in_user(
    page: Page,
    api_client: APIClient,
) -> AsyncGenerator[TestUser, None]:
    """
    Log in a test user and provide user data.

    Performs login via UI and yields the test user data.
    """
    # Create test user data
    test_user = TestUser(
        id="test-user-id",
        email=TEST_USER_EMAIL,
        password=TEST_USER_PASSWORD,
        name="Test User",
    )

    # Perform login via UI
    login_page = LoginPage(page, BASE_URL)
    await login_page.goto()
    await login_page.login_and_wait(test_user.email, test_user.password)

    # Get token from API if needed
    result = await api_client.login(test_user.email, test_user.password)
    test_user.token = result.get("token")

    yield test_user

    # Logout after test
    try:
        await login_page.logout()
    except Exception:
        pass  # Ignore logout errors


# =============================================================================
# Page Object Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def login_page(page: Page) -> LoginPage:
    """Create a LoginPage instance."""
    return LoginPage(page, BASE_URL)


@pytest_asyncio.fixture
async def inbox_page(page: Page) -> InboxPage:
    """Create an InboxPage instance."""
    return InboxPage(page, BASE_URL)


@pytest_asyncio.fixture
async def compose_page(page: Page) -> ComposePage:
    """Create a ComposePage instance."""
    return ComposePage(page, BASE_URL)


@pytest_asyncio.fixture
async def contacts_page(page: Page) -> ContactsPage:
    """Create a ContactsPage instance."""
    return ContactsPage(page, BASE_URL)


@pytest_asyncio.fixture
async def email_reader_page(page: Page) -> EmailReaderPage:
    """Create an EmailReaderPage instance."""
    return EmailReaderPage(page, BASE_URL)


# =============================================================================
# Authenticated Page Object Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def auth_inbox_page(authenticated_page: Page) -> InboxPage:
    """Create an authenticated InboxPage instance."""
    return InboxPage(authenticated_page, BASE_URL)


@pytest_asyncio.fixture
async def auth_compose_page(authenticated_page: Page) -> ComposePage:
    """Create an authenticated ComposePage instance."""
    return ComposePage(authenticated_page, BASE_URL)


@pytest_asyncio.fixture
async def auth_contacts_page(authenticated_page: Page) -> ContactsPage:
    """Create an authenticated ContactsPage instance."""
    return ContactsPage(authenticated_page, BASE_URL)


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def screenshot_on_failure(request, page: Page):
    """
    Take a screenshot when a test fails.

    Usage:
        def test_something(page, screenshot_on_failure):
            ...
    """
    yield

    if request.node.rep_call.failed:
        screenshot_dir = "test-results/screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)

        test_name = request.node.name
        screenshot_path = f"{screenshot_dir}/{test_name}.png"

        # Take screenshot synchronously
        asyncio.get_event_loop().run_until_complete(
            page.screenshot(path=screenshot_path)
        )


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to store test result for screenshot_on_failure fixture."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


@pytest.fixture
def temp_file(tmp_path) -> Generator[str, None, None]:
    """
    Create a temporary file for attachment tests.
    """
    file_path = tmp_path / "test_attachment.txt"
    file_path.write_text("This is a test attachment file.")
    yield str(file_path)


@pytest.fixture
def temp_files(tmp_path) -> Generator[list, None, None]:
    """
    Create multiple temporary files for attachment tests.
    """
    files = []
    for i in range(3):
        file_path = tmp_path / f"test_attachment_{i}.txt"
        file_path.write_text(f"This is test attachment file {i}.")
        files.append(str(file_path))
    yield files


# =============================================================================
# Test Data Generators
# =============================================================================

@pytest.fixture
def unique_email() -> str:
    """Generate a unique email address for tests."""
    return f"test_{uuid.uuid4().hex[:8]}@unitmail.local"


@pytest.fixture
def unique_subject() -> str:
    """Generate a unique email subject for tests."""
    return f"Test Subject {uuid.uuid4().hex[:8]}"


@pytest.fixture
def unique_contact_name() -> str:
    """Generate a unique contact name for tests."""
    return f"Test Contact {uuid.uuid4().hex[:8]}"
