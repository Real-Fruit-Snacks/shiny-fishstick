import argparse
import asyncio
import os
import sys
import tempfile

from textual.app import App


def main():

    from delta_vision.screens.main_screen import MainScreen
    from delta_vision.themes import register_all_themes

    parser = argparse.ArgumentParser(description="Delta Vision: File Comparison App")
    parser.add_argument('--new', type=str, help='Path to folder for stream page')
    parser.add_argument('--old', type=str, help='Path to second folder to monitor (not used on Stream)')
    parser.add_argument('--keywords', type=str, help='Path to keywords markdown file')
    parser.add_argument(
        '--notes', type=str, help='Path to notes directory or file (defaults to OS temp dir when omitted)'
    )
    parser.add_argument('--server', action='store_true', help='Start as a TCP/WebSocket server')
    parser.add_argument('--client', action='store_true', help='Connect as a network client')
    parser.add_argument('--port', type=int, default=8765, help='Port for server or client connection')
    parser.add_argument('--host', type=str, default='localhost', help='Host for client connection')

    args, unknown = parser.parse_known_args()

    # Fallback to environment variables if arguments are missing (for web/server mode)
    if not args.new:
        args.new = os.environ.get('DELTA_NEW')
    if not args.old:
        args.old = os.environ.get('DELTA_OLD')
    if not args.keywords:
        args.keywords = os.environ.get('DELTA_KEYWORDS')
    if not args.notes:
        args.notes = os.environ.get('DELTA_NOTES')

    # Network/server env overrides
    # Only apply when user didn't explicitly choose a mode
    if not args.server and not args.client:
        mode = (os.environ.get('DELTA_MODE') or '').lower().strip()
        if mode == 'server':
            args.server = True
        elif mode == 'client':
            args.client = True
        else:
            # Back-compat toggles
            if os.environ.get('DELTA_SERVER') in {'1', 'true', 'yes', 'on'}:
                args.server = True
            if os.environ.get('DELTA_CLIENT') in {'1', 'true', 'yes', 'on'}:
                args.client = True

    # Host/Port env overrides: only apply when the CLI didn't specify them
    argv = sys.argv[1:]
    cli_specified_port = any(a == '--port' or a.startswith('--port=') for a in argv)
    cli_specified_host = any(a == '--host' or a.startswith('--host=') for a in argv)

    env_port = os.environ.get('DELTA_PORT')
    if env_port and not cli_specified_port:
        try:
            args.port = int(env_port)
        except ValueError:
            pass
    env_host = os.environ.get('DELTA_HOST')
    if env_host and not cli_specified_host:
        args.host = env_host

    class HomeApp(App):
        BINDINGS = [
            ("ctrl+n", "toggle_notes", "Notes"),
        ]

        def __init__(
            self,
            folder_path=None,
            old_folder_path=None,
            keywords_path=None,
            notes_dir_path=None,
        ):
            super().__init__()
            self.folder_path = folder_path
            self.old_folder_path = old_folder_path
            self.keywords_path = keywords_path
            self._notes = None
            self._notes_reparenting = False  # reentrancy guard
            self._notes_mounted_screen_id = None  # track where the drawer was mounted
            # Determine notes save path from CLI
            DEFAULT_NAME = "DeltaVision_notes.txt"
            save_path = None

            # Interpret --notes as directory or file
            candidate = notes_dir_path
            try:
                if candidate:
                    # Treat as directory if it exists as a dir OR endswith path separator
                    if os.path.isdir(candidate) or candidate.endswith(os.sep):
                        os.makedirs(candidate, exist_ok=True)
                        save_path = os.path.join(candidate, DEFAULT_NAME)
                    else:
                        # If it looks like a file path (has a parent or an extension), use it as a file
                        parent = os.path.dirname(candidate)
                        _root, ext = os.path.splitext(candidate)
                        looks_like_file = bool(ext) or bool(parent)
                        if looks_like_file:
                            if parent:
                                os.makedirs(parent, exist_ok=True)
                            save_path = candidate
                        else:
                            # Fallback: treat as directory
                            os.makedirs(candidate, exist_ok=True)
                            save_path = os.path.join(candidate, DEFAULT_NAME)
            except Exception:
                save_path = None

            # Final fallback to OS temp directory
            if not save_path:
                resolved_dir = tempfile.gettempdir()
                save_path = os.path.join(resolved_dir, DEFAULT_NAME)
            self._notes_save_path = save_path

        def on_mount(self):
            # Auto-register bundled themes from delta_vision.themes
            try:
                register_all_themes(self)
            except Exception:
                pass

            # Set default theme to ayu-mirage
            try:
                self.default_theme = "ayu-mirage"
                self.theme = self.default_theme
            except Exception:
                pass

            # Push main screen first so we can mount the drawer into the active screen
            self.push_screen(MainScreen(self.folder_path, self.old_folder_path, self.keywords_path))
            # Mount a global notes drawer on the current screen
            try:
                from delta_vision.widgets.notes_drawer import NotesDrawer

                self._notes = NotesDrawer(save_path=self._notes_save_path)
                if self.screen:
                    self.screen.mount(self._notes)
                    # Ensure focus remains on the screen when the drawer is closed
                    try:
                        self.screen.focus()
                    except Exception:
                        pass
            except Exception:
                self._notes = None

        def action_toggle_notes(self):
            # Reentrancy / rapid-toggle guard
            if getattr(self, "_notes_reparenting", False):
                return
            self._notes_reparenting = True
            try:
                from delta_vision.widgets.notes_drawer import NotesDrawer
            except Exception:
                self._notes_reparenting = False
                return
            # Create if missing
            if not getattr(self, "_notes", None):
                try:
                    self._notes = NotesDrawer(save_path=self._notes_save_path)
                except Exception:
                    self._notes = None
            notes = getattr(self, "_notes", None)
            if not notes:
                self._notes_reparenting = False
                return
            # Ensure save path is set (in case drawer was created elsewhere)
            try:
                if hasattr(notes, "set_save_path"):
                    notes.set_save_path(self._notes_save_path)
            except Exception:
                pass
            # Ensure it's attached to the current screen and toggle
            try:
                current = self.screen
                parent = getattr(notes, "parent", None)
                mounted_now = False
                # Determine a stable screen identifier
                current_id = None
                try:
                    current_id = getattr(current, "id", None) or id(current)
                except Exception:
                    current_id = id(current) if current is not None else None
                if current is not None and parent is not current:
                    try:
                        notes.remove()
                    except Exception:
                        pass
                    try:
                        current.mount(notes)
                        mounted_now = True
                        self._notes_mounted_screen_id = current_id
                    except Exception:
                        pass
                # If already mounted on this screen, avoid redundant operations
                if current is not None and parent is current and self._notes_mounted_screen_id == current_id:
                    mounted_now = False
                # If we just mounted or reparented, defer toggle until layout refresh
                if mounted_now:
                    self.call_after_refresh(lambda: notes.toggle())
                else:
                    notes.toggle()
            except Exception:
                pass
            # After toggling, if now closed, ensure the screen has focus
            try:
                if notes and not notes.has_class("open") and self.screen:
                    self.screen.focus()
            except Exception:
                pass
            finally:
                self._notes_reparenting = False


    # Determine mode based on flags
    if args.server:
        # Pass only defined values into env so child sessions inherit file paths
        child_env = {k: v for k, v in {
            'DELTA_NEW': args.new,
            'DELTA_OLD': args.old,
            'DELTA_KEYWORDS': args.keywords,
            'DELTA_NOTES': args.notes,
        }.items() if v}
        print(f"Starting server on port {args.port}...")
        # Import here to avoid loading network code for local runs
        from delta_vision.net.server import start_server  # noqa: E402
        asyncio.run(start_server(port=args.port, child_env=child_env))
    elif args.client:
        print(f"Connecting to server at {args.host}:{args.port}...")
        from delta_vision.net.client import start_client  # noqa: E402
        asyncio.run(start_client(host=args.host, port=args.port))
    else:
        # Default to local TUI mode
        HomeApp(
            folder_path=args.new,
            old_folder_path=args.old,
            keywords_path=args.keywords,
            notes_dir_path=args.notes,
        ).run()

# Ensure main() runs both as a script and when run by textual serve
if __name__ == "__main__" or __name__.endswith(".app"):
    main()
