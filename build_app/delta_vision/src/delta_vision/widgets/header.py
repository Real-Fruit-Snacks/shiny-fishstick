from textual.widgets import Header as TextualHeader


class Header(TextualHeader):
    """A simplified header widget for the application with cohesive styling."""

    # Style the header to visually match the footer across all screens
    DEFAULT_CSS = """
    Header {
        dock: top;
        background: $panel-darken-2;
        border-bottom: heavy $primary;
        padding: 0 1;
        text-style: bold;
        content-align: center middle;
    height: 2;
    min-height: 1;
    }
    """

    def __init__(self, page_name: str = "", show_clock: bool = False):
        super().__init__(show_clock=show_clock)
        self.title = f"Delta Vision — {page_name}" if page_name else "Delta Vision"
