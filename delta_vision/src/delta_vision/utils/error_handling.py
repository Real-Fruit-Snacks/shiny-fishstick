"""Standardized error handling and logging utilities for Delta Vision.

This module consolidates duplicate error logging patterns found across
the application, providing consistent error messages and reducing code
duplication.
"""

from typing import Any, Optional

from .logger import log


def log_file_error(file_path: str, operation: str, exception: Exception) -> None:
    """Log file operation errors with consistent formatting.

    This consolidates the duplicate file error logging patterns found
    across multiple modules.

    Args:
        file_path: Path to the file that caused the error
        operation: Description of the operation (e.g., "reading", "writing")
        exception: The exception that was raised
    """
    error_type = type(exception).__name__
    log(f"[IO] Failed {operation} {file_path}: {error_type}: {exception}")


def log_network_error(host: str, port: int, operation: str, exception: Exception, prefix: str = "NET") -> None:
    """Log network operation errors with consistent formatting.

    This consolidates the duplicate network error logging patterns found
    in client.py and server.py.

    Args:
        host: Hostname or IP address
        port: Port number
        operation: Description of the operation (e.g., "connecting", "sending")
        exception: The exception that was raised
        prefix: Log prefix for categorization (default: "NET")
    """
    error_type = type(exception).__name__
    log(f"[{prefix}] Failed {operation} {host}:{port}: {error_type}: {exception}")


def log_validation_error(field: str, value: Any, exception: Exception) -> None:
    """Log validation errors with consistent formatting.

    This consolidates the duplicate validation error logging patterns.

    Args:
        field: Name of the field being validated
        value: The value that failed validation
        exception: The exception that was raised
    """
    error_type = type(exception).__name__
    log(f"[VALIDATION] Failed validating {field}='{value}': {error_type}: {exception}")


def log_ui_error(component: str, action: str, exception: Exception) -> None:
    """Log UI component errors with consistent formatting.

    This consolidates the duplicate UI error logging patterns found
    across screen files.

    Args:
        component: Name of the UI component (e.g., "table", "input")
        action: The action being performed (e.g., "setting focus", "updating")
        exception: The exception that was raised
    """
    error_type = type(exception).__name__
    log(f"[UI] Failed {action} on {component}: {error_type}: {exception}")


def log_process_error(process_name: str, operation: str, exception: Exception, pid: Optional[int] = None) -> None:
    """Log process operation errors with consistent formatting.

    This consolidates the duplicate process error logging patterns found
    in server.py and other process management code.

    Args:
        process_name: Name or description of the process
        operation: The operation being performed (e.g., "starting", "terminating")
        exception: The exception that was raised
        pid: Optional process ID for more specific logging
    """
    error_type = type(exception).__name__
    pid_str = f" (PID {pid})" if pid else ""
    log(f"[PROCESS] Failed {operation} {process_name}{pid_str}: {error_type}: {exception}")


def log_search_error(query: str, location: str, exception: Exception) -> None:
    """Log search operation errors with consistent formatting.

    This consolidates the duplicate search error logging patterns.

    Args:
        query: The search query that caused the error
        location: Where the search was performed (e.g., folder path)
        exception: The exception that was raised
    """
    error_type = type(exception).__name__
    log(f"[SEARCH] Failed searching '{query}' in {location}: {error_type}: {exception}")


def log_theme_error(theme_name: str, operation: str, exception: Exception) -> None:
    """Log theme-related errors with consistent formatting.

    This consolidates the duplicate theme error logging patterns.

    Args:
        theme_name: Name of the theme
        operation: The operation being performed (e.g., "registering", "loading")
        exception: The exception that was raised
    """
    error_type = type(exception).__name__
    log(f"[THEME] Failed {operation} theme '{theme_name}': {error_type}: {exception}")


def log_watchdog_error(path: str, operation: str, exception: Exception) -> None:
    """Log file watching errors with consistent formatting.

    This consolidates the duplicate watchdog error logging patterns.

    Args:
        path: Path being watched
        operation: The operation being performed (e.g., "starting observer", "handling event")
        exception: The exception that was raised
    """
    error_type = type(exception).__name__
    log(f"[WATCHDOG] Failed {operation} for {path}: {error_type}: {exception}")


def log_generic_error(context: str, operation: str, exception: Exception, prefix: Optional[str] = None) -> None:
    """Log generic errors with consistent formatting.

    This is a fallback for error patterns that don't fit other categories.

    Args:
        context: Context where the error occurred (e.g., "table navigation")
        operation: The operation being performed
        exception: The exception that was raised
        prefix: Optional log prefix for categorization
    """
    error_type = type(exception).__name__
    prefix_str = f"[{prefix}] " if prefix else ""
    log(f"{prefix_str}Error in {context} during {operation}: {error_type}: {exception}")


# Convenience functions for common error patterns


def log_failed_operation(operation: str, exception: Exception) -> None:
    """Log a simple failed operation.

    This is for the most common pattern: "Failed to [operation]: [exception]"

    Args:
        operation: Description of what failed
        exception: The exception that was raised
    """
    log(f"Failed to {operation}: {exception}")


def log_error_with_context(message: str, exception: Exception, context: Optional[dict] = None) -> None:
    """Log an error with additional context information.

    Args:
        message: Main error message
        exception: The exception that was raised
        context: Optional dictionary of context information
    """
    error_type = type(exception).__name__
    base_msg = f"{message}: {error_type}: {exception}"

    if context:
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        log(f"{base_msg} (Context: {context_str})")
    else:
        log(base_msg)
