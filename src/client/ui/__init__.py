"""
unitMail client UI components.
"""

from .composer import (
    ComposerWindow,
    ComposerMode,
    EmailMessage,
    create_composer,
)
from .application import UnitMailApplication, run_application
from .main_window import MainWindow, FolderItem, MessageItem
from .reader import (
    MessageViewer,
    MessageBodyView,
    sanitize_html,
    plain_text_to_html,
)
from .folders import FolderManagerDialog, FolderListItem
from .search import SearchDialog, SearchPopover
from .contacts import (
    ContactsWindow,
    Contact,
    ContactGroup,
    ContactListItem,
)
from .settings import (
    SettingsWindow,
    PasswordChangeDialog,
    create_settings_window,
)
from .view_theme import (
    ViewTheme,
    ViewThemeManager,
    ViewThemeSelector,
    get_view_theme_manager,
    THEME_DESCRIPTIONS,
)
from .widgets import (
    RecipientEntry,
    AttachmentPanel,
    AttachmentList,
    AttachmentRow,
    Attachment,
    AttachmentType,
    AttachmentPreviewDialog,
    AvatarWidget,
    MessageHeader,
    RecipientChip,
    format_file_size,
    format_date_time,
    format_email_address,
    get_avatar_color,
    get_initials,
    get_attachment_type_from_filename,
    FolderTree,
    FolderTreeItem,
    FolderData,
    FolderType,
    SYSTEM_FOLDERS,
    FOLDER_ICONS,
    SearchBar,
    SearchSuggestionItem,
    ExpandableSearchBar,
    PGPKeyManager,
    PGPKey,
    PGPKeyRow,
    KeyTrustLevel,
    KeyGenerationDialog,
    KeyDetailsDialog,
)

__all__ = [
    # Application
    "UnitMailApplication",
    "MainWindow",
    "FolderItem",
    "MessageItem",
    "run_application",
    # Composer
    "ComposerWindow",
    "ComposerMode",
    "EmailMessage",
    "create_composer",
    # Reader
    "MessageViewer",
    "MessageBodyView",
    "sanitize_html",
    "plain_text_to_html",
    # Folder Management
    "FolderManagerDialog",
    "FolderListItem",
    "FolderTree",
    "FolderTreeItem",
    "FolderData",
    "FolderType",
    "SYSTEM_FOLDERS",
    "FOLDER_ICONS",
    # Contacts
    "ContactsWindow",
    "Contact",
    "ContactGroup",
    "ContactListItem",
    # Widgets
    "RecipientEntry",
    "AttachmentPanel",
    "AttachmentList",
    "AttachmentRow",
    "Attachment",
    "AttachmentType",
    "AttachmentPreviewDialog",
    "AvatarWidget",
    "MessageHeader",
    "RecipientChip",
    "format_file_size",
    "format_date_time",
    "format_email_address",
    "get_avatar_color",
    "get_initials",
    "get_attachment_type_from_filename",
    # Search
    "SearchDialog",
    "SearchPopover",
    "SearchBar",
    "SearchSuggestionItem",
    "ExpandableSearchBar",
    # Settings
    "SettingsWindow",
    "PasswordChangeDialog",
    "create_settings_window",
    # PGP key manager
    "PGPKeyManager",
    "PGPKey",
    "PGPKeyRow",
    "KeyTrustLevel",
    "KeyGenerationDialog",
    "KeyDetailsDialog",
    # View themes
    "ViewTheme",
    "ViewThemeManager",
    "ViewThemeSelector",
    "get_view_theme_manager",
    "THEME_DESCRIPTIONS",
]
