"""
Email Reader Page Object for viewing individual emails.
"""

from typing import List
from playwright.async_api import Page, expect, Locator
from .base_page import BasePage


class EmailReaderPage(BasePage):
    """Page Object for the email reader/viewer page."""

    def __init__(self, page: Page, base_url: str = "http://localhost:8080"):
        super().__init__(page, base_url)
        self.path = "/email"

    # Selectors - Email Content
    @property
    def email_container(self) -> Locator:
        """Main email reader container."""
        return self.page.locator(
            "[data-testid='email-reader'], .email-reader, .email-view, "
            ".message-view, #email-content"
        )

    @property
    def email_subject(self) -> Locator:
        """Email subject header."""
        return self.page.locator(
            "[data-testid='email-subject'], .email-subject, "
            "h1.subject, h2.subject, .message-subject"
        )

    @property
    def email_sender(self) -> Locator:
        """Email sender information."""
        return self.page.locator(
            "[data-testid='email-sender'], .email-sender, "
            ".from-address, .sender"
        )

    @property
    def email_recipients(self) -> Locator:
        """Email recipients (To field)."""
        return self.page.locator(
            "[data-testid='email-recipients'], .email-recipients, "
            ".to-address, .recipients"
        )

    @property
    def email_cc(self) -> Locator:
        """Email CC recipients."""
        return self.page.locator(
            "[data-testid='email-cc'], .email-cc, .cc-address"
        )

    @property
    def email_date(self) -> Locator:
        """Email date/timestamp."""
        return self.page.locator(
            "[data-testid='email-date'], .email-date, "
            ".timestamp, .date, time"
        )

    @property
    def email_body(self) -> Locator:
        """Email body content."""
        return self.page.locator(
            "[data-testid='email-body'], .email-body, "
            ".message-body, .content, article"
        )

    @property
    def email_body_html(self) -> Locator:
        """HTML email body (iframe or div)."""
        return self.page.locator(
            "iframe.email-content, [data-testid='email-html'], "
            ".html-content"
        )

    @property
    def email_body_plain(self) -> Locator:
        """Plain text email body."""
        return self.page.locator(
            "[data-testid='email-plain'], .plain-text, "
            "pre.email-body"
        )

    # Selectors - Attachments
    @property
    def attachments_section(self) -> Locator:
        """Attachments section container."""
        return self.page.locator(
            "[data-testid='attachments-section'], .attachments, "
            ".attachment-list, .files"
        )

    @property
    def attachment_items(self) -> Locator:
        """Individual attachment items."""
        return self.page.locator(
            "[data-testid='attachment-item'], .attachment-item, "
            ".attachment, .file-item"
        )

    @property
    def attachment_download_button(self) -> Locator:
        """Download attachment button."""
        return self.attachment_items.locator(
            "button:has-text('Download'), a[download], "
            "[data-testid='download-attachment']"
        )

    @property
    def download_all_button(self) -> Locator:
        """Download all attachments button."""
        return self.page.locator(
            "button:has-text('Download All'), "
            "[data-testid='download-all-attachments']"
        )

    # Selectors - Actions
    @property
    def reply_button(self) -> Locator:
        """Reply to email button."""
        return self.page.locator(
            "button:has-text('Reply'), button[aria-label='Reply'], "
            "[data-testid='reply-button'], .reply-btn"
        )

    @property
    def reply_all_button(self) -> Locator:
        """Reply all button."""
        return self.page.locator(
            "button:has-text('Reply All'), button[aria-label='Reply all'], "
            "[data-testid='reply-all-button'], .reply-all-btn"
        )

    @property
    def forward_button(self) -> Locator:
        """Forward email button."""
        return self.page.locator(
            "button:has-text('Forward'), button[aria-label='Forward'], "
            "[data-testid='forward-button'], .forward-btn"
        )

    @property
    def delete_button(self) -> Locator:
        """Delete email button."""
        return self.page.locator(
            "button:has-text('Delete'), button[aria-label='Delete'], "
            "[data-testid='delete-button'], .delete-btn"
        )

    @property
    def archive_button(self) -> Locator:
        """Archive email button."""
        return self.page.locator(
            "button:has-text('Archive'), button[aria-label='Archive'], "
            "[data-testid='archive-button'], .archive-btn"
        )

    @property
    def mark_unread_button(self) -> Locator:
        """Mark as unread button."""
        return self.page.locator(
            "button:has-text('Mark Unread'), button:has-text('Mark as unread'), "
            "[data-testid='mark-unread-button']"
        )

    @property
    def star_button(self) -> Locator:
        """Star/favorite email button."""
        return self.page.locator(
            "button[aria-label*='Star'], button[aria-label*='Favorite'], "
            "[data-testid='star-button'], .star-btn"
        )

    @property
    def spam_button(self) -> Locator:
        """Mark as spam button."""
        return self.page.locator(
            "button:has-text('Spam'), button:has-text('Junk'), "
            "[data-testid='spam-button'], .spam-btn"
        )

    @property
    def more_actions_button(self) -> Locator:
        """More actions dropdown button."""
        return self.page.locator(
            "button:has-text('More'), button[aria-label='More actions'], "
            "[data-testid='more-actions'], .more-btn"
        )

    @property
    def print_button(self) -> Locator:
        """Print email button."""
        return self.page.locator(
            "button:has-text('Print'), button[aria-label='Print'], "
            "[data-testid='print-button'], .print-btn"
        )

    @property
    def back_button(self) -> Locator:
        """Back to inbox button."""
        return self.page.locator(
            "button:has-text('Back'), button[aria-label='Back'], "
            "[data-testid='back-button'], .back-btn, a:has-text('Back')"
        )

    # Selectors - Navigation (for multi-email view)
    @property
    def next_email_button(self) -> Locator:
        """Next email button."""
        return self.page.locator(
            "button[aria-label='Next'], button:has-text('Next'), "
            "[data-testid='next-email'], .next-email"
        )

    @property
    def prev_email_button(self) -> Locator:
        """Previous email button."""
        return self.page.locator(
            "button[aria-label='Previous'], button:has-text('Prev'), "
            "[data-testid='prev-email'], .prev-email"
        )

    # Selectors - Email thread/conversation
    @property
    def thread_container(self) -> Locator:
        """Email thread/conversation container."""
        return self.page.locator(
            "[data-testid='email-thread'], .email-thread, "
            ".conversation, .thread"
        )

    @property
    def thread_messages(self) -> Locator:
        """Individual messages in thread."""
        return self.page.locator(
            "[data-testid='thread-message'], .thread-message, "
            ".conversation-item"
        )

    @property
    def expand_thread_button(self) -> Locator:
        """Expand thread/show all messages button."""
        return self.page.locator(
            "button:has-text('Expand'), button:has-text('Show all'), "
            "[data-testid='expand-thread']"
        )

    # Selectors - Security indicators
    @property
    def encrypted_badge(self) -> Locator:
        """Encrypted email indicator."""
        return self.page.locator(
            "[data-testid='encrypted-badge'], .encrypted, "
            ":has-text('Encrypted'), .security-badge"
        )

    @property
    def verified_sender_badge(self) -> Locator:
        """Verified sender indicator."""
        return self.page.locator(
            "[data-testid='verified-badge'], .verified, "
            ":has-text('Verified')"
        )

    # Actions
    async def goto(self, email_id: str) -> None:
        """Navigate to a specific email."""
        await self.navigate_to(f"{self.path}/{email_id}")
        await self.wait_for_page_load()

    async def go_back(self) -> None:
        """Go back to inbox."""
        await self.back_button.click()
        await self.wait_for_page_load()

    async def reply(self) -> None:
        """Click reply button."""
        await self.reply_button.click()

    async def reply_all(self) -> None:
        """Click reply all button."""
        await self.reply_all_button.click()

    async def forward(self) -> None:
        """Click forward button."""
        await self.forward_button.click()

    async def delete(self) -> None:
        """Delete the email."""
        await self.delete_button.click()

    async def delete_and_confirm(self) -> None:
        """Delete email and confirm if dialog appears."""
        await self.delete_button.click()
        # Check if confirmation dialog appears
        if await self.confirm_button.count() > 0:
            await self.confirm_button.click()
        await self.wait_for_loading_complete()

    async def archive(self) -> None:
        """Archive the email."""
        await self.archive_button.click()
        await self.wait_for_loading_complete()

    async def mark_unread(self) -> None:
        """Mark email as unread."""
        await self.mark_unread_button.click()

    async def star(self) -> None:
        """Star/favorite the email."""
        await self.star_button.click()

    async def unstar(self) -> None:
        """Remove star from email."""
        # Toggle star
        await self.star_button.click()

    async def mark_spam(self) -> None:
        """Mark email as spam."""
        await self.spam_button.click()
        await self.wait_for_loading_complete()

    async def open_more_actions(self) -> None:
        """Open more actions menu."""
        await self.more_actions_button.click()

    async def print_email(self) -> None:
        """Open print dialog."""
        await self.print_button.click()

    async def go_to_next_email(self) -> None:
        """Navigate to next email."""
        await self.next_email_button.click()
        await self.wait_for_page_load()

    async def go_to_prev_email(self) -> None:
        """Navigate to previous email."""
        await self.prev_email_button.click()
        await self.wait_for_page_load()

    async def download_attachment(self, index: int = 0) -> None:
        """Download an attachment by index."""
        download_btn = self.attachment_items.nth(index).locator(
            "button:has-text('Download'), a[download], "
            "[data-testid='download-attachment']"
        )
        await download_btn.click()

    async def download_all_attachments(self) -> None:
        """Download all attachments."""
        await self.download_all_button.click()

    async def expand_thread(self) -> None:
        """Expand email thread to show all messages."""
        if await self.expand_thread_button.count() > 0:
            await self.expand_thread_button.click()

    async def click_thread_message(self, index: int = 0) -> None:
        """Click on a specific message in the thread."""
        await self.thread_messages.nth(index).click()

    # Getters
    async def get_subject(self) -> str:
        """Get the email subject."""
        return await self.email_subject.text_content()

    async def get_sender(self) -> str:
        """Get the sender address."""
        return await self.email_sender.text_content()

    async def get_recipients(self) -> str:
        """Get the recipients."""
        return await self.email_recipients.text_content()

    async def get_date(self) -> str:
        """Get the email date."""
        return await self.email_date.text_content()

    async def get_body_text(self) -> str:
        """Get the email body text content."""
        return await self.email_body.text_content()

    async def get_attachment_count(self) -> int:
        """Get the number of attachments."""
        return await self.attachment_items.count()

    async def get_attachment_names(self) -> List[str]:
        """Get list of attachment filenames."""
        count = await self.attachment_items.count()
        names = []
        for i in range(count):
            name = await self.attachment_items.nth(i).text_content()
            names.append(name.strip())
        return names

    async def get_thread_message_count(self) -> int:
        """Get number of messages in thread."""
        return await self.thread_messages.count()

    async def is_starred(self) -> bool:
        """Check if email is starred."""
        star_btn = self.star_button
        class_attr = await star_btn.get_attribute("class") or ""
        aria_pressed = await star_btn.get_attribute("aria-pressed")
        data_starred = await star_btn.get_attribute("data-starred")
        return (
            "starred" in class_attr
            or "active" in class_attr
            or aria_pressed == "true"
            or data_starred == "true"
        )

    async def is_encrypted(self) -> bool:
        """Check if email is encrypted."""
        return await self.encrypted_badge.count() > 0

    # Assertions
    async def assert_email_visible(self) -> None:
        """Assert that email content is visible."""
        await expect(self.email_container).to_be_visible()

    async def assert_subject(self, subject: str) -> None:
        """Assert email subject."""
        await expect(self.email_subject).to_contain_text(subject)

    async def assert_sender(self, sender: str) -> None:
        """Assert email sender."""
        await expect(self.email_sender).to_contain_text(sender)

    async def assert_body_contains(self, text: str) -> None:
        """Assert email body contains text."""
        await expect(self.email_body).to_contain_text(text)

    async def assert_attachment_count(self, count: int) -> None:
        """Assert number of attachments."""
        await expect(self.attachment_items).to_have_count(count)

    async def assert_attachment_visible(self, filename: str) -> None:
        """Assert specific attachment is visible."""
        attachment = self.attachment_items.filter(has_text=filename)
        await expect(attachment.first).to_be_visible()

    async def assert_starred(self) -> None:
        """Assert email is starred."""
        assert await self.is_starred(), "Email should be starred"

    async def assert_not_starred(self) -> None:
        """Assert email is not starred."""
        assert not await self.is_starred(), "Email should not be starred"

    async def assert_encrypted(self) -> None:
        """Assert email is encrypted."""
        await expect(self.encrypted_badge).to_be_visible()

    async def assert_thread_message_count(self, count: int) -> None:
        """Assert number of messages in thread."""
        await expect(self.thread_messages).to_have_count(count)
