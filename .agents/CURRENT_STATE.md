# unitMail - Current Development State

*Last updated: 2026-01-12*

## Project Overview
unitMail is a GTK4/libadwaita email client with:
- Sharp-corner design (no rounded corners)
- Multiple view density options (Standard, Minimal)
- Full email client functionality
- SQLite local storage with FTS5 full-text search

## Architecture

### Client (`src/client/`)
- **UI Layer**: GTK4/libadwaita with PyGObject
- **Services**: Settings, email operations
- **Models**: Message, folder data classes

### Gateway (`src/gateway/`)
- SMTP handling
- REST API
- DNS resolution
- Cryptographic operations

### Common (`src/common/`)
- Shared utilities and types

## Key UI Components

### Main Window (`src/client/ui/main_window.py`)
- Three-pane layout: Folders | Messages | Preview
- Folder list with selection handling
- Message list with context menus
- Preview pane with action buttons

### View Themes (`src/client/ui/view_theme.py`)
- `ViewTheme` enum: STANDARD, MINIMAL
- `ViewThemeManager` singleton for state
- `ViewThemeSelector` widget for settings

### Settings (`src/client/ui/settings.py`)
- Appearance tab: Theme, density selection
- Advanced tab: Export feature
- Uses Adw.PreferencesWindow

## Recent Changes (Jan 12, 2026)
See: `.agents/gui_updates_2026-01-12.md`

## Design Conventions

### CSS Styling
- No rounded corners (`border-radius: 0` globally)
- Theme classes: `.view-theme-standard`, `.view-theme-minimal`
- GTK4 limitations: No flexbox, no max-width, use margin-left/right

### Message Row
- Standard: Full layout with avatar, preview
- Minimal: Single line, starred = gold left border

### Context Menus
- Use `Gio.Menu` with `Gtk.PopoverMenu`
- Right-click via `Gtk.GestureClick(button=3)`
- Actions prefixed with `win.` for window scope

## Development Guidelines

### Running the Client
```bash
cd /home/user/projects/unitmail
python -m src.client.main
```

### Testing
```bash
pytest tests/
```

### Skills Reference
See `skills/` directory for detailed documentation on each component.
