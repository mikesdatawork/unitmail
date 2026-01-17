"""
Compose Page Object for email composition tests.
"""

from typing import List, Optional
from playwright.async_api import Page, expect, Locator
from .base_page import BasePage


class ComposePage(BasePage):
    """Page Object for the email compose page/modal."""

    def __init__(self, page: Page, base_url: str = "http://localhost:8080"):
        super().__init__(page, base_url)
        self.path = "/compose"

    # Selectors - Compose Form
    @property
    def compose_form(self) -> Locator:
        """The compose email form/container."""
        return self.page.locator(
            "[data-testid='compose-form'], .compose-form, .compose-modal, "
            ".email-composer, form.compose"
        )

    @property
    def to_input(self) -> Locator:
        """To recipients input field."""
        return self.page.locator(
            "input[name='to'], input[placeholder*='To'], "
            "[data-testid='to-input'], .to-field input, #to"
        )

    @property
    def cc_input(self) -> Locator:
        """CC recipients input field."""
        return self.page.locator(
            "input[name='cc'], input[placeholder*='Cc'], input[placeholder*='CC'], "
            "[data-testid='cc-input'], .cc-field input, #cc"
        )

    @property
    def bcc_input(self) -> Locator:
        """BCC recipients input field."""
        return self.page.locator(
            "input[name='bcc'], input[placeholder*='Bcc'], input[placeholder*='BCC'], "
            "[data-testid='bcc-input'], .bcc-field input, #bcc"
        )

    @property
    def subject_input(self) -> Locator:
        """Subject input field."""
        return self.page.locator(
            "input[name='subject'], input[placeholder*='Subject'], "
            "[data-testid='subject-input'], .subject-field input, #subject"
        )

    @property
    def body_editor(self) -> Locator:
        """Email body editor (textarea or rich text)."""
        return self.page.locator(
            "textarea[name='body'], textarea[placeholder*='message' i], "
            "[data-testid='body-editor'], .body-editor, .email-body, "
            "[contenteditable='true'], .ql-editor, .ProseMirror, #body"
        )

    @property
    def show_cc_button(self) -> Locator:
        """Button to show CC field."""
        return self.page.locator(
            "button:has-text('CC'), button:has-text('Cc'), "
            "[data-testid='show-cc'], .show-cc"
        )

    @property
    def show_bcc_button(self) -> Locator:
        """Button to show BCC field."""
        return self.page.locator(
            "button:has-text('BCC'), button:has-text('Bcc'), "
            "[data-testid='show-bcc'], .show-bcc"
        )

    # Selectors - Recipients chips/tags
    @property
    def recipient_chips(self) -> Locator:
        """Recipient chips/tags."""
        return self.page.locator(
            "[data-testid='recipient-chip'], .recipient-chip, .recipient-tag, "
            ".email-chip, .tag"
        )

    @property
    def to_recipient_chips(self) -> Locator:
        """To field recipient chips."""
        return self.page.locator(
            ".to-field [data-testid='recipient-chip'], "
            ".to-field .recipient-chip, [data-testid='to-chips'] .chip"
        )

    @property
    def cc_recipient_chips(self) -> Locator:
        """CC field recipient chips."""
        return self.page.locator(
            ".cc-field [data-testid='recipient-chip'], "
            ".cc-field .recipient-chip, [data-testid='cc-chips'] .chip"
        )

    @property
    def bcc_recipient_chips(self) -> Locator:
        """BCC field recipient chips."""
        return self.page.locator(
            ".bcc-field [data-testid='recipient-chip'], "
            ".bcc-field .recipient-chip, [data-testid='bcc-chips'] .chip"
        )

    # Selectors - Attachments
    @property
    def attachment_input(self) -> Locator:
        """Hidden file input for attachments."""
        return self.page.locator(
            "input[type='file'], [data-testid='attachment-input']"
        )

    @property
    def attach_button(self) -> Locator:
        """Attach file button."""
        return self.page.locator(
            "button:has-text('Attach'), button[aria-label*='attach' i], "
            "[data-testid='attach-button'], .attach-btn"
        )

    @property
    def attachment_list(self) -> Locator:
        """List of attached files."""
        return self.page.locator(
            "[data-testid='attachment-list'], .attachment-list, "
            ".attachments, .file-list"
        )

    @property
    def attachment_items(self) -> Locator:
        """Individual attachment items."""
        return self.page.locator(
            "[data-testid='attachment-item'], .attachment-item, "
            ".attachment, .file-item"
        )

    @property
    def remove_attachment_button(self) -> Locator:
        """Remove attachment button."""
        return self.attachment_items.locator(
            "button:has-text('Remove'), button[aria-label*='remove' i], "
            "[data-testid='remove-attachment'], .remove-btn"
        )

    # Selectors - Action Buttons
    @property
    def send_button(self) -> Locator:
        """Send email button."""
        return self.page.locator(
            "button:has-text('Send'), button[type='submit'], "
            "[data-testid='send-button'], .send-btn"
        )

    @property
    def save_draft_button(self) -> Locator:
        """Save as draft button."""
        return self.page.locator(
            "button:has-text('Save Draft'), button:has-text('Draft'), "
            "[data-testid='save-draft-button'], .draft-btn"
        )

    @property
    def discard_button(self) -> Locator:
        """Discard email button."""
        return self.page.locator(
            "button:has-text('Discard'), button:has-text('Cancel'), "
            "[data-testid='discard-button'], .discard-btn"
        )

    @property
    def close_button(self) -> Locator:
        """Close compose window button."""
        return self.page.locator(
            "button[aria-label='Close'], [data-testid='close-compose'], "
            ".close-btn, .compose-close"
        )

    # Selectors - Formatting toolbar
    @property
    def formatting_toolbar(self) -> Locator:
        """Rich text formatting toolbar."""
        return self.page.locator(
            "[data-testid='formatting-toolbar'], .formatting-toolbar, "
            ".editor-toolbar, .ql-toolbar"
        )

    @property
    def bold_button(self) -> Locator:
        """Bold formatting button."""
        return self.formatting_toolbar.locator(
            "button[aria-label*='bold' i], button:has-text('B'), .ql-bold"
        )

    @property
    def italic_button(self) -> Locator:
        """Italic formatting button."""
        return self.formatting_toolbar.locator(
            "button[aria-label*='italic' i], button:has-text('I'), .ql-italic"
        )

    @property
    def underline_button(self) -> Locator:
        """Underline formatting button."""
        return self.formatting_toolbar.locator(
            "button[aria-label*='underline' i], button:has-text('U'), .ql-underline"
        )

    # Selectors - Validation
    @property
    def validation_errors(self) -> Locator:
        """Validation error messages."""
        return self.page.locator(
            ".validation-error, .field-error, .error-message, "
            "[data-testid='validation-error'], .invalid-feedback"
        )

    @property
    def send_success_message(self) -> Locator:
        """Email sent success message."""
        return self.page.locator(
            ":has-text('sent successfully'), :has-text('Email sent'), "
            "[data-testid='send-success']"
        )

    @property
    def draft_saved_message(self) -> Locator:
        """Draft saved message."""
        return self.page.locator(
            ":has-text('Draft saved'), :has-text('Saved'), "
            "[data-testid='draft-saved']"
        )

    # Actions
    async def goto(self) -> None:
        """Navigate to the compose page."""
        await self.navigate_to(self.path)
        await self.wait_for_page_load()

    async def add_recipient_to(self, email: str) -> None:
        """Add a recipient to the To field."""
        await self.fill_input(self.to_input, email, clear_first=False)
        await self.page.keyboard.press("Enter")

    async def add_recipients_to(self, emails: List[str]) -> None:
        """Add multiple recipients to the To field."""
        for email in emails:
            await self.add_recipient_to(email)

    async def add_recipient_cc(self, email: str) -> None:
        """Add a recipient to the CC field."""
        # Show CC field if hidden
        if not await self.cc_input.is_visible():
            await self.show_cc_button.click()
        await self.fill_input(self.cc_input, email, clear_first=False)
        await self.page.keyboard.press("Enter")

    async def add_recipients_cc(self, emails: List[str]) -> None:
        """Add multiple recipients to the CC field."""
        for email in emails:
            await self.add_recipient_cc(email)

    async def add_recipient_bcc(self, email: str) -> None:
        """Add a recipient to the BCC field."""
        # Show BCC field if hidden
        if not await self.bcc_input.is_visible():
            await self.show_bcc_button.click()
        await self.fill_input(self.bcc_input, email, clear_first=False)
        await self.page.keyboard.press("Enter")

    async def add_recipients_bcc(self, emails: List[str]) -> None:
        """Add multiple recipients to the BCC field."""
        for email in emails:
            await self.add_recipient_bcc(email)

    async def set_subject(self, subject: str) -> None:
        """Set the email subject."""
        await self.fill_input(self.subject_input, subject)

    async def set_body(self, body: str) -> None:
        """Set the email body content."""
        await self.body_editor.click()
        await self.body_editor.fill(body)

    async def type_body(self, body: str) -> None:
        """Type in the email body (for rich text editors)."""
        await self.body_editor.click()
        await self.page.keyboard.type(body)

    async def attach_file(self, file_path: str) -> None:
        """Attach a file to the email."""
        await self.attachment_input.set_input_files(file_path)

    async def attach_files(self, file_paths: List[str]) -> None:
        """Attach multiple files to the email."""
        await self.attachment_input.set_input_files(file_paths)

    async def remove_attachment(self, index: int = 0) -> None:
        """Remove an attachment by index."""
        remove_btns = self.attachment_items.nth(index).locator(
            "button:has-text('Remove'), button[aria-label*='remove' i], "
            "[data-testid='remove-attachment'], .remove-btn"
        )
        await remove_btns.click()

    async def compose_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
    ) -> None:
        """
        Compose a complete email.

        Args:
            to: List of To recipients
            subject: Email subject
            body: Email body content
            cc: Optional list of CC recipients
            bcc: Optional list of BCC recipients
            attachments: Optional list of file paths to attach
        """
        await self.add_recipients_to(to)

        if cc:
            await self.add_recipients_cc(cc)

        if bcc:
            await self.add_recipients_bcc(bcc)

        await self.set_subject(subject)
        await self.set_body(body)

        if attachments:
            await self.attach_files(attachments)

    async def send_email(self) -> None:
        """Click the send button."""
        await self.send_button.click()

    async def send_and_wait(self) -> None:
        """Send email and wait for success."""
        await self.send_button.click()
        await self.wait_for_loading_complete()

    async def save_draft(self) -> None:
        """Save the email as draft."""
        await self.save_draft_button.click()

    async def save_draft_and_wait(self) -> None:
        """Save draft and wait for confirmation."""
        await self.save_draft_button.click()
        await self.wait_for_loading_complete()

    async def discard(self) -> None:
        """Discard the composed email."""
        await self.discard_button.click()

    async def close(self) -> None:
        """Close the compose window."""
        await self.close_button.click()

    async def apply_bold(self) -> None:
        """Apply bold formatting to selected text."""
        await self.bold_button.click()

    async def apply_italic(self) -> None:
        """Apply italic formatting to selected text."""
        await self.italic_button.click()

    async def apply_underline(self) -> None:
        """Apply underline formatting to selected text."""
        await self.underline_button.click()

    async def get_attachment_count(self) -> int:
        """Get the number of attached files."""
        return await self.attachment_items.count()

    async def get_to_recipient_count(self) -> int:
        """Get the number of To recipients."""
        return await self.to_recipient_chips.count()

    async def get_cc_recipient_count(self) -> int:
        """Get the number of CC recipients."""
        return await self.cc_recipient_chips.count()

    async def get_bcc_recipient_count(self) -> int:
        """Get the number of BCC recipients."""
        return await self.bcc_recipient_chips.count()

    # Assertions
    async def assert_compose_form_visible(self) -> None:
        """Assert that the compose form is visible."""
        await expect(self.compose_form).to_be_visible()

    async def assert_compose_form_hidden(self) -> None:
        """Assert that the compose form is hidden."""
        await expect(self.compose_form).to_be_hidden()

    async def assert_recipient_added(self, email: str) -> None:
        """Assert that a recipient was added."""
        chip = self.recipient_chips.filter(has_text=email)
        await expect(chip.first).to_be_visible()

    async def assert_subject(self, subject: str) -> None:
        """Assert that subject field has specific value."""
        await expect(self.subject_input).to_have_value(subject)

    async def assert_attachment_count(self, count: int) -> None:
        """Assert specific number of attachments."""
        await expect(self.attachment_items).to_have_count(count)

    async def assert_attachment_added(self, filename: str) -> None:
        """Assert that a specific attachment was added."""
        attachment = self.attachment_items.filter(has_text=filename)
        await expect(attachment.first).to_be_visible()

    async def assert_validation_error(
            self, error_text: Optional[str] = None) -> None:
        """Assert that validation error is shown."""
        await expect(self.validation_errors.first).to_be_visible()
        if error_text:
            await expect(self.validation_errors).to_contain_text(error_text)

    async def assert_email_sent(self) -> None:
        """Assert that email was sent successfully."""
        await expect(self.send_success_message).to_be_visible()

    async def assert_draft_saved(self) -> None:
        """Assert that draft was saved."""
        await expect(self.draft_saved_message).to_be_visible()
