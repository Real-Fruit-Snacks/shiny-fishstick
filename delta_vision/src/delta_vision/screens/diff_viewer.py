"""Side-by-side diff screen for comparing NEW vs OLD runs with optional tabs.

This screen renders two file panels (OLD on the left, NEW on the right),
ignoring each file's first line (treated as a header). It supports:
- Tabs to compare the latest NEW to prior NEWs or to the OLD file
- Optional keyword underlining (toggle with 'K')
- Vim-like scrolling keys (j/k/g/G) and tab navigation (h/l)
"""

from __future__ import annotations

import math
import os
import re
from difflib import SequenceMatcher

from rich.markup import escape
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, Tab, Tabs

from delta_vision.utils.base_screen import BaseScreen
from delta_vision.utils.config import config
from delta_vision.utils.diff_engine import DiffRow, DiffType, compute_diff_rows
from delta_vision.utils.file_parsing import parse_header_metadata, read_file_pair
from delta_vision.utils.fs import format_mtime, get_mtime, minutes_between
from delta_vision.utils.logger import log
from delta_vision.utils.text import make_keyword_pattern
from delta_vision.utils.watchdog import start_observer

from .keywords_parser import parse_keywords_md


class SideBySideDiffScreen(BaseScreen):
    """Show a side-by-side diff between two files (NEW vs OLD).

    The first line of each file (header) is ignored for the diff.
    """

    BINDINGS = [
        ("q", "go_back", "Back"),
        ("ctrl+k", "toggle_highlights", "Toggle Highlights"),
        ("h", "prev_tab", "Prev Tab"),
        ("l", "next_tab", "Next Tab"),
    ]

    CSS_PATH = "diff.tcss"

    # Extra layout rules to guarantee side-by-side panels
    DEFAULT_CSS = """
    #diff-root {
        width: 100%;
        height: 100%;
    }
    #diff-columns {
        width: 100%;
        height: 100%;
    }
    #diff-columns > .file-panel {
        width: 1fr;
        height: 1fr;
        margin: 1;
    }
    .file-content {
        height: 1fr;
        overflow: auto;
    }
    """
    # NOTE: Layout here ensures each panel fills half of the screen and the
    # scrollable text area grows to fit the remaining height under the title.

    def __init__(
        self,
        new_path: str,
        old_path: str,
        keywords_path: str | None = None,
        nav_pairs: list[tuple[str, str]] | None = None,
        nav_index: int | None = None,
    ) -> None:
        super().__init__(page_name="Diff")
        self.new_path = new_path
        self.old_path = old_path
        self.keywords_path = keywords_path
        # Optional navigation context
        self._nav_pairs = nav_pairs
        self._nav_index = nav_index
        # Tabs state
        self._tabs = None
        # Map tab.id -> (older_path, latest_path)
        self._tab_map = {}
        # Ordered list of tab ids for cycling
        self._tab_order = []
        # Track current active tab id
        self._active_tab_id = None
        # Panels and content
        self._left_panel = None
        self._right_panel = None
        self._left_content = None
        self._right_content = None
        # Vim-like state
        self._last_g = False
        # Keyword highlight state (enabled by default)
        self.keyword_highlight_enabled = True
        self._kw_pattern = None
        # Cache of built rows
        self._rows_cache = []
        # Per-side metadata parsed from header line
        self._old_meta = {"date": None, "time": None, "cmd": None}
        self._new_meta = {"date": None, "time": None, "cmd": None}
        # Filesystem modified timestamps (formatted)
        self._old_created = None
        self._new_created = None
        # Watchdog observers for live updates
        self._observer_old = None
        self._observer_new = None
        self._stop_old = None
        self._stop_new = None
        # Store scroll positions for state preservation
        self._left_scroll_y = 0
        self._right_scroll_y = 0

    def compose_main_content(self) -> ComposeResult:
        """Build tabs and two file panels for side-by-side diff.

        Note: Titles/subtitles and file contents are populated in
        ``on_mount`` once metadata and rows are available.
        """
        # Tabs to switch comparisons (latest vs OLD / latest vs previous runs)
        self._tabs = Tabs(id="diff-tabs")
        yield self._tabs
        with Vertical(id="diff-root"):
            with Horizontal(id="diff-columns"):
                # OLD panel
                self._left_panel = Vertical(
                    Static("", classes="file-title"),
                    Static("", classes="file-subtitle"),
                    Vertical(
                        Static("", classes="file-text", markup=True),
                        classes="file-content",
                    ),
                    classes="file-panel",
                )
                yield self._left_panel
                # NEW panel
                self._right_panel = Vertical(
                    Static("", classes="file-title"),
                    Static("", classes="file-subtitle"),
                    Vertical(
                        Static("", classes="file-text", markup=True),
                        classes="file-content",
                    ),
                    classes="file-panel",
                )
                yield self._right_panel

    def get_footer_text(self) -> str:
        """Return footer text with keybinding hints."""
        highlights_state = "ON" if self.keyword_highlight_enabled else "OFF"
        return f" [orange1]q[/orange1] Back    [orange1]Ctrl+K[/orange1] Highlights: {highlights_state}"

    async def on_mount(self):
        """Parse header metadata, build tabs, and render the initial view.

        - Derives command/date/time from the first line of each file
        - Builds a keyword regex (if provided) for optional underlining
        - Creates tabs for OLD and prior NEW occurrences and selects a default
        - Populates the left/right panels with the initial diff
        """
        await super().on_mount()  # This handles basic setup

        # Try to show command in the title, like the file viewer
        # Also parse date/time for subtitles
        self._new_meta = parse_header_metadata(self.new_path) or {"date": None, "time": None, "cmd": None}
        self._old_meta = parse_header_metadata(self.old_path) or {"date": None, "time": None, "cmd": None}
        cmd = self._new_meta.get("cmd") or self._old_meta.get("cmd")
        if cmd:
            self.title = f"{cmd} — Diff"
        # Filesystem modified timestamps
        self._old_created = format_mtime(self.old_path)
        self._new_created = format_mtime(self.new_path)
        # Build keyword pattern if provided
        try:
            if self.keywords_path and os.path.isfile(self.keywords_path):
                parsed = parse_keywords_md(self.keywords_path)
                words: list[str] = []
                for _cat, (_color, kws) in parsed.items():
                    words.extend(kws)
                self._kw_pattern = make_keyword_pattern(
                    words,
                    whole_word=True,
                    case_insensitive=True,
                )
        except (OSError, re.error, ValueError):
            log("Failed to build keyword pattern from keywords file")
            self._kw_pattern = None

        # Build tab set (latest vs others) and populate initial view
        try:
            self._build_tabs_and_select_default()
        except (OSError, AttributeError, RuntimeError):
            log("Failed to build tabs, falling back to basic diff view")
            # Fallback to the provided pair only
            old_lines, new_lines = read_file_pair(self.old_path, self.new_path)
            rows = compute_diff_rows(old_lines, new_lines)
            self._rows_cache = rows
            self._populate(rows)

        # Cache content widgets for scrolling
        try:
            if self._left_panel:
                self._left_content = self._left_panel.query_one('.file-content', Vertical)
            if self._right_panel:
                self._right_content = self._right_panel.query_one('.file-content', Vertical)
            # Ensure both panels are scrolled to the top initially
            for cont in (self._left_content, self._right_content):
                try:
                    if cont and hasattr(cont, 'scroll_home'):
                        cont.scroll_home()
                except (AttributeError, RuntimeError):
                    log("Failed to scroll content panel to home")
                    pass
        except (AttributeError, RuntimeError):
            log("Failed to cache content widgets for scrolling")
            self._left_content = None
            self._right_content = None

        # Start watchdog observers for live updates
        self._start_file_observers()

    def _start_file_observers(self):
        """Start file system observers for both files."""
        def trigger_refresh():
            """Callback for filesystem changes."""
            try:
                self.call_later(self.refresh_diff)
            except Exception as e:
                log(f"[ERROR] Failed in trigger_refresh: {e}")

        # Start observer for old file
        try:
            if self.old_path and os.path.isfile(self.old_path):
                self._observer_old, self._stop_old = start_observer(
                    os.path.dirname(self.old_path), trigger_refresh, debounce_ms=500
                )
        except (OSError, RuntimeError) as e:
            log(f"Failed to start observer for old file: {e}")
            self._observer_old = None
            self._stop_old = None

        # Start observer for new file
        try:
            if self.new_path and os.path.isfile(self.new_path):
                self._observer_new, self._stop_new = start_observer(
                    os.path.dirname(self.new_path), trigger_refresh, debounce_ms=500
                )
        except (OSError, RuntimeError) as e:
            log(f"Failed to start observer for new file: {e}")
            self._observer_new = None
            self._stop_new = None

    def _stop_file_observers(self):
        """Stop all file system observers."""
        for stop_fn in (self._stop_old, self._stop_new):
            if stop_fn:
                try:
                    stop_fn()
                except Exception as e:
                    log(f"Failed to stop observer: {e}")

    def refresh_diff(self):
        """Refresh the diff view when files change."""
        # Store current scroll positions
        try:
            if self._left_content:
                self._left_scroll_y = getattr(self._left_content, 'scroll_y', 0)
            if self._right_content:
                self._right_scroll_y = getattr(self._right_content, 'scroll_y', 0)
        except (AttributeError, RuntimeError):
            log("Failed to capture scroll positions")

        # Re-read files and rebuild diff
        try:
            # Use current tab's file pair
            if self._active_tab_id and self._active_tab_id in self._tab_map:
                pair = self._tab_map[self._active_tab_id]
                self._set_pair_and_populate(pair[0], pair[1])
            else:
                # Fallback to original pair
                old_lines, new_lines = read_file_pair(self.old_path, self.new_path)
                rows = compute_diff_rows(old_lines, new_lines)
                self._rows_cache = rows
                self._populate(rows)

            # Restore scroll positions
            self._restore_scroll_positions()
        except (OSError, RuntimeError) as e:
            log(f"Failed to refresh diff: {e}")

    def _restore_scroll_positions(self):
        """Restore saved scroll positions after refresh."""
        try:
            if self._left_content and self._left_scroll_y:
                self._left_content.scroll_to(y=self._left_scroll_y, animate=False)
            if self._right_content and self._right_scroll_y:
                self._right_content.scroll_to(y=self._right_scroll_y, animate=False)
        except (AttributeError, RuntimeError):
            log("Failed to restore scroll positions")

    def on_unmount(self):
        """Stop observers when leaving the screen."""
        self._stop_file_observers()

    def _build_tabs_and_select_default(self):
        """Create tabs for latest NEW vs all occurrences (older NEW + all OLD files)."""
        # Find latest file and all occurrences
        latest_new, other_new_files, old_files = self._find_latest_and_others()

        # Prepare tab system
        tabs = self._prepare_tab_system()
        if tabs is None:
            return

        # Build all tabs
        default_tab_id = self._build_all_tabs(tabs, latest_new, other_new_files, old_files)

        # Select default tab and populate content
        self._select_default_tab_and_populate(default_tab_id, latest_new)

    def _find_latest_and_others(self) -> tuple[str, list[str], list[str]]:
        """Find the latest file and all occurrences for tab creation.

        Returns:
            Tuple of (latest_new_path, other_new_files, old_files)
        """
        # Determine the command and find latest NEW file
        latest_new = self._newest_for_command(self.new_path)
        if latest_new is None:
            latest_new = self.new_path

        meta0 = parse_header_metadata(latest_new) if latest_new else None
        cmd = meta0.get("cmd") if isinstance(meta0, dict) else None

        # Find all NEW occurrences
        new_folder = os.path.dirname(latest_new) if latest_new else None
        new_occurrences: list[str] = []
        if cmd and new_folder and os.path.isdir(new_folder):
            new_occurrences = self._find_occurrences(new_folder, cmd)

        # Find all OLD occurrences
        old_folder = os.path.dirname(self.old_path) if self.old_path else None
        old_occurrences: list[str] = []
        if cmd and old_folder and os.path.isdir(old_folder):
            old_occurrences = self._find_occurrences(old_folder, cmd)

        # Ensure the absolute newest NEW appears as the baseline; other NEW occurrences
        # (older NEWs) become additional tabs for comparison.
        other_new_files = [p for p in new_occurrences if p != latest_new]

        return latest_new, other_new_files, old_occurrences

    def _prepare_tab_system(self):
        """Prepare the tab system by clearing existing tabs and resetting state.

        Returns:
            The tabs widget, or None if not available
        """
        tabs = self._tabs
        if tabs is None:
            return None

        # Clear any existing tabs to avoid duplicates on rebuild
        try:
            clear = getattr(tabs, "clear", None)
            if callable(clear):
                clear()
        except (AttributeError, RuntimeError):
            log("Failed to clear existing tabs")
            # If clear() is unavailable or fails, proceed; we'll overwrite maps
            pass

        # Build fresh tabs and reset internal maps used for cycling and lookup
        self._tab_map = {}
        self._tab_order = []

        return tabs

    def _build_all_tabs(self, tabs, latest_new: str, other_new_files: list[str], old_files: list[str]) -> str | None:
        """Build all tabs (prior NEW, all OLD, fallback) and return default tab ID.

        Args:
            tabs: The tabs widget
            latest_new: Path to the latest NEW file
            other_new_files: List of other NEW file paths
            old_files: List of all OLD file paths

        Returns:
            The default tab ID to select, or None if no tabs were created
        """
        default_tab_id: str | None = None

        # Add prior NEW comparisons first (2nd newest, 3rd newest, ...)
        default_tab_id = self._add_prior_new_tabs(tabs, latest_new, other_new_files, default_tab_id)

        # Add OLD comparison tabs (one for each OLD file)
        default_tab_id = self._add_old_tabs(tabs, latest_new, old_files, default_tab_id)

        # Add fallback tab if needed
        default_tab_id = self._add_fallback_tab(tabs, latest_new, default_tab_id)

        return default_tab_id

    def _add_prior_new_tabs(
        self, tabs, latest_new: str, other_new_files: list[str], default_tab_id: str | None
    ) -> str | None:
        """Add tabs for prior NEW file comparisons.

        Returns:
            The updated default_tab_id (first tab added if none set yet)
        """
        for idx, other in enumerate(other_new_files, start=1):
            # Directional minutes with sign: floor((latest - other)/60)
            # A negative value means "older than latest".
            mins = None
            try:
                t_latest = get_mtime(latest_new)
                t_other = get_mtime(other)
                if t_latest is not None and t_other is not None:
                    mins = math.floor((t_latest - t_other) / 60.0)
            except (OSError, ValueError):
                log(f"Failed to calculate time difference between {latest_new} and {other}")
                mins = None
            meta = parse_header_metadata(other) or {}
            fallback = meta.get("date") or os.path.basename(other)
            label = f"{mins:+d}m" if mins is not None else fallback
            tab_id = f"n{idx}"
            tabs.add_tab(Tab(label, id=tab_id))
            self._tab_map[tab_id] = (other, latest_new)
            self._tab_order.append(tab_id)
            if default_tab_id is None:
                default_tab_id = tab_id

        return default_tab_id

    def _add_old_tabs(self, tabs, latest_new: str, old_files: list[str], default_tab_id: str | None) -> str | None:
        """Add OLD comparison tabs for all OLD files.

        Returns:
            The updated default_tab_id (first OLD tab if none set yet)
        """
        if not old_files:
            return default_tab_id

        for idx, old_file in enumerate(old_files):
            # Calculate time difference for labeling
            mins = None
            try:
                t_latest = get_mtime(latest_new)
                t_old = get_mtime(old_file)
                if t_latest is not None and t_old is not None:
                    # OLD files are typically older, so this will be positive
                    mins = math.floor((t_latest - t_old) / 60.0)
            except (OSError, ValueError):
                log(f"Failed to calculate time difference between {latest_new} and {old_file}")
                mins = None

            # Create tab label
            if len(old_files) == 1:
                # Single OLD file - just call it "OLD"
                label = "OLD"
                tab_id = "old"
            else:
                # Multiple OLD files - distinguish them by time or index
                if mins is not None and mins > 0:
                    # Show age relative to latest NEW (e.g., "OLD+2h" means OLD is 2 hours older)
                    if mins < 60:
                        label = f"OLD+{mins}m"
                    elif mins < 1440:  # less than 24 hours
                        hours = mins // 60
                        label = f"OLD+{hours}h"
                    else:  # 24+ hours
                        days = mins // 1440
                        label = f"OLD+{days}d"
                else:
                    # Fallback to index-based naming
                    label = "OLD" if idx == 0 else f"OLD-{idx}"
                tab_id = f"old{idx}"

            # Create the tab
            tabs.add_tab(Tab(label, id=tab_id))
            self._tab_map[tab_id] = (old_file, latest_new)
            self._tab_order.append(tab_id)

            # Set first OLD tab as default if none set yet
            if default_tab_id is None:
                default_tab_id = tab_id

        return default_tab_id

    def _add_fallback_tab(self, tabs, latest_new: str, default_tab_id: str | None) -> str | None:
        """Add fallback tab if no other tabs were created.

        Returns:
            The updated default_tab_id (fallback tab if none set yet)
        """
        # Fallback: if no tabs were added (e.g., missing files and no prior NEWs),
        # create a safe default so the Tabs widget always has one option.
        if default_tab_id is None:
            try:
                tab_id = "current"
                tabs.add_tab(Tab("CURRENT", id=tab_id))
                # Map to whatever we have; read_file_pair() will handle missing files gracefully
                self._tab_map[tab_id] = (self.old_path or self.new_path, latest_new)
                self._tab_order.append(tab_id)
                default_tab_id = tab_id
            except (AttributeError, RuntimeError):
                log("Failed to create fallback tab")
                pass

        return default_tab_id

    def _select_default_tab_and_populate(self, default_tab_id: str | None, latest_new: str):
        """Select the default tab and populate the diff content.

        Args:
            default_tab_id: The tab ID to activate, or None for fallback behavior
            latest_new: Path to the latest NEW file for fallback diff
        """
        if default_tab_id:
            try:
                self._tabs.active = default_tab_id
                self._active_tab_id = default_tab_id
            except (AttributeError, RuntimeError):
                log(f"Failed to set active tab to {default_tab_id}")
                pass
            pair = self._tab_map.get(default_tab_id)
            if pair:
                self._set_pair_and_populate(pair[0], pair[1])
        else:
            # Fallback: no tabs created, show basic diff
            old_lines, new_lines = read_file_pair(self.old_path, self.new_path)
            rows = compute_diff_rows(old_lines, new_lines)
            self._rows_cache = rows
            self._populate(rows)

    def _newest_for_command(self, some_path: str) -> str | None:
        """Return the newest file in the same folder with the same command as some_path."""
        meta = parse_header_metadata(some_path) or {}
        cmd = meta.get("cmd")
        folder = os.path.dirname(some_path)
        if not cmd or not os.path.isdir(folder):
            return some_path
        candidates = self._find_occurrences(folder, cmd)
        return candidates[0] if candidates else some_path

    def _find_occurrences(self, folder: str, cmd: str) -> list[str]:
        """Find all files in folder with header command equal to cmd, newest first."""
        items: list[tuple[str, float]] = []
        try:
            for name in os.listdir(folder):
                path = os.path.join(folder, name)
                if not os.path.isfile(path):
                    continue
                try:
                    meta = parse_header_metadata(path) or {}
                    if meta.get("cmd") == cmd:
                        items.append((path, os.path.getmtime(path)))
                except (OSError, ValueError, AttributeError):
                    log(f"Failed to process file {path} for command occurrences")
                    continue
        except OSError:
            log(f"Failed to list directory {folder} for occurrences")
            pass
        items.sort(key=lambda t: t[1], reverse=True)
        return [p for p, _ in items]

    def _set_pair_and_populate(self, older_path: str, latest_path: str):
        """Set the current paths and repaint panels accordingly."""
        # Stop existing observers if paths are changing
        if older_path != self.old_path or latest_path != self.new_path:
            self._stop_file_observers()

        self.old_path = older_path
        self.new_path = latest_path

        # Update metadata and repaint
        self._old_meta = parse_header_metadata(self.old_path) or {"date": None, "time": None, "cmd": None}
        self._new_meta = parse_header_metadata(self.new_path) or {"date": None, "time": None, "cmd": None}
        # Refresh created timestamps for subtitles
        self._old_created = format_mtime(self.old_path)
        self._new_created = format_mtime(self.new_path)
        old_lines, new_lines = read_file_pair(self.old_path, self.new_path)
        rows = compute_diff_rows(old_lines, new_lines)
        self._rows_cache = rows
        self._populate(rows)

        # Restart observers for new file paths
        self._start_file_observers()

    def on_tabs_tab_activated(self, event: Tabs.TabActivated):
        """Switch the comparison when a tab is activated by the user."""
        tab_id = getattr(event.tab, "id", None)
        if isinstance(tab_id, str):
            self._active_tab_id = tab_id
        pair = self._tab_map.get(tab_id or "")
        if pair:
            self._set_pair_and_populate(pair[0], pair[1])

    def _cycle_tab(self, offset: int):
        """Move active tab left/right by offset within the known order."""
        tabs = self._tabs
        order = self._tab_order
        if not tabs or not order:
            return
        # Prefer Tabs.active if available; fall back to tracked id or first
        current_id = None
        try:
            current_id = getattr(tabs, "active", None)
        except (AttributeError, RuntimeError):
            log("Failed to get current active tab")
            current_id = None
        if not isinstance(current_id, str) or current_id not in order:
            current_id = self._active_tab_id if isinstance(self._active_tab_id, str) else (order[0] if order else None)
        if not isinstance(current_id, str):
            return
        try:
            idx = order.index(current_id)
        except ValueError:
            idx = 0
        if not order:
            return
        new_idx = (idx + offset) % len(order)
        target_id = order[new_idx]
        try:
            tabs.active = target_id
            self._active_tab_id = target_id
        except (AttributeError, RuntimeError):
            log(f"Failed to set active tab to {target_id}")
            # As a fallback, populate directly
            pair = self._tab_map.get(target_id)
            if pair:
                self._set_pair_and_populate(pair[0], pair[1])

    def on_key(self, event):
        """Handle vim-like scrolling and tab navigation keys - orchestrator for keyboard events.

        - j/k scroll both panels
        - g then g goes to top (like ``gg``)
        - G goes to end
        - Ctrl+K toggles keyword underlining
        - h/l move to previous/next tab
        """
        key = getattr(event, 'key', None)
        if key is None:
            return

        # Dispatch to specific key handlers
        if key == 'j':
            self._handle_scroll_down_key(event)
        elif key == 'k':
            self._handle_scroll_up_key(event)
        elif key == 'G':
            self._handle_scroll_end_key(event)
        elif key == 'g':
            self._handle_go_to_top_key(event)
        elif key == 'h':
            self._handle_prev_tab_key(event)
        elif key == 'l':
            self._handle_next_tab_key(event)
        else:
            self._last_g = False

    def _handle_scroll_down_key(self, event):
        """Handle j key - scroll both panels down."""
        self._apply_to_both_panels('scroll_down')
        self._last_g = False
        self._stop_event(event, "scroll down")

    def _handle_scroll_up_key(self, event):
        """Handle k key - scroll both panels up."""
        self._apply_to_both_panels('scroll_up')
        self._last_g = False
        self._stop_event(event, "scroll up")

    def _handle_scroll_end_key(self, event):
        """Handle G key - scroll both panels to end."""
        self._apply_to_both_panels('scroll_end')
        self._last_g = False
        self._stop_event(event, "scroll end")

    def _handle_go_to_top_key(self, event):
        """Handle g key - go to top with gg pattern."""
        self._stop_event(event, "'g' key")
        if self._last_g:
            self._apply_to_both_panels('scroll_home')
            self._last_g = False
        else:
            self._last_g = True

    def _handle_toggle_highlights_key(self, event):
        """Handle Ctrl+K key - toggle keyword highlights."""
        self.action_toggle_highlights()
        self._stop_event(event, "toggle highlights")

    def _handle_prev_tab_key(self, event):
        """Handle h key - navigate to previous tab."""
        self.action_prev_tab()
        self._stop_event(event, "prev tab")

    def _handle_next_tab_key(self, event):
        """Handle l key - navigate to next tab."""
        self.action_next_tab()
        self._stop_event(event, "next tab")

    def _apply_to_both_panels(self, method_name: str):
        """Apply a method to both left and right content panels."""
        for widget in (self._left_content, self._right_content):
            try:
                if widget is None:
                    continue
                method = getattr(widget, method_name, None)
                if callable(method):
                    method()
            except (AttributeError, RuntimeError):
                log(f"Failed to call {method_name} on content widget")

    def _stop_event(self, event, action_description: str):
        """Stop event propagation with error handling."""
        try:
            event.stop()
        except (AttributeError, RuntimeError):
            log(f"Failed to stop {action_description} event")

    def action_toggle_highlights(self):
        """Toggle keyword highlighting in the diff and repaint."""
        try:
            self.keyword_highlight_enabled = not self.keyword_highlight_enabled
            self._populate(self._rows_cache)
            self._update_footer()
        except (AttributeError, RuntimeError):
            log("Failed to toggle keyword highlights")
            pass

    def _update_footer(self):
        """Update footer text with current highlights toggle state."""
        try:
            from rich.text import Text
            from textual.widgets import Footer

            footer = self.query_one(Footer)
            footer.update(Text.from_markup(self.get_footer_text()))
        except Exception as e:
            log(f"Failed to update footer: {e}")

    def action_prev_tab(self):
        """Activate the previous tab (if any)."""
        try:
            self._cycle_tab(-1)
        except (AttributeError, RuntimeError, ValueError, IndexError):
            log("Failed to cycle to previous tab")
            pass

    def action_next_tab(self):
        """Activate the next tab (if any)."""
        try:
            self._cycle_tab(1)
        except (AttributeError, RuntimeError, ValueError, IndexError):
            log("Failed to cycle to next tab")
            pass

    # Prev/Next file navigation via p/n has been removed per request.

    def _minutes_between_paths(self, a: str, b: str) -> int | None:
        """Compute absolute minutes difference between two files' timestamps."""
        return minutes_between(a, b)

    def _populate(self, rows: list[DiffRow]):
        """Render the diff rows into the left/right panels.

        Orchestrates the diff rendering process by calling focused helper methods.
        """
        left = self._left_panel
        right = self._right_panel
        if not left or not right:
            return

        # Create formatting functions
        ln, word_diff = self._create_diff_formatters()

        # Render diff lines
        left_lines, right_lines = self._render_diff_lines(rows, ln, word_diff)

        # Update panel titles and subtitles
        self._update_panel_titles(left, right)

        # Apply line length limits
        left_lines, right_lines = self._apply_line_length_limits(left_lines, right_lines)

        # Update panel contents
        self._update_panel_contents(left, right, left_lines, right_lines)

    def _create_diff_formatters(self):
        """Create formatting functions for diff rendering.

        Returns:
            Tuple of (line_number_formatter, word_diff_function)
        """

        def ln(n: int | None) -> str:
            # Straight ASCII pipe as separator
            # For missing lines (None), don't draw the pipe; keep spacing for alignment only.
            # Width is 6 digits + space + pipe + space = 9 chars.
            return f"{n:>6} | " if n is not None else " " * 9

        def tokenize(s: str) -> list[str]:
            # Keep whitespace as tokens so we can reconstruct spacing
            return re.split(r"(\s+)", s)

        def underline_keywords(s: str) -> str:
            # Insert [u]...[/u] around keyword matches, escaping non-matching text
            pat = self._kw_pattern if (self.keyword_highlight_enabled and self._kw_pattern) else None
            if not pat:
                return escape(s)
            out: list[str] = []
            last = 0
            for m in pat.finditer(s):
                out.append(escape(s[last : m.start()]))
                out.append(f"[u]{escape(m.group(0))}[/u]")
                last = m.end()
            out.append(escape(s[last:]))
            return "".join(out)

        def process_token(tok: str) -> str:
            # Preserve whitespace tokens; otherwise apply keyword underline
            if tok.isspace():
                return tok
            return underline_keywords(tok)

        def word_diff(old_text: str, new_text: str) -> tuple[str, str]:
            """Return (left_markup, right_markup) with word-level coloring.

            - Unchanged: white
            - Deletions (only in old): red (left side)
            - Insertions (only in new): green (right side)
            """
            o_tokens = tokenize(old_text)
            n_tokens = tokenize(new_text)
            sm = SequenceMatcher(None, o_tokens, n_tokens)
            left_parts: list[str] = []
            right_parts: list[str] = []
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    seg_o = "".join(process_token(t) for t in o_tokens[i1:i2])
                    seg_n = "".join(process_token(t) for t in n_tokens[j1:j2])
                    left_parts.append(f"[white]{seg_o}[/white]")
                    right_parts.append(f"[white]{seg_n}[/white]")
                elif tag == "delete":
                    seg_o = "".join(process_token(t) for t in o_tokens[i1:i2])
                    left_parts.append(f"[red]{seg_o}[/red]")
                    # Nothing on right
                elif tag == "insert":
                    seg_n = "".join(process_token(t) for t in n_tokens[j1:j2])
                    right_parts.append(f"[green]{seg_n}[/green]")
                elif tag == "replace":
                    seg_o = "".join(process_token(t) for t in o_tokens[i1:i2])
                    seg_n = "".join(process_token(t) for t in n_tokens[j1:j2])
                    left_parts.append(f"[red]{seg_o}[/red]")
                    right_parts.append(f"[green]{seg_n}[/green]")
            return "".join(left_parts), "".join(right_parts)

        return ln, word_diff

    def _render_diff_lines(self, rows, ln, word_diff) -> tuple[list[str], list[str]]:
        """Render diff rows into formatted left and right lines.

        Args:
            rows: Diff rows from compute_diff_rows
            ln: Line number formatter function
            word_diff: Word-level diff function

        Returns:
            Tuple of (left_lines, right_lines)
        """
        left_lines: list[str] = []
        right_lines: list[str] = []

        for row in rows:
            if row.diff_type == DiffType.UNCHANGED:
                lmk, rmk = word_diff(row.left_content, row.right_content)
                left_lines.append(f"{ln(row.left_line_num)}{lmk}")
                right_lines.append(f"{ln(row.right_line_num)}{rmk}")
            elif row.diff_type == DiffType.MODIFIED:
                lmk, rmk = word_diff(row.left_content, row.right_content)
                left_lines.append(f"{ln(row.left_line_num)}{lmk}")
                right_lines.append(f"{ln(row.right_line_num)}{rmk}")
            elif row.diff_type == DiffType.DELETED:
                lmk, _ = word_diff(row.left_content, "")
                left_lines.append(f"{ln(row.left_line_num)}{lmk}")
                right_lines.append(f"{ln(row.right_line_num)}")
            elif row.diff_type == DiffType.ADDED:
                _, rmk = word_diff("", row.right_content)
                left_lines.append(f"{ln(row.left_line_num)}")
                right_lines.append(f"{ln(row.right_line_num)}{rmk}")
            else:
                # Fallback: treat as equal
                lmk, rmk = word_diff(row.left_content, row.right_content)
                left_lines.append(f"{ln(row.left_line_num)}{lmk}")
                right_lines.append(f"{ln(row.right_line_num)}{rmk}")

        return left_lines, right_lines

    def _update_panel_titles(self, left, right):
        """Update panel titles and subtitles with metadata."""
        try:
            lp_title = left.query_one('.file-title', Static)
            rp_title = right.query_one('.file-title', Static)
            lp_sub = left.query_one('.file-subtitle', Static)
            rp_sub = right.query_one('.file-subtitle', Static)

            old_cmd = self._old_meta.get("cmd") if isinstance(self._old_meta, dict) else None
            new_cmd = self._new_meta.get("cmd") if isinstance(self._new_meta, dict) else None

            left_title_text = (
                f"[yellow]OLD[/yellow] — {escape(old_cmd) if old_cmd else os.path.basename(self.old_path)}"
            )
            right_title_text = f"[green]NEW[/green] — {escape(new_cmd) if new_cmd else os.path.basename(self.new_path)}"

            lp_title.update(Text.from_markup(left_title_text))
            rp_title.update(Text.from_markup(right_title_text))
            lp_sub.update(f"Modified: {self._old_created}" if self._old_created else "")
            rp_sub.update(f"Modified: {self._new_created}" if self._new_created else "")
        except (AttributeError, RuntimeError):
            log("Failed to update panel titles and subtitles")
            pass

    def _apply_line_length_limits(self, left_lines: list[str], right_lines: list[str]) -> tuple[list[str], list[str]]:
        """Apply line length cap for performance and readability.

        Args:
            left_lines: Lines for left panel
            right_lines: Lines for right panel

        Returns:
            Tuple of (clamped_left_lines, clamped_right_lines)
        """

        def clamp_line(s: str) -> str:
            try:
                if config.max_preview_chars and len(s) > config.max_preview_chars:
                    return s[: config.max_preview_chars] + " …"
            except (ValueError, AttributeError):
                log(f"Failed to clamp line length for: {s[:50]}...")
                pass
            return s

        return [clamp_line(s) for s in left_lines], [clamp_line(s) for s in right_lines]

    def _update_panel_contents(self, left, right, left_lines: list[str], right_lines: list[str]):
        """Update the actual panel content widgets with rendered lines.

        Args:
            left: Left panel widget
            right: Right panel widget
            left_lines: Formatted lines for left panel
            right_lines: Formatted lines for right panel
        """
        try:
            lp_cont = left.query_one('.file-content', Vertical)
            rp_cont = right.query_one('.file-content', Vertical)
            lp_text = lp_cont.query_one('.file-text', Static)
            rp_text = rp_cont.query_one('.file-text', Static)
            lp_text.update("\n".join(left_lines))
            rp_text.update("\n".join(right_lines))
        except (AttributeError, RuntimeError):
            log("Failed to update diff content panels")
            pass
