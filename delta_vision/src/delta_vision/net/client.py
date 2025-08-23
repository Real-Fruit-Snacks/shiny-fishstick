import asyncio
import fcntl
import os
import signal
import struct
import sys
import termios
import tty

try:
    import websockets
except ImportError:
    websockets = None

from delta_vision.utils.logger import log

RESIZE_PREFIX = "RESIZE "


async def start_client(host: str, port: int):
    """Main entry point for WebSocket client with PTY terminal handling."""
    if websockets is None:
        print("Error: websockets module not available. Install with: pip install websockets")
        return
    
    uri = f"ws://{host}:{port}"
    
    # Setup terminal state and determine TTY capability
    terminal_state = _setup_terminal_state()
    
    async with websockets.connect(uri, max_size=None) as websocket:
        # Configure terminal for raw mode if TTY available
        _configure_terminal_raw_mode(terminal_state)
        
        # Setup signal handlers and events
        signal_state = _setup_signal_handlers(terminal_state['is_tty'])
        
        # Create async handler functions
        handlers = _create_async_handlers(
            websocket, terminal_state, signal_state
        )
        
        # Execute main I/O coordination
        await _coordinate_io_tasks(websocket, handlers, signal_state, terminal_state)
        
        # Cleanup is handled in finally block
        _cleanup_terminal_state(terminal_state, signal_state)

def _setup_terminal_state() -> dict:
    """Setup terminal state and detect TTY capability."""
    fd = sys.stdin.fileno()
    old_attrs = None
    is_tty = False
    
    try:
        old_attrs = termios.tcgetattr(fd)
        is_tty = True
    except (termios.error, OSError) as e:
        # Not running in a TTY or terminal not available
        print(f"Warning: Not running in TTY environment: {e}")
        print("Client will connect but terminal features may be limited.")
    
    return {
        'fd': fd,
        'old_attrs': old_attrs,
        'is_tty': is_tty
    }

def _configure_terminal_raw_mode(terminal_state: dict):
    """Configure terminal for raw mode if TTY is available."""
    if terminal_state['is_tty']:
        tty.setraw(terminal_state['fd'])

def _setup_signal_handlers(is_tty: bool) -> dict:
    """Setup signal handlers and events for terminal operations."""
    loop = asyncio.get_running_loop()
    resize_event = asyncio.Event()
    stop_event = asyncio.Event()
    
    def on_winch(signum, frame):
        resize_event.set()
    
    old_winch = None
    if is_tty:
        old_winch = signal.getsignal(signal.SIGWINCH)
        signal.signal(signal.SIGWINCH, on_winch)
    
    return {
        'loop': loop,
        'resize_event': resize_event,
        'stop_event': stop_event,
        'old_winch': old_winch,
        'on_winch': on_winch
    }

def _create_async_handlers(websocket, terminal_state: dict, signal_state: dict) -> dict:
    """Create async handler functions for I/O operations."""
    
    async def push_resize():
        """Handle terminal resize events."""
        if not terminal_state['is_tty']:
            return  # No resize handling in non-TTY mode
        while True:
            await signal_state['resize_event'].wait()
            signal_state['resize_event'].clear()
            try:
                # Query current window size
                rows, cols, _xp, _yp = struct.unpack(
                    'HHHH', fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, struct.pack('HHHH', 0, 0, 0, 0))
                )
                await websocket.send(f"{RESIZE_PREFIX}{cols} {rows}")
            except (OSError, termios.error):
                # Ignore resize errors in non-TTY environments
                pass
    
    async def stdin_to_ws():
        """Forward stdin input to websocket."""
        if not terminal_state['is_tty']:
            # In non-TTY mode, wait for stop event or timeout (30 seconds for demo)
            try:
                await asyncio.wait_for(signal_state['stop_event'].wait(), timeout=30.0)
            except asyncio.TimeoutError:
                print("Non-TTY client timeout after 30 seconds")
                signal_state['stop_event'].set()
            return
        
        while True:
            try:
                data = await signal_state['loop'].run_in_executor(
                    None, os.read, terminal_state['fd'], 4096
                )
                if not data:
                    break
                # Handle Ctrl+D as a local disconnect; Ctrl+C is passed through
                if b"\x04" in data:  # Ctrl+D (EOF)
                    try:
                        await websocket.send(b"\x04")
                    except (OSError, ConnectionError) as e:
                        log(f"[CLIENT] Failed to send EOF to websocket: {e}")
                        pass
                    signal_state['stop_event'].set()
                    break
                await websocket.send(data)
            except (OSError, BlockingIOError):
                # Handle non-blocking read errors
                await asyncio.sleep(0.1)
    
    async def ws_to_stdout():
        """Forward websocket messages to stdout."""
        async for message in websocket:
            if isinstance(message, str):
                data = message.encode()
            else:
                data = message
            if data:
                os.write(sys.stdout.fileno(), data)
    
    return {
        'push_resize': push_resize,
        'stdin_to_ws': stdin_to_ws,
        'ws_to_stdout': ws_to_stdout
    }

async def _coordinate_io_tasks(websocket, handlers: dict, signal_state: dict, terminal_state: dict):
    """Coordinate all I/O tasks and handle completion."""
    # Send initial resize (only if in TTY)
    if terminal_state['is_tty']:
        signal_state['resize_event'].set()
    
    try:
        io_task = asyncio.create_task(handlers['stdin_to_ws']())
        out_task = asyncio.create_task(handlers['ws_to_stdout']())
        res_task = asyncio.create_task(handlers['push_resize']())
        stop_task = asyncio.create_task(signal_state['stop_event'].wait())
        
        done, pending = await asyncio.wait(
            {io_task, out_task, res_task, stop_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        
        for task in pending:
            task.cancel()
        
        # Close websocket cleanly
        try:
            await websocket.close()
        except (OSError, ConnectionError) as e:
            log(f"[CLIENT] Failed to close websocket: {e}")
            pass
    finally:
        # Terminal cleanup is handled separately
        pass

def _cleanup_terminal_state(terminal_state: dict, signal_state: dict):
    """Restore terminal state and signal handlers."""
    # Restore terminal state (only if we had TTY)
    if terminal_state['is_tty'] and terminal_state['old_attrs']:
        try:
            termios.tcsetattr(
                terminal_state['fd'], 
                termios.TCSADRAIN, 
                terminal_state['old_attrs']
            )
        except (termios.error, OSError):
            pass
    
    if signal_state['old_winch'] is not None:
        try:
            signal.signal(signal.SIGWINCH, signal_state['old_winch'])
        except (OSError, ValueError):
            pass
    
    # Small UX hint on disconnect
    try:
        sys.stderr.write("\n[delta-vision] Disconnected.\n")
        sys.stderr.flush()
    except (OSError, IOError) as e:
        log(f"[CLIENT] Failed to write disconnect message: {e}")
        pass
