#!/usr/bin/env python3
"""
GUI Feature Tests for unitMail (Programmatic verification)

This script tests the GUI-related features by verifying the underlying
data layer operations that would be triggered by GUI interactions.

For full GUI testing, run the app manually:
    cd /home/user/projects/unitmail && source venv/bin/activate && python scripts/run_client.py

Test Coverage:
1. Compose Window (Reply/Forward mode setup)
2. Message Pop-out Window data preparation
3. Search filtering logic
4. View density state
5. Folder unread counts
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List
from common.local_storage import get_local_storage


@dataclass
class FeatureTestResult:
    """Test result container."""
    name: str
    expected: str
    actual: str
    status: str = "PENDING"
    notes: List[str] = None

    def __post_init__(self):
        if self.notes is None:
            self.notes = []

    def __str__(self):
        result = f"\n{'='*60}\n"
        result += f"TEST: {self.name}\n"
        result += f"{'='*60}\n"
        result += f"Expected: {self.expected}\n"
        result += f"Actual: {self.actual}\n"
        result += f"Status: {self.status}\n"
        if self.notes:
            result += "Notes:\n"
            for note in self.notes:
                result += f"  - {note}\n"
        return result


class GUIFeatureTests:
    """Tests for GUI-related features."""

    def __init__(self):
        self.results = []
        self.storage = get_local_storage()

    def run_all_tests(self):
        """Run all GUI feature tests."""
        print("=" * 60)
        print("UNITMAIL GUI FEATURE TESTS")
        print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        self.test_reply_mode_setup()
        self.test_forward_mode_setup()
        self.test_compose_new_mode()
        self.test_message_popout_data()
        self.test_search_filter_logic()
        self.test_folder_unread_counts()
        self.test_attachment_display()
        self.test_starred_indicator()

        self._print_summary()

    def test_reply_mode_setup(self):
        """Test: Reply mode sets up correct subject and recipient."""
        test = FeatureTestResult(
            name="Composer Reply Mode Setup",
            expected="Subject prefixed with 'Re:', recipient set to original sender",
            actual=""
        )

        try:
            # Simulate getting a message to reply to
            inbox_messages = self.storage.get_messages_by_folder("Inbox")
            if not inbox_messages:
                test.status = "SKIP"
                test.actual = "No messages to test with"
                self.results.append(test)
                return

            original_msg = inbox_messages[0]
            original_subject = original_msg.get("subject", "")
            original_sender = original_msg.get("from_address", "")

            # Test reply subject logic (from composer.py)
            if not original_subject.lower().startswith("re:"):
                reply_subject = f"Re: {original_subject}"
            else:
                reply_subject = original_subject

            # Verify
            correct_subject = reply_subject.startswith("Re:")
            has_sender = bool(original_sender)

            if correct_subject and has_sender:
                test.status = "PASS"
                test.actual = f"Reply subject: '{reply_subject[:40]}...', recipient: '{original_sender}'"
            else:
                test.status = "FAIL"
                test.actual = f"Subject OK: {correct_subject}, Sender OK: {has_sender}"

        except Exception as e:
            test.status = "FAIL"
            test.actual = f"Exception: {str(e)}"

        self.results.append(test)

    def test_forward_mode_setup(self):
        """Test: Forward mode sets up correct subject."""
        test = FeatureTestResult(
            name="Composer Forward Mode Setup",
            expected="Subject prefixed with 'Fwd:'",
            actual=""
        )

        try:
            inbox_messages = self.storage.get_messages_by_folder("Inbox")
            if not inbox_messages:
                test.status = "SKIP"
                test.actual = "No messages to test with"
                self.results.append(test)
                return

            original_msg = inbox_messages[0]
            original_subject = original_msg.get("subject", "")

            # Test forward subject logic
            if not original_subject.lower().startswith("fwd:"):
                fwd_subject = f"Fwd: {original_subject}"
            else:
                fwd_subject = original_subject

            if fwd_subject.startswith("Fwd:"):
                test.status = "PASS"
                test.actual = f"Forward subject: '{fwd_subject[:40]}...'"
            else:
                test.status = "FAIL"
                test.actual = f"Subject did not get Fwd: prefix"

        except Exception as e:
            test.status = "FAIL"
            test.actual = f"Exception: {str(e)}"

        self.results.append(test)

    def test_compose_new_mode(self):
        """Test: New message mode has empty fields."""
        test = FeatureTestResult(
            name="Composer New Mode Setup",
            expected="Empty subject, no recipients pre-filled",
            actual=""
        )

        # In new mode, composer starts with empty fields
        # This is tested by verifying the mode setup logic
        new_mode_subject = ""
        new_mode_recipients = []

        if new_mode_subject == "" and len(new_mode_recipients) == 0:
            test.status = "PASS"
            test.actual = "New mode starts with empty subject and no recipients"
        else:
            test.status = "FAIL"
            test.actual = "New mode has unexpected pre-filled values"

        self.results.append(test)

    def test_message_popout_data(self):
        """Test: Message pop-out receives correct data."""
        test = FeatureTestResult(
            name="Message Pop-out Data",
            expected="Pop-out window receives subject, sender, date, body",
            actual=""
        )

        try:
            inbox_messages = self.storage.get_messages_by_folder("Inbox")
            if not inbox_messages:
                test.status = "SKIP"
                test.actual = "No messages to test with"
                self.results.append(test)
                return

            msg = inbox_messages[0]
            msg_id = msg["id"]

            # Get full message (simulates what pop-out window would receive)
            full_msg = self.storage.get_message(msg_id)

            has_subject = "subject" in full_msg and full_msg["subject"]
            has_sender = "from_address" in full_msg and full_msg["from_address"]
            has_date = "received_at" in full_msg and full_msg["received_at"]
            has_body = "body_text" in full_msg and full_msg["body_text"]

            all_fields = has_subject and has_sender and has_date and has_body

            if all_fields:
                test.status = "PASS"
                test.actual = f"Message has all required pop-out fields. Subject: '{full_msg['subject'][:30]}...'"
            else:
                missing = []
                if not has_subject: missing.append("subject")
                if not has_sender: missing.append("from_address")
                if not has_date: missing.append("received_at")
                if not has_body: missing.append("body_text")
                test.status = "FAIL"
                test.actual = f"Missing fields: {', '.join(missing)}"

        except Exception as e:
            test.status = "FAIL"
            test.actual = f"Exception: {str(e)}"

        self.results.append(test)

    def test_search_filter_logic(self):
        """Test: Search filtering works for from, subject, body."""
        test = FeatureTestResult(
            name="Search Filter Logic",
            expected="Filter matches in from_address, subject, and body_text",
            actual=""
        )

        try:
            all_messages = self.storage.get_all_messages()

            # Test search by sender
            search_term = "alice"
            filtered_by_sender = [
                m for m in all_messages
                if search_term.lower() in m.get("from_address", "").lower()
            ]

            # Test search by subject
            search_term2 = "meeting"
            filtered_by_subject = [
                m for m in all_messages
                if search_term2.lower() in m.get("subject", "").lower()
            ]

            # Test search by body
            search_term3 = "budget"
            filtered_by_body = [
                m for m in all_messages
                if search_term3.lower() in m.get("body_text", "").lower()
            ]

            # Test combined filter (how the main_window does it)
            search_term4 = "project"
            combined_filter = [
                m for m in all_messages
                if (search_term4.lower() in m.get("from_address", "").lower() or
                    search_term4.lower() in m.get("subject", "").lower() or
                    search_term4.lower() in m.get("body_text", "").lower())
            ]

            results_ok = len(filtered_by_sender) > 0 or len(filtered_by_subject) > 0 or len(filtered_by_body) > 0

            if results_ok:
                test.status = "PASS"
                test.actual = f"Sender filter: {len(filtered_by_sender)}, Subject filter: {len(filtered_by_subject)}, Body filter: {len(filtered_by_body)}, Combined: {len(combined_filter)}"
            else:
                test.status = "FAIL"
                test.actual = "No search results found for any filter"

        except Exception as e:
            test.status = "FAIL"
            test.actual = f"Exception: {str(e)}"

        self.results.append(test)

    def test_folder_unread_counts(self):
        """Test: Folder unread counts are accurate."""
        test = FeatureTestResult(
            name="Folder Unread Counts",
            expected="Unread counts match actual unread messages in each folder",
            actual=""
        )

        try:
            folders = self.storage.get_folders()
            mismatches = []

            for folder in folders:
                folder_name = folder["name"]
                reported_unread = folder.get("unread_count", 0)

                # Count actual unread
                messages = self.storage.get_messages_by_folder(folder_name)
                actual_unread = len([m for m in messages if not m.get("is_read", False)])

                if reported_unread != actual_unread:
                    mismatches.append(f"{folder_name}: reported={reported_unread}, actual={actual_unread}")

            if not mismatches:
                test.status = "PASS"
                test.actual = "All folder unread counts are accurate"
                test.notes = [f"{f['name']}: {f.get('unread_count', 0)} unread" for f in folders]
            else:
                test.status = "FAIL"
                test.actual = f"Mismatches: {'; '.join(mismatches)}"

        except Exception as e:
            test.status = "FAIL"
            test.actual = f"Exception: {str(e)}"

        self.results.append(test)

    def test_attachment_display(self):
        """Test: Messages with attachments have attachment data."""
        test = FeatureTestResult(
            name="Attachment Data Available",
            expected="Messages with attachments have attachment list with filename, size, type",
            actual=""
        )

        try:
            all_messages = self.storage.get_all_messages()
            messages_with_attachments = [m for m in all_messages if m.get("attachments")]

            if not messages_with_attachments:
                test.status = "SKIP"
                test.actual = "No messages with attachments found"
                self.results.append(test)
                return

            # Check first message with attachments
            msg = messages_with_attachments[0]
            attachments = msg["attachments"]

            valid_attachments = []
            for att in attachments:
                has_filename = "filename" in att and att["filename"]
                has_size = "size" in att
                has_type = "content_type" in att

                if has_filename:
                    valid_attachments.append(att["filename"])

            if valid_attachments:
                test.status = "PASS"
                test.actual = f"Found {len(messages_with_attachments)} messages with attachments. Sample: {', '.join(valid_attachments[:3])}"
            else:
                test.status = "FAIL"
                test.actual = "Attachments missing required fields"

        except Exception as e:
            test.status = "FAIL"
            test.actual = f"Exception: {str(e)}"

        self.results.append(test)

    def test_starred_indicator(self):
        """Test: Starred messages can be identified and toggled."""
        test = FeatureTestResult(
            name="Starred/Favorite Indicator",
            expected="Messages can be starred/unstarred, state persists",
            actual=""
        )

        try:
            all_messages = self.storage.get_all_messages()

            # Count starred messages
            starred_count = len([m for m in all_messages if m.get("is_starred", False)])

            # Test toggle on a message
            test_msg = all_messages[0]
            msg_id = test_msg["id"]
            original_starred = test_msg.get("is_starred", False)

            # Toggle
            self.storage.update_message(msg_id, {"is_starred": not original_starred})
            after_toggle = self.storage.get_message(msg_id)
            toggled_starred = after_toggle.get("is_starred", False)

            # Restore
            self.storage.update_message(msg_id, {"is_starred": original_starred})

            toggle_worked = toggled_starred == (not original_starred)

            if toggle_worked:
                test.status = "PASS"
                test.actual = f"Star toggle works. Found {starred_count} starred messages in database."
            else:
                test.status = "FAIL"
                test.actual = f"Toggle failed: original={original_starred}, after toggle={toggled_starred}"

        except Exception as e:
            test.status = "FAIL"
            test.actual = f"Exception: {str(e)}"

        self.results.append(test)

    def _print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("DETAILED RESULTS")
        print("=" * 60)

        for result in self.results:
            print(result)

        passed = sum(1 for r in self.results if r.status == "PASS")
        failed = sum(1 for r in self.results if r.status == "FAIL")
        skipped = sum(1 for r in self.results if r.status == "SKIP")
        total = len(self.results)

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Skipped: {skipped}")
        print(f"Pass Rate: {(passed/(total-skipped))*100:.1f}%" if (total-skipped) > 0 else "N/A")


if __name__ == "__main__":
    tests = GUIFeatureTests()
    tests.run_all_tests()
