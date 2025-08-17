"""Home screen for DeltaVision.

This module defines the landing screen users see when the app starts. It
introduces the four primary workflows (Stream, Search, Keywords, Compare)
and exposes a compact theme switcher grouped into three rows.

Key responsibilities:
- Render hero banner and action cards that route to feature screens.
- Display available Textual themes and allow quick switching.
- Provide convenient keyboard shortcuts via Footer.
"""

from textual.app import ComposeResult
from textual.containers import Center, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static, Switch

from delta_vision.screens import stream
from delta_vision.screens.compare import CompareScreen
from delta_vision.screens.search import SearchScreen
from delta_vision.widgets.footer import Footer
from delta_vision.widgets.header import Header


class MainScreen(Screen):
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

    # Map of theme name -> Switch; defined on class for type checkers
    _theme_switches: dict[str, Switch]

    def __init__(self, folder_path=None, old_folder_path=None, keywords_path=None):
        super().__init__()
        self.folder_path = folder_path
        self.old_folder_path = old_folder_path
        self.keywords_path = keywords_path

    def compose(self) -> ComposeResult:
        """Build the static layout for the Home screen.

        Returns a composition of:
        - Header with clock
        - Hero banner (title + tagline)
        - Action cards for Stream/Search/Keywords/Compare
        - Theme panel (rows populated dynamically in on_mount)
        - Footer with hotkeys
        """
        # Header
        yield Header(page_name="Home", show_clock=True)

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
                        Center(Button(label="🚀  Stream",
                               id="stream_button", variant="primary")),
                        Static(
                            "Live tail of NEW files with keyword highlighting.", classes="desc"),
                        classes="action-card",
                    )
                    yield Vertical(
                        Center(Button(label="🔎  Search",
                               id="search_button", variant="success")),
                        Static(
                            "Search across NEW and OLD with instant previews.", classes="desc"),
                        classes="action-card",
                    )
                with Horizontal(classes="actions-row"):
                    yield Vertical(
                        Center(Button(label="📚  Keywords",
                               id="keywords_button", variant="warning")),
                        Static(
                            "Explore keywords, categories, and occurrences.", classes="desc"),
                        classes="action-card",
                    )
                    yield Vertical(
                        Center(Button(label="🧭  Compare",
                               id="compare_button", variant="default")),
                        Static(
                            "See what changed between NEW and OLD commands.", classes="desc"),
                        classes="action-card",
                    )

                # Themes title (moved up for better spacing)
                yield Static("Themes", id="themes-title")

                # Themes panel shell (rows populated in on_mount)
                with Vertical(id="themes-row"):
                    yield Horizontal(id="themes-row-top", classes="themes-row-line")
                    yield Horizontal(id="themes-row-mid", classes="themes-row-line")
                    yield Horizontal(id="themes-row-bottom", classes="themes-row-line")
                    yield Horizontal(id="themes-row-fourth", classes="themes-row-line")
                    yield Horizontal(id="themes-row-fifth", classes="themes-row-line")

        # Footer with Home hotkeys
        yield Footer(text=self._footer_text())

    async def on_mount(self):
        """Populate dynamic content and sync UI state after mount.

        - Reads the app's registered themes and builds three evenly sized rows
          of Switch + label entries (excluding noisy/unwanted themes).
        - Activates the Switch matching the current app theme, if any.
        """
        self.title = "DeltaVision — Home"
        # Guard to suppress Switch.Changed while we update values programmatically
        self._suppress_switch_events = False

        # Theme switches rows (built-in themes)
        self._theme_switches = {}

        try:
            available = getattr(self.app, "available_themes", {}) or {}
        except Exception:
            available = {}

        names = list(available.keys()) if isinstance(available, dict) else []
        # Filter out themes we don't want to surface on Home.
        # textual-ansi: very high contrast, less useful for daily use.
        # zenburn: available in codebase but intentionally hidden from picker.
        names = [n for n in names if n not in ("textual-ansi", "zenburn")]

        # Alphabetize themes strictly (case-insensitive)
        ordered: list[str] = sorted(names, key=lambda s: s.lower())

        # Split into five rows evenly (difference at most one),
        # assign extras to lower rows to keep the top row compact.
        total = len(ordered)
        base = total // 5
        extra = total % 5
        sizes = [base, base, base, base, base]
        for i in range(extra):
            sizes[4 - i] += 1  # give extras to bottom rows first

        idx = 0
        first_fifth = ordered[idx: idx + sizes[0]]
        idx += sizes[0]
        second_fifth = ordered[idx: idx + sizes[1]]
        idx += sizes[1]
        third_fifth = ordered[idx: idx + sizes[2]]
        idx += sizes[2]
        fourth_fifth = ordered[idx: idx + sizes[3]]
        idx += sizes[3]
        fifth_fifth = ordered[idx: idx + sizes[4]]

        row_top = self.query_one('#themes-row-top')
        row_mid = self.query_one('#themes-row-mid')
        row_bottom = self.query_one('#themes-row-bottom')
        row_fourth = self.query_one('#themes-row-fourth')
        row_fifth = self.query_one('#themes-row-fifth')

        # Populate rows
        for theme_name in first_fifth:
            item = Horizontal(classes="theme-item")
            await row_top.mount(item)
            sw = Switch(value=False, tooltip=f"Switch to {theme_name}")
            self._theme_switches[theme_name] = sw
            await item.mount(sw)
            await item.mount(Static(theme_name, classes="theme-label"))

        for theme_name in second_fifth:
            item = Horizontal(classes="theme-item")
            await row_mid.mount(item)
            sw = Switch(value=False, tooltip=f"Switch to {theme_name}")
            self._theme_switches[theme_name] = sw
            await item.mount(sw)
            await item.mount(Static(theme_name, classes="theme-label"))

        for theme_name in third_fifth:
            item = Horizontal(classes="theme-item")
            await row_bottom.mount(item)
            sw = Switch(value=False, tooltip=f"Switch to {theme_name}")
            self._theme_switches[theme_name] = sw
            await item.mount(sw)
            await item.mount(Static(theme_name, classes="theme-label"))

        for theme_name in fourth_fifth:
            item = Horizontal(classes="theme-item")
            await row_fourth.mount(item)
            sw = Switch(value=False, tooltip=f"Switch to {theme_name}")
            self._theme_switches[theme_name] = sw
            await item.mount(sw)
            await item.mount(Static(theme_name, classes="theme-label"))

        for theme_name in fifth_fifth:
            item = Horizontal(classes="theme-item")
            await row_fifth.mount(item)
            sw = Switch(value=False, tooltip=f"Switch to {theme_name}")
            self._theme_switches[theme_name] = sw
            await item.mount(sw)
            await item.mount(Static(theme_name, classes="theme-label"))

        # Initialize active switch to current theme (if known)
        try:
            current = getattr(self.app, "theme", None)
            if current in self._theme_switches:
                self._theme_switches[current].value = True
        except Exception:
            pass

    def _footer_text(self) -> str:
        return (
            " [orange1]1[/orange1] Stream    "
            "[orange1]2[/orange1] Search    "
            "[orange1]3[/orange1] Keywords    "
            "[orange1]4[/orange1] Compare    "
            "[orange1]Ctrl+N[/orange1] Notes"
        )

    # Hotkey actions
    def action_open_stream(self):
        """Open the live Stream screen (tail NEW files with highlights)."""
        self.app.push_screen(
            stream.StreamScreen(
                folder_path=self.folder_path,
                keywords_path=self.keywords_path,
            )
        )

    def action_open_search(self):
        """Open the Search screen (query across NEW and OLD)."""
        self.app.push_screen(
            SearchScreen(
                new_folder_path=self.folder_path,
                old_folder_path=self.old_folder_path,
                keywords_path=self.keywords_path,
            )
        )

    def action_open_keywords(self):
        """Open the Keywords screen (manage categories and terms)."""
        from .keywords_screen import KeywordsScreen

        self.app.push_screen(
            KeywordsScreen(
                new_folder_path=self.folder_path,
                old_folder_path=self.old_folder_path,
                keywords_path=self.keywords_path,
            )
        )

    def action_open_compare(self):
        self.app.push_screen(
            CompareScreen(
                new_folder_path=self.folder_path,
                old_folder_path=self.old_folder_path,
                keywords_path=self.keywords_path,
            )
        )

    def on_button_pressed(self, event):
        if event.button.id == "stream_button":
            # Stream page only monitors the --new folder
            self.app.push_screen(
                stream.StreamScreen(
                    folder_path=self.folder_path,
                    keywords_path=self.keywords_path,
                )
            )
        elif event.button.id == "search_button":
            self.app.push_screen(
                SearchScreen(
                    new_folder_path=self.folder_path,
                    old_folder_path=self.old_folder_path,
                    keywords_path=self.keywords_path,
                )
            )
        elif event.button.id == "keywords_button":
            from .keywords_screen import KeywordsScreen

            self.app.push_screen(
                KeywordsScreen(
                    new_folder_path=self.folder_path,
                    old_folder_path=self.old_folder_path,
                    keywords_path=self.keywords_path,
                )
            )
        elif event.button.id == "compare_button":
            self.app.push_screen(
                CompareScreen(
                    new_folder_path=self.folder_path,
                    old_folder_path=self.old_folder_path,
                    keywords_path=self.keywords_path,
                )
            )

    # Handle theme switch toggles
    # type: ignore[override]
    def on_switch_changed(self, message: Switch.Changed) -> None:
        try:
            if getattr(self, "_suppress_switch_events", False):
                return

            # Identify which theme this switch corresponds to
            theme_name = None
            for name, sw in self._theme_switches.items():
                if sw is message.switch:
                    theme_name = name
                    break
            if not theme_name:
                return

            # If turning a switch ON, apply that theme and clear others
            if message.value:
                try:
                    self.app.theme = theme_name  # type: ignore[attr-defined]
                except Exception:
                    return
                self._suppress_switch_events = True
                try:
                    for n, sw in self._theme_switches.items():
                        sw.value = n == theme_name
                finally:
                    self._suppress_switch_events = False
                return

            # Turning a switch OFF
            default_theme = getattr(self.app, "default_theme", "ayu-mirage")
            current_theme = getattr(self.app, "theme", None)

            if theme_name == current_theme and theme_name != default_theme:
                try:
                    # type: ignore[attr-defined]
                    self.app.theme = default_theme
                except Exception:
                    return
                self._suppress_switch_events = True
                try:
                    for n, sw in self._theme_switches.items():
                        sw.value = n == default_theme
                finally:
                    self._suppress_switch_events = False
                return

            if theme_name == default_theme and current_theme == default_theme:
                self._suppress_switch_events = True
                try:
                    message.switch.value = True
                finally:
                    self._suppress_switch_events = False
                return
        except Exception:
            pass
