# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Testing
```bash
# Activate virtual environment first
source .venv/bin/activate

# Run all tests (from repo root, configured in pytest.ini)
pytest tests/ -q

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_keywords_parser.py

# Run specific test function  
pytest tests/test_validation.py::test_function_name

# Test core functionality only
pytest tests/test_validation.py tests/test_keywords_parser.py -v

# Current test status: All tests pass consistently
```

### Code Quality
```bash
# Lint and format with ruff (configured in pyproject.toml)
ruff check .
ruff check --fix .
ruff format .

# Apply unsafe fixes for whitespace issues
ruff check --fix --unsafe-fixes .

# Check before committing (from repo root)  
ruff check . && ruff format --check .

# Current status: Excellent code quality maintained via ruff
```

### Local Development
```bash
# Install in development mode (from repo root)
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e delta_vision

# Run the application (local TUI mode)
python -m delta_vision --new /path/to/New --old /path/to/Old --keywords /path/to/keywords.md

# Quick test with included sample data
python -m delta_vision --new New/ --old Old/ --keywords keywords.md

# Run as server (spawns PTY sessions per client)
python -m delta_vision --server --port 8765 --new /path/to/New --old /path/to/Old

# Connect as client to remote server
python -m delta_vision --client --host localhost --port 8765

# Debug mode with logging
DEBUG=1 python -m delta_vision --new /path/to/New --old /path/to/Old
# Logs written to /tmp/delta_vision_debug.log

# Environment variable configuration
export DELTA_NEW=/path/to/New
export DELTA_OLD=/path/to/Old
export DELTA_KEYWORDS=/path/to/keywords.md
export DELTA_MODE=server  # or 'client'
export DELTA_HOST=localhost
export DELTA_PORT=8765
export DELTA_CONTEXT_LINES=3  # Lines of context around keyword matches
python -m delta_vision  # Uses env vars
```

### Build and Release
```bash
# Build release artifacts (standalone + app bundles)
bash scripts/make_release.sh

# Individual scripts
bash scripts/make_app_bundle_tar.sh  # Creates embedded venv bundle
bash scripts/make_source_tar.sh       # Creates source distribution

# Quick verification after build
ls -la release/  # Check generated artifacts
```

## Architecture Overview

Delta Vision is a Textual-based TUI application for file comparison and monitoring with networking capabilities.

### Core Components

**Main Application Structure:**
- `delta_vision/src/delta_vision/entry_points.py`: CLI argument parsing, app initialization, mode detection (local/server/client)
- `delta_vision/src/delta_vision/__main__.py`: Module entry point via `python -m delta_vision`
- `HomeApp`: Main Textual application class in entry_points.py
  - Auto-registers themes on mount via themes/__init__.py discovery system

**Screen Architecture:**
- `delta_vision/src/delta_vision/screens/main_screen.py`: Home screen with navigation to feature screens
- `delta_vision/src/delta_vision/screens/compare.py`: Side-by-side folder comparison
- `delta_vision/src/delta_vision/screens/diff_viewer.py`: File diff display with tabs
- `delta_vision/src/delta_vision/screens/search.py`: File content search interface
- `delta_vision/src/delta_vision/screens/stream.py`: Real-time file monitoring with command highlighting
- `delta_vision/src/delta_vision/screens/keywords_screen.py`: Keyword highlighting interface (830 lines, largest screen)
- `delta_vision/src/delta_vision/screens/keywords_parser.py`: Markdown keyword file parser for color/category definitions
- `delta_vision/src/delta_vision/screens/file_viewer.py`: File viewing with syntax highlighting and keyword support
- `delta_vision/src/delta_vision/screens/watchdog_helper.py`: File system watching utilities
- 10 Python files total, 6 CSS files (*.tcss) for styling

**Networking (Server/Client Mode):**
- `delta_vision/src/delta_vision/net/server.py`: WebSocket server that spawns PTY sessions per client (240 lines, refactored)
- `delta_vision/src/delta_vision/net/client.py`: WebSocket client for remote sessions (199 lines, refactored)
- Both use clean orchestrator pattern with focused helper methods (15-18 line main functions)
- Server spawns child processes with inherited DELTA_* environment variables
- Uses PTY for terminal multiplexing and resize handling
- Comprehensive error handling and graceful process termination
- Multi-user remote sessions supported via WebSocket

**Utilities (16 modules in delta_vision/src/delta_vision/utils/):**
- `utils/base_screen.py`: **CRITICAL** - Base screen classes (BaseScreen, BaseTableScreen) providing standardized composition patterns and eliminating structural duplication across all screens
- `utils/watchdog.py`: File system monitoring
- `utils/config.py`: Configuration management with environment variable support
- `utils/fs.py`: File system operations
- `utils/text.py`: Text processing utilities and regex compilation
- `utils/io.py`: Text encoding detection and file reading
- `utils/logger.py`: Enhanced logging system with levels (DEBUG, INFO, WARN, ERROR, CRITICAL), automatic file output when DEBUG=1, cached performance, timestamps, and color support
- `utils/validation.py`: Input validation for paths, ports, hostnames (security-focused, 331 lines)
- `utils/search_engine.py`: Core search functionality separated from UI concerns (177 lines)
- `utils/keywords_scanner.py`: Background keyword scanning with thread-safe operations (273 lines)
- `utils/table_navigation.py`: Reusable table navigation with vim-like key bindings (194 lines)
- `utils/keyword_highlighter.py`: Centralized keyword highlighting with caching and consistent styling
- `utils/file_parsing.py`: File I/O and header parsing utilities (177 lines)
- `utils/diff_engine.py`: Diff computation utilities using Python's difflib (52 lines)
- `utils/screen_navigation.py`: Screen navigation utilities
- `utils/theme_color_calculator.py`: Centralized theme color calculation with caching for search highlighting (203 lines, extracted from search.py complexity)

**UI Components:**
- `delta_vision/src/delta_vision/widgets/header.py`: Application header
- `delta_vision/src/delta_vision/widgets/footer.py`: Application footer with keybindings
- `delta_vision/src/delta_vision/themes/`: Bundled color themes (default: ayu-mirage)
  - Accessible via standard Textual command palette (Ctrl+P)
  - Theme discovery system in `themes/__init__.py` auto-registers available themes
  - 15 theme files: ayu, cyberpunk2077, dainty, hackthebox, hotdog_stand, houston, kanagawa, material, monaspace, one_dark, synthwave84, tomorrow, tomorrow_night, witch_hazel, zenburn

### Key Patterns

**Environment Variable Support:**
- `DELTA_NEW`, `DELTA_OLD`, `DELTA_KEYWORDS`: Path configurations
- `DELTA_MODE`: Set to 'server' or 'client' (overrides CLI)
- `DELTA_HOST`, `DELTA_PORT`: Network configuration
- `DELTA_CONTEXT_LINES`: Lines of context around keyword matches (default: 3)
- `DEBUG=1`: Enable debug logging to /tmp/delta_vision_debug.log
- CLI args take precedence over environment variables

**Screen Architecture (BaseScreen Pattern):**
- **ALL screens inherit from BaseScreen or BaseTableScreen** (utils/base_screen.py)
- BaseScreen provides standard header+content+footer composition
- BaseTableScreen extends BaseScreen with DataTable utilities and navigation
- Screens implement `compose_main_content()` and `get_footer_text()` methods
- Automatic table setup (zebra stripes, row cursor) via BaseTableScreen
- Common actions (action_go_back, safe_set_focus) inherited from base classes
- CSS styling via `*.tcss` files (one per screen/widget)
- Event-driven communication between widgets and screens
- Screen navigation via app.push_screen()/app.pop_screen()

**Stream Screen Performance Optimizations:**
- `KeywordProcessor`: Caches compiled regex patterns between refreshes
- File metadata caching: Single stat() call instead of duplicate isfile()+getmtime()
- Incremental updates: Reuses existing panels when file metadata unchanged
- Widget management: Extracts panel creation/updates to focused methods

**Error Handling Standards:**
- ✅ **ZERO BARE EXCEPT BLOCKS**: All 202+ bare `except Exception:` blocks systematically replaced
- Context-appropriate exception types: `OSError`, `ConnectionError`, `ValueError`, `AttributeError`, etc.
- Uses `utils/logger.py` for consistent error logging across the application
- `ValidationError` from `utils.validation` for user input validation failures  
- Comprehensive path traversal protection and input sanitization in `utils/validation.py`
- Network validation for hostnames and port ranges with security checks
- Only 2 intentional bare except blocks remain in test cleanup code

**Refactoring Patterns:**
- Extract business logic to utility modules (search_engine.py, keywords_scanner.py, etc.)
- Transform massive functions into orchestrator patterns with focused helper methods
- Separate UI concerns from computation logic (diff_engine.py, file_parsing.py)
- Use callback-based architecture for background operations
- Thread-safe operations with proper cleanup patterns

**Build System:**
- Uses Hatch as build backend (`hatchling.build`)
- PyInstaller for standalone binaries (`packaging/deltavision.spec`)
- Embedded venv bundles for dependency-free distribution
- CSS assets (`*.tcss`) included in wheel builds
- Version managed in `src/delta_vision/__about__.py`
- PyInstaller spec in `packaging/deltavision.spec` for standalone binaries

**Testing:**
- pytest with asyncio support (asyncio_mode=auto)
- Tests located in `tests/` directory (12 test files)
- Test paths configured in pytest.ini (excludes build dirs)
- **Test data**: `New/` and `Old/` directories with sample files, `keywords.md` for keyword testing
- **Current status**: All tests consistently pass
- Comprehensive coverage for utilities (validation.py, keywords_parser.py, etc.)
- Smoke tests for main screens and functionality

**Code Style:**
- Ruff for linting and formatting (line length: 120)
- Python 3.8+ compatibility  
- Type hints encouraged but not strictly enforced
- Import sorting via ruff's isort rules
- **Current status**: Excellent code quality maintained via automated linting

### Project Structure
- **Root**: Configuration files, documentation, test data (`New/`, `Old/`, `keywords.md`)
- **delta_vision/src/delta_vision/**: Main source code with screens, utils, themes, widgets, net
- **delta_vision/tests/**: Test suite (12 files)  
- **scripts/**: Build and release scripts (5 shell scripts)
- **delta_vision/packaging/**: PyInstaller configuration

**Current Architecture Status:**
- ✅ **EXCEPTIONAL REFACTORING COMPLETED**: All critical massive functions successfully refactored using orchestrator pattern:
  - `entry_points.py:main()` (106 lines → 7-line orchestrator + 4 helper methods)
  - `compare.py:_scan_and_populate()` (91 lines → 18-line orchestrator + 7 helper methods) 
  - `net/client.py:start_client()` (132 lines → 18-line orchestrator + 6 helper methods)
  - `net/server.py:handle_client()` (117 lines → 15-line orchestrator + 7 helper methods)
  - `search.py:run_search()` (228 lines → 20-line orchestrator + SearchEngine utility)
  - `search.py:on_key()` (92 lines → 15-line orchestrator + 10 helper methods)
  - `keywords_screen.py:_populate_details_for_selected()` (91 lines → 19-line orchestrator + 10 helper methods)
  - `keywords_screen.py:_populate_table()` (81 lines → 19-line orchestrator + 11 helper methods)
  - `diff_viewer.py:on_key()` (86 lines → 20-line orchestrator + 9 helper methods)
  - `keywords_scanner.py:_scan_file()` (depth 8 → depth 3 with 7 helper methods)
  - `keywords_scanner.py:_scan_folder()` (depth 7 → depth 3 with 11 helper methods)
  - `themes/__init__.py:register_all_themes()` (depth 7 → depth 3 with 11 helper methods)
  - `diff_engine.py:compute_diff_rows()` (depth 6 → depth 3 with 13 helper methods)
  - `keywords_screen.py`: 881 lines → 830 lines with KeywordScanner utility extraction
  - `diff_viewer.py`: Major functions refactored with file_parsing.py and diff_engine.py utilities
- ✅ **ALL HIGH PRIORITY ITEMS COMPLETED**: No long functions (>80 lines) remain - all successfully refactored
- ✅ **DEEP NESTING ELIMINATED**: 5 most complex functions (depth 6-8) reduced to depth 2-3
- Current file sizes: `diff_viewer.py` (830 lines), `search.py` (594 lines, reduced from 698 via theme extraction), `keywords_screen.py` (830 lines), `compare.py` (625 lines)
- **ERROR HANDLING**: All 202+ bare except blocks systematically replaced with specific exception handling
- **UTILITY EXTRACTION**: Created focused utility modules (search_engine.py, keywords_scanner.py, diff_engine.py, file_parsing.py, validation.py, table_navigation.py, theme_color_calculator.py)
- **LEGACY CODE CLEANUP**: All legacy compatibility code and unused imports removed for clean, modern codebase
- ✅ **BASE SCREEN ARCHITECTURE**: Complete screen inheritance system implemented - all screens now inherit from BaseScreen/BaseTableScreen, eliminating ~354+ lines of structural duplication with standardized composition patterns
- ✅ **CLIENT/SERVER IMPROVEMENTS**: Comprehensive graceful shutdown handling implemented with proper signal management and connection cleanup
- ✅ **KEYWORDS DEFAULT ENABLED**: File viewer automatically enables keyword highlighting when accessed from keywords/search screens
- ✅ **THEME COLOR OPTIMIZATION**: Extracted complex theme calculation logic from search.py to ThemeColorCalculator utility (203 lines) with performance caching

## Important Development Patterns

### Key Architectural Changes (Recent)
- **BaseScreen System**: All new screens MUST inherit from BaseScreen/BaseTableScreen - this is not optional
- **File Viewer Keywords**: Uses `keywords_enabled=True` parameter when called from keywords/search screens
- **Server/Client Shutdown**: Implements comprehensive signal handling with `_ignore_further_interrupts()` pattern
- **Stream Screen Styling**: Commands displayed with bold text, accent colors, and full-width dividers
- **Consistent Key Bindings**: All toggle actions now use Ctrl+ combinations (Ctrl+K for keywords, Ctrl+R for regex, Ctrl+A for anchor)
- **Dynamic Footer Updates**: Footer text shows toggle states (ON/OFF) and updates immediately when toggled
- **Enhanced Error Handling**: All screens use defensive programming patterns with comprehensive exception handling
- **Clean Project Structure**: Cleanup scripts available (`cleanup.sh`, `cleanup_safe.sh`) to remove ~203MB of build artifacts while preserving essential test data
- **Project Maintenance**: Comprehensive cleanup analysis in `cleanup.md` identifies safe-to-delete files vs essential components
- **Keyword Color Consistency**: All keyword highlighting across screens uses colors from keywords.md as single source of truth (fixed search/viewer inconsistency)
- **Theme Performance**: ThemeColorCalculator provides cached theme color calculations with luminance-based contrast optimization

### Function Refactoring Approach
When refactoring long functions, follow the proven orchestrator patterns:
1. **Orchestrator Pattern**: Transform massive functions into ~20-line orchestrators that call focused helper methods
2. **Utility Extraction**: Move pure business logic to utils/ modules (e.g., search_engine.py, diff_engine.py)
3. **Focused Methods**: Each helper method should have a single clear responsibility (typically 10-30 lines)
4. **Deep Nesting Reduction**: Functions with depth >6 should be decomposed using the orchestrator pattern
5. **Preserve Functionality**: All refactoring must maintain existing behavior and API contracts

### Screen Architecture Guidelines (MANDATORY)
- **MUST inherit from BaseScreen or BaseTableScreen** - never inherit directly from Textual's Screen
- **BaseScreen**: Use for screens without tables (main_screen.py, diff_viewer.py, file_viewer.py)
- **BaseTableScreen**: Use for screens with DataTable widgets (search.py, compare.py, keywords_screen.py)
- **Required methods to implement**:
  - `compose_main_content()` - Define screen-specific layout (instead of overriding compose())
  - `get_footer_text()` - Provide contextual footer text
- **Inherited functionality** (do not reimplement):
  - `self.safe_set_focus(widget)` - Focus management with error handling
  - `action_go_back()` - Consistent back navigation  
  - Standard header/footer composition pattern
  - `_update_footer()` - Call this when toggle states change to refresh footer display
- Each screen should have a single CSS file (*.tcss) for styling
- Extract complex logic to utility modules rather than embedding in screens

### Key Binding and UI Standards
- **Toggle Consistency**: All toggle actions use Ctrl+ combinations for consistency
  - `Ctrl+K`: Keywords/Highlights toggle (file_viewer.py, diff_viewer.py, search.py, stream.py)
  - `Ctrl+R`: Regex toggle (search.py)  
  - `Ctrl+A`: Anchor toggle (stream.py)
- **Footer State Display**: All toggleable features must show current state in footer
  - Format: `"FeatureName: ON"` or `"FeatureName: OFF"`
  - Update immediately when toggle state changes via `_update_footer()`
- **Footer Implementation Pattern**:
  ```python
  def get_footer_text(self) -> str:
      state = "ON" if self.feature_enabled else "OFF"
      return f"[orange1]Ctrl+K[/orange1] Feature: {state}"
  
  def action_toggle_feature(self):
      self.feature_enabled = not self.feature_enabled
      self._update_footer()  # Critical: update footer display
  ```

### Utility Module Patterns
- **Pure Functions**: Prefer stateless functions where possible (diff_engine.py, file_parsing.py)
- **Class-Based**: Use classes for stateful operations (KeywordScanner, SearchEngine, ThemeColorCalculator)
- **Performance Caching**: Implement caching in utilities for expensive operations (ThemeColorCalculator, KeywordHighlighter)
- **Type Safety**: Include type aliases and dataclasses (DiffRow, SearchMatch, SearchConfig)
- **Error Handling**: All utilities must use specific exception types with logging
- **Global Instances**: Provide convenience global instances (theme_calculator, highlighter) with clear cache management

### Testing Strategy
- Utility modules should have comprehensive unit tests (validation.py, keywords_parser.py well-covered)
- Screen functionality tested via smoke tests (some theme-related failures expected)
- Complex business logic (search, diff, keyword scanning) requires focused test coverage
- Use pytest fixtures for common test setup (temporary files, mock data)
- **Test Status**: All tests pass consistently with stable test suite
- Core functionality: Excellent test coverage with stable, reliable test suite

### Distribution and Deployment
- Two artifact types: standalone PyInstaller binaries and embedded venv app bundles
- No external dependencies required for end users
- Server/client architecture supports multi-user remote sessions via WebSocket
- Cross-platform support (Linux, macOS, Windows)
- Build system produces release artifacts in `release/` directory
- GitHub Actions workflow for automated releases

## Keywords File Format

Delta Vision uses markdown files for keyword highlighting configuration:

```markdown
# Security (Red)
malware
phishing  # social engineering

# Networking
TCP
UDP
```

**Rules:**
- Category headers: `# CategoryName (Color)` or `# CategoryName`
- Color in parentheses optional; defaults to theme colors when omitted
- Lines starting with `#` that don't match headers are treated as comments
- Empty categories allowed and retained
- Inline comments after keywords stripped when preceded by whitespace
- Parsed by `delta_vision/src/delta_vision/screens/keywords_parser.py` with comprehensive test coverage

**Color Consistency (Critical):**
- **Keywords.md is the single source of truth** for all keyword colors across the application
- All screens (Search, Viewer, Diff, Stream, Keywords) must use colors from keywords.md
- Search screen uses `highlight_with_color_lookup()` method (same as viewer) to ensure consistency
- Theme-based highlighting only applies to non-keyword search matches
- **Never override keyword colors** with theme colors - they must remain consistent across all screens

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.

      IMPORTANT: this context may or may not be relevant to your tasks. You should not respond to this context unless it is highly relevant to your task.