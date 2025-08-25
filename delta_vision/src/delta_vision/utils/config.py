from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from .logger import log

if TYPE_CHECKING:
    from rich.text import Text


class ConfigError(Exception):
    """Configuration validation error."""

    pass


@dataclass
class PathsConfig:
    """Configuration object for file and folder paths used throughout Delta Vision."""

    new_folder_path: str | None = None
    old_folder_path: str | None = None
    keywords_path: str | None = None

    @classmethod
    def from_args(cls, args) -> PathsConfig:
        """Create PathsConfig from command line arguments."""
        return cls(new_folder_path=args.new, old_folder_path=args.old, keywords_path=args.keywords)

    @classmethod
    def from_env(cls) -> PathsConfig:
        """Create PathsConfig from environment variables."""
        return cls(
            new_folder_path=os.environ.get('DELTA_NEW'),
            old_folder_path=os.environ.get('DELTA_OLD'),
            keywords_path=os.environ.get('DELTA_KEYWORDS'),
        )

    def merge_with_env(self) -> PathsConfig:
        """Merge with environment variables, keeping existing values if they exist."""
        return PathsConfig(
            new_folder_path=self.new_folder_path or os.environ.get('DELTA_NEW'),
            old_folder_path=self.old_folder_path or os.environ.get('DELTA_OLD'),
            keywords_path=self.keywords_path or os.environ.get('DELTA_KEYWORDS'),
        )


@dataclass
class KeywordMatchConfig:
    """Configuration object for keyword matching operations."""

    file_path: str
    keyword: str
    side: str
    color: str
    pattern: re.Pattern


@dataclass
class TableRowConfig:
    """Configuration object for adding details table rows."""

    side_cell: Text
    line_cell: Text
    highlighted: str
    line_num: int
    file_path: str


@dataclass
class SearchSummaryConfig:
    """Configuration object for search summary updates."""

    matches: list[Any]  # List of SearchMatch objects
    query: str
    elapsed: float
    files_scanned: int


class Config:
    """Delta Vision configuration with environment variable support and validation."""

    # Default values
    _DEFAULT_MAX_FILES: Final[int] = 5000
    _DEFAULT_MAX_PREVIEW_CHARS: Final[int] = 200
    _DEFAULT_MAX_RENDER_LINES: Final[int] = 5000
    _DEFAULT_REFRESH_INTERVAL: Final[float] = 1.0
    _DEFAULT_DEBOUNCE_MS: Final[int] = 300
    _DEFAULT_NETWORK_TIMEOUT: Final[int] = 30
    _DEFAULT_CONTEXT_LINES: Final[int] = 3
    _DEFAULT_MAX_PATH_LENGTH: Final[int] = 4096
    _DEFAULT_BUFFER_SIZE: Final[int] = 4096

    # Validation bounds
    _MIN_MAX_FILES: Final[int] = 100
    _MAX_MAX_FILES: Final[int] = 50000
    _MIN_PREVIEW_CHARS: Final[int] = 50
    _MAX_PREVIEW_CHARS: Final[int] = 10000
    _MIN_RENDER_LINES: Final[int] = 100
    _MAX_RENDER_LINES: Final[int] = 100000
    _MIN_REFRESH_INTERVAL: Final[float] = 0.1
    _MAX_REFRESH_INTERVAL: Final[float] = 60.0
    _MIN_DEBOUNCE_MS: Final[int] = 50
    _MAX_DEBOUNCE_MS: Final[int] = 2000
    _MIN_NETWORK_TIMEOUT: Final[int] = 5
    _MAX_NETWORK_TIMEOUT: Final[int] = 300
    _MIN_CONTEXT_LINES: Final[int] = 0
    _MAX_CONTEXT_LINES: Final[int] = 10
    _MIN_MAX_PATH_LENGTH: Final[int] = 1024
    _MAX_MAX_PATH_LENGTH: Final[int] = 65536
    _MIN_BUFFER_SIZE: Final[int] = 1024
    _MAX_BUFFER_SIZE: Final[int] = 65536

    def __init__(self):
        """Initialize configuration with environment variable overrides."""
        self.max_files = self._get_int_env("DELTA_MAX_FILES", self._DEFAULT_MAX_FILES)
        self.max_preview_chars = self._get_int_env("DELTA_MAX_PREVIEW_CHARS", self._DEFAULT_MAX_PREVIEW_CHARS)
        self.max_render_lines = self._get_int_env("DELTA_MAX_RENDER_LINES", self._DEFAULT_MAX_RENDER_LINES)
        self.refresh_interval = self._get_float_env("DELTA_REFRESH_INTERVAL", self._DEFAULT_REFRESH_INTERVAL)
        self.debounce_ms = self._get_int_env("DELTA_DEBOUNCE_MS", self._DEFAULT_DEBOUNCE_MS)
        self.network_timeout = self._get_int_env("DELTA_NETWORK_TIMEOUT", self._DEFAULT_NETWORK_TIMEOUT)
        self.context_lines = self._get_int_env("DELTA_CONTEXT_LINES", self._DEFAULT_CONTEXT_LINES)
        self.max_path_length = self._get_int_env("DELTA_MAX_PATH_LENGTH", self._DEFAULT_MAX_PATH_LENGTH)
        self.buffer_size = self._get_int_env("DELTA_BUFFER_SIZE", self._DEFAULT_BUFFER_SIZE)

        self._validate_all()

    def _get_int_env(self, key: str, default: int) -> int:
        """Get integer environment variable with fallback to default."""
        value = os.environ.get(key)
        if value is None:
            return default

        try:
            return int(value)
        except ValueError as e:
            log.warning(f"Invalid integer value for {key}='{value}', using default {default}: {e}")
            return default

    def _get_float_env(self, key: str, default: float) -> float:
        """Get float environment variable with fallback to default."""
        value = os.environ.get(key)
        if value is None:
            return default

        try:
            return float(value)
        except ValueError as e:
            log.warning(f"Invalid float value for {key}='{value}', using default {default}: {e}")
            return default

    def _validate_all(self) -> None:
        """Validate all configuration values."""
        self._validate_int("max_files", self.max_files, self._MIN_MAX_FILES, self._MAX_MAX_FILES)
        self._validate_int(
            "max_preview_chars", self.max_preview_chars, self._MIN_PREVIEW_CHARS, self._MAX_PREVIEW_CHARS
        )
        self._validate_int("max_render_lines", self.max_render_lines, self._MIN_RENDER_LINES, self._MAX_RENDER_LINES)
        self._validate_float(
            "refresh_interval", self.refresh_interval, self._MIN_REFRESH_INTERVAL, self._MAX_REFRESH_INTERVAL
        )
        self._validate_int("debounce_ms", self.debounce_ms, self._MIN_DEBOUNCE_MS, self._MAX_DEBOUNCE_MS)
        self._validate_int(
            "network_timeout", self.network_timeout, self._MIN_NETWORK_TIMEOUT, self._MAX_NETWORK_TIMEOUT
        )
        self._validate_int("context_lines", self.context_lines, self._MIN_CONTEXT_LINES, self._MAX_CONTEXT_LINES)
        self._validate_int(
            "max_path_length", self.max_path_length, self._MIN_MAX_PATH_LENGTH, self._MAX_MAX_PATH_LENGTH
        )
        self._validate_int("buffer_size", self.buffer_size, self._MIN_BUFFER_SIZE, self._MAX_BUFFER_SIZE)

    def _validate_int(self, name: str, value: int, min_val: int, max_val: int) -> None:
        """Validate integer configuration value."""
        if not isinstance(value, int):
            raise ConfigError(f"{name} must be an integer, got {type(value).__name__}")
        if not (min_val <= value <= max_val):
            raise ConfigError(f"{name} must be between {min_val} and {max_val}, got {value}")

    def _validate_float(self, name: str, value: float, min_val: float, max_val: float) -> None:
        """Validate float configuration value."""
        if not isinstance(value, (int, float)):
            raise ConfigError(f"{name} must be a number, got {type(value).__name__}")
        if not (min_val <= value <= max_val):
            raise ConfigError(f"{name} must be between {min_val} and {max_val}, got {value}")

    def __repr__(self) -> str:
        """String representation of configuration."""
        return (
            f"Config(max_files={self.max_files}, "
            f"max_preview_chars={self.max_preview_chars}, "
            f"max_render_lines={self.max_render_lines}, "
            f"refresh_interval={self.refresh_interval}, "
            f"debounce_ms={self.debounce_ms}, "
            f"network_timeout={self.network_timeout}, "
            f"context_lines={self.context_lines}, "
            f"max_path_length={self.max_path_length}, "
            f"buffer_size={self.buffer_size})"
        )


# Global configuration instance
config = Config()
