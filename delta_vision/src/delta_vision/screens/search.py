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

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Static

from delta_vision.utils.base_screen import BaseTableScreen
from delta_vision.utils.config import config
from delta_vision.utils.keyword_highlighter import KeywordHighlighter
from delta_vision.utils.logger import log
from delta_vision.utils.screen_navigation import create_navigator
from delta_vision.utils.search_engine import (
    SearchConfig,
    SearchEngine,
    SearchMatch,
    count_matches_by_type,
    validate_folders,
)
from delta_vision.utils.table_navigation import TableNavigationHandler
from delta_vision.utils.theme_color_calculator import theme_calculator
from delta_vision.utils.watchdog import start_observer
from delta_vision.widgets.footer import Footer

from .keywords_parser import parse_keywords_md


class SearchScreen(BaseTableScreen):
    """Search both the NEW and OLD folders for a query string.

    The screen provides an input bar and a results panel. Results are grouped
    by source and show a short preview around the match. Keyboard shortcuts
    are surfaced in the footer for discoverability.
    """

    BINDINGS = [
        ("q", "go_back", "Back"),
        ("ctrl+r", "toggle_regex", "Regex"),
        ("ctrl+k", "toggle_keywords", "Keywords"),
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
        super().__init__(page_name="Search")
        self.new_folder_path = new_folder_path
        self.old_folder_path = old_folder_path
        self.keywords_path = keywords_path
        # UI references
        self._table = None  # DataTable
        self._input = None  # Input
        # State
        self._regex_button = None  # Button
        self._regex_enabled = False
        self._keywords_enabled = True  # Default enabled for search screen
        # Keep last search results to resolve row -> file mapping
        self._last_results = []
        # Map table row index -> SearchMatch (or None for visual separator rows)
        self._row_map = []
        # Debounce + caps
        self._debounce_timer = None
        self._debounce_delay = 0.3  # seconds

        # Search engine configuration
        self._search_config = SearchConfig(max_files=config.max_files, max_preview_chars=config.max_preview_chars)
        self._search_engine = SearchEngine(self._search_config)

        # Table navigation handler
        self._navigation = TableNavigationHandler()

        # Keyword highlighting
        self._keyword_highlighter = KeywordHighlighter()
        self._keywords_dict = self._load_keywords_dict()

        # Watchdog observers for live updates
        self._observer_new = None
        self._observer_old = None
        self._stop_new = None
        self._stop_old = None
        # Track if search results need refreshing due to file changes
        self._files_changed = False
        # Track last search query to detect if user has modified it
        self._last_search_query = ""

    def check_idle(self) -> None:
        """Check for theme changes during idle periods and refresh highlighting if needed."""
        try:
            super().check_idle()
        except Exception:
            # Safely handle cases where there's no active app context
            return

        # Check if the theme has changed since last check
        try:
            if self.app:
                current_theme = self.app.theme
                if hasattr(self, '_current_theme') and current_theme != self._current_theme:
                    self._current_theme = current_theme
                    self._refresh_search_highlighting()
        except Exception as e:
            # Log but don't crash on theme change detection errors
            log(f"[SEARCH] Error checking for theme changes: {e}")
            pass

    def _refresh_search_highlighting(self) -> None:
        """Refresh search result highlighting with current theme colors."""
        # Only refresh if we have existing search results to re-highlight
        if hasattr(self, '_last_results') and self._last_results and self._table:
            log(f"[SEARCH] Theme changed to {self._current_theme}, refreshing search highlighting")
            try:
                # Get the folders for the current search
                folders = []
                if self.new_folder_path:
                    folders.append(self.new_folder_path)
                if self.old_folder_path:
                    folders.append(self.old_folder_path)

                # Store current cursor position
                current_cursor = self._table.cursor_row

                # Re-populate the results table with new theme-aware highlighting
                self._populate_results_table(self._last_results, folders)

                # Restore cursor position
                if current_cursor is not None and current_cursor < self._table.row_count:
                    self._table.cursor_row = current_cursor

            except (AttributeError, RuntimeError) as e:
                log(f"[SEARCH] Failed to refresh highlighting after theme change: {e}")

    def _load_keywords_dict(self) -> dict | None:
        """Load keywords dictionary from file."""
        if not self.keywords_path:
            return None
        try:
            return parse_keywords_md(self.keywords_path)
        except Exception as e:
            log(f"Failed to load keywords from {self.keywords_path}: {e}")
            return None

    def compose_main_content(self) -> ComposeResult:
        """Build the main content: toolbar and results table."""
        with Vertical(id="search-root"):
            with Horizontal(id="search-bar"):
                self._input = Input(placeholder="Type to search…", id="search-input")
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
                self._table.add_column(Text("│", style="dim", justify="center"), key="sep1", width=1)
                self._table.add_column(Text("Line", justify="center"), key="line", width=6)
                self._table.add_column(Text("│", style="dim", justify="center"), key="sep2", width=1)
                self._table.add_column(Text("Preview"), key="preview")
                yield self._table

    def get_footer_text(self) -> str:
        regex_state = "ON" if self._regex_enabled else "OFF"
        keywords_state = "ON" if self._keywords_enabled else "OFF"
        return (
            f" [orange1]q[/orange1] Back    [orange1]Enter[/orange1] Search    "
            f"[orange1]Ctrl+R[/orange1] Regex: {regex_state}    [orange1]Ctrl+K[/orange1] Keywords: {keywords_state}"
        )

    def _regex_button_label(self) -> str:
        return f"Regex: {'ON' if self._regex_enabled else 'OFF'}"

    # no helper needed for variant; set explicit literals when toggling

    async def on_mount(self):
        """Initialize state after mounting, set focus on input, and setup theme detection."""
        await super().on_mount()  # This handles table setup and title

        # Store the current theme to detect changes
        self._current_theme = self.app.theme if self.app else None

        # Start watchdog observers for live updates
        self._start_folder_observers()

        if self._input:
            self.safe_set_focus(self._input)

    def _start_folder_observers(self):
        """Start file system observers for both NEW and OLD folders."""

        def trigger_refresh():
            """Callback for filesystem changes."""
            try:
                # Mark that files have changed
                self._files_changed = True
                # Only auto-refresh if user hasn't modified the search query
                current_query = (self._input.value if self._input else "").strip()
                if current_query == self._last_search_query and current_query:
                    self.call_later(self._refresh_search_results)
                else:
                    # Update summary to show that files changed
                    self.call_later(self._update_files_changed_indicator)
            except Exception as e:
                log(f"[ERROR] Failed in trigger_refresh: {e}")

        # Start observer for NEW folder
        try:
            if self.new_folder_path and os.path.isdir(self.new_folder_path):
                self._observer_new, self._stop_new = start_observer(
                    self.new_folder_path, trigger_refresh, debounce_ms=1000
                )
        except (OSError, RuntimeError) as e:
            log(f"Failed to start observer for NEW folder {self.new_folder_path}: {e}")
            self._observer_new = None
            self._stop_new = None

        # Start observer for OLD folder
        try:
            if self.old_folder_path and os.path.isdir(self.old_folder_path):
                self._observer_old, self._stop_old = start_observer(
                    self.old_folder_path, trigger_refresh, debounce_ms=1000
                )
        except (OSError, RuntimeError) as e:
            log(f"Failed to start observer for OLD folder {self.old_folder_path}: {e}")
            self._observer_old = None
            self._stop_old = None

    def _stop_folder_observers(self):
        """Stop all file system observers."""
        for stop_fn in (self._stop_new, self._stop_old):
            if stop_fn:
                try:
                    stop_fn()
                except Exception as e:
                    log(f"Failed to stop observer: {e}")

    def _refresh_search_results(self):
        """Refresh search results when files change, preserving user state."""
        if not self._last_search_query:
            return

        # Re-run the last search (run_search handles state preservation internally)
        self.run_search(self._last_search_query)

        # Mark that we've refreshed
        self._files_changed = False

    def _update_files_changed_indicator(self):
        """Update UI to indicate files have changed but search hasn't been refreshed."""
        if self._files_changed:
            try:
                summary = self.query_one('#results-summary', Static)
                current_text = summary.renderable
                if isinstance(current_text, Text):
                    # Add indicator that files have changed
                    new_text = Text()
                    new_text.append_text(current_text)
                    new_text.append(" [dim yellow](Files changed - press Enter to refresh)[/dim yellow]")
                    summary.update(new_text)
                elif isinstance(current_text, str) and "(Files changed" not in current_text:
                    summary.update(f"{current_text} [dim yellow](Files changed - press Enter to refresh)[/dim yellow]")
            except (AttributeError, RuntimeError) as e:
                log(f"Failed to update files changed indicator: {e}")

    def on_unmount(self):
        """Stop observers when leaving the screen."""
        self._stop_folder_observers()

    def action_do_search(self):
        """Run the current query against NEW and OLD and populate results."""
        query = (self._input.value if self._input else "").strip()
        self.run_search(query)

    def action_toggle_regex(self):
        """Toggle regex mode and refresh UI indicators; re-run search if needed."""
        # Toggle regex mode and refresh footer and results
        self._regex_enabled = not self._regex_enabled
        self._update_footer_and_button()
        # Re-run search if there's a query
        query = (self._input.value if self._input else "").strip()
        if query:
            self.run_search(query)

    def action_toggle_keywords(self):
        """Toggle keyword highlighting in search results preview."""
        self._keywords_enabled = not self._keywords_enabled
        self._update_footer_and_button()
        # Re-run search if there's a query to refresh the highlighting
        query = (self._input.value if self._input else "").strip()
        if query:
            self.run_search(query)

    def _update_footer_and_button(self):
        """Update footer text and regex button after state changes."""
        try:
            # Update footer
            footer = self.query_one(Footer)
            footer.update(Text.from_markup(self.get_footer_text()))

            # Update regex button if it exists
            if self._regex_button:
                self._regex_button.label = self._regex_button_label()
                if self._regex_enabled:
                    self._regex_button.variant = "success"
                else:
                    self._regex_button.variant = "warning"
        except (AttributeError, RuntimeError) as e:
            log(f"Failed to update footer/button: {e}")

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
        except (AttributeError, RuntimeError) as e:
            log(f"Failed to stop debounce timer: {e}")
            pass
        value = (event.value or '').strip()
        if not value:
            # Clear results and reset summary when input is empty
            try:
                if self._table:
                    self._table.clear()
                summary = self.query_one('#results-summary', Static)
                summary.update("Type a query and press Enter to search.")
            except (AttributeError, RuntimeError) as e:
                log(f"Failed to clear table and update summary: {e}")
                pass
            return
        # With non-empty input, just update the hint; do not run a search yet
        try:
            summary = self.query_one('#results-summary', Static)
            summary.update("Press Enter to search.")
        except (AttributeError, RuntimeError) as e:
            log(f"Failed to update search hint: {e}")
            pass

    def on_data_table_row_selected(self, event):  # DataTable.RowSelected
        """Ensure focus follows selection so j/k navigation works reliably."""
        # Ensure the table has focus when a row is selected (mouse click)
        if self._table:
            self.safe_set_focus(self._table)

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
            if not hasattr(self, '_navigator') or self._navigator is None:
                self._navigator = create_navigator(self.app)
            self._navigator.open_file_viewer(
                file_path=match.file_path,
                line_no=match.line_no,
                keywords_path=self.keywords_path,
                keywords_enabled=True,
            )
        except (AttributeError, ValueError, IndexError) as e:
            log(f"Failed to open selected row: {e}")
            pass

    def on_key(self, event):
        """Handle key events for table navigation and actions."""
        # Prepare tables dictionary for navigation handler
        tables = {'results': self._table}

        # Handle navigation events through the integrated handler
        handled = self._navigation.handle_key_event(
            event,
            self.screen.focused,
            tables,
            enter_callback=self._handle_enter_key,
            navigation_callback=None,  # No special navigation callback needed
        )

        # Let other events pass through if not handled by navigation
        if not handled:
            return

    def _handle_enter_key(self):
        """Handle Enter key press to open selected row."""
        try:
            self._open_selected_row()
        except (AttributeError, RuntimeError) as e:
            log(f"Failed to handle Enter key on table: {e}")

    # --- Search logic ---
    def run_search(self, query: str):
        """Main search entry point - orchestrates the entire search process."""
        if not self._table:
            return

        # Track the search query for live updates
        self._last_search_query = query
        # Clear files changed flag since we're running a fresh search
        self._files_changed = False

        prev_key = self._capture_current_selection()
        self._clear_results()

        if not query:
            return

        folders = self._get_search_folders()
        search_result = self._perform_search(query, folders)
        if search_result is None:
            return  # Error already shown in summary

        matches, files_scanned, elapsed = search_result
        self._update_search_summary(matches, query, elapsed, files_scanned)
        self._populate_results_table(matches, folders)

        # Extra defensive check before restoration - table might be corrupted in client mode
        if self._table and matches:
            self._restore_selection_and_focus(matches, prev_key)

    def _capture_current_selection(self) -> str | None:
        """Capture current table selection key for restoration after rebuild."""
        try:
            coord = self._table.cursor_coordinate
            if coord is not None:
                row_index = getattr(coord, 'row', None)
                if row_index is not None and 0 <= row_index < len(self._row_map):
                    cur_match = self._row_map[row_index]
                    if cur_match is not None:
                        return f"{cur_match.file_path}:{cur_match.line_no}"
        except (AttributeError, ValueError, IndexError) as e:
            log(f"Failed to capture current selection: {e}")
        return None

    def _clear_results(self):
        """Clear the results table and reset internal state."""
        try:
            self._table.clear()
        except (AttributeError, RuntimeError) as e:
            log(f"Failed to clear table: {e}")
        self._row_map = []

    def _get_search_folders(self) -> list[str]:
        """Get list of valid folders to search."""
        candidate_folders = [self.new_folder_path, self.old_folder_path]
        return validate_folders([f for f in candidate_folders if f])

    def _show_regex_error(self, error_msg: str):
        """Show regex compilation error in summary."""
        try:
            summary = self.query_one('#results-summary', Static)
            summary.update(f"[Invalid regex: {error_msg}]")
        except (AttributeError, RuntimeError) as e:
            log(f"Failed to update regex error summary: {e}")

    def _perform_search(self, query: str, folders: list[str]) -> tuple[list[SearchMatch], int, float] | None:
        """Perform the actual search using the search engine."""
        try:
            return self._search_engine.search_folders(query, folders, self._regex_enabled)
        except Exception as e:
            # Check if it's a regex error
            if "regex" in str(e).lower() or "pattern" in str(e).lower():
                self._show_regex_error(str(e))
                return None
            else:
                log(f"Search failed: {e}")
                return [], 0, 0.0

    def _update_search_summary(self, matches: list[SearchMatch], query: str, elapsed: float, files_scanned: int):
        """Update the search summary display with results."""
        try:
            summary = self.query_one('#results-summary', Static)
            capped_note = " (capped)" if files_scanned > self._search_config.max_files else ""
            match_count, error_count = count_matches_by_type(matches)
            err_fragment = f"; [red]{error_count}[/red] error(s)" if error_count else ""

            summary.update(
                Text.from_markup(
                    f"Found [bold]{match_count}[/bold] match(es) across "
                    f"[bold]{files_scanned}[/bold] file(s){capped_note}{err_fragment} "
                    f"in [bold]{elapsed:.3f}s[/bold] for: '[bold yellow]{query}[/bold yellow]'"
                )
            )
        except (AttributeError, RuntimeError) as e:
            log(f"Failed to update search summary: {e}")

    def _populate_results_table(self, matches: list[SearchMatch], folders: list[str]):
        """Populate the results table with formatted match data."""
        if not matches:
            return

        hits_per_file = self._compute_hits_per_file(matches)

        for m in matches:
            src_text, line_text, preview_text = self._format_table_row(m, folders, hits_per_file)
            sep = Text("│", style="dim", justify="center")
            row_key = f"{m.file_path}:{m.line_no}"

            try:
                self._table.add_row(src_text, sep, line_text, sep, preview_text, key=row_key)
            except (AttributeError, RuntimeError) as e:
                log(f"Failed to add row with key: {e}")
                self._table.add_row(src_text, sep, line_text, sep, preview_text)
            self._row_map.append(m)

        self._last_results = matches

    def _compute_hits_per_file(self, matches: list[SearchMatch]) -> dict[str, int]:
        """Compute the number of hits per file for display purposes."""
        hits_per_file = {}
        for m in matches:
            if m.file_path not in hits_per_file:
                hits_per_file[m.file_path] = 0
            if m.line_no > 0:
                hits_per_file[m.file_path] += 1
        return hits_per_file

    def _format_table_row(
        self, match: SearchMatch, folders: list[str], hits_per_file: dict[str, int]
    ) -> tuple[Text, Text, Text]:
        """Format a single table row for display."""
        if match.is_error:
            return self._format_error_row(match)
        else:
            return self._format_match_row(match, folders, hits_per_file)

    def _format_error_row(self, match: SearchMatch) -> tuple[Text, Text, Text]:
        """Format an error row for display."""
        src_text = Text("[ERR] ", style="bold red")
        cmd_display = (match.cmd or os.path.basename(match.file_path)).strip()
        src_text.append(cmd_display, style="red")
        preview_text = Text(f"⚠ {match.line}", style="red")
        line_text = Text("-", style="red", justify="center")
        return src_text, line_text, preview_text

    def _format_match_row(
        self, match: SearchMatch, folders: list[str], hits_per_file: dict[str, int]
    ) -> tuple[Text, Text, Text]:
        """Format a normal match row for display."""
        # Determine source label (NEW/OLD)
        label = ""
        for base in folders:
            if match.file_path.startswith(base):
                label = "NEW" if base == self.new_folder_path else ("OLD" if base == self.old_folder_path else "")
                break

        # Build source text with label and command
        if label:
            label_color = "green" if label == "NEW" else "yellow"
            src_text = Text(f"[{label}] ", style=f"bold {label_color}")
        else:
            src_text = Text("")

        cmd_display = (match.cmd or "").strip()
        if not cmd_display:
            cmd_display = os.path.basename(match.file_path)
        src_text.append(cmd_display, style="white")

        # Add hit count if multiple hits in this file
        try:
            count = hits_per_file.get(match.file_path, 0)
            if count and count > 1:
                src_text.append(f"  ×{count}", style="dim")
        except (AttributeError, ValueError) as e:
            log(f"Failed to append hit count to source text: {e}")

        # Create highlighted preview text
        preview_text = self._create_highlighted_preview(match.line)

        line_text = Text(str(match.line_no) if match.line_no else "-", justify="center")
        return src_text, line_text, preview_text

    def _create_highlighted_preview(self, line: str) -> Text:
        """Create highlighted preview text for search matches and keywords."""
        try:
            # Start with the base line
            highlighted_line = line

            # Apply keyword highlighting first if enabled (use same method as viewer screen)
            if self._keywords_enabled and self._keywords_dict:
                # Build color lookup like viewer screen
                keyword_lookup = {}
                sorted_keywords = []
                for _cat, (color, words) in self._keywords_dict.items():
                    for w in words:
                        keyword_lookup[w] = color
                sorted_keywords = sorted(keyword_lookup.keys(), key=len, reverse=True)

                if sorted_keywords:
                    highlighted_line = self._keyword_highlighter.highlight_with_color_lookup(
                        line, sorted_keywords, keyword_lookup, case_sensitive=False
                    )

            # Convert to Text object for search query highlighting
            if self._keywords_enabled and self._keywords_dict:
                preview_text = Text.from_markup(highlighted_line)
            else:
                preview_text = Text(line)

            # Apply search query highlighting - but only if it's not already a keyword
            query = self._input.value if self._input else ""
            if query:
                if self._regex_enabled:
                    search_pattern = re.compile(query, re.IGNORECASE)
                else:
                    search_pattern = re.compile(re.escape(query), re.IGNORECASE)

                # Find search matches
                plain_line = line  # Use original line for pattern matching
                for match in search_pattern.finditer(plain_line):
                    start, end = match.span()
                    matched_text = match.group(0)

                    # Check if this match is already a keyword with defined color
                    if self._keywords_enabled and self._keywords_dict:
                        # Build the same keyword lookup we used above
                        keyword_lookup = {}
                        for _cat, (color, words) in self._keywords_dict.items():
                            for w in words:
                                keyword_lookup[w] = color

                        is_keyword = matched_text.lower() in [k.lower() for k in keyword_lookup.keys()]

                        if is_keyword:
                            # Don't override keyword colors - they're already correct
                            continue

                    # Only apply theme-based highlighting to non-keyword matches
                    highlight_style = theme_calculator.get_highlight_style(self.app)
                    preview_text.stylize(highlight_style, start, end)

            return preview_text
        except (AttributeError, ValueError, re.error) as e:
            log(f"Failed to highlight matches in preview: {e}")
            return Text(line)

    def _restore_selection_and_focus(self, matches: list[SearchMatch], prev_key: str | None):
        """Restore previous selection and set focus to results table."""
        if not matches or not self._table:
            return

        try:
            # Double-check table validity before proceeding
            if not hasattr(self._table, 'move_cursor') or not hasattr(self._table, 'cursor_coordinate'):
                log("Table missing required methods, skipping restoration")
                return

            target_row = 0
            if prev_key is not None:
                try:
                    target_row = self._find_row_by_key(prev_key)
                except Exception as e:
                    log(f"Failed to find row by key: {e}")
                    target_row = 0

            # Validate target row is within bounds
            if hasattr(self._table, 'row_count'):
                row_count = getattr(self._table, 'row_count', 0)
                if target_row >= row_count:
                    target_row = max(0, row_count - 1)

            try:
                self._table.move_cursor(row=target_row, column=0)
            except Exception as e:
                log(f"Failed to set table cursor: {e}")

            try:
                self.safe_set_focus(self._table)
            except Exception as e:
                log(f"Failed to set focus on table: {e}")

        except Exception as e:
            log(f"Failed to restore selection after search: {e}")

    def _find_row_by_key(self, prev_key: str) -> int:
        """Find the row index matching the given key."""
        try:
            # Prefer DataTable API to find row by key if available
            get_row_index = getattr(self._table, 'get_row_index', None)
            if callable(get_row_index):
                idx = get_row_index(prev_key)
                if isinstance(idx, int) and 0 <= idx < len(self._row_map):
                    return idx
            else:
                # Fallback: search our row map
                for idx, mm in enumerate(self._row_map):
                    if mm and f"{mm.file_path}:{mm.line_no}" == prev_key:
                        return idx
        except (AttributeError, ValueError) as e:
            log(f"Failed to restore previous selection: {e}")
        return 0

    # --- Actions for help/discoverability ---
