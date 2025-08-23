"""Base screen classes to eliminate structural duplication across screens.

This module provides base classes that standardize the common composition pattern
used across all Delta Vision screens: Header + main content + Footer.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable

from delta_vision.utils.logger import log
from delta_vision.widgets.footer import Footer
from delta_vision.widgets.header import Header


class BaseScreen(Screen):
    """Base class for all Delta Vision screens.

    Provides standardized header/content/footer composition pattern that all
    screens follow. Subclasses need only implement compose_main_content() to
    define their specific content layout.

    The standard structure is:
    - Header with page name and clock
    - Main content area (defined by subclass)
    - Footer with contextual text
    """

    def __init__(self, page_name: str):
        """Initialize base screen with page name.

        Args:
            page_name: Name to display in header and title
        """
        super().__init__()
        self.page_name = page_name
        self.title = f"Delta Vision — {page_name}"

    def compose(self) -> ComposeResult:
        """Standard composition: header + main content + footer.

        Subclasses should override compose_main_content() to define their
        specific layout rather than overriding this method.
        """
        # Standard header
        yield Header(page_name=self.page_name, show_clock=True)

        # Main content area (implemented by subclass)
        yield from self.compose_main_content()

        # Standard footer
        yield Footer(text=self.get_footer_text())

    def compose_main_content(self) -> ComposeResult:
        """Define the main content area for this screen.

        Must be implemented by subclasses to define their specific layout.
        Usually yields a Vertical container with screen-specific content.
        """
        raise NotImplementedError("Subclasses must implement compose_main_content()")

    def get_footer_text(self) -> str:
        """Get footer text for this screen.

        Must be implemented by subclasses to provide contextual footer text.
        """
        raise NotImplementedError("Subclasses must implement get_footer_text()")

    def safe_set_focus(self, widget) -> None:
        """Set focus on widget with error handling.

        Provides consistent focus management across all screens.

        Args:
            widget: Widget to focus on
        """
        try:
            self.set_focus(widget)
        except (AttributeError, RuntimeError) as e:
            log(f"Failed to set focus: {e}")

    def action_go_back(self):
        """Standard back navigation action.

        Provides consistent "go back" behavior across screens.
        """
        try:
            self.app.pop_screen()
        except (AttributeError, RuntimeError) as e:
            log(f"Failed to go back: {e}")

    async def on_mount(self):
        """Standard mounting behavior - set screen title.

        Subclasses can override this but should call super().on_mount()
        to preserve the title setting behavior.
        """
        self.title = f"Delta Vision — {self.page_name}"


class BaseTableScreen(BaseScreen):
    """Base class for screens that work with DataTable components.

    Extends BaseScreen with utilities for DataTable setup and configuration.
    Provides standardized table setup patterns used across multiple screens.
    """

    def __init__(self, page_name: str):
        """Initialize base table screen.

        Args:
            page_name: Name to display in header and title
        """
        super().__init__(page_name)
        self._table = None  # Will hold reference to main DataTable

    def setup_data_table(self, table: DataTable) -> None:
        """Apply standard DataTable configuration.

        Sets up zebra stripes and row cursor type for consistent table appearance
        across all screens. Handles errors gracefully for compatibility.

        Args:
            table: DataTable widget to configure
        """
        if not table:
            return

        try:
            # Enable zebra stripes for better readability
            if hasattr(table, "zebra_stripes"):
                table.zebra_stripes = True

            # Set cursor to row mode for better navigation
            if hasattr(table, "cursor_type"):
                try:
                    table.cursor_type = "row"
                except (AttributeError, RuntimeError) as e:
                    log(f"Failed to set table cursor type: {e}")

        except (AttributeError, RuntimeError) as e:
            log(f"Failed to apply table setup: {e}")

    async def on_mount(self):
        """Standard table screen mounting.

        Calls parent mount behavior and applies table setup if main table exists.
        Subclasses can override but should call super().on_mount().
        """
        await super().on_mount()

        # Apply standard table setup to main table if it exists
        if self._table:
            self.setup_data_table(self._table)
