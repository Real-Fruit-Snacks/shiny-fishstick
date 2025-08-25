"""Keywords scanner utility for Delta Vision.

This module provides background keyword scanning functionality separated from UI concerns.
It handles file system scanning, keyword counting, and metadata tracking with thread-safe operations.
"""

from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from .config import config
from .io import read_text
from .logger import log


@dataclass
class KeywordFileHit:
    """Represents keyword hits in a single file."""

    count: int = 0
    first_line_no: int = 0
    first_preview: str = ""
    lines: list[tuple[int, str]] = field(default_factory=list)


@dataclass
class ScanResult:
    """Results from a keyword scan operation."""

    summary: dict[str, KeywordFileHit]  # keyword -> aggregated hit info
    file_counts: dict[str, dict[str, dict[str, int]]]  # side -> file_path -> keyword -> count
    file_meta: dict[str, dict[str, tuple]]  # side -> file_path -> (mtime, size)
    files_scanned: int = 0
    errors: list[str] = field(default_factory=list)


class KeywordScanner:
    """Background keyword scanner with thread-safe operations."""

    def __init__(self, max_files: int = None, max_preview_chars: int = None):
        """Initialize the keyword scanner with configurable limits.

        Args:
            max_files: Maximum number of files to scan per operation (default: from config)
            max_preview_chars: Maximum characters in keyword match previews (default: from config)
        """
        self.max_files = max_files if max_files is not None else config.max_files
        self.max_preview_chars = max_preview_chars if max_preview_chars is not None else config.max_preview_chars

        # Threading state
        self._scan_thread: threading.Thread | None = None
        self._scan_lock = threading.Lock()
        self._scan_stop = threading.Event()
        self._scan_running = False
        self._pending_scan = False
        self._last_scan_end = 0.0

        # Callback for scan completion
        self._completion_callback: Callable[[ScanResult], None] | None = None

    def set_completion_callback(self, callback: Callable[[ScanResult], None]):
        """Set callback to be called when scan completes."""
        self._completion_callback = callback

    def is_scanning(self) -> bool:
        """Check if a scan is currently running."""
        return self._scan_running

    def has_pending_scan(self) -> bool:
        """Check if a scan is pending."""
        return self._pending_scan

    def start_scan(self, keywords: list[str], new_folder: str | None, old_folder: str | None):
        """Start background keyword scan."""
        if not keywords:
            return

        with self._scan_lock:
            if self._scan_running:
                self._pending_scan = True
                return

            self._scan_running = True
            self._scan_stop.clear()

        # Start background thread
        self._scan_thread = threading.Thread(
            target=self._scan_worker, args=(keywords, new_folder, old_folder), daemon=True
        )
        self._scan_thread.start()

    def stop_scan(self):
        """Stop any running or pending scans."""
        self._scan_stop.set()
        self._pending_scan = False

        if self._scan_thread and self._scan_thread.is_alive():
            self._scan_thread.join(timeout=1.0)

    def _scan_worker(self, keywords: list[str], new_folder: str | None, old_folder: str | None):
        """Background thread worker for scanning."""
        try:
            result = self._perform_scan(keywords, new_folder, old_folder)
        except Exception as e:
            log(f"Error during keyword scan: {e}")
            result = ScanResult({}, {}, {}, 0, [str(e)])
        finally:
            self._finish_scan(result)

    def _perform_scan(self, keywords: list[str], new_folder: str | None, old_folder: str | None) -> ScanResult:
        """Perform the actual keyword scanning."""
        # Build regex pattern for all keywords
        alternation = "|".join(re.escape(w) for w in keywords)
        pattern = re.compile(rf"(?<!\\w)({alternation})(?!\\w)", re.IGNORECASE)

        summary = {}
        file_counts = {"NEW": {}, "OLD": {}}
        file_meta = {"NEW": {}, "OLD": {}}
        files_scanned = 0
        errors = []

        # Initialize summary for all keywords
        for kw in keywords:
            summary[kw] = KeywordFileHit()

        # Scan each side
        folders = [("NEW", new_folder), ("OLD", old_folder)]
        for side, folder_path in folders:
            if self._scan_stop.is_set():
                break

            side_result = self._scan_folder(side, folder_path, pattern, keywords)
            file_counts[side] = side_result["counts"]
            file_meta[side] = side_result["meta"]
            files_scanned += side_result["files_scanned"]
            errors.extend(side_result["errors"])

            # Update summary
            for kw, hit_info in side_result["summary"].items():
                if kw in summary:
                    summary[kw].count += hit_info.count
                    if summary[kw].first_line_no == 0 and hit_info.first_line_no > 0:
                        summary[kw].first_line_no = hit_info.first_line_no
                        summary[kw].first_preview = hit_info.first_preview

        return ScanResult(summary, file_counts, file_meta, files_scanned, errors)

    def _scan_folder(self, side: str, folder_path: str | None, pattern: re.Pattern, keywords: list[str]) -> dict:
        """Scan a single folder for keywords - orchestrator for folder scanning."""
        result = self._initialize_scan_result(keywords)

        if not self._validate_folder_path(folder_path):
            return result

        return self._perform_folder_scan(side, folder_path, pattern, keywords, result)

    def _initialize_scan_result(self, keywords: list[str]) -> dict:
        """Initialize the result dictionary for folder scanning."""
        return {
            "counts": {},
            "meta": {},
            "summary": {kw: KeywordFileHit() for kw in keywords},
            "files_scanned": 0,
            "errors": [],
        }

    def _validate_folder_path(self, folder_path: str | None) -> bool:
        """Validate that folder path exists and is a directory."""
        return folder_path and os.path.isdir(folder_path)

    def _perform_folder_scan(
        self, side: str, folder_path: str, pattern: re.Pattern, keywords: list[str], result: dict
    ) -> dict:
        """Perform the actual folder scanning with error handling."""
        try:
            seen_paths = set()
            self._walk_and_scan_files(folder_path, pattern, keywords, result, seen_paths)
        except Exception as e:
            result["errors"].append(f"Error scanning {side} folder: {e}")
        return result

    def _walk_and_scan_files(
        self, folder_path: str, pattern: re.Pattern, keywords: list[str], result: dict, seen_paths: set
    ):
        """Walk through folder and scan all files."""
        for root, _dirs, files in os.walk(folder_path):
            if self._should_stop_scan(result):
                break
            self._scan_files_in_directory(root, files, pattern, keywords, result, seen_paths)

    def _should_stop_scan(self, result: dict) -> bool:
        """Check if scan should be stopped due to limits or cancellation."""
        return self._scan_stop.is_set() or result["files_scanned"] >= self.max_files

    def _scan_files_in_directory(
        self, root: str, files: list[str], pattern: re.Pattern, keywords: list[str], result: dict, seen_paths: set
    ):
        """Scan all files in a single directory."""
        for name in files:
            if self._should_stop_scan(result):
                break
            self._process_single_file_in_scan(root, name, pattern, keywords, result, seen_paths)

    def _process_single_file_in_scan(
        self, root: str, name: str, pattern: re.Pattern, keywords: list[str], result: dict, seen_paths: set
    ):
        """Process a single file during folder scan."""
        file_path = os.path.join(root, name)

        if not self._should_scan_file(file_path, seen_paths):
            return

        seen_paths.add(file_path)
        file_result = self._scan_file(file_path, pattern, keywords)

        if file_result:
            self._update_scan_results(file_result, result, file_path)

    def _should_scan_file(self, file_path: str, seen_paths: set) -> bool:
        """Check if file should be scanned (exists, not duplicate)."""
        return os.path.isfile(file_path) and file_path not in seen_paths

    def _update_scan_results(self, file_result: dict, result: dict, file_path: str):
        """Update scan results with file scan results."""
        result["counts"][file_path] = file_result["counts"]
        result["meta"][file_path] = file_result["meta"]
        result["files_scanned"] += 1
        self._update_summary_from_file_result(file_result, result)

    def _update_summary_from_file_result(self, file_result: dict, result: dict):
        """Update keyword summary with results from a single file."""
        for kw, count in file_result["counts"].items():
            if count > 0:
                self._update_keyword_summary(kw, count, file_result, result)

    def _update_keyword_summary(self, keyword: str, count: int, file_result: dict, result: dict):
        """Update summary for a specific keyword."""
        result["summary"][keyword].count += count

        if result["summary"][keyword].first_line_no == 0:
            result["summary"][keyword].first_line_no = file_result.get("first_line", 1)
            result["summary"][keyword].first_preview = file_result.get("first_preview", "")

    def _scan_file(self, file_path: str, pattern: re.Pattern, keywords: list[str]) -> dict | None:
        """Scan a single file for keywords - orchestrator for file scanning."""
        try:
            file_data = self._prepare_file_data(file_path, keywords)
            if not file_data:
                return None

            self._process_all_lines(file_data, pattern, keywords)
            return self._build_scan_result(file_data)

        except Exception as e:
            log(f"Error scanning file {file_path}: {e}")
            return None

    def _prepare_file_data(self, file_path: str, keywords: list[str]) -> dict | None:
        """Prepare file data for scanning."""
        stat = os.stat(file_path)
        text, _encoding = read_text(file_path)

        if not text:
            return None

        return {
            "meta": (stat.st_mtime, stat.st_size),
            "text": text,
            "counts": {kw: 0 for kw in keywords},
            "first_line": 0,
            "first_preview": "",
        }

    def _process_all_lines(self, file_data: dict, pattern: re.Pattern, keywords: list[str]):
        """Process all lines in the file for keyword matches."""
        for line_no, line in enumerate(file_data["text"].splitlines(), start=1):
            matches = pattern.findall(line)
            if matches:
                self._process_line_matches(file_data, line_no, line, matches, keywords)

    def _process_line_matches(self, file_data: dict, line_no: int, line: str, matches: list[str], keywords: list[str]):
        """Process all matches found in a single line."""
        for match in matches:
            self._process_single_match(file_data, line_no, line, match, keywords)

    def _process_single_match(self, file_data: dict, line_no: int, line: str, match: str, keywords: list[str]):
        """Process a single keyword match."""
        match_lower = match.lower()
        for kw in keywords:
            if kw.lower() == match_lower:
                self._record_keyword_match(file_data, line_no, line, kw)

    def _record_keyword_match(self, file_data: dict, line_no: int, line: str, keyword: str):
        """Record a keyword match and update counters."""
        file_data["counts"][keyword] += 1

        if file_data["first_line"] == 0:
            file_data["first_line"] = line_no
            file_data["first_preview"] = self._create_line_preview(line)

    def _create_line_preview(self, line: str) -> str:
        """Create a preview string for a line."""
        preview = line.strip()
        if len(preview) > self.max_preview_chars:
            preview = preview[: self.max_preview_chars] + "…"
        return preview

    def _build_scan_result(self, file_data: dict) -> dict | None:
        """Build the final scan result if matches were found."""
        if any(count > 0 for count in file_data["counts"].values()):
            return {
                "counts": file_data["counts"],
                "meta": file_data["meta"],
                "first_line": file_data["first_line"],
                "first_preview": file_data["first_preview"],
            }
        return None

    def _finish_scan(self, result: ScanResult):
        """Finish scan and call completion callback."""
        with self._scan_lock:
            self._scan_running = False
            self._last_scan_end = time.monotonic()

            # Check if another scan is pending
            if self._pending_scan and not self._scan_stop.is_set():
                self._pending_scan = False
                # Will be handled by the caller to restart scan

        # Call completion callback if set
        if self._completion_callback:
            try:
                self._completion_callback(result)
            except Exception as e:
                log(f"Error in scan completion callback: {e}")

    def cleanup(self):
        """Clean up scanner resources."""
        self.stop_scan()


def has_file_changed(file_path: str, old_meta: tuple | None) -> bool:
    """Check if a file has changed since last scan."""
    try:
        stat = os.stat(file_path)
        new_meta = (stat.st_mtime, stat.st_size)
        return old_meta != new_meta
    except (OSError, FileNotFoundError):
        return True  # File doesn't exist or can't be accessed
