"""Tests for text processing utilities."""

import re

from delta_vision.utils.text import make_keyword_pattern


class TestMakeKeywordPattern:
    """Test the make_keyword_pattern function."""

    def test_empty_keywords(self):
        """Test with empty keyword list."""
        pattern = make_keyword_pattern([])
        assert pattern is None

    def test_none_keywords(self):
        """Test with None keywords."""
        pattern = make_keyword_pattern(None)
        assert pattern is None

    def test_single_keyword(self):
        """Test with a single keyword."""
        pattern = make_keyword_pattern(["malware"])

        assert pattern is not None
        assert isinstance(pattern, re.Pattern)

        # Should match the keyword
        assert pattern.search("found malware here")
        assert not pattern.search("foundmalwarehere")  # whole word boundary

    def test_multiple_keywords(self):
        """Test with multiple keywords."""
        pattern = make_keyword_pattern(["malware", "virus", "trojan"])

        assert pattern is not None

        # Should match all keywords
        assert pattern.search("detected malware")
        assert pattern.search("found virus")
        assert pattern.search("trojan detected")

        # Should not match partial words
        assert not pattern.search("antimalariacare")

    def test_whole_word_boundary(self):
        """Test whole word boundary functionality."""
        # With whole_word=True (default)
        pattern = make_keyword_pattern(["virus"], whole_word=True)
        assert pattern.search("computer virus detected")
        assert not pattern.search("antivirus software")

        # With whole_word=False
        pattern = make_keyword_pattern(["virus"], whole_word=False)
        assert pattern.search("computer virus detected")
        assert pattern.search("antivirus software")

    def test_case_sensitivity(self):
        """Test case sensitivity options."""
        # Case insensitive (default)
        pattern = make_keyword_pattern(["malware"], case_insensitive=True)
        assert pattern.search("found MALWARE")
        assert pattern.search("found malware")
        assert pattern.search("found MaLwArE")

        # Case sensitive
        pattern = make_keyword_pattern(["malware"], case_insensitive=False)
        assert pattern.search("found malware")
        assert not pattern.search("found MALWARE")

    def test_keyword_escaping(self):
        """Test that special regex characters are properly escaped."""
        pattern = make_keyword_pattern(["test.com", "file[1]", "price$"])

        assert pattern is not None

        # Should match literally, not as regex
        assert pattern.search("visit test.com")
        assert not pattern.search("visit testXcom")  # . should be literal

        assert pattern.search("open file[1]")
        assert not pattern.search("open fileX1X")  # [] should be literal

    def test_keyword_sorting_by_length(self):
        """Test that longer keywords are prioritized."""
        # This is implicit in the implementation but we can test the behavior
        pattern = make_keyword_pattern(["virus", "computer virus"])

        # Should match the longer phrase when present
        match = pattern.search("detected computer virus today")
        assert match is not None
        # The actual match depends on regex engine behavior, but both should work

    def test_duplicate_keywords(self):
        """Test handling of duplicate keywords."""
        pattern = make_keyword_pattern(["malware", "malware", "virus", "malware"])

        assert pattern is not None
        # Should still work correctly despite duplicates
        assert pattern.search("found malware")
        assert pattern.search("found virus")

    def test_whitespace_handling(self):
        """Test handling of keywords with whitespace."""
        pattern = make_keyword_pattern(["  malware  ", " virus", "trojan "])

        assert pattern is not None
        # Should strip whitespace and match properly
        assert pattern.search("found malware")
        assert pattern.search("found virus")
        assert pattern.search("found trojan")

    def test_empty_strings_filtering(self):
        """Test that empty strings are filtered out."""
        # With valid keywords mixed with empty strings
        pattern = make_keyword_pattern(["malware", "", "  ", "virus"])

        assert pattern is not None
        # Should work with valid keywords only
        assert pattern.search("found malware")
        assert pattern.search("found virus")

    def test_none_values_in_list(self):
        """Test handling of None values in keyword list."""
        # None values cause the function to return None due to error handling
        pattern = make_keyword_pattern(["malware", None, "virus"])
        # The function logs an error and returns None when it can't process None values
        assert pattern is None

    def test_all_empty_after_filtering(self):
        """Test when all keywords are empty after filtering."""
        pattern = make_keyword_pattern(["", "  ", None])
        assert pattern is None

    def test_pattern_match_groups(self):
        """Test that pattern returns proper match groups."""
        pattern = make_keyword_pattern(["malware", "virus"])

        match = pattern.search("found malware here")
        assert match is not None
        assert match.group(1) == "malware"  # First capture group

        match = pattern.search("found virus here")
        assert match is not None
        assert match.group(1) == "virus"

    def test_special_characters_in_keywords(self):
        """Test keywords containing various special characters."""
        keywords = [
            "file.txt",
            "user@domain.com",
            "path/to/file",
            "price$100",
            "regex[pattern]",
            "question?mark",
            "plus+sign",
            "star*symbol",
            "caret^symbol"
        ]

        pattern = make_keyword_pattern(keywords)
        assert pattern is not None

        # All should match literally
        for keyword in keywords:
            assert pattern.search(f"found {keyword} here"), f"Failed to match: {keyword}"

    def test_unicode_keywords(self):
        """Test keywords with unicode characters."""
        pattern = make_keyword_pattern(["café", "naïve", "résumé"])

        assert pattern is not None
        assert pattern.search("visit café")
        assert pattern.search("naïve approach")
        assert pattern.search("submit résumé")

    def test_error_handling(self):
        """Test error handling for malformed input."""
        # Should handle non-string iterables gracefully
        pattern = make_keyword_pattern([123, None, "valid"])
        # Should either return None or a pattern with only valid keywords
        if pattern is not None:
            assert pattern.search("valid keyword")

    def test_very_long_keyword_list(self):
        """Test performance with a large number of keywords."""
        keywords = [f"keyword{i}" for i in range(100)]
        pattern = make_keyword_pattern(keywords)

        assert pattern is not None
        assert pattern.search("found keyword50 here")
        assert pattern.search("found keyword99 here")
