"""
Inbox Page Object for email list and management tests.
"""

from typing import Optional, List
from playwright.async_api import Page, expect, Locator
from .base_page import BasePage


class InboxPage(BasePage):
    """Page Object for the inbox/email list page."""

    def __init__(self, page: Page, base_url: str = "http://localhost:8080"):
        super().__init__(page, base_url)
        self.path = "/inbox"

    # Selectors - Email List
    @property
    def email_list(self) -> Locator:
        """Container for email list."""
        return self.page.locator(
            "[data-testid='email-list'], .email-list, .message-list, "
            ".inbox-list, [role='list']"
        )

    @property
    def email_items(self) -> Locator:
        """Individual email items in the list."""
        return self.page.locator(
            "[data-testid='email-item'], .email-item, .message-item, "
            ".email-row, [role='listitem'], tr.email"
        )

    @property
    def email_subject(self) -> Locator:
        """Email subject elements."""
        return self.page.locator(
            "[data-testid='email-subject'], .email-subject, .subject, "
            ".message-subject"
        )

    @property
    def email_sender(self) -> Locator:
        """Email sender elements."""
        return self.page.locator(
            "[data-testid='email-sender'], .email-sender, .sender, "
            ".from, .message-from"
        )

    @property
    def email_date(self) -> Locator:
        """Email date elements."""
        return self.page.locator(
            "[data-testid='email-date'], .email-date, .date, .timestamp, "
            ".message-date"
        )

    @property
    def email_preview(self) -> Locator:
        """Email preview/snippet elements."""
        return self.page.locator(
            "[data-testid='email-preview'], .email-preview, .snippet, "
            ".preview, .message-preview"
        )

    @property
    def unread_emails(self) -> Locator:
        """Unread email items."""
        return self.page.locator(
            ".unread, [data-unread='true'], [data-testid='email-item'].unread, "
            ".email-item.unread, tr.unread"
        )

    @property
    def starred_emails(self) -> Locator:
        """Starred email items."""
        return self.page.locator(
            ".starred, [data-starred='true'], [data-testid='email-item'].starred, "
            ".email-item.starred"
        )

    @property
    def selected_emails(self) -> Locator:
        """Currently selected email items."""
        return self.page.locator(
            ".selected, [data-selected='true'], [aria-selected='true'], "
            ".email-item.selected"
        )

    @property
    def empty_inbox_message(self) -> Locator:
        """Empty inbox placeholder message."""
        return self.page.locator(
            "[data-testid='empty-inbox'], .empty-inbox, .no-emails, "
            ":has-text('No emails'), :has-text('Inbox is empty')"
        )

    # Selectors - Actions
    @property
    def refresh_button(self) -> Locator:
        """Refresh inbox button."""
        return self.page.locator(
            "button:has-text('Refresh'), button[aria-label='Refresh'], "
            "[data-testid='refresh-button'], .refresh-btn"
        )

    @property
    def compose_button(self) -> Locator:
        """Compose new email button."""
        return self.page.locator(
            "button:has-text('Compose'), button:has-text('New'), "
            "[data-testid='compose-button'], .compose-btn, "
            "a:has-text('Compose'), a:has-text('New Email')"
        )

    @property
    def delete_button(self) -> Locator:
        """Delete selected emails button."""
        return self.page.locator(
            "button:has-text('Delete'), button[aria-label='Delete'], "
            "[data-testid='delete-button'], .delete-btn"
        )

    @property
    def archive_button(self) -> Locator:
        """Archive selected emails button."""
        return self.page.locator(
            "button:has-text('Archive'), button[aria-label='Archive'], "
            "[data-testid='archive-button'], .archive-btn"
        )

    @property
    def mark_read_button(self) -> Locator:
        """Mark as read button."""
        return self.page.locator(
            "button:has-text('Mark as read'), button:has-text('Mark Read'), "
            "[data-testid='mark-read-button']"
        )

    @property
    def mark_unread_button(self) -> Locator:
        """Mark as unread button."""
        return self.page.locator(
            "button:has-text('Mark as unread'), button:has-text('Mark Unread'), "
            "[data-testid='mark-unread-button']"
        )

    @property
    def select_all_checkbox(self) -> Locator:
        """Select all emails checkbox."""
        return self.page.locator(
            "[data-testid='select-all'], .select-all, "
            "input[type='checkbox'][aria-label*='select all' i]"
        )

    @property
    def search_input(self) -> Locator:
        """Search emails input."""
        return self.page.locator(
            "input[type='search'], input[placeholder*='Search'], "
            "[data-testid='search-input'], .search-input"
        )

    @property
    def search_button(self) -> Locator:
        """Search button."""
        return self.page.locator(
            "button[aria-label='Search'], button:has-text('Search'), "
            "[data-testid='search-button']"
        )

    # Selectors - Folders
    @property
    def folder_inbox(self) -> Locator:
        """Inbox folder link."""
        return self.page.locator(
            "a:has-text('Inbox'), [data-testid='folder-inbox'], "
            ".folder-inbox, [data-folder='inbox']"
        )

    @property
    def folder_sent(self) -> Locator:
        """Sent folder link."""
        return self.page.locator(
            "a:has-text('Sent'), [data-testid='folder-sent'], "
            ".folder-sent, [data-folder='sent']"
        )

    @property
    def folder_drafts(self) -> Locator:
        """Drafts folder link."""
        return self.page.locator(
            "a:has-text('Drafts'), [data-testid='folder-drafts'], "
            ".folder-drafts, [data-folder='drafts']"
        )

    @property
    def folder_trash(self) -> Locator:
        """Trash folder link."""
        return self.page.locator(
            "a:has-text('Trash'), [data-testid='folder-trash'], "
            ".folder-trash, [data-folder='trash']"
        )

    @property
    def folder_spam(self) -> Locator:
        """Spam folder link."""
        return self.page.locator(
            "a:has-text('Spam'), a:has-text('Junk'), [data-testid='folder-spam'], "
            ".folder-spam, [data-folder='spam']"
        )

    # Pagination
    @property
    def pagination(self) -> Locator:
        """Pagination container."""
        return self.page.locator(
            "[data-testid='pagination'], .pagination, nav[aria-label='Pagination']"
        )

    @property
    def next_page_button(self) -> Locator:
        """Next page button."""
        return self.page.locator(
            "button:has-text('Next'), [aria-label='Next page'], "
            "[data-testid='next-page'], .next-page"
        )

    @property
    def prev_page_button(self) -> Locator:
        """Previous page button."""
        return self.page.locator(
            "button:has-text('Previous'), button:has-text('Prev'), "
            "[aria-label='Previous page'], [data-testid='prev-page'], .prev-page"
        )

    # Actions
    async def goto(self) -> None:
        """Navigate to the inbox page."""
        await self.navigate_to(self.path)
        await self.wait_for_page_load()

    async def refresh_inbox(self) -> None:
        """Refresh the inbox."""
        await self.refresh_button.click()
        await self.wait_for_loading_complete()

    async def get_email_count(self) -> int:
        """Get the number of emails in the list."""
        return await self.email_items.count()

    async def get_unread_count(self) -> int:
        """Get the number of unread emails."""
        return await self.unread_emails.count()

    async def click_email(self, index: int = 0) -> None:
        """Click on an email by index."""
        await self.email_items.nth(index).click()

    async def click_email_by_subject(self, subject: str) -> None:
        """Click on an email by subject."""
        email = self.email_items.filter(has_text=subject).first
        await email.click()

    async def double_click_email(self, index: int = 0) -> None:
        """Double-click on an email to open it."""
        await self.email_items.nth(index).dblclick()

    async def select_email(self, index: int = 0) -> None:
        """Select an email by its checkbox."""
        checkbox = self.email_items.nth(index).locator("input[type='checkbox']")
        await checkbox.check()

    async def select_emails(self, indices: List[int]) -> None:
        """Select multiple emails by indices."""
        for index in indices:
            await self.select_email(index)

    async def select_all_emails(self) -> None:
        """Select all emails."""
        await self.select_all_checkbox.check()

    async def star_email(self, index: int = 0) -> None:
        """Star an email by index."""
        star_btn = self.email_items.nth(index).locator(
            "button[aria-label*='Star'], .star-btn, [data-testid='star-button'], "
            ".star-icon"
        )
        await star_btn.click()

    async def unstar_email(self, index: int = 0) -> None:
        """Unstar a starred email."""
        # Same action as starring - toggles the state
        await self.star_email(index)

    async def delete_email(self, index: int = 0) -> None:
        """Delete an email by index."""
        await self.select_email(index)
        await self.delete_button.click()

    async def delete_selected_emails(self) -> None:
        """Delete all selected emails."""
        await self.delete_button.click()

    async def archive_email(self, index: int = 0) -> None:
        """Archive an email by index."""
        await self.select_email(index)
        await self.archive_button.click()

    async def mark_email_read(self, index: int = 0) -> None:
        """Mark an email as read."""
        await self.select_email(index)
        await self.mark_read_button.click()

    async def mark_email_unread(self, index: int = 0) -> None:
        """Mark an email as unread."""
        await self.select_email(index)
        await self.mark_unread_button.click()

    async def search_emails(self, query: str) -> None:
        """Search for emails."""
        await self.fill_input(self.search_input, query)
        await self.search_button.click()
        await self.wait_for_loading_complete()

    async def clear_search(self) -> None:
        """Clear the search input."""
        await self.search_input.clear()
        await self.search_button.click()
        await self.wait_for_loading_complete()

    async def go_to_folder(self, folder: str) -> None:
        """Navigate to a specific folder."""
        folder_locators = {
            "inbox": self.folder_inbox,
            "sent": self.folder_sent,
            "drafts": self.folder_drafts,
            "trash": self.folder_trash,
            "spam": self.folder_spam,
        }
        locator = folder_locators.get(folder.lower())
        if locator:
            await locator.click()
            await self.wait_for_loading_complete()

    async def click_compose(self) -> None:
        """Click the compose button to create new email."""
        await self.compose_button.click()

    async def go_to_next_page(self) -> None:
        """Go to the next page of emails."""
        await self.next_page_button.click()
        await self.wait_for_loading_complete()

    async def go_to_prev_page(self) -> None:
        """Go to the previous page of emails."""
        await self.prev_page_button.click()
        await self.wait_for_loading_complete()

    # Helper methods
    async def get_email_subject(self, index: int = 0) -> str:
        """Get the subject of an email by index."""
        return await self.email_items.nth(index).locator(
            "[data-testid='email-subject'], .email-subject, .subject"
        ).text_content()

    async def get_email_sender(self, index: int = 0) -> str:
        """Get the sender of an email by index."""
        return await self.email_items.nth(index).locator(
            "[data-testid='email-sender'], .email-sender, .sender, .from"
        ).text_content()

    async def is_email_unread(self, index: int = 0) -> bool:
        """Check if an email is unread."""
        email = self.email_items.nth(index)
        class_attr = await email.get_attribute("class") or ""
        data_unread = await email.get_attribute("data-unread")
        return "unread" in class_attr or data_unread == "true"

    async def is_email_starred(self, index: int = 0) -> bool:
        """Check if an email is starred."""
        email = self.email_items.nth(index)
        class_attr = await email.get_attribute("class") or ""
        data_starred = await email.get_attribute("data-starred")
        return "starred" in class_attr or data_starred == "true"

    # Assertions
    async def assert_on_inbox_page(self) -> None:
        """Assert that we are on the inbox page."""
        await expect(self.email_list).to_be_visible()

    async def assert_email_count(self, count: int) -> None:
        """Assert specific number of emails."""
        await expect(self.email_items).to_have_count(count)

    async def assert_email_visible(self, subject: str) -> None:
        """Assert that an email with given subject is visible."""
        email = self.email_items.filter(has_text=subject)
        await expect(email.first).to_be_visible()

    async def assert_email_not_visible(self, subject: str) -> None:
        """Assert that an email with given subject is not visible."""
        email = self.email_items.filter(has_text=subject)
        await expect(email).to_have_count(0)

    async def assert_inbox_empty(self) -> None:
        """Assert that inbox is empty."""
        await expect(self.empty_inbox_message).to_be_visible()

    async def assert_unread_count(self, count: int) -> None:
        """Assert specific number of unread emails."""
        await expect(self.unread_emails).to_have_count(count)
