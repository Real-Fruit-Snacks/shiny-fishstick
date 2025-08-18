"""Stream screen: live, readable view of the newest files in a folder.

This screen renders each file as a panel with numbered lines, ordered by
modification time (oldest first). The first line of each file is treated as a
header/title and excluded from the body. A filesystem observer (watchdog)
keeps the view updated as files are added or changed.

Features:
- Optional keyword highlighting and a filter toggle (K) to show only lines near
    keyword matches (±3 lines of context per match).
- Incremental updates reuse existing panels when possible for smooth refreshes.
- A line cap via ``MAX_RENDER_LINES`` protects performance with very large files.

Key bindings: q (Back), j/k (Scroll), Shift+G (End), Shift+K (Toggle keyword filter), Shift+A (Anchor bottom).
"""

import os

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static

from delta_vision.utils.config import MAX_RENDER_LINES
from delta_vision.utils.io import read_text
from delta_vision.utils.logger import log
from delta_vision.utils.text import make_keyword_pattern
from delta_vision.utils.watchdog import start_observer
from delta_vision.widgets.footer import Footer
from delta_vision.widgets.header import Header

from .keywords_parser import parse_keywords_md
from .watchdog_helper import start_watchdog


class StreamScreen(Screen):
    """Live stream of files in a folder with optional keyword filtering.

    The screen lists files by oldest-first modification time and updates when
    changes are detected. Use K to toggle showing only lines around keyword
    matches. Press q to return to the previous screen.
    """

    # Show keys in Textual help and route to actions
    BINDINGS = [
        ("q", "go_home", "Back"),
        ("j", "scroll_down", "Down"),
        ("k", "scroll_up", "Up"),
        ("G", "scroll_end", "End"),
        ("K", "toggle_keywords", "Keywords"),
        ("A", "toggle_anchor", "Anchor Bottom"),
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
            except Exception:
                pass
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

    def compose(self) -> ComposeResult:
        """Build the static layout: header, scrollable body, and footer."""
        # Declarative layout: Header, scroll container, Footer
        yield Header(page_name="Stream", show_clock=True)
        yield Vertical(id="stream-main-scroll")
        yield Footer(
            text=" [orange1]q[/orange1] Back    [orange1]Shift+K[/orange1] Keywords    "
            "[orange1]Shift+A[/orange1] Anchor Bottom",
            classes="footer-stream",
        )

    def on_mount(self):
        """Wire up state, start the filesystem observer, and paint initial view."""
        # Set the screen title so the built-in Header shows it
        self.title = "Delta Vision — Stream"
        # Grab references to composed widgets
        try:
            self.scroll_container = self.query_one('#stream-main-scroll', Vertical)
        except Exception:
            self.scroll_container = Vertical(id="stream-main-scroll")
            self.mount(self.scroll_container)
        self.file_panels = {}
        if not self.folder_path or not os.path.isdir(self.folder_path):
            try:
                self.mount(Static("No valid folder specified."))
            except Exception:
                pass
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
            except Exception:
                app = None
            if app:
                try:
                    app.call_later(self.refresh_stream)
                except Exception:
                    pass

        log(f"[STREAM] Starting watchdog for: {self.folder_path}")
        try:
            self._observer, self._stop_observer = start_observer(self.folder_path, trigger_refresh)
        except Exception:
            # Fall back to legacy helper if utils.watchdog fails for any reason
            self._observer = start_watchdog(self.folder_path, trigger_refresh)
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
                    except Exception:
                        pass
                    try:
                        obs.join(timeout=0.5)
                    except Exception:
                        pass
        except Exception:
            pass
        self._observer = None
        self._stop_observer = None

    # Action method for the 'q' binding
    def action_go_home(self):
        """Return to the previous screen."""
        try:
            self.app.pop_screen()
        except Exception:
            pass

    # Action methods for navigation and toggles
    def action_scroll_down(self):
        """Scroll the stream body down by one step."""
        try:
            self.query_one('#stream-main-scroll').scroll_down()
        except Exception:
            pass

    def action_scroll_up(self):
        """Scroll the stream body up by one step."""
        try:
            self.query_one('#stream-main-scroll').scroll_up()
        except Exception:
            pass

    def action_scroll_end(self):
        """Jump to the bottom of the stream."""
        try:
            self.query_one('#stream-main-scroll').scroll_end()
            self._last_g = False
        except Exception:
            pass

    def action_toggle_keywords(self):
        """Enable/disable the keyword filter and repaint."""
        try:
            self.keyword_filter_enabled = not bool(self.keyword_filter_enabled)
            self.refresh_stream()
        except Exception:
            pass

    def action_toggle_anchor(self):
        """Toggle bottom anchor mode for auto-scrolling to new content."""
        try:
            self._anchor_bottom = not self._anchor_bottom
            if self._anchor_bottom:
                # Scroll to bottom immediately when enabling anchor
                self.query_one('#stream-main-scroll').scroll_end()
        except Exception:
            pass

    def refresh_stream(self):
        """Rebuild file panels and content.

        Called on mount and whenever the watchdog signals a change. Reuses
        existing panels when the file metadata hasn't changed and the filter
        state is stable to avoid unnecessary work.
        """
        # This method is called on file changes
        import re

        log("[DEBUG] refresh_stream called")
        folder_path = self.folder_path
        if not folder_path or not os.path.isdir(folder_path):
            log("[DEBUG] Folder path invalid or not a directory")
            return
        keywords_dict = self.keywords_dict
        files = [
            os.path.join(folder_path, f)
            for f in os.listdir(folder_path)
            if os.path.isfile(os.path.join(folder_path, f))
        ]
        log(f"[DEBUG] Files found: {files}")
        files.sort(key=lambda f: os.path.getmtime(f))
        # Keep files in oldest-first order (removed [::-1] reverse)
        # Build normalized keyword lookup and a single compiled regex
        keyword_lookup: dict[str, tuple[str, str]] = {}
        if keywords_dict:
            for cat, (color, words) in keywords_dict.items():
                for w in words:
                    if not w:
                        continue
                    keyword_lookup[w.lower()] = (color, cat)
        kw_pattern = (
            make_keyword_pattern(keyword_lookup.keys(), whole_word=True, case_insensitive=True)
            if keyword_lookup
            else None
        )

        def highlight_keywords(line: str) -> str:
            if not kw_pattern:
                return escape(line)
            out = []
            last = 0
            for m in kw_pattern.finditer(line):
                out.append(escape(line[last : m.start()]))
                matched = m.group(0)
                color = keyword_lookup.get(matched.lower(), ("yellow", ""))[0].lower()
                out.append(f"[u][{color}]{escape(matched)}[/{color}][/u]")
                last = m.end()
            out.append(escape(line[last:]))
            return "".join(out)

        # Incremental update: reuse panels if file unchanged and filter state hasn't changed
        new_file_panels = {}
        filter_changed = self._last_filter_state != bool(self.keyword_filter_enabled)
        for file_path in files:
            try:
                st = os.stat(file_path)
                cur_meta = (int(st.st_mtime), int(st.st_size))
            except Exception:
                cur_meta = None
            prev_meta = self._file_meta.get(file_path)

            panel = self.file_panels.get(file_path)
            # If unchanged and no filter toggle, reuse existing panel without reread
            if (not filter_changed) and prev_meta is not None and cur_meta == prev_meta and panel is not None:
                new_file_panels[file_path] = panel
                continue

            content, _enc = read_text(file_path)
            if not content:
                try:
                    content = f"[Error reading {os.path.basename(file_path)}]"
                except Exception:
                    content = "[Error reading file]"
            match = re.search(r'"([^"]+)"', content)
            title = match.group(1) if match else os.path.basename(file_path)
            self._titles[file_path] = title
            content_lines = content.splitlines()[1:] if len(content.splitlines()) > 1 else []

            # Keyword filter logic
            show_file = True
            filtered_indices = []  # indices into content_lines (0-based)
            if self.keyword_filter_enabled and kw_pattern:
                # Find all lines with a keyword
                keyword_lines = set()
                for i, line in enumerate(content_lines):
                    if kw_pattern.search(line):
                        keyword_lines.add(i)
                if not keyword_lines:
                    show_file = False
                else:
                    # Add ±3 lines around each match (keep original indices)
                    show_lines = set()
                    for idx in keyword_lines:
                        for j in range(max(0, idx - 3), min(len(content_lines), idx + 4)):
                            show_lines.add(j)
                    filtered_indices = sorted(show_lines)
            if self.keyword_filter_enabled and kw_pattern:
                if not show_file:
                    continue  # Skip this file
                # Build list of texts (not original indices); we'll number from 1
                lines_to_show = [content_lines[i] for i in filtered_indices]
            else:
                # Unfiltered: include all lines as text; we'll number from 1
                lines_to_show = content_lines

            # Apply line cap for performance
            truncated = False
            try:
                if MAX_RENDER_LINES and len(lines_to_show) > MAX_RENDER_LINES:
                    lines_to_show = lines_to_show[:MAX_RENDER_LINES]
                    truncated = True
            except Exception:
                pass

            # Render with display-relative line numbers starting at 1
            numbered_lines = []
            for display_idx, text in enumerate(lines_to_show, start=1):
                numbered_lines.append(f"{display_idx:>6} │ {highlight_keywords(text)}")
            content_with_numbers = "\n".join(numbered_lines)

            # Update or create panel in place
            needs_recreate = False
            if panel:
                try:
                    file_content_widget = panel.query_one('.file-content')
                    file_title_widget = panel.query_one('.file-title')
                except Exception:
                    needs_recreate = True
            if not panel or needs_recreate:
                panel = Vertical(
                    Static(title + (" (truncated)" if truncated else ""), classes="file-title"),
                    Static(content_with_numbers, classes="file-content", markup=True),
                    classes="file-panel",
                )
                self.scroll_container.mount(panel)
            else:
                file_content_widget.update(content_with_numbers)
                file_title_widget.update(title + (" (truncated)" if truncated else ""))
                try:
                    # Force layout to recalc sizes when content shrinks
                    panel.refresh(layout=True)
                except Exception:
                    pass
            new_file_panels[file_path] = panel
            # Update cache after successful update
            if cur_meta is not None:
                self._file_meta[file_path] = cur_meta

        # Remove panels for deleted files
        for old_path in list(self.file_panels.keys()):
            if old_path not in new_file_panels:
                self.file_panels[old_path].remove()
                del self.file_panels[old_path]

        # Reorder panels in scroll_container to match files order (no full clear)
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
        except Exception:
            pass
