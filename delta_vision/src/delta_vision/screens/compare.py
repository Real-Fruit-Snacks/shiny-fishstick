"""Compare screen: correlate files by the quoted command on the first line.

This screen scans the NEW and OLD folders and groups files by their embedded
command (read from the first line in quotes). It shows:
- DIFF: newest NEW vs newest matching OLD
- SAME: newest NEW vs the previous NEW with the same command (to detect churn)

Press Enter to open a side-by-side diff for the selected row.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable

from delta_vision.utils.base_screen import BaseTableScreen
from delta_vision.utils.io import read_lines
from delta_vision.utils.logger import log
from delta_vision.utils.screen_navigation import create_navigator
from delta_vision.utils.table_navigation import TableNavigationHandler
from delta_vision.utils.watchdog import start_observer
from delta_vision.widgets.footer import Footer


@dataclass
class Pair:
    """A comparison pair between two files for the same command.

    kind:
        - "DIFF": newest NEW vs newest OLD
        - "SAME": newest NEW vs previous NEW
    """

    command: str
    new_path: str
    old_path: str
    kind: str  # "DIFF" or "SAME"


class CompareScreen(BaseTableScreen):
    """Table of comparison pairs with quick filtering and navigation."""

    BINDINGS = [
        ("q", "go_back", "Back"),
        ("f", "toggle_changes_only", "Changes Only"),
        ("j", "next_row", "Down"),
        ("k", "prev_row", "Up"),
        ("G", "end", "End"),
    ]

    CSS_PATH = "search.tcss"  # reuse basic table styling

    def __init__(
        self,
        new_folder_path: str | None = None,
        old_folder_path: str | None = None,
        keywords_path: str | None = None,
    ):
        super().__init__(page_name="Compare")
        self.new_folder_path = new_folder_path
        self.old_folder_path = old_folder_path
        self.keywords_path = keywords_path
        self._table = None
        self._pairs = []  # full computed pairs
        self._display_pairs = []  # pairs actually displayed in the table order
        # Filter toggle (only show rows with changes)
        self._changes_only = False
        # Watchdog observers
        self._observer_new = None
        self._observer_old = None

        # Table navigation handler
        self._navigation = TableNavigationHandler()

    def compose_main_content(self) -> ComposeResult:
        """Build results table with comparison data."""
        with Vertical(id="compare-root"):
            self._table = DataTable(id="compare-table")
            # TYPE first, then Command
            self._table.add_column(Text("TYPE", justify="center"), key="type", width=6)
            # Thin visual separators between columns
            self._table.add_column(Text("│", style="dim", justify="center"), key="sep1", width=1)
            self._table.add_column(Text("Change", justify="center"), key="chg", width=8)
            self._table.add_column(Text("│", style="dim", justify="center"), key="sep2", width=1)
            self._table.add_column("Command", key="cmd")
            yield self._table

    def get_footer_text(self) -> str:
        """Return footer text that reflects the current filter state."""
        state = "ON" if self._changes_only else "OFF"
        return (
            " [orange1]q[/orange1] Back    "
            "[orange1]Enter[/orange1] View Diff    "
            f"[orange1]f[/orange1] Changes Only: {state}    "
            "Legend: [green]✓[/green] changed, [orange1]✗[/orange1] same"
        )

    async def on_mount(self) -> None:
        """Initialize and start folder watchers, then scan."""
        await super().on_mount()  # This handles table setup and title
        self._scan_and_populate()

        # Start watchers for live updates
        def trigger_refresh():
            if self.app:
                self.app.call_later(self._scan_and_populate)

        try:
            if self.new_folder_path and os.path.isdir(self.new_folder_path):
                self._observer_new, self._stop_new = start_observer(self.new_folder_path, trigger_refresh)
        except (OSError, RuntimeError) as e:
            log(f"Failed to start file watcher for new folder {self.new_folder_path}: {e}")
            self._observer_new = None
            self._stop_new = None
        try:
            if self.old_folder_path and os.path.isdir(self.old_folder_path):
                self._observer_old, self._stop_old = start_observer(self.old_folder_path, trigger_refresh)
        except (OSError, RuntimeError) as e:
            log(f"Failed to start file watcher for old folder {self.old_folder_path}: {e}")
            self._observer_old = None
            self._stop_old = None

    def on_unmount(self) -> None:
        """Stop any active observers when leaving the screen."""
        # Stop observers when leaving the screen
        # Prefer unified stop functions
        try:
            stop_new = getattr(self, "_stop_new", None)
            if callable(stop_new):
                stop_new()
        except (AttributeError, RuntimeError) as e:
            log(f"Failed to stop new folder watcher: {e}")
            pass
        try:
            stop_old = getattr(self, "_stop_old", None)
            if callable(stop_old):
                stop_old()
        except (AttributeError, RuntimeError) as e:
            log(f"Failed to stop old folder watcher: {e}")
            pass
        # Fallback: legacy observer stop if present
        for obs in (getattr(self, "_observer_new", None), getattr(self, "_observer_old", None)):
            try:
                if obs:
                    obs.stop()
                    obs.join(timeout=0.5)
            except (AttributeError, RuntimeError) as e:
                log(f"Failed to stop observer {obs}: {e}")
                pass
        self._observer_new = None
        self._observer_old = None
        self._stop_new = None
        self._stop_old = None

    def _scan_and_populate(self) -> None:
        """Recompute comparison pairs and rebuild the table.

        Preserves the current selection where possible by mapping back from the
        selected row to its underlying pair identity.
        """
        pairs = self._find_pairs()
        self._pairs = pairs
        table = self._table
        if not table:
            return

        prev_key = self._capture_current_selection(table)
        self._clear_table(table)
        display_pairs = self._process_and_add_pairs(table, pairs)
        self._display_pairs = display_pairs
        if display_pairs:
            self._restore_selection_and_focus(table, display_pairs, prev_key)

    def _capture_current_selection(self, table) -> tuple[str, str, str] | None:
        """Capture the current table selection for restoration after rebuild."""
        prev_key = None
        try:
            coord = table.cursor_coordinate
            if coord is not None:
                row_index = getattr(coord, 'row', None)
                if row_index is not None and 0 <= row_index < len(getattr(self, '_display_pairs', [])):
                    cur_pair = self._display_pairs[row_index]
                    if cur_pair:
                        prev_key = (cur_pair.new_path, cur_pair.old_path, cur_pair.kind)
        except (AttributeError, IndexError, ValueError) as e:
            log(f"Failed to capture current table selection: {e}")
            prev_key = None
        return prev_key

    def _clear_table(self, table: Any) -> None:
        """Clear the comparison table."""
        try:
            table.clear()
        except (AttributeError, RuntimeError) as e:
            log(f"Failed to clear comparison table: {e}")
            pass

    def _process_and_add_pairs(self, table, pairs) -> list[Pair]:
        """Process pairs, add rows to table with styling and filtering."""
        display_pairs = []
        for p in pairs:
            cmd_text = Text(p.command, style="bold")
            type_text = Text(p.kind, style=self._type_style(p.kind), justify="center")

            # Compute change by comparing file contents (excluding header line)
            try:
                changed = self._pair_changed(p)
            except (OSError, UnicodeError) as e:
                log(f"Failed to determine if files changed for pair {p.command}: {e}")
                changed = False

            # Filter when 'changes only' is enabled
            if self._changes_only and not changed:
                continue

            # Use symbols: ✓ for changed, ✗ for no change
            chg_text = Text(
                "✓" if changed else "✗",
                style=("bold green" if changed else "bold orange1"),
                justify="center"
            )
            sep1 = Text("│", style="dim")
            sep2 = Text("│", style="dim")

            # Add row to table
            row_key = (p.new_path, p.old_path, p.kind)
            self._add_table_row(table, type_text, sep1, chg_text, sep2, cmd_text, row_key)
            display_pairs.append(p)
        return display_pairs

    def _type_style(self, kind: str) -> str:
        """Return the style string for a pair type."""
        kind_upper = (kind or "").upper()
        if kind_upper == "DIFF":
            return "bold yellow"
        if kind_upper == "SAME":
            return "bold green"
        return "bold white"

    def _add_table_row(
        self, table: Any, type_text: str, sep1: str, chg_text: str, sep2: str, cmd_text: str, row_key: str
    ) -> None:
        """Add a row to the table with fallback error handling."""
        try:
            table.add_row(type_text, sep1, chg_text, sep2, cmd_text, key=row_key)  # type: ignore[call-arg]
        except (AttributeError, ValueError) as e:
            log(f"Failed to add row with key to table: {e}")
            table.add_row(type_text, sep1, chg_text, sep2, cmd_text)

    def _restore_selection_and_focus(
        self, table: Any, display_pairs: list[Pair], prev_key: tuple[str, str, str] | None
    ) -> None:
        """Restore the previous selection and set focus to the table."""
        try:
            # Restore selection by key when possible
            target_row = 0
            if prev_key is not None:
                target_row = self._find_target_row(table, display_pairs, prev_key)
            table.move_cursor(row=target_row, column=0)
            self.set_focus(table)
        except (AttributeError, ValueError, IndexError) as e:
            log(f"Failed to set table cursor position: {e}")
            pass

    def _find_target_row(
        self, table: Any, display_pairs: list[Pair], prev_key: tuple[str, str, str] | None
    ) -> int:
        """Find the target row index to restore selection to."""
        target_row = 0
        try:
            get_row_index = getattr(table, 'get_row_index', None)
            if callable(get_row_index):
                idx = get_row_index(prev_key)
                if isinstance(idx, int) and 0 <= idx < len(display_pairs):
                    target_row = idx
            else:
                for idx, dp in enumerate(display_pairs):
                    if (dp.new_path, dp.old_path, dp.kind) == prev_key:
                        target_row = idx
                        break
        except (AttributeError, ValueError, IndexError) as e:
            log(f"Failed to restore table selection: {e}")
            pass
        return target_row

    # Note: filenames are intentionally not shown in the table per request.

    def _pair_changed(self, p: Pair) -> bool:
        """Return True if the compared files differ in content (excluding header)."""
        a, b = None, None
        if p.kind == "DIFF":
            a, b = p.old_path, p.new_path
        else:  # SAME compares two most-recent NEW files already stored in pair
            a, b = p.old_path, p.new_path
        if not a or not b or not os.path.isfile(a) or not os.path.isfile(b):
            return False
        try:
            # Fast-path: if sizes and mtimes are identical, assume unchanged
            sa, sb = os.stat(a), os.stat(b)
            if sa.st_size == sb.st_size and int(sa.st_mtime) == int(sb.st_mtime):
                return False
            la = self._read_content_lines(a)
            lb = self._read_content_lines(b)
            return la != lb
        except (OSError, UnicodeError, ValueError) as e:
            log(f"Failed to compare files {a} and {b}: {e}")
            return False

    def _read_content_lines(self, file_path: str) -> list[str]:
        """Read file as list of lines, skipping the first line (header)."""
        lines, _enc = read_lines(file_path)
        return lines[1:] if lines else []

    def _find_pairs(self) -> list[Pair]:
        """Compute DIFF and SAME pairs for all discovered commands."""
        # Build maps of command -> list of file paths for NEW and OLD
        new_map = self._scan_folder(self.new_folder_path)
        old_map = self._scan_folder(self.old_folder_path)

        items: list[Pair] = []

        # DIFF rows: exists in both NEW and OLD; pick latest of each
        for cmd in sorted(set(new_map.keys()) & set(old_map.keys()), key=str.lower):
            new_path = max(new_map[cmd], key=self._safe_mtime)
            old_path = max(old_map[cmd], key=self._safe_mtime)
            items.append(Pair(cmd, new_path, old_path, kind="DIFF"))

        # SAME rows: command appears multiple times in NEW; compare most recent vs second most recent
        for cmd, files in new_map.items():
            if len(files) >= 2:
                latest_two = sorted(files, key=self._safe_mtime, reverse=True)[:2]
                items.append(Pair(cmd, latest_two[0], latest_two[1], kind="SAME"))

        # Sort by command, then by kind (DIFF before SAME), then by newest filename
        def sort_key(p: Pair):
            kind_order = 0 if p.kind == "DIFF" else 1
            return (p.command.lower(), kind_order, os.path.basename(p.new_path).lower())

        items.sort(key=sort_key)
        return items

    def _safe_mtime(self, path: str) -> float:
        try:
            return os.path.getmtime(path)
        except OSError as e:
            log(f"Failed to get mtime for {path}: {e}")
            return 0.0

    def _scan_folder(self, base: str | None) -> dict[str, list[str]]:
        """Return mapping of command -> file paths found under base (recursive)."""
        result: dict[str, list[str]] = {}
        if not base or not os.path.isdir(base):
            return result
        for root, _dirs, files in os.walk(base):
            for name in files:
                fp = os.path.join(root, name)
                if not os.path.isfile(fp):
                    continue
                # Extract command between quotes on first line
                cmd = self._first_line_command(fp)
                if not cmd:
                    continue
                result.setdefault(cmd, []).append(fp)
        return result

    def _first_line_command(self, file_path: str) -> str | None:
        """Extract the quoted command from the header line, if present."""
        # Centralized multi-encoding read
        lines, _enc = read_lines(file_path)
        if not lines:
            return None
        return self._extract_command(lines[0])

    def _extract_command(self, line: str) -> str | None:
        """Return text between first and last quotes in a header line."""
        if not line:
            return None
        m = re.search(r'"(.*)"', line)
        return m.group(1) if m else None

    def action_toggle_changes_only(self) -> None:
        """Toggle showing only comparisons with changes."""
        try:
            self._changes_only = not self._changes_only
            footer = self.query_one(Footer)
            footer.update(Text.from_markup(self.get_footer_text()))
            self._scan_and_populate()
        except (AttributeError, RuntimeError) as e:
            log(f"Failed to toggle changes only filter: {e}")
            pass

    def on_key(self, event: Any) -> None:
        """Handle key events for table navigation and actions."""
        # Prepare tables dictionary for navigation handler
        tables = {
            'compare': self._table
        }

        # Handle navigation events through the integrated handler
        handled = self._navigation.handle_key_event(
            event,
            self.screen.focused,
            tables,
            enter_callback=self._handle_enter_key,
            navigation_callback=None  # No special navigation callback needed
        )

        # Let other events pass through if not handled by navigation
        if not handled:
            return

    def _handle_enter_key(self) -> None:
        """Handle enter key for opening the selected comparison pair."""
        try:
            self._open_selected_pair()
        except (AttributeError, RuntimeError) as e:
            log(f"Failed to handle enter key for table selection: {e}")
            pass

    def _open_selected_pair(self) -> None:
        table = self._table
        if not table or not getattr(self, '_display_pairs', None):
            return
        try:
            coord = table.cursor_coordinate
            if coord is None:
                return
            row_index = getattr(coord, 'row', None)
            if row_index is None or row_index < 0 or row_index >= len(self._display_pairs):
                return
            pair = self._display_pairs[row_index]
            # Navigation context removed; open only the selected pair
            if not hasattr(self, '_navigator') or self._navigator is None:
                self._navigator = create_navigator(self.app)
            self._navigator.open_diff_viewer(
                new_path=pair.new_path,
                old_path=pair.old_path,
                keywords_path=self.keywords_path,
            )
        except (AttributeError, ValueError, IndexError, ImportError) as e:
            log(f"Failed to open selected comparison pair: {e}")
            pass

    # --- Actions for help/discoverability ---
    def action_next_row(self) -> None:
        table = self._table
        if not table:
            return
        try:
            coord = table.cursor_coordinate
            cur = getattr(coord, 'row', 0) if coord is not None else 0
        except (AttributeError, ValueError) as e:
            log(f"Failed to get current table cursor position: {e}")
            cur = 0
        try:
            total = getattr(table, 'row_count', None)
            if total is None:
                total = len(getattr(table, 'rows', []))
        except (AttributeError, ValueError) as e:
            log(f"Failed to get table row count: {e}")
            total = 0
        if total:
            try:
                table.move_cursor(row=min(cur + 1, total - 1), column=0)
                scroll_to_row = getattr(table, 'scroll_to_row', None)
                if callable(scroll_to_row):
                    scroll_to_row(min(cur + 1, total - 1))
                else:
                    scroll_to_cursor = getattr(table, 'scroll_to_cursor', None)
                    if callable(scroll_to_cursor):
                        scroll_to_cursor()
            except (AttributeError, RuntimeError) as e:
                log(f"Failed to move cursor to next row: {e}")
                pass

    def action_prev_row(self) -> None:
        table = self._table
        if not table:
            return
        try:
            coord = table.cursor_coordinate
            cur = getattr(coord, 'row', 0) if coord is not None else 0
        except (AttributeError, ValueError) as e:
            log(f"Failed to get current table cursor position: {e}")
            cur = 0
        try:
            # row_count may not exist on older versions; fallback to rows length
            total = getattr(table, 'row_count', None)
            if total is None:
                total = len(getattr(table, 'rows', []))
        except (AttributeError, ValueError) as e:
            log(f"Failed to get table row count: {e}")
            total = 0
        if total:
            try:
                table.move_cursor(row=max(cur - 1, 0), column=0)
                scroll_to_row = getattr(table, 'scroll_to_row', None)
                if callable(scroll_to_row):
                    scroll_to_row(max(cur - 1, 0))
                else:
                    scroll_to_cursor = getattr(table, 'scroll_to_cursor', None)
                    if callable(scroll_to_cursor):
                        scroll_to_cursor()
            except (AttributeError, RuntimeError) as e:
                log(f"Failed to move cursor to previous row: {e}")
                pass

    def action_end(self) -> None:
        table = self._table
        if not table:
            return
        try:
            total = getattr(table, 'row_count', None)
            if total is None:
                total = len(getattr(table, 'rows', []))
        except (AttributeError, ValueError) as e:
            log(f"Failed to get table row count: {e}")
            total = 0
        if total:
            try:
                table.move_cursor(row=total - 1, column=0)
                scroll_to_row = getattr(table, 'scroll_to_row', None)
                if callable(scroll_to_row):
                    scroll_to_row(total - 1)
                else:
                    scroll_to_cursor = getattr(table, 'scroll_to_cursor', None)
                    if callable(scroll_to_cursor):
                        scroll_to_cursor()
            except (AttributeError, RuntimeError) as e:
                log(f"Failed to move cursor to end row: {e}")
                pass
