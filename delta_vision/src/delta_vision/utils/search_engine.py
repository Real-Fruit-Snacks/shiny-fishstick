"""Search engine utility for Delta Vision.

This module provides the core search functionality separated from UI concerns.
It handles file scanning, pattern matching, and text processing for search operations.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from time import perf_counter
from typing import Iterator

from .io import read_text
from .logger import log


@dataclass
class SearchMatch:
    """Represents a single search match result."""

    file_path: str
    line_no: int
    line: str
    cmd: str | None = None
    is_error: bool = False


@dataclass
class SearchConfig:
    """Configuration for search operations."""

    max_files: int = 5000
    max_preview_chars: int = 200
    case_sensitive: bool = False


class SearchEngine:
    """Core search engine for file content searching."""

    def __init__(self, config: SearchConfig | None = None):
        """Initialize the search engine with optional configuration.

        Args:
            config: Search configuration object. If None, uses default SearchConfig.
        """
        self.config = config or SearchConfig()

    def search_folders(
        self, query: str, folders: list[str], regex_mode: bool = False
    ) -> tuple[list[SearchMatch], int, float]:
        """Search for query in the specified folders.

        Args:
            query: Search query string
            folders: List of folder paths to search
            regex_mode: Whether to treat query as regex

        Returns:
            Tuple of (matches, files_scanned, elapsed_time)
        """
        pattern = self._compile_pattern(query, regex_mode)
        if pattern is None:
            return [], 0, 0.0

        matches = []
        files_scanned = 0
        start_time = perf_counter()

        for folder in folders:
            folder_matches, folder_files = self._scan_folder(folder, pattern)
            matches.extend(folder_matches)
            files_scanned += folder_files

            if files_scanned > self.config.max_files:
                break

        elapsed = perf_counter() - start_time
        matches.sort(key=lambda m: (m.file_path.lower(), m.line_no))
        return matches, files_scanned, elapsed

    def _compile_pattern(self, query: str, regex_mode: bool) -> re.Pattern | None:
        """Compile search pattern based on mode."""
        try:
            flags = 0 if self.config.case_sensitive else re.IGNORECASE
            if regex_mode:
                return re.compile(query, flags)
            else:
                return re.compile(re.escape(query), flags)
        except re.error as e:
            log(f"Failed to compile search pattern: {e}")
            return None

    def _scan_folder(self, folder: str, pattern: re.Pattern) -> tuple[list[SearchMatch], int]:
        """Scan a single folder for matches."""
        matches = []
        files_scanned = 0

        try:
            for file_path in self._walk_files(folder):
                if files_scanned >= self.config.max_files:
                    break

                files_scanned += 1
                file_matches = self._scan_file(file_path, pattern)
                matches.extend(file_matches)

        except Exception as e:
            matches.append(SearchMatch(folder, 0, f"[Error reading folder: {e}]", None, True))

        return matches, files_scanned

    def _walk_files(self, folder: str) -> Iterator[str]:
        """Walk through all files in a folder."""
        for root, _dirs, files in os.walk(folder):
            for name in files:
                file_path = os.path.join(root, name)
                if os.path.isfile(file_path):
                    yield file_path

    def _scan_file(self, file_path: str, pattern: re.Pattern) -> list[SearchMatch]:
        """Scan a single file for pattern matches."""
        matches = []
        text, _enc = read_text(file_path)

        if not text:
            return matches

        cmd_str = self._extract_command(file_path, text)

        for line_no, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                preview = self._create_preview(line, pattern)
                matches.append(SearchMatch(file_path, line_no, preview, cmd_str))

        return matches

    def _extract_command(self, file_path: str, text: str) -> str | None:
        """Extract command string from first line of file."""
        try:
            if text:
                first_line = text.splitlines()[0]
                # Look for command in quotes
                match = re.search(r'"([^"]+)"', first_line)
                return match.group(1) if match else first_line.strip()
        except (UnicodeError, ValueError, IndexError) as e:
            log(f"Failed to extract command from {file_path}: {e}")
        return None

    def _create_preview(self, line: str, pattern: re.Pattern) -> str:
        """Create a preview string for a matched line, centering around the first match."""
        original = line.rstrip("\\n")
        if len(original) <= self.config.max_preview_chars:
            return original

        # Find first match to center preview around
        match = pattern.search(original)
        if not match:
            return original[: self.config.max_preview_chars] + "…"

        span_start, span_end = match.span()
        center = (span_start + span_end) // 2
        half = self.config.max_preview_chars // 2
        start = max(0, center - half)
        end = start + self.config.max_preview_chars

        if end > len(original):
            end = len(original)
            start = max(0, end - self.config.max_preview_chars)

        snippet = original[start:end]
        prefix = "…" if start > 0 else ""
        suffix = "…" if end < len(original) else ""
        return f"{prefix}{snippet}{suffix}"


def validate_folders(folders: list[str]) -> list[str]:
    """Filter list to only include valid, existing directories."""
    return [f for f in folders if f and os.path.isdir(f)]


def count_matches_by_type(matches: list[SearchMatch]) -> tuple[int, int]:
    """Count valid matches and errors separately."""
    valid_count = sum(1 for m in matches if not m.is_error and m.line_no > 0)
    error_count = sum(1 for m in matches if m.is_error)
    return valid_count, error_count
