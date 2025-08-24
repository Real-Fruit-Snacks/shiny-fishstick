# Sorted imports
import asyncio
import fcntl
import os
import pty
import signal
import struct
import subprocess
import sys
import termios
from typing import Dict, Optional, Tuple

try:
    import websockets
except ImportError:
    websockets = None

from delta_vision.utils.logger import log

# Track active child processes for clean shutdown
ACTIVE_CHILDREN = set()
_SIGNALS_REGISTERED = False

RESIZE_PREFIX = "RESIZE "


async def handle_client(websocket, *, child_env: Optional[Dict[str, str]] = None, addr: Optional[str | tuple] = None):
    """Handle a WebSocket client connection with PTY process management."""
    # Setup PTY and spawn child process
    master_fd, proc = _setup_pty_and_process(child_env, addr)

    # Create async I/O handlers
    loop = asyncio.get_running_loop()
    handlers = _create_io_handlers(websocket, master_fd, proc, loop)

    try:
        # Coordinate PTY I/O tasks
        await _coordinate_pty_tasks(handlers)
    finally:
        # Cleanup process and PTY resources
        _cleanup_process_and_pty(master_fd, proc, addr)


def _setup_pty_and_process(
    child_env: Optional[Dict[str, str]], addr: Optional[str | tuple]
) -> Tuple[int, subprocess.Popen]:
    """Setup PTY and spawn child Delta Vision process."""
    # PTY for the Delta Vision child process
    master_fd, slave_fd = pty.openpty()

    # Build child argv: if frozen (PyInstaller/standalone), exec the current binary;
    # otherwise run the module via the current Python.
    if getattr(sys, 'frozen', False):  # type: ignore[attr-defined]
        child_argv = [sys.executable]
    else:
        child_argv = [sys.executable, '-m', 'delta_vision']

    # Configure environment for child process
    env = _configure_child_environment(child_env)

    # Spawn the child process
    proc = subprocess.Popen(
        child_argv,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=env,
        preexec_fn=os.setsid,
        close_fds=True,
    )
    log(f"[server] spawned session pid={proc.pid} for {addr if addr else 'unknown client'}")

    # Track this child and close slave fd
    ACTIVE_CHILDREN.add(proc)
    try:
        os.close(slave_fd)
    except OSError as e:
        log(f"[ERROR] Failed to close slave PTY: {e}")

    return master_fd, proc


def _configure_child_environment(child_env: Optional[Dict[str, str]]) -> Dict[str, str]:
    """Configure environment variables for child process."""
    # Merge DELTA_* env so server can pass --new/--old/--keywords via env
    env: Dict[str, str] = os.environ.copy()

    # Remove network mode variables to prevent child processes from inheriting client/server mode
    env.pop('DELTA_MODE', None)
    env.pop('DELTA_SERVER', None)
    env.pop('DELTA_CLIENT', None)

    # Add marker so child processes know they're server children
    env['DELTA_SERVER_CHILD'] = 'true'

    if child_env:
        for k, v in child_env.items():
            if v is not None:
                env[str(k)] = str(v)

    return env


def _create_io_handlers(websocket, master_fd: int, proc: subprocess.Popen, loop) -> Dict[str, any]:
    """Create async I/O handler functions for PTY communication."""

    async def pty_to_ws():
        """Forward PTY output to WebSocket."""
        try:
            while True:
                data = await loop.run_in_executor(None, os.read, master_fd, 4096)
                if not data:
                    break
                # Send as binary to preserve bytes
                await websocket.send(data)
        except asyncio.CancelledError:
            log("[server] PTY to WebSocket forwarding cancelled")
            raise
        except OSError as e:
            # Handle PTY I/O errors gracefully (normal when child process exits)
            if e.errno == 5:  # Input/output error
                log("[server] PTY closed (child process exited)")
            else:
                log(f"[server] PTY I/O error: {e}")
            raise
        except Exception as e:
            # Handle websocket exceptions more broadly during shutdown
            if "ConnectionClosed" in str(type(e)) or "going away" in str(e):
                log("[server] WebSocket connection closed during data send")
            else:
                log(f"[ERROR] Failed to send data to websocket: {e}")
            raise

    async def ws_to_pty():
        """Forward WebSocket input to PTY, handling resize messages."""
        try:
            async for message in websocket:
                if isinstance(message, str):
                    # Handle resize messages
                    if message.startswith(RESIZE_PREFIX):
                        _handle_resize_message(message, master_fd, proc)
                        continue

                # Handle regular terminal data
                data = message if isinstance(message, (bytes, bytearray)) else message.encode()
                if data:
                    os.write(master_fd, data)
        except asyncio.CancelledError:
            log("[server] WebSocket to PTY forwarding cancelled")
            raise
        except Exception as e:
            # Handle websocket exceptions more broadly during shutdown
            if "ConnectionClosed" in str(type(e)) or "going away" in str(e):
                log("[server] WebSocket connection closed during message receive")
            else:
                log(f"[ERROR] Failed to write data to PTY: {e}")
            raise

    return {'pty_to_ws': pty_to_ws, 'ws_to_pty': ws_to_pty}


def _handle_resize_message(message: str, master_fd: int, proc: subprocess.Popen):
    """Handle terminal resize message from WebSocket client."""
    try:
        _p, rest = message.split(' ', 1)
        cols_str, rows_str = rest.strip().split(' ')
        cols, rows = int(cols_str), int(rows_str)
        winsize = struct.pack('HHHH', rows, cols, 0, 0)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
        os.killpg(os.getpgid(proc.pid), signal.SIGWINCH)
    except (OSError, ProcessLookupError, ValueError) as e:
        log(f"[ERROR] Failed to send SIGWINCH to process group: {e}")


async def _coordinate_pty_tasks(handlers: Dict[str, any]):
    """Coordinate PTY I/O tasks until completion."""
    try:
        await asyncio.gather(handlers['pty_to_ws'](), handlers['ws_to_pty']())
    except asyncio.CancelledError:
        log("[server] PTY tasks cancelled during shutdown")
        raise
    except OSError as e:
        # Handle PTY errors gracefully - these are normal when child exits
        if e.errno == 5:  # Input/output error
            log("[server] PTY connection closed (child process terminated)")
        else:
            log(f"[server] PTY I/O error during coordination: {e}")
        # Don't re-raise OSError for normal PTY closure
    except Exception as e:
        # Only log other unexpected errors
        if "ConnectionClosed" not in str(type(e)):
            log(f"[server] PTY task coordination failed: {e}")
        # Don't re-raise to prevent traceback spam


def _cleanup_process_and_pty(master_fd: int, proc: subprocess.Popen, addr: Optional[str | tuple]):
    """Cleanup PTY file descriptor and terminate child process."""
    # Close master PTY
    try:
        os.close(master_fd)
    except OSError as e:
        log(f"[ERROR] Failed to close master PTY: {e}")

    # Terminate process gracefully, then forcefully if needed
    _terminate_child_process(proc, addr)

    # Remove from active children set
    try:
        ACTIVE_CHILDREN.discard(proc)
    except Exception as e:
        log(f"[ERROR] Failed to remove process from active children set: {e}")


def _terminate_child_process(proc: subprocess.Popen, addr: Optional[str | tuple]):
    """Terminate child process with graceful then forceful approach."""
    # Send SIGTERM first
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (OSError, ProcessLookupError) as e:
        log(f"[ERROR] Failed to send SIGTERM to process group: {e}")

    # Wait for graceful termination
    ret = None
    try:
        proc.wait(timeout=3)
        ret = proc.returncode
    except (OSError, RuntimeError, subprocess.SubprocessError) as e:
        log(f"[ERROR] Failed to wait for process termination: {e}")
        # Force kill if graceful termination failed
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (OSError, ProcessLookupError) as kill_e:
            log(f"[ERROR] Failed to send SIGKILL to process group: {kill_e}")

    # Log process termination outcome
    try:
        if ret is None:
            log(f"[server] session pid={proc.pid} for {addr if addr else 'client'} terminated")
        else:
            log(f"[server] session pid={proc.pid} for {addr if addr else 'client'} exited code={ret}")
    except Exception as e:
        log(f"[ERROR] Failed to log session outcome: {e}")


async def start_server(*, port: int, child_env: Optional[Dict[str, str]] = None):
    """Start the WebSocket server for remote Delta Vision sessions.

    Creates a WebSocket server that spawns PTY sessions per client connection.
    Each client gets its own isolated Delta Vision process with terminal multiplexing.

    Args:
        port: Port number to bind the WebSocket server to
        child_env: Optional environment variables to pass to child processes
    """
    if websockets is None:
        print("Error: websockets module not available. Install with: pip install websockets")
        return

    serve = websockets.serve
    stop_event = asyncio.Event()

    def _signal_handler(signum, _frame=None):
        # Notify loop to stop
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(stop_event.set)
        except RuntimeError:
            # No running loop; set directly if possible
            stop_event.set()

    # Register signals
    global _SIGNALS_REGISTERED
    if not _SIGNALS_REGISTERED:
        try:
            signal.signal(signal.SIGINT, _signal_handler)
            signal.signal(signal.SIGTERM, _signal_handler)
            _SIGNALS_REGISTERED = True
        except (OSError, ValueError) as e:
            log(f"[ERROR] Failed to register signal handlers: {e}")

    print(f"Delta Vision server listening on 0.0.0.0:{port}")

    async def _handler(ws):
        # Best-effort peer address extraction
        peer = getattr(ws, "remote_address", None)
        log(f"[server] client connected: {peer}")
        try:
            return await handle_client(ws, child_env=child_env, addr=peer)
        except OSError as e:
            # Handle normal PTY closure gracefully
            if e.errno == 5:  # Input/output error
                log(f"[server] client session ended normally: {peer}")
            else:
                log(f"[server] client session I/O error: {peer} - {e}")
        except Exception as e:
            # Only log unexpected errors
            if "ConnectionClosed" not in str(type(e)):
                log(f"[server] client session error: {peer} - {e}")
        finally:
            log(f"[server] client disconnected: {peer}")

    async with serve(_handler, '0.0.0.0', port, ping_interval=20, max_size=None) as _server:
        try:
            # Wait until a signal asks us to stop
            await stop_event.wait()
        except KeyboardInterrupt:
            log("[server] Keyboard interrupt received")
        finally:
            print("\nShutting down Delta Vision server...")

    # After server exits, ensure all children are terminated
    for proc in list(ACTIVE_CHILDREN):
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (OSError, ProcessLookupError) as e:
            log(f"[ERROR] Failed to send SIGTERM to child process group during cleanup: {e}")
    # Give them a moment
    await asyncio.sleep(0.2)
    for proc in list(ACTIVE_CHILDREN):
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (OSError, ProcessLookupError) as e:
                log(f"[ERROR] Failed to send SIGKILL to child process group during cleanup: {e}")
