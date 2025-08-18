from __future__ import annotations

import os

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, TextArea


class NotesDrawer(Vertical):
    """Bottom pop-up notes drawer with save-on-close and dynamic header path display."""

    BINDINGS = [
        ("escape", "close", "Close Notes"),
        ("ctrl+n", "toggle", "Toggle Notes"),
    ]

    DEFAULT_CSS = """
    #notes-drawer {
        dock: bottom;
        height: 0;
        width: 100%;
        layer: overlay;
        background: $panel-darken-1;
        border-top: heavy $primary;
        transition: height 200ms in_out_cubic;
        padding: 1 2;
    }
    #notes-drawer.open {
        height: 12; /* rows */
    }
    #notes-drawer .notes-title {
        height: 3;
        content-align: left middle;
        padding: 0 1;
        text-style: bold underline;
        background: $panel-darken-2;
        border-bottom: heavy $primary;
        margin-bottom: 1;
    }
    #notes-drawer .notes-area {
        height: 1fr;
        background: $surface;
        border: solid $panel-darken-2;
        padding: 1;
        scrollbar-color: $primary $panel-darken-3;
        transition: border 120ms in_out_cubic;
    }
    #notes-drawer.open .notes-area {
        border: heavy $primary;
    }
    """

    def __init__(self, *, id: str = "notes-drawer", save_path: str | None = None) -> None:
        super().__init__(id=id)
        self._area = None
        self._title = None
        self._previous_focus = None
        self._save_path = save_path
        self._loaded_text = None

    def compose(self) -> ComposeResult:
        self._title = Static("📝  Notes  (Esc to close, Ctrl+N to toggle)", classes="notes-title")
        yield self._title
        self._area = TextArea(classes="notes-area")
        yield self._area

    def on_mount(self) -> None:
        # Ensure starts closed and bottom-docked even if CSS lags
        try:
            self.remove_class("open")
            self.styles.dock = "bottom"
            self.styles.height = 0
            self.styles.width = "100%"
            # Drawer container itself should not be focusable
            self.can_focus = False
        except Exception:
            pass
        # When closed, ensure editor cannot take focus
        try:
            if self._area is not None:
                self._area.can_focus = False
        except Exception:
            pass
        # Load any existing notes synchronously now that compose has run,
        # but only if the editor is effectively empty to avoid clobbering
        # in-memory edits when remounting between screens.
        self._load_from_disk(if_empty_only=True)
        self._update_title()

    def on_unmount(self) -> None:
        # Persist on unmount so switching screens doesn't lose in-memory edits
        try:
            self._persist_notes()
        except Exception:
            pass

    # Actions
    def action_close(self) -> None:
        self.close()

    def action_toggle(self) -> None:
        self.toggle()

    # Key fallback
    def on_key(self, event) -> None:  # type: ignore[override]
        try:
            if getattr(event, "key", "") == "escape":
                event.stop()
                self.close()
        except Exception:
            pass

    # Open/Close
    def open(self) -> None:
        self.add_class("open")
        # Ensure content is present when opening (avoid blank due to timing)
        self._load_from_disk(if_empty_only=True)
        # Remember focus to restore later
        try:
            focused = getattr(self.app, "focused", None) if self.app else None
            inside = False
            node = focused
            while node is not None:
                if node is self:
                    inside = True
                    break
                node = getattr(node, "parent", None)
            if focused is not None and not inside:
                self._previous_focus = focused  # type: ignore[assignment]
        except Exception:
            pass
        try:
            self.styles.height = 12
        except Exception:
            pass
        try:
            if self._area:
                # Allow focusing only while open
                try:
                    self._area.can_focus = True
                except Exception:
                    pass
                self._area.focus()
        except Exception:
            pass

    def close(self) -> None:
        self.remove_class("open")
        try:
            self.styles.height = 0
        except Exception:
            pass
        # Save on close
        self._persist_notes()
        # Explicitly blur the text area so it doesn't keep receiving input
        try:
            if self._area:
                self._area.blur()
                try:
                    # Prevent the hidden editor from stealing focus
                    self._area.can_focus = False
                except Exception:
                    pass
        except Exception:
            pass
        # Restore previous focus
        try:
            if self._previous_focus and getattr(self._previous_focus, "can_focus", False):
                self._previous_focus.focus()
            else:
                current = getattr(self.app, "screen", None) if self.app else None
                if current is not None:
                    current.focus()
        except Exception:
            pass

    def toggle(self) -> None:
        if self.has_class("open"):
            self.close()
        else:
            self.open()

    def set_save_path(self, path: str) -> None:
        """Set the save path and refresh the header; load content if editor is empty."""
        self._save_path = path
        self._loaded_text = None
        self._update_title()
        self._load_from_disk(if_empty_only=True)

    def _persist_notes(self) -> None:
        try:
            if not self._save_path:
                return
            text = self._area.text if self._area else ""
            if self._loaded_text is None and os.path.exists(self._save_path) and (text.strip() == ""):
                return
            if self._loaded_text is not None and text == self._loaded_text:
                return
            folder = os.path.dirname(self._save_path)
            if folder and not os.path.exists(folder):
                os.makedirs(folder, exist_ok=True)
            with open(self._save_path, "w", encoding="utf-8") as f:
                f.write(text)
            self._loaded_text = text
            # Show toast notification that notes were saved
            try:
                if self.app:
                    filename = os.path.basename(self._save_path)
                    self.app.notify(f"📝 Notes saved to {filename}")
            except Exception:
                pass
        except Exception:
            pass

    def _update_title(self) -> None:
        try:
            if not self._title:
                return
            path_display = self._save_path if self._save_path else "(not set)"
            self._title.update(f"📝  Notes  (Esc to close, Ctrl+N to toggle)\nSaved to: {path_display}")
        except Exception:
            pass

    def _load_from_disk(self, *, if_empty_only: bool) -> None:
        try:
            if not self._save_path or not os.path.exists(self._save_path):
                return
            if self._area is None:
                return
            if if_empty_only:
                current_text = self._area.text or ""
                if current_text.strip() != "":
                    return
            with open(self._save_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
            self._area.text = content
            self._loaded_text = content
        except Exception:
            pass
