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
from textual.screen import Screen
from textual.widgets import Static, Tab, Tabs

from delta_vision.utils.config import MAX_PREVIEW_CHARS
from delta_vision.utils.fs import format_mtime, get_mtime, minutes_between
from delta_vision.utils.text import make_keyword_pattern
from delta_vision.widgets.footer import Footer
from delta_vision.widgets.header import Header

from .keywords_parser import parse_keywords_md


class SideBySideDiffScreen(Screen):
    """Show a side-by-side diff between two files (NEW vs OLD).

    The first line of each file (header) is ignored for the diff.
    """

    BINDINGS = [
        ("q", "go_back", "Back"),
        ("K", "toggle_highlights", "Toggle Highlights"),
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
        super().__init__()
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

    def compose(self) -> ComposeResult:
        """Build and yield the header, tabs, two file panels, and a footer.

        Note: Titles/subtitles and file contents are populated in
        ``on_mount`` once metadata and rows are available.
        """
        # Title updated on_mount once we parse command
        yield Header(page_name="Diff", show_clock=True)
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
            # Footer inside compose scope
            yield Footer(
                text=(" [orange1]q[/orange1] Back    " "[orange1]Shift+K[/orange1] Toggle Highlights"),
                classes="footer-stream",
            )

    def on_mount(self):
        """Parse header metadata, build tabs, and render the initial view.

        - Derives command/date/time from the first line of each file
        - Builds a keyword regex (if provided) for optional underlining
        - Creates tabs for OLD and prior NEW occurrences and selects a default
        - Populates the left/right panels with the initial diff
        """
        # Try to show command in the title, like the file viewer
        # Also parse date/time for subtitles
        self._new_meta = self._parse_header_meta(self.new_path) or {"date": None, "time": None, "cmd": None}
        self._old_meta = self._parse_header_meta(self.old_path) or {"date": None, "time": None, "cmd": None}
        cmd = self._new_meta.get("cmd") or self._old_meta.get("cmd")
        self.title = f"{cmd} — Diff" if cmd else "Delta Vision — Diff"
        try:
            header = self.query_one(Header)
            header.title = self.title
        except Exception:
            pass
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
        except Exception:
            self._kw_pattern = None

        # Build tab set (latest vs others) and populate initial view
        try:
            self._build_tabs_and_select_default()
        except Exception:
            # Fallback to the provided pair only
            old_lines, new_lines = self._read_files()
            rows = self._build_rows(old_lines, new_lines)
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
                except Exception:
                    pass
        except Exception:
            self._left_content = None
            self._right_content = None

    def _build_tabs_and_select_default(self):
        """Create tabs for latest vs OLD and latest vs each prior NEW occurrence."""
        # Determine the command and folder to search
        latest_new = self._newest_for_command(self.new_path)
        if latest_new is None:
            latest_new = self.new_path

        meta0 = self._parse_header_meta(latest_new) if latest_new else None
        cmd = meta0.get("cmd") if isinstance(meta0, dict) else None
        folder = os.path.dirname(latest_new) if latest_new else None
        occurrences: list[str] = []
        if cmd and folder and os.path.isdir(folder):
            occurrences = self._find_occurrences(folder, cmd)

        # Ensure the absolute newest appears as the baseline; other occurrences
        # (older NEWs) become additional tabs for comparison.
        others = [p for p in occurrences if p != latest_new]

        tabs = self._tabs
        if tabs is None:
            return

        # Clear any existing tabs to avoid duplicates on rebuild
        try:
            clear = getattr(tabs, "clear", None)
            if callable(clear):
                clear()
        except Exception:
            # If clear() is unavailable or fails, proceed; we'll overwrite maps
            pass

        # Build fresh tabs and reset internal maps used for cycling and lookup
        self._tab_map = {}
        self._tab_order = []
        default_tab_id: str | None = None

        # Add prior NEW comparisons first (2nd newest, 3rd newest, ...)
        for idx, other in enumerate(others, start=1):
            # Directional minutes with sign: floor((latest - other)/60)
            # A negative value means "older than latest".
            mins = None
            try:
                t_latest = get_mtime(latest_new)
                t_other = get_mtime(other)
                if t_latest is not None and t_other is not None:
                    mins = math.floor((t_latest - t_other) / 60.0)
            except Exception:
                mins = None
            meta = self._parse_header_meta(other) or {}
            fallback = meta.get("date") or os.path.basename(other)
            label = f"{mins:+d}m" if mins is not None else fallback
            tab_id = f"n{idx}"
            tabs.add_tab(Tab(label, id=tab_id))
            self._tab_map[tab_id] = (other, latest_new)
            self._tab_order.append(tab_id)
            if default_tab_id is None:
                default_tab_id = tab_id

        # Add OLD comparison last (if present)
        # Note: add even if the file may be missing to avoid an empty Tabs bar; content will show an error
        if self.old_path:
            tab_id = "old"
            tabs.add_tab(Tab("OLD", id=tab_id))
            self._tab_map[tab_id] = (self.old_path, latest_new)
            self._tab_order.append(tab_id)
            if default_tab_id is None:
                default_tab_id = tab_id

        # Fallback: if no tabs were added (e.g., missing files and no prior NEWs),
        # create a safe default so the Tabs widget always has one option.
        if default_tab_id is None:
            try:
                tab_id = "current"
                tabs.add_tab(Tab("CURRENT", id=tab_id))
                # Map to whatever we have; _read_files() will handle missing files gracefully
                self._tab_map[tab_id] = (self.old_path or self.new_path, latest_new)
                self._tab_order.append(tab_id)
                default_tab_id = tab_id
            except Exception:
                pass

        # Select default tab and populate the panels
        if default_tab_id:
            try:
                tabs.active = default_tab_id
                self._active_tab_id = default_tab_id
            except Exception:
                pass
            pair = self._tab_map.get(default_tab_id)
            if pair:
                self._set_pair_and_populate(pair[0], pair[1])
        else:
            old_lines, new_lines = self._read_files()
            rows = self._build_rows(old_lines, new_lines)
            self._rows_cache = rows
            self._populate(rows)

    def _newest_for_command(self, some_path: str) -> str | None:
        """Return the newest file in the same folder with the same command as some_path."""
        meta = self._parse_header_meta(some_path) or {}
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
                    meta = self._parse_header_meta(path) or {}
                    if meta.get("cmd") == cmd:
                        items.append((path, os.path.getmtime(path)))
                except Exception:
                    continue
        except Exception:
            pass
        items.sort(key=lambda t: t[1], reverse=True)
        return [p for p, _ in items]

    def _set_pair_and_populate(self, older_path: str, latest_path: str):
        """Set the current paths and repaint panels accordingly."""
        self.old_path = older_path
        self.new_path = latest_path
        # Update metadata and repaint
        self._old_meta = self._parse_header_meta(self.old_path) or {"date": None, "time": None, "cmd": None}
        self._new_meta = self._parse_header_meta(self.new_path) or {"date": None, "time": None, "cmd": None}
        # Refresh created timestamps for subtitles
        self._old_created = format_mtime(self.old_path)
        self._new_created = format_mtime(self.new_path)
        old_lines, new_lines = self._read_files()
        rows = self._build_rows(old_lines, new_lines)
        self._rows_cache = rows
        self._populate(rows)

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
        except Exception:
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
        except Exception:
            # As a fallback, populate directly
            pair = self._tab_map.get(target_id)
            if pair:
                self._set_pair_and_populate(pair[0], pair[1])

    def on_key(self, event):
        """Handle vim-like scrolling and tab navigation keys.

        - j/k scroll both panels
        - g then g goes to top (like ``gg``)
        - G goes to end
        - K toggles keyword underlining
        - h/l move to previous/next tab
        """
        key = getattr(event, 'key', None)
        if key is None:
            return

        def both(fn_name: str):
            for widget in (self._left_content, self._right_content):
                try:
                    if widget is None:
                        continue
                    fn = getattr(widget, fn_name, None)
                    if callable(fn):
                        fn()
                except Exception:
                    pass

        if key == 'j':
            both('scroll_down')
            self._last_g = False
            try:
                event.stop()
            except Exception:
                pass
        elif key == 'k':
            both('scroll_up')
            self._last_g = False
            try:
                event.stop()
            except Exception:
                pass
        elif key == 'G':
            both('scroll_end')
            self._last_g = False
            try:
                event.stop()
            except Exception:
                pass
        elif key == 'g':
            try:
                event.stop()
            except Exception:
                pass
            if self._last_g:
                both('scroll_home')
                self._last_g = False
            else:
                self._last_g = True
        elif key == 'K':
            # Route to action for discoverability/help integration
            self.action_toggle_highlights()
            try:
                event.stop()
            except Exception:
                pass
        elif key == 'h':
            # Previous tab
            self.action_prev_tab()
            try:
                event.stop()
            except Exception:
                pass
        elif key == 'l':
            # Next tab
            self.action_next_tab()
            try:
                event.stop()
            except Exception:
                pass
        else:
            self._last_g = False

    def action_go_back(self):
        """Close this screen and return to the previous one."""
        try:
            self.app.pop_screen()
        except Exception:
            pass

    def action_toggle_highlights(self):
        """Toggle keyword highlighting in the diff and repaint."""
        try:
            self.keyword_highlight_enabled = not self.keyword_highlight_enabled
            self._populate(self._rows_cache)
        except Exception:
            pass

    def action_prev_tab(self):
        """Activate the previous tab (if any)."""
        try:
            self._cycle_tab(-1)
        except Exception:
            pass

    def action_next_tab(self):
        """Activate the next tab (if any)."""
        try:
            self._cycle_tab(1)
        except Exception:
            pass

    # Prev/Next file navigation via p/n has been removed per request.

    def _read_files(self) -> tuple[list[str], list[str]]:
        """Read OLD/NEW files as lists of lines, skipping the header line.

        Tries a few common encodings strictly, then falls back to utf-8 with
        errors="ignore". On read failure, returns a single-line error message
        list. The first line of each file (header) is excluded from the
        returned content.
        """

        def read(fp: str) -> list[str]:
            # Try common encodings, ignore header
            for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
                try:
                    with open(fp, encoding=enc, errors="strict") as f:
                        lines = f.read().splitlines()
                    return lines[1:] if lines else []
                except UnicodeDecodeError:
                    continue
                except Exception:
                    return ["[Error reading file]"]
            try:
                with open(fp, encoding="utf-8", errors="ignore") as f:
                    lines = f.read().splitlines()
                return lines[1:] if lines else []
            except Exception:
                return ["[Error reading file]"]

        return read(self.old_path), read(self.new_path)

    def _first_line_command(self, file_path: str) -> str | None:
        """Extract the quoted command from the first line, if present."""
        if not file_path or not os.path.isfile(file_path):
            return None
        # Try multiple encodings
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                with open(file_path, encoding=enc, errors="strict") as f:
                    first = f.readline()
                break
            except UnicodeDecodeError:
                continue
            except Exception:
                return None
        else:
            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    first = f.readline()
            except Exception:
                return None
        m = re.search(r'"([^"]+)"', first or "")
        return m.group(1) if m else None

    def _parse_header_meta(self, file_path: str):
        """Parse header line for date/time and command.

        Expected formats:
        - YYYYMMDD "command"
        - YYYYMMDD HHMMSS "command"
        - YYYYMMDDTHHMMSS "command"
        Fallbacks: pull date from filename (8 digits) and leave time None.
        """
        # The first line is parsed with a few regular expressions. If that
        # fails, we attempt to extract an 8-digit date from the filename.
        if not file_path or not os.path.isfile(file_path):
            return None
        first = None
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                with open(file_path, encoding=enc, errors="strict") as f:
                    first = f.readline()
                break
            except UnicodeDecodeError:
                continue
            except Exception:
                first = None
                break
        if first is None:
            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    first = f.readline()
            except Exception:
                first = ""
        date = None
        time = None
        cmd = None
        # Patterns
        patterns = [
            r"^\s*(\d{8})[ T](\d{6})\s+\"([^\"]+)\"",
            r"^\s*(\d{8})T(\d{6})\s+\"([^\"]+)\"",
            r"^\s*(\d{8})\s+\"([^\"]+)\"",
        ]
        for pat in patterns:
            m = re.match(pat, first or "")
            if m:
                if len(m.groups()) == 3:
                    date, time, cmd = m.group(1), m.group(2), m.group(3)
                elif len(m.groups()) == 2:
                    date, cmd = m.group(1), m.group(2)
                break
        if not date:
            # Try from filename
            bn = os.path.basename(file_path)
            m = re.search(r"(\d{8})", bn)
            if m:
                date = m.group(1)
        return {"date": date, "time": time, "cmd": cmd}

    def _minutes_between_paths(self, a: str, b: str) -> int | None:
        """Compute absolute minutes difference between two files' timestamps."""
        return minutes_between(a, b)

    def _build_rows(self, old: list[str], new: list[str]) -> list[tuple[int | None, str, int | None, str, str]]:
        """Return list of rows: (old_ln, old_text, new_ln, new_text, tag)
        tag in {'equal','replace','delete','insert'}
        Line numbers start at 1 for the first visible content line (header is skipped).
        """
        rows: list[tuple[int | None, str, int | None, str, str]] = []
        sm = SequenceMatcher(None, old, new)
        old_idx = 1  # first displayed line number
        new_idx = 1
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                for k in range(i2 - i1):
                    rows.append((old_idx, old[i1 + k], new_idx, new[j1 + k], 'equal'))
                    old_idx += 1
                    new_idx += 1
            elif tag == 'replace':
                length = max(i2 - i1, j2 - j1)
                for k in range(length):
                    o_text = old[i1 + k] if i1 + k < i2 else ""
                    n_text = new[j1 + k] if j1 + k < j2 else ""
                    o_ln = old_idx if i1 + k < i2 else None
                    n_ln = new_idx if j1 + k < j2 else None
                    if i1 + k < i2:
                        old_idx += 1
                    if j1 + k < j2:
                        new_idx += 1
                    rows.append((o_ln, o_text, n_ln, n_text, 'replace'))
            elif tag == 'delete':
                for k in range(i2 - i1):
                    rows.append((old_idx, old[i1 + k], None, "", 'delete'))
                    old_idx += 1
            elif tag == 'insert':
                for k in range(j2 - j1):
                    rows.append((None, "", new_idx, new[j1 + k], 'insert'))
                    new_idx += 1
        return rows

    def _populate(self, rows: list[tuple[int | None, str, int | None, str, str]]):
        """Render the diff rows into the left/right panels.

        Applies line numbers, word-level coloring, and optional keyword
        underlining. Updates titles from parsed metadata and shows the files'
        modified timestamps. Also clamps each rendered line to
        ``MAX_PREVIEW_CHARS`` for performance/readability.
        """
        left = self._left_panel
        right = self._right_panel
        if not left or not right:
            return

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

        left_lines: list[str] = []
        right_lines: list[str] = []

        for o_ln, o_text, n_ln, n_text, tag in rows:
            if tag == 'equal':
                lmk, rmk = word_diff(o_text, n_text)
                left_lines.append(f"{ln(o_ln)}{lmk}")
                right_lines.append(f"{ln(n_ln)}{rmk}")
            elif tag == 'replace':
                lmk, rmk = word_diff(o_text, n_text)
                left_lines.append(f"{ln(o_ln)}{lmk}")
                right_lines.append(f"{ln(n_ln)}{rmk}")
            elif tag == 'delete':
                lmk, _ = word_diff(o_text, "")
                left_lines.append(f"{ln(o_ln)}{lmk}")
                right_lines.append(f"{ln(n_ln)}")
            elif tag == 'insert':
                _, rmk = word_diff("", n_text)
                left_lines.append(f"{ln(o_ln)}")
                right_lines.append(f"{ln(n_ln)}{rmk}")
            else:
                # Fallback: treat as equal
                lmk, rmk = word_diff(o_text, n_text)
                left_lines.append(f"{ln(o_ln)}{lmk}")
                right_lines.append(f"{ln(n_ln)}{rmk}")

        # Update titles with command and subtitle with file modified datetime
        try:
            lp_title = left.query_one('.file-title', Static)
            rp_title = right.query_one('.file-title', Static)
            lp_sub = left.query_one('.file-subtitle', Static)
            rp_sub = right.query_one('.file-subtitle', Static)

            old_cmd = self._old_meta.get("cmd") if isinstance(self._old_meta, dict) else None
            new_cmd = self._new_meta.get("cmd") if isinstance(self._new_meta, dict) else None

            left_title_text = (
                f"[yellow]OLD[/yellow] — " f"{escape(old_cmd) if old_cmd else os.path.basename(self.old_path)}"
            )
            right_title_text = (
                f"[green]NEW[/green] — " f"{escape(new_cmd) if new_cmd else os.path.basename(self.new_path)}"
            )

            lp_title.update(Text.from_markup(left_title_text))
            rp_title.update(Text.from_markup(right_title_text))
            lp_sub.update(f"Modified: {self._old_created}" if self._old_created else "")
            rp_sub.update(f"Modified: {self._new_created}" if self._new_created else "")
        except Exception:
            pass

        # Apply line-length cap for performance and readability
        def clamp_line(s: str) -> str:
            try:
                if MAX_PREVIEW_CHARS and len(s) > MAX_PREVIEW_CHARS:
                    return s[:MAX_PREVIEW_CHARS] + " …"
            except Exception:
                pass
            return s

        left_lines = [clamp_line(s) for s in left_lines]
        right_lines = [clamp_line(s) for s in right_lines]

        # Update contents
        try:
            lp_cont = left.query_one('.file-content', Vertical)
            rp_cont = right.query_one('.file-content', Vertical)
            lp_text = lp_cont.query_one('.file-text', Static)
            rp_text = rp_cont.query_one('.file-text', Static)
            lp_text.update("\n".join(left_lines))
            rp_text.update("\n".join(right_lines))
        except Exception:
            pass
