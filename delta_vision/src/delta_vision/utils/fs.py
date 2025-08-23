from __future__ import annotations

import os
from datetime import datetime

from delta_vision.utils.logger import log

"""Filesystem time utilities.

Policy: prefer modified time (mtime) across all platforms instead of creation
time (ctime). On Windows, ctime is file metadata change time, not true
creation. Using mtime yields portable and predictable "newest" calculations.
"""


def get_mtime(path: str) -> float | None:
    """Return file modification time (mtime) in seconds since epoch, or None.

    Cross-platform friendly: we purposely prefer mtime instead of creation time.
    """
    try:
        return os.path.getmtime(path)
    except (OSError, IOError) as e:
        log(f"[FS] Failed to get mtime for {path}: {e}")
        return None


def minutes_between(a: str, b: str) -> int | None:
    """Absolute minutes difference between two files' mtimes, or None."""
    ta = get_mtime(a)
    tb = get_mtime(b)
    if ta is None or tb is None:
        return None
    try:
        return int(round(abs(ta - tb) / 60.0))
    except (ValueError, OverflowError, ArithmeticError) as e:
        log(f"[FS] Failed to calculate minutes between files: {e}")
        return None


def format_mtime(path: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> str | None:
    """Format file mtime as a human string, or None on error."""
    ts = get_mtime(path)
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts).strftime(fmt)
    except (ValueError, OSError) as e:
        log(f"[FS] Failed to format mtime for {path}: {e}")
        return None
