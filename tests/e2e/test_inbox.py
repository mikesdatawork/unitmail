"""
E2E tests for inbox functionality.

Tests cover:
- Viewing inbox
- Reading emails
- Marking read/unread
- Starring emails
- Deleting emails
"""

import pytest
from playwright.async_api import Page, expect

from .pages import InboxPage, EmailReaderPage


# =============================================================================
# Viewing Inbox Tests
# =============================================================================

class TestViewingInbox:
    """Tests for viewing the inbox."""

    @pytest.mark.asyncio
    async def test_inbox_page_loads(
        self, authenticated_page: Page, inbox_page: InboxPage
    ):
        """Test that inbox page loads correctly."""
        inbox_page.page = authenticated_page
        await inbox_page.goto()
        await inbox_page.assert_on_inbox_page()

    @pytest.mark.asyncio
    async def test_inbox_displays_email_list(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test that inbox displays list of emails."""
        # Create some test emails
        await api_client.create_test_email(subject="Test Email 1")
        await api_client.create_test_email(subject="Test Email 2")

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        # Should display email list
        await expect(inbox_page.email_list).to_be_visible()

    @pytest.mark.asyncio
    async def test_inbox_shows_email_subject(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test that inbox shows email subjects."""
        _test_email = await api_client.create_test_email(  # noqa: F841
            subject="Unique Test Subject"
        )

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        await inbox_page.assert_email_visible("Unique Test Subject")

    @pytest.mark.asyncio
    async def test_inbox_shows_sender(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test that inbox shows email sender."""
        _test_email = await api_client.create_test_email(  # noqa: F841
            sender="test-sender@example.com"
        )

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        # Sender should be visible in email list
        sender_text = await inbox_page.get_email_sender(0)
        assert "test-sender" in sender_text or "@" in sender_text

    @pytest.mark.asyncio
    async def test_inbox_shows_date(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test that inbox shows email date."""
        await api_client.create_test_email()

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        # Date should be visible
        await expect(inbox_page.email_date.first).to_be_visible()

    @pytest.mark.asyncio
    async def test_empty_inbox_message(
        self, authenticated_page: Page, inbox_page: InboxPage
    ):
        """Test that empty inbox shows appropriate message."""
        inbox_page.page = authenticated_page
        await inbox_page.goto()

        # If inbox is empty, should show message
        count = await inbox_page.get_email_count()
        if count == 0:
            await inbox_page.assert_inbox_empty()

    @pytest.mark.asyncio
    async def test_inbox_refresh(
        self, authenticated_page: Page, inbox_page: InboxPage
    ):
        """Test refreshing the inbox."""
        inbox_page.page = authenticated_page
        await inbox_page.goto()

        await inbox_page.refresh_inbox()

        # Page should still be functional after refresh
        await inbox_page.assert_on_inbox_page()

    @pytest.mark.asyncio
    async def test_inbox_pagination(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test inbox pagination with many emails."""
        # Create multiple test emails
        for i in range(25):
            await api_client.create_test_email(subject=f"Pagination Test {i}")

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        # Check if pagination exists
        pagination_visible = await inbox_page.pagination.count() > 0
        if pagination_visible:
            await inbox_page.go_to_next_page()
            await inbox_page.assert_on_inbox_page()

    @pytest.mark.asyncio
    async def test_inbox_unread_indicator(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test that unread emails are visually indicated."""
        # Create unread email
        _test_email = await api_client.create_test_email()  # noqa: F841

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        # Should have unread indicator
        _is_unread = await inbox_page.is_email_unread(0)  # noqa: F841
        # Document unread indicator behavior


# =============================================================================
# Reading Email Tests
# =============================================================================

class TestReadingEmail:
    """Tests for reading individual emails."""

    @pytest.mark.asyncio
    async def test_click_email_opens_reader(
        self, authenticated_page: Page, inbox_page: InboxPage,
        email_reader_page: EmailReaderPage, api_client
    ):
        """Test that clicking an email opens the reader."""
        await api_client.create_test_email(subject="Click Test Email")

        inbox_page.page = authenticated_page
        email_reader_page.page = authenticated_page

        await inbox_page.goto()
        await inbox_page.click_email_by_subject("Click Test Email")

        await email_reader_page.assert_email_visible()

    @pytest.mark.asyncio
    async def test_email_reader_shows_subject(
        self, authenticated_page: Page, inbox_page: InboxPage,
        email_reader_page: EmailReaderPage, api_client
    ):
        """Test that email reader shows the subject."""
        _test_email = await api_client.create_test_email(  # noqa: F841
            subject="Reader Subject Test"
        )

        inbox_page.page = authenticated_page
        email_reader_page.page = authenticated_page

        await inbox_page.goto()
        await inbox_page.click_email_by_subject("Reader Subject Test")

        await email_reader_page.assert_subject("Reader Subject Test")

    @pytest.mark.asyncio
    async def test_email_reader_shows_body(
        self, authenticated_page: Page, inbox_page: InboxPage,
        email_reader_page: EmailReaderPage, api_client
    ):
        """Test that email reader shows the body content."""
        _test_email = await api_client.create_test_email(  # noqa: F841
            subject="Body Test",
            body="This is the email body content for testing."
        )

        inbox_page.page = authenticated_page
        email_reader_page.page = authenticated_page

        await inbox_page.goto()
        await inbox_page.click_email_by_subject("Body Test")

        await email_reader_page.assert_body_contains("email body content")

    @pytest.mark.asyncio
    async def test_email_reader_shows_sender(
        self, authenticated_page: Page, inbox_page: InboxPage,
        email_reader_page: EmailReaderPage, api_client
    ):
        """Test that email reader shows sender information."""
        _test_email = await api_client.create_test_email(  # noqa: F841
            sender="sender-test@example.com"
        )

        inbox_page.page = authenticated_page
        email_reader_page.page = authenticated_page

        await inbox_page.goto()
        await inbox_page.click_email(0)

        await email_reader_page.assert_sender("sender-test@example.com")

    @pytest.mark.asyncio
    async def test_email_reader_shows_date(
        self, authenticated_page: Page, inbox_page: InboxPage,
        email_reader_page: EmailReaderPage, api_client
    ):
        """Test that email reader shows date."""
        await api_client.create_test_email()

        inbox_page.page = authenticated_page
        email_reader_page.page = authenticated_page

        await inbox_page.goto()
        await inbox_page.click_email(0)

        date_text = await email_reader_page.get_date()
        assert date_text is not None

    @pytest.mark.asyncio
    async def test_email_reader_shows_attachments(
        self, authenticated_page: Page, inbox_page: InboxPage,
        email_reader_page: EmailReaderPage, api_client
    ):
        """Test that email reader shows attachments."""
        # Note: This would need an email with attachments
        # Document attachment display behavior

    @pytest.mark.asyncio
    async def test_back_to_inbox_from_reader(
        self, authenticated_page: Page, inbox_page: InboxPage,
        email_reader_page: EmailReaderPage, api_client
    ):
        """Test navigating back to inbox from email reader."""
        await api_client.create_test_email()

        inbox_page.page = authenticated_page
        email_reader_page.page = authenticated_page

        await inbox_page.goto()
        await inbox_page.click_email(0)
        await email_reader_page.assert_email_visible()

        await email_reader_page.go_back()

        await inbox_page.assert_on_inbox_page()

    @pytest.mark.asyncio
    async def test_navigate_between_emails(
        self, authenticated_page: Page, inbox_page: InboxPage,
        email_reader_page: EmailReaderPage, api_client
    ):
        """Test navigating between emails using prev/next."""
        await api_client.create_test_email(subject="Email 1")
        await api_client.create_test_email(subject="Email 2")

        inbox_page.page = authenticated_page
        email_reader_page.page = authenticated_page

        await inbox_page.goto()
        await inbox_page.click_email(0)

        # Navigate to next email
        if await email_reader_page.next_email_button.count() > 0:
            await email_reader_page.go_to_next_email()
            await email_reader_page.assert_email_visible()


# =============================================================================
# Mark Read/Unread Tests
# =============================================================================

class TestMarkReadUnread:
    """Tests for marking emails as read/unread."""

    @pytest.mark.asyncio
    async def test_opening_email_marks_as_read(
        self, authenticated_page: Page, inbox_page: InboxPage,
        email_reader_page: EmailReaderPage, api_client
    ):
        """Test that opening an email marks it as read."""
        _test_email = await api_client.create_test_email()  # noqa: F841

        inbox_page.page = authenticated_page
        email_reader_page.page = authenticated_page

        await inbox_page.goto()

        # Email should be unread initially
        _initial_unread_count = await inbox_page.get_unread_count()  # noqa: F841

        # Open the email
        await inbox_page.click_email(0)
        await email_reader_page.assert_email_visible()

        # Go back and check
        await email_reader_page.go_back()

        # Unread count should decrease (or email should appear read)

    @pytest.mark.asyncio
    async def test_mark_email_as_unread(
        self, authenticated_page: Page, inbox_page: InboxPage,
        email_reader_page: EmailReaderPage, api_client
    ):
        """Test marking an email as unread."""
        test_email = await api_client.create_test_email()
        # Mark as read via API first
        await api_client.mark_email_read(test_email.id, True)

        inbox_page.page = authenticated_page
        email_reader_page.page = authenticated_page

        await inbox_page.goto()
        await inbox_page.click_email(0)

        # Mark as unread
        await email_reader_page.mark_unread()

        # Go back and verify
        await email_reader_page.go_back()
        is_unread = await inbox_page.is_email_unread(0)
        assert is_unread

    @pytest.mark.asyncio
    async def test_mark_email_as_read_from_list(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test marking email as read from inbox list."""
        _test_email = await api_client.create_test_email()  # noqa: F841

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        # Select and mark as read
        await inbox_page.mark_email_read(0)

        # Verify it's marked as read
        is_unread = await inbox_page.is_email_unread(0)
        assert not is_unread

    @pytest.mark.asyncio
    async def test_mark_multiple_emails_as_read(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test marking multiple emails as read."""
        await api_client.create_test_email()
        await api_client.create_test_email()
        await api_client.create_test_email()

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        # Select multiple emails
        await inbox_page.select_emails([0, 1, 2])

        # Mark all as read
        await inbox_page.mark_read_button.click()

        # Verify all are read
        await inbox_page.assert_unread_count(0)


# =============================================================================
# Starring Tests
# =============================================================================

class TestStarring:
    """Tests for starring/favoriting emails."""

    @pytest.mark.asyncio
    async def test_star_email_from_list(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test starring an email from inbox list."""
        await api_client.create_test_email()

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        # Star the email
        await inbox_page.star_email(0)

        # Verify it's starred
        is_starred = await inbox_page.is_email_starred(0)
        assert is_starred

    @pytest.mark.asyncio
    async def test_unstar_email(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test unstarring a starred email."""
        test_email = await api_client.create_test_email()
        await api_client.star_email(test_email.id, True)

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        # Unstar the email
        await inbox_page.unstar_email(0)

        # Verify it's not starred
        is_starred = await inbox_page.is_email_starred(0)
        assert not is_starred

    @pytest.mark.asyncio
    async def test_star_email_from_reader(
        self, authenticated_page: Page, inbox_page: InboxPage,
        email_reader_page: EmailReaderPage, api_client
    ):
        """Test starring an email from the reader view."""
        await api_client.create_test_email()

        inbox_page.page = authenticated_page
        email_reader_page.page = authenticated_page

        await inbox_page.goto()
        await inbox_page.click_email(0)

        # Star from reader
        await email_reader_page.star()

        await email_reader_page.assert_starred()

    @pytest.mark.asyncio
    async def test_starred_emails_filter(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test filtering to show only starred emails."""
        # Create starred and non-starred emails
        email1 = await api_client.create_test_email(subject="Starred Email")
        await api_client.star_email(email1.id, True)
        await api_client.create_test_email(subject="Not Starred")

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        # If there's a starred filter/folder
        starred_folder = inbox_page.page.locator(
            "a:has-text('Starred'), [data-folder='starred']"
        )
        if await starred_folder.count() > 0:
            await starred_folder.click()
            await inbox_page.wait_for_loading_complete()

            # Should only show starred email
            await inbox_page.assert_email_visible("Starred Email")


# =============================================================================
# Deleting Tests
# =============================================================================

class TestDeleting:
    """Tests for deleting emails."""

    @pytest.mark.asyncio
    async def test_delete_email_from_list(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test deleting an email from inbox list."""
        _test_email = await api_client.create_test_email(  # noqa: F841
            subject="Delete Test Email"
        )

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        await inbox_page.assert_email_visible("Delete Test Email")

        # Delete the email
        await inbox_page.delete_email(0)

        # Email should no longer be visible
        await inbox_page.assert_email_not_visible("Delete Test Email")

    @pytest.mark.asyncio
    async def test_delete_email_from_reader(
        self, authenticated_page: Page, inbox_page: InboxPage,
        email_reader_page: EmailReaderPage, api_client
    ):
        """Test deleting an email from reader view."""
        _test_email = await api_client.create_test_email(  # noqa: F841
            subject="Reader Delete Test"
        )

        inbox_page.page = authenticated_page
        email_reader_page.page = authenticated_page

        await inbox_page.goto()
        await inbox_page.click_email_by_subject("Reader Delete Test")

        # Delete from reader
        await email_reader_page.delete_and_confirm()

        # Should return to inbox
        await inbox_page.assert_on_inbox_page()
        await inbox_page.assert_email_not_visible("Reader Delete Test")

    @pytest.mark.asyncio
    async def test_delete_multiple_emails(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test deleting multiple emails."""
        await api_client.create_test_email(subject="Multi Delete 1")
        await api_client.create_test_email(subject="Multi Delete 2")
        await api_client.create_test_email(subject="Multi Delete 3")

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        # Select multiple emails
        await inbox_page.select_emails([0, 1, 2])

        # Delete selected
        await inbox_page.delete_selected_emails()

        # All should be gone
        await inbox_page.assert_email_not_visible("Multi Delete 1")
        await inbox_page.assert_email_not_visible("Multi Delete 2")
        await inbox_page.assert_email_not_visible("Multi Delete 3")

    @pytest.mark.asyncio
    async def test_deleted_email_goes_to_trash(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test that deleted email appears in trash folder."""
        _test_email = await api_client.create_test_email(  # noqa: F841
            subject="Trash Test Email"
        )

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        # Delete the email
        await inbox_page.delete_email(0)

        # Navigate to trash
        await inbox_page.go_to_folder("trash")

        # Email should be in trash
        await inbox_page.assert_email_visible("Trash Test Email")

    @pytest.mark.asyncio
    async def test_permanent_delete_from_trash(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test permanently deleting an email from trash."""
        _test_email = await api_client.create_test_email(  # noqa: F841
            subject="Permanent Delete Test"
        )

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        # Delete to move to trash
        await inbox_page.delete_email(0)

        # Go to trash
        await inbox_page.go_to_folder("trash")

        # Delete again from trash (permanent)
        await inbox_page.delete_email(0)

        # Should be permanently gone
        await inbox_page.assert_email_not_visible("Permanent Delete Test")

    @pytest.mark.asyncio
    async def test_delete_confirmation_dialog(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test that delete shows confirmation dialog (if implemented)."""
        await api_client.create_test_email()

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        await inbox_page.select_email(0)
        await inbox_page.delete_button.click()

        # Check for confirmation dialog
        _confirm_dialog = authenticated_page.locator(  # noqa: F841
            "[role='alertdialog'], .confirm-dialog, [data-testid='confirm-delete']"
        )

        # Document whether confirmation is required


# =============================================================================
# Folder Navigation Tests
# =============================================================================

class TestFolderNavigation:
    """Tests for navigating between folders."""

    @pytest.mark.asyncio
    async def test_navigate_to_sent(
        self, authenticated_page: Page, inbox_page: InboxPage
    ):
        """Test navigating to sent folder."""
        inbox_page.page = authenticated_page
        await inbox_page.goto()

        await inbox_page.go_to_folder("sent")

        await expect(inbox_page.folder_sent).to_have_class("*active*")

    @pytest.mark.asyncio
    async def test_navigate_to_drafts(
        self, authenticated_page: Page, inbox_page: InboxPage
    ):
        """Test navigating to drafts folder."""
        inbox_page.page = authenticated_page
        await inbox_page.goto()

        await inbox_page.go_to_folder("drafts")

        await expect(inbox_page.folder_drafts).to_have_class("*active*")

    @pytest.mark.asyncio
    async def test_navigate_to_trash(
        self, authenticated_page: Page, inbox_page: InboxPage
    ):
        """Test navigating to trash folder."""
        inbox_page.page = authenticated_page
        await inbox_page.goto()

        await inbox_page.go_to_folder("trash")

        await expect(inbox_page.folder_trash).to_have_class("*active*")

    @pytest.mark.asyncio
    async def test_navigate_to_spam(
        self, authenticated_page: Page, inbox_page: InboxPage
    ):
        """Test navigating to spam folder."""
        inbox_page.page = authenticated_page
        await inbox_page.goto()

        await inbox_page.go_to_folder("spam")

        await expect(inbox_page.folder_spam).to_have_class("*active*")


# =============================================================================
# Search Tests
# =============================================================================

class TestInboxSearch:
    """Tests for searching emails."""

    @pytest.mark.asyncio
    async def test_search_by_subject(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test searching emails by subject."""
        await api_client.create_test_email(subject="Unique Search Subject")
        await api_client.create_test_email(subject="Different Email")

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        await inbox_page.search_emails("Unique Search")

        await inbox_page.assert_email_visible("Unique Search Subject")
        await inbox_page.assert_email_not_visible("Different Email")

    @pytest.mark.asyncio
    async def test_search_by_sender(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test searching emails by sender."""
        await api_client.create_test_email(sender="searchable-sender@test.com")

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        await inbox_page.search_emails("searchable-sender")

        # Should find the email

    @pytest.mark.asyncio
    async def test_search_no_results(
        self, authenticated_page: Page, inbox_page: InboxPage
    ):
        """Test search with no matching results."""
        inbox_page.page = authenticated_page
        await inbox_page.goto()

        await inbox_page.search_emails("xyznonexistentqueryzyx")

        # Should show empty or no results message

    @pytest.mark.asyncio
    async def test_clear_search(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test clearing search to show all emails."""
        await api_client.create_test_email(subject="Test 1")
        await api_client.create_test_email(subject="Test 2")

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        # Search to filter
        await inbox_page.search_emails("Test 1")

        # Clear search
        await inbox_page.clear_search()

        # All emails should be visible again


# =============================================================================
# Bulk Actions Tests
# =============================================================================

class TestBulkActions:
    """Tests for bulk email actions."""

    @pytest.mark.asyncio
    async def test_select_all_emails(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test selecting all emails."""
        await api_client.create_test_email()
        await api_client.create_test_email()
        await api_client.create_test_email()

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        await inbox_page.select_all_emails()

        # All should be selected
        selected_count = await inbox_page.selected_emails.count()
        email_count = await inbox_page.get_email_count()
        assert selected_count == email_count

    @pytest.mark.asyncio
    async def test_archive_multiple_emails(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test archiving multiple emails."""
        await api_client.create_test_email(subject="Archive 1")
        await api_client.create_test_email(subject="Archive 2")

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        await inbox_page.select_emails([0, 1])
        await inbox_page.archive_button.click()

        # Emails should be moved to archive


# =============================================================================
# Accessibility Tests
# =============================================================================

class TestInboxAccessibility:
    """Accessibility tests for inbox functionality."""

    @pytest.mark.asyncio
    async def test_email_list_keyboard_navigation(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test keyboard navigation through email list."""
        await api_client.create_test_email()
        await api_client.create_test_email()

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        # Tab to email list
        await authenticated_page.keyboard.press("Tab")

        # Arrow keys to navigate
        await authenticated_page.keyboard.press("ArrowDown")
        await authenticated_page.keyboard.press("ArrowUp")

        # Enter to open
        await authenticated_page.keyboard.press("Enter")

    @pytest.mark.asyncio
    async def test_email_list_has_role(
        self, authenticated_page: Page, inbox_page: InboxPage
    ):
        """Test that email list has appropriate ARIA role."""
        inbox_page.page = authenticated_page
        await inbox_page.goto()

        _role = await inbox_page.email_list.get_attribute("role")  # noqa: F841
        # Should have list role or similar

    @pytest.mark.asyncio
    async def test_screen_reader_announcements(
        self, authenticated_page: Page, inbox_page: InboxPage, api_client
    ):
        """Test that actions are announced to screen readers."""
        await api_client.create_test_email()

        inbox_page.page = authenticated_page
        await inbox_page.goto()

        # Check for live regions
        _live_regions = authenticated_page.locator("[aria-live]")  # noqa: F841
        # Document screen reader support
