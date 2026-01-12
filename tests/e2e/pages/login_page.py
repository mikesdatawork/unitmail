"""
Login Page Object for authentication-related tests.
"""

from playwright.async_api import Page, expect, Locator
from .base_page import BasePage


class LoginPage(BasePage):
    """Page Object for the login page."""

    def __init__(self, page: Page, base_url: str = "http://localhost:8080"):
        super().__init__(page, base_url)
        self.path = "/login"

    # Selectors
    @property
    def email_input(self) -> Locator:
        """Email/username input field."""
        return self.page.locator(
            "input[type='email'], input[name='email'], "
            "input[name='username'], input[id='email'], "
            "[data-testid='email-input'], [data-testid='username-input']"
        )

    @property
    def password_input(self) -> Locator:
        """Password input field."""
        return self.page.locator(
            "input[type='password'], input[name='password'], "
            "input[id='password'], [data-testid='password-input']"
        )

    @property
    def login_button(self) -> Locator:
        """Login/submit button."""
        return self.page.locator(
            "button[type='submit'], button:has-text('Login'), "
            "button:has-text('Sign In'), button:has-text('Log In'), "
            "[data-testid='login-button']"
        )

    @property
    def remember_me_checkbox(self) -> Locator:
        """Remember me checkbox."""
        return self.page.locator(
            "input[type='checkbox'][name='remember'], "
            "[data-testid='remember-me'], #remember-me"
        )

    @property
    def forgot_password_link(self) -> Locator:
        """Forgot password link."""
        return self.page.locator(
            "a:has-text('Forgot'), a:has-text('Reset'), "
            "[data-testid='forgot-password']"
        )

    @property
    def register_link(self) -> Locator:
        """Registration link."""
        return self.page.locator(
            "a:has-text('Register'), a:has-text('Sign Up'), "
            "a:has-text('Create Account'), [data-testid='register-link']"
        )

    @property
    def login_error(self) -> Locator:
        """Login error message."""
        return self.page.locator(
            ".login-error, .error-message, [data-testid='login-error'], "
            "[role='alert'], .alert-danger, .alert-error"
        )

    @property
    def validation_error(self) -> Locator:
        """Form validation error messages."""
        return self.page.locator(
            ".validation-error, .field-error, .invalid-feedback, "
            "[data-testid='validation-error']"
        )

    @property
    def login_form(self) -> Locator:
        """Login form element."""
        return self.page.locator(
            "form, [data-testid='login-form'], .login-form"
        )

    @property
    def logout_button(self) -> Locator:
        """Logout button (visible after login)."""
        return self.page.locator(
            "button:has-text('Logout'), button:has-text('Sign Out'), "
            "button:has-text('Log Out'), a:has-text('Logout'), "
            "[data-testid='logout-button']"
        )

    @property
    def user_menu(self) -> Locator:
        """User menu dropdown (for accessing logout)."""
        return self.page.locator(
            "[data-testid='user-menu'], .user-menu, .profile-menu, "
            ".account-menu, [aria-label='User menu']"
        )

    @property
    def session_expired_message(self) -> Locator:
        """Session expired notification."""
        return self.page.locator(
            ":has-text('session expired'), :has-text('Session Expired'), "
            ":has-text('logged out'), [data-testid='session-expired']"
        )

    # Actions
    async def goto(self) -> None:
        """Navigate to the login page."""
        await self.navigate_to(self.path)
        await self.wait_for_page_load()

    async def login(
        self, email: str, password: str, remember_me: bool = False
    ) -> None:
        """
        Perform login with given credentials.

        Args:
            email: User email or username
            password: User password
            remember_me: Whether to check remember me option
        """
        await self.fill_input(self.email_input, email)
        await self.fill_input(self.password_input, password)

        if remember_me:
            await self.check_checkbox(self.remember_me_checkbox)

        await self.login_button.click()

    async def login_and_wait(
        self, email: str, password: str, remember_me: bool = False
    ) -> None:
        """Login and wait for navigation to complete."""
        await self.login(email, password, remember_me)
        await self.wait_for_page_load()

    async def logout(self) -> None:
        """Perform logout."""
        # Try to find logout button directly
        if await self.logout_button.count() > 0:
            await self.logout_button.click()
        else:
            # Try opening user menu first
            if await self.user_menu.count() > 0:
                await self.user_menu.click()
                await self.logout_button.click()
        await self.wait_for_page_load()

    async def click_forgot_password(self) -> None:
        """Click the forgot password link."""
        await self.forgot_password_link.click()
        await self.wait_for_page_load()

    async def click_register(self) -> None:
        """Click the register link."""
        await self.register_link.click()
        await self.wait_for_page_load()

    # Assertions
    async def assert_on_login_page(self) -> None:
        """Assert that we are on the login page."""
        await expect(self.login_form).to_be_visible()

    async def assert_login_successful(self) -> None:
        """Assert that login was successful."""
        # Should not be on login page anymore
        await expect(self.login_form).to_be_hidden(timeout=10000)
        # Should not show login error
        await expect(self.login_error).to_be_hidden()

    async def assert_login_failed(self, error_text: str = None) -> None:
        """Assert that login failed with optional error text check."""
        await expect(self.login_error).to_be_visible()
        if error_text:
            await expect(self.login_error).to_contain_text(error_text)

    async def assert_validation_error_shown(self, error_text: str = None) -> None:
        """Assert that validation error is shown."""
        await expect(self.validation_error).to_be_visible()
        if error_text:
            await expect(self.validation_error).to_contain_text(error_text)

    async def assert_logged_out(self) -> None:
        """Assert that user is logged out."""
        await expect(self.login_form).to_be_visible()

    async def assert_session_expired(self) -> None:
        """Assert that session expired message is shown."""
        await expect(self.session_expired_message).to_be_visible()

    async def get_login_error_text(self) -> str:
        """Get the text of the login error message."""
        return await self.login_error.text_content()
