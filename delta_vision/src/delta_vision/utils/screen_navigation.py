"""Screen navigation helper utilities for Delta Vision.

This module provides centralized navigation helpers to reduce code duplication
when navigating between screens with common parameter patterns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from delta_vision.utils.logger import log

if TYPE_CHECKING:
    from textual.app import App


class ScreenNavigator:
    """Helper class for consistent screen navigation across the application."""

    def __init__(self, app: App):
        """Initialize the navigator with the Textual app instance.

        Args:
            app: The Textual App instance for screen navigation
        """
        self.app = app

    def open_stream_screen(self, folder_path: str | None = None, keywords_path: str | None = None) -> None:
        """Open the live Stream screen for tailing NEW files with highlights.

        Args:
            folder_path: Path to the NEW folder to monitor
            keywords_path: Path to the keywords markdown file
        """
        try:
            from delta_vision.screens import stream

            self.app.push_screen(
                stream.StreamScreen(
                    folder_path=folder_path,
                    keywords_path=keywords_path,
                )
            )
        except ImportError as e:
            log.error(f"Failed to import StreamScreen: {e}")
        except Exception as e:
            log.error(f"Failed to open Stream screen: {e}")

    def open_search_screen(
        self, new_folder_path: str | None = None, old_folder_path: str | None = None, keywords_path: str | None = None
    ) -> None:
        """Open the Search screen for querying across NEW and OLD folders.

        Args:
            new_folder_path: Path to the NEW folder
            old_folder_path: Path to the OLD folder
            keywords_path: Path to the keywords markdown file
        """
        try:
            from delta_vision.screens.search import SearchScreen

            self.app.push_screen(
                SearchScreen(
                    new_folder_path=new_folder_path,
                    old_folder_path=old_folder_path,
                    keywords_path=keywords_path,
                )
            )
        except ImportError as e:
            log.error(f"Failed to import SearchScreen: {e}")
        except Exception as e:
            log.error(f"Failed to open Search screen: {e}")

    def open_keywords_screen(
        self, new_folder_path: str | None = None, old_folder_path: str | None = None, keywords_path: str | None = None
    ) -> None:
        """Open the Keywords screen for managing categories and terms.

        Args:
            new_folder_path: Path to the NEW folder
            old_folder_path: Path to the OLD folder
            keywords_path: Path to the keywords markdown file
        """
        try:
            from delta_vision.screens.keywords_screen import KeywordsScreen

            self.app.push_screen(
                KeywordsScreen(
                    new_folder_path=new_folder_path,
                    old_folder_path=old_folder_path,
                    keywords_path=keywords_path,
                )
            )
        except ImportError as e:
            log.error(f"Failed to import KeywordsScreen: {e}")
        except Exception as e:
            log.error(f"Failed to open Keywords screen: {e}")

    def open_compare_screen(
        self, new_folder_path: str | None = None, old_folder_path: str | None = None, keywords_path: str | None = None
    ) -> None:
        """Open the Compare screen for side-by-side folder comparison.

        Args:
            new_folder_path: Path to the NEW folder
            old_folder_path: Path to the OLD folder
            keywords_path: Path to the keywords markdown file
        """
        try:
            from delta_vision.screens.compare import CompareScreen

            self.app.push_screen(
                CompareScreen(
                    new_folder_path=new_folder_path,
                    old_folder_path=old_folder_path,
                    keywords_path=keywords_path,
                )
            )
        except ImportError as e:
            log.error(f"Failed to import CompareScreen: {e}")
        except Exception as e:
            log.error(f"Failed to open Compare screen: {e}")

    def open_file_viewer(
        self,
        file_path: str,
        line_no: int | None = None,
        keywords_path: str | None = None,
        keywords_enabled: bool = True,
    ) -> None:
        """Open the File Viewer screen for a specific file.

        Args:
            file_path: Path to the file to view
            line_no: Optional line number to jump to
            keywords_path: Path to the keywords markdown file
            keywords_enabled: Whether to enable keyword highlighting by default
        """
        try:
            from delta_vision.screens.file_viewer import FileViewerScreen

            viewer = FileViewerScreen(
                file_path, line_no, keywords_path=keywords_path, keywords_enabled=keywords_enabled
            )
            self.app.push_screen(viewer)
        except ImportError as e:
            log.error(f"Failed to import FileViewerScreen: {e}")
        except Exception as e:
            log.error(f"Failed to open File Viewer for {file_path}: {e}")

    def open_diff_viewer(self, new_path: str, old_path: str | None = None, keywords_path: str | None = None) -> None:
        """Open the Side-by-Side Diff Viewer screen for file comparison.

        Args:
            new_path: Path to the NEW file
            old_path: Path to the OLD file (optional)
            keywords_path: Path to the keywords markdown file
        """
        try:
            from delta_vision.screens.diff_viewer import SideBySideDiffScreen

            self.app.push_screen(
                SideBySideDiffScreen(
                    new_path,
                    old_path,
                    keywords_path=keywords_path,
                )
            )
        except ImportError as e:
            log.error(f"Failed to import SideBySideDiffScreen: {e}")
        except Exception as e:
            log.error(f"Failed to open Diff Viewer for {new_path}: {e}")


def create_navigator(app: App) -> ScreenNavigator:
    """Factory function to create a ScreenNavigator instance.

    Args:
        app: The Textual App instance

    Returns:
        ScreenNavigator instance for the given app
    """
    return ScreenNavigator(app)
