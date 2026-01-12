# Skill: GUI Theming and View Modes

## What This Skill Does
Implements GUI styling with sharp corners design, multiple email view themes, and intuitive settings UI.

## Design Principles

### No Rounded Corners
All UI elements have sharp, square edges:
- Windows, dialogs, popovers
- Buttons, entries, checkboxes
- Badges, scrollbars, switches
- Message rows, folder items

CSS applies `border-radius: 0` globally.

## Email View Themes

Four view themes for message list density:

| Theme | Description | Row Height |
|-------|-------------|------------|
| **standard** | Balanced spacing (default) | ~48px |
| **compact** | Dense, no preview | ~32px |
| **comfortable** | Spacious, larger fonts | ~80px |
| **minimal** | Single line: time, from, subject | ~24px |

### Theme Classes
```css
.view-theme-standard
.view-theme-compact
.view-theme-comfortable
.view-theme-minimal
```

## Usage

### Python API
```python
from client.ui.view_theme import (
    ViewTheme,
    ViewThemeManager,
    ViewThemeSelector,
    get_view_theme_manager,
)

# Get manager singleton
manager = get_view_theme_manager()

# Set theme
manager.set_theme(ViewTheme.COMPACT)

# Get current theme
current = manager.current_theme

# Register widget for theme updates
manager.register_widget(message_list_container)

# Listen for changes
manager.connect("theme-changed", on_theme_changed)
```

### Adding Theme Selector to Settings
```python
from client.ui.view_theme import ViewThemeSelector

# Add to settings dialog
theme_selector = ViewThemeSelector()
settings_box.append(theme_selector)
```

## Files

| File | Purpose |
|------|---------|
| `src/client/ui/styles.css` | CSS with theme definitions |
| `src/client/ui/view_theme.py` | Theme manager and selector widget |

## Theme Comparison

### Standard (Default)
- Shows: avatar, from, subject, preview, date
- Best for: General use

### Compact
- Shows: small avatar, from, subject, date
- Hides: preview
- Best for: Power users, large mailboxes

### Comfortable
- Shows: large avatar, from, subject, extended preview, date
- Best for: Casual reading, accessibility

### Minimal
- Shows: single line with time | from | subject
- Hides: avatar, preview
- Best for: Maximum density, keyboard navigation

## Settings UI

### Access
- Gear icon button in header bar (direct access)
- Menu > Settings
- Keyboard: Ctrl+,

### Appearance Page
Visual radio button selectors for:

**Color Scheme:**
- System (follows OS preference)
- Light (always light)
- Dark (always dark)

**Message List Density:**
- Standard (default)
- Compact
- Comfortable
- Minimal

Each option shows:
- Icon prefix
- Title
- Descriptive subtitle
- Radio button for selection
