# Skill: Context Menus and Message Actions

## What This Skill Does
Implements right-click context menus for messages and folders, plus action buttons in the message preview header.

## Message Context Menu

Right-click on any message in the list to access:

### Read Status
- Mark as Read
- Mark as Unread

### Star/Favorite
- Add Star
- Remove Star

### Actions
- Reply
- Reply All
- Forward

### Move To
- Move to Archive
- Move to Spam
- Move to Trash

### Delete
- Delete Message

## Folder Context Menu

Right-click on any folder in the sidebar to access:

### Standard Folders (Inbox, Sent, etc.)
- Mark All as Read
- Refresh
- Empty Folder (for Trash/Spam only)

### Custom Folders
- Rename Folder
- Delete Folder

## Preview Header Actions

The message preview pane includes action buttons:

| Button | Icon | Action |
|--------|------|--------|
| Reply | `mail-reply-sender` | Reply to sender |
| Reply All | `mail-reply-all` | Reply to all |
| Forward | `mail-forward` | Forward message |
| Archive | `folder-symbolic` | Move to Archive |
| Delete | `user-trash-symbolic` | Move to Trash |

## Implementation

### Message Context Menu Setup
```python
def _setup_message_context_menu(self, list_view: Gtk.ListView) -> None:
    menu = Gio.Menu()

    # Read status section
    read_section = Gio.Menu()
    read_section.append("Mark as Read", "win.mark-read")
    read_section.append("Mark as Unread", "win.mark-unread")
    menu.append_section(None, read_section)

    # Create popover
    self._message_context_menu = Gtk.PopoverMenu(
        menu_model=menu,
        has_arrow=False
    )

    # Add right-click gesture
    click_gesture = Gtk.GestureClick(button=3)
    click_gesture.connect("pressed", self._on_message_right_click)
    list_view.add_controller(click_gesture)
```

### Folder Context Menu Setup
```python
def _setup_folder_context_menu(self, list_view: Gtk.ListView) -> None:
    menu = Gio.Menu()

    actions_section = Gio.Menu()
    actions_section.append("Mark All as Read", "win.folder-mark-all-read")
    actions_section.append("Refresh", "win.folder-refresh")
    menu.append_section(None, actions_section)

    self._folder_context_menu = Gtk.PopoverMenu(
        menu_model=menu,
        has_arrow=False
    )
```

### Action Handlers
```python
def _on_mark_read(self, action: Gio.SimpleAction, param: None) -> None:
    if self._context_menu_message:
        item = self._context_menu_message
        item.is_read = True
        logging.info(f"Marked message as read: {item.subject}")

def _on_delete_message(self, action: Gio.SimpleAction, param: None) -> None:
    if self._context_menu_message:
        item = self._context_menu_message
        logging.info(f"Deleting message: {item.subject}")
        # Remove from store or move to trash
```

## Files

| File | Purpose |
|------|---------|
| `src/client/ui/main_window.py` | Context menu setup and handlers |
| `src/client/ui/styles.css` | Menu styling (sharp corners) |

## GTK4 Notes

- Use `Gio.Menu` for menu model (declarative)
- Use `Gtk.PopoverMenu` for display
- Use `Gtk.GestureClick` with `button=3` for right-click
- Actions registered with `win.` prefix for window scope
- `has_arrow=False` for context menu style
