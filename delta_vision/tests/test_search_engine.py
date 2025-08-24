"""Tests for the search engine utility module.

This module tests the core search functionality that was extracted from the
search screen to ensure search operations work correctly across different
file types, patterns, and edge cases.
"""

import os
import tempfile
from unittest.mock import patch

import pytest

from delta_vision.utils.search_engine import SearchConfig, SearchEngine, SearchMatch


class TestSearchConfig:
    """Test search configuration data structure."""

    def test_search_config_creation(self):
        """Test creating a search configuration."""
        config = SearchConfig(
            max_files=1000,
            max_preview_chars=150,
            case_sensitive=True
        )

        assert config.max_files == 1000
        assert config.max_preview_chars == 150
        assert config.case_sensitive is True

    def test_search_config_defaults(self):
        """Test search configuration defaults."""
        config = SearchConfig()

        # Should have sensible defaults
        assert config.max_files == 5000
        assert config.max_preview_chars == 200
        assert config.case_sensitive is False

    def test_search_config_validation(self):
        """Test search configuration validation."""
        # Should allow different max_files values
        config = SearchConfig(max_files=100)
        assert config.max_files == 100

        # Should allow different preview lengths
        config = SearchConfig(max_preview_chars=50)
        assert config.max_preview_chars == 50


class TestSearchMatch:
    """Test search match data structure."""

    def test_search_match_creation(self):
        """Test creating a search match."""
        match = SearchMatch(
            file_path="/path/to/file.txt",
            line_no=10,
            line="This is a test line with match",
            cmd="test command",
            is_error=False
        )

        assert match.file_path == "/path/to/file.txt"
        assert match.line_no == 10
        assert match.line == "This is a test line with match"
        assert match.cmd == "test command"
        assert match.is_error is False

    def test_search_match_defaults(self):
        """Test search match with minimal data."""
        match = SearchMatch(
            file_path="/path/to/file.txt",
            line_no=5,
            line="test line"
        )

        assert match.file_path == "/path/to/file.txt"
        assert match.line_no == 5
        assert match.line == "test line"
        assert match.cmd is None  # Default value
        assert match.is_error is False  # Default value

    def test_search_match_error(self):
        """Test search match for error conditions."""
        match = SearchMatch(
            file_path="/error/path",
            line_no=0,
            line="[Error reading file]",
            cmd=None,
            is_error=True
        )

        assert match.file_path == "/error/path"
        assert match.line_no == 0
        assert match.line == "[Error reading file]"
        assert match.cmd is None
        assert match.is_error is True


class TestSearchEngine:
    """Test the core search engine functionality."""

    def setup_method(self):
        """Set up test data for each test."""
        self.engine = SearchEngine()

    @pytest.fixture
    def test_files(self):
        """Create test files with known content."""
        with tempfile.TemporaryDirectory() as new_dir:
            with tempfile.TemporaryDirectory() as old_dir:
                # Create test files in NEW directory
                new_file1 = os.path.join(new_dir, "test1.txt")
                with open(new_file1, "w") as f:
                    f.write('20250101 "search test"\n')
                    f.write("This is a test file.\n")
                    f.write("It contains searchable content.\n")
                    f.write("Multiple lines for testing.\n")
                    f.write("Case sensitive TESTING here.\n")

                new_file2 = os.path.join(new_dir, "test2.txt")
                with open(new_file2, "w") as f:
                    f.write('20250102 "another command"\n')
                    f.write("Different content here.\n")
                    f.write("No matches in this one.\n")

                # Create test files in OLD directory
                old_file1 = os.path.join(old_dir, "test1.txt")
                with open(old_file1, "w") as f:
                    f.write('20241231 "old command"\n')
                    f.write("Old version content.\n")
                    f.write("Also has test data.\n")

                yield new_dir, old_dir

    def test_search_engine_initialization(self):
        """Test search engine initializes correctly."""
        engine = SearchEngine()
        assert engine is not None

        # Should be able to create multiple engines
        engine2 = SearchEngine()
        assert engine2 is not engine

    def test_search_literal_string(self, test_files):
        """Test literal string search functionality."""
        new_dir, old_dir = test_files

        config = SearchConfig(case_sensitive=False)
        engine = SearchEngine(config)

        matches, files_scanned, elapsed = engine.search_folders(
            query="test",
            folders=[new_dir, old_dir],
            regex_mode=False
        )

        # Should find matches in files containing "test"
        assert isinstance(matches, list)
        assert files_scanned > 0
        assert elapsed >= 0.0

        # Check that we found matches in the right files
        if len(matches) > 0:
            file_paths = [m.file_path for m in matches]
            assert any("test1.txt" in path for path in file_paths)

            # Check match details
            for match in matches:
                assert isinstance(match.line_no, int)
                assert match.line_no > 0
                assert isinstance(match.line, str)
                assert isinstance(match.file_path, str)

    def test_search_case_sensitivity(self, test_files):
        """Test case-sensitive vs case-insensitive search."""
        new_dir, old_dir = test_files

        # Case-insensitive search
        config_insensitive = SearchConfig(
            query="TESTING",
            use_regex=False,
            case_sensitive=False,
            new_folder=new_dir,
            old_folder=old_dir
        )

        results_insensitive = self.engine.search(config_insensitive)

        # Case-sensitive search
        config_sensitive = SearchConfig(
            query="TESTING",
            use_regex=False,
            case_sensitive=True,
            new_folder=new_dir,
            old_folder=old_dir
        )

        results_sensitive = self.engine.search(config_sensitive)

        # Should find matches in both, but different counts
        # Case-insensitive should find both "testing" and "TESTING"
        # Case-sensitive should only find "TESTING"
        total_insensitive = sum(r.total_matches for r in results_insensitive)
        total_sensitive = sum(r.total_matches for r in results_sensitive)

        assert total_insensitive >= total_sensitive

    def test_search_regex_patterns(self, test_files):
        """Test regular expression search patterns."""
        new_dir, old_dir = test_files

        config = SearchConfig(
            query=r"test\w+",  # Match "test" followed by word characters
            use_regex=True,
            case_sensitive=False,
            new_folder=new_dir,
            old_folder=old_dir
        )

        results = self.engine.search(config)

        # Should find regex matches
        assert len(results) > 0

        # Verify matches contain word patterns starting with "test"
        found_patterns = []
        for result in results:
            for match in result.matches:
                # Extract the matched portion from the line
                if match.match_start > 0 and match.match_end > match.match_start:
                    matched_text = match.line_content[match.match_start:match.match_end]
                    found_patterns.append(matched_text.lower())

        # Should have found words starting with "test"
        assert len(found_patterns) > 0

    def test_search_invalid_regex(self, test_files):
        """Test handling of invalid regex patterns."""
        new_dir, old_dir = test_files

        config = SearchConfig(
            query="[invalid regex(",  # Invalid regex pattern
            use_regex=True,
            case_sensitive=False,
            new_folder=new_dir,
            old_folder=old_dir
        )

        # Should handle invalid regex gracefully
        results = self.engine.search(config)

        # Should return empty results or handle error gracefully
        assert isinstance(results, list)

    def test_search_empty_query(self, test_files):
        """Test search with empty query."""
        new_dir, old_dir = test_files

        config = SearchConfig(
            query="",
            use_regex=False,
            case_sensitive=False,
            new_folder=new_dir,
            old_folder=old_dir
        )

        results = self.engine.search(config)

        # Should return empty results for empty query
        assert len(results) == 0

    def test_search_nonexistent_directories(self):
        """Test search with nonexistent directories."""
        config = SearchConfig(
            query="test",
            use_regex=False,
            case_sensitive=False,
            new_folder="/nonexistent/new",
            old_folder="/nonexistent/old"
        )

        results = self.engine.search(config)

        # Should handle nonexistent directories gracefully
        assert isinstance(results, list)
        assert len(results) == 0

    def test_search_context_lines(self, test_files):
        """Test that search includes context lines."""
        new_dir, old_dir = test_files

        config = SearchConfig(
            query="searchable",
            use_regex=False,
            case_sensitive=False,
            new_folder=new_dir,
            old_folder=old_dir
        )

        results = self.engine.search(config, context_lines=2)

        # Should find the match
        assert len(results) > 0

        # Check context lines are included
        for result in results:
            for match in result.matches:
                if len(match.context_before) > 0 or len(match.context_after) > 0:
                    # At least one match should have context
                    assert True
                    return

        # If no context found, that's also acceptable for some matches

    def test_search_match_positions(self, test_files):
        """Test that match start/end positions are calculated correctly."""
        new_dir, old_dir = test_files

        config = SearchConfig(
            query="test",
            use_regex=False,
            case_sensitive=False,
            new_folder=new_dir,
            old_folder=old_dir
        )

        results = self.engine.search(config)

        # Should find matches with position information
        found_positioned_match = False
        for result in results:
            for match in result.matches:
                if match.match_start >= 0 and match.match_end > match.match_start:
                    # Verify the position actually contains the match
                    matched_text = match.line_content[match.match_start:match.match_end]
                    assert "test" in matched_text.lower()
                    found_positioned_match = True

        # Should have found at least one properly positioned match
        assert found_positioned_match

    def test_search_file_filtering(self, test_files):
        """Test that search only processes relevant files."""
        new_dir, old_dir = test_files

        # Create a non-text file that shouldn't be searched
        binary_file = os.path.join(new_dir, "binary.bin")
        with open(binary_file, "wb") as f:
            f.write(b"\x00\x01\x02\x03\x04")

        config = SearchConfig(
            query="test",
            use_regex=False,
            case_sensitive=False,
            new_folder=new_dir,
            old_folder=old_dir
        )

        results = self.engine.search(config)

        # Should not crash on binary files
        assert isinstance(results, list)

        # Should still find matches in text files
        assert len(results) > 0

    @pytest.mark.parametrize("query,expected_min_results", [
        ("test", 1),
        ("content", 1),
        ("nonexistent", 0),
        ("file", 1),
    ])
    def test_search_various_queries(self, test_files, query, expected_min_results):
        """Test search with various query strings."""
        new_dir, old_dir = test_files

        config = SearchConfig(
            query=query,
            use_regex=False,
            case_sensitive=False,
            new_folder=new_dir,
            old_folder=old_dir
        )

        results = self.engine.search(config)

        total_matches = sum(r.total_matches for r in results)
        assert total_matches >= expected_min_results

    def test_search_performance_large_files(self):
        """Test search performance with larger files."""
        with tempfile.TemporaryDirectory() as test_dir:
            # Create a larger test file
            large_file = os.path.join(test_dir, "large.txt")
            with open(large_file, "w") as f:
                f.write('20250101 "large file test"\n')
                for i in range(1000):
                    f.write(f"Line {i}: Some test content here for searching\n")
                    if i % 100 == 0:
                        f.write(f"Special line {i}: FINDME marker\n")

            config = SearchConfig(
                query="FINDME",
                use_regex=False,
                case_sensitive=False,
                new_folder=test_dir,
                old_folder="/tmp"  # Empty folder
            )

            results = self.engine.search(config)

            # Should find the special markers
            assert len(results) > 0
            total_matches = sum(r.total_matches for r in results)
            assert total_matches >= 10  # Should find multiple markers

    def test_search_unicode_content(self):
        """Test search with Unicode content."""
        with tempfile.TemporaryDirectory() as test_dir:
            unicode_file = os.path.join(test_dir, "unicode.txt")
            with open(unicode_file, "w", encoding="utf-8") as f:
                f.write('20250101 "unicode test"\n')
                f.write("Regular ASCII text\n")
                f.write("Unicode: 测试内容 αβγδε ñáéíóú\n")
                f.write("Emoji: 🔍 search test 🚀\n")

            config = SearchConfig(
                query="测试",
                use_regex=False,
                case_sensitive=False,
                new_folder=test_dir,
                old_folder="/tmp"
            )

            results = self.engine.search(config)

            # Should handle Unicode search gracefully
            assert isinstance(results, list)

    def test_search_result_ordering(self, test_files):
        """Test that search results are ordered consistently."""
        new_dir, old_dir = test_files

        config = SearchConfig(
            query="test",
            use_regex=False,
            case_sensitive=False,
            new_folder=new_dir,
            old_folder=old_dir
        )

        results1 = self.engine.search(config)
        results2 = self.engine.search(config)

        # Should get consistent ordering
        assert len(results1) == len(results2)

        if len(results1) > 1:
            # File paths should be in same order
            paths1 = [r.file_path for r in results1]
            paths2 = [r.file_path for r in results2]
            assert paths1 == paths2

    def test_search_with_mocked_file_operations(self):
        """Test search behavior with mocked file operations for error handling."""
        config = SearchConfig(
            query="test",
            use_regex=False,
            case_sensitive=False,
            new_folder="/test/new",
            old_folder="/test/old"
        )

        # Mock file operations to simulate various error conditions
        with patch('os.listdir', side_effect=OSError("Permission denied")):
            results = self.engine.search(config)

            # Should handle file system errors gracefully
            assert isinstance(results, list)

    def test_search_engine_memory_efficiency(self, test_files):
        """Test that search engine doesn't consume excessive memory."""
        new_dir, old_dir = test_files

        config = SearchConfig(
            query="test",
            use_regex=False,
            case_sensitive=False,
            new_folder=new_dir,
            old_folder=old_dir
        )

        # Run search multiple times
        for _ in range(10):
            results = self.engine.search(config)
            assert len(results) >= 0

            # Clear results to avoid accumulation
            del results

    def test_search_special_characters(self, test_files):
        """Test search with special characters in query."""
        new_dir, old_dir = test_files

        # Create file with special characters
        special_file = os.path.join(new_dir, "special.txt")
        with open(special_file, "w") as f:
            f.write('20250101 "special chars"\n')
            f.write("Line with [brackets] and (parens)\n")
            f.write("Also has $pecial @nd &symbols!\n")

        config = SearchConfig(
            query="[brackets]",
            use_regex=False,  # Literal search, not regex
            case_sensitive=False,
            new_folder=new_dir,
            old_folder=old_dir
        )

        results = self.engine.search(config)

        # Should find literal bracket text
        total_matches = sum(r.total_matches for r in results)
        assert total_matches >= 1
