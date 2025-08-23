"""File I/O and header parsing utilities for Delta Vision.

This module provides utilities for reading files with multiple encoding fallbacks
and parsing header metadata from Delta Vision log files.
"""

import os
import re
from typing import Optional

from .logger import log


def read_file_with_fallback(file_path: str, skip_header: bool = True) -> list[str]:
    """Read a file with multiple encoding attempts, optionally skipping header line.

    Args:
        file_path: Path to the file to read
        skip_header: Whether to skip the first line (header)

    Returns:
        List of lines from the file (header excluded if skip_header=True)
        Returns single-item error list on read failure
    """
    if not file_path:
        return ["[Error: No file path provided]"]

    # Try common encodings, ignore header
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(file_path, encoding=enc, errors="strict") as f:
                lines = f.read().splitlines()
            if skip_header:
                return lines[1:] if lines else []
            else:
                return lines
        except UnicodeDecodeError:
            continue
        except (OSError, PermissionError):
            log(f"Failed to read file {file_path} with encoding {enc}")
            return ["[Error reading file]"]

    # Final fallback with error ignoring
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            lines = f.read().splitlines()
        if skip_header:
            return lines[1:] if lines else []
        else:
            return lines
    except (OSError, PermissionError):
        log(f"Failed to read file {file_path} with fallback encoding")
        return ["[Error reading file]"]


def read_file_pair(old_path: str, new_path: str) -> tuple[list[str], list[str]]:
    """Read OLD/NEW files as lists of lines, skipping the header line.

    Args:
        old_path: Path to the old file
        new_path: Path to the new file

    Returns:
        Tuple of (old_lines, new_lines) with headers excluded
    """
    return read_file_with_fallback(old_path), read_file_with_fallback(new_path)


def extract_first_line_command(file_path: str) -> Optional[str]:
    """Extract the quoted command from the first line, if present.

    Args:
        file_path: Path to the file to read

    Returns:
        The command string extracted from quotes, or None if not found
    """
    if not file_path or not os.path.isfile(file_path):
        return None

    # Try multiple encodings for just the first line
    first_line = None
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(file_path, encoding=enc, errors="strict") as f:
                first_line = f.readline()
            break
        except UnicodeDecodeError:
            continue
        except (OSError, PermissionError):
            log(f"Failed to read first line from {file_path} with encoding {enc}")
            return None

    # Fallback with error ignoring
    if first_line is None:
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                first_line = f.readline()
        except (OSError, PermissionError):
            log(f"Failed to read first line from {file_path} with fallback encoding")
            return None

    # Extract command from quotes
    match = re.search(r'"([^"]+)"', first_line or "")
    return match.group(1) if match else None


def parse_header_metadata(file_path: str) -> Optional[dict[str, Optional[str]]]:
    """Parse header line for date/time and command.

    Expected formats:
    - YYYYMMDD "command"
    - YYYYMMDD HHMMSS "command"
    - YYYYMMDDTHHMMSS "command"

    Falls back to extracting 8-digit date from filename if header parsing fails.

    Args:
        file_path: Path to the file to parse

    Returns:
        Dict with keys 'date', 'time', 'cmd' or None if file not accessible
    """
    if not file_path or not os.path.isfile(file_path):
        return None

    # Read first line with encoding fallbacks
    first_line = None
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(file_path, encoding=enc, errors="strict") as f:
                first_line = f.readline()
            break
        except UnicodeDecodeError:
            continue
        except (OSError, PermissionError):
            log(f"Failed to read header from {file_path} with encoding {enc}")
            break

    # Fallback encoding with error ignoring
    if first_line is None:
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                first_line = f.readline()
        except (OSError, PermissionError):
            log(f"Failed to read header from {file_path} with fallback encoding")
            first_line = ""

    # Initialize return values
    date = None
    time = None
    cmd = None

    # Try multiple header patterns
    patterns = [
        r"^\s*(\d{8})[ T](\d{6})\s+\"([^\"]+)\"",  # YYYYMMDD HHMMSS "cmd" or YYYYMMDDTHHMMSS "cmd"
        r"^\s*(\d{8})T(\d{6})\s+\"([^\"]+)\"",    # YYYYMMDDTHHMMSS "cmd"
        r"^\s*(\d{8})\s+\"([^\"]+)\"",            # YYYYMMDD "cmd"
    ]

    for pattern in patterns:
        match = re.match(pattern, first_line or "")
        if match:
            groups = match.groups()
            if len(groups) == 3:
                date, time, cmd = groups[0], groups[1], groups[2]
            elif len(groups) == 2:
                date, cmd = groups[0], groups[1]
            break

    # Fallback: try to extract date from filename
    if not date:
        basename = os.path.basename(file_path)
        match = re.search(r"(\d{8})", basename)
        if match:
            date = match.group(1)

    return {"date": date, "time": time, "cmd": cmd}
