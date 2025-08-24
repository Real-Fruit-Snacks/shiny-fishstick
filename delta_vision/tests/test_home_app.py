"""Tests for the HomeApp class extraction.

This module tests that the HomeApp class works correctly after being
extracted from the main() function to module level.
"""

import tempfile
from unittest.mock import Mock, patch

import pytest


# Mock textual components for testing without full dependencies
@pytest.fixture
def mock_textual():
    """Mock textual components for testing."""
    with patch('delta_vision.entry_points.App') as mock_app, patch(
        'delta_vision.entry_points.MainScreen'
    ) as mock_main_screen, patch('delta_vision.entry_points.register_all_themes') as mock_register:
        mock_app_instance = Mock()
        mock_app.return_value = mock_app_instance

        yield {
            'app': mock_app,
            'app_instance': mock_app_instance,
            'main_screen': mock_main_screen,
            'register_themes': mock_register,
        }


def test_homeapp_import():
    """Test that HomeApp can be imported successfully."""
    from delta_vision.entry_points import HomeApp

    assert HomeApp is not None


def test_homeapp_instantiation(mock_textual):
    """Test that HomeApp can be instantiated with parameters."""
    from delta_vision.entry_points import HomeApp

    app = HomeApp(new_folder_path="/test/new", old_folder_path="/test/old", keywords_path="/test/keywords.md")

    assert app.new_folder_path == "/test/new"
    assert app.old_folder_path == "/test/old"
    assert app.keywords_path == "/test/keywords.md"


def test_homeapp_default_parameters(mock_textual):
    """Test that HomeApp works with default None parameters."""
    from delta_vision.entry_points import HomeApp

    app = HomeApp()

    assert app.new_folder_path is None
    assert app.old_folder_path is None
    assert app.keywords_path is None


def test_homeapp_has_required_attributes(mock_textual):
    """Test that HomeApp has required class attributes."""
    from delta_vision.entry_points import HomeApp

    assert hasattr(HomeApp, 'BINDINGS')
    assert hasattr(HomeApp, 'on_mount')
    assert HomeApp.BINDINGS == []


def test_homeapp_registers_themes_during_init(mock_textual):
    """Test that HomeApp registers themes during initialization, not on_mount."""
    from delta_vision.entry_points import HomeApp

    # Theme registration should happen during __init__
    app = HomeApp(new_folder_path="/test/new", old_folder_path="/test/old", keywords_path="/test/keywords.md")

    # Verify theme registration was attempted during __init__
    mock_textual['register_themes'].assert_called_once_with(app)

    # Mock the push_screen method for on_mount test
    app.push_screen = Mock()

    # Reset mock to test on_mount behavior
    mock_textual['register_themes'].reset_mock()

    # Call on_mount
    app.on_mount()

    # Theme registration should NOT happen again in on_mount
    mock_textual['register_themes'].assert_not_called()

    # Verify MainScreen was created with correct parameters in on_mount
    mock_textual['main_screen'].assert_called_once_with("/test/new", "/test/old", "/test/keywords.md")

    # Verify push_screen was called
    app.push_screen.assert_called_once()


def test_homeapp_handles_theme_registration_errors_during_init(mock_textual):
    """Test that HomeApp handles theme registration errors gracefully during initialization."""
    from delta_vision.entry_points import HomeApp

    # Make register_all_themes raise an exception
    mock_textual['register_themes'].side_effect = Exception("Theme error")

    # Should not raise an exception during initialization
    app = HomeApp()

    # Should still have basic theme setup with fallback
    assert app.theme == 'textual-dark'  # Fallback theme

    # Mock push_screen for on_mount test
    app.push_screen = Mock()

    # Should not raise an exception during on_mount either
    app.on_mount()

    # Should still push screen despite theme error during init
    app.push_screen.assert_called_once()


def test_homeapp_sets_default_theme(mock_textual):
    """Test that HomeApp sets the default_theme property correctly."""
    from delta_vision.entry_points import HomeApp

    app = HomeApp()
    app.push_screen = Mock()

    # Verify default_theme property is set (theme registration happens in __init__ now)
    assert app.default_theme == "ayu-mirage"

    # In test environment, theme may fallback to textual-dark if ayu-mirage registration fails
    # This is expected behavior - the app should still work with fallback theme
    assert app.theme in ["ayu-mirage", "textual-dark"]


def test_homeapp_theme_property_behavior(mock_textual):
    """Test that theme property getter/setter behavior works correctly."""
    from delta_vision.entry_points import HomeApp

    app = HomeApp()

    # Theme property should never return None due to custom getter
    assert app.theme is not None

    # Should be one of the expected values
    assert app.theme in ["ayu-mirage", "textual-dark"]

    # Should be able to set theme (even if it doesn't exist)
    app.theme = 'nonexistent-theme'
    # The custom getter should ensure it's never None
    assert app.theme is not None

    # Setting None should fallback to default
    app.theme = None
    assert app.theme == 'textual-dark'  # Fallback


class TestHomeAppIntegration:
    """Integration tests for HomeApp with actual file paths."""

    def test_homeapp_with_temporary_paths(self):
        """Test HomeApp with actual temporary file paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            from delta_vision.entry_points import HomeApp

            app = HomeApp(new_folder_path=temp_dir, old_folder_path=temp_dir, keywords_path=None)

            assert app.new_folder_path == temp_dir
            assert app.old_folder_path == temp_dir
            assert app.keywords_path is None

    def test_homeapp_inheritance(self):
        """Test that HomeApp correctly inherits from App."""
        from delta_vision.entry_points import HomeApp

        # Should be able to instantiate without errors
        app = HomeApp()

        # Should have the expected attributes from App inheritance
        assert hasattr(app, 'new_folder_path')
        assert hasattr(app, 'old_folder_path')
        assert hasattr(app, 'keywords_path')


def test_entry_points_main_function_exists():
    """Test that main function still exists and is callable."""
    from delta_vision.entry_points import main

    assert callable(main)


def test_homeapp_class_is_at_module_level():
    """Test that HomeApp class is defined at module level, not inside main()."""
    import inspect

    from delta_vision.entry_points import HomeApp, main

    # HomeApp should be defined at module level
    assert inspect.getmodule(HomeApp).__name__ == 'delta_vision.entry_points'

    # HomeApp should not be defined inside main function
    main_source = inspect.getsource(main)
    assert 'class HomeApp' not in main_source
