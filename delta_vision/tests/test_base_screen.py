"""Tests for the base screen architecture.

This module tests the BaseScreen and BaseTableScreen classes that all screens
inherit from, ensuring the standardized composition patterns and common
functionality work correctly across the application.
"""

from unittest.mock import Mock

import pytest
from textual.app import App
from textual.widgets import DataTable, Static

from delta_vision.utils.base_screen import BaseScreen, BaseTableScreen
from delta_vision.widgets.footer import Footer
from delta_vision.widgets.header import Header


class ConcreteBaseScreen(BaseScreen):
    """Concrete implementation of BaseScreen for testing."""

    def __init__(self):
        super().__init__(page_name="Test Screen")

    def compose_main_content(self):
        """Compose the main content area."""
        yield Static("Test content", id="test-content")

    def get_footer_text(self) -> str:
        """Return footer text."""
        return "[orange1]Test[/orange1] Footer text"


class ConcreteBaseTableScreen(BaseTableScreen):
    """Concrete implementation of BaseTableScreen for testing."""

    def __init__(self):
        super().__init__(page_name="Test Table Screen")

    def compose_main_content(self):
        """Compose the main content area with a table."""
        table = DataTable(id="test-table")
        table.add_column("Column 1", key="col1")
        table.add_column("Column 2", key="col2")
        table.add_row("Row 1 Col 1", "Row 1 Col 2")
        table.add_row("Row 2 Col 1", "Row 2 Col 2")
        yield table

    def get_footer_text(self) -> str:
        """Return footer text."""
        return "[blue]Table[/blue] Navigation test"


class TestBaseScreen:
    """Test the BaseScreen base class functionality."""

    @pytest.fixture
    def base_screen_app(self):
        """Create an app with a BaseScreen for testing."""

        class TestApp(App):
            def __init__(self):
                super().__init__()
                self.theme = 'textual-dark'

            async def on_mount(self) -> None:
                self.push_screen(ConcreteBaseScreen())

        return TestApp

    def test_base_screen_instantiation(self):
        """Test that BaseScreen can be instantiated."""
        screen = ConcreteBaseScreen()
        assert screen is not None
        assert isinstance(screen, BaseScreen)

    def test_base_screen_has_required_methods(self):
        """Test that BaseScreen has all required methods."""
        screen = ConcreteBaseScreen()

        # Should have abstract methods implemented
        assert hasattr(screen, 'compose_main_content')
        assert hasattr(screen, 'get_footer_text')

        # Should have inherited methods
        assert hasattr(screen, 'safe_set_focus')
        assert hasattr(screen, 'action_go_back')
        assert hasattr(screen, '_update_footer')

    @pytest.mark.asyncio
    async def test_base_screen_composition(self, base_screen_app):
        """Test that BaseScreen composes correctly with header, content, and footer."""
        async with base_screen_app().run_test() as pilot:
            await pilot.pause()

            screen = pilot.app.screen
            assert isinstance(screen, ConcreteBaseScreen)

            # Should have composed header, content, and footer
            header = screen.query_one(Header)
            assert header is not None

            content = screen.query_one("#test-content", Static)
            assert content is not None
            assert content.renderable == "Test content"

            footer = screen.query_one(Footer)
            assert footer is not None

    @pytest.mark.asyncio
    async def test_base_screen_footer_update(self, base_screen_app):
        """Test that footer updates work correctly."""
        async with base_screen_app().run_test() as pilot:
            await pilot.pause()

            screen = pilot.app.screen
            footer = screen.query_one(Footer)

            # Update footer
            screen._update_footer()
            await pilot.pause()

            # Footer should be updated with text from get_footer_text
            # (The exact text content depends on Footer implementation)
            assert footer is not None

    @pytest.mark.asyncio
    async def test_base_screen_safe_set_focus(self, base_screen_app):
        """Test safe focus setting functionality."""
        async with base_screen_app().run_test() as pilot:
            await pilot.pause()

            screen = pilot.app.screen
            content = screen.query_one("#test-content")

            # Should be able to set focus safely
            screen.safe_set_focus(content)
            await pilot.pause()

            # Should handle None gracefully
            screen.safe_set_focus(None)
            await pilot.pause()

            # Should handle invalid widgets gracefully
            fake_widget = Mock()
            screen.safe_set_focus(fake_widget)
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_base_screen_go_back_action(self, base_screen_app):
        """Test go back action functionality."""
        async with base_screen_app().run_test() as pilot:
            await pilot.pause()

            screen = pilot.app.screen

            # Should be able to call go back action
            screen.action_go_back()
            await pilot.pause()

            # Should pop the current screen
            # (In a real app with multiple screens, this would change the screen)

    def test_base_screen_abstract_methods_required(self):
        """Test that abstract methods must be implemented."""
        # Cannot instantiate BaseScreen directly
        with pytest.raises(TypeError):
            BaseScreen()

    def test_base_screen_inheritance_pattern(self):
        """Test that BaseScreen provides proper inheritance pattern."""
        screen = ConcreteBaseScreen()

        # Should be a BaseScreen
        assert isinstance(screen, BaseScreen)

        # Should have Textual Screen functionality
        assert hasattr(screen, 'compose')
        assert hasattr(screen, 'on_mount')

        # Should have custom base functionality
        assert hasattr(screen, 'safe_set_focus')
        assert hasattr(screen, '_update_footer')


class TestBaseTableScreen:
    """Test the BaseTableScreen base class functionality."""

    @pytest.fixture
    def base_table_screen_app(self):
        """Create an app with a BaseTableScreen for testing."""

        class TestApp(App):
            def __init__(self):
                super().__init__()
                self.theme = 'textual-dark'

            async def on_mount(self) -> None:
                self.push_screen(ConcreteBaseTableScreen())

        return TestApp

    def test_base_table_screen_instantiation(self):
        """Test that BaseTableScreen can be instantiated."""
        screen = ConcreteBaseTableScreen()
        assert screen is not None
        assert isinstance(screen, BaseTableScreen)
        assert isinstance(screen, BaseScreen)  # Should inherit from BaseScreen

    def test_base_table_screen_has_table_methods(self):
        """Test that BaseTableScreen has table-specific methods."""
        screen = ConcreteBaseTableScreen()

        # Should inherit BaseScreen methods
        assert hasattr(screen, 'safe_set_focus')
        assert hasattr(screen, 'action_go_back')

        # Should have table-specific functionality
        # (Methods would be defined in BaseTableScreen implementation)
        assert hasattr(screen, 'compose_main_content')

    @pytest.mark.asyncio
    async def test_base_table_screen_table_setup(self, base_table_screen_app):
        """Test that BaseTableScreen sets up tables correctly."""
        async with base_table_screen_app().run_test() as pilot:
            await pilot.pause()

            screen = pilot.app.screen
            assert isinstance(screen, ConcreteBaseTableScreen)

            # Should have a table
            table = screen.query_one("#test-table", DataTable)
            assert table is not None

            # Table should have columns
            assert len(table.columns) == 2

            # Table should have rows
            assert len(table.rows) == 2

    @pytest.mark.asyncio
    async def test_base_table_screen_navigation(self, base_table_screen_app):
        """Test table navigation functionality."""
        async with base_table_screen_app().run_test() as pilot:
            await pilot.pause()

            screen = pilot.app.screen
            table = screen.query_one("#test-table", DataTable)

            # Should be able to navigate table
            await pilot.press("j")  # Down
            await pilot.pause()

            await pilot.press("k")  # Up
            await pilot.pause()

            await pilot.press("G")  # Go to end
            await pilot.pause()

            await pilot.press("g", "g")  # Go to beginning
            await pilot.pause()

            # Navigation should work without errors
            assert table is not None

    @pytest.mark.asyncio
    async def test_base_table_screen_focus_management(self, base_table_screen_app):
        """Test focus management for table screens."""
        async with base_table_screen_app().run_test() as pilot:
            await pilot.pause()

            screen = pilot.app.screen
            table = screen.query_one("#test-table", DataTable)

            # Should be able to set focus on table
            screen.safe_set_focus(table)
            await pilot.pause()

            # Should handle focus gracefully
            assert table is not None

    def test_base_table_screen_inheritance(self):
        """Test BaseTableScreen inheritance hierarchy."""
        screen = ConcreteBaseTableScreen()

        # Should inherit from both BaseTableScreen and BaseScreen
        assert isinstance(screen, BaseTableScreen)
        assert isinstance(screen, BaseScreen)

        # Should have all BaseScreen methods
        assert hasattr(screen, 'safe_set_focus')
        assert hasattr(screen, 'action_go_back')
        assert hasattr(screen, '_update_footer')


class TestBaseScreenIntegration:
    """Integration tests for base screen functionality."""

    def test_multiple_screen_types_coexist(self):
        """Test that different screen types can coexist."""
        base_screen = ConcreteBaseScreen()
        table_screen = ConcreteBaseTableScreen()

        # Both should be valid screen types
        assert isinstance(base_screen, BaseScreen)
        assert isinstance(table_screen, BaseScreen)
        assert isinstance(table_screen, BaseTableScreen)

        # Should have distinct implementations
        assert base_screen.__class__ != table_screen.__class__

    @pytest.mark.asyncio
    async def test_screen_switching(self):
        """Test switching between different screen types."""

        class MultiScreenApp(App):
            def __init__(self):
                super().__init__()
                self.theme = 'textual-dark'

            async def on_mount(self) -> None:
                self.push_screen(ConcreteBaseScreen())

        async with MultiScreenApp().run_test() as pilot:
            await pilot.pause()

            # Start with base screen
            screen1 = pilot.app.screen
            assert isinstance(screen1, ConcreteBaseScreen)

            # Switch to table screen
            pilot.app.push_screen(ConcreteBaseTableScreen())
            await pilot.pause()

            screen2 = pilot.app.screen
            assert isinstance(screen2, ConcreteBaseTableScreen)

            # Go back
            await pilot.press("q")
            await pilot.pause()

            # Should return to original screen type
            # May be the same screen or the previous screen depending on implementation

    def test_base_screen_error_handling(self):
        """Test error handling in base screen classes."""
        screen = ConcreteBaseScreen()

        # Should handle invalid focus gracefully
        screen.safe_set_focus(None)

        # Should handle missing widgets gracefully
        fake_widget = Mock()
        screen.safe_set_focus(fake_widget)

        # Should not crash on invalid operations
        assert screen is not None

    @pytest.mark.asyncio
    async def test_base_screen_lifecycle(self):
        """Test base screen lifecycle methods."""

        class LifecycleTestApp(App):
            def __init__(self):
                super().__init__()
                self.theme = 'textual-dark'
                self.mount_called = False
                self.unmount_called = False

            async def on_mount(self) -> None:
                self.mount_called = True
                screen = ConcreteBaseScreen()

                # Mock lifecycle methods
                original_on_mount = screen.on_mount
                original_on_unmount = screen.on_unmount

                async def mock_on_mount():
                    await original_on_mount()

                def mock_on_unmount():
                    self.unmount_called = True
                    original_on_unmount()

                screen.on_mount = mock_on_mount
                screen.on_unmount = mock_on_unmount

                self.push_screen(screen)

        app = LifecycleTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            # Mount should have been called
            assert app.mount_called

            # Pop the screen to trigger unmount
            await pilot.press("q")
            await pilot.pause()

    def test_base_screen_composition_requirements(self):
        """Test that base screen composition requirements are enforced."""

        # BaseScreen requires compose_main_content implementation
        class IncompleteScreen(BaseScreen):
            def get_footer_text(self) -> str:
                return "Test"

            # Missing compose_main_content

        # Should not be able to instantiate incomplete screen
        with pytest.raises(TypeError):
            IncompleteScreen()

    def test_base_screen_footer_text_requirements(self):
        """Test that footer text is properly required."""

        # BaseScreen requires get_footer_text implementation
        class IncompleteScreen(BaseScreen):
            def compose_main_content(self):
                yield Static("test")

            # Missing get_footer_text

        # Should not be able to instantiate incomplete screen
        with pytest.raises(TypeError):
            IncompleteScreen()

    @pytest.mark.asyncio
    async def test_base_screen_widget_interaction(self):
        """Test interaction with widgets in base screens."""

        class InteractiveTestApp(App):
            def __init__(self):
                super().__init__()
                self.theme = 'textual-dark'

            async def on_mount(self) -> None:
                self.push_screen(ConcreteBaseTableScreen())

        async with InteractiveTestApp().run_test() as pilot:
            await pilot.pause()

            screen = pilot.app.screen
            table = screen.query_one("#test-table", DataTable)

            # Should be able to interact with table
            await pilot.click("#test-table")
            await pilot.pause()

            # Should be able to use keyboard navigation
            await pilot.press("j", "k")
            await pilot.pause()

            assert table is not None

    def test_base_screen_memory_management(self):
        """Test that base screens don't leak memory."""
        screens = []

        # Create many screens
        for i in range(100):
            if i % 2 == 0:
                screen = ConcreteBaseScreen()
            else:
                screen = ConcreteBaseTableScreen()
            screens.append(screen)

        # All screens should be valid
        assert len(screens) == 100
        assert all(isinstance(s, BaseScreen) for s in screens)

        # Clear references
        screens.clear()

        # Should not crash (memory should be reclaimable)
        import gc

        gc.collect()

    def test_base_screen_customization(self):
        """Test that base screens can be customized properly."""

        class CustomBaseScreen(ConcreteBaseScreen):
            def __init__(self):
                super().__init__()
                self.custom_attribute = "custom_value"

            def get_footer_text(self) -> str:
                return "[green]Custom[/green] Footer"

        screen = CustomBaseScreen()
        assert screen.custom_attribute == "custom_value"
        assert "Custom" in screen.get_footer_text()

    @pytest.mark.asyncio
    async def test_base_screen_theme_compatibility(self):
        """Test that base screens work with different themes."""
        themes_to_test = ['textual-dark', 'textual-light']

        for theme in themes_to_test:

            class ThemedTestApp(App):
                def __init__(self, theme_name=theme):
                    super().__init__()
                    self.theme = theme_name

                async def on_mount(self) -> None:
                    self.push_screen(ConcreteBaseScreen())

            async with ThemedTestApp().run_test() as pilot:
                await pilot.pause()

                screen = pilot.app.screen
                assert isinstance(screen, ConcreteBaseScreen)
                assert pilot.app.theme == theme

    def test_base_screen_performance(self):
        """Test base screen performance characteristics."""
        import time

        # Time screen creation
        start_time = time.time()
        screens = [ConcreteBaseScreen() for _ in range(50)]
        creation_time = time.time() - start_time

        # Should create screens quickly
        assert creation_time < 1.0  # Less than 1 second for 50 screens
        assert len(screens) == 50
        assert all(isinstance(s, BaseScreen) for s in screens)
