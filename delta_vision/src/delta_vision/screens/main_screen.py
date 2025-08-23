"""Home screen for DeltaVision.

This module defines the landing screen users see when the app starts. It
introduces the four primary workflows (Stream, Search, Keywords, Compare).

Key responsibilities:
- Render hero banner and action cards that route to feature screens.
- Provide convenient keyboard shortcuts via Footer.
"""

from textual.app import ComposeResult
from textual.containers import Center, Horizontal, Vertical
from textual.widgets import Button, Static

from delta_vision.utils.base_screen import BaseScreen
from delta_vision.utils.screen_navigation import create_navigator


class MainScreen(BaseScreen):
    """DeltaVision home.

    Presents entry points to core features and a theme picker. This screen
    intentionally keeps logic light: it composes widgets, wires up actions,
    and defers heavy work to the dedicated feature screens.
    """

    CSS_PATH = "main_screen.tcss"
    BINDINGS = [
        ("1", "open_stream", "Stream"),
        ("2", "open_search", "Search"),
        ("3", "open_keywords", "Keywords"),
        ("4", "open_compare", "Compare"),
    ]


    def __init__(self, new_folder_path=None, old_folder_path=None, keywords_path=None):
        super().__init__(page_name="Home")
        self.new_folder_path = new_folder_path
        self.old_folder_path = old_folder_path
        self.keywords_path = keywords_path
        self._navigator = None

    def compose_main_content(self) -> ComposeResult:
        """Build the main content layout for the Home screen.

        Returns a composition of:
        - Hero banner (title + tagline)
        - Action cards for Stream/Search/Keywords/Compare
        """
        # Main content root
        with Vertical(id="main-root"):
            # Hero section
            yield Vertical(
                Static("[b]DeltaVision[/b]", markup=True, id="title"),
                Static(
                    "[dim]Diff. Stream. Search. Keywords\nEverything you need to compare at a glance.[/dim]",
                    markup=True,
                    id="tagline",
                ),
                id="hero",
            )

            # Actions grid (cards) — 2 rows x 2 columns
            with Vertical(id="actions-grid"):
                with Horizontal(classes="actions-row"):
                    yield Vertical(
                        Center(Button(label="🚀  Stream", id="stream_button", variant="primary")),
                        Static("Live tail of NEW files with keyword highlighting.", classes="desc"),
                        classes="action-card",
                    )
                    yield Vertical(
                        Center(Button(label="🔎  Search", id="search_button", variant="success")),
                        Static("Search across NEW and OLD with instant previews.", classes="desc"),
                        classes="action-card",
                    )
                with Horizontal(classes="actions-row"):
                    yield Vertical(
                        Center(Button(label="📚  Keywords", id="keywords_button", variant="warning")),
                        Static("Explore keywords, categories, and occurrences.", classes="desc"),
                        classes="action-card",
                    )
                    yield Vertical(
                        Center(Button(label="🧭  Compare", id="compare_button", variant="default")),
                        Static("See what changed between NEW and OLD commands.", classes="desc"),
                        classes="action-card",
                    )

                # Future features placeholder row
                with Horizontal(classes="actions-row"):
                    yield Vertical(
                        Center(Static("[dim]More features coming soon...[/dim]", markup=True)),
                        Static("", classes="desc"),
                        classes="action-card placeholder",
                    )
                    # Empty card for symmetry
                    yield Vertical(
                        Center(Static("[dim]Use Ctrl+P for themes and more[/dim]", markup=True)),
                        Static("", classes="desc"),
                        classes="action-card placeholder",
                    )

    async def on_mount(self):
        """Set screen title after mount and initialize navigator."""
        await super().on_mount()
        self._navigator = create_navigator(self.app)


    def get_footer_text(self) -> str:
        return (
            " [orange1]1[/orange1] Stream    "
            "[orange1]2[/orange1] Search    "
            "[orange1]3[/orange1] Keywords    "
            "[orange1]4[/orange1] Compare    "
            "[orange1]Ctrl+P[/orange1] Commands"
        )

    # Hotkey actions
    def action_open_stream(self):
        """Open the live Stream screen (tail NEW files with highlights)."""
        if self._navigator:
            self._navigator.open_stream_screen(
                folder_path=self.new_folder_path,
                keywords_path=self.keywords_path,
            )

    def action_open_search(self):
        """Open the Search screen (query across NEW and OLD)."""
        if self._navigator:
            self._navigator.open_search_screen(
                new_folder_path=self.new_folder_path,
                old_folder_path=self.old_folder_path,
                keywords_path=self.keywords_path,
            )

    def action_open_keywords(self):
        """Open the Keywords screen (manage categories and terms)."""
        if self._navigator:
            self._navigator.open_keywords_screen(
                new_folder_path=self.new_folder_path,
                old_folder_path=self.old_folder_path,
                keywords_path=self.keywords_path,
            )

    def action_open_compare(self):
        """Navigate to the folder comparison screen.

        Opens the CompareScreen with the configured NEW and OLD folder paths
        for side-by-side file comparison and analysis.
        """
        if self._navigator:
            self._navigator.open_compare_screen(
                new_folder_path=self.new_folder_path,
                old_folder_path=self.old_folder_path,
                keywords_path=self.keywords_path,
            )


    def on_button_pressed(self, event):
        """Route button presses to corresponding action methods to eliminate duplication."""
        button_to_action = {
            "stream_button": self.action_open_stream,
            "search_button": self.action_open_search,
            "keywords_button": self.action_open_keywords,
            "compare_button": self.action_open_compare,
        }

        action = button_to_action.get(event.button.id)
        if action:
            action()

