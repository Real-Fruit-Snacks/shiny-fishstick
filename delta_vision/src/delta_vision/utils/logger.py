from __future__ import annotations

import os
import sys
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Any, TextIO

# Enhanced logger with levels, file output, caching, and timestamps
# Use: from delta_vision.utils.logger import log, LogLevel
# log.info("message")
# log.debug("debug info", extra={"key": "value"})
# log.error("error occurred", exc_info=sys.exc_info())


class LogLevel(IntEnum):
    """Log severity levels."""
    DEBUG = 10
    INFO = 20
    WARN = 30
    WARNING = 30  # Alias for WARN
    ERROR = 40
    CRITICAL = 50


class Logger:
    """Enhanced logger with levels, file output, and better formatting."""

    def __init__(self):
        self._level = LogLevel.INFO
        self._file_handle: TextIO | None = None
        self._file_path: Path | None = None
        self._headless_cached: bool | None = None
        self._format_string = "{timestamp} [{level:8}] {message}"
        self._include_location = False

        # Check environment for configuration
        self._configure_from_env()

    def _configure_from_env(self) -> None:
        """Configure logger from environment variables."""
        # Set debug mode and file output if DEBUG=1
        if os.environ.get("DEBUG") == "1":
            self._level = LogLevel.DEBUG
            self._include_location = True
            # Set up file output to /tmp/delta_vision_debug.log
            log_path = Path("/tmp/delta_vision_debug.log")
            self.set_file_output(log_path)

        # Allow LOG_LEVEL env var to override
        level_str = os.environ.get("LOG_LEVEL", "").upper()
        if level_str in ["DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL"]:
            self._level = LogLevel[level_str]

    def set_level(self, level: LogLevel) -> None:
        """Set the minimum log level."""
        self._level = level

    def set_file_output(self, path: Path, append: bool = True) -> None:
        """Enable file output for logging."""
        try:
            # Close existing file if open
            if self._file_handle:
                self._file_handle.close()

            # Open new file
            mode = "a" if append else "w"
            self._file_handle = open(path, mode, encoding="utf-8")
            self._file_path = path
        except OSError:
            # Can't log errors about logging setup
            self._file_handle = None
            self._file_path = None

    def _can_write_stdout(self) -> bool:
        """Check if we can write to stdout (cached for performance)."""
        # Use cached result if available
        if self._headless_cached is not None:
            return not self._headless_cached

        try:
            from textual.app import App  # lazy import

            app = getattr(App, "app", None)
            if app is None:
                self._headless_cached = False
                return True

            is_headless = bool(getattr(app, "is_headless", False))
            self._headless_cached = is_headless
            return not is_headless
        except (ImportError, AttributeError, RuntimeError):
            # If anything is odd, be safe and don't write
            self._headless_cached = False
            return False

    def _format_message(
        self,
        level: LogLevel,
        message: str,
        extra: dict | None = None,
        exc_info: tuple | None = None
    ) -> str:
        """Format a log message with timestamp and level."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        level_name = level.name

        # Build base message
        formatted = self._format_string.format(
            timestamp=timestamp,
            level=level_name,
            message=message
        )

        # Add extra context if provided
        if extra:
            formatted += f" | {extra}"

        # Add exception info if provided
        if exc_info and exc_info[0] is not None:
            import traceback
            exc_str = "".join(traceback.format_exception(*exc_info))
            formatted += f"\n{exc_str}"

        return formatted

    def _write(
        self,
        level: LogLevel,
        *args: Any,
        sep: str = " ",
        extra: dict | None = None,
        exc_info: tuple | None = None
    ) -> None:
        """Write a log message at the specified level."""
        # Check if this level should be logged
        if level < self._level:
            return

        # Build message from args
        message = sep.join(str(a) for a in args)
        formatted = self._format_message(level, message, extra, exc_info)

        # Write to file if configured
        if self._file_handle:
            try:
                self._file_handle.write(formatted + "\n")
                self._file_handle.flush()
            except OSError:
                # Can't log errors about logging
                pass

        # Write to stdout if not headless
        if self._can_write_stdout():
            try:
                # Use color codes for terminal output
                color_codes = {
                    LogLevel.DEBUG: "\033[90m",    # Gray
                    LogLevel.INFO: "\033[0m",       # Default
                    LogLevel.WARN: "\033[93m",      # Yellow
                    LogLevel.ERROR: "\033[91m",     # Red
                    LogLevel.CRITICAL: "\033[95m",  # Magenta
                }
                color = color_codes.get(level, "\033[0m")
                reset = "\033[0m"

                # Check if stdout is a tty for color support
                if sys.stdout.isatty():
                    sys.stdout.write(f"{color}{formatted}{reset}\n")
                else:
                    sys.stdout.write(formatted + "\n")
                sys.stdout.flush()
            except (OSError, ValueError):
                # Never raise from logging
                pass

    def debug(self, *args: Any, **kwargs) -> None:
        """Log a debug message."""
        self._write(LogLevel.DEBUG, *args, **kwargs)

    def info(self, *args: Any, **kwargs) -> None:
        """Log an info message."""
        self._write(LogLevel.INFO, *args, **kwargs)

    def warn(self, *args: Any, **kwargs) -> None:
        """Log a warning message."""
        self._write(LogLevel.WARN, *args, **kwargs)

    def warning(self, *args: Any, **kwargs) -> None:
        """Alias for warn()."""
        self.warn(*args, **kwargs)

    def error(self, *args: Any, **kwargs) -> None:
        """Log an error message."""
        self._write(LogLevel.ERROR, *args, **kwargs)

    def critical(self, *args: Any, **kwargs) -> None:
        """Log a critical message."""
        self._write(LogLevel.CRITICAL, *args, **kwargs)

    def __call__(self, *args: Any, sep: str = " ", end: str = "\n") -> None:
        """Legacy compatibility - log at INFO level."""
        self.info(*args, sep=sep)


# Create singleton logger instance
log = Logger()
