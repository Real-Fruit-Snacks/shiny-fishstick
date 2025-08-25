"""Base screen classes to eliminate structural duplication across screens.

This module provides base classes that standardize the common composition pattern
used across all Delta Vision screens: Header + main content + Footer.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Union

from rich.text import Text
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable

from delta_vision.utils.logger import log
from delta_vision.widgets.footer import Footer
from delta_vision.widgets.header import Header


@dataclass
class ColumnConfig:
    """Configuration for a single table column."""

    title: Union[str, Text]
    key: str
    width: Optional[int] = None
    justify: str = "left"  # left, center, right


@dataclass
class TableConfig:
    """Configuration for standardized DataTable setup.

    This dataclass eliminates duplicate table configuration patterns
    found across multiple screens.
    """

    zebra_stripes: bool = True
    cursor_type: str = "row"
    show_header: bool = True
    columns: List[ColumnConfig] = field(default_factory=list)
    add_separator_columns: bool = False  # Auto-add separator columns between data columns
    separator_style: str = "dim"
    separator_char: str = "│"

    def add_column(self, title: Union[str, Text], key: str, width: Optional[int] = None, justify: str = "left") -> None:
        """Add a column configuration."""
        self.columns.append(ColumnConfig(title, key, width, justify))

    def add_separator(self, key: str) -> None:
        """Add a separator column with standard styling."""
        self.columns.append(
            ColumnConfig(Text(self.separator_char, style=self.separator_style, justify="center"), key=key, width=1)
        )


class BaseNavigationMixin:
    """Mixin providing common table navigation actions.

    Screens using this mixin must have a `_table` attribute referencing
    their main DataTable widget.
    """

    def action_next_row(self):
        """Navigate to next row in the main table."""
        table = getattr(self, '_table', None)
        if not table:
            return

        try:
            coord = table.cursor_coordinate
            cur = getattr(coord, 'row', 0) if coord is not None else 0
        except (AttributeError, ValueError) as e:
            log(f"Failed to get current cursor position for next row: {e}")
            cur = 0

        try:
            # Get total row count using both methods for compatibility
            total = getattr(table, 'row_count', None)
            if total is None:
                total = len(getattr(table, 'rows', []))
        except (AttributeError, ValueError) as e:
            log(f"Failed to get table row count: {e}")
            total = 0

        if total:
            try:
                next_row = min(cur + 1, total - 1)
                # Try move_cursor first (more advanced), fallback to cursor_coordinate
                if hasattr(table, 'move_cursor'):
                    table.move_cursor(row=next_row, column=0)
                    # Handle scrolling if available
                    self._handle_scroll_to_row(table, next_row)
                else:
                    table.cursor_coordinate = table.cursor_coordinate._replace(row=next_row)
            except (AttributeError, ValueError) as e:
                log(f"Failed to move to next row: {e}")

        # Clear vim-like navigation state if it exists
        if hasattr(self, '_last_g'):
            self._last_g = False

    def action_prev_row(self):
        """Navigate to previous row in the main table."""
        table = getattr(self, '_table', None)
        if not table:
            return

        try:
            coord = table.cursor_coordinate
            cur = getattr(coord, 'row', 0) if coord is not None else 0
        except (AttributeError, ValueError) as e:
            log(f"Failed to get current cursor position for previous row: {e}")
            cur = 0

        try:
            prev_row = max(0, cur - 1)
            # Try move_cursor first (more advanced), fallback to cursor_coordinate
            if hasattr(table, 'move_cursor'):
                table.move_cursor(row=prev_row, column=0)
                # Handle scrolling if available
                self._handle_scroll_to_row(table, prev_row)
            else:
                table.cursor_coordinate = table.cursor_coordinate._replace(row=prev_row)
        except (AttributeError, ValueError) as e:
            log(f"Failed to move to previous row: {e}")

        # Clear vim-like navigation state if it exists
        if hasattr(self, '_last_g'):
            self._last_g = False

    def action_end(self):
        """Navigate to the last row in the main table."""
        table = getattr(self, '_table', None)
        if not table:
            return

        try:
            # Get total row count using both methods for compatibility
            total = getattr(table, 'row_count', None)
            if total is None:
                total = len(getattr(table, 'rows', []))
        except (AttributeError, ValueError) as e:
            log(f"Failed to get table row count for end action: {e}")
            total = 0

        if total:
            try:
                last_row = total - 1
                # Try move_cursor first (more advanced), fallback to cursor_coordinate
                if hasattr(table, 'move_cursor'):
                    table.move_cursor(row=last_row, column=0)
                    # Handle scrolling if available
                    self._handle_scroll_to_row(table, last_row)
                else:
                    table.cursor_coordinate = table.cursor_coordinate._replace(row=last_row)
            except (AttributeError, ValueError) as e:
                log(f"Failed to move to end row: {e}")

        # Clear vim-like navigation state if it exists
        if hasattr(self, '_last_g'):
            self._last_g = False

    def action_home(self):
        """Navigate to the first row in the main table."""
        table = getattr(self, '_table', None)
        if not table:
            return

        try:
            # Try move_cursor first (more advanced), fallback to cursor_coordinate
            if hasattr(table, 'move_cursor'):
                table.move_cursor(row=0, column=0)
                # Handle scrolling if available
                self._handle_scroll_to_row(table, 0)
            else:
                table.cursor_coordinate = table.cursor_coordinate._replace(row=0)
        except (AttributeError, ValueError) as e:
            log(f"Failed to move to home row: {e}")

        # Clear vim-like navigation state if it exists
        if hasattr(self, '_last_g'):
            self._last_g = False

    def _handle_scroll_to_row(self, table, row: int):
        """Handle scrolling to a specific row with fallback options."""
        try:
            # Try scroll_to_row first (most specific)
            scroll_to_row = getattr(table, 'scroll_to_row', None)
            if callable(scroll_to_row):
                scroll_to_row(row)
                return

            # Fallback to scroll_to_cursor (more general)
            scroll_to_cursor = getattr(table, 'scroll_to_cursor', None)
            if callable(scroll_to_cursor):
                scroll_to_cursor()
        except (AttributeError, RuntimeError) as e:
            log(f"Failed to scroll to row {row}: {e}")


class BaseToggleMixin:
    """Mixin providing common toggle functionality patterns.

    Screens using this mixin should implement _update_footer() method
    to refresh UI indicators after toggle state changes.
    """

    def _handle_toggle(self, attribute_name: str, refresh_callback=None):
        """Generic toggle handler for boolean screen attributes.

        Args:
            attribute_name: Name of the boolean attribute to toggle
            refresh_callback: Optional callback to call after toggling
        """
        try:
            current_value = getattr(self, attribute_name, False)
            setattr(self, attribute_name, not current_value)

            # Update footer if method exists
            if hasattr(self, '_update_footer'):
                self._update_footer()

            # Call refresh callback if provided
            if refresh_callback and callable(refresh_callback):
                refresh_callback()

        except (AttributeError, RuntimeError) as e:
            log(f"Failed to toggle {attribute_name}: {e}")


class BaseKeyHandlerMixin:
    """Mixin providing common key event handling patterns.

    This consolidates duplicate key event handling logic found across
    multiple screens including escape for back, enter for selection,
    and vim-like navigation keys.
    """

    # Default key bindings that can be overridden by subclasses
    KEY_BINDINGS = {
        'escape': 'action_go_back',
        'q': 'action_go_back',
        'enter': 'action_select_item',
        'j': 'action_next_row',
        'k': 'action_prev_row',
        'g': 'action_home',
        'G': 'action_end',
    }

    def handle_common_keys(self, event) -> bool:
        """Handle common key events with standard bindings.

        This method checks if the pressed key matches any standard binding
        and calls the corresponding action method if it exists.

        Args:
            event: Key event from Textual

        Returns:
            True if the key was handled, False otherwise
        """
        key = getattr(event, 'key', None)
        if key is None:
            return False

        # Check if this key has a binding
        action_name = self.KEY_BINDINGS.get(key)
        if action_name:
            # Check if the action method exists
            action_method = getattr(self, action_name, None)
            if action_method and callable(action_method):
                try:
                    action_method()
                    # Stop propagation of handled keys
                    if hasattr(event, 'stop'):
                        event.stop()
                    return True
                except (AttributeError, RuntimeError) as e:
                    log(f"Failed to execute action {action_name}: {e}")

        return False

    def action_select_item(self):
        """Default implementation for item selection.

        Subclasses should override this to provide specific selection behavior.
        """
        pass  # Default does nothing, subclasses override as needed


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


class BaseTableScreen(BaseScreen, BaseNavigationMixin):
    """Base class for screens that work with DataTable components.

    Extends BaseScreen with utilities for DataTable setup and configuration.
    Provides standardized table setup patterns used across multiple screens.
    Includes common navigation actions via BaseNavigationMixin.
    """

    def __init__(self, page_name: str):
        """Initialize base table screen.

        Args:
            page_name: Name to display in header and title
        """
        super().__init__(page_name)
        self._table = None  # Will hold reference to main DataTable

    def setup_data_table(self, table: DataTable, config: Optional[TableConfig] = None) -> None:
        """Apply standard or custom DataTable configuration.

        Sets up table properties and columns based on configuration to ensure
        consistent appearance across all screens. Handles errors gracefully.

        Args:
            table: DataTable widget to configure
            config: Optional TableConfig with custom settings. If None, uses defaults.
        """
        if not table:
            return

        # Use provided config or create default
        if config is None:
            config = TableConfig()

        try:
            # Apply basic table properties
            if hasattr(table, "zebra_stripes"):
                table.zebra_stripes = config.zebra_stripes

            if hasattr(table, "cursor_type"):
                try:
                    table.cursor_type = config.cursor_type
                except (AttributeError, RuntimeError) as e:
                    log(f"Failed to set table cursor type: {e}")

            if hasattr(table, "show_header"):
                table.show_header = config.show_header

            # Add configured columns if provided
            if config.columns:
                self._add_table_columns(table, config)

        except (AttributeError, RuntimeError) as e:
            log(f"Failed to apply table setup: {e}")

    def _add_table_columns(self, table: DataTable, config: TableConfig) -> None:
        """Add columns to table based on configuration.

        This consolidates the duplicate column addition patterns found
        across multiple screens.

        Args:
            table: DataTable to add columns to
            config: TableConfig with column definitions
        """
        try:
            for col in config.columns:
                # Handle both Text and string titles
                if isinstance(col.title, Text):
                    table.add_column(col.title, key=col.key, width=col.width)
                else:
                    # Create Text with justification if needed
                    if col.justify != "left":
                        title = Text(str(col.title), justify=col.justify)
                        table.add_column(title, key=col.key, width=col.width)
                    else:
                        table.add_column(str(col.title), key=col.key, width=col.width)
        except (AttributeError, RuntimeError) as e:
            log(f"Failed to add columns to table: {e}")

    def create_table_config(self) -> Optional[TableConfig]:
        """Create table configuration for this screen.

        Subclasses can override this to provide custom table configuration.
        This eliminates the need to duplicate column setup in each screen.

        Returns:
            TableConfig instance or None to use defaults
        """
        return None

    async def on_mount(self):
        """Standard table screen mounting.

        Calls parent mount behavior and applies table setup if main table exists.
        Subclasses can override but should call super().on_mount().
        """
        await super().on_mount()

        # Apply standard table setup to main table if it exists
        if self._table:
            # Get custom config from subclass if provided
            config = self.create_table_config()
            self.setup_data_table(self._table, config)
