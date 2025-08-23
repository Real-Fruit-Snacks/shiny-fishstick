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
        self._search_config = SearchConfig(max_files=5000, max_preview_chars=200)
        self._search_engine = SearchEngine(self._search_config)

        # Table navigation handler
        self._navigation = TableNavigationHandler()

        # Keyword highlighting
        self._keyword_highlighter = KeywordHighlighter()
        self._keywords_dict = self._load_keywords_dict()

    def on_mount(self) -> None:
        """Setup initial state when screen mounts."""
        super().on_mount()
        # Store the current theme to detect changes
        self._current_theme = self.app.theme if self.app else None

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
        """Initialize state after mounting and set focus on input."""
        await super().on_mount()  # This handles table setup and title
        if self._input:
            self.safe_set_focus(self._input)


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
            )
        except (AttributeError, ValueError, IndexError) as e:
            log(f"Failed to open selected row: {e}")
            pass

    def on_key(self, event):
        """Handle key events for table navigation and actions."""
        # Prepare tables dictionary for navigation handler
        tables = {
            'results': self._table
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

            # Apply keyword highlighting first if enabled
            if self._keywords_enabled and self._keywords_dict:
                pattern, keyword_lookup = self._keyword_highlighter.get_pattern_and_lookup(self._keywords_dict)
                if pattern and keyword_lookup:
                    highlighted_line = self._keyword_highlighter.highlight_line(
                        line, pattern, keyword_lookup, underline=False
                    )

            # Convert to Text object for search query highlighting
            if self._keywords_enabled and self._keywords_dict:
                preview_text = Text.from_markup(highlighted_line)
            else:
                preview_text = Text(line)

            # Apply search query highlighting on top of keyword highlighting
            query = self._input.value if self._input else ""
            if query:
                if self._regex_enabled:
                    search_pattern = re.compile(query, re.IGNORECASE)
                else:
                    search_pattern = re.compile(re.escape(query), re.IGNORECASE)

                # Find search matches and highlight them with theme-appropriate colors
                plain_line = line  # Use original line for pattern matching
                highlight_style = self._get_theme_highlight_style()
                for match in search_pattern.finditer(plain_line):
                    start, end = match.span()
                    # Use theme-appropriate style for search matches that will overlay keyword highlighting
                    preview_text.stylize(highlight_style, start, end)

            return preview_text
        except (AttributeError, ValueError, re.error) as e:
            log(f"Failed to highlight matches in preview: {e}")
            return Text(line)

    def _get_theme_highlight_style(self) -> str:
        """Get theme-appropriate highlight style with best aesthetic and contrast balance."""
        try:
            # Get current theme object
            current_theme = self.app.get_theme(self.app.theme) if self.app else None
            
            if current_theme:
                # Try theme colors in order of preference for highlighting
                # Avoid harsh warning/error colors, prefer softer accent/secondary colors
                candidate_colors = [
                    current_theme.accent,     # Usually a pleasant accent color
                    current_theme.secondary,  # Secondary theme color
                    current_theme.primary,    # Primary theme color
                    current_theme.success,    # Success color (often green)
                    current_theme.warning,    # Warning color (yellow/orange) - last resort
                ]
                
                # Find the first color that provides good contrast and aesthetics
                for bg_color in candidate_colors:
                    if bg_color:
                        # Calculate contrast and pick best text color
                        fg_color = self._get_readable_text_color(bg_color)
                        
                        # Avoid harsh combinations (white text on very bright colors)
                        if self._is_good_highlight_combination(bg_color, fg_color):
                            return f"bold {fg_color} on {bg_color}"
                
                # If no good combination found, fall back to a softer approach
                return self._get_fallback_highlight_style(current_theme)
            
        except (AttributeError, ValueError) as e:
            log(f"Failed to get theme colors for highlighting: {e}")
        
        # Ultimate fallback to guaranteed readable style
        return "bold black on yellow"

    def _get_readable_text_color(self, bg_hex: str) -> str:
        """Calculate the most readable text color (black or white) for given background."""
        try:
            luminance = self._get_luminance(bg_hex)
            
            # Use white text on dark backgrounds, black text on light backgrounds
            # Threshold of 0.5 provides good contrast in most cases
            return "#FFFFFF" if luminance < 0.5 else "#000000"
            
        except (ValueError, IndexError) as e:
            log(f"Failed to calculate readable text color for {bg_hex}: {e}")
            # Fallback to black (safe for most yellow/orange backgrounds)
            return "#000000"

    def _is_good_highlight_combination(self, bg_color: str, fg_color: str) -> bool:
        """Check if a background/foreground color combination is aesthetically pleasing."""
        try:
            # Get luminance of background color
            bg_luminance = self._get_luminance(bg_color)
            
            # Avoid very bright backgrounds with white text (harsh to read)
            if fg_color == "#FFFFFF" and bg_luminance > 0.7:
                return False
                
            # Avoid very dark backgrounds with black text (poor contrast)
            if fg_color == "#000000" and bg_luminance < 0.3:
                return False
                
            # Otherwise it's a good combination
            return True
            
        except (ValueError, IndexError):
            # If we can't determine, assume it's okay
            return True

    def _get_luminance(self, hex_color: str) -> float:
        """Calculate the luminance of a hex color (0.0 = black, 1.0 = white)."""
        try:
            hex_color = hex_color.lstrip('#')
            r = int(hex_color[0:2], 16) / 255.0
            g = int(hex_color[2:4], 16) / 255.0  
            b = int(hex_color[4:6], 16) / 255.0
            
            # Gamma correction for sRGB
            def gamma_correct(c):
                return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
            
            r_linear = gamma_correct(r)
            g_linear = gamma_correct(g)
            b_linear = gamma_correct(b)
            
            return 0.2126 * r_linear + 0.7152 * g_linear + 0.0722 * b_linear
            
        except (ValueError, IndexError):
            return 0.5  # Medium luminance fallback

    def _get_fallback_highlight_style(self, theme) -> str:
        """Get a fallback highlight style when no theme colors work well."""
        try:
            # For dark themes, use a subtle light background with dark text
            if getattr(theme, 'dark', True):  # Default to dark theme behavior
                return "bold #1F2430 on #CCCAC2"  # Dark text on light background
            else:
                # For light themes, use a subtle dark background with light text  
                return "bold #CCCAC2 on #1F2430"  # Light text on dark background
                
        except (AttributeError, ValueError):
            return "bold black on yellow"  # Ultimate fallback

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
    def action_next_row(self):
        table = self._table
        if not table:
            return
        try:
            coord = table.cursor_coordinate
            cur = getattr(coord, 'row', 0) if coord is not None else 0
        except (AttributeError, ValueError) as e:
            log(f"Failed to get current cursor position for next row: {e}")
            cur = 0
        try:
            total = getattr(table, 'row_count', None)
            if total is None:
                total = len(getattr(table, 'rows', []))
        except (AttributeError, ValueError) as e:
            log(f"Failed to get table row count for next row: {e}")
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
                log(f"Failed to move to next row: {e}")
                pass
        self._last_g = False

    def action_prev_row(self):
        table = self._table
        if not table:
            return
        try:
            coord = table.cursor_coordinate
            cur = getattr(coord, 'row', 0) if coord is not None else 0
        except (AttributeError, ValueError) as e:
            log(f"Failed to get current cursor position for previous row: {e}")
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
            except (AttributeError, RuntimeError) as e:
                log(f"Failed to move to previous row: {e}")
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
        except (AttributeError, ValueError) as e:
            log(f"Failed to get table row count for end action: {e}")
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
                log(f"Failed to move to end row: {e}")
                pass
        self._last_g = False
