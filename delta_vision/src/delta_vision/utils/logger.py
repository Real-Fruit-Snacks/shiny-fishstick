from __future__ import annotations

import sys
from typing import Any

# Simple logger that avoids writing to stdout/stderr when Textual is headless.
# Use: from delta_vision.utils.logger import log
# log("message", ctx={...})


def _can_write() -> bool:
    try:
        from textual.app import App  # lazy import

        app = getattr(App, "app", None)
        if app is None:
            return True
        return not bool(getattr(app, "is_headless", False))
    except (ImportError, AttributeError, RuntimeError) as e:
        # If anything is odd, be safe and don't write
        # Note: Can't use log() here to avoid infinite recursion
        return False


def log(*args: Any, sep: str = " ", end: str = "\n") -> None:
    if not _can_write():
        return
    try:
        sys.stdout.write(sep.join(str(a) for a in args) + end)
        sys.stdout.flush()
    except (OSError, IOError, ValueError) as e:
        # Never raise from logging
        # Note: Can't use log() here to avoid infinite recursion
        pass
