from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from delta_vision.utils.logger import log


class DirectoryChangeHandler(FileSystemEventHandler):
    def __init__(self, callback, verbose: bool = False):
        self.callback = callback
        self.verbose = verbose

    def on_any_event(self, event):
        # Headless-safe logging (gate spam unless verbose)
        if self.verbose:
            log("[WATCHDOG] Event:", getattr(event, "event_type", "?"), "on", getattr(event, "src_path", ""))
        try:
            self.callback()
        except (RuntimeError, OSError) as e:
            # Don't let exceptions in callbacks kill the observer thread
            log(f"[WATCHDOG] Callback failed: {e}")
            pass


def start_watchdog(path, callback, *, verbose: bool = False):
    import os

    abs_path = os.path.abspath(path)
    # Headless-safe logging
    if verbose:
        log(f"[WATCHDOG] Watching path: {abs_path}")
    event_handler = DirectoryChangeHandler(callback, verbose=verbose)
    observer = Observer()
    try:
        observer.schedule(event_handler, abs_path, recursive=False)
        observer.start()
    except Exception as e:
        log(f"[WATCHDOG] Failed to start observer for {abs_path}: {e}")

        class _NoOp:
            def stop(self):
                pass

            def join(self, *a, **k):
                pass

        return _NoOp()
    return observer
