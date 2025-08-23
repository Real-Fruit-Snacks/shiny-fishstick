from __future__ import annotations

import os
import threading
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .logger import log


class _DebouncedHandler(FileSystemEventHandler):
    def __init__(self, callback: Callable[[], None], debounce_ms: int = 100) -> None:
        self._callback = callback
        self._debounce = max(0, int(debounce_ms)) / 1000.0
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def _schedule(self) -> None:
        def fire() -> None:
            try:
                self._callback()
            except (RuntimeError, OSError) as e:
                log(f"[WATCHDOG] Callback failed: {e}")
                pass

        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce, fire)
            self._timer.daemon = True
            self._timer.start()

    def cancel(self) -> None:
        with self._lock:
            if self._timer is not None:
                try:
                    self._timer.cancel()
                except (RuntimeError, OSError) as e:
                    log(f"[WATCHDOG] Timer cancel failed: {e}")
                    pass
                self._timer = None

    # Watchdog hooks
    def on_any_event(self, event: FileSystemEvent):  # type: ignore[override]
        # Only react to events that likely change file contents or names.
        et = getattr(event, "event_type", "")
        if et not in ("modified", "created", "moved", "deleted"):
            return
        try:
            log("[WATCHDOG] Event:", et, "on", getattr(event, "src_path", ""))
        except (OSError, RuntimeError) as e:
            log(f"[WATCHDOG] Event logging failed: {e}")
            pass
        self._schedule()


def start_observer(
    path: str, on_change: Callable[[], None], *, recursive: bool = False, debounce_ms: int = 100
) -> tuple[object, Callable[[], None]]:
    """
    Start a filesystem observer and return (observer, stop_fn).

    stop_fn() is idempotent and cancels any pending debounced callbacks.
    """
    abs_path = os.path.abspath(path)
    log(f"[WATCHDOG] Watching path: {abs_path}")
    handler = _DebouncedHandler(on_change, debounce_ms=debounce_ms)
    observer = Observer()
    observer.schedule(handler, abs_path, recursive=recursive)
    observer.start()

    _stopped = False
    _lock = threading.Lock()

    def stop() -> None:
        nonlocal _stopped
        with _lock:
            if _stopped:
                return
            _stopped = True
        try:
            handler.cancel()
        except (RuntimeError, OSError) as e:
            log(f"[WATCHDOG] Handler cancel failed: {e}")
            pass
        try:
            observer.stop()
        except (RuntimeError, OSError) as e:
            log(f"[WATCHDOG] Observer stop failed: {e}")
            pass
        try:
            observer.join(timeout=0.5)
        except (RuntimeError, OSError) as e:
            log(f"[WATCHDOG] Observer join failed: {e}")
            pass

    return observer, stop
