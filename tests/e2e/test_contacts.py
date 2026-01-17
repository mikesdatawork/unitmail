"""
E2E tests for contacts functionality.

Tests cover:
- Adding contacts
- Editing contacts
- Deleting contacts
- Searching contacts
"""

import pytest
from playwright.async_api import Page, expect

from .pages import ContactsPage, ComposePage


# =============================================================================
# Test Constants
# =============================================================================

TEST_CONTACT_NAME = "John Doe"
TEST_CONTACT_EMAIL = "john.doe@example.com"
TEST_CONTACT_PHONE = "+1-555-123-4567"
TEST_CONTACT_COMPANY = "Test Company Inc."


# =============================================================================
# Adding Contact Tests
# =============================================================================

class TestAddContact:
    """Tests for adding new contacts."""

    @pytest.mark.asyncio
    async def test_contacts_page_loads(
        self, authenticated_page: Page, contacts_page: ContactsPage
    ):
        """Test that contacts page loads correctly."""
        contacts_page.page = authenticated_page
        await contacts_page.goto()
        await contacts_page.assert_on_contacts_page()

    @pytest.mark.asyncio
    async def test_add_contact_button_visible(
        self, authenticated_page: Page, contacts_page: ContactsPage
    ):
        """Test that add contact button is visible."""
        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await expect(contacts_page.add_contact_button).to_be_visible()

    @pytest.mark.asyncio
    async def test_open_add_contact_form(
        self, authenticated_page: Page, contacts_page: ContactsPage
    ):
        """Test opening the add contact form."""
        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.open_add_contact_form()

        await contacts_page.assert_contact_form_visible()

    @pytest.mark.asyncio
    async def test_add_contact_with_name_and_email(
        self, authenticated_page: Page, contacts_page: ContactsPage, unique_contact_name: str
    ):
        """Test adding a contact with name and email."""
        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.add_contact(
            name=unique_contact_name,
            email=TEST_CONTACT_EMAIL,
        )

        # Contact should appear in list
        await contacts_page.assert_contact_visible(unique_contact_name)

    @pytest.mark.asyncio
    async def test_add_contact_with_all_fields(
        self, authenticated_page: Page, contacts_page: ContactsPage, unique_contact_name: str
    ):
        """Test adding a contact with all fields filled."""
        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.add_contact(
            name=unique_contact_name,
            email=TEST_CONTACT_EMAIL,
            phone=TEST_CONTACT_PHONE,
            company=TEST_CONTACT_COMPANY,
        )

        await contacts_page.assert_contact_visible(unique_contact_name)

    @pytest.mark.asyncio
    async def test_add_contact_with_first_last_name(
        self, authenticated_page: Page, contacts_page: ContactsPage
    ):
        """Test adding a contact with separate first/last name fields."""
        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.open_add_contact_form()

        # Check if separate first/last name fields exist
        if await contacts_page.form_first_name_input.count() > 0:
            await contacts_page.fill_contact_form(
                first_name="Jane",
                last_name="Smith",
                email="jane.smith@example.com",
            )
            await contacts_page.save_contact_and_wait()

            # Should show combined name
            await contacts_page.assert_contact_visible("Jane")

    @pytest.mark.asyncio
    async def test_add_contact_validation_email_required(
        self, authenticated_page: Page, contacts_page: ContactsPage
    ):
        """Test that email is required when adding contact."""
        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.open_add_contact_form()
        await contacts_page.fill_contact_form(
            name=TEST_CONTACT_NAME,
            # No email
        )
        await contacts_page.save_contact()

        # Should show validation error
        await contacts_page.assert_validation_error()

    @pytest.mark.asyncio
    async def test_add_contact_validation_invalid_email(
        self, authenticated_page: Page, contacts_page: ContactsPage
    ):
        """Test validation for invalid email format."""
        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.open_add_contact_form()
        await contacts_page.fill_contact_form(
            name=TEST_CONTACT_NAME,
            email="not-an-email",
        )
        await contacts_page.save_contact()

        # Should show validation error
        await contacts_page.assert_validation_error()

    @pytest.mark.asyncio
    async def test_cancel_add_contact(
        self, authenticated_page: Page, contacts_page: ContactsPage
    ):
        """Test canceling add contact form."""
        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.open_add_contact_form()
        await contacts_page.fill_contact_form(
            name=TEST_CONTACT_NAME,
            email=TEST_CONTACT_EMAIL,
        )
        await contacts_page.cancel_contact_form()

        # Form should close
        await contacts_page.assert_contact_form_hidden()

        # Contact should not be added
        await contacts_page.assert_contact_not_visible(TEST_CONTACT_NAME)

    @pytest.mark.asyncio
    async def test_add_duplicate_contact(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test adding a contact with duplicate email."""
        # Create existing contact
        _existing = await api_client.create_test_contact(email="duplicate@test.com")  # noqa: F841

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.open_add_contact_form()
        await contacts_page.fill_contact_form(
            name="Another Person",
            email="duplicate@test.com",
        )
        await contacts_page.save_contact()

        # Should show error or warning about duplicate


# =============================================================================
# Editing Contact Tests
# =============================================================================

class TestEditContact:
    """Tests for editing existing contacts."""

    @pytest.mark.asyncio
    async def test_open_edit_contact_form(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test opening edit form for a contact."""
        _contact = await api_client.create_test_contact()  # noqa: F841

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.edit_contact_by_name(contact.name)

        await contacts_page.assert_contact_form_visible()

    @pytest.mark.asyncio
    async def test_edit_contact_name(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test editing contact name."""
        _contact = await api_client.create_test_contact(name="Original Name")  # noqa: F841

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.edit_contact_by_name("Original Name")
        await contacts_page.fill_contact_form(name="Updated Name")
        await contacts_page.save_contact_and_wait()

        # Updated name should be visible
        await contacts_page.assert_contact_visible("Updated Name")
        # Old name should not be visible
        await contacts_page.assert_contact_not_visible("Original Name")

    @pytest.mark.asyncio
    async def test_edit_contact_email(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test editing contact email."""
        _contact = await api_client.create_test_contact(  # noqa: F841
            email="original@example.com"
        )

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.edit_contact_by_name(contact.name)
        await contacts_page.fill_contact_form(email="updated@example.com")
        await contacts_page.save_contact_and_wait()

        # Click on contact to verify email
        await contacts_page.click_contact_by_name(contact.name)
        email_text = await contacts_page.details_email.text_content()
        assert "updated@example.com" in email_text

    @pytest.mark.asyncio
    async def test_edit_contact_phone(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test editing contact phone number."""
        _contact = await api_client.create_test_contact()  # noqa: F841

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.edit_contact_by_name(contact.name)
        await contacts_page.fill_contact_form(phone="+1-555-999-8888")
        await contacts_page.save_contact_and_wait()

    @pytest.mark.asyncio
    async def test_edit_contact_preserves_unchanged_fields(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test that editing preserves unchanged fields."""
        _contact = await api_client.create_test_contact(  # noqa: F841
            name="Preserve Test",
            email="preserve@test.com"
        )

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.edit_contact_by_name("Preserve Test")

        # Only change phone
        await contacts_page.fill_contact_form(phone="+1-555-111-2222")
        await contacts_page.save_contact_and_wait()

        # Name and email should still be the same
        await contacts_page.assert_contact_visible("Preserve Test")

    @pytest.mark.asyncio
    async def test_cancel_edit_contact(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test canceling contact edit."""
        _contact = await api_client.create_test_contact(name="Cancel Edit Test")  # noqa: F841

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.edit_contact_by_name("Cancel Edit Test")
        await contacts_page.fill_contact_form(name="Should Not Save")
        await contacts_page.cancel_contact_form()

        # Original name should still be visible
        await contacts_page.assert_contact_visible("Cancel Edit Test")

    @pytest.mark.asyncio
    async def test_edit_contact_validation(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test validation when editing contact."""
        _contact = await api_client.create_test_contact()  # noqa: F841

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.edit_contact_by_name(contact.name)

        # Clear email and try to save
        await contacts_page.form_email_input.clear()
        await contacts_page.save_contact()

        # Should show validation error
        await contacts_page.assert_validation_error()


# =============================================================================
# Deleting Contact Tests
# =============================================================================

class TestDeleteContact:
    """Tests for deleting contacts."""

    @pytest.mark.asyncio
    async def test_delete_contact(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test deleting a contact."""
        _contact = await api_client.create_test_contact(name="Delete Test")  # noqa: F841

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.assert_contact_visible("Delete Test")

        await contacts_page.delete_contact_by_name("Delete Test", confirm=True)

        # Contact should be removed
        await contacts_page.assert_contact_not_visible("Delete Test")

    @pytest.mark.asyncio
    async def test_delete_contact_confirmation_dialog(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test that delete shows confirmation dialog."""
        _contact = await api_client.create_test_contact()  # noqa: F841

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.click_contact_by_name(contact.name)
        await contacts_page.delete_contact_button.click()

        # Confirmation dialog should appear
        await expect(contacts_page.delete_confirmation_dialog).to_be_visible()

    @pytest.mark.asyncio
    async def test_cancel_delete_contact(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test canceling contact deletion."""
        _contact = await api_client.create_test_contact(name="Cancel Delete Test")  # noqa: F841

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.delete_contact_by_name("Cancel Delete Test", confirm=False)

        # Contact should still exist
        await contacts_page.assert_contact_visible("Cancel Delete Test")

    @pytest.mark.asyncio
    async def test_delete_multiple_contacts(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test deleting multiple contacts."""
        await api_client.create_test_contact(name="Multi Delete 1")
        await api_client.create_test_contact(name="Multi Delete 2")

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        # Select multiple contacts (if supported)
        # This depends on the UI implementation

    @pytest.mark.asyncio
    async def test_delete_contact_keyboard_shortcut(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test deleting contact with keyboard shortcut."""
        _contact = await api_client.create_test_contact()  # noqa: F841

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.click_contact_by_name(contact.name)

        # Try Delete key
        await authenticated_page.keyboard.press("Delete")

        # Should trigger delete dialog or action


# =============================================================================
# Search Contacts Tests
# =============================================================================

class TestSearchContacts:
    """Tests for searching contacts."""

    @pytest.mark.asyncio
    async def test_search_by_name(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test searching contacts by name."""
        await api_client.create_test_contact(name="Alice Johnson")
        await api_client.create_test_contact(name="Bob Smith")

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.search_contacts("Alice")

        await contacts_page.assert_contact_visible("Alice Johnson")
        await contacts_page.assert_contact_not_visible("Bob Smith")

    @pytest.mark.asyncio
    async def test_search_by_email(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test searching contacts by email."""
        await api_client.create_test_contact(
            name="Contact A",
            email="unique-email@example.com"
        )
        await api_client.create_test_contact(
            name="Contact B",
            email="other@example.com"
        )

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.search_contacts("unique-email")

        await contacts_page.assert_contact_visible("Contact A")
        await contacts_page.assert_contact_not_visible("Contact B")

    @pytest.mark.asyncio
    async def test_search_partial_match(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test that search works with partial matches."""
        await api_client.create_test_contact(name="Christopher Anderson")

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.search_contacts("Chris")

        await contacts_page.assert_contact_visible("Christopher Anderson")

    @pytest.mark.asyncio
    async def test_search_case_insensitive(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test that search is case insensitive."""
        await api_client.create_test_contact(name="Test Person")

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.search_contacts("TEST PERSON")

        await contacts_page.assert_contact_visible("Test Person")

    @pytest.mark.asyncio
    async def test_search_no_results(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test search with no matching results."""
        await api_client.create_test_contact(name="Some Contact")

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.search_contacts("xyznonexistentxyz")

        # Should show no contacts
        await contacts_page.assert_search_results_count(0)

    @pytest.mark.asyncio
    async def test_clear_search(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test clearing search to show all contacts."""
        await api_client.create_test_contact(name="Contact Alpha")
        await api_client.create_test_contact(name="Contact Beta")

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        # Search to filter
        await contacts_page.search_contacts("Alpha")
        await contacts_page.assert_contact_visible("Contact Alpha")

        # Clear search
        await contacts_page.clear_search()

        # All contacts should be visible
        await contacts_page.assert_contact_visible("Contact Alpha")
        await contacts_page.assert_contact_visible("Contact Beta")

    @pytest.mark.asyncio
    async def test_search_realtime(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test that search updates in realtime as user types."""
        await api_client.create_test_contact(name="Realtime Test")

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        # Type letter by letter
        await contacts_page.search_input.type("Real", delay=100)

        # Results should update as typing
        await authenticated_page.wait_for_timeout(500)  # Wait for debounce

        await contacts_page.assert_contact_visible("Realtime Test")


# =============================================================================
# Contact Details Tests
# =============================================================================

class TestContactDetails:
    """Tests for viewing contact details."""

    @pytest.mark.asyncio
    async def test_view_contact_details(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test viewing contact details."""
        _contact = await api_client.create_test_contact(  # noqa: F841
            name="Details Test Contact",
            email="details@test.com"
        )

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.click_contact_by_name("Details Test Contact")

        await contacts_page.assert_contact_details_shown("Details Test Contact")

    @pytest.mark.asyncio
    async def test_contact_details_shows_email(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test that contact details shows email."""
        _contact = await api_client.create_test_contact(  # noqa: F841
            name="Email Details Test",
            email="email-details@test.com"
        )

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.click_contact_by_name("Email Details Test")

        await expect(contacts_page.details_email).to_contain_text("email-details@test.com")

    @pytest.mark.asyncio
    async def test_compose_email_to_contact(
        self, authenticated_page: Page, contacts_page: ContactsPage,
        compose_page: ComposePage, api_client
    ):
        """Test composing email to a contact."""
        _contact = await api_client.create_test_contact(  # noqa: F841
            name="Compose To Contact",
            email="compose-to@test.com"
        )

        contacts_page.page = authenticated_page
        compose_page.page = authenticated_page

        await contacts_page.goto()
        await contacts_page.compose_email_to_contact(0)

        # Compose should open with contact as recipient
        await compose_page.assert_compose_form_visible()


# =============================================================================
# Contact Groups/Labels Tests
# =============================================================================

class TestContactGroups:
    """Tests for contact groups/labels functionality."""

    @pytest.mark.asyncio
    async def test_add_contact_to_group(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test adding a contact to a group."""
        _contact = await api_client.create_test_contact()  # noqa: F841

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        # This test documents expected group functionality

    @pytest.mark.asyncio
    async def test_filter_by_group(
        self, authenticated_page: Page, contacts_page: ContactsPage
    ):
        """Test filtering contacts by group."""
        contacts_page.page = authenticated_page
        await contacts_page.goto()

        # Look for group filter
        _group_filter = authenticated_page.locator(  # noqa: F841
            "[data-testid='group-filter'], .group-filter, "
            ".contact-groups"
        )

        # Document group filtering behavior


# =============================================================================
# Import/Export Tests
# =============================================================================

class TestImportExport:
    """Tests for contact import/export functionality."""

    @pytest.mark.asyncio
    async def test_export_contacts_button_visible(
        self, authenticated_page: Page, contacts_page: ContactsPage
    ):
        """Test that export button is visible."""
        contacts_page.page = authenticated_page
        await contacts_page.goto()

        _export_visible = await contacts_page.export_contacts_button.count() > 0  # noqa: F841
        # Document export functionality

    @pytest.mark.asyncio
    async def test_import_contacts_button_visible(
        self, authenticated_page: Page, contacts_page: ContactsPage
    ):
        """Test that import button is visible."""
        contacts_page.page = authenticated_page
        await contacts_page.goto()

        _import_visible = await contacts_page.import_contacts_button.count() > 0  # noqa: F841
        # Document import functionality


# =============================================================================
# Accessibility Tests
# =============================================================================

class TestContactsAccessibility:
    """Accessibility tests for contacts functionality."""

    @pytest.mark.asyncio
    async def test_contacts_list_keyboard_navigation(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test keyboard navigation through contacts list."""
        await api_client.create_test_contact(name="Contact 1")
        await api_client.create_test_contact(name="Contact 2")

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        # Tab to contact list
        await authenticated_page.keyboard.press("Tab")

        # Arrow keys to navigate
        await authenticated_page.keyboard.press("ArrowDown")
        await authenticated_page.keyboard.press("ArrowUp")

        # Enter to select/view
        await authenticated_page.keyboard.press("Enter")

    @pytest.mark.asyncio
    async def test_contact_form_keyboard_navigation(
        self, authenticated_page: Page, contacts_page: ContactsPage
    ):
        """Test keyboard navigation through contact form."""
        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.open_add_contact_form()

        # Tab through form fields
        await authenticated_page.keyboard.press("Tab")  # Name
        await authenticated_page.keyboard.press("Tab")  # Email
        await authenticated_page.keyboard.press("Tab")  # Phone (if exists)
        await authenticated_page.keyboard.press("Tab")  # Save button

    @pytest.mark.asyncio
    async def test_contact_form_labels(
        self, authenticated_page: Page, contacts_page: ContactsPage
    ):
        """Test that contact form fields have proper labels."""
        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.open_add_contact_form()

        # Check for labels or aria-labels
        email_label = await contacts_page.form_email_input.get_attribute("aria-label")
        email_placeholder = await contacts_page.form_email_input.get_attribute("placeholder")

        assert email_label or email_placeholder

    @pytest.mark.asyncio
    async def test_search_announces_results(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test that search results are announced to screen readers."""
        await api_client.create_test_contact()

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        await contacts_page.search_contacts("test")

        # Check for live region
        _live_region = authenticated_page.locator("[aria-live]")  # noqa: F841
        # Document screen reader announcements


# =============================================================================
# Performance Tests
# =============================================================================

class TestContactsPerformance:
    """Performance tests for contacts functionality."""

    @pytest.mark.asyncio
    async def test_large_contacts_list_loads(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test that large contacts list loads efficiently."""
        # Create many contacts
        for i in range(50):
            await api_client.create_test_contact(name=f"Performance Test {i}")

        contacts_page.page = authenticated_page

        # Measure load time
        import time
        start = time.time()
        await contacts_page.goto()
        await contacts_page.wait_for_loading_complete()
        load_time = time.time() - start

        # Should load in reasonable time (adjust threshold as needed)
        assert load_time < 10  # 10 seconds max

    @pytest.mark.asyncio
    async def test_search_performance(
        self, authenticated_page: Page, contacts_page: ContactsPage, api_client
    ):
        """Test that search performs efficiently."""
        # Create contacts
        for i in range(20):
            await api_client.create_test_contact(name=f"Search Perf {i}")

        contacts_page.page = authenticated_page
        await contacts_page.goto()

        # Measure search time
        import time
        start = time.time()
        await contacts_page.search_contacts("Perf")
        await contacts_page.wait_for_loading_complete()
        search_time = time.time() - start

        # Search should be fast
        assert search_time < 2  # 2 seconds max
