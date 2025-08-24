from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static


class Footer(Static):
    """A simple footer widget for displaying contextual text and keybindings."""

    def __init__(self, text: str | None = None, classes: str = "footer") -> None:
        content = text if text is not None else " [orange1]K[/orange1] Keywords"
        super().__init__(Text.from_markup(content), classes=classes)


class HotkeyFooter(Horizontal):
    """An enhanced footer widget with individual hotkey sections."""

    def __init__(self, hotkeys: list[tuple[str, str, str]] | None = None, classes: str = "footer") -> None:
        """Initialize footer with hotkeys.

        Args:
            hotkeys: List of tuples (display_text, tooltip_text, widget_id)
                    Note: tooltip_text is kept for API compatibility but not displayed
            classes: CSS classes for styling
        """
        super().__init__(classes=classes)
        self._hotkeys = hotkeys or []

    def compose(self) -> ComposeResult:
        """Compose the hotkey sections."""
        for display_text, _tooltip_text, widget_id in self._hotkeys:
            yield Static(Text.from_markup(display_text), id=widget_id, classes="hotkey-section")

    def update_hotkey(self, widget_id: str, display_text: str, tooltip_text: str | None = None) -> None:
        """Update a specific hotkey section."""
        try:
            hotkey_widget = self.query_one(f"#{widget_id}", Static)
            hotkey_widget.update(Text.from_markup(display_text))
            # Note: tooltip_text parameter kept for API compatibility but not used
            _ = tooltip_text  # Explicitly mark as intentionally unused
        except Exception:
            pass  # Widget not found or other error
