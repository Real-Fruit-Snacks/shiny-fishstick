"""Input validation utilities for Delta Vision.

This module provides comprehensive validation for user inputs including
paths, ports, hostnames, and other configuration values to prevent
security issues and improve user experience.
"""

from __future__ import annotations

import os
import re
import socket
from pathlib import Path

from .config import config


class ValidationError(Exception):
    """Raised when input validation fails."""

    pass


def validate_directory_path(path: str, name: str = "Path", must_exist: bool = True) -> str:
    """Validate a directory path for security and accessibility.

    Args:
        path: The directory path to validate
        name: Human-readable name for error messages
        must_exist: Whether the directory must already exist

    Returns:
        Normalized absolute path

    Raises:
        ValidationError: If validation fails
    """
    if not path or not path.strip():
        raise ValidationError(f"{name} cannot be empty")

    path = path.strip()

    # Check for dangerous path traversal attempts
    # Block excessive upward traversal (more than 2 levels up)
    if path.count('../') > 2 or path.count('..\\') > 2:
        raise ValidationError(f"{name} contains excessive path traversal sequences")

    # Block dangerous patterns that could access system files
    dangerous_patterns = [
        '/etc/',
        '/bin/',
        '/usr/',
        '/var/',
        '/root/',
        '/home/',
        '\\windows\\',
        '\\system32\\',
        '\\boot\\',
    ]
    path_lower = path.lower()
    for pattern in dangerous_patterns:
        if pattern in path_lower and '../' in path_lower:
            raise ValidationError(f"{name} appears to target system directories")

    # Normalize and resolve the path
    try:
        resolved_path = Path(path).resolve()
        abs_path = str(resolved_path)
    except (OSError, ValueError) as e:
        raise ValidationError(f"{name} is not a valid path: {e}") from e

    # Check path length (reasonable limit)
    if len(abs_path) > config.max_path_length:
        raise ValidationError(f"{name} is too long (max {config.max_path_length} characters)")

    # Check for null bytes and other dangerous characters
    if '\x00' in abs_path or any(ord(c) < 32 for c in abs_path if c not in '\t\n\r'):
        raise ValidationError(f"{name} contains invalid characters")

    if must_exist:
        if not resolved_path.exists():
            raise ValidationError(f"{name} does not exist: {abs_path}")

        if not resolved_path.is_dir():
            raise ValidationError(f"{name} is not a directory: {abs_path}")

        # Check if directory is readable
        if not os.access(abs_path, os.R_OK):
            raise ValidationError(f"{name} is not readable: {abs_path}")

    return abs_path


def validate_file_path(path: str, name: str = "File", must_exist: bool = True, check_readable: bool = True) -> str:
    """Validate a file path for security and accessibility.

    Args:
        path: The file path to validate
        name: Human-readable name for error messages
        must_exist: Whether the file must already exist
        check_readable: Whether to check if file is readable (only if exists)

    Returns:
        Normalized absolute path

    Raises:
        ValidationError: If validation fails
    """
    if not path or not path.strip():
        raise ValidationError(f"{name} cannot be empty")

    path = path.strip()

    # Check for dangerous path traversal attempts
    # Block excessive upward traversal (more than 2 levels up)
    if path.count('../') > 2 or path.count('..\\') > 2:
        raise ValidationError(f"{name} contains excessive path traversal sequences")

    # Block dangerous patterns that could access system files
    dangerous_patterns = [
        '/etc/',
        '/bin/',
        '/usr/',
        '/var/',
        '/root/',
        '/home/',
        '\\windows\\',
        '\\system32\\',
        '\\boot\\',
    ]
    path_lower = path.lower()
    for pattern in dangerous_patterns:
        if pattern in path_lower and '../' in path_lower:
            raise ValidationError(f"{name} appears to target system directories")

    # Normalize and resolve the path
    try:
        resolved_path = Path(path).resolve()
        abs_path = str(resolved_path)
    except (OSError, ValueError) as e:
        raise ValidationError(f"{name} is not a valid path: {e}") from e

    # Check path length
    if len(abs_path) > config.max_path_length:
        raise ValidationError(f"{name} is too long (max {config.max_path_length} characters)")

    # Check for dangerous characters
    if '\x00' in abs_path or any(ord(c) < 32 for c in abs_path if c not in '\t\n\r'):
        raise ValidationError(f"{name} contains invalid characters")

    if must_exist:
        if not resolved_path.exists():
            raise ValidationError(f"{name} does not exist: {abs_path}")

        if not resolved_path.is_file():
            raise ValidationError(f"{name} is not a file: {abs_path}")

        if check_readable and not os.access(abs_path, os.R_OK):
            raise ValidationError(f"{name} is not readable: {abs_path}")

    return abs_path


def validate_port(port: int | str, name: str = "Port") -> int:
    """Validate a network port number.

    Args:
        port: Port number to validate (int or string)
        name: Human-readable name for error messages

    Returns:
        Validated port number as integer

    Raises:
        ValidationError: If validation fails
    """
    # Convert string to int if needed
    if isinstance(port, str):
        port = port.strip()
        if not port:
            raise ValidationError(f"{name} cannot be empty")
        try:
            port = int(port)
        except ValueError as e:
            raise ValidationError(f"{name} must be a number, got: {port}") from e

    # Validate port range
    if not isinstance(port, int):
        raise ValidationError(f"{name} must be an integer")

    if port < 1 or port > 65535:
        raise ValidationError(f"{name} must be between 1 and 65535, got: {port}")

    # Warn about privileged ports (but don't fail - might be running as root)
    if port < 1024:
        # This is just a note, not a failure
        pass

    return port


def validate_hostname(hostname: str, name: str = "Hostname") -> str:
    """Validate a hostname or IP address.

    Args:
        hostname: Hostname or IP to validate
        name: Human-readable name for error messages

    Returns:
        Validated hostname

    Raises:
        ValidationError: If validation fails
    """
    if not hostname or not hostname.strip():
        raise ValidationError(f"{name} cannot be empty")

    hostname = hostname.strip().lower()

    # Check length
    if len(hostname) > 253:
        raise ValidationError(f"{name} is too long (max 253 characters)")

    # Check for dangerous characters
    if any(ord(c) < 32 for c in hostname):
        raise ValidationError(f"{name} contains invalid characters")

    # Try to validate as IP address first
    try:
        socket.inet_aton(hostname)
        return hostname  # Valid IPv4 address
    except OSError:
        pass

    # Try IPv6
    try:
        socket.inet_pton(socket.AF_INET6, hostname)
        return hostname  # Valid IPv6 address
    except (OSError, AttributeError):
        pass

    # Validate as hostname
    if not re.match(r'^[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?)*$', hostname):
        raise ValidationError(f"{name} is not a valid hostname or IP address: {hostname}")

    # Check each label length
    labels = hostname.split('.')
    for label in labels:
        if len(label) > 63:
            raise ValidationError(f"{name} has a label longer than 63 characters: {label}")

    return hostname


def validate_environment_string(value: str, name: str = "Environment variable") -> str:
    """Validate an environment variable value.

    Args:
        value: Environment variable value to validate
        name: Human-readable name for error messages

    Returns:
        Validated string value

    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be a string")

    # Check for null bytes
    if '\x00' in value:
        raise ValidationError(f"{name} contains null bytes")

    # Check reasonable length
    if len(value) > 8192:
        raise ValidationError(f"{name} is too long (max 8192 characters)")

    return value


def validate_config_paths(
    new_path: str | None = None, old_path: str | None = None, keywords_path: str | None = None
) -> tuple[str | None, str | None, str | None]:
    """Validate all configuration paths at once.

    Args:
        new_path: Path to new files directory
        old_path: Path to old files directory
        keywords_path: Path to keywords file

    Returns:
        Tuple of (validated_new_path, validated_old_path, validated_keywords_path)

    Raises:
        ValidationError: If any validation fails
    """
    validated_new = None
    validated_old = None
    validated_keywords = None

    if new_path:
        validated_new = validate_directory_path(new_path, "New folder path", must_exist=True)

    if old_path:
        validated_old = validate_directory_path(old_path, "Old folder path", must_exist=True)

    if keywords_path:
        validated_keywords = validate_file_path(
            keywords_path, "Keywords file path", must_exist=True, check_readable=True
        )

    return validated_new, validated_old, validated_keywords


def validate_network_config(host: str, port: int | str) -> tuple[str, int]:
    """Validate network configuration (host and port).

    Args:
        host: Hostname or IP address
        port: Port number

    Returns:
        Tuple of (validated_host, validated_port)

    Raises:
        ValidationError: If validation fails
    """
    validated_host = validate_hostname(host, "Host")
    validated_port = validate_port(port, "Port")

    return validated_host, validated_port
