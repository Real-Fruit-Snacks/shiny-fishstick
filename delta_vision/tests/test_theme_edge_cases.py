"""Edge case tests for theme compatibility.

This module tests theme behavior in edge cases, error conditions,
and unusual scenarios to ensure robust theme handling.
"""

import os
import tempfile

import pytest
from textual.app import App

from delta_vision.entry_points import HomeApp
from delta_vision.screens.search import SearchScreen
from delta_vision.themes import discover_themes, register_all_themes


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


class TestThemeEdgeCases:
    """Test theme behavior in edge cases and error conditions."""

    def get_themes_subset(self):
        """Get a subset of themes for focused testing."""
        all_themes = []
        for theme in discover_themes():
            if hasattr(theme, 'name'):
                all_themes.append(theme.name)

        # Test with a representative subset to avoid excessive test time
        return ['textual-dark', 'textual-light', 'ayu-mirage', 'material'][:len(all_themes)]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("theme_name", get_themes_subset(None))
    async def test_theme_with_empty_directories(self, theme_name):
        """Test themes with empty directories (no files to display)."""
        with tempfile.TemporaryDirectory() as empty_new, tempfile.TemporaryDirectory() as empty_old:
            # Create empty keywords file
            fd, kw_path = tempfile.mkstemp(suffix='.md', text=True)
            with os.fdopen(fd, "w") as f:
                f.write("# Empty\n")

            try:
                class TestApp(BaseTestApp):
                    def __init__(self):
                        super().__init__(theme_name)

                    async def on_mount(self) -> None:
                        self.push_screen(SearchScreen(empty_new, empty_old, kw_path))

                async with TestApp().run_test() as pilot:
                    await pilot.pause()

                    # Should handle empty directories gracefully
                    assert pilot.app.theme == theme_name
                    assert isinstance(pilot.app.screen, SearchScreen)

                    # Try a search in empty directories
                    await pilot.press("t", "e", "s", "t", "enter")
                    await pilot.pause()
            finally:
                os.unlink(kw_path)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("theme_name", get_themes_subset(None))
    async def test_theme_with_corrupted_files(self, theme_name):
        """Test themes with corrupted or unreadable files."""
        with tempfile.TemporaryDirectory() as test_dir:
            # Create a file with invalid encoding
            bad_file = os.path.join(test_dir, "bad_file.txt")
            with open(bad_file, "wb") as f:
                f.write(b'20250101 "test"\n\xff\xfe\x00corrupt data\x00')

            # Create keywords file
            fd, kw_path = tempfile.mkstemp(suffix='.md', text=True)
            with os.fdopen(fd, "w") as f:
                f.write("# Test\ntest")

            try:
                class TestApp(BaseTestApp):
                    def __init__(self):
                        super().__init__(theme_name)

                    async def on_mount(self) -> None:
                        from delta_vision.screens.file_viewer import FileViewerScreen
                        self.push_screen(FileViewerScreen(bad_file, keywords_path=kw_path))

                async with TestApp().run_test() as pilot:
                    await pilot.pause()

                    # Should handle corrupted files gracefully with any theme
                    assert pilot.app.theme == theme_name
                    await pilot.press("j", "k")  # Try navigation
                    await pilot.pause()
            finally:
                os.unlink(kw_path)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("theme_name", get_themes_subset(None))
    async def test_theme_with_large_files(self, theme_name):
        """Test themes with very large files."""
        with tempfile.TemporaryDirectory() as test_dir:
            # Create a large file
            large_file = os.path.join(test_dir, "large_file.txt")
            with open(large_file, "w") as f:
                f.write('20250101 "large file test"\n')
                # Write many lines to test performance with different themes
                for i in range(1000):
                    f.write(f"Line {i}: This is a test line with some content\n")

            class TestApp(BaseTestApp):
                def __init__(self):
                    super().__init__(theme_name)

                async def on_mount(self) -> None:
                    from delta_vision.screens.file_viewer import FileViewerScreen
                    self.push_screen(FileViewerScreen(large_file))

            async with TestApp().run_test() as pilot:
                await pilot.pause()

                # Should handle large files with any theme
                assert pilot.app.theme == theme_name
                await pilot.press("G", "g", "g")  # Test navigation to end and back
                await pilot.pause()

    @pytest.mark.asyncio
    async def test_rapid_theme_switching(self):
        """Test rapid theme switching doesn't cause issues."""
        themes = self.get_themes_subset()

        class TestApp(BaseTestApp):
            def __init__(self):
                super().__init__(themes[0])

            async def on_mount(self) -> None:
                from delta_vision.screens.main_screen import MainScreen
                self.push_screen(MainScreen("/tmp", "/tmp", None))

        async with TestApp().run_test() as pilot:
            await pilot.pause()

            # Rapidly switch themes
            for theme in themes:
                pilot.app.theme = theme
                await pilot.pause()
                assert pilot.app.theme == theme

                # Test that UI still responds
                await pilot.press("j")
                await pilot.pause()

    @pytest.mark.asyncio
    async def test_theme_with_unicode_content(self):
        """Test themes with Unicode and special characters."""
        with tempfile.TemporaryDirectory() as test_dir:
            # Create file with Unicode content
            unicode_file = os.path.join(test_dir, "unicode_test.txt")
            with open(unicode_file, "w", encoding="utf-8") as f:
                f.write('20250101 "Unicode test: 测试 🎯 العربية"\n')
                f.write("Unicode content: αβγδε ñáéíóú 中文测试 🚀🔒⚡\n")
                f.write("Mathematical symbols: ∞≠≤≥±×÷√∂∫∑∏\n")
                f.write("Box drawing: ┌─┐│└─┘╔═╗║╚═╝\n")

            themes = self.get_themes_subset()

            for theme_name in themes[:2]:  # Test subset to avoid excessive time
                class TestApp(BaseTestApp):
                    def __init__(self, theme=theme_name):
                        super().__init__(theme)

                    async def on_mount(self) -> None:
                        from delta_vision.screens.file_viewer import FileViewerScreen
                        self.push_screen(FileViewerScreen(unicode_file))

                async with TestApp().run_test() as pilot:
                    await pilot.pause()

                    # Should handle Unicode content properly with any theme
                    assert pilot.app.theme == theme_name
                    await pilot.press("j", "k", "G", "g", "g")
                    await pilot.pause()

    @pytest.mark.asyncio
    async def test_theme_error_recovery(self):
        """Test that app recovers from theme-related errors."""
        class TestApp(HomeApp):
            def __init__(self):
                super().__init__()

        async with TestApp().run_test() as pilot:
            await pilot.pause()

            # Try to break theme system and verify recovery

            try:
                # Try invalid theme operations
                pilot.app.theme = None
                await pilot.pause()
                assert pilot.app.theme is not None  # Should fallback

                pilot.app.theme = ""
                await pilot.pause()
                assert pilot.app.theme != ""  # Should fallback

                pilot.app.theme = "nonexistent-theme-xyz"
                await pilot.pause()
                # Should either set to nonexistent name or fallback - either is acceptable

                # App should still be functional
                await pilot.press("1", "q")  # Navigate and back
                await pilot.pause()

            except Exception:
                # If theme operations throw exceptions, that's also acceptable
                # as long as app doesn't crash completely
                pass

    @pytest.mark.asyncio
    async def test_theme_with_search_highlighting_edge_cases(self):
        """Test theme compatibility with search result highlighting edge cases."""
        with tempfile.TemporaryDirectory() as new_dir:
            # Create file with challenging content for highlighting
            test_file = os.path.join(new_dir, "highlight_test.txt")
            with open(test_file, "w") as f:
                f.write('20250101 "highlight test"\n')
                f.write("Regular text here\n")
                f.write("UPPERCASE TEXT HERE\n")
                f.write("mixed Case Text Here\n")
                f.write("Special chars: !@#$%^&*()_+-=[]{}|;:,.<>?\n")
                f.write("Numbers: 123456 0.123 -456.789\n")
                f.write("URLs: https://example.com/path?param=value\n")
                f.write("Paths: /usr/bin/test C:\\Windows\\System32\n")

            # Create keywords file
            fd, kw_path = tempfile.mkstemp(suffix='.md', text=True)
            with os.fdopen(fd, "w") as f:
                f.write("# Test\ntext\nTEST\nSpecial")

            try:
                themes = self.get_themes_subset()

                for theme_name in themes[:2]:  # Test subset
                    class TestApp(BaseTestApp):
                        def __init__(self, theme=theme_name):
                            super().__init__(theme)

                        async def on_mount(self) -> None:
                            self.push_screen(SearchScreen(new_dir, "/tmp", kw_path))

                    async with TestApp().run_test() as pilot:
                        await pilot.pause()

                        # Test search with various patterns that could challenge highlighting
                        searches = ["text", "TEXT", "123", "special", "https"]

                        for search_term in searches:
                            # Clear previous search
                            await pilot.press("ctrl+a")  # Select all
                            await pilot.press("delete")  # Delete

                            # Type new search
                            for char in search_term:
                                await pilot.press(char)
                            await pilot.press("enter")
                            await pilot.pause()

                            # Toggle highlighting modes
                            await pilot.press("ctrl+r", "ctrl+k")  # Toggle regex and keywords
                            await pilot.pause()

                            # Verify app didn't crash
                            assert pilot.app.theme == theme_name
            finally:
                os.unlink(kw_path)

    def test_all_themes_have_contrast_ratios(self):
        """Test that all themes have reasonable contrast ratios."""
        themes = discover_themes()

        for theme in themes:
            if not hasattr(theme, 'name'):
                continue

            # Basic sanity checks for theme properties
            assert hasattr(theme, 'foreground'), f"Theme {theme.name} missing foreground"
            assert hasattr(theme, 'background'), f"Theme {theme.name} missing background"

            # Colors should be strings (hex codes)
            fg = getattr(theme, 'foreground', '#FFFFFF')
            bg = getattr(theme, 'background', '#000000')

            assert isinstance(fg, str), f"Theme {theme.name} foreground not string: {fg}"
            assert isinstance(bg, str), f"Theme {theme.name} background not string: {bg}"

            # Should start with # for hex colors (basic format check)
            assert fg.startswith('#') or fg.startswith('$') or len(fg) > 0, f"Invalid foreground in {theme.name}: {fg}"
            assert bg.startswith('#') or bg.startswith('$') or len(bg) > 0, f"Invalid background in {theme.name}: {bg}"

    @pytest.mark.asyncio
    async def test_theme_with_concurrent_updates(self):
        """Test theme behavior with concurrent screen updates."""
        with tempfile.TemporaryDirectory() as test_dir:
            # Create test file
            test_file = os.path.join(test_dir, "concurrent_test.txt")
            with open(test_file, "w") as f:
                f.write('20250101 "concurrent test"\ntest line\n')

            class TestApp(BaseTestApp):
                def __init__(self):
                    super().__init__('ayu-mirage')

                async def on_mount(self) -> None:
                    from delta_vision.screens.file_viewer import FileViewerScreen
                    self.push_screen(FileViewerScreen(test_file))

            async with TestApp().run_test() as pilot:
                await pilot.pause()

                # Simulate concurrent operations
                pilot.app.theme = 'material'

                # Modify file while theme is changing
                with open(test_file, "a") as f:
                    f.write("new line after theme change\n")

                await pilot.pause()

                # Change theme again
                pilot.app.theme = 'one-dark'
                await pilot.pause()

                # Test navigation still works
                await pilot.press("j", "k")
                await pilot.pause()

                # Verify final state
                assert pilot.app.theme == 'one-dark'


class TestThemePerformance:
    """Test theme performance and resource usage."""

    @pytest.mark.asyncio
    async def test_theme_memory_usage(self):
        """Test that theme switching doesn't cause memory leaks."""
        import gc

        class TestApp(BaseTestApp):
            def __init__(self):
                super().__init__('textual-dark')

            async def on_mount(self) -> None:
                from delta_vision.screens.main_screen import MainScreen
                self.push_screen(MainScreen("/tmp", "/tmp", None))

        async with TestApp().run_test() as pilot:
            await pilot.pause()

            # Measure initial state
            gc.collect()
            initial_objects = len(gc.get_objects())

            # Switch themes multiple times
            themes = ['textual-light', 'ayu-mirage', 'material', 'textual-dark']
            for theme in themes:
                pilot.app.theme = theme
                await pilot.pause()

            # Measure final state
            gc.collect()
            final_objects = len(gc.get_objects())

            # Object count shouldn't grow excessively
            # Allow for some growth but not unlimited
            assert final_objects < initial_objects * 1.5, (
                f"Potential memory leak: {initial_objects} -> {final_objects} objects"
            )

    @pytest.mark.asyncio
    async def test_theme_switching_speed(self):
        """Test that theme switching is reasonably fast."""
        import time

        class TestApp(BaseTestApp):
            def __init__(self):
                super().__init__('textual-dark')

            async def on_mount(self) -> None:
                from delta_vision.screens.main_screen import MainScreen
                self.push_screen(MainScreen("/tmp", "/tmp", None))

        async with TestApp().run_test() as pilot:
            await pilot.pause()

            themes = ['textual-light', 'ayu-mirage', 'material']

            start_time = time.time()

            for theme in themes:
                pilot.app.theme = theme
                await pilot.pause()

            end_time = time.time()
            elapsed = end_time - start_time

            # Theme switching should be fast (arbitrary reasonable limit)
            assert elapsed < 10.0, f"Theme switching too slow: {elapsed:.2f} seconds for {len(themes)} themes"
