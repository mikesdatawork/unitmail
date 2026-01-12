# Skill: GTK 4 Client Application

## What This Skill Does
Creates the complete GTK 4 desktop client for unitMail using PyGObject and libadwaita.

## Components

### application.py
- `UnitMailApplication` - Gtk.Application subclass
- Single instance handling
- Application actions (quit, compose, settings)
- Dark/light theme switching
- CSS loading

### main_window.py
- Three-pane layout (folders, messages, preview)
- Header bar with compose, refresh, search
- Status bar with connection info
- Keyboard shortcuts (Ctrl+N, j/k, Delete)

### composer.py
- `ComposerWindow` - Email composition
- To/CC/BCC with auto-complete
- Rich text formatting toolbar
- Attachment panel with drag-drop
- Reply/Forward modes

### reader.py
- `MessageViewer` - Email display
- HTML rendering (WebKit, sanitized)
- Plain text fallback
- External content blocking
- Action toolbar

### Widgets
- `RecipientEntry` - Multi-recipient with chips
- `AttachmentPanel` - Add/remove attachments
- `MessageHeader` - Header display with avatars
- `AttachmentList` - View/download attachments

## Usage
```bash
python scripts/run_client.py
python scripts/run_client.py --debug
```

## Shortcuts
| Key | Action |
|-----|--------|
| Ctrl+N | Compose |
| Ctrl+Q | Quit |
| Delete | Delete message |
| j/k | Navigate messages |
