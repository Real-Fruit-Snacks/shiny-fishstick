from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Static

from delta_vision.utils.base_screen import BaseTableScreen
from delta_vision.utils.config import config
from delta_vision.utils.io import read_text
from delta_vision.utils.keyword_highlighter import highlighter
from delta_vision.utils.keywords_scanner import KeywordScanner, ScanResult
from delta_vision.utils.logger import log
from delta_vision.utils.table_navigation import TableNavigationHandler
from delta_vision.utils.watchdog import start_observer

from .keywords_parser import parse_keywords_md


@dataclass
class KwFileHit:
    count: int = 0
    first_line_no: int = 0
    first_preview: str = ""
    # All occurrences for this file: list of (line_no, preview)
    lines: list[tuple[int, str]] = field(default_factory=list)


class KeywordsScreen(BaseTableScreen):
    BINDINGS = [
        ("q", "go_back", "Back"),
        ("enter", "open_selected", "Open"),
        ("h", "toggle_hits_only", "Hits Only"),
        ("c", "clear_filter", "Clear"),
    ]

    CSS_PATH = "keywords.tcss"

    def __init__(self, new_folder_path: str | None, old_folder_path: str | None, keywords_path: str | None):
        super().__init__(page_name="Keywords")
        self.new_folder_path = new_folder_path
        self.old_folder_path = old_folder_path
        self.keywords_path = keywords_path

        # UI widgets
        self._table = None
        self._details_table = None
        self._filter = None
        self._hits_btn = None
        self._status = None

        # Data structures
        self._keywords = []
        self._kw_color_by_word = {}
        self._kw_category_by_word = {}
        # Summary aggregated across files (per keyword)
        self._summary = {}
        # Bounded-memory: per-file keyword counts only (no per-line storage)
        # _file_kw_counts[side][file_path][keyword] = count
        self._file_kw_counts = {"NEW": {}, "OLD": {}}
        # Track file meta to skip unchanged (mtime,int + size)
        self._file_meta = {"NEW": {}, "OLD": {}}
        self._row_keywords = []

        # Settings/state
        self._hits_only = True  # default Hits: On
        self._detail_rows = []
        # preserve right-table selection when kw unchanged
        self._current_kw = None

        # Watchdog observers
        self._observer_new = None
        self._observer_old = None
        self._stop_new = None
        self._stop_old = None

        # Background scanning and navigation
        self._scanner = KeywordScanner(max_files=config.max_files, max_preview_chars=config.max_preview_chars)
        self._scanner.set_completion_callback(self._on_scan_complete)
        self._navigation = TableNavigationHandler()


    def compose_main_content(self) -> ComposeResult:
        with Vertical(id="kw-root"):
            with Vertical(id="kw-toolbar"):
                with Horizontal(id="kw-toolbar-row"):
                    # Left: buttons
                    _label = f"Hits: {'On' if self._hits_only else 'Off'}"
                    _variant = "success" if self._hits_only else "error"
                    self._hits_btn = Button(
                        _label, id="kw-hits-only", variant=_variant)
                    yield self._hits_btn
                    yield Button("Clear", id="kw-clear", variant="warning")
                    # Expanding search input takes remaining width
                    self._filter = Input(
                        placeholder="Filter keywords…", id="kw-filter")
                    yield self._filter
                with Horizontal(id="kw-status-row"):
                    # Right-aligned lightweight status text
                    self._status = Static("", id="kw-status")
                    yield self._status
            with Horizontal(id="kw-body"):
                self._table = DataTable(id="kw-table")
                self._table.add_column("Keyword", key="kw", width=32)
                self._table.add_column("│", key="sep1", width=1)
                self._table.add_column(
                    Text("Category", justify="center"), key="cat", width=12)
                self._table.add_column("│", key="sep2", width=1)
                self._table.add_column(
                    Text("NEW", justify="center"), key="new", width=4)
                self._table.add_column("│", key="sep3", width=1)
                self._table.add_column(
                    Text("OLD", justify="center"), key="old", width=4)
                self._table.add_column("│", key="sep4", width=1)
                self._table.add_column(
                    Text("Total", justify="center"), key="total", width=5)
                yield self._table
                # Right-side table for exact matches (no file column)
                self._details_table = DataTable(id="kw-details")
                self._details_table.add_column(
                    Text("Side", justify="center"), key="side", width=6)
                self._details_table.add_column("│", key="dsep1", width=1)
                self._details_table.add_column(
                    Text("Line", justify="center"), key="line", width=6)
                self._details_table.add_column("│", key="dsep2", width=1)
                self._details_table.add_column("Preview", key="preview")
                yield self._details_table

    def get_footer_text(self) -> str:
        return (
            " [orange1]q[/orange1] Back    [orange1]Enter[/orange1] Open    "
            "[orange1]H[/orange1] Hits Only    [orange1]C[/orange1] Clear"
        )

    async def on_mount(self):
        await super().on_mount()  # This handles table setup and title
        # Setup the details table which isn't the main _table
        if self._details_table:
            self.setup_data_table(self._details_table)

        self._load_keywords()
        # Kick off background scan; UI will populate when done
        self._start_scan()
        if self._filter:
            self.safe_set_focus(self._filter)

        # Start watchers for live updates when NEW/OLD folders change
        def trigger_refresh():
            if self.app:
                # Schedule a conditional rescan that avoids flicker when only atime changes
                self.app.call_later(self._maybe_rescan)

        try:
            if self.new_folder_path and os.path.isdir(self.new_folder_path):
                # Use a higher debounce to coalesce bursts from large trees
                self._observer_new, self._stop_new = start_observer(
                    self.new_folder_path, trigger_refresh, debounce_ms=1000)
        except OSError:
            log("Could not start file watcher for NEW folder")
            self._observer_new = None
            self._stop_new = None
        try:
            if self.old_folder_path and os.path.isdir(self.old_folder_path):
                self._observer_old, self._stop_old = start_observer(
                    self.old_folder_path, trigger_refresh, debounce_ms=1000)
        except OSError:
            log("Could not start file watcher for OLD folder")
            self._observer_old = None
            self._stop_old = None

    def on_unmount(self):
        # Stop observers when leaving the screen
        try:
            stop_new = getattr(self, "_stop_new", None)
            if callable(stop_new):
                stop_new()
        except AttributeError:
            log("Could not stop NEW folder watcher")
            pass
        try:
            stop_old = getattr(self, "_stop_old", None)
            if callable(stop_old):
                stop_old()
        except AttributeError:
            log("Could not stop OLD folder watcher")
            pass
        # Observers are stopped via their stop callbacks above
        self._observer_new = None
        self._observer_old = None
        self._stop_new = None
        self._stop_old = None
        # Stop background scanning
        try:
            self._scanner.stop_scan()
        except (AttributeError, RuntimeError):
            log("Could not stop background scanner")
            pass

    # Background scanning
    def _maybe_rescan(self) -> None:
        """Trigger a background rescan only if file mtimes/sizes changed.

        This avoids re-running a full scan in response to metadata-only events
        like atime updates that can be generated by our own reads on some
        filesystems. We do a cheap mtime/size pass without reading file
        contents; if nothing relevant changed, we leave the UI as-is.
        """
        try:
            if not self._keywords:
                return
            if self._scanner.is_scanning():
                # A scan is already underway; scanner will handle pending
                return
            # Check for relevant changes before scanning
            if self._has_relevant_changes():
                self._start_scan()
        except (AttributeError, RuntimeError):
            log("Error in maybe_rescan, falling back to full scan")
            # Fallback: if anything goes wrong, do the safe thing and scan.
            self._start_scan()

    def _has_relevant_changes(self) -> bool:
        """Return True if NEW/OLD trees differ from our cached snapshot.

        Only checks existence, size, and mtime; does not read file contents.
        """
        def side_changed(side: str, base: str | None) -> bool:
            if not base or not os.path.isdir(base):
                # If previously had entries but base is now missing, that's a change
                return bool(self._file_meta.get(side))
            seen = set()
            try:
                for root, _dirs, files in os.walk(base):
                    for name in files:
                        p = os.path.join(root, name)
                        try:
                            st = os.stat(p)
                            meta = (int(st.st_mtime), int(st.st_size))
                        except OSError:
                            log(f"Could not stat file {p} during change detection")
                            # Treat failures as a change to refresh later
                            return True
                        seen.add(p)
                        prev = self._file_meta.get(side, {}).get(p)
                        if prev != meta:
                            return True
                # Also detect deletions
                for old_p in self._file_meta.get(side, {}).keys():
                    if old_p not in seen:
                        return True
            except OSError:
                log(f"Could not walk directory {base} during change detection")
                return True
            return False

        return side_changed("NEW", self.new_folder_path) or side_changed("OLD", self.old_folder_path)
    def _start_scan(self):
        """Start background scanning."""
        try:
            if not self._keywords:
                return
            self._set_status("Scanning…")
            self._scanner.start_scan(self._keywords, self.new_folder_path, self.old_folder_path)
        except Exception as e:
            log(f"Error starting scan: {e}")
            self._set_status("Error starting scan")

    def _set_status(self, text: str) -> None:
        try:
            if self._status is not None:
                self._status.update(text)
        except AttributeError:
            log("Could not update status widget")
            pass

    def _on_scan_complete(self, result: ScanResult):
        """Called when background scan completes."""
        try:
            # Update data with scan results
            self._update_data_from_scan_result(result)

            # Update UI
            if self.app:
                self.app.call_later(self._finish_scan_update)
        except Exception as e:
            log(f"Error processing scan results: {e}")

    def _update_data_from_scan_result(self, result: ScanResult):
        """Update internal data structures from scan result."""
        # Convert KeywordFileHit summary to our internal format
        summary = {}
        for kw, _hit_info in result.summary.items():
            # Build summary statistics like the original code
            new_count = sum(result.file_counts.get("NEW", {}).get(fp, {}).get(kw, 0)
                           for fp in result.file_counts.get("NEW", {}))
            old_count = sum(result.file_counts.get("OLD", {}).get(fp, {}).get(kw, 0)
                           for fp in result.file_counts.get("OLD", {}))
            new_files = sum(1 for counts in result.file_counts.get("NEW", {}).values()
                           if counts.get(kw, 0) > 0)
            old_files = sum(1 for counts in result.file_counts.get("OLD", {}).values()
                           if counts.get(kw, 0) > 0)

            summary[kw] = {
                "NEW": new_count,
                "OLD": old_count,
                "TOTAL": new_count + old_count,
                "NEW_FILES": new_files,
                "OLD_FILES": old_files
            }

        self._summary = summary
        self._file_kw_counts = result.file_counts
        self._file_meta = result.file_meta

    def _finish_scan_update(self):
        """Finish updating UI after scan completion."""
        try:
            self._set_status("Watching for changes")
            self._populate_table()
        except Exception as e:
            log(f"Error updating UI after scan: {e}")


    def on_button_pressed(self, event):
        if event.button.id == "kw-clear" and self._filter:
            self.action_clear_filter()
        elif event.button.id == "kw-hits-only":
            # Toggle hits-only mode and update button label
            self.action_toggle_hits_only()

    def action_toggle_hits_only(self):
        self._hits_only = not self._hits_only
        try:
            if self._hits_btn:
                self._hits_btn.label = f"Hits: {'On' if self._hits_only else 'Off'}"
                # Change button color based on state
                self._hits_btn.variant = "success" if self._hits_only else "error"
                try:
                    self._hits_btn.refresh()
                except (AttributeError, RuntimeError):
                    log("Could not refresh hits button")
                    pass
        except AttributeError:
            log("Could not update hits button properties")
            pass
        self._populate_table()

    def action_clear_filter(self):
        try:
            if self._filter:
                self._filter.value = ""
        except AttributeError:
            log("Could not clear filter input")
            pass
        self._populate_table()
        # Return focus to the filter for quick typing
        try:
            if self._filter:
                self.set_focus(self._filter)
        except (AttributeError, RuntimeError):
            log("Could not set focus to filter input")
            pass

    def on_input_changed(self, event: Input.Changed):
        if event.input.id == "kw-filter":
            self._populate_table()

    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "kw-filter":
            # Refresh results and move focus to the keywords table
            self._populate_table()
            if self._table:
                try:
                    self.set_focus(self._table)
                except (AttributeError, RuntimeError):
                    log("Could not set focus to table")
                    pass

    def on_data_table_row_selected(self, event):
        if event.data_table.id == "kw-table":
            try:
                self.set_focus(self._table)
            except (AttributeError, RuntimeError):
                log("Could not set focus to keywords table")
                pass
            self._populate_details_for_selected()
        elif event.data_table.id == "kw-details":
            try:
                self.set_focus(self._details_table)
            except (AttributeError, RuntimeError):
                log("Could not set focus to details table")
                pass
            # Do not auto-open on selection; Enter will open explicitly

    # Keep details in sync when left table selection changes via mouse or keys
    def on_data_table_cell_selected(self, event):  # DataTable.CellSelected
        try:
            if getattr(event, 'data_table', None) is self._table:
                self._populate_details_for_selected()
        except AttributeError:
            log("Could not populate details for selected keyword")
            pass

    def on_data_table_row_highlighted(self, event):  # DataTable.RowHighlighted
        try:
            if getattr(event, 'data_table', None) is self._table:
                self._populate_details_for_selected()
        except AttributeError:
            log("Could not populate details for highlighted row")
            pass

    # DataTable.CellHighlighted
    def on_data_table_cell_highlighted(self, event):
        try:
            if getattr(event, 'data_table', None) is self._table:
                self._populate_details_for_selected()
        except AttributeError:
            log("Could not populate details for highlighted cell")
            pass

    def _load_keywords(self):
        self._keywords = []
        self._kw_color_by_word = {}
        self._kw_category_by_word = {}
        if not self.keywords_path or not os.path.isfile(self.keywords_path):
            return
        try:
            parsed = parse_keywords_md(self.keywords_path)
        except (OSError, FileNotFoundError, ValueError):
            log(f"Could not parse keywords file {self.keywords_path}")
            parsed = {}
        for cat, (color, words) in parsed.items():
            for w in words:
                self._keywords.append(w)
                self._kw_color_by_word[w] = (color or "yellow").lower()
                self._kw_category_by_word[w] = cat
        self._keywords.sort(key=str.lower)

    # Helper: iterate files containing a keyword on a side
    def _iter_files_for_keyword(self, side: str, kw: str):
        files_map = self._file_kw_counts.get(side, {})
        for file_path, counts in files_map.items():
            if counts.get(kw, 0) > 0 and os.path.isfile(file_path):
                yield file_path

    def _populate_table(self):
        """Populate keywords table - orchestrator for table population."""
        if not self._table:
            return

        # Capture current state and clear table
        prev_kw, prev_row_index = self._capture_table_selection_state()
        self._clear_table()

        # Prepare and filter keywords
        filter_text = self._get_filter_text()
        sorted_keywords = self._get_sorted_keywords()

        # Build table rows
        self._build_keyword_table_rows(sorted_keywords, filter_text)

        # Restore selection and update details
        self._restore_table_selection(prev_kw, prev_row_index)
        self._populate_details_for_selected()

    def _capture_table_selection_state(self) -> tuple[str | None, int]:
        """Capture current table selection state for restoration."""
        prev_kw = None
        prev_row_index = 0
        try:
            coord = getattr(self._table, 'cursor_coordinate', None)
            prev_row_index = getattr(coord, 'row', 0) if coord is not None else 0
            if isinstance(prev_row_index, int) and 0 <= prev_row_index < len(self._row_keywords):
                prev_kw = self._row_keywords[prev_row_index]
        except (AttributeError, IndexError):
            log("Could not get previous keyword selection")
            prev_kw = None
        return prev_kw, prev_row_index

    def _clear_table(self):
        """Clear the table and reset row keywords list."""
        self._table.clear()
        self._row_keywords = []

    def _get_filter_text(self) -> str:
        """Get current filter text from filter widget."""
        return (self._filter.value if self._filter else "").strip().lower()

    def _get_sorted_keywords(self) -> list[str]:
        """Get keywords sorted by total count (highest first)."""
        keys = list(self._keywords)
        keys.sort(key=lambda k: self._summary.get(k, {}).get("TOTAL", 0), reverse=True)
        return keys

    def _build_keyword_table_rows(self, sorted_keywords: list[str], filter_text: str):
        """Build and add all keyword table rows."""
        for kw in sorted_keywords:
            if self._should_include_keyword(kw, filter_text):
                self._add_keyword_table_row(kw)

    def _should_include_keyword(self, keyword: str, filter_text: str) -> bool:
        """Check if keyword should be included based on filters."""
        # Filter by text
        if filter_text and filter_text not in keyword.lower():
            return False

        # Filter by hits-only mode
        summary = self._summary.get(keyword, {"NEW": 0, "OLD": 0, "TOTAL": 0, "NEW_FILES": 0, "OLD_FILES": 0})
        if self._hits_only and summary.get("TOTAL", 0) == 0:
            return False

        return True

    def _add_keyword_table_row(self, keyword: str):
        """Add a single keyword row to the table."""
        summary = self._summary.get(keyword, {"NEW": 0, "OLD": 0, "TOTAL": 0, "NEW_FILES": 0, "OLD_FILES": 0})
        color = self._kw_color_by_word.get(keyword, "yellow")
        category = self._kw_category_by_word.get(keyword, "")

        # Create table cells
        kw_text = keyword
        category_cell = self._create_category_cell(category, color)
        new_cell = Text(str(summary.get("NEW", 0)), justify="center")
        old_cell = Text(str(summary.get("OLD", 0)), justify="center")
        total_cell = Text(str(summary.get("TOTAL", 0)), justify="center")

        # Add row with separators
        self._table.add_row(
            kw_text,
            self._create_separator_cell(),
            category_cell,
            self._create_separator_cell(),
            new_cell,
            self._create_separator_cell(),
            old_cell,
            self._create_separator_cell(),
            total_cell,
        )
        self._row_keywords.append(keyword)

    def _create_category_cell(self, category: str, color: str) -> Text:
        """Create category cell with appropriate formatting."""
        if category:
            cat_cell = Text.from_markup(f"[{color}]{category}[/{color}]")
        else:
            cat_cell = Text("")
        cat_cell.justify = "center"
        return cat_cell

    def _create_separator_cell(self) -> Text | str:
        """Create separator cell for table columns."""
        try:
            return Text("│", style="grey37")
        except (AttributeError, RuntimeError):
            log("Could not create separator cell")
            return "|"

    def _restore_table_selection(self, prev_kw: str | None, prev_row_index: int):
        """Restore previous table selection if possible."""
        target_row = self._determine_target_row(prev_kw, prev_row_index)
        self._move_table_cursor_to_row(target_row)

    def _determine_target_row(self, prev_kw: str | None, prev_row_index: int) -> int:
        """Determine which row to select after table rebuild."""
        try:
            if prev_kw and prev_kw in self._row_keywords:
                return self._row_keywords.index(prev_kw)
            elif isinstance(prev_row_index, int) and 0 <= prev_row_index < len(self._row_keywords):
                return prev_row_index
        except (AttributeError, ValueError, IndexError):
            log("Could not determine target row for table selection")
        return 0

    def _move_table_cursor_to_row(self, target_row: int):
        """Move table cursor to specified row."""
        try:
            if self._table and self._row_keywords:
                self._table.move_cursor(row=target_row, column=0)
        except (AttributeError, RuntimeError):
            log("Could not move table cursor to target row")

    def _populate_details_for_selected(self):
        """Populate details table for selected keyword - orchestrator for detail view population."""
        if not self._table or not self._details_table:
            return

        # Get selected keyword and previous cursor position
        kw = self._get_selected_keyword()
        if not kw:
            return

        prev_row, prev_col = self._capture_details_cursor_position()
        self._clear_details_table()

        # Populate details for both sides
        self._add_keyword_side_details(kw, "NEW")
        self._add_keyword_side_details(kw, "OLD")

        # Restore cursor and update state
        self._restore_details_cursor(kw, prev_row, prev_col)
        self._update_current_keyword(kw)

    def _get_selected_keyword(self) -> str | None:
        """Get the currently selected keyword from the main table."""
        try:
            coord = getattr(self._table, 'cursor_coordinate', None)
            row_index = getattr(coord, 'row', 0) if coord is not None else 0
            if isinstance(row_index, int) and 0 <= row_index < len(self._row_keywords):
                return self._row_keywords[row_index]
        except (AttributeError, IndexError):
            log("Could not get selected keyword from table")
        return None

    def _capture_details_cursor_position(self) -> tuple[int, int]:
        """Capture current cursor position in details table."""
        try:
            dt = self._details_table
            if dt and getattr(dt, 'cursor_coordinate', None) is not None:
                prev_row = getattr(dt.cursor_coordinate, 'row', 0)
                prev_col = getattr(dt.cursor_coordinate, 'column', 0)
                return prev_row, prev_col
        except AttributeError:
            log("Could not get previous details table cursor position")
        return 0, 0

    def _clear_details_table(self):
        """Clear the details table and reset detail rows."""
        dt = self._details_table
        if dt:
            try:
                dt.clear()
                self._detail_rows = []
            except (AttributeError, RuntimeError):
                log("Could not clear details table")

    def _add_keyword_side_details(self, keyword: str, side: str):
        """Add keyword match details for one side (NEW or OLD)."""
        color = self._kw_color_by_word.get(keyword, "yellow")
        kw_pattern = self._create_keyword_pattern(keyword)

        for file_path in self._iter_files_for_keyword(side, keyword):
            self._process_file_for_keyword(file_path, keyword, side, color, kw_pattern)

    def _create_keyword_pattern(self, keyword: str) -> re.Pattern:
        """Create compiled regex pattern for keyword matching."""
        return re.compile(rf"(?<!\w)({re.escape(keyword)})(?!\w)", re.IGNORECASE)

    def _process_file_for_keyword(self, file_path: str, keyword: str, side: str, color: str, pattern: re.Pattern):
        """Process a single file for keyword matches."""
        text, _enc = read_text(file_path)
        if not text:
            return

        for line_num, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                self._create_keyword_match_row(line, line_num, side, color, pattern, file_path)

    def _create_keyword_match_row(
        self, line: str, line_num: int, side: str, color: str, pattern: re.Pattern, file_path: str
    ):
        """Create and add a table row for a keyword match."""
        # Trim preview around first match
        plain = self._trim_line_preview(line, pattern)

        # Create highlighted preview using centralized highlighter
        highlighted = highlighter.highlight_with_pattern(
            text=plain,
            pattern=pattern,
            color=color,
            underline=False
        )

        # Create table cells
        side_cell = self._create_side_cell(side)
        line_cell = Text(str(line_num), justify="center")

        # Add row to table
        self._add_details_table_row(side_cell, line_cell, highlighted, line_num, file_path)

    def _trim_line_preview(self, line: str, pattern: re.Pattern) -> str:
        """Trim line to preview length, centering around first match."""
        if len(line) <= config.max_preview_chars:
            return line

        match = pattern.search(line)
        if match:
            start = max(0, match.start() - config.max_preview_chars // 2)
            end = start + config.max_preview_chars
            return line[start:end]
        else:
            return line[:config.max_preview_chars]

    def _create_side_cell(self, side: str) -> Text:
        """Create side indicator cell (NEW/OLD)."""
        if side == "NEW":
            side_cell = Text.from_markup("[green]NEW[/green]")
        else:
            side_cell = Text.from_markup("[yellow]OLD[/yellow]")
        side_cell.justify = "center"
        return side_cell

    def _add_details_table_row(self, side_cell: Text, line_cell: Text, highlighted: str, line_num: int, file_path: str):
        """Add a row to the details table."""
        dt = self._details_table
        if dt:
            try:
                dsep = Text("│", style="grey37")
                dt.add_row(side_cell, dsep, line_cell, dsep, Text.from_markup(highlighted))
                self._detail_rows.append((file_path, line_num))
            except (AttributeError, RuntimeError):
                log("Could not add row to details table")

    def _restore_details_cursor(self, keyword: str, prev_row: int, prev_col: int):
        """Restore cursor position in details table."""
        dt = self._details_table
        try:
            if dt and getattr(dt, 'row_count', 0):
                # Preserve row/col when keyword didn't change; otherwise reset to top
                if getattr(self, '_current_kw', None) == keyword:
                    target_row = max(0, min(prev_row, dt.row_count - 1))
                    target_col = max(0, prev_col)
                else:
                    target_row = 0
                    target_col = 0
                dt.move_cursor(row=target_row, column=target_col)
        except (AttributeError, RuntimeError):
            log("Could not set details table cursor position")

    def _update_current_keyword(self, keyword: str):
        """Update current keyword tracker."""
        self._current_kw = keyword

    def action_open_selected(self):
        # If details table focused, open selected hit
        if self._details_table:
            try:
                if self.screen.focused == self._details_table:
                    coord = getattr(self._details_table,
                                    'cursor_coordinate', None)
                    if coord is None:
                        return
                    row_index = getattr(coord, 'row', None)
                    if row_index is None:
                        return
                    if row_index < 0 or row_index >= len(self._detail_rows):
                        return
                    file_path, line_no = self._detail_rows[row_index]

                    if not hasattr(self, '_navigator') or self._navigator is None:
                        from delta_vision.utils.screen_navigation import create_navigator
                        self._navigator = create_navigator(self.app)

                    self._navigator.open_file_viewer(
                        file_path=file_path,
                        line_no=line_no,
                        keywords_path=self.keywords_path,
                        keywords_enabled=True,
                    )
                    return
            except (AttributeError, IndexError):
                log("Could not open selected file from details table")
                pass
        return

    def on_key(self, event):
        """Handle key events for table navigation and actions."""
        # Prepare tables dictionary for navigation handler
        tables = {
            'main': self._table,
            'details': self._details_table
        }

        # Handle special cases first
        key = getattr(event, 'key', None)

        # Arrow keys need special handling for details refresh
        if key in ('up', 'down', 'left', 'right', 'home', 'end', 'pageup', 'pagedown'):
            if self._table:
                # Let default navigation happen, then refresh details
                self._schedule_details_refresh()
            return  # Let default navigation occur

        # Use navigation handler for enter and vim keys
        handled = self._navigation.handle_key_event(
            event,
            self.screen.focused,
            tables,
            enter_callback=self._handle_enter_key,
            navigation_callback=self._on_navigation_change
        )

        if handled:
            # Check if we need to refresh details after vim navigation
            if key in ('j', 'k', 'g', 'G') and self.screen.focused == self._table:
                self._populate_details_for_selected()

    def _handle_enter_key(self):
        """Handle Enter key press for opening selected item."""
        try:
            if self._details_table and self.screen.focused == self._details_table:
                self.action_open_selected()
        except Exception as e:
            log(f"Error handling Enter key: {e}")

    def _on_navigation_change(self):
        """Called when navigation changes occur."""
        # This would be called after arrow key navigation if needed
        pass

    def _schedule_details_refresh(self):
        """Schedule details refresh after navigation."""
        try:
            self.set_timer(0.01, self._populate_details_for_selected)
        except (AttributeError, RuntimeError):
            log("Could not set timer for details refresh, trying call_later")
            if self.app:
                self.app.call_later(self._populate_details_for_selected)
