"""Tests for the keyword highlighter utility."""

import re

from delta_vision.utils.keyword_highlighter import KeywordHighlighter, highlight_keywords


class TestKeywordHighlighter:
    """Test the KeywordHighlighter class functionality."""

    def test_get_pattern_and_lookup_empty(self):
        """Test pattern generation with empty keywords dict."""
        highlighter = KeywordHighlighter()
        pattern, lookup = highlighter.get_pattern_and_lookup(None)

        assert pattern is None
        assert lookup == {}

    def test_get_pattern_and_lookup_basic(self):
        """Test basic pattern generation and lookup."""
        highlighter = KeywordHighlighter()
        keywords_dict = {
            "Security": ("red", ["malware", "virus"]),
            "Network": ("blue", ["tcp", "udp"])
        }

        pattern, lookup = highlighter.get_pattern_and_lookup(keywords_dict)

        assert pattern is not None
        assert isinstance(pattern, re.Pattern)
        assert lookup == {
            "malware": ("red", "Security"),
            "virus": ("red", "Security"),
            "tcp": ("blue", "Network"),
            "udp": ("blue", "Network")
        }

    def test_get_pattern_caching(self):
        """Test that patterns are cached properly."""
        highlighter = KeywordHighlighter()
        keywords_dict = {
            "Security": ("red", ["malware", "virus"])
        }

        pattern1, lookup1 = highlighter.get_pattern_and_lookup(keywords_dict)
        pattern2, lookup2 = highlighter.get_pattern_and_lookup(keywords_dict)

        # Should return the same objects due to caching
        assert pattern1 is pattern2
        assert lookup1 is lookup2

    def test_get_pattern_cache_invalidation(self):
        """Test that cache is invalidated when keywords change."""
        highlighter = KeywordHighlighter()
        keywords_dict1 = {
            "Security": ("red", ["malware"])
        }
        keywords_dict2 = {
            "Security": ("red", ["virus"])
        }

        pattern1, lookup1 = highlighter.get_pattern_and_lookup(keywords_dict1)
        pattern2, lookup2 = highlighter.get_pattern_and_lookup(keywords_dict2)

        # Should be different objects after cache invalidation
        assert pattern1 is not pattern2
        assert lookup1 != lookup2
        assert "malware" in lookup1
        assert "virus" in lookup2

    def test_highlight_line_no_pattern(self):
        """Test highlighting with no pattern."""
        highlighter = KeywordHighlighter()
        result = highlighter.highlight_line("test line", None, {})
        assert result == "test line"  # Should be escaped but plain

    def test_highlight_line_basic(self):
        """Test basic line highlighting."""
        highlighter = KeywordHighlighter()
        keywords_dict = {
            "Security": ("red", ["malware"])
        }
        pattern, lookup = highlighter.get_pattern_and_lookup(keywords_dict)

        result = highlighter.highlight_line("Found malware in file", pattern, lookup)

        assert "[u][red]malware[/red][/u]" in result
        assert "Found" in result
        assert "in file" in result

    def test_highlight_line_no_underline(self):
        """Test line highlighting without underline."""
        highlighter = KeywordHighlighter()
        keywords_dict = {
            "Security": ("red", ["malware"])
        }
        pattern, lookup = highlighter.get_pattern_and_lookup(keywords_dict)

        result = highlighter.highlight_line("Found malware in file", pattern, lookup, underline=False)

        assert "[red]malware[/red]" in result
        assert "[u]" not in result
        assert "[/u]" not in result

    def test_highlight_line_case_insensitive(self):
        """Test case insensitive highlighting."""
        highlighter = KeywordHighlighter()
        keywords_dict = {
            "Security": ("red", ["malware"])
        }
        pattern, lookup = highlighter.get_pattern_and_lookup(keywords_dict)

        result = highlighter.highlight_line("Found MALWARE in file", pattern, lookup)

        assert "[u][red]MALWARE[/red][/u]" in result

    def test_highlight_line_multiple_matches(self):
        """Test highlighting multiple keywords in one line."""
        highlighter = KeywordHighlighter()
        keywords_dict = {
            "Security": ("red", ["malware", "virus"]),
            "Network": ("blue", ["tcp"])
        }
        pattern, lookup = highlighter.get_pattern_and_lookup(keywords_dict)

        result = highlighter.highlight_line("malware uses tcp and virus", pattern, lookup)

        assert "[u][red]malware[/red][/u]" in result
        assert "[u][red]virus[/red][/u]" in result
        assert "[u][blue]tcp[/blue][/u]" in result

    def test_highlight_with_color_lookup_basic(self):
        """Test color lookup highlighting method."""
        highlighter = KeywordHighlighter()
        keywords = ["malware", "virus"]
        color_lookup = {"malware": "red", "virus": "orange"}

        result = highlighter.highlight_with_color_lookup(
            "Found malware and virus", keywords, color_lookup
        )

        assert "[u][red]malware[/red][/u]" in result
        assert "[u][orange]virus[/orange][/u]" in result

    def test_highlight_with_color_lookup_empty(self):
        """Test color lookup with empty inputs."""
        highlighter = KeywordHighlighter()

        result = highlighter.highlight_with_color_lookup("test", [], {})
        assert result == "test"

        result = highlighter.highlight_with_color_lookup("test", ["word"], {})
        assert result == "test"

    def test_highlight_with_color_lookup_case_sensitivity(self):
        """Test case sensitivity option in color lookup."""
        highlighter = KeywordHighlighter()
        keywords = ["malware"]
        color_lookup = {"malware": "red"}

        # Case insensitive (default)
        result = highlighter.highlight_with_color_lookup(
            "Found MALWARE", keywords, color_lookup, case_sensitive=False
        )
        assert "[u][red]MALWARE[/red][/u]" in result

        # Case sensitive
        result = highlighter.highlight_with_color_lookup(
            "Found MALWARE", keywords, color_lookup, case_sensitive=True
        )
        assert "[u][red]" not in result  # Should not highlight

    def test_highlight_with_pattern_basic(self):
        """Test pattern-based highlighting."""
        highlighter = KeywordHighlighter()
        pattern = re.compile(r"(error|warning)", re.IGNORECASE)

        result = highlighter.highlight_with_pattern("Found error in log", pattern, "red")

        # Note: this method expects the pattern to have a capture group
        assert "error" in result

    def test_highlight_with_pattern_underline(self):
        """Test pattern-based highlighting with underline option."""
        highlighter = KeywordHighlighter()
        pattern = re.compile(r"(error)")

        result = highlighter.highlight_with_pattern("Found error", pattern, "red", underline=True)
        assert "[u][red]" in result

        result = highlighter.highlight_with_pattern("Found error", pattern, "red", underline=False)
        assert "[u]" not in result

    def test_highlight_with_pattern_no_pattern(self):
        """Test pattern highlighting with None pattern."""
        highlighter = KeywordHighlighter()

        result = highlighter.highlight_with_pattern("test", None, "red")
        assert result == "test"

    def test_clear_cache(self):
        """Test cache clearing functionality."""
        highlighter = KeywordHighlighter()
        keywords_dict = {
            "Security": ("red", ["malware"])
        }

        # Populate cache
        pattern1, lookup1 = highlighter.get_pattern_and_lookup(keywords_dict)
        assert pattern1 is not None
        assert highlighter._cached_pattern is not None
        assert highlighter._cached_lookup is not None

        # Clear cache
        highlighter.clear_cache()

        # Cache should be cleared
        assert highlighter._cached_pattern is None
        assert highlighter._cached_lookup is None
        assert highlighter._last_keywords_dict is None

        # Get pattern again - should be regenerated
        pattern2, lookup2 = highlighter.get_pattern_and_lookup(keywords_dict)
        assert pattern2 is not None
        # Cache should be populated again
        assert highlighter._cached_pattern is not None
        assert highlighter._cached_lookup is not None


class TestHighlightKeywordsFunction:
    """Test the convenience function."""

    def test_highlight_keywords_convenience(self):
        """Test the convenience function works correctly."""
        keywords_dict = {
            "Security": ("red", ["malware"])
        }

        result = highlight_keywords("Found malware", keywords_dict)

        assert "[u][red]malware[/red][/u]" in result
        assert "Found" in result

    def test_highlight_keywords_no_underline(self):
        """Test convenience function without underline."""
        keywords_dict = {
            "Security": ("red", ["malware"])
        }

        result = highlight_keywords("Found malware", keywords_dict, underline=False)

        assert "[red]malware[/red]" in result
        assert "[u]" not in result

    def test_highlight_keywords_empty(self):
        """Test convenience function with empty keywords."""
        result = highlight_keywords("test line", None)
        assert result == "test line"

        result = highlight_keywords("test line", {})
        assert result == "test line"
