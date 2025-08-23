"""Keyword highlighting utilities for Delta Vision.

This module provides centralized keyword highlighting functionality that can be used
across different screens for consistent text highlighting behavior.
"""

from __future__ import annotations

import re

from rich.markup import escape

from .logger import log
from .text import make_keyword_pattern


class KeywordHighlighter:
    """Centralized keyword highlighting with caching and consistent styling."""

    def __init__(self):
        """Initialize the highlighter with empty cache."""
        self._cached_pattern = None
        self._cached_lookup = None
        self._last_keywords_dict = None

    def get_pattern_and_lookup(
        self, keywords_dict: dict | None
    ) -> tuple[re.Pattern | None, dict[str, tuple[str, str]]]:
        """Get compiled keyword pattern and lookup dict, using cache when possible.

        Args:
            keywords_dict: Dictionary mapping {category: (color, [keywords])}

        Returns:
            Tuple of (compiled_pattern, keyword_lookup) where keyword_lookup maps
            keyword -> (color, category)
        """
        # Check if we can reuse cached pattern
        if keywords_dict == self._last_keywords_dict and self._cached_pattern is not None:
            return self._cached_pattern, self._cached_lookup

        # Build new pattern and lookup
        keyword_lookup: dict[str, tuple[str, str]] = {}
        if keywords_dict:
            for cat, (color, words) in keywords_dict.items():
                for word in words:
                    if not word:
                        continue
                    keyword_lookup[word.lower()] = (color, cat)

        pattern = (
            make_keyword_pattern(keyword_lookup.keys(), whole_word=True, case_insensitive=True)
            if keyword_lookup
            else None
        )

        # Cache for next time
        self._cached_pattern = pattern
        self._cached_lookup = keyword_lookup
        self._last_keywords_dict = keywords_dict

        return pattern, keyword_lookup

    def highlight_line(
        self,
        line: str,
        pattern: re.Pattern | None,
        keyword_lookup: dict[str, tuple[str, str]],
        underline: bool = True,
    ) -> str:
        """Apply keyword highlighting to a line of text.

        Args:
            line: The text line to highlight
            pattern: Compiled regex pattern for finding keywords
            keyword_lookup: Mapping of keyword -> (color, category)
            underline: Whether to add underline markup to highlights

        Returns:
            Rich markup string with keywords highlighted
        """
        if not pattern:
            return escape(line)

        out = []
        last = 0
        for match in pattern.finditer(line):
            # Add text before the match
            out.append(escape(line[last : match.start()]))

            # Add highlighted keyword
            matched = match.group(0)
            color = keyword_lookup.get(matched.lower(), ("yellow", ""))[0].lower()

            if underline:
                out.append(f"[u][{color}]{escape(matched)}[/{color}][/u]")
            else:
                out.append(f"[{color}]{escape(matched)}[/{color}]")

            last = match.end()

        # Add remaining text
        out.append(escape(line[last:]))
        return "".join(out)

    def highlight_with_color_lookup(
        self, line: str, keywords: list[str], color_lookup: dict[str, str], case_sensitive: bool = False
    ) -> str:
        """Apply keyword highlighting using a simple color lookup.

        Args:
            line: The text line to highlight
            keywords: List of keywords to highlight (sorted by length, longest first)
            color_lookup: Mapping of keyword -> color
            case_sensitive: Whether matching should be case sensitive

        Returns:
            Rich markup string with keywords highlighted
        """
        if not keywords or not color_lookup:
            return escape(line)

        result = line

        # Process keywords from longest to shortest to avoid partial matches
        for keyword in keywords:
            color = color_lookup.get(keyword)
            if not color:
                continue

            # Create pattern for whole word matching
            flags = 0 if case_sensitive else re.IGNORECASE
            pattern = rf'(?<!\w)({re.escape(keyword)})(?!\w)'
            replacement = rf'[u][{color.lower()}]\1[/{color.lower()}][/u]'

            try:
                result = re.sub(pattern, replacement, result, flags=flags)
            except re.error as e:
                log.warning(f"Failed to highlight keyword '{keyword}': {e}")
                continue

        return result

    def highlight_with_pattern(self, text: str, pattern: re.Pattern, color: str, underline: bool = False) -> str:
        """Apply highlighting using a pre-compiled pattern and single color.

        Args:
            text: The text to highlight
            pattern: Pre-compiled regex pattern
            color: Color to use for highlights
            underline: Whether to add underline markup

        Returns:
            Rich markup string with pattern matches highlighted
        """
        if not pattern:
            return escape(text)

        try:
            if underline:
                replacement = rf'[u][{color}]\1[/{color}][/u]'
            else:
                replacement = rf'[{color}]\1[/{color}]'

            # Escape the text first, then apply highlighting
            safe_text = escape(text)
            return pattern.sub(replacement, safe_text)
        except (re.error, AttributeError) as e:
            log.warning(f"Failed to apply pattern highlighting: {e}")
            return escape(text)

    def clear_cache(self):
        """Clear the pattern cache to force regeneration."""
        self._cached_pattern = None
        self._cached_lookup = None
        self._last_keywords_dict = None


# Global instance for convenience
highlighter = KeywordHighlighter()


def highlight_keywords(line: str, keywords_dict: dict | None, underline: bool = True) -> str:
    """Convenience function for highlighting keywords in a line.

    Args:
        line: The text line to highlight
        keywords_dict: Dictionary mapping {category: (color, [keywords])}
        underline: Whether to add underline markup

    Returns:
        Rich markup string with keywords highlighted
    """
    pattern, lookup = highlighter.get_pattern_and_lookup(keywords_dict)
    return highlighter.highlight_line(line, pattern, lookup, underline)
