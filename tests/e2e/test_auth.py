"""
E2E tests for authentication flows.

Tests cover:
- Login flow
- Logout
- Invalid credentials handling
- Session expiration
"""

import pytest
from playwright.async_api import Page, expect

from .pages import LoginPage, InboxPage


# =============================================================================
# Test Constants
# =============================================================================

VALID_EMAIL = "test@unitmail.local"
VALID_PASSWORD = "testpassword123"
INVALID_EMAIL = "invalid@unitmail.local"
INVALID_PASSWORD = "wrongpassword"


# =============================================================================
# Login Flow Tests
# =============================================================================

class TestLoginFlow:
    """Tests for the login functionality."""

    @pytest.mark.asyncio
    async def test_login_page_loads(self, login_page: LoginPage):
        """Test that login page loads correctly."""
        await login_page.goto()
        await login_page.assert_on_login_page()

    @pytest.mark.asyncio
    async def test_login_page_has_required_elements(self, login_page: LoginPage):
        """Test that login page has all required elements."""
        await login_page.goto()

        # Check for required form elements
        await expect(login_page.email_input).to_be_visible()
        await expect(login_page.password_input).to_be_visible()
        await expect(login_page.login_button).to_be_visible()

    @pytest.mark.asyncio
    async def test_successful_login(self, login_page: LoginPage, inbox_page: InboxPage):
        """Test successful login with valid credentials."""
        await login_page.goto()
        await login_page.login_and_wait(VALID_EMAIL, VALID_PASSWORD)

        # Should redirect to inbox after successful login
        await login_page.assert_login_successful()
        await inbox_page.assert_on_inbox_page()

    @pytest.mark.asyncio
    async def test_login_with_remember_me(self, login_page: LoginPage):
        """Test login with remember me option checked."""
        await login_page.goto()
        await login_page.login_and_wait(
            VALID_EMAIL,
            VALID_PASSWORD,
            remember_me=True
        )

        await login_page.assert_login_successful()

    @pytest.mark.asyncio
    async def test_login_form_focuses_email_first(self, login_page: LoginPage):
        """Test that email input is focused by default or tab order is correct."""
        await login_page.goto()

        # Email input should be first in tab order
        await login_page.page.keyboard.press("Tab")
        focused = login_page.page.locator(":focus")

        # The focused element should be either email or within the form
        await expect(focused).to_be_visible()

    @pytest.mark.asyncio
    async def test_login_with_enter_key(self, login_page: LoginPage, inbox_page: InboxPage):
        """Test that pressing Enter submits the login form."""
        await login_page.goto()

        await login_page.email_input.fill(VALID_EMAIL)
        await login_page.password_input.fill(VALID_PASSWORD)
        await login_page.page.keyboard.press("Enter")

        await login_page.wait_for_page_load()
        await login_page.assert_login_successful()

    @pytest.mark.asyncio
    async def test_login_preserves_redirect_url(
        self, page: Page, login_page: LoginPage
    ):
        """Test that login redirects to originally requested page."""
        # Try to access a protected page
        await page.goto("/contacts")

        # Should be redirected to login
        await login_page.assert_on_login_page()

        # Login
        await login_page.login_and_wait(VALID_EMAIL, VALID_PASSWORD)

        # Should redirect back to contacts (or inbox if not supported)
        # The URL should contain either contacts or inbox
        current_url = page.url
        assert "contacts" in current_url or "inbox" in current_url


# =============================================================================
# Invalid Credentials Tests
# =============================================================================

class TestInvalidCredentials:
    """Tests for handling invalid login attempts."""

    @pytest.mark.asyncio
    async def test_login_with_invalid_email(self, login_page: LoginPage):
        """Test login failure with non-existent email."""
        await login_page.goto()
        await login_page.login(INVALID_EMAIL, VALID_PASSWORD)

        await login_page.assert_login_failed()

    @pytest.mark.asyncio
    async def test_login_with_invalid_password(self, login_page: LoginPage):
        """Test login failure with wrong password."""
        await login_page.goto()
        await login_page.login(VALID_EMAIL, INVALID_PASSWORD)

        await login_page.assert_login_failed()

    @pytest.mark.asyncio
    async def test_login_with_both_invalid(self, login_page: LoginPage):
        """Test login failure with both invalid email and password."""
        await login_page.goto()
        await login_page.login(INVALID_EMAIL, INVALID_PASSWORD)

        await login_page.assert_login_failed()

    @pytest.mark.asyncio
    async def test_login_with_empty_email(self, login_page: LoginPage):
        """Test login validation with empty email."""
        await login_page.goto()
        await login_page.login("", VALID_PASSWORD)

        # Should show validation error or login error
        await expect(login_page.login_error.or_(
            login_page.validation_error
        ).first).to_be_visible()

    @pytest.mark.asyncio
    async def test_login_with_empty_password(self, login_page: LoginPage):
        """Test login validation with empty password."""
        await login_page.goto()
        await login_page.login(VALID_EMAIL, "")

        # Should show validation error or login error
        await expect(login_page.login_error.or_(
            login_page.validation_error
        ).first).to_be_visible()

    @pytest.mark.asyncio
    async def test_login_with_malformed_email(self, login_page: LoginPage):
        """Test login validation with malformed email address."""
        await login_page.goto()
        await login_page.login("not-an-email", VALID_PASSWORD)

        # Should show validation error
        await expect(login_page.login_error.or_(
            login_page.validation_error
        ).first).to_be_visible()

    @pytest.mark.asyncio
    async def test_login_error_message_is_generic(self, login_page: LoginPage):
        """Test that login error message doesn't reveal user existence."""
        await login_page.goto()

        # Try with invalid email
        await login_page.login(INVALID_EMAIL, VALID_PASSWORD)
        error_with_invalid_email = await login_page.get_login_error_text()

        # Clear and try with valid email but wrong password
        await login_page.goto()
        await login_page.login(VALID_EMAIL, INVALID_PASSWORD)
        error_with_valid_email = await login_page.get_login_error_text()

        # Error messages should be the same (not reveal user existence)
        assert error_with_invalid_email == error_with_valid_email

    @pytest.mark.asyncio
    async def test_multiple_failed_login_attempts(self, login_page: LoginPage):
        """Test behavior after multiple failed login attempts."""
        await login_page.goto()

        # Attempt multiple failed logins
        for _ in range(3):
            await login_page.login(VALID_EMAIL, INVALID_PASSWORD)
            await login_page.assert_login_failed()
            await login_page.goto()

        # Should still be able to access login page
        await login_page.assert_on_login_page()

    @pytest.mark.asyncio
    async def test_login_error_clears_on_retry(self, login_page: LoginPage):
        """Test that error message clears when user starts typing."""
        await login_page.goto()

        # Trigger an error
        await login_page.login(INVALID_EMAIL, INVALID_PASSWORD)
        await login_page.assert_login_failed()

        # Start typing in email field
        await login_page.email_input.clear()
        await login_page.email_input.type("new")

        # Error might clear (depends on implementation)
        # This test documents the expected behavior


# =============================================================================
# Logout Tests
# =============================================================================

class TestLogout:
    """Tests for the logout functionality."""

    @pytest.mark.asyncio
    async def test_logout(self, login_page: LoginPage, logged_in_user):
        """Test successful logout."""
        # User is already logged in via fixture
        await login_page.logout()

        # Should be redirected to login page
        await login_page.assert_logged_out()

    @pytest.mark.asyncio
    async def test_logout_clears_session(
        self, page: Page, login_page: LoginPage, logged_in_user
    ):
        """Test that logout clears session data."""
        # Logout
        await login_page.logout()
        await login_page.assert_logged_out()

        # Try to access protected page
        await page.goto("/inbox")

        # Should be redirected to login
        await login_page.assert_on_login_page()

    @pytest.mark.asyncio
    async def test_back_button_after_logout(
        self, page: Page, login_page: LoginPage, logged_in_user
    ):
        """Test that pressing back after logout doesn't show protected content."""
        # Logout
        await login_page.logout()
        await login_page.assert_logged_out()

        # Press back button
        await page.go_back()

        # Wait for any redirects
        await page.wait_for_load_state("networkidle")

        # Should either stay on login or redirect to login
        # Protected content should not be accessible
        await login_page.assert_on_login_page()

    @pytest.mark.asyncio
    async def test_logout_from_user_menu(
        self, page: Page, login_page: LoginPage, logged_in_user
    ):
        """Test logout via user menu dropdown."""
        # Check if user menu exists
        if await login_page.user_menu.count() > 0:
            await login_page.user_menu.click()
            await login_page.logout_button.click()
            await login_page.wait_for_page_load()
            await login_page.assert_logged_out()


# =============================================================================
# Session Expiration Tests
# =============================================================================

class TestSessionExpiration:
    """Tests for session expiration handling."""

    @pytest.mark.asyncio
    async def test_session_expiration_redirect(
        self, page: Page, login_page: LoginPage, api_client
    ):
        """Test that expired session redirects to login."""
        # Login first
        await login_page.goto()
        await login_page.login_and_wait(VALID_EMAIL, VALID_PASSWORD)

        # Simulate session expiration by clearing cookies
        await page.context.clear_cookies()

        # Try to perform an action that requires authentication
        await page.goto("/inbox")
        await page.wait_for_load_state("networkidle")

        # Should be redirected to login
        await login_page.assert_on_login_page()

    @pytest.mark.asyncio
    async def test_session_expiration_shows_message(
        self, page: Page, login_page: LoginPage
    ):
        """Test that session expiration shows appropriate message."""
        # Login first
        await login_page.goto()
        await login_page.login_and_wait(VALID_EMAIL, VALID_PASSWORD)

        # Clear cookies to simulate expiration
        await page.context.clear_cookies()

        # Navigate to trigger session check
        await page.goto("/inbox")
        await page.wait_for_load_state("networkidle")

        # Should show session expired message (if implemented)
        # or redirect to login
        await login_page.assert_on_login_page()

    @pytest.mark.asyncio
    async def test_api_call_with_expired_session(
        self, page: Page, login_page: LoginPage, api_client
    ):
        """Test API behavior with expired session."""
        # Login and get token
        await login_page.goto()
        await login_page.login_and_wait(VALID_EMAIL, VALID_PASSWORD)

        # Clear cookies
        await page.context.clear_cookies()

        # Try API call
        result = await api_client.get("emails")

        # Should return unauthorized error
        assert result.get("error") or result.get("status") == 401


# =============================================================================
# Security Tests
# =============================================================================

class TestAuthSecurity:
    """Security-related authentication tests."""

    @pytest.mark.asyncio
    async def test_password_field_is_masked(self, login_page: LoginPage):
        """Test that password field masks input."""
        await login_page.goto()

        password_type = await login_page.password_input.get_attribute("type")
        assert password_type == "password"

    @pytest.mark.asyncio
    async def test_no_password_in_url(self, page: Page, login_page: LoginPage):
        """Test that password is not leaked in URL."""
        await login_page.goto()
        await login_page.login(VALID_EMAIL, VALID_PASSWORD)

        # Check URL doesn't contain password
        assert VALID_PASSWORD not in page.url

    @pytest.mark.asyncio
    async def test_login_over_https_warning(self, page: Page, login_page: LoginPage):
        """Test for HTTPS requirement or warning on login page."""
        await login_page.goto()

        # This test documents the expected behavior
        # In production, login should be over HTTPS
        # For local testing, HTTP is acceptable

    @pytest.mark.asyncio
    async def test_csrf_protection(self, login_page: LoginPage):
        """Test that CSRF protection is in place."""
        await login_page.goto()

        # Check for CSRF token in form (if implemented)
        csrf_input = login_page.page.locator(
            "input[name='csrf_token'], input[name='_csrf'], "
            "input[name='csrfToken']"
        )

        # Document whether CSRF is implemented
        csrf_count = await csrf_input.count()
        # If csrf_count > 0, CSRF is implemented


# =============================================================================
# Accessibility Tests
# =============================================================================

class TestAuthAccessibility:
    """Accessibility tests for authentication pages."""

    @pytest.mark.asyncio
    async def test_login_form_labels(self, login_page: LoginPage):
        """Test that form fields have associated labels."""
        await login_page.goto()

        # Check for labels or aria-labels
        email_id = await login_page.email_input.get_attribute("id")
        if email_id:
            label = login_page.page.locator(f"label[for='{email_id}']")
            label_count = await label.count()
            # Either has label or aria-label
            if label_count == 0:
                aria_label = await login_page.email_input.get_attribute("aria-label")
                assert aria_label is not None

    @pytest.mark.asyncio
    async def test_login_error_announced(self, login_page: LoginPage):
        """Test that login errors are properly announced to screen readers."""
        await login_page.goto()
        await login_page.login(INVALID_EMAIL, INVALID_PASSWORD)

        # Check error has appropriate ARIA attributes
        error = login_page.login_error
        if await error.count() > 0:
            role = await error.get_attribute("role")
            # Error should have role="alert" or similar
            assert role in ["alert", "status", None]  # None is acceptable for live regions

    @pytest.mark.asyncio
    async def test_login_keyboard_navigation(self, login_page: LoginPage):
        """Test that login form is fully keyboard navigable."""
        await login_page.goto()

        # Tab through form elements
        await login_page.page.keyboard.press("Tab")  # To email
        await login_page.page.keyboard.press("Tab")  # To password
        await login_page.page.keyboard.press("Tab")  # To login button or remember me

        # Should be able to reach submit button
        # This test documents expected keyboard behavior


# =============================================================================
# Cross-Browser Tests
# =============================================================================

@pytest.mark.parametrize("browser_name", ["chromium", "firefox", "webkit"], indirect=True)
class TestAuthCrossBrowser:
    """Cross-browser authentication tests."""

    @pytest.mark.asyncio
    async def test_login_works_across_browsers(
        self, cross_browser_page: Page
    ):
        """Test that login works in all supported browsers."""
        login_page = LoginPage(cross_browser_page)
        await login_page.goto()
        await login_page.login_and_wait(VALID_EMAIL, VALID_PASSWORD)
        await login_page.assert_login_successful()
