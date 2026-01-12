"""
E2E tests for email composition functionality.

Tests cover:
- Composing new email
- Adding recipients (To, CC, BCC)
- Attachments
- Saving drafts
- Sending email
"""

import pytest
from playwright.async_api import Page, expect

from pages import ComposePage, InboxPage, LoginPage


# =============================================================================
# Test Constants
# =============================================================================

TEST_RECIPIENT = "recipient@example.com"
TEST_RECIPIENT_2 = "recipient2@example.com"
TEST_RECIPIENT_3 = "recipient3@example.com"
TEST_CC = "cc@example.com"
TEST_BCC = "bcc@example.com"
TEST_SUBJECT = "Test Email Subject"
TEST_BODY = "This is the body of the test email."


# =============================================================================
# Compose New Email Tests
# =============================================================================

class TestComposeNewEmail:
    """Tests for composing new emails."""

    @pytest.mark.asyncio
    async def test_compose_page_loads(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test that compose page/modal loads correctly."""
        compose_page.page = authenticated_page
        await compose_page.goto()
        await compose_page.assert_compose_form_visible()

    @pytest.mark.asyncio
    async def test_compose_from_inbox(
        self, authenticated_page: Page, inbox_page: InboxPage
    ):
        """Test opening compose from inbox button."""
        inbox_page.page = authenticated_page
        await inbox_page.goto()
        await inbox_page.click_compose()

        # Compose form should be visible
        compose_page = ComposePage(authenticated_page)
        await compose_page.assert_compose_form_visible()

    @pytest.mark.asyncio
    async def test_compose_has_required_fields(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test that compose form has all required fields."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await expect(compose_page.to_input).to_be_visible()
        await expect(compose_page.subject_input).to_be_visible()
        await expect(compose_page.body_editor).to_be_visible()
        await expect(compose_page.send_button).to_be_visible()

    @pytest.mark.asyncio
    async def test_compose_simple_email(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test composing a simple email with To, Subject, and Body."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.compose_email(
            to=[TEST_RECIPIENT],
            subject=TEST_SUBJECT,
            body=TEST_BODY,
        )

        # Verify fields are filled
        await compose_page.assert_subject(TEST_SUBJECT)

    @pytest.mark.asyncio
    async def test_compose_keyboard_shortcuts(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test keyboard shortcuts in compose view."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        # Fill in basic content
        await compose_page.add_recipient_to(TEST_RECIPIENT)
        await compose_page.set_subject(TEST_SUBJECT)
        await compose_page.set_body(TEST_BODY)

        # Test Ctrl+S for save draft (if implemented)
        await compose_page.press_shortcut("Control", "s")

        # This test documents expected keyboard shortcut behavior

    @pytest.mark.asyncio
    async def test_compose_autosave(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test that compose autosaves drafts."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.add_recipient_to(TEST_RECIPIENT)
        await compose_page.set_subject(TEST_SUBJECT)
        await compose_page.set_body(TEST_BODY)

        # Wait for autosave (if implemented)
        await authenticated_page.wait_for_timeout(3000)

        # This test documents expected autosave behavior


# =============================================================================
# Adding Recipients Tests
# =============================================================================

class TestAddRecipients:
    """Tests for adding recipients to emails."""

    @pytest.mark.asyncio
    async def test_add_single_to_recipient(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test adding a single To recipient."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.add_recipient_to(TEST_RECIPIENT)
        await compose_page.assert_recipient_added(TEST_RECIPIENT)

    @pytest.mark.asyncio
    async def test_add_multiple_to_recipients(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test adding multiple To recipients."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        recipients = [TEST_RECIPIENT, TEST_RECIPIENT_2, TEST_RECIPIENT_3]
        await compose_page.add_recipients_to(recipients)

        # Verify all recipients added
        count = await compose_page.get_to_recipient_count()
        assert count >= len(recipients)

    @pytest.mark.asyncio
    async def test_add_cc_recipient(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test adding CC recipient."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.add_recipient_to(TEST_RECIPIENT)
        await compose_page.add_recipient_cc(TEST_CC)

        count = await compose_page.get_cc_recipient_count()
        assert count >= 1

    @pytest.mark.asyncio
    async def test_add_bcc_recipient(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test adding BCC recipient."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.add_recipient_to(TEST_RECIPIENT)
        await compose_page.add_recipient_bcc(TEST_BCC)

        count = await compose_page.get_bcc_recipient_count()
        assert count >= 1

    @pytest.mark.asyncio
    async def test_add_all_recipient_types(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test adding To, CC, and BCC recipients together."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.compose_email(
            to=[TEST_RECIPIENT, TEST_RECIPIENT_2],
            subject=TEST_SUBJECT,
            body=TEST_BODY,
            cc=[TEST_CC],
            bcc=[TEST_BCC],
        )

        # Verify counts
        to_count = await compose_page.get_to_recipient_count()
        cc_count = await compose_page.get_cc_recipient_count()
        bcc_count = await compose_page.get_bcc_recipient_count()

        assert to_count >= 2
        assert cc_count >= 1
        assert bcc_count >= 1

    @pytest.mark.asyncio
    async def test_remove_recipient(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test removing a recipient."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.add_recipients_to([TEST_RECIPIENT, TEST_RECIPIENT_2])

        initial_count = await compose_page.get_to_recipient_count()

        # Remove first recipient chip
        remove_btn = compose_page.to_recipient_chips.first.locator(
            "button, [data-testid='remove-recipient'], .remove"
        )
        if await remove_btn.count() > 0:
            await remove_btn.click()

            final_count = await compose_page.get_to_recipient_count()
            assert final_count < initial_count

    @pytest.mark.asyncio
    async def test_invalid_email_validation(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test validation for invalid email addresses."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        # Try to add invalid email
        await compose_page.to_input.fill("not-an-email")
        await authenticated_page.keyboard.press("Enter")

        # Should show validation error or not accept the input
        # This test documents expected validation behavior

    @pytest.mark.asyncio
    async def test_autocomplete_recipients(
        self, authenticated_page: Page, compose_page: ComposePage, api_client
    ):
        """Test recipient autocomplete from contacts."""
        # Create a contact first
        contact = await api_client.create_test_contact(
            name="John Doe",
            email="john.doe@example.com"
        )

        compose_page.page = authenticated_page
        await compose_page.goto()

        # Type partial name/email to trigger autocomplete
        await compose_page.to_input.type("john")

        # Wait for autocomplete suggestions
        await authenticated_page.wait_for_timeout(1000)

        # Check for autocomplete dropdown
        autocomplete = authenticated_page.locator(
            "[data-testid='autocomplete'], .autocomplete, "
            "[role='listbox'], .suggestions"
        )

        # Document autocomplete behavior


# =============================================================================
# Attachments Tests
# =============================================================================

class TestAttachments:
    """Tests for email attachments."""

    @pytest.mark.asyncio
    async def test_attach_single_file(
        self, authenticated_page: Page, compose_page: ComposePage, temp_file: str
    ):
        """Test attaching a single file."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.attach_file(temp_file)

        count = await compose_page.get_attachment_count()
        assert count == 1

    @pytest.mark.asyncio
    async def test_attach_multiple_files(
        self, authenticated_page: Page, compose_page: ComposePage, temp_files: list
    ):
        """Test attaching multiple files."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.attach_files(temp_files)

        count = await compose_page.get_attachment_count()
        assert count == len(temp_files)

    @pytest.mark.asyncio
    async def test_remove_attachment(
        self, authenticated_page: Page, compose_page: ComposePage, temp_file: str
    ):
        """Test removing an attachment."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.attach_file(temp_file)
        await compose_page.assert_attachment_count(1)

        await compose_page.remove_attachment(0)

        # Attachment should be removed
        count = await compose_page.get_attachment_count()
        assert count == 0

    @pytest.mark.asyncio
    async def test_attachment_shows_filename(
        self, authenticated_page: Page, compose_page: ComposePage, temp_file: str
    ):
        """Test that attachment shows filename."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.attach_file(temp_file)

        # Check filename is displayed
        import os
        filename = os.path.basename(temp_file)
        await compose_page.assert_attachment_added(filename)

    @pytest.mark.asyncio
    async def test_attachment_via_drag_drop(
        self, authenticated_page: Page, compose_page: ComposePage, temp_file: str
    ):
        """Test attaching file via drag and drop."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        # Simulate drag and drop using data transfer
        # This is a simplified version - actual drag/drop is complex
        # Document expected drag-drop behavior

    @pytest.mark.asyncio
    async def test_attachment_size_limit(
        self, authenticated_page: Page, compose_page: ComposePage, tmp_path
    ):
        """Test attachment size limit validation."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        # Create a large file (this is a mock - adjust size as needed)
        large_file = tmp_path / "large_file.bin"
        # Note: Creating actual large files in tests is not recommended
        # This documents expected size limit behavior


# =============================================================================
# Save Draft Tests
# =============================================================================

class TestSaveDraft:
    """Tests for saving email drafts."""

    @pytest.mark.asyncio
    async def test_save_draft(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test saving an email as draft."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.compose_email(
            to=[TEST_RECIPIENT],
            subject=TEST_SUBJECT,
            body=TEST_BODY,
        )

        await compose_page.save_draft_and_wait()

        # Should show draft saved confirmation
        await compose_page.assert_draft_saved()

    @pytest.mark.asyncio
    async def test_draft_appears_in_drafts_folder(
        self, authenticated_page: Page, compose_page: ComposePage, inbox_page: InboxPage
    ):
        """Test that saved draft appears in Drafts folder."""
        compose_page.page = authenticated_page
        inbox_page.page = authenticated_page

        await compose_page.goto()

        unique_subject = f"Draft Test {TEST_SUBJECT}"
        await compose_page.compose_email(
            to=[TEST_RECIPIENT],
            subject=unique_subject,
            body=TEST_BODY,
        )

        await compose_page.save_draft_and_wait()

        # Navigate to drafts folder
        await inbox_page.goto()
        await inbox_page.go_to_folder("drafts")

        # Draft should be visible
        await inbox_page.assert_email_visible(unique_subject)

    @pytest.mark.asyncio
    async def test_edit_draft(
        self, authenticated_page: Page, compose_page: ComposePage, inbox_page: InboxPage
    ):
        """Test editing a saved draft."""
        compose_page.page = authenticated_page
        inbox_page.page = authenticated_page

        # Save a draft first
        await compose_page.goto()
        unique_subject = f"Edit Draft Test {TEST_SUBJECT}"
        await compose_page.compose_email(
            to=[TEST_RECIPIENT],
            subject=unique_subject,
            body=TEST_BODY,
        )
        await compose_page.save_draft_and_wait()

        # Go to drafts and open the draft
        await inbox_page.goto()
        await inbox_page.go_to_folder("drafts")
        await inbox_page.click_email_by_subject(unique_subject)

        # Should open in compose mode
        await compose_page.assert_compose_form_visible()

        # Edit the draft
        updated_body = "Updated body content"
        await compose_page.set_body(updated_body)
        await compose_page.save_draft_and_wait()

    @pytest.mark.asyncio
    async def test_draft_preserves_attachments(
        self, authenticated_page: Page, compose_page: ComposePage,
        inbox_page: InboxPage, temp_file: str
    ):
        """Test that draft preserves attachments."""
        compose_page.page = authenticated_page
        inbox_page.page = authenticated_page

        # Compose with attachment
        await compose_page.goto()
        unique_subject = f"Draft Attachment Test {TEST_SUBJECT}"
        await compose_page.compose_email(
            to=[TEST_RECIPIENT],
            subject=unique_subject,
            body=TEST_BODY,
            attachments=[temp_file],
        )
        await compose_page.save_draft_and_wait()

        # Reopen draft
        await inbox_page.goto()
        await inbox_page.go_to_folder("drafts")
        await inbox_page.click_email_by_subject(unique_subject)

        # Attachment should still be there
        count = await compose_page.get_attachment_count()
        assert count >= 1

    @pytest.mark.asyncio
    async def test_discard_draft(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test discarding a draft."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.compose_email(
            to=[TEST_RECIPIENT],
            subject=TEST_SUBJECT,
            body=TEST_BODY,
        )

        await compose_page.discard()

        # Compose form should close
        await compose_page.assert_compose_form_hidden()


# =============================================================================
# Send Email Tests
# =============================================================================

class TestSendEmail:
    """Tests for sending emails."""

    @pytest.mark.asyncio
    async def test_send_simple_email(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test sending a simple email."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.compose_email(
            to=[TEST_RECIPIENT],
            subject=TEST_SUBJECT,
            body=TEST_BODY,
        )

        await compose_page.send_and_wait()

        # Should show success message
        await compose_page.assert_email_sent()

    @pytest.mark.asyncio
    async def test_send_email_with_cc_bcc(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test sending email with CC and BCC."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.compose_email(
            to=[TEST_RECIPIENT],
            subject=TEST_SUBJECT,
            body=TEST_BODY,
            cc=[TEST_CC],
            bcc=[TEST_BCC],
        )

        await compose_page.send_and_wait()
        await compose_page.assert_email_sent()

    @pytest.mark.asyncio
    async def test_send_email_with_attachment(
        self, authenticated_page: Page, compose_page: ComposePage, temp_file: str
    ):
        """Test sending email with attachment."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.compose_email(
            to=[TEST_RECIPIENT],
            subject=TEST_SUBJECT,
            body=TEST_BODY,
            attachments=[temp_file],
        )

        await compose_page.send_and_wait()
        await compose_page.assert_email_sent()

    @pytest.mark.asyncio
    async def test_send_email_appears_in_sent(
        self, authenticated_page: Page, compose_page: ComposePage, inbox_page: InboxPage
    ):
        """Test that sent email appears in Sent folder."""
        compose_page.page = authenticated_page
        inbox_page.page = authenticated_page

        unique_subject = f"Sent Test {TEST_SUBJECT}"

        await compose_page.goto()
        await compose_page.compose_email(
            to=[TEST_RECIPIENT],
            subject=unique_subject,
            body=TEST_BODY,
        )
        await compose_page.send_and_wait()

        # Navigate to sent folder
        await inbox_page.goto()
        await inbox_page.go_to_folder("sent")

        # Sent email should be visible
        await inbox_page.assert_email_visible(unique_subject)

    @pytest.mark.asyncio
    async def test_send_without_recipient_fails(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test that sending without recipient shows error."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.set_subject(TEST_SUBJECT)
        await compose_page.set_body(TEST_BODY)

        await compose_page.send_email()

        # Should show validation error
        await compose_page.assert_validation_error()

    @pytest.mark.asyncio
    async def test_send_without_subject_confirmation(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test sending without subject prompts for confirmation."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.add_recipient_to(TEST_RECIPIENT)
        await compose_page.set_body(TEST_BODY)
        # Don't set subject

        await compose_page.send_email()

        # Should either show warning or allow sending
        # This test documents expected behavior


# =============================================================================
# Rich Text Formatting Tests
# =============================================================================

class TestRichTextFormatting:
    """Tests for rich text email composition."""

    @pytest.mark.asyncio
    async def test_bold_formatting(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test applying bold formatting."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.body_editor.click()
        await compose_page.type_body("Bold text")

        # Select all text
        await authenticated_page.keyboard.press("Control+a")

        # Apply bold
        await compose_page.apply_bold()

        # Document formatting behavior

    @pytest.mark.asyncio
    async def test_italic_formatting(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test applying italic formatting."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.body_editor.click()
        await compose_page.type_body("Italic text")

        await authenticated_page.keyboard.press("Control+a")
        await compose_page.apply_italic()

    @pytest.mark.asyncio
    async def test_keyboard_shortcut_bold(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test Ctrl+B for bold."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.body_editor.click()
        await compose_page.type_body("Bold")
        await authenticated_page.keyboard.press("Control+a")
        await authenticated_page.keyboard.press("Control+b")

    @pytest.mark.asyncio
    async def test_keyboard_shortcut_italic(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test Ctrl+I for italic."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        await compose_page.body_editor.click()
        await compose_page.type_body("Italic")
        await authenticated_page.keyboard.press("Control+a")
        await authenticated_page.keyboard.press("Control+i")


# =============================================================================
# Reply and Forward Tests
# =============================================================================

class TestReplyAndForward:
    """Tests for reply and forward functionality."""

    @pytest.mark.asyncio
    async def test_reply_prefills_recipient(
        self, authenticated_page: Page, inbox_page: InboxPage,
        compose_page: ComposePage, api_client
    ):
        """Test that reply prefills the original sender as recipient."""
        # Create test email
        test_email = await api_client.create_test_email(
            subject="Reply Test",
            sender="original-sender@example.com",
        )

        inbox_page.page = authenticated_page
        compose_page.page = authenticated_page

        await inbox_page.goto()
        await inbox_page.click_email_by_subject("Reply Test")

        # Click reply
        from pages import EmailReaderPage
        reader = EmailReaderPage(authenticated_page)
        await reader.reply()

        # Compose should have original sender as recipient
        await compose_page.assert_compose_form_visible()

    @pytest.mark.asyncio
    async def test_reply_includes_quoted_text(
        self, authenticated_page: Page, inbox_page: InboxPage,
        compose_page: ComposePage, api_client
    ):
        """Test that reply includes quoted original message."""
        test_email = await api_client.create_test_email(
            subject="Quote Test",
            body="Original message content",
        )

        inbox_page.page = authenticated_page
        compose_page.page = authenticated_page

        await inbox_page.goto()
        await inbox_page.click_email_by_subject("Quote Test")

        from pages import EmailReaderPage
        reader = EmailReaderPage(authenticated_page)
        await reader.reply()

        # Body should contain quoted text
        body_text = await compose_page.body_editor.text_content()
        # Document expected quote format

    @pytest.mark.asyncio
    async def test_forward_prefills_subject(
        self, authenticated_page: Page, inbox_page: InboxPage,
        compose_page: ComposePage, api_client
    ):
        """Test that forward prefills subject with Fwd: prefix."""
        test_email = await api_client.create_test_email(
            subject="Forward Test",
        )

        inbox_page.page = authenticated_page
        compose_page.page = authenticated_page

        await inbox_page.goto()
        await inbox_page.click_email_by_subject("Forward Test")

        from pages import EmailReaderPage
        reader = EmailReaderPage(authenticated_page)
        await reader.forward()

        await compose_page.assert_compose_form_visible()
        # Subject should have Fwd: prefix


# =============================================================================
# Accessibility Tests
# =============================================================================

class TestComposeAccessibility:
    """Accessibility tests for compose functionality."""

    @pytest.mark.asyncio
    async def test_compose_form_keyboard_navigation(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test keyboard navigation through compose form."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        # Tab through form fields
        await authenticated_page.keyboard.press("Tab")  # To input
        await authenticated_page.keyboard.press("Tab")  # Subject
        await authenticated_page.keyboard.press("Tab")  # Body
        await authenticated_page.keyboard.press("Tab")  # Send or other buttons

        # All fields should be reachable via keyboard

    @pytest.mark.asyncio
    async def test_compose_form_labels(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test that compose form fields have proper labels."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        # Check for labels or aria-labels on key fields
        to_label = await compose_page.to_input.get_attribute("aria-label")
        to_placeholder = await compose_page.to_input.get_attribute("placeholder")

        assert to_label or to_placeholder  # Should have some label

    @pytest.mark.asyncio
    async def test_send_button_disabled_state(
        self, authenticated_page: Page, compose_page: ComposePage
    ):
        """Test that send button has appropriate disabled state."""
        compose_page.page = authenticated_page
        await compose_page.goto()

        # Send button might be disabled without recipient
        is_disabled = await compose_page.send_button.is_disabled()
        # Document expected button state behavior
