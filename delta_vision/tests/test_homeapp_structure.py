"""Tests for HomeApp class structure without requiring textual imports.

This module tests the basic structure and organization of the HomeApp class
after extraction from main() function, using AST parsing instead of imports.
"""

import ast
from pathlib import Path


def test_homeapp_class_exists_at_module_level():
    """Test that HomeApp class is defined at module level."""
    entry_points_path = Path(__file__).parent.parent / "src" / "delta_vision" / "entry_points.py"

    with open(entry_points_path, encoding='utf-8') as f:
        source = f.read()

    tree = ast.parse(source)

    # Find all class definitions at module level
    module_level_classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    class_names = [cls.name for cls in module_level_classes]

    assert "HomeApp" in class_names, f"HomeApp not found in module-level classes: {class_names}"


def test_homeapp_not_defined_inside_main():
    """Test that HomeApp is not defined inside main() function."""
    entry_points_path = Path(__file__).parent.parent / "src" / "delta_vision" / "entry_points.py"

    with open(entry_points_path, encoding='utf-8') as f:
        source = f.read()

    tree = ast.parse(source)

    # Find the main function
    main_func = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            main_func = node
            break

    assert main_func is not None, "main() function not found"

    # Check that no class is defined inside main
    classes_in_main = [node for node in ast.walk(main_func) if isinstance(node, ast.ClassDef)]
    class_names_in_main = [cls.name for cls in classes_in_main]

    assert "HomeApp" not in class_names_in_main, f"HomeApp still defined inside main(): {class_names_in_main}"


def test_homeapp_has_required_methods():
    """Test that HomeApp class has required methods."""
    entry_points_path = Path(__file__).parent.parent / "src" / "delta_vision" / "entry_points.py"

    with open(entry_points_path, encoding='utf-8') as f:
        source = f.read()

    tree = ast.parse(source)

    # Find HomeApp class
    homeapp_class = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "HomeApp":
            homeapp_class = node
            break

    assert homeapp_class is not None, "HomeApp class not found"

    # Check for required methods
    method_names = [node.name for node in homeapp_class.body if isinstance(node, ast.FunctionDef)]

    assert "__init__" in method_names, "HomeApp missing __init__ method"
    assert "on_mount" in method_names, "HomeApp missing on_mount method"


def test_homeapp_has_bindings_attribute():
    """Test that HomeApp class has BINDINGS attribute."""
    entry_points_path = Path(__file__).parent.parent / "src" / "delta_vision" / "entry_points.py"

    with open(entry_points_path, encoding='utf-8') as f:
        source = f.read()

    tree = ast.parse(source)

    # Find HomeApp class
    homeapp_class = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "HomeApp":
            homeapp_class = node
            break

    assert homeapp_class is not None, "HomeApp class not found"

    # Check for BINDINGS class attribute
    assignments = [node for node in homeapp_class.body if isinstance(node, ast.Assign)]
    binding_assigns = []

    for assign in assignments:
        for target in assign.targets:
            if isinstance(target, ast.Name) and target.id == "BINDINGS":
                binding_assigns.append(assign)

    assert len(binding_assigns) > 0, "HomeApp missing BINDINGS class attribute"


def test_main_function_still_exists():
    """Test that main() function still exists."""
    entry_points_path = Path(__file__).parent.parent / "src" / "delta_vision" / "entry_points.py"

    with open(entry_points_path, encoding='utf-8') as f:
        source = f.read()

    tree = ast.parse(source)

    # Find all function definitions at module level
    module_level_functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    function_names = [func.name for func in module_level_functions]

    assert "main" in function_names, f"main() function not found: {function_names}"


def test_imports_moved_to_module_level():
    """Test that necessary imports are at module level."""
    entry_points_path = Path(__file__).parent.parent / "src" / "delta_vision" / "entry_points.py"

    with open(entry_points_path, encoding='utf-8') as f:
        source = f.read()

    tree = ast.parse(source)

    # Collect module-level imports
    module_imports = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            module_imports.extend([alias.name for alias in node.names])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for alias in node.names:
                    module_imports.append(f"{node.module}.{alias.name}")

    # Check for key imports that should be at module level
    expected_imports = [
        "delta_vision.screens.main_screen.MainScreen",
        "delta_vision.themes.register_all_themes",
        "textual.app.App",
    ]

    for expected in expected_imports:
        found = any(expected in imp for imp in module_imports)
        assert found, f"Expected import not found at module level: {expected}"


def test_homeapp_init_parameters():
    """Test that HomeApp.__init__ has expected parameters."""
    entry_points_path = Path(__file__).parent.parent / "src" / "delta_vision" / "entry_points.py"

    with open(entry_points_path, encoding='utf-8') as f:
        source = f.read()

    tree = ast.parse(source)

    # Find HomeApp class and its __init__ method
    homeapp_class = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "HomeApp":
            homeapp_class = node
            break

    assert homeapp_class is not None, "HomeApp class not found"

    init_method = None
    for node in homeapp_class.body:
        if isinstance(node, ast.FunctionDef) and node.name == "__init__":
            init_method = node
            break

    assert init_method is not None, "HomeApp.__init__ method not found"

    # Check parameter names
    param_names = [arg.arg for arg in init_method.args.args]

    expected_params = ["self", "new_folder_path", "old_folder_path", "keywords_path"]
    for expected in expected_params:
        assert expected in param_names, f"Expected parameter not found in __init__: {expected}"


def test_validation_imports_present():
    """Test that validation module imports are present."""
    entry_points_path = Path(__file__).parent.parent / "src" / "delta_vision" / "entry_points.py"

    with open(entry_points_path, encoding='utf-8') as f:
        source = f.read()

    # Check that validation imports are present
    expected_validation_imports = [
        "ValidationError",
        "validate_config_paths",
        "validate_network_config",
        "validate_port",
    ]

    for expected in expected_validation_imports:
        assert expected in source, f"Expected validation import not found: {expected}"


def test_module_structure_correct():
    """Test overall module structure is correct."""
    entry_points_path = Path(__file__).parent.parent / "src" / "delta_vision" / "entry_points.py"

    with open(entry_points_path, encoding='utf-8') as f:
        source = f.read()

    tree = ast.parse(source)

    # Count different types of top-level definitions
    imports = len([node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))])
    classes = len([node for node in tree.body if isinstance(node, ast.ClassDef)])
    functions = len([node for node in tree.body if isinstance(node, ast.FunctionDef)])

    # Should have imports, exactly 1 class (HomeApp), and at least 1 function (main)
    assert imports > 0, "No imports found at module level"
    assert classes == 1, f"Expected exactly 1 class, found {classes}"
    assert functions >= 1, f"Expected at least 1 function, found {functions}"
