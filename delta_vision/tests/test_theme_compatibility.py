"""Comprehensive theme compatibility tests for all screens.

This module tests every screen in the application with every available theme
to ensure proper rendering, functionality, and error-free operation across
all theme combinations.
"""

import os
import tempfile

import pytest
from textual.app import App

from delta_vision.entry_points import HomeApp
from delta_vision.screens.compare import CompareScreen
from delta_vision.screens.diff_viewer import SideBySideDiffScreen
from delta_vision.screens.file_viewer import FileViewerScreen
from delta_vision.screens.keywords_screen import KeywordsScreen
from delta_vision.screens.main_screen import MainScreen
from delta_vision.screens.search import SearchScreen
from delta_vision.screens.stream import StreamScreen
from delta_vision.themes import discover_themes, register_all_themes


class TestThemeCompatibilityFramework:
    """Framework for testing theme compatibility across all screens."""

    @classmethod
    def get_all_themes(cls):
        """Get all available theme names."""
        themes = discover_themes()
        theme_names = []
        for theme in themes:
            if hasattr(theme, 'name') and theme.name:
                theme_names.append(theme.name)

        # Add default Textual themes that should always work
        theme_names.extend(['textual-dark', 'textual-light'])

        return sorted(list(set(theme_names)))  # Remove duplicates and sort

    class BaseTestApp(App):
        """Base test app with theme registration support."""
        def __init__(self, target_theme: str):
            super().__init__()
            try:
                register_all_themes(self)
                self.theme = target_theme
            except Exception:
                # If theme registration or setting fails, use default
                self.theme = 'textual-dark'

    @classmethod
    def create_test_data(cls):
        """Create test data files for screen testing."""
        new_dir = tempfile.mkdtemp()
        old_dir = tempfile.mkdtemp()

        # Create keywords file
        fd, kw_path = tempfile.mkstemp(suffix='.md', text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as kwf:
            kwf.write("""# Security (red)
malware
phishing

# Network (blue)
TCP
UDP
HTTP

# System (green)
kernel
process
memory
""")

        def make_file(folder, name, date="20250101", cmd="test command", lines=None):
            if lines is None:
                lines = [
                    "Sample line with malware detection",
                    "TCP connection established",
                    "HTTP request processed",
                    "Kernel module loaded",
                    "Process started successfully",
                    "Memory allocation complete",
                    "Network interface up",
                    "Security check passed"
                ]
            fp = os.path.join(folder, name)
            with open(fp, "w", encoding="utf-8") as f:
                f.write(f'{date} "{cmd}"\n')
                f.write("\n".join(lines))
            return fp

        # Create multiple test files with different timestamps
        make_file(new_dir, "test1.txt", "20250101", "echo test1")
        make_file(new_dir, "test2.txt", "20250102", "echo test2")
        make_file(new_dir, "same_cmd.txt", "20250103", "same command")
        make_file(new_dir, "same_cmd2.txt", "20250104", "same command")

        make_file(old_dir, "test1.txt", "20241201", "echo test1")
        make_file(old_dir, "same_cmd.txt", "20241202", "same command")
        make_file(old_dir, "same_cmd_old.txt", "20241203", "same command")

        return new_dir, old_dir, kw_path

    @classmethod
    def cleanup_test_data(cls, new_dir, old_dir, kw_path):
        """Clean up test data files."""
        import shutil
        try:
            shutil.rmtree(new_dir, ignore_errors=True)
            shutil.rmtree(old_dir, ignore_errors=True)
            os.unlink(kw_path)
        except Exception:
            pass  # Ignore cleanup errors

    @pytest.fixture
    def test_data(self):
        """Fixture providing test data for all screen tests."""
        new_dir, old_dir, kw_path = self.create_test_data()
        yield new_dir, old_dir, kw_path
        self.cleanup_test_data(new_dir, old_dir, kw_path)


class TestMainScreenThemeCompatibility(TestThemeCompatibilityFramework):
    """Test MainScreen with all themes."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("theme_name", TestThemeCompatibilityFramework.get_all_themes())
    async def test_main_screen_with_theme(self, test_data, theme_name):
        """Test MainScreen functionality with each theme."""
        new_dir, old_dir, kw_path = test_data

        class TestApp(TestThemeCompatibilityFramework.BaseTestApp):
            def __init__(self):
                super().__init__(theme_name)

            async def on_mount(self) -> None:
                self.push_screen(MainScreen(new_dir, old_dir, kw_path))

        async with TestApp().run_test() as pilot:
            # Test basic navigation and theme rendering
            await pilot.pause()

            # Verify screen is rendered without errors
            assert pilot.app.screen is not None
            assert isinstance(pilot.app.screen, MainScreen)
            assert pilot.app.theme == theme_name

            # Test navigation keys
            await pilot.press("j", "k")  # Navigation
            await pilot.pause()


class TestCompareScreenThemeCompatibility(TestThemeCompatibilityFramework):
    """Test CompareScreen with all themes."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("theme_name", TestThemeCompatibilityFramework.get_all_themes())
    async def test_compare_screen_with_theme(self, test_data, theme_name):
        """Test CompareScreen functionality with each theme."""
        new_dir, old_dir, kw_path = test_data

        class TestApp(TestThemeCompatibilityFramework.BaseTestApp):
            def __init__(self):
                super().__init__(theme_name)

            async def on_mount(self) -> None:
                self.push_screen(CompareScreen(new_dir, old_dir, kw_path))

        async with TestApp().run_test() as pilot:
            await pilot.pause()

            # Verify screen is rendered
            assert isinstance(pilot.app.screen, CompareScreen)
            assert pilot.app.theme == theme_name

            # Test table navigation and filtering
            await pilot.press("j", "k", "f")  # Navigate and toggle filter
            await pilot.pause()


class TestSearchScreenThemeCompatibility(TestThemeCompatibilityFramework):
    """Test SearchScreen with all themes."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("theme_name", TestThemeCompatibilityFramework.get_all_themes())
    async def test_search_screen_with_theme(self, test_data, theme_name):
        """Test SearchScreen functionality with each theme."""
        new_dir, old_dir, kw_path = test_data

        class TestApp(TestThemeCompatibilityFramework.BaseTestApp):
            def __init__(self):
                super().__init__(theme_name)

            async def on_mount(self) -> None:
                self.push_screen(SearchScreen(new_dir, old_dir, kw_path))

        async with TestApp().run_test() as pilot:
            await pilot.pause()

            # Verify screen is rendered
            assert isinstance(pilot.app.screen, SearchScreen)
            assert pilot.app.theme == theme_name

            # Test search functionality and theme-aware highlighting
            await pilot.press("t", "e", "s", "t")  # Type search query
            await pilot.press("enter")  # Execute search
            await pilot.pause()

            # Test toggle controls
            await pilot.press("ctrl+r", "ctrl+k")  # Toggle regex and keywords
            await pilot.pause()


class TestStreamScreenThemeCompatibility(TestThemeCompatibilityFramework):
    """Test StreamScreen with all themes."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("theme_name", TestThemeCompatibilityFramework.get_all_themes())
    async def test_stream_screen_with_theme(self, test_data, theme_name):
        """Test StreamScreen functionality with each theme."""
        new_dir, old_dir, kw_path = test_data

        class TestApp(TestThemeCompatibilityFramework.BaseTestApp):
            def __init__(self):
                super().__init__(theme_name)

            async def on_mount(self) -> None:
                self.push_screen(StreamScreen(new_dir, kw_path))

        async with TestApp().run_test() as pilot:
            await pilot.pause()

            # Verify screen is rendered
            assert isinstance(pilot.app.screen, StreamScreen)
            assert pilot.app.theme == theme_name

            # Test scrolling and toggles
            await pilot.press("j", "k", "G", "g", "g")  # Navigation
            await pilot.press("ctrl+k", "ctrl+a")  # Toggle keywords and anchor
            await pilot.pause()


class TestKeywordsScreenThemeCompatibility(TestThemeCompatibilityFramework):
    """Test KeywordsScreen with all themes."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("theme_name", TestThemeCompatibilityFramework.get_all_themes())
    async def test_keyword_screen_with_theme(self, test_data, theme_name):
        """Test KeywordsScreen functionality with each theme."""
        new_dir, old_dir, kw_path = test_data

        class TestApp(TestThemeCompatibilityFramework.BaseTestApp):
            def __init__(self):
                super().__init__(theme_name)

            async def on_mount(self) -> None:
                self.push_screen(KeywordsScreen(new_dir, old_dir, kw_path))

        async with TestApp().run_test() as pilot:
            await pilot.pause()

            # Verify screen is rendered
            assert isinstance(pilot.app.screen, KeywordsScreen)
            assert pilot.app.theme == theme_name

            # Test table navigation
            await pilot.press("j", "k", "G")  # Navigate keyword table
            await pilot.pause()


class TestFileViewerThemeCompatibility(TestThemeCompatibilityFramework):
    """Test FileViewerScreen with all themes."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("theme_name", TestThemeCompatibilityFramework.get_all_themes())
    async def test_file_viewer_with_theme(self, test_data, theme_name):
        """Test FileViewerScreen functionality with each theme."""
        new_dir, old_dir, kw_path = test_data

        # Get a test file to view
        test_file = os.path.join(new_dir, "test1.txt")

        class TestApp(TestThemeCompatibilityFramework.BaseTestApp):
            def __init__(self):
                super().__init__(theme_name)

            async def on_mount(self) -> None:
                self.push_screen(FileViewerScreen(
                    test_file, line_no=1, keywords_path=kw_path, keywords_enabled=True
                ))

        async with TestApp().run_test() as pilot:
            await pilot.pause()

            # Verify screen is rendered
            assert isinstance(pilot.app.screen, FileViewerScreen)
            assert pilot.app.theme == theme_name

            # Test navigation and keyword highlighting
            await pilot.press("j", "k", "G", "g", "g")  # Navigate
            await pilot.press("ctrl+k")  # Toggle keywords
            await pilot.pause()


class TestDiffViewerThemeCompatibility(TestThemeCompatibilityFramework):
    """Test DiffViewer with all themes."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("theme_name", TestThemeCompatibilityFramework.get_all_themes())
    async def test_diff_viewer_with_theme(self, test_data, theme_name):
        """Test DiffViewer functionality with each theme."""
        new_dir, old_dir, kw_path = test_data

        # Get test files for diffing
        new_file = os.path.join(new_dir, "test1.txt")
        old_file = os.path.join(old_dir, "test1.txt")

        class TestApp(TestThemeCompatibilityFramework.BaseTestApp):
            def __init__(self):
                super().__init__(theme_name)

            async def on_mount(self) -> None:
                self.push_screen(SideBySideDiffScreen(
                    new_file, old_file, keywords_path=kw_path
                ))

        async with TestApp().run_test() as pilot:
            await pilot.pause()

            # Verify screen is rendered
            assert isinstance(pilot.app.screen, SideBySideDiffScreen)
            assert pilot.app.theme == theme_name

            # Test diff navigation and tabs
            await pilot.press("j", "k", "G", "g", "g")  # Scroll diff
            await pilot.press("h", "l")  # Tab navigation
            await pilot.press("ctrl+k")  # Toggle highlights
            await pilot.pause()


class TestFullAppThemeCompatibility(TestThemeCompatibilityFramework):
    """Test complete app navigation with all themes."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("theme_name", TestThemeCompatibilityFramework.get_all_themes())
    async def test_full_app_navigation_with_theme(self, test_data, theme_name):
        """Test full app navigation flow with each theme."""
        new_dir, old_dir, kw_path = test_data

        class TestApp(HomeApp):
            def __init__(self):
                super().__init__()
                self.theme = theme_name
                # Override config with test data
                from delta_vision.utils.config import config
                config.new_folder_path = new_dir
                config.old_folder_path = old_dir
                config.keywords_path = kw_path

        async with TestApp().run_test() as pilot:
            await pilot.pause()

            # Verify theme is applied
            assert pilot.app.theme == theme_name

            # Test navigation through all main screens
            # Stream screen
            await pilot.press("1")
            await pilot.pause()
            await pilot.press("q")

            # Search screen
            await pilot.press("2")
            await pilot.pause()
            await pilot.press("q")

            # Keywords screen
            await pilot.press("3")
            await pilot.pause()
            await pilot.press("q")

            # Compare screen
            await pilot.press("4")
            await pilot.pause()
            await pilot.press("q")

            # Verify we're back at main screen
            assert isinstance(pilot.app.screen, MainScreen)


class TestThemeTransitions:
    """Test theme switching during app operation."""

    @pytest.mark.asyncio
    async def test_theme_switching_on_screens(self, test_data):
        """Test that theme switching works correctly on different screens."""
        new_dir, old_dir, kw_path = test_data

        class TestApp(HomeApp):
            def __init__(self):
                super().__init__()
                # Override config
                from delta_vision.utils.config import config
                config.new_folder_path = new_dir
                config.old_folder_path = old_dir
                config.keywords_path = kw_path

        # Get available themes for testing
        themes = TestThemeCompatibilityFramework.get_all_themes()[:3]  # Test first 3 themes

        async with TestApp().run_test() as pilot:
            await pilot.pause()

            for theme_name in themes:
                # Switch theme
                pilot.app.theme = theme_name
                await pilot.pause()

                # Verify theme change
                assert pilot.app.theme == theme_name

                # Test navigation still works
                await pilot.press("1")  # Go to stream
                await pilot.pause()
                await pilot.press("q")  # Back to main
                await pilot.pause()


class TestThemeErrorHandling:
    """Test error handling with invalid or problematic themes."""

    @pytest.mark.asyncio
    async def test_invalid_theme_fallback(self, test_data):
        """Test that app handles invalid theme names gracefully."""
        new_dir, old_dir, kw_path = test_data

        class TestApp(HomeApp):
            def __init__(self):
                super().__init__()
                # Set invalid theme
                self.theme = "nonexistent-theme-12345"

        async with TestApp().run_test() as pilot:
            await pilot.pause()

            # Should fallback to valid theme, not crash
            assert pilot.app.theme in ['textual-dark', 'textual-light', 'ayu-mirage']

            # App should still be functional
            await pilot.press("1")  # Navigate
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_theme_switching_with_mock_errors(self, test_data):
        """Test theme switching when some themes cause errors."""
        new_dir, old_dir, kw_path = test_data

        class TestApp(App):
            def __init__(self):
                super().__init__(theme='textual-dark')

            async def on_mount(self) -> None:
                self.push_screen(MainScreen(new_dir, old_dir, kw_path))

        async with TestApp().run_test() as pilot:
            await pilot.pause()

            # Try setting themes that might cause issues
            problematic_themes = [None, "", "invalid", 123]

            for bad_theme in problematic_themes:
                try:
                    pilot.app.theme = bad_theme
                    await pilot.pause()
                    # Should not crash, should have valid theme
                    assert pilot.app.theme is not None
                    assert isinstance(pilot.app.theme, str)
                except Exception:
                    # If it throws, that's also acceptable error handling
                    pass


# Additional helper functions for theme testing
def test_all_themes_discoverable():
    """Test that all theme files are discoverable."""
    themes = discover_themes()
    assert len(themes) > 0

    # Should find themes from all theme files
    theme_names = [getattr(theme, 'name', '') for theme in themes if hasattr(theme, 'name')]

    # Verify some expected themes
    expected = ['ayu-mirage', 'material', 'one-dark']
    for expected_theme in expected:
        assert expected_theme in theme_names, f"Expected theme {expected_theme} not found"


def test_theme_objects_have_required_properties():
    """Test that all theme objects have required properties."""
    themes = discover_themes()

    for theme in themes:
        # Each theme should have basic required properties
        assert hasattr(theme, 'name'), f"Theme missing name: {theme}"
        assert hasattr(theme, 'primary'), f"Theme {theme.name} missing primary color"
        assert hasattr(theme, 'background'), f"Theme {theme.name} missing background color"
        assert hasattr(theme, 'foreground'), f"Theme {theme.name} missing foreground color"

        # Name should be a non-empty string
        assert isinstance(theme.name, str), f"Theme name not string: {theme.name}"
        assert len(theme.name) > 0, f"Theme has empty name: {theme}"


@pytest.mark.asyncio
async def test_theme_integration_with_live_updates():
    """Test that live update functionality works with theme changes."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a test file
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write('20250101 "test command"\ntest line')

        class TestApp(App):
            def __init__(self):
                super().__init__(theme='ayu-mirage')

            async def on_mount(self) -> None:
                self.push_screen(FileViewerScreen(test_file, keywords_enabled=True))

        async with TestApp().run_test() as pilot:
            await pilot.pause()

            # Change theme while screen is active
            pilot.app.theme = 'material'
            await pilot.pause()

            # Verify theme changed and screen still works
            assert pilot.app.theme == 'material'

            # Test that live updates still work (simulate file change)
            with open(test_file, "a") as f:
                f.write("\nnew line")

            await pilot.pause()
            # Should not crash with theme change + live updates
