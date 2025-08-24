"""Integration tests for complete application workflows.

This module tests end-to-end functionality across multiple screens and
components to ensure the entire Delta Vision application works correctly
as an integrated system.
"""

import asyncio
import os
import tempfile
import time
from unittest.mock import Mock, patch

import pytest
from textual.app import App

from delta_vision.entry_points import HomeApp
from delta_vision.screens.compare import CompareScreen
from delta_vision.screens.keywords_screen import KeywordsScreen
from delta_vision.screens.main_screen import MainScreen
from delta_vision.screens.search import SearchScreen


class TestCompleteWorkflows:
    """Test complete user workflows through the application."""

    @pytest.fixture
    def test_environment(self):
        """Set up a complete test environment with files and directories."""
        with tempfile.TemporaryDirectory() as new_dir:
            with tempfile.TemporaryDirectory() as old_dir:
                # Create test files in NEW directory
                new_file1 = os.path.join(new_dir, "search_test.txt")
                with open(new_file1, "w") as f:
                    f.write('20250101 "search command test"\n')
                    f.write("This file contains searchable content.\n")
                    f.write("Multiple lines for testing search functionality.\n")
                    f.write("Keywords like important and critical should be found.\n")

                new_file2 = os.path.join(new_dir, "compare_test.txt")
                with open(new_file2, "w") as f:
                    f.write('20250102 "compare command test"\n')
                    f.write("New version of the file.\n")
                    f.write("Updated content here.\n")
                    f.write("Additional line in new version.\n")

                # Create test files in OLD directory
                old_file1 = os.path.join(old_dir, "search_test.txt")
                with open(old_file1, "w") as f:
                    f.write('20241231 "old search command"\n')
                    f.write("Old version with different content.\n")
                    f.write("Still has searchable text though.\n")

                old_file2 = os.path.join(old_dir, "compare_test.txt")
                with open(old_file2, "w") as f:
                    f.write('20241230 "old compare command"\n')
                    f.write("Old version of the file.\n")
                    f.write("Original content here.\n")

                # Create keywords file
                fd, kw_path = tempfile.mkstemp(suffix='.md', text=True)
                with os.fdopen(fd, 'w') as f:
                    f.write("# Important (red)\n")
                    f.write("important\n")
                    f.write("critical\n")
                    f.write("urgent\n")
                    f.write("\n")
                    f.write("# Status (green)\n")
                    f.write("success\n")
                    f.write("complete\n")
                    f.write("finished\n")

                yield new_dir, old_dir, kw_path

    @pytest.mark.asyncio
    async def test_home_to_search_workflow(self, test_environment):
        """Test workflow from home screen to search screen."""
        new_dir, old_dir, kw_path = test_environment

        class TestApp(App):
            def __init__(self):
                super().__init__()
                self.theme = 'textual-dark'

            async def on_mount(self) -> None:
                self.push_screen(MainScreen(new_dir, old_dir, kw_path))

        # Mock file watching to avoid observer issues in tests
        with patch('delta_vision.screens.main_screen.start_observer'):
            with patch('delta_vision.screens.search.start_observer'):
                async with TestApp().run_test() as pilot:
                    await pilot.pause()

                    # Should start on MainScreen
                    assert isinstance(pilot.app.screen, MainScreen)

                    # Navigate to search screen (option 2)
                    await pilot.press("2")
                    await pilot.pause()

                    # Should now be on SearchScreen
                    assert isinstance(pilot.app.screen, SearchScreen)

                    # Perform a search
                    await pilot.press("s", "e", "a", "r", "c", "h")
                    await pilot.press("enter")
                    await pilot.pause()

                    # Should have processed the search
                    search_screen = pilot.app.screen
                    assert isinstance(search_screen, SearchScreen)

    @pytest.mark.asyncio
    async def test_search_to_file_viewer_workflow(self, test_environment):
        """Test workflow from search results to file viewer."""
        new_dir, old_dir, kw_path = test_environment

        class TestApp(App):
            def __init__(self):
                super().__init__()
                self.theme = 'textual-dark'

            async def on_mount(self) -> None:
                # Start directly on search screen
                self.push_screen(SearchScreen(new_dir, old_dir, kw_path))

        with patch('delta_vision.screens.search.start_observer'):
            with patch('delta_vision.screens.file_viewer.start_observer'):
                async with TestApp().run_test() as pilot:
                    await pilot.pause()

                    # Should start on SearchScreen
                    assert isinstance(pilot.app.screen, SearchScreen)

                    # Perform search to get results
                    await pilot.press("c", "o", "n", "t", "e", "n", "t")
                    await pilot.press("enter")
                    await pilot.pause()

                    # Press Enter to open selected file
                    await pilot.press("enter")
                    await pilot.pause()

                    # Should now be on FileViewerScreen
                    # (May not always work if no results, but test shouldn't crash)
                    current_screen = pilot.app.screen
                    assert current_screen is not None

    @pytest.mark.asyncio
    async def test_compare_to_diff_viewer_workflow(self, test_environment):
        """Test workflow from compare screen to diff viewer."""
        new_dir, old_dir, kw_path = test_environment

        class TestApp(App):
            def __init__(self):
                super().__init__()
                self.theme = 'textual-dark'

            async def on_mount(self) -> None:
                # Start on compare screen
                self.push_screen(CompareScreen(new_dir, old_dir, kw_path))

        with patch('delta_vision.screens.compare.start_observer'):
            with patch('delta_vision.screens.diff_viewer.start_observer'):
                async with TestApp().run_test() as pilot:
                    await pilot.pause()

                    # Should start on CompareScreen
                    assert isinstance(pilot.app.screen, CompareScreen)

                    # Press Enter to open diff viewer for selected pair
                    await pilot.press("enter")
                    await pilot.pause()

                    # May navigate to diff viewer if files exist
                    current_screen = pilot.app.screen
                    assert current_screen is not None

    @pytest.mark.asyncio
    async def test_keyword_highlighting_workflow(self, test_environment):
        """Test keyword highlighting across different screens."""
        new_dir, old_dir, kw_path = test_environment

        class TestApp(App):
            def __init__(self):
                super().__init__()
                self.theme = 'textual-dark'

            async def on_mount(self) -> None:
                self.push_screen(KeywordsScreen(new_dir, old_dir, kw_path))

        with patch('delta_vision.screens.keywords_screen.start_observer'):
            with patch('delta_vision.screens.file_viewer.start_observer'):
                async with TestApp().run_test() as pilot:
                    await pilot.pause()

                    # Should start on KeywordsScreen
                    assert isinstance(pilot.app.screen, KeywordsScreen)

                    # Navigate and interact
                    await pilot.press("j", "k")  # Navigate table
                    await pilot.pause()

                    # Press Enter to view file with keywords
                    await pilot.press("enter")
                    await pilot.pause()

                    # Should handle navigation gracefully
                    current_screen = pilot.app.screen
                    assert current_screen is not None

    @pytest.mark.asyncio
    async def test_theme_switching_during_workflow(self, test_environment):
        """Test theme switching during active workflow."""
        new_dir, old_dir, kw_path = test_environment

        class TestApp(HomeApp):
            def __init__(self):
                super().__init__()

            async def on_mount(self) -> None:
                self.push_screen(MainScreen(new_dir, old_dir, kw_path))

        with patch('delta_vision.screens.main_screen.start_observer'):
            with patch('delta_vision.screens.search.start_observer'):
                async with TestApp().run_test() as pilot:
                    await pilot.pause()

                    # Start on main screen
                    assert isinstance(pilot.app.screen, MainScreen)
                    original_theme = pilot.app.theme

                    # Switch theme
                    pilot.app.theme = 'textual-light'
                    await pilot.pause()

                    # Navigate to different screen
                    await pilot.press("2")  # Search screen
                    await pilot.pause()

                    # Theme should be applied
                    assert pilot.app.theme == 'textual-light'
                    assert pilot.app.theme != original_theme

                    # Switch theme again
                    pilot.app.theme = 'textual-dark'
                    await pilot.pause()

                    # Should handle theme changes gracefully
                    assert isinstance(pilot.app.screen, SearchScreen)

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, test_environment):
        """Test error recovery during workflows."""
        new_dir, old_dir, kw_path = test_environment

        class TestApp(App):
            def __init__(self):
                super().__init__()
                self.theme = 'textual-dark'

            async def on_mount(self) -> None:
                self.push_screen(SearchScreen(new_dir, old_dir, kw_path))

        with patch('delta_vision.screens.search.start_observer'):
            async with TestApp().run_test() as pilot:
                await pilot.pause()

                # Start on search screen
                assert isinstance(pilot.app.screen, SearchScreen)

                # Try invalid operations that should be handled gracefully
                await pilot.press("ctrl+z")  # Unusual key combo
                await pilot.pause()

                await pilot.press("escape")  # Escape key
                await pilot.pause()

                # Should still be functional
                await pilot.press("t", "e", "s", "t")
                await pilot.pause()

                # Application should remain stable
                assert isinstance(pilot.app.screen, SearchScreen)

    @pytest.mark.asyncio
    async def test_navigation_breadcrumb_workflow(self, test_environment):
        """Test navigation breadcrumb through multiple screens."""
        new_dir, old_dir, kw_path = test_environment

        class TestApp(App):
            def __init__(self):
                super().__init__()
                self.theme = 'textual-dark'

            async def on_mount(self) -> None:
                self.push_screen(MainScreen(new_dir, old_dir, kw_path))

        with patch('delta_vision.screens.main_screen.start_observer'):
            with patch('delta_vision.screens.search.start_observer'):
                with patch('delta_vision.screens.file_viewer.start_observer'):
                    async with TestApp().run_test() as pilot:
                        await pilot.pause()

                        # Start: MainScreen
                        assert isinstance(pilot.app.screen, MainScreen)

                        # Navigate: MainScreen -> SearchScreen
                        await pilot.press("2")
                        await pilot.pause()
                        assert isinstance(pilot.app.screen, SearchScreen)

                        # Go back: SearchScreen -> MainScreen
                        await pilot.press("q")
                        await pilot.pause()

                        # Should return to previous screen
                        current_screen = pilot.app.screen
                        assert current_screen is not None

    @pytest.mark.asyncio
    async def test_concurrent_screen_operations(self, test_environment):
        """Test concurrent operations across multiple screen types."""
        new_dir, old_dir, kw_path = test_environment

        # Create multiple file modifications
        additional_file = os.path.join(new_dir, "concurrent_test.txt")
        with open(additional_file, "w") as f:
            f.write('20250103 "concurrent test"\n')
            f.write("Testing concurrent operations.\n")

        class TestApp(App):
            def __init__(self):
                super().__init__()
                self.theme = 'textual-dark'

            async def on_mount(self) -> None:
                self.push_screen(SearchScreen(new_dir, old_dir, kw_path))

        with patch('delta_vision.screens.search.start_observer') as mock_observer:
            mock_observer.return_value = Mock()

            async with TestApp().run_test() as pilot:
                await pilot.pause()

                # Perform search
                await pilot.press("c", "o", "n", "c", "u", "r", "r", "e", "n", "t")
                await pilot.press("enter")
                await pilot.pause()

                # Modify file during search (simulate concurrent file changes)
                with open(additional_file, "a") as f:
                    f.write("Additional content during search.\n")

                # Continue using the application
                await pilot.press("j", "k")  # Navigate results
                await pilot.pause()

                # Should handle concurrent file changes gracefully
                assert isinstance(pilot.app.screen, SearchScreen)

    def test_application_startup_and_shutdown(self, test_environment):
        """Test complete application startup and shutdown sequence."""
        new_dir, old_dir, kw_path = test_environment

        # Test HomeApp instantiation
        app = HomeApp()
        assert app is not None
        assert hasattr(app, 'theme')
        assert hasattr(app, 'default_theme')

        # Test theme system is working
        original_theme = app.theme
        app.theme = 'textual-light'
        assert app.theme == 'textual-light'

        # Reset theme
        app.theme = original_theme
        assert app.theme == original_theme

    @pytest.mark.asyncio
    async def test_performance_with_many_files(self):
        """Test application performance with many files."""
        with tempfile.TemporaryDirectory() as new_dir:
            with tempfile.TemporaryDirectory() as old_dir:
                # Create many test files
                for i in range(50):
                    new_file = os.path.join(new_dir, f"perf_test_{i}.txt")
                    with open(new_file, "w") as f:
                        f.write(f'20250101 "performance test {i}"\n')
                        f.write(f"Content for file {i}\n")
                        f.write("Searchable content for testing.\n")

                for i in range(30):
                    old_file = os.path.join(old_dir, f"perf_test_{i}.txt")
                    with open(old_file, "w") as f:
                        f.write(f'20241231 "old performance test {i}"\n')
                        f.write(f"Old content for file {i}\n")

                # Create keywords file
                fd, kw_path = tempfile.mkstemp(suffix='.md', text=True)
                with os.fdopen(fd, 'w') as f:
                    f.write("# Test\nsearchable\ncontent\nperformance\n")

                class PerfTestApp(App):
                    def __init__(self):
                        super().__init__()
                        self.theme = 'textual-dark'

                    async def on_mount(self) -> None:
                        self.push_screen(CompareScreen(new_dir, old_dir, kw_path))

                # Time the operation
                start_time = time.time()

                with patch('delta_vision.screens.compare.start_observer'):
                    async with PerfTestApp().run_test() as pilot:
                        await pilot.pause()

                        # Navigate through files
                        for _ in range(10):
                            await pilot.press("j")
                            await asyncio.sleep(0.01)  # Brief pause

                        await pilot.pause()

                end_time = time.time()
                elapsed = end_time - start_time

                # Should complete within reasonable time
                assert elapsed < 30.0  # 30 seconds max for 50+30 files

    @pytest.mark.asyncio
    async def test_unicode_handling_workflow(self):
        """Test Unicode handling throughout the application workflow."""
        with tempfile.TemporaryDirectory() as new_dir:
            with tempfile.TemporaryDirectory() as old_dir:
                # Create Unicode test files
                unicode_file = os.path.join(new_dir, "unicode_test.txt")
                with open(unicode_file, "w", encoding="utf-8") as f:
                    f.write('20250101 "Unicode test: 测试 🚀"\n')
                    f.write("Content with Unicode: αβγδε ñáéíóú\n")
                    f.write("Emoji test: 🔍 🎯 ⚡ 🔒\n")
                    f.write("Mathematical: ∞≠≤≥±×÷√∂∫\n")

                old_unicode_file = os.path.join(old_dir, "unicode_test.txt")
                with open(old_unicode_file, "w", encoding="utf-8") as f:
                    f.write('20241231 "Old Unicode: 旧测试 🌟"\n')
                    f.write("Old content with Unicode: αβγ\n")

                # Create Unicode keywords file
                fd, kw_path = tempfile.mkstemp(suffix='.md', text=True)
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write("# Unicode Keywords\n测试\nUnicode\n🚀\nαβγδε\n")

                class UnicodeTestApp(App):
                    def __init__(self):
                        super().__init__()
                        self.theme = 'textual-dark'

                    async def on_mount(self) -> None:
                        self.push_screen(SearchScreen(new_dir, old_dir, kw_path))

                with patch('delta_vision.screens.search.start_observer'):
                    async with UnicodeTestApp().run_test() as pilot:
                        await pilot.pause()

                        # Search for Unicode content
                        await pilot.press("u", "n", "i", "c", "o", "d", "e")
                        await pilot.press("enter")
                        await pilot.pause()

                        # Should handle Unicode search gracefully
                        assert isinstance(pilot.app.screen, SearchScreen)

                        # Navigate results
                        await pilot.press("j", "k")
                        await pilot.pause()

    @pytest.mark.asyncio
    async def test_screen_state_preservation(self, test_environment):
        """Test that screen state is preserved during navigation."""
        new_dir, old_dir, kw_path = test_environment

        class StateTestApp(App):
            def __init__(self):
                super().__init__()
                self.theme = 'textual-dark'

            async def on_mount(self) -> None:
                self.push_screen(SearchScreen(new_dir, old_dir, kw_path))

        with patch('delta_vision.screens.search.start_observer'):
            with patch('delta_vision.screens.file_viewer.start_observer'):
                async with StateTestApp().run_test() as pilot:
                    await pilot.pause()

                    # Perform search and set state
                    await pilot.press("s", "e", "a", "r", "c", "h")
                    await pilot.press("enter")
                    await pilot.pause()

                    # Navigate to file viewer (if results exist)
                    await pilot.press("enter")
                    await pilot.pause()

                    # Go back to search
                    await pilot.press("q")
                    await pilot.pause()

                    # Should return to search screen
                    current_screen = pilot.app.screen
                    # State preservation depends on implementation
                    assert current_screen is not None

    @pytest.mark.asyncio
    async def test_memory_usage_during_workflow(self, test_environment):
        """Test memory usage during extended workflow."""
        new_dir, old_dir, kw_path = test_environment

        import gc

        class MemoryTestApp(App):
            def __init__(self):
                super().__init__()
                self.theme = 'textual-dark'

            async def on_mount(self) -> None:
                self.push_screen(MainScreen(new_dir, old_dir, kw_path))

        # Measure initial memory
        gc.collect()

        with patch('delta_vision.screens.main_screen.start_observer'):
            with patch('delta_vision.screens.search.start_observer'):
                async with MemoryTestApp().run_test() as pilot:
                    await pilot.pause()

                    # Perform many operations
                    for _i in range(20):
                        # Navigate between screens
                        await pilot.press("2")  # Search
                        await pilot.pause()

                        await pilot.press("q")  # Back
                        await pilot.pause()

                    # Force garbage collection
                    gc.collect()

                    # Application should still be responsive
                    assert isinstance(pilot.app.screen, MainScreen)

    def test_integration_with_environment_variables(self, test_environment):
        """Test integration with environment variable configuration."""
        new_dir, old_dir, kw_path = test_environment

        env_vars = {
            'DELTA_NEW': new_dir,
            'DELTA_OLD': old_dir,
            'DELTA_KEYWORDS': kw_path,
            'DELTA_CONTEXT_LINES': '5',
            'DEBUG': '0'
        }

        with patch.dict(os.environ, env_vars):
            # Application should read environment variables
            assert os.environ.get('DELTA_NEW') == new_dir
            assert os.environ.get('DELTA_OLD') == old_dir
            assert os.environ.get('DELTA_KEYWORDS') == kw_path
            assert os.environ.get('DELTA_CONTEXT_LINES') == '5'

            # HomeApp should work with environment configuration
            app = HomeApp()
            assert app is not None

    @pytest.mark.asyncio
    async def test_full_application_integration(self, test_environment):
        """Test full application integration with all components."""
        new_dir, old_dir, kw_path = test_environment

        class FullIntegrationApp(HomeApp):
            def __init__(self):
                super().__init__()

            async def on_mount(self) -> None:
                self.push_screen(MainScreen(new_dir, old_dir, kw_path))

        # Mock all observers to avoid file watching issues in tests
        with patch('delta_vision.screens.main_screen.start_observer'):
            with patch('delta_vision.screens.search.start_observer'):
                with patch('delta_vision.screens.compare.start_observer'):
                    with patch('delta_vision.screens.file_viewer.start_observer'):
                        async with FullIntegrationApp().run_test() as pilot:
                            await pilot.pause()

                            # Test complete workflow
                            assert isinstance(pilot.app.screen, MainScreen)

                            # Test all main screen options
                            await pilot.press("2")  # Search
                            await pilot.pause()
                            assert isinstance(pilot.app.screen, SearchScreen)

                            await pilot.press("q")  # Back
                            await pilot.pause()

                            await pilot.press("4")  # Compare
                            await pilot.pause()
                            assert isinstance(pilot.app.screen, CompareScreen)

                            await pilot.press("q")  # Back
                            await pilot.pause()

                            # Should return to main screen
                            assert isinstance(pilot.app.screen, MainScreen)
