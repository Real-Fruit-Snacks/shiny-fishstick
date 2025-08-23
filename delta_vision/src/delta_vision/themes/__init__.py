"""Theme plugins for the app.

Drop Python files in this package that expose either:
- THEMES: list[textual.theme.Theme]
- get_themes() -> list[textual.theme.Theme] | textual.theme.Theme

They will be auto-discovered and registered on startup.
"""

from __future__ import annotations

import importlib
import pkgutil

from delta_vision.utils.logger import log

try:
    from textual.theme import Theme  # type: ignore
except (ImportError, ModuleNotFoundError):  # pragma: no cover - textual not loaded yet in some tools
    log("Failed to import textual.theme.Theme, using fallback object")
    Theme = object  # type: ignore


def _coerce_to_list(obj):
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj  # type: ignore
    return [obj]  # type: ignore


def discover_themes():
    themes = []
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


def register_all_themes(app) -> int:
    """Register all discovered themes on the provided Textual App.

    Returns the number of themes registered.
    """
    count = 0
    for theme in discover_themes():
        try:
            app.register_theme(theme)
            count += 1
        except (RuntimeError, ValueError, TypeError):
            # Skip duplicates or invalid themes
            log(f"Failed to register theme: {getattr(theme, 'name', 'unknown')}")
            pass

    # Fallback: register built-in themes matching file names when module exports are empty
    try:
        existing = set()
        try:
            existing = set(getattr(app, "available_themes", {}).keys())
        except AttributeError:
            log("Failed to get existing themes from app, using empty set")
            existing = set()
        for modinfo in pkgutil.iter_modules(__path__, prefix=__name__ + "."):
            try:
                stem = modinfo.name.rsplit(".", 1)[-1]
            except (ValueError, IndexError):
                log(f"Failed to extract module stem from: {modinfo.name}")
                continue
            if stem.startswith("__"):
                continue

            name_candidates = [stem, stem.replace("_", "-")]
            for name in name_candidates:
                if name in existing:
                    continue
                theme_obj = None
                try:
                    if hasattr(app, "get_theme"):
                        # type: ignore[attr-defined]
                        theme_obj = app.get_theme(name)
                except (AttributeError, ValueError, TypeError):
                    log(f"Failed to get theme by name: {name}")
                    theme_obj = None
                if theme_obj is None:
                    try:
                        if hasattr(app, "search_themes"):
                            # type: ignore[attr-defined]
                            results = app.search_themes(name)
                            if results and name in results:
                                theme_obj = results[name]
                    except (AttributeError, ValueError, TypeError):
                        log(f"Failed to search themes for: {name}")
                        theme_obj = None
                if theme_obj is None:
                    continue
                try:
                    app.register_theme(theme_obj)
                    existing.add(name)
                    count += 1
                    break
                except (RuntimeError, ValueError, TypeError):
                    log(f"Failed to register fallback theme: {name}")
                    pass
    except (ImportError, AttributeError):
        log("Failed during fallback theme discovery and registration")
        pass

    return count
