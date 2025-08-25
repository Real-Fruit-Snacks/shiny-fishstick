"""Theme color calculation utilities for Delta Vision.

This module provides centralized theme color calculation functionality with
caching and consistent styling behavior across the application.
"""

from __future__ import annotations

from .logger import log


class ThemeColorCalculator:
    """Centralized theme color calculation with caching and aesthetic optimization."""

    def __init__(self):
        """Initialize the calculator with empty cache."""
        self._cache = {}

    def get_highlight_style(self, app) -> str:
        """Get theme-appropriate highlight style with best aesthetic and contrast balance.

        Args:
            app: Textual application instance with theme access

        Returns:
            Rich markup string for highlighting (e.g., "bold black on yellow")
        """
        try:
            # Cache key based on current theme name
            theme_name = getattr(app, 'theme', 'default') if app else 'default'
            cache_key = f"highlight_{theme_name}"

            # Return cached result if available
            if cache_key in self._cache:
                return self._cache[cache_key]

            # Calculate and cache new result
            style = self._calculate_highlight_style(app)
            self._cache[cache_key] = style
            return style

        except Exception as e:
            log(f"Failed to get theme highlight style: {e}")
            return self._get_ultimate_fallback()

    def _calculate_highlight_style(self, app) -> str:
        """Calculate the best highlight style for the current theme."""
        try:
            # Get current theme object
            current_theme = app.get_theme(app.theme) if app else None

            if current_theme:
                # Try theme colors in order of preference for highlighting
                # Avoid harsh warning/error colors, prefer softer accent/secondary colors
                candidate_colors = [
                    current_theme.accent,  # Usually a pleasant accent color
                    current_theme.secondary,  # Secondary theme color
                    current_theme.primary,  # Primary theme color
                    current_theme.success,  # Success color (often green)
                    current_theme.warning,  # Warning color (yellow/orange) - last resort
                ]

                # Find the first color that provides good contrast and aesthetics
                for bg_color in candidate_colors:
                    if bg_color:
                        # Calculate contrast and pick best text color
                        fg_color = self._get_readable_text_color(bg_color)

                        # Avoid harsh combinations (white text on very bright colors)
                        if self._is_good_highlight_combination(bg_color, fg_color):
                            return f"bold {fg_color} on {bg_color}"

                # If no good combination found, fall back to theme-specific fallback
                return self._get_theme_fallback_style(current_theme)

        except (AttributeError, ValueError) as e:
            log(f"Failed to calculate theme colors for highlighting: {e}")

        # Ultimate fallback to guaranteed readable style
        return self._get_ultimate_fallback()

    def _get_readable_text_color(self, bg_hex: str) -> str:
        """Calculate the most readable text color (black or white) for given background.

        Args:
            bg_hex: Background color in hex format (#RRGGBB)

        Returns:
            Hex color string for optimal text contrast
        """
        try:
            luminance = self._get_luminance(bg_hex)

            # Use white text on dark backgrounds, black text on light backgrounds
            # Threshold of 0.5 provides good contrast in most cases
            return "#FFFFFF" if luminance < 0.5 else "#000000"

        except (ValueError, IndexError) as e:
            log(f"Failed to calculate readable text color for {bg_hex}: {e}")
            # Fallback to black (safe for most yellow/orange backgrounds)
            return "#000000"

    def _is_good_highlight_combination(self, bg_color: str, fg_color: str) -> bool:
        """Check if a background/foreground color combination is aesthetically pleasing.

        Args:
            bg_color: Background color in hex format
            fg_color: Foreground color in hex format

        Returns:
            True if the combination provides good contrast and aesthetics
        """
        try:
            # Get luminance of background color
            bg_luminance = self._get_luminance(bg_color)

            # Avoid very bright backgrounds with white text (harsh to read)
            if fg_color == "#FFFFFF" and bg_luminance > 0.7:
                return False

            # Avoid very dark backgrounds with black text (poor contrast)
            if fg_color == "#000000" and bg_luminance < 0.3:
                return False

            # Otherwise it's a good combination
            return True

        except (ValueError, IndexError):
            # If we can't determine, assume it's okay
            return True

    def _get_luminance(self, hex_color: str) -> float:
        """Calculate the luminance of a hex color using sRGB gamma correction.

        Args:
            hex_color: Color in hex format (#RRGGBB)

        Returns:
            Luminance value between 0.0 (black) and 1.0 (white)
        """
        try:
            hex_color = hex_color.lstrip('#')
            r = int(hex_color[0:2], 16) / 255.0
            g = int(hex_color[2:4], 16) / 255.0
            b = int(hex_color[4:6], 16) / 255.0

            # Gamma correction for sRGB
            def gamma_correct(c):
                return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

            r_linear = gamma_correct(r)
            g_linear = gamma_correct(g)
            b_linear = gamma_correct(b)

            # Calculate luminance using standard coefficients
            return 0.2126 * r_linear + 0.7152 * g_linear + 0.0722 * b_linear

        except (ValueError, IndexError):
            return 0.5  # Medium luminance fallback

    def _get_theme_fallback_style(self, theme) -> str:
        """Get a theme-appropriate fallback highlight style when no theme colors work well.

        Args:
            theme: Current theme object

        Returns:
            Rich markup string for fallback highlighting
        """
        try:
            # For dark themes, use a subtle light background with dark text
            if getattr(theme, 'dark', True):  # Default to dark theme behavior
                return "bold #1F2430 on #CCCAC2"  # Dark text on light background
            else:
                # For light themes, use a subtle dark background with light text
                return "bold #CCCAC2 on #1F2430"  # Light text on dark background

        except (AttributeError, ValueError):
            return self._get_ultimate_fallback()

    def _get_ultimate_fallback(self) -> str:
        """Get the ultimate fallback style that works in all situations."""
        return "bold black on yellow"

    def clear_cache(self):
        """Clear the style cache to force recalculation."""
        self._cache.clear()


# Global instance for convenience
theme_calculator = ThemeColorCalculator()


def get_theme_highlight_style(app) -> str:
    """Convenience function for getting theme highlight style.

    Args:
        app: Textual application instance

    Returns:
        Rich markup string for highlighting
    """
    return theme_calculator.get_highlight_style(app)
