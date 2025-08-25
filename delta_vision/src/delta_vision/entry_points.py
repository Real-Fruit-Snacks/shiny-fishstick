import argparse
import asyncio
import os
import signal
import sys
import time

from textual.app import App

from delta_vision.net.client import start_client
from delta_vision.net.server import start_server
from delta_vision.net.server_config import ServerConfig
from delta_vision.screens.main_screen import MainScreen
from delta_vision.themes import register_all_themes
from delta_vision.utils.config import PathsConfig
from delta_vision.utils.logger import log
from delta_vision.utils.validation import ValidationError, validate_config_paths, validate_network_config, validate_port


def _ignore_further_interrupts():
    """Install a signal handler that ignores further SIGINT signals."""

    def ignore_signal(signum, frame):
        # Silently ignore further interrupts
        pass

    try:
        signal.signal(signal.SIGINT, ignore_signal)
    except (OSError, ValueError):
        # If we can't install the handler, just continue
        pass


class HomeApp(App):
    BINDINGS = []
    DEFAULT_CSS = """
    App {
        background: $surface-darken-3;
    }

    Screen {
        background: $surface-darken-3;
        width: 100%;
        height: 100%;
    }
    """

    @property
    def theme(self):
        """Override theme property to ensure it never returns None."""
        try:
            # Try to get the theme from the parent class
            return super().theme or 'textual-dark'
        except (AttributeError, TypeError):
            # Fallback if theme access fails
            return 'textual-dark'

    @theme.setter
    def theme(self, value):
        """Set theme using Textual's Reactive system."""
        try:
            # Use the base App class to set the theme properly
            from textual.app import App

            App.theme.__set__(self, value or 'textual-dark')
        except (AttributeError, TypeError, ValueError):
            # Fallback to ensure theme is never None
            from textual.app import App

            App.theme.__set__(self, 'textual-dark')
        except Exception:
            # Handle InvalidThemeError and other theme-related errors gracefully
            # This ensures theme changes don't crash the app if theme doesn't exist
            from textual.app import App

            try:
                App.theme.__set__(self, 'textual-dark')
            except Exception:
                # Ultimate fallback - store as instance variable
                self._theme = 'textual-dark'

    def __init__(self, paths_config: PathsConfig):
        """Initialize the main Delta Vision application.

        Args:
            paths_config: Configuration object containing all path settings
        """
        super().__init__()

        # Set theme immediately after super().__init__()
        self.theme = 'textual-dark'

        # Store configuration
        self.paths_config = paths_config

        # Register themes immediately after App initialization
        self._register_themes_safely()

    def _register_themes_safely(self):
        """Register themes safely during initialization.

        This method is called during __init__ after super().__init__() to ensure
        themes are available before on_mount() and other lifecycle methods.
        """
        try:
            register_all_themes(self)
            # Set default_theme property for test compatibility
            self.default_theme = "ayu-mirage"
            # Try to set preferred theme, fall back to default if it fails
            try:
                self.theme = "ayu-mirage"
            except (ValueError, KeyError, AttributeError):
                # Theme not available or not registered, keep default
                log("[INFO] ayu-mirage theme not available, using default theme")
        except (ImportError, ModuleNotFoundError) as e:
            log(f"[ERROR] Failed to import theme modules: {e}")
        except (AttributeError, TypeError) as e:
            log(f"[ERROR] Invalid theme objects during registration: {e}")
        except ValueError as e:
            log(f"[ERROR] Invalid theme data during registration: {e}")
        except OSError as e:
            log(f"[ERROR] File system error during theme discovery: {e}")
        except Exception as e:
            log(f"[ERROR] Unexpected error during theme registration: {e}")

    def on_mount(self):
        """Initialize application on mount.

        Pushes the main screen to begin the application UI.
        Theme registration is handled during __init__ for proper initialization order.
        """
        # Push main screen (themes already registered in __init__)
        self.push_screen(MainScreen(self.paths_config))


def _create_argument_parser():
    """Create and configure the command-line argument parser."""
    parser = argparse.ArgumentParser(description="Delta Vision: File Comparison App")
    parser.add_argument('--new', type=str, help='Path to folder for stream page')
    parser.add_argument('--old', type=str, help='Path to second folder to monitor (not used on Stream)')
    parser.add_argument('--keywords', type=str, help='Path to keywords markdown file')
    parser.add_argument('--server', action='store_true', help='Start as a TCP/WebSocket server')
    parser.add_argument('--client', action='store_true', help='Connect as a network client')
    parser.add_argument('--port', type=int, default=8765, help='Port for server or client connection')
    parser.add_argument('--host', type=str, default='localhost', help='Host for client connection')
    parser.add_argument(
        '--bind-address',
        type=str,
        default='127.0.0.1',
        help='Bind address for server (default: 127.0.0.1 for security)',
    )
    parser.add_argument('--max-connections', type=int, default=10, help='Maximum concurrent connections for server')
    return parser


def _apply_environment_overrides(args):
    """Apply environment variable overrides to parsed arguments with proper CLI precedence."""
    # Fallback to environment variables if arguments are missing (for web/server mode)
    if not args.new:
        args.new = os.environ.get('DELTA_NEW')
    if not args.old:
        args.old = os.environ.get('DELTA_OLD')
    if not args.keywords:
        args.keywords = os.environ.get('DELTA_KEYWORDS')

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


def _validate_configuration(args):
    """Validate all user inputs for security and correctness."""
    try:
        # Validate file/directory paths
        if args.new or args.old or args.keywords:
            validated_new, validated_old, validated_keywords = validate_config_paths(args.new, args.old, args.keywords)
            args.new = validated_new
            args.old = validated_old
            args.keywords = validated_keywords

        # Validate network configuration for server/client modes
        if args.server or args.client:
            validated_host, validated_port = validate_network_config(args.host, args.port)
            args.host = validated_host
            args.port = validated_port
        else:
            # Even in local mode, validate port if specified (in case user specified it)
            args.port = validate_port(args.port, "Port")

    except ValidationError as e:
        log(f"Configuration validation failed: {e}")
        sys.stderr.write(f"Configuration Error: {e}\n")
        sys.stderr.write("\nPlease check your arguments and try again.\n")
        sys.stderr.write("Use --help for usage information.\n")
        sys.exit(1)
    except Exception as e:
        log(f"Unexpected validation error: {e}")
        sys.stderr.write(f"Unexpected validation error: {e}\n")
        sys.exit(1)


def _execute_mode(args):
    """Determine and execute the appropriate application mode."""
    if args.server:
        # Pass only defined values into env so child sessions inherit file paths
        child_env = {
            k: v
            for k, v in {
                'DELTA_NEW': args.new,
                'DELTA_OLD': args.old,
                'DELTA_KEYWORDS': args.keywords,
            }.items()
            if v
        }
        # Create server configuration with security settings
        server_config = ServerConfig(
            bind_address=getattr(args, 'bind_address', '127.0.0.1'),
            port=args.port,
            max_connections=getattr(args, 'max_connections', 10),
        )
        log(f"Starting Delta Vision server on {server_config.bind_address}:{server_config.port}")
        sys.stderr.write(f"Delta Vision server starting on {server_config.bind_address}:{server_config.port}...\n")
        try:
            asyncio.run(start_server(port=args.port, child_env=child_env, server_config=server_config))
        except KeyboardInterrupt:
            log("Server stopped by user (KeyboardInterrupt)")
            sys.stderr.write("\n[delta-vision] Server stopped by user\n")
            # Ignore any further Ctrl+C presses during cleanup
            _ignore_further_interrupts()
            # Give a small delay to allow background threads to finish
            time.sleep(0.2)
            return
    elif args.client:
        log(f"Starting Delta Vision client, connecting to {args.host}:{args.port}")
        sys.stderr.write(f"Connecting to Delta Vision server at {args.host}:{args.port}...\n")
        try:
            asyncio.run(start_client(host=args.host, port=args.port))
        except KeyboardInterrupt:
            log("Client stopped by user (KeyboardInterrupt)")
            sys.stderr.write("\n[delta-vision] Client stopped by user\n")
            # Ignore any further Ctrl+C presses during cleanup
            _ignore_further_interrupts()
            # Give a small delay to allow background threads to finish
            time.sleep(0.2)
            return
        except Exception as e:
            # Handle other client connection errors
            if "ConnectionRefused" in str(type(e)) or "connection refused" in str(e).lower():
                log(f"Client connection refused to {args.host}:{args.port}: {e}")
                sys.stderr.write(f"Error: Cannot connect to server at {args.host}:{args.port}\n")
                sys.stderr.write("Make sure the server is running with: python -m delta_vision --server\n")
            else:
                log(f"Client connection error: {e}")
                sys.stderr.write(f"Client error: {e}\n")
            return
    else:
        # Default to local TUI mode
        paths_config = PathsConfig.from_args(args)
        HomeApp(paths_config).run()


def main():
    """Main entry point for Delta Vision application."""
    parser = _create_argument_parser()
    args, unknown = parser.parse_known_args()

    _apply_environment_overrides(args)
    _validate_configuration(args)
    _execute_mode(args)


# Ensure main() runs both as a script and when run by textual serve
if __name__ == "__main__" or __name__.endswith(".app"):
    main()
