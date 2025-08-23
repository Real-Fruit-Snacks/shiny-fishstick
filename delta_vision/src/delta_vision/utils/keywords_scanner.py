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
from typing import Callable, Dict, List, Set

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
    summary: Dict[str, KeywordFileHit]  # keyword -> aggregated hit info
    file_counts: Dict[str, Dict[str, Dict[str, int]]]  # side -> file_path -> keyword -> count
    file_meta: Dict[str, Dict[str, tuple]]  # side -> file_path -> (mtime, size)
    files_scanned: int = 0
    errors: List[str] = field(default_factory=list)


class KeywordScanner:
    """Background keyword scanner with thread-safe operations."""
    
    def __init__(self, max_files: int = 5000, max_preview_chars: int = 200):
        self.max_files = max_files
        self.max_preview_chars = max_preview_chars
        
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
        
    def start_scan(self, keywords: List[str], new_folder: str | None, old_folder: str | None):
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
            target=self._scan_worker,
            args=(keywords, new_folder, old_folder),
            daemon=True
        )
        self._scan_thread.start()
        
    def stop_scan(self):
        """Stop any running or pending scans."""
        self._scan_stop.set()
        self._pending_scan = False
        
        if self._scan_thread and self._scan_thread.is_alive():
            self._scan_thread.join(timeout=1.0)
            
    def _scan_worker(self, keywords: List[str], new_folder: str | None, old_folder: str | None):
        """Background thread worker for scanning."""
        try:
            result = self._perform_scan(keywords, new_folder, old_folder)
        except Exception as e:
            log(f"Error during keyword scan: {e}")
            result = ScanResult({}, {}, {}, 0, [str(e)])
        finally:
            self._finish_scan(result)
            
    def _perform_scan(self, keywords: List[str], new_folder: str | None, old_folder: str | None) -> ScanResult:
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
        
    def _scan_folder(self, side: str, folder_path: str | None, pattern: re.Pattern, keywords: List[str]) -> Dict:
        """Scan a single folder for keywords."""
        result = {
            "counts": {},
            "meta": {},
            "summary": {kw: KeywordFileHit() for kw in keywords},
            "files_scanned": 0,
            "errors": []
        }
        
        if not folder_path or not os.path.isdir(folder_path):
            return result
            
        seen_paths = set()
        
        try:
            for root, _dirs, files in os.walk(folder_path):
                if self._scan_stop.is_set():
                    break
                    
                for name in files:
                    if result["files_scanned"] >= self.max_files:
                        break
                        
                    file_path = os.path.join(root, name)
                    if not os.path.isfile(file_path) or file_path in seen_paths:
                        continue
                        
                    seen_paths.add(file_path)
                    file_result = self._scan_file(file_path, pattern, keywords)
                    
                    if file_result:
                        result["counts"][file_path] = file_result["counts"]
                        result["meta"][file_path] = file_result["meta"]
                        result["files_scanned"] += 1
                        
                        # Update summary
                        for kw, count in file_result["counts"].items():
                            if count > 0:
                                result["summary"][kw].count += count
                                if result["summary"][kw].first_line_no == 0:
                                    # Set first occurrence info
                                    result["summary"][kw].first_line_no = file_result.get("first_line", 1)
                                    result["summary"][kw].first_preview = file_result.get("first_preview", "")
                                    
                if result["files_scanned"] >= self.max_files:
                    break
                    
        except Exception as e:
            result["errors"].append(f"Error scanning {side} folder: {e}")
            
        return result
        
    def _scan_file(self, file_path: str, pattern: re.Pattern, keywords: List[str]) -> Dict | None:
        """Scan a single file for keywords."""
        try:
            # Get file metadata
            stat = os.stat(file_path)
            meta = (stat.st_mtime, stat.st_size)
            
            # Read file content
            text, _encoding = read_text(file_path)
            if not text:
                return None
                
            # Count keywords
            counts = {kw: 0 for kw in keywords}
            first_line = 0
            first_preview = ""
            
            for line_no, line in enumerate(text.splitlines(), start=1):
                matches = pattern.findall(line)
                if matches:
                    for match in matches:
                        match_lower = match.lower()
                        for kw in keywords:
                            if kw.lower() == match_lower:
                                counts[kw] += 1
                                if first_line == 0:
                                    first_line = line_no
                                    # Create preview
                                    preview = line.strip()
                                    if len(preview) > self.max_preview_chars:
                                        preview = preview[:self.max_preview_chars] + "…"
                                    first_preview = preview
                                    
            # Only return if we found matches
            if any(count > 0 for count in counts.values()):
                return {
                    "counts": counts,
                    "meta": meta,
                    "first_line": first_line,
                    "first_preview": first_preview
                }
                
        except Exception as e:
            log(f"Error scanning file {file_path}: {e}")
            
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