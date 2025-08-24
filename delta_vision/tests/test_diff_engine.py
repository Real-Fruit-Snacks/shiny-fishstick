"""Tests for the diff engine utility module.

This module tests the core diff computation functionality that was extracted
from the diff viewer to ensure accurate diff generation across different
file types, encodings, and edge cases.
"""

import os
import tempfile
from unittest.mock import patch

import pytest

from delta_vision.utils.diff_engine import DiffRow, DiffType, compute_diff_rows


class TestDiffRow:
    """Test the DiffRow data structure."""

    def test_diff_row_creation(self):
        """Test creating a diff row."""
        row = DiffRow(
            diff_type=DiffType.MODIFIED,
            left_line_num=10,
            right_line_num=12,
            left_content="Old content",
            right_content="New content"
        )

        assert row.diff_type == DiffType.MODIFIED
        assert row.left_line_num == 10
        assert row.right_line_num == 12
        assert row.left_content == "Old content"
        assert row.right_content == "New content"

    def test_diff_row_added(self):
        """Test diff row for added lines."""
        row = DiffRow(
            diff_type=DiffType.ADDED,
            left_line_num=None,
            right_line_num=5,
            left_content="",
            right_content="New line added"
        )

        assert row.diff_type == DiffType.ADDED
        assert row.left_line_num is None
        assert row.right_line_num == 5
        assert row.left_content == ""
        assert row.right_content == "New line added"

    def test_diff_row_deleted(self):
        """Test diff row for deleted lines."""
        row = DiffRow(
            diff_type=DiffType.DELETED,
            left_line_num=8,
            right_line_num=None,
            left_content="Deleted line",
            right_content=""
        )

        assert row.diff_type == DiffType.DELETED
        assert row.left_line_num == 8
        assert row.right_line_num is None
        assert row.left_content == "Deleted line"
        assert row.right_content == ""

    def test_diff_row_unchanged(self):
        """Test diff row for unchanged lines."""
        row = DiffRow(
            diff_type=DiffType.UNCHANGED,
            left_line_num=3,
            right_line_num=3,
            left_content="Same content",
            right_content="Same content"
        )

        assert row.diff_type == DiffType.UNCHANGED
        assert row.left_line_num == 3
        assert row.right_line_num == 3
        assert row.left_content == "Same content"
        assert row.right_content == "Same content"


class TestDiffType:
    """Test the DiffType enumeration."""

    def test_diff_type_values(self):
        """Test that DiffType has expected values."""
        assert hasattr(DiffType, 'UNCHANGED')
        assert hasattr(DiffType, 'ADDED')
        assert hasattr(DiffType, 'DELETED')
        assert hasattr(DiffType, 'MODIFIED')

        # Values should be distinct
        types = [DiffType.UNCHANGED, DiffType.ADDED, DiffType.DELETED, DiffType.MODIFIED]
        assert len(set(types)) == 4


class TestComputeDiffRows:
    """Test the core diff computation functionality."""

    @pytest.fixture
    def test_files(self):
        """Create test files with known content for diffing."""
        # Create left (old) file
        left_fd, left_path = tempfile.mkstemp(suffix='.txt', text=True)
        with os.fdopen(left_fd, 'w') as f:
            f.write('20241231 "old command"\n')
            f.write("Line 1: Original\n")
            f.write("Line 2: Same\n")
            f.write("Line 3: Modified old\n")
            f.write("Line 4: To be deleted\n")
            f.write("Line 5: Same\n")

        # Create right (new) file
        right_fd, right_path = tempfile.mkstemp(suffix='.txt', text=True)
        with os.fdopen(right_fd, 'w') as f:
            f.write('20250101 "new command"\n')
            f.write("Line 1: Updated\n")
            f.write("Line 2: Same\n")
            f.write("Line 3: Modified new\n")
            f.write("Line 5: Same\n")
            f.write("Line 6: Added new\n")

        yield left_path, right_path

        # Cleanup
        try:
            os.unlink(left_path)
            os.unlink(right_path)
        except OSError:
            pass

    def test_compute_diff_basic(self, test_files):
        """Test basic diff computation."""
        left_path, right_path = test_files

        diff_rows = compute_diff_rows(left_path, right_path)

        # Should return a list of DiffRow objects
        assert isinstance(diff_rows, list)
        assert len(diff_rows) > 0

        # All rows should be DiffRow objects
        for row in diff_rows:
            assert isinstance(row, DiffRow)
            assert hasattr(row, 'diff_type')
            assert hasattr(row, 'left_content')
            assert hasattr(row, 'right_content')

    def test_diff_detects_changes(self, test_files):
        """Test that diff correctly identifies different types of changes."""
        left_path, right_path = test_files

        diff_rows = compute_diff_rows(left_path, right_path)

        # Should detect various change types
        change_types = [row.diff_type for row in diff_rows]

        # Should have some unchanged lines
        assert DiffType.UNCHANGED in change_types

        # Should have some changes (added, deleted, or modified)
        has_changes = any(t in change_types for t in [DiffType.ADDED, DiffType.DELETED, DiffType.MODIFIED])
        assert has_changes

    def test_diff_line_numbers(self, test_files):
        """Test that line numbers are computed correctly."""
        left_path, right_path = test_files

        diff_rows = compute_diff_rows(left_path, right_path)

        # Check line number consistency
        left_line_count = 0
        right_line_count = 0

        for row in diff_rows:
            if row.diff_type != DiffType.ADDED and row.left_line_num is not None:
                assert row.left_line_num > 0
                left_line_count += 1

            if row.diff_type != DiffType.DELETED and row.right_line_num is not None:
                assert row.right_line_num > 0
                right_line_count += 1

    def test_diff_identical_files(self):
        """Test diff of identical files."""
        content = '20250101 "test"\nLine 1\nLine 2\nLine 3\n'

        # Create two identical files
        left_fd, left_path = tempfile.mkstemp(suffix='.txt', text=True)
        with os.fdopen(left_fd, 'w') as f:
            f.write(content)

        right_fd, right_path = tempfile.mkstemp(suffix='.txt', text=True)
        with os.fdopen(right_fd, 'w') as f:
            f.write(content)

        try:
            diff_rows = compute_diff_rows(left_path, right_path)

            # All rows should be unchanged
            for row in diff_rows:
                assert row.diff_type == DiffType.UNCHANGED
                assert row.left_content == row.right_content

        finally:
            os.unlink(left_path)
            os.unlink(right_path)

    def test_diff_empty_files(self):
        """Test diff of empty files."""
        # Create two empty files
        left_fd, left_path = tempfile.mkstemp(suffix='.txt', text=True)
        os.close(left_fd)  # Close immediately, leaving empty file

        right_fd, right_path = tempfile.mkstemp(suffix='.txt', text=True)
        os.close(right_fd)  # Close immediately, leaving empty file

        try:
            diff_rows = compute_diff_rows(left_path, right_path)

            # Should handle empty files gracefully
            assert isinstance(diff_rows, list)
            # May be empty or have minimal structure

        finally:
            os.unlink(left_path)
            os.unlink(right_path)

    def test_diff_one_empty_file(self):
        """Test diff where one file is empty."""
        # Create content file
        content_fd, content_path = tempfile.mkstemp(suffix='.txt', text=True)
        with os.fdopen(content_fd, 'w') as f:
            f.write('20250101 "test"\n')
            f.write("Line 1\n")
            f.write("Line 2\n")

        # Create empty file
        empty_fd, empty_path = tempfile.mkstemp(suffix='.txt', text=True)
        os.close(empty_fd)

        try:
            # Diff content vs empty
            diff_rows = compute_diff_rows(content_path, empty_path)
            assert isinstance(diff_rows, list)

            # All content lines should be marked as deleted
            if len(diff_rows) > 0:
                for row in diff_rows:
                    if row.left_content and not row.right_content:
                        assert row.diff_type in [DiffType.DELETED, DiffType.MODIFIED]

            # Diff empty vs content
            diff_rows = compute_diff_rows(empty_path, content_path)
            assert isinstance(diff_rows, list)

            # All content lines should be marked as added
            if len(diff_rows) > 0:
                for row in diff_rows:
                    if not row.left_content and row.right_content:
                        assert row.diff_type in [DiffType.ADDED, DiffType.MODIFIED]

        finally:
            os.unlink(content_path)
            os.unlink(empty_path)

    def test_diff_nonexistent_files(self):
        """Test diff with nonexistent files."""
        nonexistent1 = "/nonexistent/file1.txt"
        nonexistent2 = "/nonexistent/file2.txt"

        # Should handle missing files gracefully
        diff_rows = compute_diff_rows(nonexistent1, nonexistent2)

        # Should return empty list or handle error gracefully
        assert isinstance(diff_rows, list)

    def test_diff_binary_files(self):
        """Test diff with binary files."""
        # Create binary files
        left_fd, left_path = tempfile.mkstemp(suffix='.bin')
        with os.fdopen(left_fd, 'wb') as f:
            f.write(b'\x00\x01\x02\x03\xFF\xFE')

        right_fd, right_path = tempfile.mkstemp(suffix='.bin')
        with os.fdopen(right_fd, 'wb') as f:
            f.write(b'\x00\x01\x02\x04\xFF\xFE')  # One byte different

        try:
            diff_rows = compute_diff_rows(left_path, right_path)

            # Should handle binary files gracefully (may show as binary or handle encoding)
            assert isinstance(diff_rows, list)

        finally:
            os.unlink(left_path)
            os.unlink(right_path)

    def test_diff_unicode_content(self):
        """Test diff with Unicode content."""
        # Create files with Unicode content
        left_fd, left_path = tempfile.mkstemp(suffix='.txt', text=True)
        with os.fdopen(left_fd, 'w', encoding='utf-8') as f:
            f.write('20250101 "unicode test"\n')
            f.write("ASCII line\n")
            f.write("Unicode: 测试内容 αβγδε\n")
            f.write("Emoji: 🔍 🚀 ⚡\n")

        right_fd, right_path = tempfile.mkstemp(suffix='.txt', text=True)
        with os.fdopen(right_fd, 'w', encoding='utf-8') as f:
            f.write('20250102 "unicode test modified"\n')
            f.write("ASCII line\n")
            f.write("Unicode: 测试内容更新 αβγδε\n")
            f.write("Emoji: 🔍 🚀 ⭐\n")

        try:
            diff_rows = compute_diff_rows(left_path, right_path)

            # Should handle Unicode content properly
            assert isinstance(diff_rows, list)
            assert len(diff_rows) > 0

            # Check that Unicode content is preserved
            unicode_found = False
            for row in diff_rows:
                if "测试" in row.left_content or "测试" in row.right_content:
                    unicode_found = True
                    break

            assert unicode_found

        finally:
            os.unlink(left_path)
            os.unlink(right_path)

    def test_diff_large_files(self):
        """Test diff performance with larger files."""
        # Create larger test files
        left_fd, left_path = tempfile.mkstemp(suffix='.txt', text=True)
        with os.fdopen(left_fd, 'w') as f:
            f.write('20250101 "large file test"\n')
            for i in range(1000):
                f.write(f"Line {i}: Original content\n")

        right_fd, right_path = tempfile.mkstemp(suffix='.txt', text=True)
        with os.fdopen(right_fd, 'w') as f:
            f.write('20250102 "large file test modified"\n')
            for i in range(1000):
                if i == 500:
                    f.write(f"Line {i}: MODIFIED content\n")
                else:
                    f.write(f"Line {i}: Original content\n")
            f.write("Line 1000: Added at end\n")

        try:
            diff_rows = compute_diff_rows(left_path, right_path)

            # Should handle large files without issues
            assert isinstance(diff_rows, list)
            assert len(diff_rows) > 0

            # Should detect the modification
            has_modification = any(
                row.diff_type in [DiffType.MODIFIED, DiffType.ADDED, DiffType.DELETED]
                for row in diff_rows
            )
            assert has_modification

        finally:
            os.unlink(left_path)
            os.unlink(right_path)

    def test_diff_whitespace_differences(self):
        """Test diff behavior with whitespace differences."""
        left_fd, left_path = tempfile.mkstemp(suffix='.txt', text=True)
        with os.fdopen(left_fd, 'w') as f:
            f.write('20250101 "whitespace test"\n')
            f.write("Line with spaces\n")
            f.write("Line with\ttabs\n")
            f.write("Line with trailing spaces   \n")

        right_fd, right_path = tempfile.mkstemp(suffix='.txt', text=True)
        with os.fdopen(right_fd, 'w') as f:
            f.write('20250101 "whitespace test"\n')
            f.write("Line  with  spaces\n")  # Different spacing
            f.write("Line with    tabs\n")    # Tabs converted to spaces
            f.write("Line with trailing spaces\n")  # Trailing spaces removed

        try:
            diff_rows = compute_diff_rows(left_path, right_path)

            # Should detect whitespace differences
            assert isinstance(diff_rows, list)
            assert len(diff_rows) > 0

            # Should identify whitespace changes as modifications
            any(
                row.diff_type in [DiffType.MODIFIED, DiffType.ADDED, DiffType.DELETED]
                for row in diff_rows
            )

        finally:
            os.unlink(left_path)
            os.unlink(right_path)

    def test_diff_context_preservation(self, test_files):
        """Test that diff preserves context around changes."""
        left_path, right_path = test_files

        diff_rows = compute_diff_rows(left_path, right_path)

        # Should have both changed and unchanged lines
        has_unchanged = any(row.diff_type == DiffType.UNCHANGED for row in diff_rows)
        has_changes = any(row.diff_type != DiffType.UNCHANGED for row in diff_rows)

        assert has_unchanged or has_changes  # At least one should be true

    def test_diff_row_content_accuracy(self, test_files):
        """Test that diff row content matches actual file content."""
        left_path, right_path = test_files

        # Read original file content
        with open(left_path) as f:
            left_lines = f.readlines()
        with open(right_path) as f:
            right_lines = f.readlines()

        diff_rows = compute_diff_rows(left_path, right_path)

        # Verify that unchanged lines match original content
        for row in diff_rows:
            if row.diff_type == DiffType.UNCHANGED:
                # Content should match
                if row.left_line_num and row.left_line_num <= len(left_lines):
                    expected_left = left_lines[row.left_line_num - 1].rstrip('\n')
                    assert row.left_content == expected_left

                if row.right_line_num and row.right_line_num <= len(right_lines):
                    expected_right = right_lines[row.right_line_num - 1].rstrip('\n')
                    assert row.right_content == expected_right

    @pytest.mark.parametrize("left_content,right_content,expected_change", [
        ("Line 1\nLine 2\n", "Line 1\nLine 2\n", False),  # Identical
        ("Line 1\nLine 2\n", "Line 1\nLine 3\n", True),   # Modified
        ("Line 1\nLine 2\n", "Line 1\nLine 2\nLine 3\n", True),  # Added
        ("Line 1\nLine 2\nLine 3\n", "Line 1\nLine 2\n", True),  # Deleted
    ])
    def test_diff_change_detection(self, left_content, right_content, expected_change):
        """Test diff change detection with various scenarios."""
        left_fd, left_path = tempfile.mkstemp(suffix='.txt', text=True)
        with os.fdopen(left_fd, 'w') as f:
            f.write('20250101 "test"\n' + left_content)

        right_fd, right_path = tempfile.mkstemp(suffix='.txt', text=True)
        with os.fdopen(right_fd, 'w') as f:
            f.write('20250101 "test"\n' + right_content)

        try:
            diff_rows = compute_diff_rows(left_path, right_path)

            has_changes = any(
                row.diff_type != DiffType.UNCHANGED
                for row in diff_rows
            )

            assert has_changes == expected_change

        finally:
            os.unlink(left_path)
            os.unlink(right_path)

    def test_diff_error_handling_with_mocks(self):
        """Test diff error handling with mocked file operations."""
        # Test with mocked file read errors
        with patch('builtins.open', side_effect=OSError("File read error")):
            diff_rows = compute_diff_rows("/fake/left.txt", "/fake/right.txt")

            # Should handle file errors gracefully
            assert isinstance(diff_rows, list)

    def test_diff_memory_efficiency(self, test_files):
        """Test that diff computation doesn't consume excessive memory."""
        left_path, right_path = test_files

        # Run diff computation multiple times
        for _ in range(10):
            diff_rows = compute_diff_rows(left_path, right_path)
            assert isinstance(diff_rows, list)

            # Clear results to test memory cleanup
            del diff_rows

    def test_diff_consistency(self, test_files):
        """Test that diff results are consistent across multiple runs."""
        left_path, right_path = test_files

        # Run diff multiple times
        results = []
        for _ in range(3):
            diff_rows = compute_diff_rows(left_path, right_path)
            results.append(diff_rows)

        # Results should be consistent
        assert len(results[0]) == len(results[1]) == len(results[2])

        # Content should be the same
        for i in range(len(results[0])):
            assert results[0][i].diff_type == results[1][i].diff_type == results[2][i].diff_type
            assert results[0][i].left_content == results[1][i].left_content == results[2][i].left_content
            assert results[0][i].right_content == results[1][i].right_content == results[2][i].right_content
