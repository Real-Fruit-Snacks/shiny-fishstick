from __future__ import annotations

from typing import Iterable

from .logger import log

DEFAULT_ENCODINGS: tuple[str, ...] = (
    "utf-8",
    "utf-8-sig",
    "cp1252",
    "latin-1",
)


def read_text(
    path: str, encodings: Iterable[str] = DEFAULT_ENCODINGS, errors: str = "strict", ignore_on_last: bool = True
) -> tuple[str, str]:
    """
    Read a text file trying multiple encodings in order.

    Returns (text, used_encoding).
    If all strict attempts fail and ignore_on_last is True, retries the last
    encoding with errors="ignore" and logs a warning.
    """
    last_enc = None
    for enc in encodings:
        last_enc = enc
        try:
            with open(path, encoding=enc, errors=errors) as f:
                return f.read(), enc
        except UnicodeDecodeError:
            continue
        except (OSError, IOError) as e:
            # For IO errors, propagate a simple, empty content result
            # (callers already guard and present an error row/message)
            log(f"[IO] Failed to read {path} with {enc}: {e}")
            return ("", enc)
    if ignore_on_last and last_enc:
        try:
            with open(path, encoding=last_enc, errors="ignore") as f:
                log(f"[IO] Decoded with ignore: {path} ({last_enc})")
                return f.read(), f"{last_enc}+ignore"
        except (OSError, IOError) as e:
            log(f"[IO] Failed to read {path} with ignore mode: {e}")
            pass
    return ("", last_enc or "")


def read_lines(
    path: str, encodings: Iterable[str] = DEFAULT_ENCODINGS, errors: str = "strict", ignore_on_last: bool = True
) -> tuple[list[str], str]:
    text, used = read_text(path, encodings=encodings, errors=errors, ignore_on_last=ignore_on_last)
    if not text:
        return ([], used)
    return (text.splitlines(), used)
