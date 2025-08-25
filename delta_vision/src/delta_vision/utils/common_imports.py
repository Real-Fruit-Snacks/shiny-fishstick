"""Common widget and utility imports for Delta Vision screens.

This module consolidates frequently used imports to reduce duplication
across screen files. Instead of repeating the same import statements,
screens can import collections from this module.
"""

# Textual core imports - used by all screens
# Rich text formatting - used for styled output
from rich.text import Text
from textual.app import ComposeResult

# Common containers - used by most screens
from textual.containers import Center, Horizontal, Vertical
from textual.screen import Screen

# Common widgets - frequently used across screens
from textual.widgets import Button, DataTable, Input, ListItem, ListView, Static, Tab, Tabs

# Delta Vision imports commonly used together
from delta_vision.utils.logger import log
from delta_vision.widgets.footer import Footer
from delta_vision.widgets.header import Header

# Collections for different screen types
__all__ = [
    'COMMON_TEXTUAL_IMPORTS',
    'TABLE_SCREEN_IMPORTS',
    'LAYOUT_IMPORTS',
    'ALL_WIDGETS',
    'ComposeResult',
    'Screen',
    'Horizontal',
    'Vertical',
    'Center',
    'Button',
    'DataTable',
    'Input',
    'ListItem',
    'ListView',
    'Static',
    'Tab',
    'Tabs',
    'Text',
    'log',
    'Footer',
    'Header',
]

# Import collections for convenience
COMMON_TEXTUAL_IMPORTS = (ComposeResult, Screen, Horizontal, Vertical, Static)

TABLE_SCREEN_IMPORTS = (ComposeResult, Screen, DataTable, Horizontal, Vertical, Static, Button, Input)

LAYOUT_IMPORTS = (Center, Horizontal, Vertical)

ALL_WIDGETS = (Button, DataTable, Input, ListItem, ListView, Static, Tab, Tabs)
