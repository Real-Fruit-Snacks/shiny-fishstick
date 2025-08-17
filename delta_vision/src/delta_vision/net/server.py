# Sorted imports
import asyncio
import fcntl
import os
import pty
import signal
import struct
import sys
import termios
from typing import Dict, Optional

from delta_vision.utils.logger import log

# Track active child processes for clean shutdown
ACTIVE_CHILDREN = set()
_SIGNALS_REGISTERED = False

RESIZE_PREFIX = "RESIZE "

async def handle_client(websocket, *, child_env: Optional[Dict[str, str]] = None, addr: Optional[str | tuple] = None):
    import subprocess
    # PTY for the Delta Vision child process
    master_fd, slave_fd = pty.openpty()

    # Build child argv: if frozen (PyInstaller/standalone), exec the current binary;
    # otherwise run the module via the current Python.
    if getattr(sys, 'frozen', False):  # type: ignore[attr-defined]
        child_argv = [sys.executable]
    else:
        child_argv = [sys.executable, '-m', 'delta_vision']

    # Merge DELTA_* env so server can pass --new/--old/--keywords via env
    env: Dict[str, str] = os.environ.copy()
    if child_env:
        for k, v in child_env.items():
            if v is not None:
                env[str(k)] = str(v)

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
    # Track this child
    ACTIVE_CHILDREN.add(proc)
    try:
        os.close(slave_fd)
    except Exception:
        pass

    loop = asyncio.get_running_loop()

    async def pty_to_ws():
        try:
            while True:
                data = await loop.run_in_executor(None, os.read, master_fd, 4096)
                if not data:
                    break
                # Send as binary to preserve bytes
                await websocket.send(data)
        except Exception:
            pass

    async def ws_to_pty():
        try:
            async for message in websocket:
                if isinstance(message, str) and message.startswith(RESIZE_PREFIX):
                    try:
                        _p, rest = message.split(' ', 1)
                        cols_str, rows_str = rest.strip().split(' ')
                        cols, rows = int(cols_str), int(rows_str)
                        winsize = struct.pack('HHHH', rows, cols, 0, 0)
                        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
                        os.killpg(os.getpgid(proc.pid), signal.SIGWINCH)
                    except Exception:
                        pass
                else:
                    data = message if isinstance(message, (bytes, bytearray)) else message.encode()
                    if data:
                        os.write(master_fd, data)
        except Exception:
            pass

    try:
        await asyncio.gather(pty_to_ws(), ws_to_pty())
    finally:
        try:
            os.close(master_fd)
        except Exception:
            pass
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            pass
        ret = None
        try:
            proc.wait(timeout=3)
            ret = proc.returncode
        except Exception:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass
        # Log outcome and remove from active set
        try:
            if ret is None:
                log(f"[server] session pid={proc.pid} for {addr if addr else 'client'} terminated")
            else:
                log(f"[server] session pid={proc.pid} for {addr if addr else 'client'} exited code={ret}")
        except Exception:
            pass
        try:
            ACTIVE_CHILDREN.discard(proc)
        except Exception:
            pass

async def start_server(*, port: int, child_env: Optional[Dict[str, str]] = None):
    ws_mod = __import__("websockets")
    serve = ws_mod.serve
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
        except Exception:
            pass

    print(f"Delta Vision server listening on 0.0.0.0:{port}")

    async def _handler(ws):
        # Best-effort peer address extraction
        peer = getattr(ws, "remote_address", None)
        log(f"[server] client connected: {peer}")
        try:
            return await handle_client(ws, child_env=child_env, addr=peer)
        finally:
            log(f"[server] client disconnected: {peer}")

    async with serve(_handler, '0.0.0.0', port, ping_interval=20, max_size=None) as _server:
        # Wait until a signal asks us to stop
        await stop_event.wait()

    # After server exits, ensure all children are terminated
    for proc in list(ACTIVE_CHILDREN):
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            pass
    # Give them a moment
    await asyncio.sleep(0.2)
    for proc in list(ACTIVE_CHILDREN):
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass
