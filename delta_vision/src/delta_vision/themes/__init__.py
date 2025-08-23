"""Theme plugins for the app.

Drop Python files in this package that expose either:
- THEMES: list[textual.theme.Theme]
- get_themes() -> list[textual.theme.Theme] | textual.theme.Theme

They will be auto-discovered and registered on startup.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from delta_vision.utils.logger import log

try:
    from textual.theme import Theme  # type: ignore
except (ImportError, ModuleNotFoundError):  # pragma: no cover - textual not loaded yet in some tools
    log("Failed to import textual.theme.Theme, using fallback object")
    Theme = object  # type: ignore


def _coerce_to_list(obj: Any) -> list[Any]:
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj  # type: ignore
    return [obj]  # type: ignore


def discover_themes() -> list[Any]:
    themes: list[Any] = []
    for modinfo in pkgutil.iter_modules(__path__, prefix=__name__ + "."):
        try:
            mod = importlib.import_module(modinfo.name)
        except (ImportError, ModuleNotFoundError):
            log(f"Failed to import theme module: {modinfo.name}")
            continue
        try:
            if hasattr(mod, "THEMES"):
                themes.extend(list(mod.THEMES))  # type: ignore
            elif hasattr(mod, "get_themes"):
                got = mod.get_themes()  # type: ignore[attr-defined]
                themes.extend(_coerce_to_list(got))
            elif hasattr(mod, "theme"):
                themes.extend(_coerce_to_list(mod.theme))
        except (AttributeError, ValueError, TypeError):
            log(f"Failed to extract themes from module: {modinfo.name}")
            continue
    return themes


def register_all_themes(app: Any) -> int:
    """Register all discovered themes on the provided Textual App - orchestrator for theme registration.

    Returns the number of themes registered.
    """
    count = 0
    count += _register_discovered_themes(app)
    count += _register_fallback_themes(app)
    return count


def _register_discovered_themes(app: Any) -> int:
    """Register themes from module discovery."""
    count = 0
    for theme in discover_themes():
        try:
            app.register_theme(theme)
            count += 1
        except (RuntimeError, ValueError, TypeError):
            # Skip duplicates or invalid themes
            log(f"Failed to register theme: {getattr(theme, 'name', 'unknown')}")
    return count


def _register_fallback_themes(app: Any) -> int:
    """Register built-in themes matching file names when module exports are empty."""
    try:
        existing = _get_existing_themes(app)
        return _process_fallback_modules(app, existing)
    except (ImportError, AttributeError):
        log("Failed during fallback theme discovery and registration")
        return 0


def _get_existing_themes(app: Any) -> set[str]:
    """Get set of existing theme names from the app."""
    try:
        return set(getattr(app, "available_themes", {}).keys())
    except AttributeError:
        log("Failed to get existing themes from app, using empty set")
        return set()


def _process_fallback_modules(app: Any, existing: set[str]) -> int:
    """Process all modules for fallback theme registration."""
    count = 0
    for modinfo in pkgutil.iter_modules(__path__, prefix=__name__ + "."):
        stem = _extract_module_stem(modinfo)
        if stem:
            count += _try_register_theme_variants(app, stem, existing)
    return count


def _extract_module_stem(modinfo: Any) -> str | None:
    """Extract module stem name, skipping invalid or private modules."""
    try:
        stem = modinfo.name.rsplit(".", 1)[-1]
    except (ValueError, IndexError):
        log(f"Failed to extract module stem from: {modinfo.name}")
        return None

    if stem.startswith("__"):
        return None

    return stem


def _try_register_theme_variants(app: Any, stem: str, existing: set[str]) -> int:
    """Try to register theme variants (with _ and - names)."""
    name_candidates: list[str] = [stem, stem.replace("_", "-")]

    for name in name_candidates:
        if name in existing:
            continue

        if _try_register_single_theme(app, name, existing):
            return 1  # Successfully registered, stop trying variants

    return 0


def _try_register_single_theme(app: Any, name: str, existing: set[str]) -> bool:
    """Try to register a single theme by name."""
    theme_obj = _find_theme_object(app, name)

    if theme_obj is None:
        return False

    return _register_theme_object(app, theme_obj, name, existing)


def _find_theme_object(app: Any, name: str) -> Any:
    """Find theme object by name using various app methods."""
    # Try get_theme first
    theme_obj = _try_get_theme(app, name)
    if theme_obj:
        return theme_obj

    # Try search_themes as fallback
    return _try_search_themes(app, name)


def _try_get_theme(app: Any, name: str) -> Any:
    """Try to get theme using app.get_theme method."""
    try:
        if hasattr(app, "get_theme"):
            return app.get_theme(name)  # type: ignore[attr-defined]
    except (AttributeError, ValueError, TypeError):
        log.debug(f"Failed to get theme by name: {name}")
    return None


def _try_search_themes(app: Any, name: str) -> Any:
    """Try to search for theme using app.search_themes method."""
    try:
        if hasattr(app, "search_themes"):
            results = app.search_themes(name)  # type: ignore[attr-defined]
            if results and name in results:
                return results[name]
    except (AttributeError, ValueError, TypeError):
        log.debug(f"Failed to search themes for: {name}")
    return None


def _register_theme_object(app: Any, theme_obj: Any, name: str, existing: set[str]) -> bool:
    """Register a theme object and update existing themes set."""
    try:
        app.register_theme(theme_obj)
        existing.add(name)
        return True
    except (RuntimeError, ValueError, TypeError):
        log.debug(f"Failed to register fallback theme: {name}")
        return False
