from __future__ import annotations

import os
import re

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import ListItem, ListView, Static

from delta_vision.utils.io import read_lines
from delta_vision.utils.logger import log
from delta_vision.widgets.footer import Footer
from delta_vision.widgets.header import Header

from .keywords_parser import parse_keywords_md


class FileViewerScreen(Screen):
    """Simple file viewer that opens a file and jumps to a specific line."""

    BINDINGS = [
        ("q", "go_back", "Back"),
        ("j", "next_line", "Down"),
        ("k", "prev_line", "Up"),
        ("G", "end", "End"),
        ("K", "toggle_keywords", "Keywords"),
    ]

    CSS_PATH = "stream.tcss"

    def __init__(self, file_path: str, line_no: int = 1, title: str | None = None, keywords_path: str | None = None):
        super().__init__()
        self.file_path = file_path
        self.line_no = max(1, int(line_no or 1))
        self.viewer_title = title or f"Viewer — {os.path.basename(file_path)}"
        # UI refs
        self._list = None
        # Keyword highlighting
        self.keywords_path = keywords_path
        self.keywords_dict = None
        self.keyword_highlight_enabled = False
        # Cached state for smooth repaints
        self._display_lines = []
        self._keyword_lookup = {}
        self._sorted_keywords = []
        self._line_widgets = []
        self._target_index = 0
        # Vim-like navigation support (double 'g')
        self._last_g = False
        # Render limits
        self._max_render_lines = 5000

    def compose(self) -> ComposeResult:
        yield Header(page_name="Viewer", show_clock=True)
        with Vertical(id="viewer-root"):
            with Vertical(classes="file-panel"):
                yield Static("", id="viewer-title", classes="file-title")
                yield Static("", id="viewer-subtitle", classes="file-subtitle")
                with Vertical(classes="file-content"):
                    self._list = ListView(id="viewer-list")
                    yield self._list
            yield Footer(
                text=" [orange1]q[/orange1] Back    [orange1]Shift+K[/orange1] Keywords", classes="footer-stream"
            )

    def on_mount(self):
        self.title = self.viewer_title
        content, _enc = read_lines(self.file_path)
        if not content:
            content = ["[Error reading file]"]

        # Parse keywords if provided
        if self.keywords_path and os.path.isfile(self.keywords_path):
            try:
                self.keywords_dict = parse_keywords_md(self.keywords_path)
            except (OSError, IOError, ValueError, AttributeError):
                log(f"Failed to parse keywords file {self.keywords_path}")
                self.keywords_dict = None

        # Hide the first line (date/command header) from display
        all_display_lines = content[1:] if len(content) > 0 else []
        truncated = False
        if len(all_display_lines) > self._max_render_lines:
            display_lines = all_display_lines[: self._max_render_lines]
            truncated = True
        else:
            display_lines = all_display_lines
        self._display_lines = display_lines

        # Compute target index (line 2 maps to index 0)
        if self.line_no <= 1:
            target_index = 0 if display_lines else 0
        else:
            target_index = max(0, min(len(display_lines) - 1, self.line_no - 2))
        self._target_index = target_index

        # Update title with command from header line (between quotes)
        try:
            title_widget = self.query_one('#viewer-title', Static)
            subtitle_widget = self.query_one('#viewer-subtitle', Static)
            header_line = content[0] if content else ""
            cmd_match = re.search(r'"([^"]+)"', header_line) if header_line else None
            title_text = cmd_match.group(1) if cmd_match else self.viewer_title
            title_widget.update(title_text)
            if truncated:
                total = len(all_display_lines)
                shown = len(display_lines)
                subtitle_widget.update(f"Showing {shown} of {total} lines (truncated)")
            else:
                subtitle_widget.update("")
        except (AttributeError, RuntimeError):
            log("Failed to update title and subtitle widgets")
            pass

        if self._list is not None:
            try:
                self._list.clear()
            except (AttributeError, RuntimeError):
                log("Failed to clear list widget")
                pass

            # Build keyword caches
            self._keyword_lookup = {}
            if self.keywords_dict:
                for _cat, (color, words) in self.keywords_dict.items():
                    for w in words:
                        self._keyword_lookup[w] = color
            self._sorted_keywords = sorted(self._keyword_lookup.keys(), key=len, reverse=True)

            # Build line widgets and keep references for smooth repaint
            self._line_widgets = []
            for i, line in enumerate(self._display_lines):
                markup = self._render_markup_for_line(i, line)
                static = Static(Text.from_markup(markup))
                self._line_widgets.append(static)
                self._list.append(ListItem(static))

            # Set initial selection/scroll
            try:
                self._list.index = target_index
            except (AttributeError, ValueError, IndexError):
                log(f"Failed to set list index to {target_index}")
                pass

    def action_go_back(self):
        try:
            self.app.pop_screen()
        except (AttributeError, RuntimeError):
            log("Failed to pop screen")
            pass

    def on_key(self, event):
        # Preserve only double-"g" go-to-top behavior here; other keys are actions
        key = getattr(event, 'key', None)
        if key == 'g':
            lv = self._list
            if not lv:
                return
            try:
                self.set_focus(lv)
            except (AttributeError, RuntimeError):
                log("Failed to set focus on list view")
                pass
            try:
                event.stop()
            except AttributeError:
                log("Failed to stop event")
                pass
            # no-op read of index removed (was unused)
            total = len(self._display_lines) if self._display_lines else 0

            def set_index(i: int):
                try:
                    lv.index = i
                    scroll_to_index = getattr(lv, 'scroll_to_index', None)
                    if callable(scroll_to_index):
                        scroll_to_index(i)
                except (AttributeError, ValueError, IndexError):
                    log(f"Failed to set list index to {i}")
                    pass

            if self._last_g:
                if total:
                    set_index(0)
                self._last_g = False
            else:
                self._last_g = True
            return
        else:
            self._last_g = False

    # --- Actions for help/discoverability ---
    def action_next_line(self):
        lv = self._list
        if not lv:
            return
        try:
            self.set_focus(lv)
        except (AttributeError, RuntimeError):
            log("Failed to set focus on list view in next_line")
            pass
        try:
            cur = getattr(lv, 'index', 0) or 0
        except AttributeError:
            log("Failed to get current list index in next_line")
            cur = 0
        total = len(self._display_lines) if self._display_lines else 0
        if total:
            try:
                new_i = min(cur + 1, total - 1)
                lv.index = new_i
                scroll_to_index = getattr(lv, 'scroll_to_index', None)
                if callable(scroll_to_index):
                    scroll_to_index(new_i)
            except (AttributeError, ValueError, IndexError):
                log(f"Failed to move to next line (index {cur + 1})")
                pass
        self._last_g = False

    def action_prev_line(self):
        lv = self._list
        if not lv:
            return
        try:
            self.set_focus(lv)
        except (AttributeError, RuntimeError):
            log("Failed to set focus on list view in prev_line")
            pass
        try:
            cur = getattr(lv, 'index', 0) or 0
        except AttributeError:
            log("Failed to get current list index in prev_line")
            cur = 0
        if True:
            try:
                new_i = max(cur - 1, 0)
                lv.index = new_i
                scroll_to_index = getattr(lv, 'scroll_to_index', None)
                if callable(scroll_to_index):
                    scroll_to_index(new_i)
            except (AttributeError, ValueError, IndexError):
                log(f"Failed to move to previous line (index {cur - 1})")
                pass
        self._last_g = False

    def action_end(self):
        lv = self._list
        if not lv:
            return
        try:
            self.set_focus(lv)
        except (AttributeError, RuntimeError):
            log("Failed to set focus on list view in end")
            pass
        total = len(self._display_lines) if self._display_lines else 0
        if total:
            try:
                lv.index = total - 1
                scroll_to_index = getattr(lv, 'scroll_to_index', None)
                if callable(scroll_to_index):
                    scroll_to_index(total - 1)
            except (AttributeError, ValueError, IndexError):
                log(f"Failed to jump to end (index {total - 1})")
                pass
        self._last_g = False

    def action_toggle_keywords(self):
        self.keyword_highlight_enabled = not self.keyword_highlight_enabled
        self._repaint_highlighting()

    def _render_markup_for_line(self, i: int, line: str) -> str:
        disp_num = i + 1
        orig_idx = i + 2
        left = f"[dim]{disp_num:>6} │ [/dim]"
        content = line
        if self.keyword_highlight_enabled and self._sorted_keywords:
            for kw in self._sorted_keywords:
                color = self._keyword_lookup.get(kw)
                if not color:
                    continue
                pattern = rf'(?<!\\w)({re.escape(kw)})(?!\\w)'
                repl = rf'[u][{color.lower()}]\1[/{color.lower()}][/u]'
                content = re.sub(pattern, repl, content)
        if orig_idx == self.line_no:
            content = f"[on grey23]{content}[/on grey23]"
        return left + content

    def _repaint_highlighting(self):
        # Update text of existing items in place to avoid flashing
        try:
            for i, static in enumerate(self._line_widgets):
                if i < len(self._display_lines):
                    markup = self._render_markup_for_line(i, self._display_lines[i])
                    static.update(Text.from_markup(markup))
        except (AttributeError, ValueError, IndexError, UnicodeError):
            log("Failed to repaint highlighting")
            pass
