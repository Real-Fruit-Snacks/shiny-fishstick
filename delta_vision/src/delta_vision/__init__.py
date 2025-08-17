"""delta_vision package initialization.

This module applies a small compatibility patch for Textual on Windows when
running headless tests. Textual's App._press_keys prints debug messages which
are routed through App._print; on some environments, writing to the original
stdout can raise OSError(WinError 6). We wrap App._print to ignore that error
so tests don't fail.
"""

from __future__ import annotations

try:
    from textual.app import App  # type: ignore

    _orig_print = getattr(App, "_print", None)

    if callable(_orig_print):
        # type: ignore[override]
        def _safe_print(self: App, text: str, stderr: bool = False):
            try:
                return _orig_print(self, text, stderr)  # type: ignore[misc]
            except OSError:
                # Ignore invalid handle errors on Windows test environments
                return None
            except Exception:
                # Be conservative: never let printing crash the app
                return None

        try:
            App._print = _safe_print
        except Exception:
            pass
except Exception:
    # If Textual isn't available at import time, skip the patch
    pass
