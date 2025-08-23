from __future__ import annotations

import re
from typing import Iterable, Pattern

from delta_vision.utils.logger import log


def make_keyword_pattern(
    keywords: Iterable[str],
    *,
    whole_word: bool = True,
    case_insensitive: bool = True,
) -> Pattern[str] | None:
    r"""Build a compiled regex to match any of the given keywords.

    - Sorts by length (desc) to prefer longer matches.
    - Escapes keywords.
    - When whole_word is True, uses simple word boundaries via (?<!\w) ... (?!\w).
    - When case_insensitive is True, compiles with re.IGNORECASE.

    Returns None if the input is empty after de-duplication.
    """
    try:
        words = [w for w in set(k.strip() for k in keywords or []) if w]
    except (ValueError, TypeError, AttributeError) as e:
        log(f"[TEXT] Failed to process keywords: {e}")
        words = []
    if not words:
        return None
    # Prefer longer matches first
    words.sort(key=len, reverse=True)
    alt = "|".join(re.escape(w) for w in words)
    core = f"({alt})"
    if whole_word:
        pat = rf"(?<!\w){core}(?!\w)"
    else:
        pat = core
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        return re.compile(pat, flags)
    except re.error:
        # Fallback to a safe literal OR pattern
        try:
            return re.compile(core, flags)
        except (re.error, ValueError, RuntimeError) as e:
            log(f"[TEXT] Failed to compile fallback regex pattern: {e}")
            return None
