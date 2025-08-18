"""Theme plugins for the app.

Drop Python files in this package that expose either:
- THEMES: list[textual.theme.Theme]
- get_themes() -> list[textual.theme.Theme] | textual.theme.Theme

They will be auto-discovered and registered on startup.
"""

from __future__ import annotations

import importlib
import pkgutil

try:
    from textual.theme import Theme  # type: ignore
except Exception:  # pragma: no cover - textual not loaded yet in some tools
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
        except Exception:
            continue
        try:
            if hasattr(mod, "THEMES"):
                themes.extend(list(mod.THEMES))  # type: ignore
            elif hasattr(mod, "get_themes"):
                got = mod.get_themes()  # type: ignore[attr-defined]
                themes.extend(_coerce_to_list(got))
            elif hasattr(mod, "theme"):
                themes.extend(_coerce_to_list(mod.theme))
        except Exception:
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
        except Exception:
            # Skip duplicates or invalid themes
            pass

    # Fallback: register built-in themes matching file names when module exports are empty
    try:
        existing = set()
        try:
            existing = set(getattr(app, "available_themes", {}).keys())
        except Exception:
            existing = set()
        for modinfo in pkgutil.iter_modules(__path__, prefix=__name__ + "."):
            try:
                stem = modinfo.name.rsplit(".", 1)[-1]
            except Exception:
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
                except Exception:
                    theme_obj = None
                if theme_obj is None:
                    try:
                        if hasattr(app, "search_themes"):
                            # type: ignore[attr-defined]
                            results = app.search_themes(name)
                            if results and name in results:
                                theme_obj = results[name]
                    except Exception:
                        theme_obj = None
                if theme_obj is None:
                    continue
                try:
                    app.register_theme(theme_obj)
                    existing.add(name)
                    count += 1
                    break
                except Exception:
                    pass
    except Exception:
        pass

    return count
