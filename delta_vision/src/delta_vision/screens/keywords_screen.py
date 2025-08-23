from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from rich.markup import escape
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Static

from delta_vision.utils.config import MAX_FILES, MAX_PREVIEW_CHARS
from delta_vision.utils.io import read_text
from delta_vision.utils.keywords_scanner import KeywordScanner, ScanResult
from delta_vision.utils.logger import log
from delta_vision.utils.table_navigation import TableNavigationHandler
from delta_vision.utils.watchdog import start_observer
from delta_vision.widgets.footer import Footer
from delta_vision.widgets.header import Header

from .keywords_parser import parse_keywords_md


@dataclass
class KwFileHit:
    count: int = 0
    first_line_no: int = 0
    first_preview: str = ""
    # All occurrences for this file: list of (line_no, preview)
    lines: list[tuple[int, str]] = field(default_factory=list)


class KeywordsScreen(Screen):
    BINDINGS = [
        ("q", "go_back", "Back"),
        ("enter", "open_selected", "Open"),
        ("h", "toggle_hits_only", "Hits Only"),
        ("c", "clear_filter", "Clear"),
    ]

    CSS_PATH = "keywords.tcss"

    def __init__(self, new_folder_path: str | None, old_folder_path: str | None, keywords_path: str | None):
        super().__init__()
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
        self._scanner = KeywordScanner(max_files=MAX_FILES, max_preview_chars=MAX_PREVIEW_CHARS)
        self._scanner.set_completion_callback(self._on_scan_complete)
        self._navigation = TableNavigationHandler()


    def compose(self) -> ComposeResult:
        yield Header(page_name="Keywords", show_clock=True)
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
        yield Footer(
            text=(
                " [orange1]q[/orange1] Back    [orange1]Enter[/orange1] Open    "
                "[orange1]H[/orange1] Hits Only    [orange1]C[/orange1] Clear"
            ),
            classes="footer-search",
        )

    def on_mount(self):
        self.title = "Delta Vision — Keywords"
        # Enable zebra striping for better row readability if supported
        try:
            if self._table and hasattr(self._table, "zebra_stripes"):
                self._table.zebra_stripes = True
            if self._details_table and hasattr(self._details_table, "zebra_stripes"):
                self._details_table.zebra_stripes = True
        except AttributeError:
            log("Could not set zebra_stripes on table widget")
            pass
        self._load_keywords()
        # Kick off background scan; UI will populate when done
        self._start_scan()
        if self._filter:
            self.set_focus(self._filter)

        # Start watchers for live updates when NEW/OLD folders change
        def trigger_refresh():
            if self.app:
                # Schedule a conditional rescan that avoids flicker when only atime changes
                self.app.call_later(self._maybe_rescan)

        import os as _os

        try:
            if self.new_folder_path and _os.path.isdir(self.new_folder_path):
                # Use a higher debounce to coalesce bursts from large trees
                self._observer_new, self._stop_new = start_observer(
                    self.new_folder_path, trigger_refresh, debounce_ms=1000)
        except OSError:
            log("Could not start file watcher for NEW folder")
            self._observer_new = None
            self._stop_new = None
        try:
            if self.old_folder_path and _os.path.isdir(self.old_folder_path):
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


    def action_go_back(self):
        try:
            self.app.pop_screen()
        except (AttributeError, RuntimeError):
            log("Could not pop screen")
            pass

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
        if not self._table:
            return
        # Capture current selection (by keyword) to restore after rebuild
        prev_kw = None
        prev_row_index = 0
        try:
            coord = getattr(self._table, 'cursor_coordinate', None)
            prev_row_index = getattr(
                coord, 'row', 0) if coord is not None else 0
            if isinstance(prev_row_index, int) and 0 <= prev_row_index < len(self._row_keywords):
                prev_kw = self._row_keywords[prev_row_index]
        except (AttributeError, IndexError):
            log("Could not get previous keyword selection")
            prev_kw = None
        self._table.clear()
        # Reusable dim separator cell

        def sep_cell():
            try:
                return Text("│", style="grey37")
            except (AttributeError, RuntimeError):
                log("Could not create separator cell")
                return "|"

        filter_text = (
            self._filter.value if self._filter else "").strip().lower()
        keys = list(self._keywords)
        keys.sort(key=lambda k: self._summary.get(
            k, {}).get("TOTAL", 0), reverse=True)
        self._row_keywords = []
        for kw in keys:
            if filter_text and filter_text not in kw.lower():
                continue
            s = self._summary.get(
                kw, {"NEW": 0, "OLD": 0, "TOTAL": 0, "NEW_FILES": 0, "OLD_FILES": 0})
            if self._hits_only and s.get("TOTAL", 0) == 0:
                continue
            color = self._kw_color_by_word.get(kw, "yellow")
            cat = self._kw_category_by_word.get(kw, "")
            # Show keyword as plain text; colorize the Category cell instead
            kw_text = kw  # left-aligned
            if cat:
                cat_cell = Text.from_markup(f"[{color}]{cat}[/{color}]")
            else:
                cat_cell = Text("")
            cat_cell.justify = "center"

            new_cell = Text(str(s.get("NEW", 0)), justify="center")
            old_cell = Text(str(s.get("OLD", 0)), justify="center")
            total_cell = Text(str(s.get("TOTAL", 0)), justify="center")

            self._table.add_row(
                kw_text,
                sep_cell(),
                cat_cell,
                sep_cell(),
                new_cell,
                sep_cell(),
                old_cell,
                sep_cell(),
                total_cell,
            )
            self._row_keywords.append(kw)
        # Restore selection if possible and refresh details
        target_row = 0
        try:
            if prev_kw and prev_kw in self._row_keywords:
                target_row = self._row_keywords.index(prev_kw)
            elif isinstance(prev_row_index, int) and 0 <= prev_row_index < len(self._row_keywords):
                target_row = prev_row_index
        except (AttributeError, ValueError, IndexError):
            log("Could not determine target row for table selection")
            target_row = 0
        try:
            if self._table and self._row_keywords:
                self._table.move_cursor(row=target_row, column=0)
        except (AttributeError, RuntimeError):
            log("Could not move table cursor to target row")
            pass
        self._populate_details_for_selected()

    def _populate_details_for_selected(self):
        if not self._table or not self._details_table:
            return
        dt = self._details_table
        # Resolve selected keyword via our row→keyword map
        kw = None
        try:
            coord = getattr(self._table, 'cursor_coordinate', None)
            row_index = getattr(coord, 'row', 0) if coord is not None else 0
            if isinstance(row_index, int) and 0 <= row_index < len(self._row_keywords):
                kw = self._row_keywords[row_index]
        except (AttributeError, IndexError):
            log("Could not get selected keyword from table")
            kw = None
        # Capture previous right-table cursor to preserve position when keyword stays the same
        prev_dt_row = 0
        prev_dt_col = 0
        try:
            if dt and getattr(dt, 'cursor_coordinate', None) is not None:
                prev_dt_row = getattr(dt.cursor_coordinate, 'row', 0)
                prev_dt_col = getattr(dt.cursor_coordinate, 'column', 0)
        except AttributeError:
            log("Could not get previous details table cursor position")
            prev_dt_row = 0
            prev_dt_col = 0
        if dt:
            try:
                dt.clear()
                self._detail_rows = []
            except (AttributeError, RuntimeError):
                log("Could not clear details table")
                pass
        if not kw:
            return

        def add_side(side: str):
            color = self._kw_color_by_word.get(kw, "yellow")
            kw_pat = re.compile(
                rf"(?<!\w)({re.escape(kw)})(?!\w)", re.IGNORECASE)
            for file_path in self._iter_files_for_keyword(side, kw):
                text, _enc = read_text(file_path)
                if not text:
                    continue
                for idx, line in enumerate(text.splitlines(), start=1):
                    if not kw_pat.search(line):
                        continue
                    # Trim preview around first match
                    plain = line
                    if len(plain) > MAX_PREVIEW_CHARS:
                        m = kw_pat.search(plain)
                        if m:
                            start = max(0, m.start() - MAX_PREVIEW_CHARS // 2)
                            end = start + MAX_PREVIEW_CHARS
                            plain = plain[start:end]
                        else:
                            plain = plain[:MAX_PREVIEW_CHARS]
                    safe_preview = escape(plain)
                    highlighted = kw_pat.sub(
                        lambda mm: f"[{color}]{mm.group(1)}[/{color}]", safe_preview)
                    side_cell = Text.from_markup(
                        "[green]NEW[/green]" if side == "NEW" else "[yellow]OLD[/yellow]")
                    side_cell.justify = "center"
                    line_cell = Text(str(idx), justify="center")
                    if dt:
                        try:
                            dsep = Text("│", style="grey37")
                            dt.add_row(side_cell, dsep, line_cell,
                                       dsep, Text.from_markup(highlighted))
                            self._detail_rows.append((file_path, idx))
                        except (AttributeError, RuntimeError):
                            log("Could not add row to details table")
                            pass

        add_side("NEW")
        add_side("OLD")
        # Ensure there is a visible selection in the details table
        try:
            if dt and getattr(dt, 'row_count', 0):
                # Preserve row/col when keyword didn't change; otherwise reset to top
                if getattr(self, '_current_kw', None) == kw:
                    target_row = max(0, min(prev_dt_row, dt.row_count - 1))
                    target_col = max(0, prev_dt_col)
                else:
                    target_row = 0
                    target_col = 0
                dt.move_cursor(row=target_row, column=target_col)
        except (AttributeError, RuntimeError):
            log("Could not set details table cursor position")
            pass
        # Update current keyword tracker
        self._current_kw = kw

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
                    from .file_viewer import FileViewerScreen

                    viewer = FileViewerScreen(
                        file_path, line_no, keywords_path=self.keywords_path)
                    self.app.push_screen(viewer)
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
