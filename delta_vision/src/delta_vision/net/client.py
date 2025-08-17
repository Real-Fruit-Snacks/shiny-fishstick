import asyncio
import fcntl
import os
import signal
import struct
import sys
import termios
import tty

RESIZE_PREFIX = "RESIZE "

async def start_client(host: str, port: int):
    ws_mod = __import__("websockets")
    uri = f"ws://{host}:{port}"

    # Save terminal state and switch to raw mode
    fd = sys.stdin.fileno()
    old_attrs = termios.tcgetattr(fd)

    async with ws_mod.connect(uri, max_size=None) as websocket:
        tty.setraw(fd)

        loop = asyncio.get_running_loop()
        resize_event = asyncio.Event()

        def on_winch(signum, frame):
            resize_event.set()

        old_winch = signal.getsignal(signal.SIGWINCH)
        signal.signal(signal.SIGWINCH, on_winch)

        # Local stop event (e.g., on Ctrl+D/EOF)
        stop_event = asyncio.Event()

        async def push_resize():
            while True:
                await resize_event.wait()
                resize_event.clear()
                # Query current window size
                rows, cols, _xp, _yp = struct.unpack(
                    'HHHH', fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, struct.pack('HHHH', 0, 0, 0, 0))
                )
                await websocket.send(f"{RESIZE_PREFIX}{cols} {rows}")

        async def stdin_to_ws():
            while True:
                data = await loop.run_in_executor(None, os.read, fd, 4096)
                if not data:
                    break
                # Handle Ctrl+D as a local disconnect; Ctrl+C is passed through
                if b"\x04" in data:  # Ctrl+D (EOF)
                    try:
                        await websocket.send(b"\x04")
                    except Exception:
                        pass
                    stop_event.set()
                    break
                await websocket.send(data)

        async def ws_to_stdout():
            async for message in websocket:
                if isinstance(message, str):
                    data = message.encode()
                else:
                    data = message
                if data:
                    os.write(sys.stdout.fileno(), data)

        # Send initial resize
        resize_event.set()
        try:
            io_task = asyncio.create_task(stdin_to_ws())
            out_task = asyncio.create_task(ws_to_stdout())
            res_task = asyncio.create_task(push_resize())
            stop_task = asyncio.create_task(stop_event.wait())
            done, pending = await asyncio.wait(
                {io_task, out_task, res_task, stop_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            # Close websocket cleanly
            try:
                await websocket.close()
            except Exception:
                pass
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
            signal.signal(signal.SIGWINCH, old_winch)
            # Small UX hint on disconnect
            try:
                sys.stderr.write("\n[delta-vision] Disconnected.\n")
                sys.stderr.flush()
            except Exception:
                pass
