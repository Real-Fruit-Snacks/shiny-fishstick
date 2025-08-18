"""Search screen for DeltaVision.

This module implements a fast, keyboard-friendly search across the NEW and
OLD folders. It supports optional regex mode, a results summary, and a
DataTable listing matches with a preview.

Highlights:
- Debounced user input with explicit Enter to search.
- Clickable toggle for regex mode reflected in footer and button label.
- Row selection opens a focused file viewer at the selected line.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from time import perf_counter

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Static

from delta_vision.utils.io import read_text
from delta_vision.widgets.footer import Footer
from delta_vision.widgets.header import Header

from .file_viewer import FileViewerScreen


@dataclass
class Match:
    file_path: str
    line_no: int
    line: str
    cmd: str | None = None
    is_error: bool = False


class SearchScreen(Screen):
    """Search both the NEW and OLD folders for a query string.

    The screen provides an input bar and a results panel. Results are grouped
    by source and show a short preview around the match. Keyboard shortcuts
    are surfaced in the footer for discoverability.
    """

    BINDINGS = [
        ("q", "go_home", "Back"),
        ("r", "toggle_regex", "Regex"),
        ("j", "next_row", "Down"),
        ("k", "prev_row", "Up"),
        ("G", "end", "End"),
    ]

    CSS_PATH = "search.tcss"

    def __init__(
        self,
        new_folder_path: str | None = None,
        old_folder_path: str | None = None,
        keywords_path: str | None = None,
    ):
        super().__init__()
        self.new_folder_path = new_folder_path
        self.old_folder_path = old_folder_path
        self.keywords_path = keywords_path
        # UI references
        self._table = None  # DataTable
        self._input = None  # Input
        self._footer = None  # Footer
        # State
        self._regex_button = None  # Button
        self._regex_enabled = False
        # Tracks whether the previous key was a lone 'g' for gg behavior
        self._last_g = False
        # Keep last search results to resolve row -> file mapping
        self._last_results = []
        # Map table row index -> Match (or None for visual separator rows)
        self._row_map = []
        # Debounce + caps
        self._debounce_timer = None
        self._debounce_delay = 0.3  # seconds
        self._max_files = 5000
        self._max_preview_chars = 200  # cap preview length, centered on first match

    def compose(self) -> ComposeResult:
        """Build the static UI: header, toolbar, and results table."""
        yield Header(page_name="Search", show_clock=True)
        with Vertical(id="search-root"):
            with Horizontal(id="search-bar"):
                self._input = Input(
                    placeholder="Type to search…", id="search-input")
                yield self._input
                yield Button("Search", id="search-btn", variant="primary")
                # Clickable toggle for regex mode
                self._regex_button = Button(
                    self._regex_button_label(),
                    id="regex-toggle",
                    variant="warning",
                )
                yield self._regex_button
            # Results panel with a summary and table
            with Vertical(id="results-panel"):
                yield Static("Type a query and press Enter to search.", id="results-summary")
                self._table = DataTable(id="results-table")
                # Define columns with thin separators for a crisp grid look
                self._table.add_column(Text("Source"), key="source")
                self._table.add_column(
                    Text("│", style="dim", justify="center"), key="sep1", width=1)
                self._table.add_column(
                    Text("Line", justify="center"), key="line", width=6)
                self._table.add_column(
                    Text("│", style="dim", justify="center"), key="sep2", width=1)
                self._table.add_column(Text("Preview"), key="preview")
                yield self._table
        # Footer with hotkeys and regex toggle indicator
        self._footer = Footer(text=self._footer_text(),
                              classes="footer-search")
        yield self._footer

    def _footer_text(self) -> str:
        state = "ON" if self._regex_enabled else "OFF"
        return (
            " [orange1]q[/orange1] Back    "
            "[orange1]Enter[/orange1] Search    "
            f"[orange1]r[/orange1] Regex: {state}"
        )

    def _regex_button_label(self) -> str:
        return f"Regex: {'ON' if self._regex_enabled else 'OFF'}"

    # no helper needed for variant; set explicit literals when toggling

    def on_mount(self):
        """Initialize state after mounting and apply table polish if supported."""
        self.title = "Delta Vision — Search"
        if self._input:
            self.set_focus(self._input)
        # Optional visual polish for the table
        try:
            if self._table:
                # Enable zebra stripes and row-only cursor if supported
                if hasattr(self._table, "zebra_stripes"):
                    self._table.zebra_stripes = True
                if hasattr(self._table, "cursor_type"):
                    try:
                        self._table.cursor_type = "row"
                    except Exception:
                        pass
        except Exception:
            pass

    def action_go_home(self):
        """Return to the previous screen (Home)."""
        try:
            self.app.pop_screen()
        except Exception:
            pass

    def action_do_search(self):
        """Run the current query against NEW and OLD and populate results."""
        query = (self._input.value if self._input else "").strip()
        self.run_search(query)

    def action_toggle_regex(self):
        """Toggle regex mode and refresh UI indicators; re-run search if needed."""
        # Toggle regex mode and refresh footer and results
        self._regex_enabled = not self._regex_enabled
        try:
            if self._footer:
                self._footer.update(Text.from_markup(self._footer_text()))
            if self._regex_button:
                # Update the button label and color to reflect new state
                self._regex_button.label = self._regex_button_label()
                if self._regex_enabled:
                    self._regex_button.variant = "success"
                else:
                    self._regex_button.variant = "warning"
        except Exception:
            pass
        # Re-run search if there's a query
        query = (self._input.value if self._input else "").strip()
        if query:
            self.run_search(query)

    def on_button_pressed(self, event):
        """Handle toolbar button presses for Search and Regex toggle."""
        if event.button.id == "search-btn":
            self.action_do_search()
        elif event.button.id == "regex-toggle":
            self.action_toggle_regex()

    def on_input_submitted(self, event: Input.Submitted):
        """Enter in the input triggers a search."""
        # Trigger search when pressing Enter in the input field only
        self.action_do_search()

    def on_input_changed(self, event: Input.Changed):
        """Update hints live; do not auto-run the search on typing."""
        # Do not auto-run searches on typing; wait for Enter or button click
        if getattr(event.input, 'id', '') != 'search-input':
            return
        # Cancel previous timer if any (legacy)
        try:
            if self._debounce_timer is not None:
                self._debounce_timer.stop()
                self._debounce_timer = None
        except Exception:
            pass
        value = (event.value or '').strip()
        if not value:
            # Clear results and reset summary when input is empty
            try:
                if self._table:
                    self._table.clear()
                summary = self.query_one('#results-summary', Static)
                summary.update("Type a query and press Enter to search.")
            except Exception:
                pass
            return
        # With non-empty input, just update the hint; do not run a search yet
        try:
            summary = self.query_one('#results-summary', Static)
            summary.update("Press Enter to search.")
        except Exception:
            pass

    def on_data_table_row_selected(self, event):  # DataTable.RowSelected
        """Ensure focus follows selection so j/k navigation works reliably."""
        # Ensure the table has focus when a row is selected (mouse click)
        try:
            if self._table:
                self.set_focus(self._table)
        except Exception:
            pass

    def _open_selected_row(self):
        """Open a FileViewer at the currently selected result row, if any."""
        table = self._table
        if not table or not self._row_map:
            return
        try:
            coord = table.cursor_coordinate
            if coord is None:
                return
            row_index = getattr(coord, 'row', None)
            if row_index is None:
                return
            if row_index < 0 or row_index >= len(self._row_map):
                return
            match = self._row_map[row_index]
            if match is None or getattr(match, 'is_error', False):
                return
            # Push viewer screen
            viewer = FileViewerScreen(
                match.file_path, match.line_no, keywords_path=self.keywords_path)
            self.app.push_screen(viewer)
        except Exception:
            pass

    def on_key(self, event):
        # Vim-like navigation for results table and Enter-to-open behavior
        table = self._table
        key = getattr(event, 'key', None)
        if not table or key is None:
            return

        # Enter on table opens viewer; let Enter bubble if focus is not on table
        if key == 'enter':
            try:
                if self.screen.focused == table:
                    event.stop()
                    self._open_selected_row()
                    return
            except Exception:
                pass
            return

        if key in ('j', 'k', 'g', 'G'):
            # Move focus to table for vim-like navigation and stop propagation
            try:
                self.set_focus(table)
            except Exception:
                pass
            try:
                event.stop()
            except Exception:
                pass

            # Helpers scoped here
            def get_pos():
                cur = 0
                try:
                    coord = table.cursor_coordinate
                    if coord is not None:
                        cur = getattr(coord, 'row', 0)
                except Exception:
                    pass
                try:
                    total = getattr(table, 'row_count', None)
                    if total is None:
                        total = len(getattr(table, 'rows', []))
                except Exception:
                    total = 0
                return cur, total

            def set_row(r):
                try:
                    table.move_cursor(row=r, column=0)
                    try:
                        scroll_to_row = getattr(table, 'scroll_to_row', None)
                        if callable(scroll_to_row):
                            scroll_to_row(r)
                        else:
                            scroll_to_cursor = getattr(
                                table, 'scroll_to_cursor', None)
                            if callable(scroll_to_cursor):
                                scroll_to_cursor()
                    except Exception:
                        pass
                except Exception:
                    pass

            if key == 'j':
                cur, total = get_pos()
                if total:
                    set_row(min(cur + 1, total - 1))
                self._last_g = False
            elif key == 'k':
                cur, total = get_pos()
                if total:
                    set_row(max(cur - 1, 0))
                self._last_g = False
            elif key == 'G':
                _cur, total = get_pos()
                if total:
                    set_row(total - 1)
                self._last_g = False
            elif key == 'g':
                if self._last_g:
                    set_row(0)
                    self._last_g = False
                else:
                    self._last_g = True
            else:
                self._last_g = False

    # --- Search logic ---
    def run_search(self, query: str):
        if not self._table:
            return
        # Capture current selection key to restore after rebuild
        prev_key: str | None = None
        try:
            coord = self._table.cursor_coordinate
            if coord is not None:
                row_index = getattr(coord, 'row', None)
                if row_index is not None and 0 <= row_index < len(self._row_map):
                    cur_match = self._row_map[row_index]
                    if cur_match is not None:
                        prev_key = f"{cur_match.file_path}:{cur_match.line_no}"
        except Exception:
            prev_key = None
        try:
            self._table.clear()
        except Exception:
            pass
        self._row_map = []
        if not query:
            return

        # Aggregate folders to search; only existing directories
        folders: list[str] = []
        for p in [self.new_folder_path, self.old_folder_path]:
            if p and os.path.isdir(p):
                folders.append(p)

        # Build pattern depending on regex mode
        try:
            if self._regex_enabled:
                # egrep-like: treat query as a regex (approximate with Python re)
                pattern = re.compile(query, re.IGNORECASE)
            else:
                # Substring search when regex is off
                pattern = re.compile(re.escape(query), re.IGNORECASE)
        except re.error as e:
            # Invalid regex: show message in summary and stop
            try:
                summary = self.query_one('#results-summary', Static)
                summary.update(f"[Invalid regex: {e}]")
            except Exception:
                pass
            return

        matches: list[Match] = []
        files_scanned: int = 0
        start_time = perf_counter()
        stop_scan = False
        for folder in folders:
            try:
                for root, _dirs, files in os.walk(folder):
                    if stop_scan:
                        break
                    for name in files:
                        file_path = os.path.join(root, name)
                        if not os.path.isfile(file_path):
                            continue
                        files_scanned += 1
                        if files_scanned > self._max_files:
                            stop_scan = True
                            break
                        # Centralized multi-encoding read
                        text, _enc = read_text(file_path)
                        # Extract command from first line if present (in quotes)
                        cmd_str: str | None = None
                        try:
                            if text:
                                first = text.splitlines()[0]
                                mcmd = re.search(r'"([^"]+)"', first)
                                cmd_str = mcmd.group(
                                    1) if mcmd else first.strip()
                        except Exception:
                            cmd_str = None
                        # Skip empty files entirely - they shouldn't appear in search results
                        if not text:
                            continue
                        for idx, line in enumerate(text.splitlines(), start=1):
                            mobj = pattern.search(line)
                            if mobj:
                                original = line.rstrip("\n")
                                preview = original
                                if len(original) > self._max_preview_chars:
                                    # Center preview around first match span
                                    span_start, span_end = mobj.span()
                                    center = (span_start + span_end) // 2
                                    half = self._max_preview_chars // 2
                                    start = max(0, center - half)
                                    end = start + self._max_preview_chars
                                    if end > len(original):
                                        end = len(original)
                                        start = max(
                                            0, end - self._max_preview_chars)
                                    snippet = original[start:end]
                                    prefix = "…" if start > 0 else ""
                                    suffix = "…" if end < len(original) else ""
                                    preview = f"{prefix}{snippet}{suffix}"
                                matches.append(
                                    Match(file_path, idx, preview, cmd_str))
                    if stop_scan:
                        break
            except Exception as e:
                # Add a row indicating folder error
                matches.append(
                    Match(folder, 0, f"[Error reading folder: {e}]", None, True))
        elapsed = perf_counter() - start_time

        # Sort by path then line number for determinism
        matches.sort(key=lambda m: (m.file_path.lower(), m.line_no))

        # Update summary with match count, error count, files scanned, and duration
        try:
            summary = self.query_one('#results-summary', Static)
            capped_note = " (capped)" if files_scanned > self._max_files else ""
            match_count = sum(
                1 for _m in matches if not _m.is_error and _m.line_no > 0)
            error_count = sum(1 for _m in matches if _m.is_error)
            err_fragment = f"; [red]{error_count}[/red] error(s)" if error_count else ""
            summary.update(
                Text.from_markup(
                    f"Found [bold]{match_count}[/bold] match(es) across "
                    f"[bold]{files_scanned}[/bold] file(s){capped_note}{err_fragment} "
                    f"in [bold]{elapsed:.3f}s[/bold] for: '[magenta]{query}[/magenta]'"
                )
            )
        except Exception:
            pass

        # Compute hits per file for display
        hits_per_file: dict[str, int] = {}
        for m in matches:
            if m.file_path not in hits_per_file:
                hits_per_file[m.file_path] = 0
            if m.line_no > 0:
                hits_per_file[m.file_path] += 1

        # Populate table with source (NEW/OLD) and command from header; style errors distinctly
        for _i, m in enumerate(matches):
            src_text: Text | None = None
            if m.is_error:
                src_text = Text("[ERR] ", style="bold red")
                cmd_display = (m.cmd or os.path.basename(m.file_path)).strip()
                src_text.append(cmd_display, style="red")
                preview_text = Text(f"⚠ {m.line}", style="red")
                line_text = Text("-", style="red", justify="center")
            else:
                label = ""
                for base in folders:
                    if m.file_path.startswith(base):
                        label = (
                            "NEW" if base == self.new_folder_path else (
                                "OLD" if base == self.old_folder_path else "")
                        )
                        break
                if label:
                    label_color = "green" if label == "NEW" else "yellow"
                    src_text = Text(f"[{label}] ", style=f"bold {label_color}")
                else:
                    src_text = Text("")
                # Append the command (or a fallback) with neutral styling
                cmd_display = (m.cmd or "").strip()
                if not cmd_display:
                    cmd_display = os.path.basename(m.file_path)
                src_text.append(cmd_display, style="white")
                # If this file has multiple hits, append a dim count indicator
                try:
                    count = hits_per_file.get(m.file_path, 0)
                    if count and count > 1:
                        src_text.append(f"  ×{count}", style="dim")
                except Exception:
                    pass

                # Highlight matches in the preview using Rich Text
                try:
                    preview_text = Text(m.line)
                    for match in pattern.finditer(m.line):
                        start, end = match.span()
                        preview_text.stylize("bold magenta", start, end)
                except Exception:
                    preview_text = Text(m.line)

                line_text = Text(
                    str(m.line_no) if m.line_no else "-", justify="center")
            sep = Text("│", style="dim", justify="center")
            # Assign a stable string row key when supported by Textual
            row_key = f"{m.file_path}:{m.line_no}"
            try:
                self._table.add_row(src_text, sep, line_text,
                                    sep, preview_text, key=row_key)
            except Exception:
                self._table.add_row(
                    src_text, sep, line_text, sep, preview_text)
            self._row_map.append(m)

        # Remember results for row mapping
        self._last_results = matches

        # Move focus to results and set initial cursor if we have any matches
        if matches and self._table:
            try:
                # Restore previous selection if possible, else default to first row
                target_row = 0
                if prev_key is not None:
                    try:
                        # Prefer DataTable API to find row by key if available
                        get_row_index = getattr(
                            self._table, 'get_row_index', None)
                        if callable(get_row_index):
                            idx = get_row_index(prev_key)
                            if isinstance(idx, int) and 0 <= idx < len(self._row_map):
                                target_row = idx
                        else:
                            # Fallback: search our row map
                            for idx, mm in enumerate(self._row_map):
                                if mm and f"{mm.file_path}:{mm.line_no}" == prev_key:
                                    target_row = idx
                                    break
                    except Exception:
                        pass
                try:
                    self._table.move_cursor(row=target_row, column=0)
                except Exception:
                    pass
                self.set_focus(self._table)
            except Exception:
                pass

    # --- Actions for help/discoverability ---
    def action_next_row(self):
        table = self._table
        if not table:
            return
        try:
            coord = table.cursor_coordinate
            cur = getattr(coord, 'row', 0) if coord is not None else 0
        except Exception:
            cur = 0
        try:
            total = getattr(table, 'row_count', None)
            if total is None:
                total = len(getattr(table, 'rows', []))
        except Exception:
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
            except Exception:
                pass
        self._last_g = False

    def action_prev_row(self):
        table = self._table
        if not table:
            return
        try:
            coord = table.cursor_coordinate
            cur = getattr(coord, 'row', 0) if coord is not None else 0
        except Exception:
            cur = 0
        if True:
            try:
                table.move_cursor(row=max(cur - 1, 0), column=0)
                scroll_to_row = getattr(table, 'scroll_to_row', None)
                if callable(scroll_to_row):
                    scroll_to_row(max(cur - 1, 0))
                else:
                    scroll_to_cursor = getattr(table, 'scroll_to_cursor', None)
                    if callable(scroll_to_cursor):
                        scroll_to_cursor()
            except Exception:
                pass
        self._last_g = False

    def action_end(self):
        table = self._table
        if not table:
            return
        try:
            total = getattr(table, 'row_count', None)
            if total is None:
                total = len(getattr(table, 'rows', []))
        except Exception:
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
            except Exception:
                pass
        self._last_g = False
