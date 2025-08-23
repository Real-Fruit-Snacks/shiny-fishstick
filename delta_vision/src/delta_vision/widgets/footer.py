from rich.text import Text
from textual.widgets import Static


class Footer(Static):
    """A footer widget for the application."""

    def __init__(self, text: str | None = None, classes: str = "footer") -> None:
        content = text if text is not None else " [orange1]K[/orange1] Keywords"
        super().__init__(Text.from_markup(content), classes=classes)
