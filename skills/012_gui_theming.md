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

Two view themes for message list density:

| Theme | Description | Row Height |
|-------|-------------|------------|
| **standard** | Balanced spacing (default) | ~48px |
| **minimal** | Single line: date \| from \| subject | ~26px |

### Theme Classes
```css
.view-theme-standard
.view-theme-minimal
```

### Minimal View Features
- Single line display: `2026/12/01   friend@domain.com   what do you want for lunch today?`
- Starred/favorite messages indicated by gold left border (3px)
- Checkbox and star button hidden via CSS (opacity: 0)
- Tighter row spacing for maximum density

### Starred Message Indicator (Minimal View)
```css
.view-theme-minimal .message-row.starred {
    border-left: 3px solid @warning_color;
}

.view-theme-minimal .message-row:not(.starred) {
    border-left: 3px solid transparent;
}
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
manager.set_theme(ViewTheme.MINIMAL)

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
- Shows: avatar, from, subject, preview, date, star button
- Best for: General use

### Minimal
- Shows: single line with date | from | subject
- Starred: Gold left border indicator
- Hides: avatar, preview, checkbox, star button
- Format: `2026/12/01   user@example.com   Email subject here`
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
- Minimal

Settings persist automatically and apply immediately on selection.

### Advanced Settings
- Email export feature (mbox and JSON formats)
- Export location selection via file dialog
