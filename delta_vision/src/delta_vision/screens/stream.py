"""Stream screen: live, readable view of the newest files in a folder.

This screen renders each file as a panel with numbered lines, ordered by
modification time (oldest first). The first line of each file is treated as a
header/title and excluded from the body. A filesystem observer (watchdog)
keeps the view updated as files are added or changed.

Features:
- Optional keyword highlighting and a filter toggle (K) to show only lines near
    keyword matches (configurable lines of context per match).
- Incremental updates reuse existing panels when possible for smooth refreshes.
- A line cap via ``config.max_render_lines`` protects performance with very large files.

Key bindings: q (Back), j/k (Scroll), Shift+G (End), Ctrl+K (Toggle keyword filter), Ctrl+A (Anchor bottom).
"""

import os
import re
import stat
from typing import Dict, List, Optional, Set, Tuple

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static

from delta_vision.utils.config import config
from delta_vision.utils.io import read_text
from delta_vision.utils.keyword_highlighter import KeywordHighlighter
from delta_vision.utils.logger import log
from delta_vision.utils.watchdog import start_observer
from delta_vision.widgets.footer import Footer
from delta_vision.widgets.header import Header

from .keywords_parser import parse_keywords_md
from .watchdog_helper import start_watchdog

# KeywordProcessor functionality moved to utils/keyword_highlighter.py for reuse across screens


class StreamScreen(Screen):
    """Live stream of files in a folder with optional keyword filtering.

    The screen lists files by oldest-first modification time and updates when
    changes are detected. Use Ctrl+K to toggle showing only lines around keyword
    matches. Press q to return to the previous screen.
    """

    # Show keys in Textual help and route to actions
    BINDINGS = [
        ("q", "go_home", "Back"),
        ("j", "scroll_down", "Down"),
        ("k", "scroll_up", "Up"),
        ("G", "scroll_end", "End"),
        ("ctrl+k", "toggle_keywords", "Keywords"),
        ("ctrl+a", "toggle_anchor", "Anchor Bottom"),
    ]

    # Minimal on_key to preserve double-"g" behavior for go-to-top
    def on_key(self, event):
        if event.key == 'g':
            try:
                scroll = self.query_one('#stream-main-scroll')
                if getattr(self, '_last_g', False):
                    scroll.scroll_home()
                    self._last_g = False
                else:
                    self._last_g = True
                    return
            except Exception as e:
                log(f"[ERROR] Failed to handle 'g' key navigation: {e}")
                self._last_g = False
        else:
            self._last_g = False

    CSS_PATH = "stream.tcss"

    def __init__(self, folder_path=None, keywords_path=None):
        super().__init__()
        self.folder_path = folder_path
        self.keywords_path = keywords_path
        self.keywords_dict = None
        self.keyword_filter_enabled = False
        self._observer = None
        self._stop_observer = None
        # Cache file metadata and titles to avoid full rereads when unchanged
        self._file_meta = {}  # path -> (int(mtime), size)
        self._titles = {}  # path -> last derived title
        self._last_filter_state = False
        # Anchor to bottom for auto-scroll to new files
        self._anchor_bottom = False
        # Keyword processor for pattern caching
        self._keyword_highlighter = KeywordHighlighter()
        # Cache for file stat info to avoid duplicate filesystem calls
        self._cached_stats = {}

    def _get_footer_text(self) -> str:
        """Generate dynamic footer text showing toggle states."""
        keywords_state = "ON" if self.keyword_filter_enabled else "OFF"
        anchor_state = "ON" if self._anchor_bottom else "OFF"
        return (
            f" [orange1]q[/orange1] Back    "
            f"[orange1]Ctrl+K[/orange1] Keywords: {keywords_state}    "
            f"[orange1]Ctrl+A[/orange1] Anchor: {anchor_state}"
        )

    def _update_footer(self):
        """Update footer text with current toggle states."""
        try:
            footer = self.query_one(Footer)
            from rich.text import Text
            footer.update(Text.from_markup(self._get_footer_text()))
        except Exception as e:
            log(f"[ERROR] Failed to update footer: {e}")

    def compose(self) -> ComposeResult:
        """Build the static layout: header, scrollable body, and footer."""
        # Declarative layout: Header, scroll container, Footer
        yield Header(page_name="Stream", show_clock=True)
        yield Vertical(id="stream-main-scroll")
        yield Footer(
            text=self._get_footer_text(),
            classes="footer-stream",
        )

    def on_mount(self):
        """Wire up state, start the filesystem observer, and paint initial view."""
        # Set the screen title so the built-in Header shows it
        self.title = "Delta Vision — Stream"
        # Grab references to composed widgets
        try:
            self.scroll_container = self.query_one('#stream-main-scroll', Vertical)
        except Exception as e:
            log(f"[ERROR] Failed to find scroll container, creating new one: {e}")
            self.scroll_container = Vertical(id="stream-main-scroll")
            self.mount(self.scroll_container)
        self.file_panels = {}
        if not self.folder_path or not os.path.isdir(self.folder_path):
            try:
                self.mount(Static("No valid folder specified."))
            except Exception as e:
                log(f"[ERROR] Failed to mount error message: {e}")
            return

        # Parse keywords file if provided
        keywords_dict = None
        if self.keywords_path and os.path.isfile(self.keywords_path):
            try:
                keywords_dict = parse_keywords_md(self.keywords_path)
            except Exception as e:
                keywords_dict = None
                self.mount(Static(f"[Error parsing keywords file: {e}]"))
                return
        self.keywords_dict = keywords_dict

        # Start watchdog observer for live updates
        def trigger_refresh():
            # Debug log for watchdog callbacks
            log("[WATCHDOG] trigger_refresh called")
            try:
                app = self.app
            except Exception as e:
                log(f"[ERROR] Failed to access app in trigger_refresh: {e}")
                app = None
            if app:
                try:
                    app.call_later(self.refresh_stream)
                except Exception as e:
                    log(f"[ERROR] Failed to schedule refresh via app.call_later: {e}")

        log(f"[STREAM] Starting watchdog for: {self.folder_path}")
        try:
            self._observer, self._stop_observer = start_observer(self.folder_path, trigger_refresh)
        except Exception as e:
            log(f"[ERROR] Failed to start new observer, falling back to legacy: {e}")
            # Fall back to legacy helper if utils.watchdog fails for any reason
            try:
                self._observer = start_watchdog(self.folder_path, trigger_refresh)
                self._stop_observer = None
            except Exception as e2:
                log(f"[ERROR] Failed to start legacy watchdog: {e2}")
                self._observer = None
                self._stop_observer = None

        self.refresh_stream()

    def on_unmount(self):
        """Stop filesystem observers when leaving the screen."""
        # Stop watchdog observer when leaving the screen
        try:
            stop = getattr(self, "_stop_observer", None)
            if callable(stop):
                stop()
            else:
                obs = getattr(self, "_observer", None)
                if obs:
                    try:
                        obs.stop()
                    except Exception as e:
                        log(f"[ERROR] Failed to stop observer: {e}")
                    try:
                        obs.join(timeout=0.5)
                    except Exception as e:
                        log(f"[ERROR] Failed to join observer thread: {e}")
        except Exception as e:
            log(f"[ERROR] Failed to cleanup observer: {e}")
        self._observer = None
        self._stop_observer = None

    # Action method for the 'q' binding
    def action_go_home(self):
        """Return to the previous screen."""
        try:
            self.app.pop_screen()
        except Exception as e:
            log(f"[ERROR] Failed to pop screen: {e}")

    # Action methods for navigation and toggles
    def action_scroll_down(self):
        """Scroll the stream body down by one step."""
        try:
            self.query_one('#stream-main-scroll').scroll_down()
        except Exception as e:
            log(f"[ERROR] Failed to scroll down: {e}")

    def action_scroll_up(self):
        """Scroll the stream body up by one step."""
        try:
            self.query_one('#stream-main-scroll').scroll_up()
        except Exception as e:
            log(f"[ERROR] Failed to scroll up: {e}")

    def action_scroll_end(self):
        """Jump to the bottom of the stream."""
        try:
            self.query_one('#stream-main-scroll').scroll_end()
            self._last_g = False
        except Exception as e:
            log(f"[ERROR] Failed to scroll to end: {e}")

    def action_toggle_keywords(self):
        """Enable/disable the keyword filter and repaint."""
        try:
            self.keyword_filter_enabled = not bool(self.keyword_filter_enabled)
            self._update_footer()
            self.refresh_stream()
        except Exception as e:
            log(f"[ERROR] Failed to toggle keyword filter: {e}")

    def action_toggle_anchor(self):
        """Toggle bottom anchor mode for auto-scrolling to new content."""
        try:
            self._anchor_bottom = not self._anchor_bottom
            self._update_footer()
            if self._anchor_bottom:
                # Scroll to bottom immediately when enabling anchor
                self.query_one('#stream-main-scroll').scroll_end()
        except Exception as e:
            log(f"[ERROR] Failed to toggle anchor mode: {e}")

    def _discover_files(self) -> List[str]:
        """Discover and sort files by modification time (oldest first).

        Optimized to use single stat() call per file instead of separate
        isfile() + getmtime() calls, reducing file system operations.
        """
        folder_path = self.folder_path
        if not folder_path or not os.path.isdir(folder_path):
            log("[DEBUG] Folder path invalid or not a directory")
            return []

        # Get files with stat info in single pass to avoid duplicate file operations
        files_with_stats = []
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            try:
                stat_info = os.stat(file_path)
                # Only include regular files (not directories, symlinks, etc.)
                if stat.S_ISREG(stat_info.st_mode):
                    files_with_stats.append((file_path, stat_info))
            except OSError:
                # Skip files that can't be stat'd (permissions, deleted, etc.)
                continue

        # Sort by modification time (oldest first) using cached stat info
        files_with_stats.sort(key=lambda item: item[1].st_mtime)
        files = [file_path for file_path, _ in files_with_stats]

        # Cache the stat info for use in refresh_stream to avoid duplicate stat calls
        self._cached_stats = {file_path: stat_info for file_path, stat_info in files_with_stats}

        log(f"[DEBUG] Files found: {files}")
        return files

    def _apply_keyword_filter(self, content_lines: List[str], pattern: Optional[re.Pattern]) -> Tuple[bool, List[int]]:
        """Apply keyword filtering to content lines.

        Returns:
            Tuple of (show_file, filtered_indices) where filtered_indices contains
            the line indices to show (with ±config.context_lines context around matches).
        """
        if not self.keyword_filter_enabled or not pattern:
            return True, list(range(len(content_lines)))

        # Find all lines with a keyword
        keyword_lines = set()
        for i, line in enumerate(content_lines):
            if pattern.search(line):
                keyword_lines.add(i)

        if not keyword_lines:
            return False, []

        # Add ±config.context_lines lines around each match
        show_lines = set()
        for idx in keyword_lines:
            for j in range(max(0, idx - config.context_lines), min(len(content_lines), idx + config.context_lines + 1)):
                show_lines.add(j)

        return True, sorted(show_lines)

    def _process_file_content(self, file_path: str, pattern: Optional[re.Pattern], keyword_lookup: Dict[str, Tuple[str, str]]) -> Optional[Tuple[str, str, bool]]:
        """Process a file's content for display.

        Returns:
            Tuple of (title, formatted_content, truncated) or None if file should be skipped.
        """
        content, _enc = read_text(file_path)
        if not content:
            try:
                content = f"[Error reading {os.path.basename(file_path)}]"
            except Exception as e:
                log(f"[ERROR] Failed to get basename for error message: {e}")
                content = "[Error reading file]"

        # Extract title from first line
        match = re.search(r'"([^"]+)"', content)
        title = match.group(1) if match else os.path.basename(file_path)
        self._titles[file_path] = title

        # Get content lines (skip header line)
        content_lines = content.splitlines()[1:] if len(content.splitlines()) > 1 else []

        # Apply keyword filtering
        show_file, filtered_indices = self._apply_keyword_filter(content_lines, pattern)
        if not show_file:
            return None

        # Get lines to show
        lines_to_show = [content_lines[i] for i in filtered_indices] if filtered_indices else content_lines

        # Apply line cap for performance
        truncated = False
        try:
            if config.max_render_lines and len(lines_to_show) > config.max_render_lines:
                lines_to_show = lines_to_show[:config.max_render_lines]
                truncated = True
        except Exception as e:
            log(f"[ERROR] Failed to apply line cap: {e}")

        # Format with line numbers and highlighting
        numbered_lines = []
        for display_idx, text in enumerate(lines_to_show, start=1):
            highlighted_text = self._keyword_highlighter.highlight_line(text, pattern, keyword_lookup)
            numbered_lines.append(f"{display_idx:>6} │ {highlighted_text}")

        content_with_numbers = "\n".join(numbered_lines)
        return title, content_with_numbers, truncated

    def _update_file_panel(self, file_path: str, title: str, content_with_numbers: str, truncated: bool) -> Vertical:
        """Update or create a file panel with the given content."""
        panel = self.file_panels.get(file_path)

        # Check if we need to recreate the panel
        needs_recreate = False
        if panel:
            try:
                file_content_widget = panel.query_one('.file-content')
                file_title_widget = panel.query_one('.file-title')
            except Exception as e:
                log(f"[ERROR] Failed to query panel widgets, will recreate: {e}")
                needs_recreate = True

        display_title = title + (" (truncated)" if truncated else "")

        if not panel or needs_recreate:
            # Create new panel
            panel = Vertical(
                Static(display_title, classes="file-title"),
                Static(content_with_numbers, classes="file-content", markup=True),
                classes="file-panel",
            )
            self.scroll_container.mount(panel)
        else:
            # Update existing panel
            file_content_widget.update(content_with_numbers)
            file_title_widget.update(display_title)
            try:
                # Force layout to recalc sizes when content shrinks
                panel.refresh(layout=True)
            except Exception as e:
                log(f"[ERROR] Failed to refresh panel layout: {e}")

        return panel

    def _cleanup_deleted_files(self, current_files: Set[str]):
        """Remove panels for files that no longer exist."""
        for old_path in list(self.file_panels.keys()):
            if old_path not in current_files:
                try:
                    self.file_panels[old_path].remove()
                    del self.file_panels[old_path]
                except Exception as e:
                    log(f"[ERROR] Failed to remove panel for {old_path}: {e}")

    def _reorder_and_refresh(self, files: List[str], new_file_panels: Dict[str, Vertical]):
        """Reorder panels and refresh the UI."""
        # Reorder panels in scroll_container to match files order
        for f in files:
            if f in new_file_panels:
                panel = new_file_panels[f]
                if panel.parent is not self.scroll_container:
                    self.scroll_container.mount(panel)

        self.file_panels = new_file_panels
        self._last_filter_state = bool(self.keyword_filter_enabled)

        try:
            # Ensure container reflows to content
            self.scroll_container.refresh(layout=True)
            # Auto-scroll to bottom if anchor mode is enabled
            if self._anchor_bottom:
                self.scroll_container.scroll_end()
        except Exception as e:
            log(f"[ERROR] Failed to refresh container layout or scroll: {e}")

    def refresh_stream(self):
        """Rebuild file panels and content.

        Called on mount and whenever the watchdog signals a change. Reuses
        existing panels when the file metadata hasn't changed and the filter
        state is stable to avoid unnecessary work.
        """
        log("[DEBUG] refresh_stream called")

        # Discover files in the folder
        files = self._discover_files()
        if not files:
            return

        # Get keyword pattern and lookup (with caching for performance)
        pattern, keyword_lookup = self._keyword_highlighter.get_pattern_and_lookup(self.keywords_dict)

        # Incremental update: reuse panels if file unchanged and filter state hasn't changed
        new_file_panels = {}
        filter_changed = self._last_filter_state != bool(self.keyword_filter_enabled)

        for file_path in files:
            # Use cached stat info from _discover_files if available, otherwise stat
            cached_stat = getattr(self, '_cached_stats', {}).get(file_path)
            if cached_stat:
                # Use cached stat info to avoid duplicate file system call
                cur_meta = (int(cached_stat.st_mtime), int(cached_stat.st_size))
            else:
                # Fallback to stat call if not in cache (shouldn't normally happen)
                try:
                    st = os.stat(file_path)
                    cur_meta = (int(st.st_mtime), int(st.st_size))
                except OSError as e:
                    log(f"[ERROR] Failed to stat file {file_path}: {e}")
                    cur_meta = None
                except Exception as e:
                    log(f"[ERROR] Unexpected error checking file metadata {file_path}: {e}")
                    cur_meta = None

            prev_meta = self._file_meta.get(file_path)
            panel = self.file_panels.get(file_path)

            # If unchanged and no filter toggle, reuse existing panel without reread
            if (not filter_changed and prev_meta is not None and
                cur_meta == prev_meta and panel is not None):
                new_file_panels[file_path] = panel
                continue

            # Process file content
            result = self._process_file_content(file_path, pattern, keyword_lookup)
            if result is None:
                continue  # Skip this file (filtered out)

            title, content_with_numbers, truncated = result

            # Update or create panel
            panel = self._update_file_panel(file_path, title, content_with_numbers, truncated)
            new_file_panels[file_path] = panel

            # Update metadata cache after successful update
            if cur_meta is not None:
                self._file_meta[file_path] = cur_meta

        # Clean up deleted files and refresh UI
        self._cleanup_deleted_files(set(new_file_panels.keys()))
        self._reorder_and_refresh(files, new_file_panels)

        # Clear cached stats after refresh to prevent memory buildup
        self._cached_stats = {}
