"""Tests to verify that notes functionality removal was complete and clean.

This module verifies that:
1. No orphaned references to notes functionality remain
2. The application starts without notes-related errors
3. Environment variables no longer include notes references
4. CLI arguments no longer include notes options
"""

import tempfile
from unittest.mock import Mock, patch

import pytest


def test_no_notes_imports_in_entry_points():
    """Test that entry_points.py doesn't import any notes modules."""
    import ast
    import inspect
    
    from delta_vision import entry_points
    
    # Get the source code of the entry_points module
    source = inspect.getsource(entry_points)
    tree = ast.parse(source)
    
    # Collect all import statements
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend([alias.name for alias in node.names])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
                imports.extend([f"{node.module}.{alias.name}" for alias in node.names])
    
    # Check that no notes-related imports exist
    notes_imports = [imp for imp in imports if 'notes' in imp.lower()]
    assert len(notes_imports) == 0, f"Found notes-related imports: {notes_imports}"


def test_no_notes_environment_variables():
    """Test that no notes environment variables are referenced."""
    import ast
    import inspect
    
    from delta_vision import entry_points
    
    source = inspect.getsource(entry_points)
    tree = ast.parse(source)
    
    # Look for environment variable references
    env_vars = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            if (isinstance(node.value, ast.Attribute) and 
                isinstance(node.value.value, ast.Name) and
                node.value.value.id == 'os' and
                node.value.attr == 'environ'):
                if isinstance(node.slice, ast.Constant):
                    env_vars.append(node.slice.value)
        elif isinstance(node, ast.Call):
            if (isinstance(node.func, ast.Attribute) and
                isinstance(node.func.value, ast.Attribute) and
                isinstance(node.func.value.value, ast.Name) and
                node.func.value.value.id == 'os' and
                node.func.value.attr == 'environ' and
                node.func.attr == 'get'):
                if node.args and isinstance(node.args[0], ast.Constant):
                    env_vars.append(node.args[0].value)
    
    # Check that no notes environment variables exist
    notes_env_vars = [var for var in env_vars if 'notes' in var.lower()]
    assert len(notes_env_vars) == 0, f"Found notes environment variables: {notes_env_vars}"


def test_no_notes_cli_arguments():
    """Test that no notes CLI arguments are defined."""
    import ast
    import inspect
    
    from delta_vision import entry_points
    
    source = inspect.getsource(entry_points.main)
    tree = ast.parse(source)
    
    # Look for add_argument calls
    arg_names = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and
            isinstance(node.func, ast.Attribute) and
            node.func.attr == 'add_argument'):
            if node.args and isinstance(node.args[0], ast.Constant):
                arg_names.append(node.args[0].value)
    
    # Check that no notes arguments exist
    notes_args = [arg for arg in arg_names if 'notes' in arg.lower()]
    assert len(notes_args) == 0, f"Found notes CLI arguments: {notes_args}"


def test_no_notes_files_exist():
    """Test that notes-related files have been removed."""
    import os
    from pathlib import Path
    
    # Get the project source directory
    project_root = Path(__file__).parent.parent / "src" / "delta_vision"
    
    # Look for any files with 'notes' in the name
    notes_files = []
    for root, dirs, files in os.walk(project_root):
        for file in files:
            if 'notes' in file.lower():
                notes_files.append(os.path.join(root, file))
    
    assert len(notes_files) == 0, f"Found notes-related files: {notes_files}"


def test_homeapp_class_has_no_notes_references():
    """Test that HomeApp class doesn't reference notes functionality."""
    import ast
    import inspect
    
    from delta_vision.entry_points import HomeApp
    
    source = inspect.getsource(HomeApp)
    
    # Check for notes references in the source
    assert 'notes' not in source.lower(), "Found notes references in HomeApp class"


@patch('delta_vision.entry_points.asyncio.run')
@patch('delta_vision.entry_points.start_server')
def test_server_mode_no_notes_env(mock_start_server, mock_asyncio_run):
    """Test that server mode doesn't pass notes environment variables."""
    from delta_vision.entry_points import main
    
    # Mock sys.argv to simulate server mode
    with patch('delta_vision.entry_points.sys.argv', ['delta_vision', '--server', '--port', '8765']):
        with patch('delta_vision.entry_points.argparse.ArgumentParser.parse_known_args') as mock_parse:
            # Create a mock args object
            mock_args = Mock()
            mock_args.server = True
            mock_args.client = False
            mock_args.port = 8765
            mock_args.new = "/test/new"
            mock_args.old = "/test/old" 
            mock_args.keywords = "/test/keywords.md"
            mock_parse.return_value = (mock_args, [])
            
            # Mock validation functions
            with patch('delta_vision.entry_points.validate_config_paths') as mock_validate_paths, \
                 patch('delta_vision.entry_points.validate_network_config') as mock_validate_network:
                
                mock_validate_paths.return_value = ("/test/new", "/test/old", "/test/keywords.md")
                mock_validate_network.return_value = ("localhost", 8765)
                
                try:
                    main()
                except SystemExit:
                    pass  # Expected for test
                
                # Check that start_server was called
                if mock_start_server.called:
                    call_args = mock_start_server.call_args
                    if 'child_env' in call_args.kwargs:
                        child_env = call_args.kwargs['child_env']
                        # Verify no notes environment variables
                        notes_env_keys = [key for key in child_env.keys() if 'notes' in key.lower()]
                        assert len(notes_env_keys) == 0, f"Found notes env vars in server: {notes_env_keys}"


def test_validation_module_imported_correctly():
    """Test that validation module is imported and used correctly."""
    from delta_vision import entry_points
    
    # Check that validation functions are imported
    assert hasattr(entry_points, 'ValidationError')
    assert hasattr(entry_points, 'validate_config_paths')
    assert hasattr(entry_points, 'validate_network_config')
    assert hasattr(entry_points, 'validate_port')


def test_no_notes_drawer_references():
    """Test that no references to notes_drawer remain in the codebase."""
    import os
    from pathlib import Path
    
    project_root = Path(__file__).parent.parent / "src"
    
    # Search for notes_drawer references in Python files
    notes_drawer_refs = []
    for root, dirs, files in os.walk(project_root):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if 'notes_drawer' in content:
                            notes_drawer_refs.append(file_path)
                except Exception:
                    pass  # Skip files that can't be read
    
    assert len(notes_drawer_refs) == 0, f"Found notes_drawer references in: {notes_drawer_refs}"


def test_main_screen_no_notes_references():
    """Test that MainScreen doesn't have notes references."""
    try:
        from delta_vision.screens.main_screen import MainScreen
        import inspect
        
        source = inspect.getsource(MainScreen)
        
        # Check for notes references (case insensitive)
        notes_lines = [line.strip() for line in source.split('\n') 
                      if 'notes' in line.lower() and not line.strip().startswith('#')]
        
        # Filter out comments and docstrings
        actual_notes_refs = [line for line in notes_lines 
                           if not ('"""' in line or "'''" in line or line.strip().startswith('*'))]
        
        assert len(actual_notes_refs) == 0, f"Found notes references in MainScreen: {actual_notes_refs}"
        
    except ImportError:
        pytest.skip("MainScreen not available for testing")


def test_footer_widget_no_notes_references():
    """Test that footer widget doesn't reference notes functionality."""
    try:
        from delta_vision.widgets.footer import Footer
        import inspect
        
        source = inspect.getsource(Footer)
        
        # Check for notes references
        assert 'notes' not in source.lower(), "Found notes references in Footer widget"
        
    except ImportError:
        pytest.skip("Footer widget not available for testing")