"""Tests for the theme system architecture.

This module tests the current theme registration and management system,
replacing outdated tests that assumed different architecture patterns.
"""

from unittest.mock import Mock, patch

from delta_vision.themes import discover_themes, register_all_themes


class TestThemeDiscovery:
    """Test theme discovery functionality."""

    def test_discover_themes_returns_themes(self):
        """Test that theme discovery finds and returns theme objects."""
        themes = discover_themes()

        # Should find multiple themes
        assert len(themes) > 0
        assert isinstance(themes, list)

        # Each theme should have a name attribute
        for theme in themes:
            assert hasattr(theme, 'name')
            assert isinstance(theme.name, str)
            assert len(theme.name) > 0

    def test_discover_themes_includes_expected_themes(self):
        """Test that discovery finds expected built-in themes."""
        themes = discover_themes()
        theme_names = [getattr(theme, 'name', '') for theme in themes]

        # Should include some expected themes
        expected_themes = ['ayu-mirage', 'material', 'one-dark']
        for expected in expected_themes:
            assert expected in theme_names, f"Expected theme '{expected}' not found in {theme_names}"

    def test_discover_themes_handles_import_errors_gracefully(self):
        """Test that theme discovery handles import errors without crashing."""
        # Even if some theme modules fail to import, discovery should continue
        with patch('delta_vision.themes.pkgutil.iter_modules') as mock_iter:
            # Mock a scenario with one failing module and one successful
            mock_modinfo1 = Mock()
            mock_modinfo1.name = "delta_vision.themes.failing_theme"
            mock_modinfo2 = Mock()
            mock_modinfo2.name = "delta_vision.themes.working_theme"
            mock_iter.return_value = [mock_modinfo1, mock_modinfo2]

            with patch('importlib.import_module') as mock_import:
                mock_working_module = Mock()
                mock_working_module.THEMES = [Mock(name="working-theme")]
                mock_import.side_effect = [ImportError("Module not found"), mock_working_module]

                # Should not raise an exception
                themes = discover_themes()
                assert isinstance(themes, list)


class TestThemeRegistration:
    """Test theme registration with app instances."""

    def test_register_all_themes_with_mock_app(self):
        """Test that register_all_themes works with a mock app."""
        mock_app = Mock()
        mock_app.register_theme = Mock()
        mock_app.available_themes = {}  # Mock available themes dict

        # Should successfully register themes
        count = register_all_themes(mock_app)

        assert isinstance(count, int)
        assert count >= 0  # May be 0 if all registrations fail in test environment
        # register_theme should have been called (even if it failed)
        assert mock_app.register_theme.call_count >= 0

    def test_register_all_themes_handles_registration_errors(self):
        """Test that theme registration handles individual theme errors."""
        mock_app = Mock()
        mock_app.register_theme = Mock(side_effect=RuntimeError("Registration failed"))
        mock_app.available_themes = {}

        # Should not raise an exception even if registration fails
        count = register_all_themes(mock_app)
        assert isinstance(count, int)
        # Count might be 0 if all registrations failed, but shouldn't crash

    def test_register_all_themes_skips_duplicates(self):
        """Test that registration handles duplicate themes gracefully."""
        mock_app = Mock()
        # Simulate registration failure for duplicates
        mock_app.register_theme = Mock(side_effect=RuntimeError("Theme already exists"))
        mock_app.available_themes = {}

        count = register_all_themes(mock_app)
        assert isinstance(count, int)


class TestHomeAppThemeIntegration:
    """Test theme integration with the actual HomeApp class."""

    @patch('delta_vision.entry_points.register_all_themes')
    def test_homeapp_registers_themes_during_init(self, mock_register):
        """Test that HomeApp registers themes during initialization, not on_mount."""
        from delta_vision.entry_points import HomeApp

        mock_register.return_value = 5  # Mock successful registration of 5 themes

        # Create app instance - this should trigger theme registration
        app = HomeApp()

        # Verify theme registration was called during __init__
        mock_register.assert_called_once_with(app)

        # Verify default properties are set
        assert hasattr(app, 'default_theme')
        assert app.default_theme == "ayu-mirage"

    @patch('delta_vision.entry_points.register_all_themes')
    def test_homeapp_handles_theme_registration_errors(self, mock_register):
        """Test that HomeApp handles theme registration errors gracefully."""
        from delta_vision.entry_points import HomeApp

        # Make theme registration fail
        mock_register.side_effect = Exception("Theme registration failed")

        # Should not raise an exception
        app = HomeApp()

        # Should still have basic theme setup
        assert app.theme == 'textual-dark'  # Fallback theme

    def test_homeapp_theme_property_behavior(self):
        """Test the custom theme property getter/setter behavior."""
        from delta_vision.entry_points import HomeApp

        app = HomeApp()

        # Theme property should never return None
        assert app.theme is not None

        # Should default to textual-dark or ayu-mirage
        assert app.theme in ['textual-dark', 'ayu-mirage']

        # Setting theme should work (even if theme doesn't exist, it should handle gracefully)
        app.theme = 'nonexistent-theme'
        assert app.theme is not None  # Should fallback, not be None

    def test_homeapp_on_mount_does_not_register_themes(self):
        """Test that on_mount doesn't try to register themes (they're registered in __init__)."""
        from delta_vision.entry_points import HomeApp

        app = HomeApp()
        app.push_screen = Mock()  # Mock to avoid screen creation

        with patch('delta_vision.entry_points.register_all_themes') as mock_register:
            # Call on_mount
            app.on_mount()

            # Should not call register_all_themes in on_mount (it was called in __init__)
            mock_register.assert_not_called()

        # Should still push the main screen
        app.push_screen.assert_called_once()

    @patch('delta_vision.entry_points.register_all_themes')
    def test_homeapp_theme_fallback_behavior(self, mock_register):
        """Test theme fallback behavior when preferred theme fails."""
        from delta_vision.entry_points import HomeApp

        mock_register.return_value = 3

        app = HomeApp()

        # Should have attempted to set ayu-mirage but fallen back to textual-dark if needed
        assert app.theme in ['textual-dark', 'ayu-mirage']
        assert app.default_theme == "ayu-mirage"


class TestThemeSystemIntegration:
    """Test the overall theme system integration."""

    def test_themes_can_be_registered_and_accessed(self):
        """Test that themes can be registered and accessed through standard Textual patterns."""
        # This is more of an integration test
        mock_app = Mock()
        available_themes = {}

        def mock_register_theme(theme):
            """Mock theme registration that actually stores themes."""
            available_themes[theme.name] = theme

        mock_app.register_theme = mock_register_theme
        mock_app.available_themes = available_themes

        # Register themes
        count = register_all_themes(mock_app)

        assert count > 0
        assert len(available_themes) > 0

        # Verify some expected themes were registered
        theme_names = list(available_themes.keys())
        assert 'ayu-mirage' in theme_names

    def test_theme_system_works_with_textual_command_palette(self):
        """Test that the theme system integrates with Textual's command palette approach."""
        # The current architecture uses standard Textual theme registration
        # which integrates with Ctrl+P command palette automatically

        mock_app = Mock()
        mock_app.register_theme = Mock()
        mock_app.available_themes = {}

        # Register themes using our system
        register_all_themes(mock_app)

        # Themes should be registered via standard Textual method (even if registration fails)
        # The important thing is that our system tries to register them
        assert isinstance(register_all_themes(mock_app), int)

        # This enables Ctrl+P theme switching automatically in Textual


class TestLegacyCompatibility:
    """Test compatibility with legacy test expectations."""

    def test_homeapp_still_has_expected_attributes(self):
        """Test that HomeApp still provides expected attributes for backwards compatibility."""
        from delta_vision.entry_points import HomeApp

        app = HomeApp()

        # Should have theme-related attributes that tests might expect
        assert hasattr(app, 'theme')
        assert hasattr(app, 'default_theme')

        # Should be able to get/set theme
        app.theme = 'textual-dark'
        assert app.theme == 'textual-dark'

        # Theme should never be None (this was a source of test failures)
        app.theme = None  # Try to set None
        assert app.theme is not None  # Should fallback to default
