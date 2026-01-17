#!/usr/bin/env python3
"""
Test script for verifying implemented features.

Tests:
1. Import verification - all modules import without errors
2. Widget instantiation - GTK widgets can be created
3. Feature implementation checks
"""

import sys
import os
import logging
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class FeatureTestResults:
    """Track test results."""
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []

    def add_pass(self, test_name, details=""):
        self.passed.append((test_name, details))
        logger.info(f"✓ {test_name}")
        if details:
            logger.info(f"  {details}")

    def add_fail(self, test_name, error):
        self.failed.append((test_name, str(error)))
        logger.error(f"✗ {test_name}: {error}")

    def add_warning(self, test_name, message):
        self.warnings.append((test_name, message))
        logger.warning(f"⚠ {test_name}: {message}")


def test_imports(results: FeatureTestResults):
    """Test that all modified modules can be imported."""
    logger.info("\n=== Testing Imports ===")

    # Core modules
    modules_to_test = [
        ('client.ui.main_window', ['MainWindow', 'MessageItem', 'FolderItem']),
        ('client.ui.view_theme', ['ViewTheme', 'get_view_theme_manager']),
        ('client.ui.application', ['UnitMailApplication']),
        ('client.ui.composer', ['ComposerWindow', 'ComposerMode']),
    ]

    for module_name, expected_classes in modules_to_test:
        try:
            module = __import__(module_name, fromlist=expected_classes)
            # Verify classes exist
            missing = [c for c in expected_classes if not hasattr(module, c)]
            if missing:
                results.add_fail(f"Import {module_name}", f"Missing classes: {missing}")
            else:
                results.add_pass(f"Import {module_name}", f"Classes: {', '.join(expected_classes)}")
        except Exception as e:
            results.add_fail(f"Import {module_name}", str(e))


def test_widget_instantiation(results: FeatureTestResults):
    """Test that GTK widgets can be instantiated."""
    logger.info("\n=== Testing Widget Instantiation ===")

    try:
        import gi
        gi.require_version('Gtk', '4.0')
        gi.require_version('Adw', '1')
        from gi.repository import Gtk, Adw, Gio  # noqa: F401
        results.add_pass("GTK4 initialization", "GTK4 and Adwaita available")
    except Exception as e:
        results.add_fail("GTK4 initialization", str(e))
        return

    # Test MessageItem
    try:
        from client.ui.main_window import MessageItem
        msg = MessageItem(
            message_id="test1",
            from_address="test@example.com",
            subject="Test Subject",
            preview="Test preview text",
            date=datetime.now(),
            is_read=False,
            is_starred=False,
        )
        assert msg.message_id == "test1"
        assert msg.from_address == "test@example.com"
        results.add_pass("MessageItem instantiation", f"Created with ID: {msg.message_id}")
    except Exception as e:
        results.add_fail("MessageItem instantiation", str(e))

    # Test FolderItem
    try:
        from client.ui.main_window import FolderItem
        folder = FolderItem(
            folder_id="inbox",
            name="Inbox",
            icon_name="mail-inbox-symbolic",
            unread_count=5,
        )
        assert folder.folder_id == "inbox"
        assert folder.name == "Inbox"
        results.add_pass("FolderItem instantiation", f"Created folder: {folder.name}")
    except Exception as e:
        results.add_fail("FolderItem instantiation", str(e))


def test_feature_implementation(results: FeatureTestResults):
    """Test that features are properly implemented."""
    logger.info("\n=== Testing Feature Implementation ===")

    # Test 1: Favorite toggle implementation
    try:
        from client.ui.main_window import MainWindow
        import inspect

        # Check for starred/favorite methods
        methods = inspect.getmembers(MainWindow, predicate=inspect.isfunction)
        method_names = [m[0] for m in methods]

        required_methods = ['_on_mark_starred', '_on_unstar_message', '_set_message_starred']
        missing = [m for m in required_methods if m not in method_names]

        if missing:
            results.add_fail("Favorite toggle feature", f"Missing methods: {missing}")
        else:
            results.add_pass("Favorite toggle feature", "All required methods present")
    except Exception as e:
        results.add_fail("Favorite toggle feature", str(e))

    # Test 2: Delete message implementation
    try:
        from client.ui.main_window import MainWindow
        import inspect

        methods = inspect.getmembers(MainWindow, predicate=inspect.isfunction)
        method_names = [m[0] for m in methods]

        if '_on_delete_message' in method_names:
            results.add_pass("Delete message feature", "Delete handler implemented")
        else:
            results.add_fail("Delete message feature", "Missing _on_delete_message handler")
    except Exception as e:
        results.add_fail("Delete message feature", str(e))

    # Test 3: Double-click pop-out implementation
    try:
        from client.ui.main_window import MainWindow
        import inspect

        methods = inspect.getmembers(MainWindow, predicate=inspect.isfunction)
        method_names = [m[0] for m in methods]

        required_methods = ['_on_message_double_click', '_open_message_popout']
        missing = [m for m in required_methods if m not in method_names]

        if missing:
            results.add_fail("Double-click pop-out feature", f"Missing methods: {missing}")
        else:
            results.add_pass("Double-click pop-out feature", "Pop-out handlers implemented")
    except Exception as e:
        results.add_fail("Double-click pop-out feature", str(e))

    # Test 4: Header alignment (column headers)
    try:
        from client.ui.main_window import MainWindow
        import inspect

        source = inspect.getsource(MainWindow._create_message_list_pane)

        if '_column_headers' in source and 'margin_start=12' in source:
            results.add_pass("Header alignment feature", "Column headers with proper margins")
        else:
            results.add_warning("Header alignment feature", "Column headers may need margin adjustment")
    except Exception as e:
        results.add_fail("Header alignment feature", str(e))

    # Test 5: Search focus implementation
    try:
        from client.ui.main_window import MainWindow
        import inspect

        methods = inspect.getmembers(MainWindow, predicate=inspect.isfunction)
        method_names = [m[0] for m in methods]

        if '_on_search_focus' in method_names:
            results.add_pass("Search focus feature", "Search focus handler implemented")
        else:
            results.add_fail("Search focus feature", "Missing _on_search_focus handler")
    except Exception as e:
        results.add_fail("Search focus feature", str(e))

    # Test 6: Threaded messages in sample data
    try:
        from client.ui.main_window import MainWindow
        import inspect

        source = inspect.getsource(MainWindow._load_sample_data)

        # Check for threaded conversation markers
        if 'thread1-1' in source and 'Project Planning' in source:
            results.add_pass("Threaded messages feature", "Sample threaded conversation present")
        else:
            results.add_fail("Threaded messages feature", "Threaded conversation not found in sample data")
    except Exception as e:
        results.add_fail("Threaded messages feature", str(e))


def test_view_theme_manager(results: FeatureTestResults):
    """Test view theme manager functionality."""
    logger.info("\n=== Testing View Theme Manager ===")

    try:
        from client.ui.view_theme import ViewTheme, ViewThemeManager, get_view_theme_manager  # noqa: F401

        # Test enum values exist
        assert hasattr(ViewTheme, 'STANDARD')
        assert hasattr(ViewTheme, 'MINIMAL')
        results.add_pass("ViewTheme enum", "All theme values defined")

        # Test singleton
        manager1 = get_view_theme_manager()
        manager2 = get_view_theme_manager()
        assert manager1 is manager2
        results.add_pass("ViewThemeManager singleton", "Singleton pattern working")

        # Test theme switching
        manager1.set_theme(ViewTheme.MINIMAL)
        assert manager1.current_theme == ViewTheme.MINIMAL
        results.add_pass("ViewTheme switching", "Can switch between themes")

    except Exception as e:
        import traceback
        results.add_fail("View theme manager", f"{str(e)}\n{traceback.format_exc()}")


def generate_report(results: FeatureTestResults):
    """Generate test report."""
    print("\n" + "="*70)
    print("TEST AUTOMATION REPORT".center(70))
    print("="*70)

    # Import Tests
    print("\n## Import Tests")
    print("| Module | Status |")
    print("|--------|--------|")
    for test_name, details in results.passed:
        if test_name.startswith("Import"):
            print(f"| {test_name.replace('Import ', '')} | ✓ PASS |")
    for test_name, error in results.failed:
        if test_name.startswith("Import"):
            print(f"| {test_name.replace('Import ', '')} | ✗ FAIL |")

    # Widget Instantiation Tests
    print("\n## Widget Instantiation Tests")
    print("| Widget | Status |")
    print("|--------|--------|")
    for test_name, details in results.passed:
        if "instantiation" in test_name or "initialization" in test_name:
            print(f"| {test_name} | ✓ PASS |")
    for test_name, error in results.failed:
        if "instantiation" in test_name or "initialization" in test_name:
            print(f"| {test_name} | ✗ FAIL |")

    # Feature Verification
    print("\n## Feature Verification")
    print("| Feature | Status | Notes |")
    print("|---------|--------|-------|")

    feature_tests = [
        ("Favorite toggle", "Favorite toggle feature"),
        ("Delete message", "Delete message feature"),
        ("Double-click pop-out", "Double-click pop-out feature"),
        ("Header alignment", "Header alignment feature"),
        ("Search focus", "Search focus feature"),
        ("Threaded messages", "Threaded messages feature"),
    ]

    for feature_name, test_key in feature_tests:
        status = "NOT TESTED"
        notes = ""

        for test_name, details in results.passed:
            if test_key in test_name:
                status = "✓ PASS"
                notes = details
                break

        for test_name, error in results.failed:
            if test_key in test_name:
                status = "✗ FAIL"
                notes = error
                break

        for test_name, warning in results.warnings:
            if test_key in test_name:
                status = "⚠ WARN"
                notes = warning
                break

        print(f"| {feature_name} | {status} | {notes[:50]} |")

    # Issues Found
    print("\n## Issues Found")
    if results.failed:
        for test_name, error in results.failed:
            print(f"- **{test_name}**: {error}")
    else:
        print("No critical issues found.")

    if results.warnings:
        print("\n### Warnings")
        for test_name, warning in results.warnings:
            print(f"- **{test_name}**: {warning}")

    # Summary
    print("\n## Summary")
    total_tests = len(results.passed) + len(results.failed)
    pass_rate = (len(results.passed) / total_tests * 100) if total_tests > 0 else 0

    print(f"- Total Tests: {total_tests}")
    print(f"- Passed: {len(results.passed)}")
    print(f"- Failed: {len(results.failed)}")
    print(f"- Warnings: {len(results.warnings)}")
    print(f"- Pass Rate: {pass_rate:.1f}%")

    # Verdict
    print("\n## Verdict")
    if len(results.failed) == 0:
        print("✓ **PASS** - All tests passed successfully!")
    elif len(results.failed) <= 2 and pass_rate >= 80:
        print("⚠ **CONDITIONAL PASS** - Most tests passed with minor issues")
    else:
        print("✗ **FAIL** - Critical issues found that need resolution")

    print("\n" + "="*70)
    print("Route to change-coordinator for status report.")
    print("="*70 + "\n")

    return len(results.failed) == 0


def main():
    """Run all tests."""
    results = FeatureTestResults()

    print("="*70)
    print("Starting Test Automation".center(70))
    print("="*70)

    # Run tests
    test_imports(results)
    test_widget_instantiation(results)
    test_feature_implementation(results)
    test_view_theme_manager(results)

    # Generate report
    success = generate_report(results)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
