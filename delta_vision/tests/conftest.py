import os
import sys
import tempfile
from typing import Iterator, Tuple
from unittest.mock import Mock

import pytest
from textual.app import App
from textual.events import Key

# Ensure local src path is importable
_here = os.path.dirname(os.path.dirname(__file__))  # delta_vision folder
_src = os.path.join(_here, "src")
if os.path.isdir(_src) and _src not in sys.path:
    sys.path.insert(0, _src)

from delta_vision.themes import register_all_themes  # noqa: E402


class BaseTestApp(App):
    """Base test application with proper theme registration.

    This eliminates the duplicate theme setup patterns found across
    multiple test files.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Register themes to prevent theme-related test failures
        register_all_themes(self)


@pytest.fixture
def test_app_with_themes() -> BaseTestApp:
    """Create a test app with themes properly registered.

    This fixture eliminates the duplicate app initialization with theme
    registration pattern found across multiple test files.
    """
    return BaseTestApp()


@pytest.fixture
def temp_test_environment() -> Iterator[Tuple[str, str]]:
    """Create a complete test environment with standard test files.

    This fixture creates temporary directories with standardized test content,
    eliminating the duplicate test file creation patterns found in:
    - test_integration.py
    - test_live_updates.py
    - test_search_engine.py
    - test_networking.py

    Returns:
        Tuple of (new_dir, old_dir) paths with test files
    """
    with tempfile.TemporaryDirectory() as new_dir:
        with tempfile.TemporaryDirectory() as old_dir:
            # Standard NEW directory test files
            create_standard_new_files(new_dir)

            # Standard OLD directory test files
            create_standard_old_files(old_dir)

            yield new_dir, old_dir


def create_standard_new_files(new_dir: str) -> None:
    """Create standard test files in the NEW directory."""
    # Primary search/comparison test file
    new_file1 = os.path.join(new_dir, "search_test.txt")
    with open(new_file1, "w", encoding="utf-8") as f:
        f.write('20250101 "search command test"\n')
        f.write("This file contains searchable content.\n")
        f.write("Multiple lines for testing search functionality.\n")
        f.write("Keywords like important and critical should be found.\n")
        f.write("Case sensitive TESTING here.\n")

    # Secondary comparison test file
    new_file2 = os.path.join(new_dir, "compare_test.txt")
    with open(new_file2, "w", encoding="utf-8") as f:
        f.write('20250102 "compare command test"\n')
        f.write("New version of the file.\n")
        f.write("Updated content here.\n")
        f.write("Additional line in new version.\n")

    # Keywords test file
    new_file3 = os.path.join(new_dir, "keywords_test.txt")
    with open(new_file3, "w", encoding="utf-8") as f:
        f.write('20250103 "keywords test command"\n')
        f.write("This line contains important keywords.\n")
        f.write("Critical security alert in this line.\n")
        f.write("Normal content without special terms.\n")


def create_standard_old_files(old_dir: str) -> None:
    """Create standard test files in the OLD directory."""
    # Primary comparison file (older version)
    old_file1 = os.path.join(old_dir, "search_test.txt")
    with open(old_file1, "w", encoding="utf-8") as f:
        f.write('20241231 "old search command"\n')
        f.write("Old version of searchable content.\n")
        f.write("Different keywords and patterns here.\n")
        f.write("Some content removed in new version.\n")

    # Secondary comparison file (older version)
    old_file2 = os.path.join(old_dir, "compare_test.txt")
    with open(old_file2, "w", encoding="utf-8") as f:
        f.write('20241230 "old compare command"\n')
        f.write("Original version of the file.\n")
        f.write("Content that was updated.\n")


@pytest.fixture
def temp_keywords_file() -> Iterator[str]:
    """Create a temporary keywords file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("# Security (Red)\n")
        f.write("critical\n")
        f.write("important\n")
        f.write("security\n")
        f.write("\n")
        f.write("# Networking (Blue)\n")
        f.write("TCP\n")
        f.write("UDP\n")
        f.write("connection\n")
        f.write("\n")
        f.write("# Testing\n")
        f.write("test\n")
        f.write("testing\n")
        keywords_path = f.name

    try:
        yield keywords_path
    finally:
        try:
            os.unlink(keywords_path)
        except OSError:
            pass  # File may have been deleted already


def create_mock_key_event(key: str, **kwargs) -> Mock:
    """Create a mock keyboard event for testing.

    Args:
        key: The key string (e.g., "enter", "escape", "j", "k")
        **kwargs: Additional attributes for the mock event

    Returns:
        Mock Key event object
    """
    mock_event = Mock(spec=Key)
    mock_event.key = key
    mock_event.char = key if len(key) == 1 else None
    mock_event.is_printable = len(key) == 1 and key.isprintable()

    # Set any additional attributes
    for attr_name, attr_value in kwargs.items():
        setattr(mock_event, attr_name, attr_value)

    return mock_event
