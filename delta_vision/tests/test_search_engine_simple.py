"""Simplified tests for the search engine utility module.

This module tests the core search functionality with the actual API
that exists in the codebase.
"""

import os
import tempfile

import pytest

from delta_vision.utils.search_engine import SearchConfig, SearchEngine, SearchMatch


class TestSearchEngineBasic:
    """Basic tests for search engine functionality."""

    @pytest.fixture
    def test_files(self):
        """Create test files with known content."""
        with tempfile.TemporaryDirectory() as test_dir:
            # Create test files
            test_file1 = os.path.join(test_dir, "test1.txt")
            with open(test_file1, "w") as f:
                f.write('20250101 "search test"\n')
                f.write("This is a test file.\n")
                f.write("It contains searchable content.\n")
                f.write("Multiple lines for testing.\n")

            test_file2 = os.path.join(test_dir, "test2.txt")
            with open(test_file2, "w") as f:
                f.write('20250102 "another command"\n')
                f.write("Different content here.\n")
                f.write("No matches in this one.\n")

            yield test_dir

    def test_search_engine_creation(self):
        """Test search engine can be created."""
        engine = SearchEngine()
        assert engine is not None
        assert engine.config is not None

    def test_search_config_defaults(self):
        """Test search configuration defaults."""
        config = SearchConfig()
        assert config.max_files == 5000
        assert config.max_preview_chars == 200
        assert config.case_sensitive is False

    def test_search_match_creation(self):
        """Test search match creation."""
        match = SearchMatch(file_path="/test/file.txt", line_no=1, line="test content", cmd="test command")
        assert match.file_path == "/test/file.txt"
        assert match.line_no == 1
        assert match.line == "test content"
        assert match.cmd == "test command"

    def test_basic_search(self, test_files):
        """Test basic search functionality."""
        engine = SearchEngine()

        matches, files_scanned, elapsed = engine.search_folders(query="test", folders=[test_files], regex_mode=False)

        # Basic validation
        assert isinstance(matches, list)
        assert isinstance(files_scanned, int)
        assert isinstance(elapsed, float)
        assert files_scanned >= 0
        assert elapsed >= 0.0

    def test_regex_search(self, test_files):
        """Test regex search functionality."""
        engine = SearchEngine()

        matches, files_scanned, elapsed = engine.search_folders(query=r"test\w*", folders=[test_files], regex_mode=True)

        # Should handle regex without crashing
        assert isinstance(matches, list)
        assert isinstance(files_scanned, int)
        assert isinstance(elapsed, float)

    def test_case_sensitive_search(self, test_files):
        """Test case sensitive search."""
        config = SearchConfig(case_sensitive=True)
        engine = SearchEngine(config)

        matches, files_scanned, elapsed = engine.search_folders(query="TEST", folders=[test_files], regex_mode=False)

        # Should handle case sensitivity
        assert isinstance(matches, list)
        assert isinstance(files_scanned, int)

    def test_empty_query(self, test_files):
        """Test search with empty query."""
        engine = SearchEngine()

        matches, files_scanned, elapsed = engine.search_folders(query="", folders=[test_files], regex_mode=False)

        # Should handle empty query gracefully
        # (May return all lines or no lines depending on implementation)
        assert isinstance(matches, list)

    def test_nonexistent_folder(self):
        """Test search in nonexistent folder."""
        engine = SearchEngine()

        matches, files_scanned, elapsed = engine.search_folders(
            query="test", folders=["/nonexistent/path"], regex_mode=False
        )

        # Should handle missing folders gracefully
        assert isinstance(matches, list)
        assert isinstance(files_scanned, int)

    def test_invalid_regex(self, test_files):
        """Test search with invalid regex."""
        engine = SearchEngine()

        matches, files_scanned, elapsed = engine.search_folders(
            query="[invalid regex(", folders=[test_files], regex_mode=True
        )

        # Should handle invalid regex gracefully
        assert isinstance(matches, list)
        assert len(matches) == 0  # No results due to invalid regex

    def test_max_files_limit(self, test_files):
        """Test max files limit."""
        config = SearchConfig(max_files=1)
        engine = SearchEngine(config)

        matches, files_scanned, elapsed = engine.search_folders(query="test", folders=[test_files], regex_mode=False)

        # Should respect max files limit
        assert files_scanned <= 1

    def test_search_multiple_folders(self, test_files):
        """Test searching multiple folders."""
        engine = SearchEngine()

        with tempfile.TemporaryDirectory() as second_dir:
            # Create another test file
            test_file = os.path.join(second_dir, "another.txt")
            with open(test_file, "w") as f:
                f.write('20250103 "more tests"\n')
                f.write("More test content.\n")

            matches, files_scanned, elapsed = engine.search_folders(
                query="test", folders=[test_files, second_dir], regex_mode=False
            )

            # Should search both folders
            assert isinstance(matches, list)
            assert files_scanned > 0

    def test_search_performance(self, test_files):
        """Test that search completes in reasonable time."""
        import time

        engine = SearchEngine()
        start_time = time.time()

        matches, files_scanned, elapsed = engine.search_folders(query="test", folders=[test_files], regex_mode=False)

        total_time = time.time() - start_time

        # Should complete quickly for small test set
        assert total_time < 5.0  # 5 seconds max
        assert elapsed <= total_time  # Reported time should be reasonable
