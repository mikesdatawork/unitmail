"""
Contacts Page Object for contact management tests.
"""

from typing import Optional
from playwright.async_api import Page, expect, Locator
from .base_page import BasePage


class ContactsPage(BasePage):
    """Page Object for the contacts page."""

    def __init__(self, page: Page, base_url: str = "http://localhost:8080"):
        super().__init__(page, base_url)
        self.path = "/contacts"

    # Selectors - Contact List
    @property
    def contacts_container(self) -> Locator:
        """Main contacts container."""
        return self.page.locator(
            "[data-testid='contacts-container'], .contacts-container, "
            ".contacts-page, #contacts"
        )

    @property
    def contact_list(self) -> Locator:
        """Contact list container."""
        return self.page.locator(
            "[data-testid='contact-list'], .contact-list, "
            "[role='list'], .contacts-list"
        )

    @property
    def contact_items(self) -> Locator:
        """Individual contact items."""
        return self.page.locator(
            "[data-testid='contact-item'], .contact-item, "
            ".contact-row, [role='listitem']"
        )

    @property
    def contact_name(self) -> Locator:
        """Contact name elements."""
        return self.page.locator(
            "[data-testid='contact-name'], .contact-name, .name"
        )

    @property
    def contact_email(self) -> Locator:
        """Contact email elements."""
        return self.page.locator(
            "[data-testid='contact-email'], .contact-email, .email"
        )

    @property
    def contact_phone(self) -> Locator:
        """Contact phone elements."""
        return self.page.locator(
            "[data-testid='contact-phone'], .contact-phone, .phone"
        )

    @property
    def empty_contacts_message(self) -> Locator:
        """Empty contacts placeholder."""
        return self.page.locator(
            "[data-testid='empty-contacts'], .empty-contacts, "
            ":has-text('No contacts'), :has-text('Add your first contact')"
        )

    @property
    def selected_contacts(self) -> Locator:
        """Currently selected contacts."""
        return self.page.locator(
            ".contact-item.selected, [data-selected='true'], "
            "[aria-selected='true']"
        )

    # Selectors - Actions
    @property
    def add_contact_button(self) -> Locator:
        """Add new contact button."""
        return self.page.locator(
            "button:has-text('Add Contact'), button:has-text('New Contact'), "
            "button:has-text('Add'), [data-testid='add-contact-button'], "
            ".add-contact-btn"
        )

    @property
    def edit_contact_button(self) -> Locator:
        """Edit contact button."""
        return self.page.locator(
            "button:has-text('Edit'), button[aria-label='Edit'], "
            "[data-testid='edit-contact-button'], .edit-btn"
        )

    @property
    def delete_contact_button(self) -> Locator:
        """Delete contact button."""
        return self.page.locator(
            "button:has-text('Delete'), button[aria-label='Delete'], "
            "[data-testid='delete-contact-button'], .delete-btn"
        )

    @property
    def import_contacts_button(self) -> Locator:
        """Import contacts button."""
        return self.page.locator(
            "button:has-text('Import'), [data-testid='import-contacts'], "
            ".import-btn"
        )

    @property
    def export_contacts_button(self) -> Locator:
        """Export contacts button."""
        return self.page.locator(
            "button:has-text('Export'), [data-testid='export-contacts'], "
            ".export-btn"
        )

    # Selectors - Search
    @property
    def search_input(self) -> Locator:
        """Search contacts input."""
        return self.page.locator(
            "input[type='search'], input[placeholder*='Search'], "
            "[data-testid='contacts-search'], .search-input"
        )

    @property
    def search_button(self) -> Locator:
        """Search button."""
        return self.page.locator(
            "button[aria-label='Search'], button:has-text('Search'), "
            "[data-testid='search-button']"
        )

    @property
    def clear_search_button(self) -> Locator:
        """Clear search button."""
        return self.page.locator(
            "button[aria-label='Clear'], button:has-text('Clear'), "
            "[data-testid='clear-search']"
        )

    # Selectors - Contact Form (Add/Edit)
    @property
    def contact_form(self) -> Locator:
        """Contact add/edit form."""
        return self.page.locator(
            "[data-testid='contact-form'], .contact-form, "
            "form.contact, [role='dialog'] form"
        )

    @property
    def form_name_input(self) -> Locator:
        """Name input in contact form."""
        return self.page.locator(
            "input[name='name'], input[placeholder*='Name'], "
            "[data-testid='contact-name-input'], #contact-name"
        )

    @property
    def form_first_name_input(self) -> Locator:
        """First name input in contact form."""
        return self.page.locator(
            "input[name='firstName'], input[name='first_name'], "
            "input[placeholder*='First'], [data-testid='first-name-input']"
        )

    @property
    def form_last_name_input(self) -> Locator:
        """Last name input in contact form."""
        return self.page.locator(
            "input[name='lastName'], input[name='last_name'], "
            "input[placeholder*='Last'], [data-testid='last-name-input']"
        )

    @property
    def form_email_input(self) -> Locator:
        """Email input in contact form."""
        return self.page.locator(
            "input[name='email'], input[type='email'], "
            "input[placeholder*='Email'], [data-testid='contact-email-input']"
        )

    @property
    def form_phone_input(self) -> Locator:
        """Phone input in contact form."""
        return self.page.locator(
            "input[name='phone'], input[type='tel'], "
            "input[placeholder*='Phone'], [data-testid='contact-phone-input']"
        )

    @property
    def form_company_input(self) -> Locator:
        """Company input in contact form."""
        return self.page.locator(
            "input[name='company'], input[placeholder*='Company'], "
            "[data-testid='contact-company-input']"
        )

    @property
    def form_notes_input(self) -> Locator:
        """Notes input in contact form."""
        return self.page.locator(
            "textarea[name='notes'], [data-testid='contact-notes-input'], "
            ".notes-field textarea"
        )

    @property
    def form_save_button(self) -> Locator:
        """Save button in contact form."""
        return self.page.locator(
            "button:has-text('Save'), button[type='submit'], "
            "[data-testid='save-contact-button']"
        )

    @property
    def form_cancel_button(self) -> Locator:
        """Cancel button in contact form."""
        return self.page.locator(
            "button:has-text('Cancel'), [data-testid='cancel-contact-button']"
        )

    # Selectors - Contact Details
    @property
    def contact_details_panel(self) -> Locator:
        """Contact details panel/sidebar."""
        return self.page.locator(
            "[data-testid='contact-details'], .contact-details, "
            ".details-panel, aside.contact"
        )

    @property
    def details_name(self) -> Locator:
        """Name in contact details."""
        return self.contact_details_panel.locator(
            "[data-testid='details-name'], .details-name, h2, h3"
        )

    @property
    def details_email(self) -> Locator:
        """Email in contact details."""
        return self.contact_details_panel.locator(
            "[data-testid='details-email'], .details-email, "
            "a[href^='mailto:']"
        )

    @property
    def details_phone(self) -> Locator:
        """Phone in contact details."""
        return self.contact_details_panel.locator(
            "[data-testid='details-phone'], .details-phone, "
            "a[href^='tel:']"
        )

    @property
    def compose_email_button(self) -> Locator:
        """Compose email to contact button."""
        return self.page.locator(
            "button:has-text('Compose'), button:has-text('Email'), "
            "[data-testid='compose-to-contact'], .compose-email-btn"
        )

    # Selectors - Validation
    @property
    def validation_errors(self) -> Locator:
        """Form validation errors."""
        return self.page.locator(
            ".validation-error, .field-error, .error-message, "
            "[data-testid='validation-error'], .invalid-feedback"
        )

    # Selectors - Delete Confirmation
    @property
    def delete_confirmation_dialog(self) -> Locator:
        """Delete confirmation dialog."""
        return self.page.locator(
            "[data-testid='delete-confirmation'], .delete-dialog, "
            "[role='alertdialog'], .confirm-delete"
        )

    @property
    def confirm_delete_button(self) -> Locator:
        """Confirm delete button in dialog."""
        return self.delete_confirmation_dialog.locator(
            "button:has-text('Delete'), button:has-text('Confirm'), "
            "button:has-text('Yes'), [data-testid='confirm-delete']"
        )

    @property
    def cancel_delete_button(self) -> Locator:
        """Cancel delete button in dialog."""
        return self.delete_confirmation_dialog.locator(
            "button:has-text('Cancel'), button:has-text('No'), "
            "[data-testid='cancel-delete']"
        )

    # Actions
    async def goto(self) -> None:
        """Navigate to the contacts page."""
        await self.navigate_to(self.path)
        await self.wait_for_page_load()

    async def get_contact_count(self) -> int:
        """Get the number of contacts in the list."""
        return await self.contact_items.count()

    async def click_contact(self, index: int = 0) -> None:
        """Click on a contact by index."""
        await self.contact_items.nth(index).click()

    async def click_contact_by_name(self, name: str) -> None:
        """Click on a contact by name."""
        contact = self.contact_items.filter(has_text=name).first
        await contact.click()

    async def click_contact_by_email(self, email: str) -> None:
        """Click on a contact by email."""
        contact = self.contact_items.filter(has_text=email).first
        await contact.click()

    async def open_add_contact_form(self) -> None:
        """Open the add contact form."""
        await self.add_contact_button.click()
        await expect(self.contact_form).to_be_visible()

    async def fill_contact_form(
        self,
        name: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        company: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        """Fill in the contact form fields."""
        if name and await self.form_name_input.count() > 0:
            await self.fill_input(self.form_name_input, name)
        if first_name and await self.form_first_name_input.count() > 0:
            await self.fill_input(self.form_first_name_input, first_name)
        if last_name and await self.form_last_name_input.count() > 0:
            await self.fill_input(self.form_last_name_input, last_name)
        if email:
            await self.fill_input(self.form_email_input, email)
        if phone and await self.form_phone_input.count() > 0:
            await self.fill_input(self.form_phone_input, phone)
        if company and await self.form_company_input.count() > 0:
            await self.fill_input(self.form_company_input, company)
        if notes and await self.form_notes_input.count() > 0:
            await self.fill_input(self.form_notes_input, notes)

    async def save_contact(self) -> None:
        """Save the contact form."""
        await self.form_save_button.click()

    async def save_contact_and_wait(self) -> None:
        """Save contact and wait for completion."""
        await self.form_save_button.click()
        await self.wait_for_loading_complete()

    async def cancel_contact_form(self) -> None:
        """Cancel the contact form."""
        await self.form_cancel_button.click()

    async def add_contact(
        self,
        name: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        company: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        """Add a new contact with given details."""
        await self.open_add_contact_form()
        await self.fill_contact_form(
            name=name,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            company=company,
            notes=notes,
        )
        await self.save_contact_and_wait()

    async def edit_contact(self, index: int = 0) -> None:
        """Open edit form for a contact."""
        await self.click_contact(index)
        await self.edit_contact_button.click()
        await expect(self.contact_form).to_be_visible()

    async def edit_contact_by_name(self, name: str) -> None:
        """Open edit form for a contact by name."""
        await self.click_contact_by_name(name)
        await self.edit_contact_button.click()
        await expect(self.contact_form).to_be_visible()

    async def delete_contact(self, index: int = 0, confirm: bool = True) -> None:
        """Delete a contact by index."""
        await self.click_contact(index)
        await self.delete_contact_button.click()
        if confirm:
            await self.confirm_delete_button.click()
        else:
            await self.cancel_delete_button.click()
        await self.wait_for_loading_complete()

    async def delete_contact_by_name(self, name: str, confirm: bool = True) -> None:
        """Delete a contact by name."""
        await self.click_contact_by_name(name)
        await self.delete_contact_button.click()
        if confirm:
            await self.confirm_delete_button.click()
        else:
            await self.cancel_delete_button.click()
        await self.wait_for_loading_complete()

    async def search_contacts(self, query: str) -> None:
        """Search for contacts."""
        await self.fill_input(self.search_input, query)
        # Trigger search - either by button or by waiting for debounced search
        if await self.search_button.count() > 0:
            await self.search_button.click()
        else:
            await self.page.keyboard.press("Enter")
        await self.wait_for_loading_complete()

    async def clear_search(self) -> None:
        """Clear the search input."""
        if await self.clear_search_button.count() > 0:
            await self.clear_search_button.click()
        else:
            await self.search_input.clear()
            await self.page.keyboard.press("Enter")
        await self.wait_for_loading_complete()

    async def get_contact_name(self, index: int = 0) -> str:
        """Get the name of a contact by index."""
        return await self.contact_items.nth(index).locator(
            "[data-testid='contact-name'], .contact-name, .name"
        ).text_content()

    async def get_contact_email(self, index: int = 0) -> str:
        """Get the email of a contact by index."""
        return await self.contact_items.nth(index).locator(
            "[data-testid='contact-email'], .contact-email, .email"
        ).text_content()

    async def compose_email_to_contact(self, index: int = 0) -> None:
        """Open compose window with contact as recipient."""
        await self.click_contact(index)
        await self.compose_email_button.click()

    # Assertions
    async def assert_on_contacts_page(self) -> None:
        """Assert that we are on the contacts page."""
        await expect(self.contacts_container).to_be_visible()

    async def assert_contact_count(self, count: int) -> None:
        """Assert specific number of contacts."""
        await expect(self.contact_items).to_have_count(count)

    async def assert_contact_visible(self, name: str) -> None:
        """Assert that a contact with given name is visible."""
        contact = self.contact_items.filter(has_text=name)
        await expect(contact.first).to_be_visible()

    async def assert_contact_not_visible(self, name: str) -> None:
        """Assert that a contact with given name is not visible."""
        contact = self.contact_items.filter(has_text=name)
        await expect(contact).to_have_count(0)

    async def assert_contacts_empty(self) -> None:
        """Assert that contacts list is empty."""
        await expect(self.empty_contacts_message).to_be_visible()

    async def assert_contact_form_visible(self) -> None:
        """Assert that contact form is visible."""
        await expect(self.contact_form).to_be_visible()

    async def assert_contact_form_hidden(self) -> None:
        """Assert that contact form is hidden."""
        await expect(self.contact_form).to_be_hidden()

    async def assert_validation_error(self, error_text: Optional[str] = None) -> None:
        """Assert that validation error is shown."""
        await expect(self.validation_errors.first).to_be_visible()
        if error_text:
            await expect(self.validation_errors).to_contain_text(error_text)

    async def assert_contact_details_shown(self, name: str) -> None:
        """Assert that contact details panel shows specific contact."""
        await expect(self.contact_details_panel).to_be_visible()
        await expect(self.details_name).to_contain_text(name)

    async def assert_search_results_count(self, count: int) -> None:
        """Assert number of contacts in search results."""
        await expect(self.contact_items).to_have_count(count)
