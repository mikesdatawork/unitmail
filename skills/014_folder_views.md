# Skill: Folder-Specific Views

## What This Skill Does
Implements distinct message views for each folder type, displaying appropriate sample/placeholder content based on folder purpose.

## Folder Types

| Folder | Purpose | Sample Content |
|--------|---------|----------------|
| **Inbox** | Received messages | Active emails from contacts |
| **Sent** | Sent messages | Outgoing emails you've sent |
| **Drafts** | Incomplete messages | Unsent email drafts |
| **Trash** | Deleted messages | Messages pending permanent deletion |
| **Spam** | Spam/junk mail | Detected spam messages |
| **Archive** | Archived messages | Older messages saved for reference |

## Implementation

### Folder Selection Handler
```python
def _on_folder_selection_changed(self, selection: Gtk.SingleSelection, param) -> None:
    position = selection.get_selected()
    if position != Gtk.INVALID_LIST_POSITION:
        folder = self._folder_store.get_item(position)
        folder_name = folder.name
        logging.info(f"Selected folder: {folder_name}")
        self._load_folder_messages(folder_name)
```

### Loading Folder Messages
```python
def _load_folder_messages(self, folder_name: str) -> None:
    """Load messages for a specific folder."""
    self._message_store.remove_all()

    folder_messages = {
        "Inbox": [
            MessageItem(
                message_id="1",
                sender="Alice Johnson <alice@example.com>",
                subject="Re: Project update",
                preview="Thanks for the update...",
                date="2026/01/12",
                is_read=False,
                is_starred=True,
            ),
            # ... more inbox messages
        ],
        "Sent": [
            MessageItem(
                message_id="101",
                sender="To: Bob Smith",
                subject="Meeting tomorrow",
                preview="Hi Bob, confirming our meeting...",
                date="2026/01/12",
                is_read=True,
                is_starred=False,
            ),
            # ... more sent messages
        ],
        "Drafts": [
            MessageItem(
                message_id="201",
                sender="Draft",
                subject="Quarterly report (incomplete)",
                preview="The Q4 results show...",
                date="2026/01/11",
                is_read=True,
                is_starred=False,
            ),
        ],
        "Trash": [
            MessageItem(
                message_id="301",
                sender="Old Newsletter",
                subject="[Deleted] Weekly digest",
                preview="This message was deleted...",
                date="2026/01/10",
                is_read=True,
                is_starred=False,
            ),
        ],
        "Spam": [
            MessageItem(
                message_id="401",
                sender="Unknown Sender",
                subject="[SPAM] You've won!",
                preview="Congratulations, you've been selected...",
                date="2026/01/09",
                is_read=True,
                is_starred=False,
            ),
        ],
        "Archive": [
            MessageItem(
                message_id="501",
                sender="HR Department",
                subject="Policy update from last year",
                preview="Please review the updated...",
                date="2025/06/15",
                is_read=True,
                is_starred=False,
            ),
        ],
    }

    messages = folder_messages.get(folder_name, [])
    for message in messages:
        self._message_store.append(message)
```

## Folder Display Conventions

### Sent Folder
- Sender field shows "To: recipient" instead of sender
- All messages typically marked as read

### Drafts Folder
- Sender field shows "Draft"
- Preview shows incomplete content
- No read/unread distinction

### Trash Folder
- Subject may be prefixed with "[Deleted]"
- Messages await permanent deletion
- Empty folder action available via context menu

### Spam Folder
- Subject prefixed with "[SPAM]"
- Messages detected as spam
- Empty folder action available via context menu

### Archive Folder
- Older dates typical
- All messages read
- Long-term storage purpose

## Files

| File | Purpose |
|------|---------|
| `src/client/ui/main_window.py` | Folder view implementation |
| `src/client/models/message.py` | MessageItem data class |

## Future Enhancements
- Real database integration for folder contents
- Folder-specific sorting defaults
- Virtual/smart folders based on filters
- Folder message counts from actual data
