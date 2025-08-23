"""Tests for the configuration system."""

import pytest

from delta_vision.utils.config import Config, ConfigError


class TestConfig:
    """Test the Config class functionality."""

    def test_config_defaults(self):
        """Test that config uses correct default values."""
        config = Config()
        assert config.max_files == 5000
        assert config.max_preview_chars == 500
        assert config.max_render_lines == 5000
        assert config.refresh_interval == 1.0
        assert config.debounce_ms == 300
        assert config.network_timeout == 30
        assert config.context_lines == 3

    def test_config_environment_variables(self, monkeypatch):
        """Test that environment variables override defaults."""
        monkeypatch.setenv("DELTA_MAX_FILES", "1000")
        monkeypatch.setenv("DELTA_MAX_PREVIEW_CHARS", "200")
        monkeypatch.setenv("DELTA_MAX_RENDER_LINES", "2000")
        monkeypatch.setenv("DELTA_REFRESH_INTERVAL", "0.5")
        monkeypatch.setenv("DELTA_DEBOUNCE_MS", "150")
        monkeypatch.setenv("DELTA_NETWORK_TIMEOUT", "60")
        monkeypatch.setenv("DELTA_CONTEXT_LINES", "5")

        config = Config()
        assert config.max_files == 1000
        assert config.max_preview_chars == 200
        assert config.max_render_lines == 2000
        assert config.refresh_interval == 0.5
        assert config.debounce_ms == 150
        assert config.network_timeout == 60
        assert config.context_lines == 5

    def test_config_invalid_environment_variables(self, monkeypatch):
        """Test that invalid environment variables fall back to defaults."""
        monkeypatch.setenv("DELTA_MAX_FILES", "not_a_number")
        monkeypatch.setenv("DELTA_REFRESH_INTERVAL", "invalid_float")

        config = Config()
        # Should fall back to defaults when env vars are invalid
        assert config.max_files == 5000
        assert config.refresh_interval == 1.0

    def test_config_validation_bounds(self):
        """Test that configuration values are validated against bounds."""
        # Test max_files out of bounds
        with pytest.raises(ConfigError, match="max_files must be between"):
            config = Config()
            config.max_files = 50  # Below minimum
            config._validate_all()

        with pytest.raises(ConfigError, match="max_files must be between"):
            config = Config()
            config.max_files = 100000  # Above maximum
            config._validate_all()

    def test_config_validation_types(self):
        """Test that configuration values must be correct types."""
        # Test integer validation
        config = Config()
        with pytest.raises(ConfigError, match="max_files must be an integer"):
            config.max_files = "not_an_int"
            config._validate_all()

        # Test float validation separately
        config = Config()
        with pytest.raises(ConfigError, match="refresh_interval must be a number"):
            config.refresh_interval = "not_a_float"
            config._validate_all()

    def test_config_boundary_values(self, monkeypatch):
        """Test configuration values at boundary limits."""
        # Test minimum valid values
        monkeypatch.setenv("DELTA_MAX_FILES", "100")
        monkeypatch.setenv("DELTA_MAX_PREVIEW_CHARS", "50")
        monkeypatch.setenv("DELTA_MAX_RENDER_LINES", "100")
        monkeypatch.setenv("DELTA_REFRESH_INTERVAL", "0.1")
        monkeypatch.setenv("DELTA_DEBOUNCE_MS", "50")
        monkeypatch.setenv("DELTA_NETWORK_TIMEOUT", "5")
        monkeypatch.setenv("DELTA_CONTEXT_LINES", "0")

        config = Config()
        assert config.max_files == 100
        assert config.max_preview_chars == 50
        assert config.max_render_lines == 100
        assert config.refresh_interval == 0.1
        assert config.debounce_ms == 50
        assert config.network_timeout == 5
        assert config.context_lines == 0

        # Test maximum valid values
        monkeypatch.setenv("DELTA_MAX_FILES", "50000")
        monkeypatch.setenv("DELTA_MAX_PREVIEW_CHARS", "10000")
        monkeypatch.setenv("DELTA_MAX_RENDER_LINES", "100000")
        monkeypatch.setenv("DELTA_REFRESH_INTERVAL", "60.0")
        monkeypatch.setenv("DELTA_DEBOUNCE_MS", "2000")
        monkeypatch.setenv("DELTA_NETWORK_TIMEOUT", "300")
        monkeypatch.setenv("DELTA_CONTEXT_LINES", "10")

        config = Config()
        assert config.max_files == 50000
        assert config.max_preview_chars == 10000
        assert config.max_render_lines == 100000
        assert config.refresh_interval == 60.0
        assert config.debounce_ms == 2000
        assert config.network_timeout == 300
        assert config.context_lines == 10

    def test_config_repr(self):
        """Test the string representation of config."""
        config = Config()
        repr_str = repr(config)

        assert "Config(" in repr_str
        assert "max_files=5000" in repr_str
        assert "max_preview_chars=500" in repr_str
        assert "max_render_lines=5000" in repr_str
        assert "refresh_interval=1.0" in repr_str
        assert "debounce_ms=300" in repr_str
        assert "network_timeout=30" in repr_str
        assert "context_lines=3" in repr_str

    def test_config_error_inheritance(self):
        """Test that ConfigError is properly defined."""
        assert issubclass(ConfigError, Exception)

        # Test that it can be raised and caught
        with pytest.raises(ConfigError):
            raise ConfigError("Test error")
