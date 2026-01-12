"""
Page Object Model classes for unitMail E2E tests.

These classes provide reusable selectors and methods for interacting
with different pages in the unitMail application.
"""

from .base_page import BasePage
from .login_page import LoginPage
from .inbox_page import InboxPage
from .compose_page import ComposePage
from .contacts_page import ContactsPage
from .email_reader_page import EmailReaderPage

__all__ = [
    "BasePage",
    "LoginPage",
    "InboxPage",
    "ComposePage",
    "ContactsPage",
    "EmailReaderPage",
]
