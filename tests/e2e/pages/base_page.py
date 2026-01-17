"""
Base Page Object class with common functionality for all pages.
"""

from typing import Optional
from playwright.async_api import Page, expect, Locator


class BasePage:
    """Base class for all Page Objects with common functionality."""

    def __init__(self, page: Page, base_url: str = "http://localhost:8080"):
        self.page = page
        self.base_url = base_url

    # Common selectors
    @property
    def header(self) -> Locator:
        """Application header."""
        return self.page.locator("header, [data-testid='app-header']")

    @property
    def sidebar(self) -> Locator:
        """Application sidebar/navigation."""
        return self.page.locator(
            "nav, aside, [data-testid='sidebar'], .sidebar"
        )

    @property
    def main_content(self) -> Locator:
        """Main content area."""
        return self.page.locator(
            "main, [data-testid='main-content'], .main-content")

    @property
    def loading_indicator(self) -> Locator:
        """Loading spinner or indicator."""
        return self.page.locator(
            ".loading, .spinner, [data-testid='loading'], [aria-busy='true']"
        )

    @property
    def toast_notification(self) -> Locator:
        """Toast/notification messages."""
        return self.page.locator(
            ".toast, .notification, [data-testid='toast'], [role='alert']"
        )

    @property
    def error_message(self) -> Locator:
        """Error message elements."""
        return self.page.locator(
            ".error, .error-message, [data-testid='error'], [role='alert'].error"
        )

    @property
    def success_message(self) -> Locator:
        """Success message elements."""
        return self.page.locator(
            ".success, .success-message, [data-testid='success']"
        )

    @property
    def modal(self) -> Locator:
        """Modal/dialog elements."""
        return self.page.locator(
            "[role='dialog'], .modal, [data-testid='modal']"
        )

    @property
    def modal_close_button(self) -> Locator:
        """Close button within modal."""
        return self.modal.locator(
            "button:has-text('Close'), button:has-text('Cancel'), "
            "[data-testid='modal-close'], .modal-close"
        )

    @property
    def confirm_button(self) -> Locator:
        """Confirm/OK button in dialogs."""
        return self.page.locator(
            "button:has-text('Confirm'), button:has-text('OK'), "
            "button:has-text('Yes'), [data-testid='confirm-button']"
        )

    @property
    def cancel_button(self) -> Locator:
        """Cancel button in dialogs."""
        return self.page.locator(
            "button:has-text('Cancel'), button:has-text('No'), "
            "[data-testid='cancel-button']"
        )

    # Common navigation methods
    async def navigate_to(self, path: str = "") -> None:
        """Navigate to a specific path."""
        url = f"{self.base_url}/{path.lstrip('/')}" if path else self.base_url
        await self.page.goto(url)

    async def wait_for_page_load(self, timeout: int = 30000) -> None:
        """Wait for page to fully load."""
        await self.page.wait_for_load_state("networkidle", timeout=timeout)

    async def wait_for_loading_complete(self, timeout: int = 30000) -> None:
        """Wait for loading indicator to disappear."""
        try:
            await self.loading_indicator.wait_for(state="hidden", timeout=timeout)
        except Exception:
            # Loading indicator might not exist, which is fine
            pass

    # Common interaction methods
    async def click_and_wait(self, locator: Locator,
                             timeout: int = 5000) -> None:
        """Click an element and wait for navigation/network."""
        await locator.click()
        await self.page.wait_for_load_state("networkidle", timeout=timeout)

    async def fill_input(
        self, locator: Locator, value: str, clear_first: bool = True
    ) -> None:
        """Fill an input field."""
        if clear_first:
            await locator.clear()
        await locator.fill(value)

    async def get_input_value(self, locator: Locator) -> str:
        """Get the current value of an input."""
        return await locator.input_value()

    async def select_option(self, locator: Locator, value: str) -> None:
        """Select an option from a dropdown."""
        await locator.select_option(value)

    async def check_checkbox(self, locator: Locator,
                             check: bool = True) -> None:
        """Check or uncheck a checkbox."""
        if check:
            await locator.check()
        else:
            await locator.uncheck()

    # Common assertion helpers
    async def assert_url_contains(self, text: str) -> None:
        """Assert that current URL contains specific text."""
        await expect(self.page).to_have_url(f"*{text}*")

    async def assert_url_is(self, url: str) -> None:
        """Assert that current URL matches exactly."""
        await expect(self.page).to_have_url(url)

    async def assert_title_contains(self, text: str) -> None:
        """Assert that page title contains specific text."""
        await expect(self.page).to_have_title(f"*{text}*")

    async def assert_visible(self, locator: Locator) -> None:
        """Assert that an element is visible."""
        await expect(locator).to_be_visible()

    async def assert_hidden(self, locator: Locator) -> None:
        """Assert that an element is hidden."""
        await expect(locator).to_be_hidden()

    async def assert_text_content(self, locator: Locator, text: str) -> None:
        """Assert that element contains specific text."""
        await expect(locator).to_contain_text(text)

    async def assert_has_class(self, locator: Locator,
                               class_name: str) -> None:
        """Assert that element has a specific class."""
        await expect(locator).to_have_class(f"*{class_name}*")

    # Toast/notification helpers
    async def wait_for_toast(
            self, text: Optional[str] = None, timeout: int = 5000) -> None:
        """Wait for a toast notification to appear."""
        if text:
            await expect(self.toast_notification.filter(has_text=text)).to_be_visible(
                timeout=timeout
            )
        else:
            await expect(self.toast_notification.first).to_be_visible(timeout=timeout)

    async def dismiss_toast(self) -> None:
        """Dismiss any visible toast notification."""
        close_btn = self.toast_notification.locator(
            "button, [data-testid='toast-close']"
        )
        if await close_btn.count() > 0:
            await close_btn.first.click()

    # Modal helpers
    async def wait_for_modal(self, timeout: int = 5000) -> None:
        """Wait for modal to appear."""
        await expect(self.modal).to_be_visible(timeout=timeout)

    async def close_modal(self) -> None:
        """Close the modal dialog."""
        await self.modal_close_button.click()
        await expect(self.modal).to_be_hidden()

    async def confirm_modal(self) -> None:
        """Click confirm button in modal."""
        await self.confirm_button.click()

    # Screenshot helper
    async def take_screenshot(self, name: str) -> bytes:
        """Take a screenshot with given name."""
        return await self.page.screenshot(path=f"screenshots/{name}.png")

    # Keyboard shortcuts
    async def press_key(self, key: str) -> None:
        """Press a keyboard key."""
        await self.page.keyboard.press(key)

    async def press_shortcut(self, *keys: str) -> None:
        """Press a keyboard shortcut (e.g., Ctrl+S)."""
        await self.page.keyboard.press("+".join(keys))
