"""
Custom widgets for unitMail client UI.
"""

from .recipient_entry import RecipientEntry
from .attachment_panel import AttachmentPanel
from .attachment_list import (
    Attachment,
    AttachmentList,
    AttachmentRow,
    AttachmentType,
    AttachmentPreviewDialog,
    format_file_size,
    get_attachment_type_from_filename,
)
from .message_header import (
    AvatarWidget,
    MessageHeader,
    RecipientChip,
    format_date_time,
    format_email_address,
    get_avatar_color,
    get_initials,
)
from .folder_tree import (
    FolderTree,
    FolderTreeItem,
    FolderData,
    FolderType,
    SYSTEM_FOLDERS,
    FOLDER_ICONS,
)
from .search_bar import (
    SearchBar,
    SearchSuggestionItem,
    ExpandableSearchBar,
)
from .pgp_key_manager import (
    PGPKeyManager,
    PGPKey,
    PGPKeyRow,
    KeyTrustLevel,
    KeyGenerationDialog,
    KeyDetailsDialog,
)

__all__ = [
    # Existing widgets
    'RecipientEntry',
    'AttachmentPanel',
    # Attachment widgets
    'Attachment',
    'AttachmentList',
    'AttachmentRow',
    'AttachmentType',
    'AttachmentPreviewDialog',
    'format_file_size',
    'get_attachment_type_from_filename',
    # Header widgets
    'AvatarWidget',
    'MessageHeader',
    'RecipientChip',
    'format_date_time',
    'format_email_address',
    'get_avatar_color',
    'get_initials',
    # Folder tree widget
    'FolderTree',
    'FolderTreeItem',
    'FolderData',
    'FolderType',
    'SYSTEM_FOLDERS',
    'FOLDER_ICONS',
    # Search widgets
    'SearchBar',
    'SearchSuggestionItem',
    'ExpandableSearchBar',
    # PGP key manager
    'PGPKeyManager',
    'PGPKey',
    'PGPKeyRow',
    'KeyTrustLevel',
    'KeyGenerationDialog',
    'KeyDetailsDialog',
]
