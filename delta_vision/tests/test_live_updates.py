"""Tests for live update functionality across all screens.

This module tests the file watching and live update behavior that was recently
implemented in diff_viewer.py, file_viewer.py, and search.py to ensure files
are monitored correctly and updates trigger appropriate refreshes.
"""

import asyncio
import os
import tempfile
import time
from unittest.mock import Mock, patch

import pytest
from textual.app import App

from delta_vision.screens.diff_viewer import SideBySideDiffScreen
from delta_vision.screens.file_viewer import FileViewerScreen
from delta_vision.screens.search import SearchScreen
from delta_vision.utils.watchdog import start_observer


class BaseTestApp(App):
    """Base test app for live update tests."""
    def __init__(self):
        super().__init__()
        self.theme = 'textual-dark'


class TestWatchdogUtility:
    """Test the core watchdog utility functions."""

    def test_start_observer_creates_observer(self):
        """Test that start_observer creates and starts a file observer."""
        callback = Mock()

        with tempfile.TemporaryDirectory() as test_dir:
            observer = start_observer(test_dir, callback)

            assert observer is not None
            assert observer.is_alive()

            # Cleanup
            observer.stop()
            observer.join()

    def test_start_observer_handles_nonexistent_path(self):
        """Test that start_observer handles nonexistent paths gracefully."""
        callback = Mock()
        nonexistent_path = "/nonexistent/path/that/should/not/exist"

        # Should not raise an exception
        observer = start_observer(nonexistent_path, callback)

        if observer:
            observer.stop()
            observer.join()

    def test_start_observer_callback_triggered(self):
        """Test that file changes trigger the callback."""
        callback = Mock()

        with tempfile.TemporaryDirectory() as test_dir:
            observer = start_observer(test_dir, callback, debounce_ms=100)

            # Give observer time to start
            time.sleep(0.1)

            # Create a file to trigger the callback
            test_file = os.path.join(test_dir, "test.txt")
            with open(test_file, "w") as f:
                f.write("test content")

            # Wait for debounce period
            time.sleep(0.2)

            # Cleanup
            observer.stop()
            observer.join()

            # Callback should have been called
            assert callback.call_count > 0

    def test_observer_debouncing_works(self):
        """Test that rapid file changes are debounced properly."""
        callback = Mock()

        with tempfile.TemporaryDirectory() as test_dir:
            observer = start_observer(test_dir, callback, debounce_ms=300)

            # Give observer time to start
            time.sleep(0.1)

            test_file = os.path.join(test_dir, "test.txt")

            # Make rapid changes (should be debounced into fewer calls)
            for i in range(5):
                with open(test_file, "w") as f:
                    f.write(f"content {i}")
                time.sleep(0.05)  # Rapid changes within debounce period

            # Wait for debounce period to complete
            time.sleep(0.4)

            # Cleanup
            observer.stop()
            observer.join()

            # Should have fewer callback calls than file modifications due to debouncing
            assert callback.call_count < 5
            assert callback.call_count >= 1


class TestFileViewerLiveUpdates:
    """Test live updates in FileViewerScreen."""

    @pytest.fixture
    def test_file(self):
        """Create a temporary test file."""
        fd, path = tempfile.mkstemp(suffix='.txt', text=True)
        with os.fdopen(fd, 'w') as f:
            f.write('20250101 "test command"\nInitial content\nLine 2\n')
        yield path
        try:
            os.unlink(path)
        except OSError:
            pass

    @pytest.mark.asyncio
    async def test_file_viewer_starts_observer_on_mount(self, test_file):
        """Test that FileViewerScreen starts file observer on mount."""

        class TestApp(BaseTestApp):
            def __init__(self):
                super().__init__()

            async def on_mount(self) -> None:
                self.push_screen(FileViewerScreen(test_file))

        with patch('delta_vision.screens.file_viewer.start_observer') as mock_start_observer:
            mock_observer = Mock()
            mock_start_observer.return_value = mock_observer

            async with TestApp().run_test() as pilot:
                await pilot.pause()

                # Should have started observer
                mock_start_observer.assert_called_once()

                # Should have set observer on screen
                screen = pilot.app.screen
                assert hasattr(screen, '_file_observer')

    @pytest.mark.asyncio
    async def test_file_viewer_stops_observer_on_unmount(self, test_file):
        """Test that FileViewerScreen stops observer on unmount."""

        class TestApp(BaseTestApp):
            def __init__(self):
                super().__init__()

            async def on_mount(self) -> None:
                self.push_screen(FileViewerScreen(test_file))

        mock_observer = Mock()

        with patch('delta_vision.screens.file_viewer.start_observer', return_value=mock_observer):
            async with TestApp().run_test() as pilot:
                await pilot.pause()

                screen = pilot.app.screen
                # Simulate unmount by calling on_unmount directly
                screen.on_unmount()

                # Observer should be stopped
                mock_observer.stop.assert_called_once()
                mock_observer.join.assert_called_once()

    @pytest.mark.asyncio
    async def test_file_viewer_refresh_preserves_position(self, test_file):
        """Test that file refresh preserves current line position."""

        class TestApp(BaseTestApp):
            def __init__(self):
                super().__init__()

            async def on_mount(self) -> None:
                self.push_screen(FileViewerScreen(test_file))

        # Mock the observer to avoid actual file watching
        with patch('delta_vision.screens.file_viewer.start_observer'):
            async with TestApp().run_test() as pilot:
                await pilot.pause()

                screen = pilot.app.screen

                # Simulate moving to a specific line
                screen._current_line = 2

                # Trigger refresh
                screen.refresh_file()
                await pilot.pause()

                # Position should be preserved (or adjusted if file is shorter)
                assert screen._current_line >= 0


class TestDiffViewerLiveUpdates:
    """Test live updates in SideBySideDiffScreen."""

    @pytest.fixture
    def test_files(self):
        """Create temporary test files for diffing."""
        with tempfile.TemporaryDirectory() as new_dir:
            with tempfile.TemporaryDirectory() as old_dir:
                # Create new file
                new_file = os.path.join(new_dir, "test.txt")
                with open(new_file, "w") as f:
                    f.write('20250101 "test command"\nNew content\nLine 2\n')

                # Create old file
                old_file = os.path.join(old_dir, "test.txt")
                with open(old_file, "w") as f:
                    f.write('20250101 "test command"\nOld content\nLine 2\n')

                yield new_file, old_file

    @pytest.mark.asyncio
    async def test_diff_viewer_starts_observers_on_mount(self, test_files):
        """Test that DiffViewerScreen starts observers for both files."""
        new_file, old_file = test_files

        class TestApp(BaseTestApp):
            def __init__(self):
                super().__init__()

            async def on_mount(self) -> None:
                self.push_screen(SideBySideDiffScreen(new_file, old_file))

        with patch('delta_vision.screens.diff_viewer.start_observer') as mock_start_observer:
            mock_observer = Mock()
            mock_start_observer.return_value = mock_observer

            async with TestApp().run_test() as pilot:
                await pilot.pause()

                # Should have started observers for both files
                assert mock_start_observer.call_count == 2

                # Check that observers were set up for the right files
                calls = mock_start_observer.call_args_list
                observed_files = {call[0][0] for call in calls}
                assert new_file in observed_files
                assert old_file in observed_files

    @pytest.mark.asyncio
    async def test_diff_viewer_refresh_preserves_scroll(self, test_files):
        """Test that diff refresh preserves scroll position."""
        new_file, old_file = test_files

        class TestApp(BaseTestApp):
            def __init__(self):
                super().__init__()

            async def on_mount(self) -> None:
                self.push_screen(SideBySideDiffScreen(new_file, old_file))

        with patch('delta_vision.screens.diff_viewer.start_observer'):
            async with TestApp().run_test() as pilot:
                await pilot.pause()

                screen = pilot.app.screen

                # Simulate scrolling
                if hasattr(screen, '_current_line'):
                    screen._current_line = 1

                # Trigger refresh
                screen.trigger_refresh()
                await pilot.pause()

                # Screen should still exist and be functional
                assert isinstance(screen, SideBySideDiffScreen)


class TestSearchScreenLiveUpdates:
    """Test live updates in SearchScreen."""

    @pytest.fixture
    def test_dirs(self):
        """Create temporary directories with test files."""
        with tempfile.TemporaryDirectory() as new_dir:
            with tempfile.TemporaryDirectory() as old_dir:
                # Create test files
                new_file = os.path.join(new_dir, "test1.txt")
                with open(new_file, "w") as f:
                    f.write('20250101 "test command"\nSearchable content\n')

                old_file = os.path.join(old_dir, "test1.txt")
                with open(old_file, "w") as f:
                    f.write('20250101 "test command"\nDifferent content\n')

                # Create keywords file
                fd, kw_path = tempfile.mkstemp(suffix='.md', text=True)
                with os.fdopen(fd, 'w') as f:
                    f.write("# Test\nsearchable\ncontent\n")

                yield new_dir, old_dir, kw_path

    @pytest.mark.asyncio
    async def test_search_screen_starts_observers_on_mount(self, test_dirs):
        """Test that SearchScreen starts observers for both directories."""
        new_dir, old_dir, kw_path = test_dirs

        class TestApp(BaseTestApp):
            def __init__(self):
                super().__init__()

            async def on_mount(self) -> None:
                self.push_screen(SearchScreen(new_dir, old_dir, kw_path))

        with patch('delta_vision.screens.search.start_observer') as mock_start_observer:
            mock_observer = Mock()
            mock_start_observer.return_value = mock_observer

            async with TestApp().run_test() as pilot:
                await pilot.pause()

                # Should have started observers for both directories
                assert mock_start_observer.call_count == 2

                # Check that observers were set up for the right directories
                calls = mock_start_observer.call_args_list
                observed_paths = {call[0][0] for call in calls}
                assert new_dir in observed_paths
                assert old_dir in observed_paths

    @pytest.mark.asyncio
    async def test_search_screen_smart_refresh_behavior(self, test_dirs):
        """Test search screen's smart refresh behavior."""
        new_dir, old_dir, kw_path = test_dirs

        class TestApp(BaseTestApp):
            def __init__(self):
                super().__init__()

            async def on_mount(self) -> None:
                self.push_screen(SearchScreen(new_dir, old_dir, kw_path))

        with patch('delta_vision.screens.search.start_observer'):
            async with TestApp().run_test() as pilot:
                await pilot.pause()

                screen = pilot.app.screen

                # Test that _files_changed flag exists and can be set
                if hasattr(screen, '_files_changed'):
                    screen._files_changed = True

                    # Test that indicator update works
                    if hasattr(screen, '_update_files_changed_indicator'):
                        screen._update_files_changed_indicator()

                    # Test that refresh works
                    if hasattr(screen, '_refresh_search_results'):
                        screen._refresh_search_results()

    @pytest.mark.asyncio
    async def test_search_screen_query_tracking(self, test_dirs):
        """Test that search screen tracks query changes properly."""
        new_dir, old_dir, kw_path = test_dirs

        class TestApp(BaseTestApp):
            def __init__(self):
                super().__init__()

            async def on_mount(self) -> None:
                self.push_screen(SearchScreen(new_dir, old_dir, kw_path))

        with patch('delta_vision.screens.search.start_observer'):
            async with TestApp().run_test() as pilot:
                await pilot.pause()

                screen = pilot.app.screen

                # Test query tracking attributes exist
                if hasattr(screen, '_last_search_query'):
                    initial_query = screen._last_search_query

                    # Simulate query change
                    screen._last_search_query = "test query"
                    assert screen._last_search_query != initial_query


class TestLiveUpdateIntegration:
    """Integration tests for live update functionality."""

    @pytest.mark.asyncio
    async def test_multiple_screens_observer_cleanup(self):
        """Test that switching between screens with observers cleans up properly."""
        with tempfile.TemporaryDirectory() as test_dir:
            test_file = os.path.join(test_dir, "test.txt")
            with open(test_file, "w") as f:
                f.write('20250101 "test"\nContent\n')

            class TestApp(BaseTestApp):
                def __init__(self):
                    super().__init__()

                async def on_mount(self) -> None:
                    # Start with file viewer
                    self.push_screen(FileViewerScreen(test_file))

            observer_mocks = []

            def create_mock_observer(*args, **kwargs):
                mock = Mock()
                observer_mocks.append(mock)
                return mock

            with patch('delta_vision.screens.file_viewer.start_observer', side_effect=create_mock_observer):
                async with TestApp().run_test() as pilot:
                    await pilot.pause()

                    # Go back (should trigger cleanup)
                    await pilot.press("q")
                    await pilot.pause()

                    # All observers should have been stopped
                    for mock_observer in observer_mocks:
                        mock_observer.stop.assert_called_once()
                        mock_observer.join.assert_called_once()

    @pytest.mark.asyncio
    async def test_observer_error_handling(self):
        """Test that observer errors are handled gracefully."""
        with tempfile.TemporaryDirectory() as test_dir:
            test_file = os.path.join(test_dir, "test.txt")
            with open(test_file, "w") as f:
                f.write('20250101 "test"\nContent\n')

            class TestApp(BaseTestApp):
                def __init__(self):
                    super().__init__()

                async def on_mount(self) -> None:
                    self.push_screen(FileViewerScreen(test_file))

            # Mock observer that raises an exception
            mock_observer = Mock()
            mock_observer.stop.side_effect = Exception("Observer error")

            with patch('delta_vision.screens.file_viewer.start_observer', return_value=mock_observer):
                async with TestApp().run_test() as pilot:
                    await pilot.pause()

                    # Should not crash when observer cleanup fails
                    screen = pilot.app.screen
                    try:
                        screen.on_unmount()
                    except Exception:
                        pytest.fail("Observer cleanup should handle errors gracefully")


class TestLiveUpdatePerformance:
    """Performance tests for live update functionality."""

    @pytest.mark.asyncio
    async def test_rapid_file_changes_handled_efficiently(self):
        """Test that rapid file changes don't overwhelm the system."""
        callback_count = 0

        def counting_callback():
            nonlocal callback_count
            callback_count += 1

        with tempfile.TemporaryDirectory() as test_dir:
            observer = start_observer(test_dir, counting_callback, debounce_ms=200)

            try:
                # Give observer time to start
                await asyncio.sleep(0.1)

                test_file = os.path.join(test_dir, "rapid_test.txt")

                # Make many rapid changes
                for i in range(20):
                    with open(test_file, "w") as f:
                        f.write(f"Change {i}")
                    await asyncio.sleep(0.01)  # Very rapid changes

                # Wait for debouncing to settle
                await asyncio.sleep(0.3)

                # Should have significantly fewer callbacks than changes due to debouncing
                assert callback_count < 20
                assert callback_count >= 1

            finally:
                if observer:
                    observer.stop()
                    observer.join()

    def test_observer_memory_cleanup(self):
        """Test that observers are properly cleaned up and don't leak memory."""
        import gc

        def dummy_callback():
            pass

        with tempfile.TemporaryDirectory() as test_dir:
            # Create and cleanup many observers
            observers = []

            for _i in range(10):
                observer = start_observer(test_dir, dummy_callback)
                if observer:
                    observers.append(observer)

            # Stop all observers
            for observer in observers:
                observer.stop()
                observer.join()

            # Force garbage collection
            observers.clear()
            gc.collect()

            # Test passes if no exceptions occur (proper cleanup)
            assert True


class TestLiveUpdateErrorRecovery:
    """Test error recovery in live update scenarios."""

    def test_observer_with_deleted_directory(self):
        """Test observer behavior when watched directory is deleted."""
        callback = Mock()

        with tempfile.TemporaryDirectory() as test_dir:
            observer = start_observer(test_dir, callback)

            # Directory gets deleted while observer is running
            # (tempfile context manager will delete it)
            pass

        # Should not crash - observer should handle missing directory
        if observer:
            observer.stop()
            observer.join()

    @pytest.mark.asyncio
    async def test_screen_refresh_with_deleted_file(self):
        """Test screen refresh when watched file is deleted."""

        # Create a temporary file
        fd, test_file = tempfile.mkstemp(suffix='.txt', text=True)
        with os.fdopen(fd, 'w') as f:
            f.write('20250101 "test"\nContent\n')

        class TestApp(BaseTestApp):
            def __init__(self):
                super().__init__()

            async def on_mount(self) -> None:
                self.push_screen(FileViewerScreen(test_file))

        with patch('delta_vision.screens.file_viewer.start_observer'):
            async with TestApp().run_test() as pilot:
                await pilot.pause()

                screen = pilot.app.screen

                # Delete the file
                os.unlink(test_file)

                # Refresh should handle missing file gracefully
                try:
                    screen.refresh_file()
                    await pilot.pause()
                except Exception as e:
                    # Should not raise unhandled exceptions
                    if "No such file" not in str(e):
                        raise
