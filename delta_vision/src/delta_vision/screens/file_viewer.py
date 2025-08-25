from __future__ import annotations

import os
import re

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import ListItem, Static

from delta_vision.utils.config import config
from delta_vision.utils.io import read_lines
from delta_vision.utils.keyword_highlighter import highlighter
from delta_vision.utils.logger import log
from delta_vision.utils.watchdog import start_observer
from delta_vision.widgets.footer import Footer
from delta_vision.widgets.header import Header

from .keywords_parser import parse_keywords_md


class FileViewerScreen(Screen):
    """Simple file viewer that opens a file and jumps to a specific line."""

    CSS_PATH = "viewer.tcss"

    BINDINGS = [
        ("q", "go_back", "Back"),
        ("j", "next_line", "Down"),
        ("k", "prev_line", "Up"),
        ("G", "end", "End"),
        ("ctrl+k", "toggle_keywords", "Keywords"),
    ]

    CSS_PATH = "viewer.tcss"

    def __init__(
        self,
        file_path: str,
        line_no: int = 1,
        title: str | None = None,
        keywords_path: str | None = None,
        keywords_enabled: bool = True,
    ):
        super().__init__()
        self.page_name = title or f"Viewer — {os.path.basename(file_path)}"
        self.title = f"Delta Vision — {self.page_name}"
        self.file_path = file_path
        self.line_no = max(1, int(line_no or 1))
        # UI refs
        self._file_panel = None
        # Keyword highlighting
        self.keywords_path = keywords_path
        self.keywords_dict = None
        self.keyword_highlight_enabled = keywords_enabled
        # Cached state
        self._display_lines = []
        self._keyword_lookup = {}
        self._sorted_keywords = []
        # Vim-like navigation support (double 'g')
        self._last_g = False
        # Render limits
        self._max_render_lines = config.max_render_lines
        # Watchdog observer for live updates
        self._observer = None
        self._stop_observer = None

    def compose(self) -> ComposeResult:
        # Standard header
        yield Header(page_name=self.page_name, show_clock=True)

        # Main content exactly like stream screen - simple scrollable container
        yield Vertical(id="viewer-main-scroll")

        # Standard footer
        yield Footer(text=self.get_footer_text())

    def get_footer_text(self) -> str:
        keywords_state = "ON" if self.keyword_highlight_enabled else "OFF"
        return f" [orange1]q[/orange1] Back    [orange1]Ctrl+K[/orange1] Keywords: {keywords_state}"

    def action_go_back(self):
        """Go back to the previous screen."""
        self.app.pop_screen()

    async def on_mount(self):
        content, _enc = read_lines(self.file_path)
        if not content:
            content = ["[Error reading file]"]

        # Parse keywords if provided
        if self.keywords_path and os.path.isfile(self.keywords_path):
            try:
                self.keywords_dict = parse_keywords_md(self.keywords_path)
            except (OSError, ValueError, AttributeError):
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

        # Build keyword caches
        self._keyword_lookup = {}
        if self.keywords_dict:
            for _cat, (color, words) in self.keywords_dict.items():
                for w in words:
                    self._keyword_lookup[w] = color
        self._sorted_keywords = (
            sorted(self._keyword_lookup.keys(), key=len, reverse=True) if self._keyword_lookup else []
        )

        # Create title from header line (between quotes) - exactly like stream screen
        header_line = content[0] if content else ""
        cmd_match = re.search(r'"([^"]+)"', header_line) if header_line else None
        title_text = cmd_match.group(1) if cmd_match else self.page_name

        # Add truncation info to the title if needed
        if truncated:
            total = len(all_display_lines)
            shown = len(display_lines)
            title_text = f"{title_text} (Showing {shown} of {total} lines)"

        # Create content with line numbers - exactly like stream screen
        content_lines = []
        for i, line in enumerate(display_lines):
            # Create display content with line numbers
            line_display = f"{i + 2:4}│ {line}"

            # Apply keyword highlighting if enabled
            if self.keyword_highlight_enabled and self._sorted_keywords:
                line_display = self._apply_keyword_highlighting(line_display)

            content_lines.append(line_display)

        content_with_numbers = "\n".join(content_lines)

        # Get the scroll container and mount the file panel - exactly like stream screen
        try:
            scroll_container = self.query_one('#viewer-main-scroll')

            # Create file panel with same structure as stream screen
            file_panel = Vertical(
                Static(title_text, classes="file-command"),
                Static(content_with_numbers, classes="file-content", markup=True),
                classes="file-panel",
            )

            scroll_container.mount(file_panel)
            self._file_panel = file_panel
        except Exception as e:
            log(f"Failed to create file panel: {e}")

        # Start watchdog observer for live updates
        self._start_file_observer()

    def _start_file_observer(self):
        """Start file system observer for the viewed file."""

        def trigger_refresh():
            """Callback for filesystem changes."""
            try:
                self.call_later(self.refresh_file)
            except Exception as e:
                log(f"[ERROR] Failed in trigger_refresh: {e}")

        # Start observer for the viewed file
        try:
            if self.file_path and os.path.isfile(self.file_path):
                self._observer, self._stop_observer = start_observer(
                    os.path.dirname(self.file_path), trigger_refresh, debounce_ms=250
                )
        except (OSError, RuntimeError) as e:
            log(f"Failed to start observer for file {self.file_path}: {e}")
            self._observer = None
            self._stop_observer = None

    def refresh_file(self):
        """Refresh the file viewer when the file changes."""
        # Store current selection index for restoration
        current_index = 0
        try:
            if self._list:
                current_index = getattr(self._list, 'index', 0) or 0
        except (AttributeError, RuntimeError):
            log("Failed to capture current list index")

        # Re-read file and rebuild view
        try:
            content, _enc = read_lines(self.file_path)
            if not content:
                content = ["[Error reading file]"]

            # Parse keywords if provided
            if self.keywords_path and os.path.isfile(self.keywords_path):
                try:
                    self.keywords_dict = parse_keywords_md(self.keywords_path)
                except (OSError, ValueError, AttributeError):
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

            if self._list is not None:
                try:
                    self._list.clear()
                except (AttributeError, RuntimeError):
                    log("Failed to clear list widget")

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

                # Restore selection/scroll to preserved position
                try:
                    # Ensure the index is within bounds
                    max_index = len(self._display_lines) - 1
                    restore_index = min(current_index, max_index) if max_index >= 0 else 0
                    self._list.index = restore_index
                except (AttributeError, ValueError, IndexError):
                    log(f"Failed to restore list index to {current_index}")

        except (OSError, RuntimeError) as e:
            log(f"Failed to refresh file viewer: {e}")

    def on_unmount(self):
        """Stop observer when leaving the screen."""
        if self._stop_observer:
            try:
                self._stop_observer()
            except Exception as e:
                log(f"Failed to stop file observer: {e}")

    def on_key(self, event):
        # Preserve only double-"g" go-to-top behavior here; other keys are actions
        key = getattr(event, 'key', None)
        if key == 'g':
            lv = self._list
            if not lv:
                return
            self.safe_set_focus(lv)
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
        """Scroll down by one line."""
        try:
            scroll_container = self.query_one('#viewer-main-scroll')
            scroll_container.scroll_down(animate=False)
        except Exception as e:
            log(f"Failed to scroll down: {e}")
        self._last_g = False

    def action_prev_line(self):
        """Scroll up by one line."""
        try:
            scroll_container = self.query_one('#viewer-main-scroll')
            scroll_container.scroll_up(animate=False)
        except Exception as e:
            log(f"Failed to scroll up: {e}")
        self._last_g = False

    def action_end(self):
        """Scroll to the end of the content."""
        try:
            scroll_container = self.query_one('#viewer-main-scroll')
            scroll_container.scroll_end(animate=False)
        except Exception as e:
            log(f"Failed to scroll to end: {e}")
        self._last_g = False

    def action_toggle_keywords(self):
        self.keyword_highlight_enabled = not self.keyword_highlight_enabled
        self._repaint_highlighting()
        self._update_footer()

    def _update_footer(self):
        """Update footer text with current keyword toggle state."""
        try:
            from rich.text import Text
            from textual.widgets import Footer

            footer = self.query_one(Footer)
            footer.update(Text.from_markup(self.get_footer_text()))
        except Exception as e:
            log(f"Failed to update footer: {e}")

    def _render_markup_for_line(self, i: int, line: str) -> str:
        disp_num = i + 1
        orig_idx = i + 2
        left = f"[dim]{disp_num:>6} │ [/dim]"
        content = line
        if self.keyword_highlight_enabled and self._sorted_keywords:
            # Use centralized keyword highlighter with the sorted keywords and color lookup
            content = highlighter.highlight_with_color_lookup(
                line=content, keywords=self._sorted_keywords, color_lookup=self._keyword_lookup, case_sensitive=False
            )
        if orig_idx == self.line_no:
            content = f"[on grey23]{content}[/on grey23]"
        return left + content

    def _repaint_highlighting(self):
        """Update highlighting in the content Static widget."""
        try:
            if not hasattr(self, '_file_panel') or not hasattr(self, '_display_lines'):
                return

            # Regenerate content with current keyword highlighting state
            content_lines = []
            for i, line in enumerate(self._display_lines):
                # Create display content with line numbers
                line_display = f"{i + 2:4}│ {line}"

                # Apply keyword highlighting if enabled
                if self.keyword_highlight_enabled and self._sorted_keywords:
                    line_display = self._apply_keyword_highlighting(line_display)

                content_lines.append(line_display)

            content_with_numbers = "\n".join(content_lines)

            # Update the file-content Static widget
            content_widget = self._file_panel.query_one('.file-content', Static)
            content_widget.update(content_with_numbers)

        except (AttributeError, ValueError, IndexError, UnicodeError) as e:
            log(f"Failed to repaint highlighting: {e}")
            pass

    def _apply_keyword_highlighting(self, text: str) -> str:
        """Apply keyword highlighting to text using the centralized highlighter."""
        if not self.keywords_dict or not self._sorted_keywords:
            return text

        return highlighter.highlight_with_color_lookup(
            text, self._sorted_keywords, self._keyword_lookup, case_sensitive=False
        )
