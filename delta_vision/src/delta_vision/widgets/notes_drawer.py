from __future__ import annotations

import asyncio
import json
import os
import secrets
import string

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, TextArea


class NotesDrawer(Vertical):
    """Bottom pop-up notes drawer with save-on-close and dynamic header path display."""

    BINDINGS = [
        ("escape", "close_notes", "Close Notes"),
        ("ctrl+n", "toggle_notes", "Toggle Notes"),
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
    # Collaboration state
        self._notes_ws_url = os.environ.get("DELTA_NOTES_WS") or None
        self._ws_task = None
        self._ws = None
        self._client_id = self._make_client_id()
        self._send_debounce_handle = None
        self._last_remote_update_source = None

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
        # Start collaboration channel if available
        try:
            if self._notes_ws_url and self._ws_task is None:
                self._ws_task = asyncio.create_task(self._notes_ws_loop(self._notes_ws_url))
        except Exception:
            self._ws_task = None

    def on_unmount(self) -> None:
        # Persist on unmount so switching screens doesn't lose in-memory edits
        try:
            self._persist_notes()
        except Exception:
            pass
        # Stop collaboration loop
        try:
            if self._ws_task and not self._ws_task.done():
                self._ws_task.cancel()
        except Exception:
            pass

    # Actions
    def action_close_notes(self) -> None:
        self.close()

    def action_toggle_notes(self) -> None:
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

    # --- Collaboration wiring ---
    def _make_client_id(self) -> str:
        try:
            alphabet = string.ascii_lowercase + string.digits
            return "cli-" + "".join(secrets.choice(alphabet) for _ in range(8))
        except Exception:
            return "cli-xxxxxxx"

    async def _notes_ws_loop(self, url: str) -> None:
        """Background task: connect to server /notes and keep state in sync.

        - On connect, server will send a full sync we apply to the editor.
        - On editor changes, we debounce and push updates.
        - On incoming sync from others, we apply and show a toast.
        - Reconnect with a short backoff if the connection drops.
        """
        try:
            import websockets  # type: ignore
        except Exception:
            return
        backoff = 0.5
        while True:
            try:
                async with websockets.connect(url, ping_interval=20, max_size=None) as ws:  # type: ignore
                    self._ws = ws
                    # Receive loop
                    async for msg in ws:
                        try:
                            if not isinstance(msg, str):
                                continue
                            data = json.loads(msg)
                        except Exception:
                            continue
                        if not isinstance(data, dict):
                            continue
                        if data.get("type") == "sync":
                            text = data.get("text")
                            source = data.get("source")
                            if isinstance(text, str):
                                self._apply_remote_text(text, source)
                    self._ws = None
            except asyncio.CancelledError:
                break
            except Exception:
                self._ws = None
                # Reconnect after backoff
                try:
                    await asyncio.sleep(backoff)
                except Exception:
                    break
                # Cap backoff modestly
                backoff = min(backoff * 2, 4.0)

    def _apply_remote_text(self, text: str, source: str | None) -> None:
        # Update editor content if changed; show a toast if it came from others
        try:
            current = self._area.text if self._area else ""
            if text != current:
                if self._area is not None:
                    self._area.text = text
                self._loaded_text = text
                try:
                    if self.app and source and source != self._client_id:
                        self.app.notify("📝 Notes updated by another user", timeout=3)
                except Exception:
                    pass
        except Exception:
            pass

    def _schedule_send_update(self) -> None:
        # Debounce sending frequent edits
        try:
            loop = asyncio.get_running_loop()
            if self._send_debounce_handle and not self._send_debounce_handle.cancelled():
                self._send_debounce_handle.cancel()
            self._send_debounce_handle = loop.call_later(0.3, lambda: asyncio.create_task(self._send_update_now()))
        except Exception:
            pass

    async def _send_update_now(self) -> None:
        try:
            if not self._ws:
                return
            text = self._area.text if self._area else ""
            payload = {"type": "update", "text": text, "client_id": self._client_id}
            await self._ws.send(json.dumps(payload))
        except Exception:
            pass

    # Text change hook from TextArea
    def on_text_area_changed(self, event: TextArea.Changed) -> None:  # type: ignore[override]
        # When user types, schedule an update to server
        try:
            # Update local-loaded snapshot so _persist_notes only writes when needed
            self._loaded_text = None
        except Exception:
            pass
        self._schedule_send_update()

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
