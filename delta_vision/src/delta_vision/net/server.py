import asyncio
import fcntl
import json
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

# ---- Notes collaboration state (shared across all sessions) ----
NOTES_ROUTE = "/notes"
SHARED_NOTES_TEXT: str = ""
NOTES_SUBSCRIBERS = set()  # websocket connections

async def _notes_broadcast(payload: dict) -> None:
    """Broadcast a JSON payload to all current notes subscribers."""
    if not NOTES_SUBSCRIBERS:
        return
    data = json.dumps(payload)
    dead = []
    for ws in list(NOTES_SUBSCRIBERS):
        try:
            sender = getattr(ws, "send", None)
            if sender is None:
                dead.append(ws)
            else:
                await sender(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        try:
            NOTES_SUBSCRIBERS.discard(ws)
        except Exception:
            pass

async def handle_notes_channel(websocket):
    """Handle /notes websocket connections.

    Protocol (JSON text frames):
      - Server -> client on connect: {"type":"sync","text": <str>}
      - Client -> server on edit:   {"type":"update","text": <str>, "client_id": <str>}
      - Server -> all on update:    {"type":"sync","text": <str>, "source": <str>}
    """
    # Register
    NOTES_SUBSCRIBERS.add(websocket)
    try:
        # Initial sync to the new client
        await websocket.send(json.dumps({"type": "sync", "text": SHARED_NOTES_TEXT}))
        # Listen for updates
        async for msg in websocket:
            try:
                if not isinstance(msg, str):
                    # Ignore non-text frames on notes channel
                    continue
                obj = json.loads(msg)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            if obj.get("type") == "update":
                text = obj.get("text")
                source = obj.get("client_id")
                if not isinstance(text, str):
                    continue
                # Update shared state then broadcast to everyone (including sender)
                global SHARED_NOTES_TEXT
                SHARED_NOTES_TEXT = text
                await _notes_broadcast({"type": "sync", "text": SHARED_NOTES_TEXT, "source": source})
            # else: ignore unknown types
    finally:
        try:
            NOTES_SUBSCRIBERS.discard(websocket)
        except Exception:
            pass

async def handle_client(
    websocket,
    *,
    child_env: Optional[Dict[str, str]] = None,
    addr: Optional[str | tuple] = None,
    server_port: Optional[int] = None,
):
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
    # Provide notes websocket URL to child app so it can collaborate
    try:
        if server_port:
            env.setdefault('DELTA_NOTES_WS', f"ws://127.0.0.1:{server_port}{NOTES_ROUTE}")
    except Exception:
        pass

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
        # Route based on path: /notes is collaboration channel; anything else is a session
        path = getattr(ws, "path", "/")
        if path == NOTES_ROUTE:
            log(f"[server] notes client connected: {peer}")
            try:
                return await handle_notes_channel(ws)
            finally:
                log(f"[server] notes client disconnected: {peer}")
        else:
            log(f"[server] client connected: {peer}")
            try:
                return await handle_client(ws, child_env=child_env, addr=peer, server_port=port)
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
