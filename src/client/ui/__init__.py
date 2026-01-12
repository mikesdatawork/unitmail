"""
unitMail client UI components.
"""

from .composer import ComposerWindow, ComposerMode, EmailMessage, create_composer
from .application import UnitMailApplication, run_application
from .main_window import MainWindow, FolderItem, MessageItem
from .reader import MessageViewer, MessageBodyView, sanitize_html, plain_text_to_html
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
)

__all__ = [
    # Application
    'UnitMailApplication',
    'MainWindow',
    'FolderItem',
    'MessageItem',
    'run_application',
    # Composer
    'ComposerWindow',
    'ComposerMode',
    'EmailMessage',
    'create_composer',
    # Reader
    'MessageViewer',
    'MessageBodyView',
    'sanitize_html',
    'plain_text_to_html',
    # Widgets
    'RecipientEntry',
    'AttachmentPanel',
    'AttachmentList',
    'AttachmentRow',
    'Attachment',
    'AttachmentType',
    'AttachmentPreviewDialog',
    'AvatarWidget',
    'MessageHeader',
    'RecipientChip',
    'format_file_size',
    'format_date_time',
    'format_email_address',
    'get_avatar_color',
    'get_initials',
    'get_attachment_type_from_filename',
]
