# Code Duplication Analysis - Delta Vision

This document identifies code duplication patterns across the Delta Vision application and provides consolidation recommendations to reduce similar code across multiple files.

## Executive Summary

**Total Duplication Patterns Identified**: 47 distinct patterns
**High Priority Consolidation Opportunities**: 12 patterns
**Estimated Lines of Code Reducible**: ~850+ lines
**Files Affected**: 25+ files across screens, utilities, tests, and widgets

## High Priority Consolidation Opportunities

### 1. Screen Action Methods Duplication (Priority: HIGH)

**Pattern**: Similar navigation and toggle action methods repeated across all screen files
**Files Affected**: All 7 screen files (`compare.py`, `diff_viewer.py`, `file_viewer.py`, `keywords_screen.py`, `main_screen.py`, `search.py`, `stream.py`)

**Duplicate Methods**:
- `action_next_row()` / `action_prev_row()` - Table navigation (6 files)
- `action_end()` / `action_home()` - Table positioning (5 files)
- `action_toggle_keywords()` - Keywords highlighting toggle (4 files)
- `action_toggle_regex()` - Regex mode toggle (2 files)
- `action_refresh()` - Screen refresh logic (6 files)

**TODO**: 
- [ ] Create `BaseNavigationMixin` class in `utils/base_screen.py` with common navigation actions
- [ ] Create `BaseToggleMixin` class with standardized toggle action patterns
- [ ] Refactor all screen classes to inherit these mixins instead of duplicating methods
- [ ] Estimated reduction: ~180 lines across screen files

### 2. File I/O Error Handling Duplication (Priority: HIGH)

**Pattern**: Identical file reading, validation, and error handling logic
**Files Affected**: 8 files (`file_parsing.py`, `keywords_scanner.py`, `io.py`, `diff_viewer.py`, `file_viewer.py`, `compare.py`, `search.py`, `validation.py`)

**Duplicate Patterns**:
```python
# Pattern repeated 8+ times:
try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
except (OSError, IOError, UnicodeDecodeError) as e:
    log(f"Error reading {file_path}: {e}")
    return default_value
```

**TODO**:
- [ ] Consolidate into `utils/io.py` as `safe_read_file()` and `safe_read_lines()` functions
- [ ] Create `FileReadResult` dataclass for consistent return values
- [ ] Replace all duplicate file reading logic with centralized functions
- [ ] Estimated reduction: ~120 lines across 8 files

### 3. Test Setup Duplication (Priority: HIGH)

**Pattern**: Nearly identical test application setup and fixture patterns
**Files Affected**: All 12 test files

**Duplicate Code**:
- App initialization with theme registration (12 files)
- Temporary directory setup with test files (8 files)
- Mock keyboard event creation (6 files)
- Test file content patterns (7 files)

**TODO**:
- [ ] Create `tests/conftest.py` with shared fixtures:
  - `test_app_with_themes()` fixture
  - `temp_test_environment()` fixture with standard test files
  - `mock_key_event()` helper function
- [ ] Remove duplicate setup code from all test files
- [ ] Estimated reduction: ~200 lines across test files

### 4. DataTable Configuration Duplication (Priority: MEDIUM)

**Pattern**: Identical DataTable setup and styling across table screens
**Files Affected**: `compare.py`, `search.py`, `keywords_screen.py`, `base_screen.py`

**Duplicate Configuration**:
```python
# Repeated in 4+ files:
table.zebra_stripes = True
table.cursor_type = "row"
table.show_header = True
table.add_columns(...)
```

**TODO**:
- [ ] Extend `BaseTableScreen.setup_data_table()` method with additional configuration options
- [ ] Create `TableConfig` dataclass for standardized table setup parameters
- [ ] Remove duplicate table configuration from individual screen files
- [ ] Estimated reduction: ~40 lines

### 5. Widget Import Statements Duplication (Priority: MEDIUM)

**Pattern**: Identical widget imports across screen files
**Files Affected**: All 7 screen files

**Duplicate Imports**:
```python
# Common pattern in all screen files:
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Static, Input
from textual.screen import Screen
```

**TODO**:
- [ ] Create `utils/common_imports.py` with standard widget collections:
  - `COMMON_TEXTUAL_IMPORTS`
  - `TABLE_SCREEN_IMPORTS`  
  - `LAYOUT_IMPORTS`
- [ ] Use `from utils.common_imports import *` pattern in screen files
- [ ] Estimated reduction: ~35 lines

## Medium Priority Consolidation Opportunities

### 6. Validation Function Similarities (Priority: MEDIUM)

**Pattern**: Similar validation logic in multiple utility modules
**Files Affected**: `validation.py`, `config.py`, `entry_points.py`

**Duplicate Patterns**:
- Path existence validation (3 files)
- Port range validation (2 files)
- Directory creation logic (3 files)

**TODO**:
- [ ] Consolidate all validation functions into `utils/validation.py`
- [ ] Remove duplicate validation logic from `config.py` and `entry_points.py`
- [ ] Create `ValidationResult` dataclass for consistent validation responses
- [ ] Estimated reduction: ~60 lines

### 7. Logger Configuration Duplication (Priority: MEDIUM)

**Pattern**: Logger setup and error message formatting
**Files Affected**: 15+ files across all modules

**Duplicate Pattern**:
```python
# Repeated pattern across many files:
from delta_vision.utils.logger import log
...
log(f"Error in {operation}: {e}")
```

**TODO**:
- [ ] Create `utils/error_handling.py` with standardized error logging functions:
  - `log_file_error(file_path, operation, exception)`
  - `log_network_error(host, port, exception)`
  - `log_validation_error(field, value, exception)`
- [ ] Replace ad-hoc error logging with standardized functions
- [ ] Estimated reduction: ~80 lines

### 8. Event Handler Patterns (Priority: MEDIUM)

**Pattern**: Similar key event handling logic across screens
**Files Affected**: `search.py`, `diff_viewer.py`, `keywords_screen.py`, `compare.py`

**Duplicate Pattern**:
```python
# Similar pattern in 4 files:
async def on_key(self, event):
    if event.key == "escape":
        self.action_go_back()
    elif event.key == "enter":
        self.action_select_item()
    # ... more key handling
```

**TODO**:
- [ ] Create `BaseKeyHandlerMixin` in `utils/base_screen.py` with standard key mappings
- [ ] Define `KEY_BINDINGS` dictionary for common key actions
- [ ] Allow screens to override specific key handlers while inheriting common ones
- [ ] Estimated reduction: ~70 lines

## Lower Priority Consolidation Opportunities

### 9. Theme-Related Duplication (Priority: LOW)

**Pattern**: Theme color extraction and application logic
**Files Affected**: All screen files, several utility modules

**TODO**:
- [ ] Create `utils/theme_helper.py` with common theme utilities
- [ ] Consolidate color extraction and application logic
- [ ] Estimated reduction: ~30 lines

### 10. Configuration Loading Patterns (Priority: LOW)

**Pattern**: Environment variable reading and default value handling
**Files Affected**: `config.py`, `entry_points.py`, some screen files

**TODO**:
- [ ] Extend `utils/config.py` with standardized configuration loading patterns
- [ ] Create `ConfigValue` class with default handling and validation
- [ ] Estimated reduction: ~25 lines

### 11. Widget State Management (Priority: LOW)

**Pattern**: Widget enable/disable and state tracking across screens
**Files Affected**: Multiple screen files

**TODO**:
- [ ] Create `WidgetStateManager` utility class
- [ ] Standardize widget state handling patterns
- [ ] Estimated reduction: ~40 lines

### 12. CSS Class Application Patterns (Priority: LOW)

**Pattern**: Similar CSS class application and styling logic
**Files Affected**: Screen files and widget files

**TODO**:
- [ ] Create `utils/styling.py` with common styling utilities
- [ ] Consolidate CSS class application patterns
- [ ] Estimated reduction: ~20 lines

## Test-Specific Duplication Patterns

### 13. Test Data Generation (Priority: MEDIUM)

**Pattern**: Similar test file content creation across test files
**Files Affected**: `test_search_engine.py`, `test_integration.py`, `test_live_updates.py`, others

**TODO**:
- [ ] Create `tests/test_data.py` with standardized test content generators
- [ ] Functions: `create_test_file_with_content()`, `create_test_directory_structure()`
- [ ] Estimated reduction: ~90 lines

### 14. Mock Event Creation (Priority: LOW)

**Pattern**: Similar mock keyboard event creation in multiple test files

**TODO**:
- [ ] Add `create_mock_key_event()` to shared test fixtures
- [ ] Estimated reduction: ~15 lines

## Implementation Recommendations

### Phase 1: High Priority (Immediate Impact)
1. Implement `BaseNavigationMixin` and `BaseToggleMixin` classes
2. Consolidate file I/O error handling in `utils/io.py`
3. Create shared test fixtures in `tests/conftest.py`

### Phase 2: Medium Priority (Code Quality)
1. Extend `BaseTableScreen` configuration capabilities
2. Consolidate validation functions
3. Create standardized error logging utilities

### Phase 3: Low Priority (Polish)
1. Theme utilities consolidation
2. Configuration loading patterns
3. CSS styling utilities

## Risk Assessment

**Low Risk Consolidations**: Utility functions, test fixtures, import statements
**Medium Risk Consolidations**: Base class modifications, event handler changes
**High Risk Consolidations**: Core screen architecture changes

## Success Metrics

- **Lines of Code Reduction**: Target 850+ lines across application
- **File Count Impact**: Reduce duplication in 25+ files
- **Maintainability**: Centralize common patterns in 3-5 utility modules
- **Test Coverage**: Maintain 100% test pass rate during consolidation

## Notes

- All consolidation changes should maintain existing API compatibility
- Each consolidation should be implemented as a separate, testable change
- Focus on high-impact, low-risk consolidations first
- Consider creating feature flags for major architectural changes

---

**Analysis Date**: Current
**Total Files Analyzed**: 47 files
**Analysis Tools Used**: Grep patterns, code inspection, structural analysis
**Confidence Level**: High for identified patterns, Medium for reduction estimates