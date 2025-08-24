"""Tests for the validation module.

This module tests the security-critical input validation functions
to ensure they properly prevent path traversal, validate ports/hostnames,
and handle edge cases correctly.
"""

import pytest

from delta_vision.utils.validation import (
    ValidationError,
    validate_config_paths,
    validate_directory_path,
    validate_file_path,
    validate_hostname,
    validate_network_config,
    validate_port,
)


class TestValidateDirectoryPath:
    """Tests for directory path validation."""

    def test_valid_existing_directory(self, tmp_path):
        """Test validation of valid existing directory."""
        result = validate_directory_path(str(tmp_path))
        assert result == str(tmp_path.resolve())

    def test_empty_path_raises_error(self):
        """Test that empty path raises ValidationError."""
        with pytest.raises(ValidationError, match="Path cannot be empty"):
            validate_directory_path("")

    def test_whitespace_only_path_raises_error(self):
        """Test that whitespace-only path raises ValidationError."""
        with pytest.raises(ValidationError, match="Path cannot be empty"):
            validate_directory_path("   ")

    def test_nonexistent_directory_raises_error(self):
        """Test that non-existent directory raises ValidationError."""
        with pytest.raises(ValidationError, match="does not exist"):
            validate_directory_path("/nonexistent/path/123456")

    def test_file_instead_of_directory_raises_error(self, tmp_path):
        """Test that passing a file instead of directory raises ValidationError."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with pytest.raises(ValidationError, match="is not a directory"):
            validate_directory_path(str(test_file))

    def test_excessive_path_traversal_blocked(self):
        """Test that excessive path traversal attempts are blocked."""
        dangerous_path = "../../../../../../../etc/passwd"
        with pytest.raises(ValidationError, match="excessive path traversal"):
            validate_directory_path(dangerous_path)

    def test_system_directory_traversal_blocked(self):
        """Test that traversal to system directories is blocked."""
        dangerous_path = "../../etc/../etc"
        with pytest.raises(ValidationError, match="excessive path traversal"):
            validate_directory_path(dangerous_path)

    def test_long_path_rejected(self):
        """Test that excessively long paths are rejected."""
        long_path = "a" * 5000
        with pytest.raises(ValidationError, match="is too long"):
            validate_directory_path(long_path)

    def test_null_byte_rejected(self):
        """Test that paths with null bytes are rejected."""
        with pytest.raises(ValidationError, match="is not a valid path"):
            validate_directory_path("valid/path\x00/evil")

    def test_must_exist_false_allows_nonexistent(self, tmp_path):
        """Test that must_exist=False allows non-existent paths."""
        nonexistent = tmp_path / "nonexistent"
        result = validate_directory_path(str(nonexistent), must_exist=False)
        assert result == str(nonexistent.resolve())


class TestValidateFilePath:
    """Tests for file path validation."""

    def test_valid_existing_file(self, tmp_path):
        """Test validation of valid existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = validate_file_path(str(test_file))
        assert result == str(test_file.resolve())

    def test_nonexistent_file_raises_error(self):
        """Test that non-existent file raises ValidationError."""
        with pytest.raises(ValidationError, match="does not exist"):
            validate_file_path("/nonexistent/file.txt")

    def test_directory_instead_of_file_raises_error(self, tmp_path):
        """Test that passing a directory instead of file raises ValidationError."""
        with pytest.raises(ValidationError, match="is not a file"):
            validate_file_path(str(tmp_path))

    def test_excessive_path_traversal_blocked(self):
        """Test that excessive path traversal attempts are blocked."""
        dangerous_path = "../../../../../../../etc/passwd"
        with pytest.raises(ValidationError, match="excessive path traversal"):
            validate_file_path(dangerous_path)


class TestValidatePort:
    """Tests for port validation."""

    def test_valid_port_numbers(self):
        """Test validation of valid port numbers."""
        assert validate_port(80) == 80
        assert validate_port(8080) == 8080
        assert validate_port(65535) == 65535
        assert validate_port("8765") == 8765

    def test_invalid_port_ranges(self):
        """Test that invalid port ranges are rejected."""
        with pytest.raises(ValidationError, match="must be between 1 and 65535"):
            validate_port(0)

        with pytest.raises(ValidationError, match="must be between 1 and 65535"):
            validate_port(65536)

        with pytest.raises(ValidationError, match="must be between 1 and 65535"):
            validate_port(-1)

    def test_non_numeric_port_rejected(self):
        """Test that non-numeric port strings are rejected."""
        with pytest.raises(ValidationError, match="must be a number"):
            validate_port("abc")

        with pytest.raises(ValidationError, match="must be a number"):
            validate_port("80.5")

    def test_empty_port_string_rejected(self):
        """Test that empty port string is rejected."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_port("")

    def test_privileged_ports_allowed(self):
        """Test that privileged ports are allowed (but noted)."""
        # Should not raise an error, just a note
        assert validate_port(22) == 22
        assert validate_port(80) == 80


class TestValidateHostname:
    """Tests for hostname validation."""

    def test_valid_hostnames(self):
        """Test validation of valid hostnames."""
        assert validate_hostname("localhost") == "localhost"
        assert validate_hostname("example.com") == "example.com"
        assert validate_hostname("test-server.local") == "test-server.local"

    def test_valid_ip_addresses(self):
        """Test validation of valid IP addresses."""
        assert validate_hostname("127.0.0.1") == "127.0.0.1"
        assert validate_hostname("192.168.1.1") == "192.168.1.1"
        assert validate_hostname("::1") == "::1"

    def test_empty_hostname_rejected(self):
        """Test that empty hostname is rejected."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_hostname("")

    def test_too_long_hostname_rejected(self):
        """Test that excessively long hostnames are rejected."""
        long_hostname = "a" * 300
        with pytest.raises(ValidationError, match="is too long"):
            validate_hostname(long_hostname)

    def test_invalid_hostname_format_rejected(self):
        """Test that invalid hostname formats are rejected."""
        with pytest.raises(ValidationError, match="is not a valid hostname"):
            validate_hostname("invalid..hostname")

        with pytest.raises(ValidationError, match="is not a valid hostname"):
            validate_hostname("-invalid-start")


class TestValidateNetworkConfig:
    """Tests for network configuration validation."""

    def test_valid_network_config(self):
        """Test validation of valid network configuration."""
        host, port = validate_network_config("localhost", 8080)
        assert host == "localhost"
        assert port == 8080

    def test_string_port_converted(self):
        """Test that string port is converted to integer."""
        host, port = validate_network_config("127.0.0.1", "9000")
        assert host == "127.0.0.1"
        assert port == 9000

    def test_invalid_host_rejected(self):
        """Test that invalid host is rejected."""
        with pytest.raises(ValidationError, match="is not a valid hostname"):
            validate_network_config("invalid..host", 8080)

    def test_invalid_port_rejected(self):
        """Test that invalid port is rejected."""
        with pytest.raises(ValidationError, match="must be between 1 and 65535"):
            validate_network_config("localhost", 0)


class TestValidateConfigPaths:
    """Tests for configuration path validation."""

    def test_all_valid_paths(self, tmp_path):
        """Test validation when all paths are valid."""
        new_dir = tmp_path / "new"
        old_dir = tmp_path / "old"
        keywords_file = tmp_path / "keywords.md"

        new_dir.mkdir()
        old_dir.mkdir()
        keywords_file.write_text("# Test\nkeyword")

        new_path, old_path, kw_path = validate_config_paths(str(new_dir), str(old_dir), str(keywords_file))

        assert new_path == str(new_dir.resolve())
        assert old_path == str(old_dir.resolve())
        assert kw_path == str(keywords_file.resolve())

    def test_none_values_preserved(self):
        """Test that None values are preserved."""
        new_path, old_path, kw_path = validate_config_paths(None, None, None)
        assert new_path is None
        assert old_path is None
        assert kw_path is None

    def test_mixed_valid_and_none(self, tmp_path):
        """Test validation with mix of valid paths and None."""
        new_dir = tmp_path / "new"
        new_dir.mkdir()

        new_path, old_path, kw_path = validate_config_paths(str(new_dir), None, None)
        assert new_path == str(new_dir.resolve())
        assert old_path is None
        assert kw_path is None

    def test_invalid_path_raises_error(self):
        """Test that invalid path in config raises ValidationError."""
        with pytest.raises(ValidationError, match="does not exist"):
            validate_config_paths("/nonexistent", None, None)


class TestSecurityScenarios:
    """Tests for security-specific attack scenarios."""

    def test_path_traversal_attacks_blocked(self):
        """Test that various path traversal attacks are blocked."""
        attack_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",  # URL encoded
            "....//....//etc/passwd",  # Double dots
        ]

        for attack_path in attack_paths:
            with pytest.raises(ValidationError):
                validate_directory_path(attack_path)

    def test_system_file_access_blocked(self):
        """Test that access to system files is blocked."""
        system_paths = [
            "../../etc",
            "../../../bin",
            "../../../../usr/bin",
        ]

        for sys_path in system_paths:
            with pytest.raises(ValidationError):
                validate_directory_path(sys_path)

    def test_null_byte_injection_blocked(self):
        """Test that null byte injection is blocked."""
        null_byte_paths = [
            "valid\x00/etc/passwd",
            "test\x00.txt",
            "\x00",
        ]

        for null_path in null_byte_paths:
            with pytest.raises(ValidationError, match="is not a valid path"):
                validate_directory_path(null_path, must_exist=False)
