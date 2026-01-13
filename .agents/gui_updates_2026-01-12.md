# GUI Updates - January 12, 2026

## Summary
Major GUI improvements to the unitMail GTK4 email client, enhancing usability and implementing standard email client features.

## Changes Implemented

### 1. View Density Simplified
- **Removed**: Compact view (no longer available)
- **Retained**: Standard and Minimal views only
- **Fixed**: View density now persists correctly across sessions
- **Fixed**: View applies immediately on selection (no refresh needed)

### 2. Minimal View Improvements
- Starred messages indicated by **gold left border** (3px width)
- Checkbox and star button hidden in minimal view
- Tighter row spacing (26px height)
- Columnar layout: Date | From | Subject

### 3. Context Menus Added
**Message Context Menu** (right-click on message):
- Mark as Read/Unread
- Add/Remove Star
- Reply, Reply All, Forward
- Move to Archive/Spam/Trash
- Delete Message

**Folder Context Menu** (right-click on folder):
- Mark All as Read
- Refresh
- Empty Folder (Trash/Spam only)

### 4. Preview Header Actions
Action buttons added to message preview:
- Reply, Reply All, Forward
- Archive, Delete

### 5. Folder-Specific Views
Each folder now displays appropriate content:
- **Inbox**: Received messages
- **Sent**: Shows "To: recipient" format
- **Drafts**: Shows "Draft" as sender
- **Trash**: Deleted messages with [Deleted] prefix
- **Spam**: Spam messages with [SPAM] prefix
- **Archive**: Older archived messages

### 6. Export Feature
Under Advanced settings:
- Export emails to mbox format (universal)
- Export emails to JSON format
- File dialog for choosing export location

## Files Modified

| File | Changes |
|------|---------|
| `src/client/ui/main_window.py` | Context menus, folder views, action handlers |
| `src/client/ui/settings.py` | Removed compact, added export feature |
| `src/client/ui/styles.css` | Starred border, hidden elements in minimal |
| `src/client/ui/view_theme.py` | Removed COMPACT enum value |
| `src/client/services/settings_service.py` | Added view_density persistence |

## Commits
- `d180e2e` - Add context menus, folder views, and GUI improvements
- `dc8f138` - Update minimal view screenshot

## Testing Notes
- Verified view persistence across app restart
- Tested context menus on messages and folders
- Confirmed folder switching loads appropriate content
- Screenshot updated: `screenshots/example_minimal_message_view.png`

## Skills Documentation Updated
- `skills/012_gui_theming.md` - Updated for two-view system
- `skills/013_context_menus.md` - New: context menu documentation
- `skills/014_folder_views.md` - New: folder view documentation
