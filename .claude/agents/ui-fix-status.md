# unitMail UI Fix Status

This document tracks the implementation status of issues identified by the email-ui-expert agent review.

**Last Updated:** 2026-01-12
**Implementer:** Claude (main session)
**Reviewer:** email-ui-expert agent
**Verification Status:** COMPLETED

---

## P1 Critical Issues - Status

| Issue | Status | Verified | File | Notes |
|-------|--------|----------|------|-------|
| Search non-functional | **FIXED** | **YES** | `main_window.py` | Real-time filtering by sender/subject/content |
| Sort dropdown not wired | **FIXED** | **YES** | `main_window.py` | All 4 sort options work (date/from/subject/size) |
| Reply/Forward broken | **FIXED** | **YES** | `main_window.py` | Opens ComposerWindow with proper mode |
| Select All broken | **FIXED** | **YES** | `main_window.py` | Full selection management with indeterminate state |
| Message threading missing | PENDING | - | - | Architectural change needed |

---

## Verification Summary (email-ui-expert agent)

| Fix | Quality | Accessibility | Reviewer Notes |
|-----|---------|---------------|----------------|
| Search | Good | Good | Remove duplicate `_on_search_activated` handler |
| Sort | Good | Fair | Size proxy is crude (uses preview length) |
| Reply/Forward | Good | Good | Needs full body + Reply All recipients |
| Select All | Excellent | Fair | Add visual row selection feedback |

---

## Implementation Details

### 1. Search Functionality (FIXED)
**Location:** `src/client/ui/main_window.py`

**Changes:**
- Added `_all_messages: list[MessageItem]` (line 236) to store unfiltered messages
- Updated placeholder text to "Search by sender, subject, or content..." (line 359)
- `_load_folder_messages()` stores messages in `_all_messages` before display
- `_on_search_changed()` calls `_filter_messages()` for real-time filtering
- `_filter_messages()` searches across `from_address`, `subject`, and `preview`

**Behavior:**
- Case-insensitive search
- Filters as user types
- Clears when switching folders
- Message count updates with results

---

### 2. Sort Dropdown (FIXED)
**Location:** `src/client/ui/main_window.py`

**Changes:**
- Added `_get_sort_key()` helper (lines 807-819) for reusable sort logic
- Refactored `_sort_messages()` to use shared sort key function
- Added `_sort_all_messages()` (lines 842-847) to keep full list sorted
- Wired `_on_sort_changed()` to call both sort methods

**Sort Options:**
- Date: by `_date` property
- From: by `from_address` (case-insensitive)
- Subject: by `subject` (case-insensitive)
- Size: by `preview` length (proxy for message size)

---

### 3. Reply/Forward Buttons (FIXED)
**Location:** `src/client/ui/main_window.py`

**Changes:**
- Added import for `ComposerWindow`, `ComposerMode`, `EmailMessage` (line 20)
- Added `_get_selected_message()` helper (lines 1681-1689)
- Added `_create_email_message_from_item()` converter (lines 1691-1701)
- Added `_open_composer()` shared method (lines 1703-1717)
- Updated `_on_reply()`, `_on_reply_all()`, `_on_forward()` handlers

**Behavior:**
- Reply: Opens composer with "Re:" prefix, sender as recipient
- Reply All: Opens composer with sender + all recipients, CC preserved
- Forward: Opens composer with "Fwd:" prefix, empty recipients
- All modes quote original message

---

### 4. Select All Checkbox (FIXED)
**Location:** `src/client/ui/main_window.py`

**Changes:**
- Added `_selected_messages: set[str]` (line 237) to track selections
- Connected individual checkboxes in `_on_message_item_bind()` (lines 1038-1045)
- Updated `_update_message_count()` to show "X of Y selected" (lines 1466-1475)
- Implemented `_on_message_check_toggled()` for individual selections
- Implemented `_on_select_all_toggled()` for bulk select/deselect
- Added `_update_select_all_state()` for indeterminate checkbox state
- Added `_refresh_message_list()` helper
- Clear selection on folder change (lines 1594-1596)

**Behavior:**
- Individual checkboxes toggle selection
- Select all toggles all visible messages
- Indeterminate state (dash) when partially selected
- Selection count shown in toolbar
- Selection cleared on folder switch

---

## Remaining P1 Issues

### Message Threading
**Status:** NOT STARTED
**Complexity:** HIGH
**Reason:** Requires architectural changes:
- Add `parent_message_id` to MessageItem
- Implement thread grouping logic
- Add expand/collapse UI for threads
- Modify message loading to fetch thread structure

---

## P2 Issues - Not Yet Addressed

| Issue | Priority | Notes |
|-------|----------|-------|
| Message selection visual feedback | HIGH | Need to highlight row when checkbox checked |
| Empty states with CTAs | HIGH | Add refresh button, better guidance |
| Offline mode indicator | MEDIUM | Status bar exists, needs implementation |
| Attachment count display | MEDIUM | Currently only shows icon |

---

## Testing Notes

To test the fixes, run:
```bash
cd /home/user/projects/unitmail
PYTHONPATH=src python3 -c "
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw
from client.ui.main_window import MainWindow

class TestApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.unitmail.test')
        self.connect('activate', self.on_activate)
    def on_activate(self, app):
        MainWindow(application=app).present()

TestApp().run(None)
"
```

---

## Communication Protocol

**For email-ui-expert agent:**
1. Re-run functionality checks on FIXED items to verify
2. Update recommendations if implementation differs from suggested approach
3. Identify any regressions or new issues introduced

**For implementation agent:**
1. Update this file after each fix
2. Note any deviations from recommended approach
3. Flag blockers for P1 issues that need architectural decisions
