import re
from typing import Dict, List, Optional, Tuple

from delta_vision.utils.io import read_lines


def parse_keywords_md(path: str) -> Dict[str, Tuple[str, List[str]]]:
    """
    Parse a markdown keywords file.

    Rules:
    - Category header lines begin with '#', e.g. '# Category (Color)'.
      The '(Color)' part is optional. Whitespace is trimmed.
    - Any other lines starting with '#' are treated as comments and ignored.
    - Keywords are non-empty lines under the current category. Inline comments
      after a keyword are stripped when preceded by whitespace, e.g. 'foo  # note'.
    - Empty categories are allowed and should be preserved in the result.
    - Returns mapping: {category: (color, [keywords])}. Color may be empty ''.
    - Decoding uses the centralized multi-encoding reader.
    """
    result: Dict[str, Tuple[str, List[str]]] = {}
    current_category: Optional[str] = None
    current_color: str = ""
    current_keywords: List[str] = []

    lines, _enc = read_lines(path)
    for raw in lines:
        line = (raw or "").strip()
        if not line:
            continue

        # Header: '# Category' or '# Category (Color)'
        if line.startswith('#'):
            # Header requires Category starting with an uppercase letter
            m = re.match(r"^\s*#\s*([A-Z][A-Za-z0-9 _-]*?)(?:\s*\(([^)]+)\))?\s*$", line)
            if m:
                # Save previous category, even if empty
                if current_category is not None:
                    result[current_category] = (current_color or "", current_keywords)
                # Start new category
                cat = (m.group(1) or "").strip()
                col = (m.group(2) or "").strip()
                current_category = cat
                current_color = col
                current_keywords = []
                continue
            else:
                # Non-header comment: ignore
                continue

        # Keyword line (only if we have an active category)
        if current_category is not None:
            # Strip inline comment when there's whitespace before '#'
            # e.g., 'foo  # bar' -> 'foo'
            kw = re.sub(r"\s+#.*$", "", line).strip()
            if kw:
                current_keywords.append(kw)

    # Save last category (even if empty)
    if current_category is not None:
        result[current_category] = (current_color or "", current_keywords)

    return result
