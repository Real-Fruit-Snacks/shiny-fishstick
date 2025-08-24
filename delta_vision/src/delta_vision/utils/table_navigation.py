"""Table navigation utilities for Delta Vision.

This module provides reusable table navigation functionality including vim-like key bindings
and multi-table focus management.
"""

from __future__ import annotations

from typing import Callable

from textual.widgets import DataTable

from .logger import log


class TableNavigationHandler:
    """Handles complex table navigation with vim-like key bindings."""

    def __init__(self):
        self._last_g = False  # Track 'g' key for 'gg' behavior

    def handle_key_event(
        self,
        event,
        focused_widget,
        tables: dict[str, DataTable],
        enter_callback: Callable[[], None] | None = None,
        navigation_callback: Callable[[], None] | None = None,
    ) -> bool:
        """
        Handle key events for table navigation.

        Args:
            event: The key event
            focused_widget: Currently focused widget
            tables: Dict of table name -> DataTable widget
            enter_callback: Callback for Enter key presses
            navigation_callback: Callback after navigation changes

        Returns:
            True if event was handled, False otherwise
        """
        try:
            key = getattr(event, 'key', None)
            if not key:
                return False

            # Handle Enter key
            if key == 'enter' and enter_callback:
                for _table_name, table in tables.items():
                    if table and focused_widget == table:
                        event.stop()
                        enter_callback()
                        return True

            # Handle arrow keys with navigation callback
            if key in ('up', 'down', 'left', 'right', 'home', 'end', 'pageup', 'pagedown'):
                if navigation_callback:
                    # Let the default navigation happen first, then call callback
                    # This needs to be deferred to after the table updates
                    return False  # Let default handling occur

            # Handle vim-like navigation
            if key in ('j', 'k', 'g', 'G'):
                focused_table = self._get_focused_table(focused_widget, tables)
                if focused_table:
                    event.stop()
                    return self._handle_vim_navigation(key, focused_table)

        except Exception as e:
            log(f"Error handling key event: {e}")

        return False

    def _get_focused_table(self, focused_widget, tables: dict[str, DataTable]) -> DataTable | None:
        """Get the currently focused table from the tables dict."""
        for table in tables.values():
            if table and focused_widget == table:
                return table
        return None

    def _handle_vim_navigation(self, key: str, table: DataTable) -> bool:
        """Handle vim-like navigation keys (j/k/g/G)."""
        try:
            if key == 'j':
                self._move_cursor_down(table)
                self._last_g = False
            elif key == 'k':
                self._move_cursor_up(table)
                self._last_g = False
            elif key == 'G':
                self._move_cursor_to_end(table)
                self._last_g = False
            elif key == 'g':
                if self._last_g:
                    self._move_cursor_to_start(table)
                    self._last_g = False
                else:
                    self._last_g = True
            else:
                self._last_g = False

            return True

        except Exception as e:
            log(f"Error in vim navigation: {e}")
            return False

    def _get_table_position(self, table: DataTable) -> tuple[int, int]:
        """Get current cursor position and total rows."""
        try:
            coord = table.cursor_coordinate
            current_row = getattr(coord, 'row', 0) if coord else 0

            # Get total rows
            total_rows = getattr(table, 'row_count', 0)
            if total_rows == 0:
                rows = getattr(table, 'rows', [])
                total_rows = len(rows) if rows else 0

            return current_row, total_rows
        except Exception as e:
            log(f"Error getting table position: {e}")
            return 0, 0

    def _move_cursor_to_row(self, table: DataTable, row: int):
        """Move cursor to specific row with scrolling."""
        try:
            table.move_cursor(row=row, column=0)

            # Try to scroll to the row if possible
            scroll_to_row = getattr(table, 'scroll_to_row', None)
            if callable(scroll_to_row):
                scroll_to_row(row)
            else:
                scroll_to_cursor = getattr(table, 'scroll_to_cursor', None)
                if callable(scroll_to_cursor):
                    scroll_to_cursor()

        except Exception as e:
            log(f"Error moving cursor to row {row}: {e}")

    def _move_cursor_down(self, table: DataTable):
        """Move cursor down one row."""
        current_row, total_rows = self._get_table_position(table)
        if total_rows > 0:
            new_row = min(current_row + 1, total_rows - 1)
            self._move_cursor_to_row(table, new_row)

    def _move_cursor_up(self, table: DataTable):
        """Move cursor up one row."""
        current_row, _total_rows = self._get_table_position(table)
        new_row = max(current_row - 1, 0)
        self._move_cursor_to_row(table, new_row)

    def _move_cursor_to_start(self, table: DataTable):
        """Move cursor to first row (gg behavior)."""
        self._move_cursor_to_row(table, 0)

    def _move_cursor_to_end(self, table: DataTable):
        """Move cursor to last row (G behavior)."""
        _current_row, total_rows = self._get_table_position(table)
        if total_rows > 0:
            self._move_cursor_to_row(table, total_rows - 1)

    def reset_state(self):
        """Reset internal navigation state."""
        self._last_g = False


class MultiTableManager:
    """Manages multiple tables with synchronized behavior."""

    def __init__(self):
        self.tables: dict[str, DataTable] = {}
        self.navigation_handler = TableNavigationHandler()

    def register_table(self, name: str, table: DataTable):
        """Register a table for management."""
        self.tables[name] = table

    def unregister_table(self, name: str):
        """Unregister a table."""
        self.tables.pop(name, None)

    def get_focused_table_name(self, focused_widget) -> str | None:
        """Get the name of the currently focused table."""
        for name, table in self.tables.items():
            if table and focused_widget == table:
                return name
        return None

    def handle_navigation(
        self,
        event,
        focused_widget,
        enter_callback: Callable[[], None] | None = None,
        navigation_callback: Callable[[], None] | None = None,
    ) -> bool:
        """Handle navigation events across managed tables."""
        return self.navigation_handler.handle_key_event(
            event, focused_widget, self.tables, enter_callback, navigation_callback
        )

    def clear_all_tables(self):
        """Clear all registered tables."""
        for table in self.tables.values():
            if table:
                try:
                    table.clear()
                except Exception as e:
                    log(f"Error clearing table: {e}")

    def get_table_stats(self) -> dict[str, dict]:
        """Get statistics for all tables."""
        stats = {}
        for name, table in self.tables.items():
            if table:
                try:
                    current_row, total_rows = self.navigation_handler._get_table_position(table)
                    stats[name] = {
                        "current_row": current_row,
                        "total_rows": total_rows,
                        "has_focus": False,  # Will be set by caller
                    }
                except Exception as e:
                    log(f"Error getting stats for table {name}: {e}")
                    stats[name] = {"error": str(e)}
        return stats
