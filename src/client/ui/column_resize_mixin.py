"""
Column Resize Mixin for Main Window.

This module provides resizable column functionality for the minimal/columnar view
in the message list. It adds drag handles between column headers that allow users
to adjust column widths, with persistence via settings.
"""

import logging
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, Gtk

logger = logging.getLogger(__name__)


class ColumnResizeMixin:
    """
    Mixin to add resizable column functionality to MainWindow.

    This mixin should be mixed into the MainWindow class to provide
    column resize capabilities for the minimal view.
    """

    # Minimum column widths to prevent making columns too narrow
    MIN_COLUMN_WIDTH_RECEIVED = 80
    MIN_COLUMN_WIDTH_FROM = 120
    MIN_COLUMN_WIDTH_SUBJECT = 100

    def _create_resize_handle(self, column_name: str) -> Gtk.Widget:
        """
        Create a resize handle widget for a column.

        Args:
            column_name: Name of the column ('received', 'from', 'subject')

        Returns:
            A widget that acts as a resize handle.
        """
        # Create a separator that will act as the resize handle
        handle = Gtk.Separator(
            orientation=Gtk.Orientation.VERTICAL,
            css_classes=["column-resize-handle"],
        )
        handle.set_size_request(8, -1)  # 8px wide drag area

        # Add motion controller for cursor change
        motion_ctrl = Gtk.EventControllerMotion()
        motion_ctrl.connect("enter", self._on_resize_handle_enter)
        motion_ctrl.connect("leave", self._on_resize_handle_leave)
        handle.add_controller(motion_ctrl)

        # Add drag gesture for resizing
        drag_gesture = Gtk.GestureDrag()
        drag_gesture.connect("drag-begin", self._on_resize_drag_begin, column_name)
        drag_gesture.connect("drag-update", self._on_resize_drag_update, column_name)
        drag_gesture.connect("drag-end", self._on_resize_drag_end, column_name)
        handle.add_controller(drag_gesture)

        return handle

    def _on_resize_handle_enter(
        self,
        controller: Gtk.EventControllerMotion,
        x: float,
        y: float,
    ) -> None:
        """Handle mouse entering resize handle - change cursor."""
        widget = controller.get_widget()
        widget.set_cursor(Gdk.Cursor.new_from_name("col-resize", None))

    def _on_resize_handle_leave(
        self,
        controller: Gtk.EventControllerMotion,
    ) -> None:
        """Handle mouse leaving resize handle - restore cursor."""
        widget = controller.get_widget()
        widget.set_cursor(None)

    def _on_resize_drag_begin(
        self,
        gesture: Gtk.GestureDrag,
        start_x: float,
        start_y: float,
        column_name: str,
    ) -> None:
        """
        Handle start of column resize drag.

        Args:
            gesture: The drag gesture.
            start_x: Starting X coordinate.
            start_y: Starting Y coordinate.
            column_name: Name of the column being resized.
        """
        self._resizing_column = column_name
        self._resize_start_x = start_x

        # Store the current width of the column being resized
        if column_name == "received":
            self._resize_start_width = self._column_width_received
        elif column_name == "from":
            self._resize_start_width = self._column_width_from

        logger.debug(f"Started resizing column: {column_name}, start_width: {self._resize_start_width}")

    def _on_resize_drag_update(
        self,
        gesture: Gtk.GestureDrag,
        offset_x: float,
        offset_y: float,
        column_name: str,
    ) -> None:
        """
        Handle column resize drag update - adjust column width.

        Args:
            gesture: The drag gesture.
            offset_x: X offset from drag start.
            offset_y: Y offset from drag start.
            column_name: Name of the column being resized.
        """
        if not self._resizing_column:
            return

        # Calculate new width
        new_width = int(self._resize_start_width + offset_x)

        # Apply minimum width constraints
        if column_name == "received":
            new_width = max(new_width, self.MIN_COLUMN_WIDTH_RECEIVED)
            self._column_width_received = new_width
            self._received_header_btn.set_size_request(new_width, -1)
        elif column_name == "from":
            new_width = max(new_width, self.MIN_COLUMN_WIDTH_FROM)
            self._column_width_from = new_width
            self._from_header_btn.set_size_request(new_width, -1)

        # Force message list to refresh to reflect new column widths
        # This will trigger rebinding of all visible rows
        if hasattr(self, '_message_store') and self._message_store:
            n_items = self._message_store.get_n_items()
            if n_items > 0:
                self._message_store.items_changed(0, n_items, n_items)

    def _on_resize_drag_end(
        self,
        gesture: Gtk.GestureDrag,
        offset_x: float,
        offset_y: float,
        column_name: str,
    ) -> None:
        """
        Handle end of column resize - save to settings.

        Args:
            gesture: The drag gesture.
            offset_x: Final X offset from drag start.
            offset_y: Final Y offset from drag start.
            column_name: Name of the column being resized.
        """
        if not self._resizing_column:
            return

        logger.info(
            f"Finished resizing column: {column_name}, "
            f"received={self._column_width_received}, "
            f"from={self._column_width_from}"
        )

        # Save column widths to settings
        self._save_column_widths()

        # Clear resize state
        self._resizing_column = None

    def _save_column_widths(self) -> None:
        """Save current column widths to user settings."""
        try:
            from client.services.settings_service import get_settings_service
            settings = get_settings_service()
            settings.update_appearance(
                column_width_received=self._column_width_received,
                column_width_from=self._column_width_from,
                column_width_subject=self._column_width_subject,
            )
            settings.save()
            logger.debug(f"Saved column widths to settings")
        except Exception as e:
            logger.warning(f"Failed to save column widths: {e}")

    def _load_column_widths(self) -> None:
        """Load column widths from user settings."""
        try:
            from client.services.settings_service import get_settings_service
            settings = get_settings_service()
            self._column_width_received = settings.appearance.column_width_received
            self._column_width_from = settings.appearance.column_width_from
            self._column_width_subject = settings.appearance.column_width_subject
            logger.debug(
                f"Loaded column widths: received={self._column_width_received}, "
                f"from={self._column_width_from}, subject={self._column_width_subject}"
            )
        except Exception as e:
            logger.warning(f"Failed to load column widths, using defaults: {e}")
            self._column_width_received = 120
            self._column_width_from = 250
            self._column_width_subject = -1
