from rich.text import Text
from textual.widgets import Static


class Footer(Static):
    """A footer widget for the application."""

    def __init__(self, text: str | None = None, classes: str = "footer") -> None:
        # Always include a standard Notes hint for discoverability
        notes_hint = "    [orange1]Ctrl+N[/orange1] Notes"
        base = text if text is not None else " [orange1]K[/orange1] Keywords"
        # Append the notes hint if it isn't present already
        content = base if "Ctrl+N" in base else (base + notes_hint)
        super().__init__(Text.from_markup(content), classes=classes)
