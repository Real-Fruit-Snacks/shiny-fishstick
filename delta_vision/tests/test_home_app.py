"""Tests for the HomeApp class extraction.

This module tests that the HomeApp class works correctly after being 
extracted from the main() function to module level.
"""

import tempfile
from unittest.mock import Mock, patch

import pytest

# Mock textual components for testing without full dependencies
@pytest.fixture(autouse=True)
def mock_textual():
    """Mock textual components for testing."""
    with patch('delta_vision.entry_points.App') as mock_app, \
         patch('delta_vision.entry_points.MainScreen') as mock_main_screen, \
         patch('delta_vision.entry_points.register_all_themes') as mock_register:
        
        mock_app_instance = Mock()
        mock_app.return_value = mock_app_instance
        
        yield {
            'app': mock_app,
            'app_instance': mock_app_instance,
            'main_screen': mock_main_screen,
            'register_themes': mock_register
        }


def test_homeapp_import():
    """Test that HomeApp can be imported successfully."""
    from delta_vision.entry_points import HomeApp
    assert HomeApp is not None


def test_homeapp_instantiation(mock_textual):
    """Test that HomeApp can be instantiated with parameters."""
    from delta_vision.entry_points import HomeApp
    
    app = HomeApp(
        folder_path="/test/new",
        old_folder_path="/test/old", 
        keywords_path="/test/keywords.md"
    )
    
    assert app.folder_path == "/test/new"
    assert app.old_folder_path == "/test/old"
    assert app.keywords_path == "/test/keywords.md"


def test_homeapp_default_parameters(mock_textual):
    """Test that HomeApp works with default None parameters."""
    from delta_vision.entry_points import HomeApp
    
    app = HomeApp()
    
    assert app.folder_path is None
    assert app.old_folder_path is None  
    assert app.keywords_path is None


def test_homeapp_has_required_attributes(mock_textual):
    """Test that HomeApp has required class attributes."""
    from delta_vision.entry_points import HomeApp
    
    assert hasattr(HomeApp, 'BINDINGS')
    assert hasattr(HomeApp, 'on_mount')
    assert HomeApp.BINDINGS == []


def test_homeapp_on_mount_calls_expected_methods(mock_textual):
    """Test that on_mount calls expected initialization methods."""
    from delta_vision.entry_points import HomeApp
    
    app = HomeApp(
        folder_path="/test/new",
        old_folder_path="/test/old",
        keywords_path="/test/keywords.md"
    )
    
    # Mock the app attributes
    app.default_theme = None
    app.theme = None
    app.push_screen = Mock()
    
    # Call on_mount
    app.on_mount()
    
    # Verify theme registration was attempted
    mock_textual['register_themes'].assert_called_once_with(app)
    
    # Verify MainScreen was created with correct parameters
    mock_textual['main_screen'].assert_called_once_with("/test/new", "/test/old", "/test/keywords.md")
    
    # Verify push_screen was called
    app.push_screen.assert_called_once()


def test_homeapp_on_mount_handles_theme_errors(mock_textual):
    """Test that on_mount handles theme registration errors gracefully."""
    from delta_vision.entry_points import HomeApp
    
    # Make register_all_themes raise an exception
    mock_textual['register_themes'].side_effect = Exception("Theme error")
    
    app = HomeApp()
    app.default_theme = None
    app.theme = None
    app.push_screen = Mock()
    
    # Should not raise an exception
    app.on_mount()
    
    # Should still try to set default theme and push screen
    app.push_screen.assert_called_once()


def test_homeapp_sets_default_theme(mock_textual):
    """Test that on_mount sets the default theme correctly."""
    from delta_vision.entry_points import HomeApp
    
    app = HomeApp()
    app.push_screen = Mock()
    
    # Call on_mount
    app.on_mount()
    
    # Verify default theme is set
    assert app.default_theme == "ayu-mirage"
    assert app.theme == "ayu-mirage"


def test_homeapp_theme_setting_handles_errors(mock_textual):
    """Test that theme setting handles errors gracefully."""
    from delta_vision.entry_points import HomeApp
    
    app = HomeApp()
    app.push_screen = Mock()
    
    # Mock theme setting to raise an exception
    def theme_setter_error(value):
        raise Exception("Theme setting error")
    
    type(app).theme = property(lambda self: None, theme_setter_error)
    
    # Should not raise an exception
    app.on_mount()
    
    # Should still push the main screen
    app.push_screen.assert_called_once()


class TestHomeAppIntegration:
    """Integration tests for HomeApp with actual file paths."""
    
    def test_homeapp_with_temporary_paths(self, mock_textual):
        """Test HomeApp with actual temporary file paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            from delta_vision.entry_points import HomeApp
            
            app = HomeApp(
                folder_path=temp_dir,
                old_folder_path=temp_dir,
                keywords_path=None
            )
            
            assert app.folder_path == temp_dir
            assert app.old_folder_path == temp_dir
            assert app.keywords_path is None
    
    def test_homeapp_inheritance(self, mock_textual):
        """Test that HomeApp correctly inherits from App."""
        from delta_vision.entry_points import HomeApp
        
        # Should be able to instantiate and call parent methods
        app = HomeApp()
        
        # Should have inherited from mock App
        mock_textual['app'].assert_called_once()


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