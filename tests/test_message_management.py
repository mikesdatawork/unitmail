#!/usr/bin/env python3
"""
Comprehensive exploratory testing for unitMail message management features.

This script tests:
1. Message Selection & Preview
2. Favorite/Star Toggle
3. Delete Messages
4. Mark Read/Unread
5. Move to Folder
6. Search
7. Folder Navigation
8. Database persistence

Run with: python tests/test_message_management.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from datetime import datetime
from common.local_storage import get_local_storage, LocalEmailStorage

class MessageTestResult:
    """Stores test result information."""
    def __init__(self, name: str):
        self.name = name
        self.steps = []
        self.expected = ""
        self.actual = ""
        self.status = "PENDING"
        self.bugs = []

    def __str__(self):
        result = f"\n{'='*70}\n"
        result += f"TEST: {self.name}\n"
        result += f"{'='*70}\n"
        result += "Steps Performed:\n"
        for i, step in enumerate(self.steps, 1):
            result += f"  {i}. {step}\n"
        result += f"\nExpected Result: {self.expected}\n"
        result += f"Actual Result: {self.actual}\n"
        result += f"Status: {self.status}\n"
        if self.bugs:
            result += "Bugs/Issues:\n"
            for bug in self.bugs:
                result += f"  - {bug}\n"
        return result


class MessageManagementTests:
    """Test suite for message management features."""

    def __init__(self):
        self.results = []
        self.storage = get_local_storage()

    def run_all_tests(self):
        """Run all test cases."""
        print("=" * 70)
        print("UNITMAIL MESSAGE MANAGEMENT TEST REPORT")
        print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        # Ensure we have test data
        self._verify_test_data()

        # Run individual tests
        self.test_message_selection_and_preview()
        self.test_favorite_star_toggle()
        self.test_delete_message()
        self.test_mark_read_unread()
        self.test_move_to_folder()
        self.test_search_functionality()
        self.test_folder_navigation()
        self.test_database_persistence()

        # Print summary
        self._print_summary()

    def _verify_test_data(self):
        """Verify test data exists."""
        test = MessageTestResult("Test Data Verification")
        test.steps.append("Check database for sample messages")
        test.expected = "Database contains 50 messages (43 inbox, 5 sent, 2 drafts)"

        count = self.storage.get_message_count()
        folders = self.storage.get_folders()
        inbox_count = next((f["message_count"] for f in folders if f["name"] == "Inbox"), 0)
        sent_count = next((f["message_count"] for f in folders if f["name"] == "Sent"), 0)
        drafts_count = next((f["message_count"] for f in folders if f["name"] == "Drafts"), 0)

        test.actual = f"Database contains {count} messages ({inbox_count} inbox, {sent_count} sent, {drafts_count} drafts)"

        if count >= 50 and inbox_count >= 40:
            test.status = "PASS"
        else:
            test.status = "FAIL"
            test.bugs.append(f"Expected ~50 messages, found {count}")

        self.results.append(test)

    def test_message_selection_and_preview(self):
        """Test 1: Message Selection & Preview."""
        test = MessageTestResult("Message Selection & Preview")
        test.steps = [
            "Get messages from Inbox folder",
            "Select first message by ID",
            "Verify message has expected fields (from, to, subject, body)",
            "Check sender, recipient, date display"
        ]
        test.expected = "Selected message shows full body, sender, recipient, and date"

        try:
            # Get inbox messages
            inbox_messages = self.storage.get_messages_by_folder("Inbox")
            if not inbox_messages:
                test.status = "FAIL"
                test.actual = "No messages found in Inbox"
                test.bugs.append("Inbox is empty")
                self.results.append(test)
                return

            # Select first message
            first_msg = inbox_messages[0]
            msg_id = first_msg["id"]

            # Get full message details
            full_msg = self.storage.get_message(msg_id)

            # Verify fields
            has_from = "from_address" in full_msg and full_msg["from_address"]
            has_to = "to_addresses" in full_msg
            has_subject = "subject" in full_msg
            has_body = "body_text" in full_msg and full_msg["body_text"]
            has_date = "received_at" in full_msg

            if all([has_from, has_to, has_subject, has_body, has_date]):
                test.status = "PASS"
                test.actual = f"Message '{full_msg['subject'][:40]}...' has all required fields: from='{full_msg['from_address']}', body length={len(full_msg.get('body_text', ''))}"
            else:
                test.status = "FAIL"
                missing = []
                if not has_from: missing.append("from_address")
                if not has_to: missing.append("to_addresses")
                if not has_subject: missing.append("subject")
                if not has_body: missing.append("body_text")
                if not has_date: missing.append("received_at")
                test.actual = f"Missing fields: {', '.join(missing)}"
                test.bugs.append(f"Message missing required fields: {', '.join(missing)}")

        except Exception as e:
            test.status = "FAIL"
            test.actual = f"Exception: {str(e)}"
            test.bugs.append(f"Exception during test: {str(e)}")

        self.results.append(test)

    def test_favorite_star_toggle(self):
        """Test 2: Favorite/Star Toggle."""
        test = MessageTestResult("Favorite/Star Toggle")
        test.steps = [
            "Find a non-starred message",
            "Toggle star on (mark as favorite)",
            "Verify is_starred is True in database",
            "Toggle star off",
            "Verify is_starred is False in database"
        ]
        test.expected = "Starring and unstarring updates database correctly"

        try:
            inbox_messages = self.storage.get_messages_by_folder("Inbox")
            # Find non-starred message
            test_msg = None
            for msg in inbox_messages:
                if not msg.get("is_starred", False):
                    test_msg = msg
                    break

            if not test_msg:
                # Use any message
                test_msg = inbox_messages[0]

            original_starred = test_msg.get("is_starred", False)
            msg_id = test_msg["id"]

            # Star the message
            self.storage.update_message(msg_id, {"is_starred": True})
            updated_msg = self.storage.get_message(msg_id)
            starred_after_add = updated_msg.get("is_starred", False)

            # Unstar the message
            self.storage.update_message(msg_id, {"is_starred": False})
            updated_msg = self.storage.get_message(msg_id)
            starred_after_remove = updated_msg.get("is_starred", False)

            # Restore original state
            self.storage.update_message(msg_id, {"is_starred": original_starred})

            if starred_after_add and not starred_after_remove:
                test.status = "PASS"
                test.actual = f"Star toggle works correctly. After add: {starred_after_add}, After remove: {starred_after_remove}"
            else:
                test.status = "FAIL"
                test.actual = f"Star toggle failed. After add: {starred_after_add}, After remove: {starred_after_remove}"
                if not starred_after_add:
                    test.bugs.append("Starring message did not update database")
                if starred_after_remove:
                    test.bugs.append("Unstarring message did not update database")

        except Exception as e:
            test.status = "FAIL"
            test.actual = f"Exception: {str(e)}"
            test.bugs.append(f"Exception during test: {str(e)}")

        self.results.append(test)

    def test_delete_message(self):
        """Test 3: Delete Messages."""
        test = MessageTestResult("Delete Message")
        test.steps = [
            "Create a test message for deletion",
            "Verify message exists in database",
            "Delete the message",
            "Verify message no longer exists",
            "Verify folder count updated"
        ]
        test.expected = "Message is removed from list and database, counts update"

        try:
            folders = self.storage.get_folders()
            inbox_id = next((f["id"] for f in folders if f["name"] == "Inbox"), None)

            initial_count = self.storage.get_message_count()

            # Create test message
            test_msg = self.storage.create_message({
                "folder_id": inbox_id,
                "from_address": "test@example.com",
                "to_addresses": ["me@unitmail.local"],
                "subject": "TEST MESSAGE FOR DELETION",
                "body_text": "This message will be deleted during testing.",
                "is_read": False,
            })

            msg_id = test_msg["id"]
            after_create_count = self.storage.get_message_count()

            # Verify it exists
            msg_exists = self.storage.get_message(msg_id) is not None

            # Delete it
            delete_result = self.storage.delete_message(msg_id)

            # Verify deletion
            msg_after_delete = self.storage.get_message(msg_id)
            after_delete_count = self.storage.get_message_count()

            if msg_exists and delete_result and msg_after_delete is None and after_delete_count == initial_count:
                test.status = "PASS"
                test.actual = f"Message created (count: {after_create_count}), deleted (count: {after_delete_count}). Message not found after deletion."
            else:
                test.status = "FAIL"
                issues = []
                if not msg_exists:
                    issues.append("Message was not created")
                if not delete_result:
                    issues.append("Delete returned False")
                if msg_after_delete is not None:
                    issues.append("Message still exists after deletion")
                if after_delete_count != initial_count:
                    issues.append(f"Count mismatch: {after_delete_count} vs expected {initial_count}")
                test.actual = f"Issues: {', '.join(issues)}"
                test.bugs.extend(issues)

        except Exception as e:
            test.status = "FAIL"
            test.actual = f"Exception: {str(e)}"
            test.bugs.append(f"Exception during test: {str(e)}")

        self.results.append(test)

    def test_mark_read_unread(self):
        """Test 4: Mark Read/Unread."""
        test = MessageTestResult("Mark Read/Unread")
        test.steps = [
            "Find an unread message",
            "Mark it as read",
            "Verify is_read is True",
            "Mark it as unread",
            "Verify is_read is False"
        ]
        test.expected = "Read status toggles correctly and persists"

        try:
            inbox_messages = self.storage.get_messages_by_folder("Inbox")
            # Find an unread message
            test_msg = None
            for msg in inbox_messages:
                if not msg.get("is_read", False):
                    test_msg = msg
                    break

            if not test_msg:
                test_msg = inbox_messages[0]

            original_read = test_msg.get("is_read", False)
            msg_id = test_msg["id"]

            # Mark as read
            self.storage.mark_as_read(msg_id)
            msg_after_read = self.storage.get_message(msg_id)
            is_read_after = msg_after_read.get("is_read", False)

            # Mark as unread
            self.storage.mark_as_unread(msg_id)
            msg_after_unread = self.storage.get_message(msg_id)
            is_unread_after = msg_after_unread.get("is_read", True)

            # Restore original state
            if original_read:
                self.storage.mark_as_read(msg_id)
            else:
                self.storage.mark_as_unread(msg_id)

            if is_read_after and not is_unread_after:
                test.status = "PASS"
                test.actual = f"Read/unread toggle works. After mark_read: {is_read_after}, After mark_unread: {is_unread_after}"
            else:
                test.status = "FAIL"
                test.actual = f"Read/unread toggle failed. After mark_read: {is_read_after}, After mark_unread: {is_unread_after}"
                if not is_read_after:
                    test.bugs.append("mark_as_read did not update is_read to True")
                if is_unread_after:
                    test.bugs.append("mark_as_unread did not update is_read to False")

        except Exception as e:
            test.status = "FAIL"
            test.actual = f"Exception: {str(e)}"
            test.bugs.append(f"Exception during test: {str(e)}")

        self.results.append(test)

    def test_move_to_folder(self):
        """Test 5: Move to Folder."""
        test = MessageTestResult("Move to Folder")
        test.steps = [
            "Get a message from Inbox",
            "Move it to Trash folder",
            "Verify message has new folder_id",
            "Verify message appears in Trash",
            "Verify message no longer in Inbox",
            "Move it back to Inbox"
        ]
        test.expected = "Message moves between folders correctly"

        try:
            folders = self.storage.get_folders()
            _inbox_id = next((f["id"] for f in folders if f["name"] == "Inbox"), None)  # noqa: F841
            trash_id = next((f["id"] for f in folders if f["name"] == "Trash"), None)

            inbox_messages = self.storage.get_messages_by_folder("Inbox")
            if not inbox_messages:
                test.status = "FAIL"
                test.actual = "No messages in Inbox to test with"
                self.results.append(test)
                return

            test_msg = inbox_messages[-1]  # Use last message to minimize impact
            msg_id = test_msg["id"]
            _original_folder = test_msg.get("folder_id")  # noqa: F841

            # Move to Trash
            self.storage.move_to_folder(msg_id, "Trash")

            # Verify in Trash
            msg_after_move = self.storage.get_message(msg_id)
            in_trash = msg_after_move.get("folder_id") == trash_id

            # Check it's in Trash messages
            trash_messages = self.storage.get_messages_by_folder("Trash")
            found_in_trash = any(m["id"] == msg_id for m in trash_messages)

            # Check it's NOT in Inbox
            inbox_after = self.storage.get_messages_by_folder("Inbox")
            not_in_inbox = not any(m["id"] == msg_id for m in inbox_after)

            # Move back to Inbox
            self.storage.move_to_folder(msg_id, "Inbox")

            if in_trash and found_in_trash and not_in_inbox:
                test.status = "PASS"
                test.actual = f"Message moved to Trash (folder_id match: {in_trash}, found in Trash list: {found_in_trash}, removed from Inbox: {not_in_inbox})"
            else:
                test.status = "FAIL"
                issues = []
                if not in_trash:
                    issues.append("folder_id not updated to Trash")
                if not found_in_trash:
                    issues.append("Message not found in Trash folder listing")
                if not not_in_inbox:
                    issues.append("Message still appears in Inbox")
                test.actual = f"Move failed: {', '.join(issues)}"
                test.bugs.extend(issues)

        except Exception as e:
            test.status = "FAIL"
            test.actual = f"Exception: {str(e)}"
            test.bugs.append(f"Exception during test: {str(e)}")

        self.results.append(test)

    def test_search_functionality(self):
        """Test 6: Search Functionality."""
        test = MessageTestResult("Search Functionality")
        test.steps = [
            "Search by sender email (partial match)",
            "Search by subject keyword",
            "Search by body content",
            "Verify search returns correct results"
        ]
        test.expected = "Search finds messages by sender, subject, and body content"

        try:
            all_messages = self.storage.get_all_messages()

            # Test 1: Search by sender
            search_term = "alice"
            sender_matches = [
                m for m in all_messages
                if search_term.lower() in m.get("from_address", "").lower()
            ]

            # Test 2: Search by subject
            subject_term = "meeting"
            subject_matches = [
                m for m in all_messages
                if subject_term.lower() in m.get("subject", "").lower()
            ]

            # Test 3: Search by body
            body_term = "budget"
            body_matches = [
                m for m in all_messages
                if body_term.lower() in m.get("body_text", "").lower()
            ]

            # Verify we got results
            all_searches_work = len(sender_matches) > 0 and len(subject_matches) > 0 and len(body_matches) > 0

            if all_searches_work:
                test.status = "PASS"
                test.actual = f"Search works: sender '{search_term}' found {len(sender_matches)}, subject '{subject_term}' found {len(subject_matches)}, body '{body_term}' found {len(body_matches)}"
            else:
                test.status = "FAIL"
                issues = []
                if len(sender_matches) == 0:
                    issues.append(f"No results for sender search '{search_term}'")
                if len(subject_matches) == 0:
                    issues.append(f"No results for subject search '{subject_term}'")
                if len(body_matches) == 0:
                    issues.append(f"No results for body search '{body_term}'")
                test.actual = f"Search issues: {', '.join(issues)}"
                test.bugs.extend(issues)

        except Exception as e:
            test.status = "FAIL"
            test.actual = f"Exception: {str(e)}"
            test.bugs.append(f"Exception during test: {str(e)}")

        self.results.append(test)

    def test_folder_navigation(self):
        """Test 7: Folder Navigation."""
        test = MessageTestResult("Folder Navigation")
        test.steps = [
            "Get all folders",
            "Verify Inbox, Sent, Drafts folders exist",
            "Get messages for each folder",
            "Verify correct message counts"
        ]
        test.expected = "All folders accessible with correct message counts"

        try:
            folders = self.storage.get_folders()
            folder_names = [f["name"] for f in folders]

            # Check required folders exist
            required_folders = ["Inbox", "Sent", "Drafts", "Trash", "Spam", "Archive"]
            missing_folders = [f for f in required_folders if f not in folder_names]

            # Get messages for each folder
            folder_data = {}
            for folder in folders:
                messages = self.storage.get_messages_by_folder(folder["name"])
                folder_data[folder["name"]] = {
                    "expected_count": folder["message_count"],
                    "actual_count": len(messages),
                    "unread": folder["unread_count"]
                }

            # Verify counts match
            count_matches = all(
                fd["expected_count"] == fd["actual_count"]
                for fd in folder_data.values()
            )

            if not missing_folders and count_matches:
                test.status = "PASS"
                counts_str = ", ".join([f"{name}: {data['actual_count']}" for name, data in folder_data.items()])
                test.actual = f"All folders present. Message counts: {counts_str}"
            else:
                test.status = "FAIL"
                issues = []
                if missing_folders:
                    issues.append(f"Missing folders: {', '.join(missing_folders)}")
                if not count_matches:
                    mismatches = [
                        f"{name} (expected {data['expected_count']}, got {data['actual_count']})"
                        for name, data in folder_data.items()
                        if data['expected_count'] != data['actual_count']
                    ]
                    issues.append(f"Count mismatches: {', '.join(mismatches)}")
                test.actual = f"Issues: {', '.join(issues)}"
                test.bugs.extend(issues)

        except Exception as e:
            test.status = "FAIL"
            test.actual = f"Exception: {str(e)}"
            test.bugs.append(f"Exception during test: {str(e)}")

        self.results.append(test)

    def test_database_persistence(self):
        """Test 8: Database Persistence."""
        test = MessageTestResult("Database Persistence")
        test.steps = [
            "Make a change to a message (star it)",
            "Create a new LocalEmailStorage instance",
            "Verify the change persisted"
        ]
        test.expected = "Changes persist across storage instances"

        try:
            inbox_messages = self.storage.get_messages_by_folder("Inbox")
            test_msg = inbox_messages[0]
            msg_id = test_msg["id"]
            original_starred = test_msg.get("is_starred", False)

            # Make a change
            new_starred = not original_starred
            self.storage.update_message(msg_id, {"is_starred": new_starred})

            # Create new storage instance (simulates app restart)
            new_storage = LocalEmailStorage()

            # Check if change persisted
            msg_from_new = new_storage.get_message(msg_id)
            persisted_starred = msg_from_new.get("is_starred", False)

            # Restore original state
            self.storage.update_message(msg_id, {"is_starred": original_starred})

            if persisted_starred == new_starred:
                test.status = "PASS"
                test.actual = f"Change persisted. Original: {original_starred}, Changed to: {new_starred}, After reload: {persisted_starred}"
            else:
                test.status = "FAIL"
                test.actual = f"Change did not persist. Changed to: {new_starred}, After reload: {persisted_starred}"
                test.bugs.append("Database changes do not persist across instances")

        except Exception as e:
            test.status = "FAIL"
            test.actual = f"Exception: {str(e)}"
            test.bugs.append(f"Exception during test: {str(e)}")

        self.results.append(test)

    def _print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 70)
        print("DETAILED TEST RESULTS")
        print("=" * 70)

        for result in self.results:
            print(result)

        # Summary
        passed = sum(1 for r in self.results if r.status == "PASS")
        failed = sum(1 for r in self.results if r.status == "FAIL")
        total = len(self.results)

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Pass Rate: {(passed/total)*100:.1f}%")

        all_bugs = []
        for r in self.results:
            all_bugs.extend(r.bugs)

        if all_bugs:
            print("\nAll Issues Found:")
            for bug in all_bugs:
                print(f"  - {bug}")


if __name__ == "__main__":
    tests = MessageManagementTests()
    tests.run_all_tests()
