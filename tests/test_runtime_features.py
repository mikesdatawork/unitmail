#!/usr/bin/env python3
"""
Runtime test for verifying features work in actual application.

This test launches the application in a non-interactive mode and verifies
that all features can be accessed programmatically.
"""

import sys
import os
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def test_application_initialization():
    """Test that the application can be initialized."""
    logger.info("Testing application initialization...")

    try:
        import gi
        gi.require_version('Gtk', '4.0')
        gi.require_version('Adw', '1')
        from gi.repository import Gtk, Adw, Gio

        from client.ui.application import UnitMailApplication

        # Create application
        app = UnitMailApplication()
        logger.info("✓ Application created successfully")

        # Verify app properties
        assert app is not None
        logger.info("✓ Application instance is valid")

    except Exception as e:
        logger.error(f"✗ Application initialization failed: {e}")
        import traceback
        traceback.print_exc()
        raise


def test_main_window_creation():
    """Test that main window can be created."""
    logger.info("\nTesting main window creation...")

    try:
        import gi
        gi.require_version('Gtk', '4.0')
        gi.require_version('Adw', '1')
        from gi.repository import Gtk, Adw, Gio

        from client.ui.application import UnitMailApplication
        from client.ui.main_window import MainWindow

        # Create application and window
        app = UnitMailApplication()
        window = MainWindow(application=app)
        logger.info("✓ Main window created successfully")

        # Verify window components
        assert hasattr(window, '_folder_store')
        logger.info("✓ Folder store initialized")

        assert hasattr(window, '_message_store')
        logger.info("✓ Message store initialized")

        assert hasattr(window, '_search_entry')
        logger.info("✓ Search entry initialized")

        # Check that sample data loaded
        folder_count = window._folder_store.get_n_items()
        logger.info(f"✓ {folder_count} folders loaded")

        message_count = window._message_store.get_n_items()
        logger.info(f"✓ {message_count} messages loaded")

    except Exception as e:
        logger.error(f"✗ Main window creation failed: {e}")
        import traceback
        traceback.print_exc()
        raise


def test_message_operations():
    """Test message operations like favorite, delete, etc."""
    logger.info("\nTesting message operations...")

    try:
        import gi
        gi.require_version('Gtk', '4.0')
        gi.require_version('Adw', '1')
        from gi.repository import Gtk, Adw, Gio

        from client.ui.application import UnitMailApplication
        from client.ui.main_window import MainWindow

        app = UnitMailApplication()
        window = MainWindow(application=app)

        # Get first message
        initial_count = window._message_store.get_n_items()
        if initial_count == 0:
            logger.warning("⚠ No messages loaded for testing")
            return  # Skip rest of test if no messages

        first_message = window._message_store.get_item(0)
        logger.info(f"✓ Retrieved message: {first_message.subject}")

        # Test favorite toggle
        initial_starred = first_message.is_starred
        window._set_message_starred(first_message.message_id, not initial_starred)
        assert first_message.is_starred == (not initial_starred)
        logger.info("✓ Favorite toggle works")

        # Test mark read
        window._set_message_read(first_message.message_id, True)
        assert first_message.is_read == True
        logger.info("✓ Mark read works")

        # Test delete (get count before and after)
        before_delete = window._message_store.get_n_items()
        window._selected_message_id = first_message.message_id
        window._on_delete_message(None, None)
        after_delete = window._message_store.get_n_items()
        assert after_delete == before_delete - 1
        logger.info("✓ Delete message works")

    except Exception as e:
        logger.error(f"✗ Message operations failed: {e}")
        import traceback
        traceback.print_exc()
        raise


def test_search_functionality():
    """Test search functionality."""
    logger.info("\nTesting search functionality...")

    try:
        import gi
        gi.require_version('Gtk', '4.0')
        gi.require_version('Adw', '1')
        from gi.repository import Gtk, Adw, Gio

        from client.ui.application import UnitMailApplication
        from client.ui.main_window import MainWindow

        app = UnitMailApplication()
        window = MainWindow(application=app)

        # Select inbox first to ensure we have a folder context
        if window._folder_store.get_n_items() > 0:
            first_folder = window._folder_store.get_item(0)
            window._selected_folder_id = first_folder.folder_id
            window._load_folder_messages(first_folder.name)

        initial_count = window._message_store.get_n_items()
        logger.info(f"✓ Initial message count: {initial_count}")

        # Test search filter
        window._filter_messages("alice")
        filtered_count = window._message_store.get_n_items()
        logger.info(f"✓ Filtered to {filtered_count} messages")
        assert filtered_count <= initial_count, "Filtered count should be <= initial count"

        # Clear search
        window._filter_messages("")
        restored_count = window._message_store.get_n_items()
        assert restored_count == initial_count, f"Expected {initial_count}, got {restored_count}"
        logger.info("✓ Search filter and clear works")

    except Exception as e:
        logger.error(f"✗ Search functionality failed: {e}")
        import traceback
        traceback.print_exc()
        raise


def test_view_theme_switching():
    """Test view theme switching."""
    logger.info("\nTesting view theme switching...")

    try:
        from client.ui.view_theme import ViewTheme, get_view_theme_manager

        manager = get_view_theme_manager()
        initial_theme = manager.current_theme
        logger.info(f"✓ Initial theme: {initial_theme}")

        # Switch to minimal
        manager.set_theme(ViewTheme.MINIMAL)
        assert manager.current_theme == ViewTheme.MINIMAL
        logger.info("✓ Switched to minimal theme")

        # Switch to standard
        manager.set_theme(ViewTheme.STANDARD)
        assert manager.current_theme == ViewTheme.STANDARD
        logger.info("✓ Switched to standard theme")

    except Exception as e:
        logger.error(f"✗ View theme switching failed: {e}")
        import traceback
        traceback.print_exc()
        raise


def main():
    """Run all runtime tests."""
    print("="*70)
    print("Runtime Feature Testing".center(70))
    print("="*70)

    tests = [
        ("Application Initialization", test_application_initialization),
        ("Main Window Creation", test_main_window_creation),
        ("Message Operations", test_message_operations),
        ("Search Functionality", test_search_functionality),
        ("View Theme Switching", test_view_theme_switching),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*70}")
        print(f"Running: {test_name}")
        print('='*70)
        try:
            test_func()
            results.append((test_name, True))
        except Exception as e:
            logger.error(f"Test {test_name} crashed: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "="*70)
    print("RUNTIME TEST SUMMARY".center(70))
    print("="*70)

    passed = sum(1 for _, result in results if result)
    failed = len(results) - passed

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:10} - {test_name}")

    print(f"\nTotal: {len(results)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Pass Rate: {passed/len(results)*100:.1f}%")

    if failed == 0:
        print("\n✓ All runtime tests passed!")
        return 0
    else:
        print(f"\n✗ {failed} runtime test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
