from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .logger import log


@dataclass
class FileReadResult:
    """Result of file reading operations with consistent error handling."""
    success: bool
    content: str = ""
    lines: list[str] = None
    encoding: str = ""
    error_message: str = ""

    def __post_init__(self):
        if self.lines is None:
            self.lines = []

DEFAULT_ENCODINGS: tuple[str, ...] = (
    "utf-8",
    "utf-8-sig",
    "cp1252",
    "latin-1",
)


def read_text(
    path: str, encodings: Iterable[str] = DEFAULT_ENCODINGS, errors: str = "strict", ignore_on_last: bool = True
) -> tuple[str, str]:
    """
    Read a text file trying multiple encodings in order.

    Returns (text, used_encoding).
    If all strict attempts fail and ignore_on_last is True, retries the last
    encoding with errors="ignore" and logs a warning.
    """
    last_enc = None
    for enc in encodings:
        last_enc = enc
        try:
            with open(path, encoding=enc, errors=errors) as f:
                return f.read(), enc
        except UnicodeDecodeError:
            continue
        except OSError as e:
            # For IO errors, propagate a simple, empty content result
            # (callers already guard and present an error row/message)
            log(f"[IO] Failed to read {path} with {enc}: {e}")
            return ("", enc)
    if ignore_on_last and last_enc:
        try:
            with open(path, encoding=last_enc, errors="ignore") as f:
                log(f"[IO] Decoded with ignore: {path} ({last_enc})")
                return f.read(), f"{last_enc}+ignore"
        except OSError as e:
            log(f"[IO] Failed to read {path} with ignore mode: {e}")
            pass
    return ("", last_enc or "")


def read_lines(
    path: str, encodings: Iterable[str] = DEFAULT_ENCODINGS, errors: str = "strict", ignore_on_last: bool = True
) -> tuple[list[str], str]:
    text, used = read_text(path, encodings=encodings, errors=errors, ignore_on_last=ignore_on_last)
    if not text:
        return ([], used)
    return (text.splitlines(), used)


# Consolidated file I/O functions to reduce duplication

def safe_read_file(file_path: str, default_content: str = "") -> FileReadResult:
    """Safely read a file with comprehensive error handling.

    This function consolidates the duplicate file reading patterns used
    across the application with consistent error handling and logging.

    Args:
        file_path: Path to the file to read
        default_content: Content to return on error (default: empty string)

    Returns:
        FileReadResult with success status, content, and error details
    """
    if not file_path:
        return FileReadResult(
            success=False,
            content=default_content,
            error_message="No file path provided"
        )

    try:
        content, encoding = read_text(file_path)
        if content or encoding:  # Success case
            return FileReadResult(
                success=True,
                content=content,
                lines=content.splitlines() if content else [],
                encoding=encoding
            )
        else:  # Empty result indicates read failure
            error_msg = f"Failed to read file: {file_path}"
            log(f"[IO] {error_msg}")
            return FileReadResult(
                success=False,
                content=default_content,
                error_message=error_msg
            )
    except (OSError, UnicodeDecodeError) as e:
        error_msg = f"Error reading {file_path}: {e}"
        log(f"[IO] {error_msg}")
        return FileReadResult(
            success=False,
            content=default_content,
            error_message=error_msg
        )


def safe_read_lines(file_path: str, skip_header: bool = False) -> FileReadResult:
    """Safely read a file as lines with comprehensive error handling.

    This function consolidates the duplicate line reading patterns used
    across the application, particularly for log files and structured data.

    Args:
        file_path: Path to the file to read
        skip_header: Whether to skip the first line (default: False)

    Returns:
        FileReadResult with success status, lines, and error details
    """
    result = safe_read_file(file_path)

    if result.success and result.content:
        lines = result.content.splitlines()
        if skip_header and lines:
            lines = lines[1:]
        result.lines = lines
    elif not result.success:
        # Return error indicator as single line for compatibility
        result.lines = ["[Error reading file]"]

    return result


def safe_read_first_line(file_path: str) -> str | None:
    """Safely read just the first line of a file.

    Useful for header parsing and quick file inspection.
    Consolidates patterns used in file_parsing.py and other modules.

    Args:
        file_path: Path to the file to read

    Returns:
        First line of the file, or None if read fails
    """
    if not file_path:
        return None

    try:
        # Use the existing read_text for consistency
        content, _ = read_text(file_path)
        if content:
            lines = content.splitlines()
            return lines[0] if lines else ""
        return None
    except (OSError, UnicodeDecodeError) as e:
        log(f"[IO] Failed to read first line from {file_path}: {e}")
        return None
