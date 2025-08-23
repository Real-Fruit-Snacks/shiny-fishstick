"""Diff computation utilities for Delta Vision.

This module provides text comparison functionality using Python's difflib
to generate line-by-line diff data suitable for UI rendering.
"""

from difflib import SequenceMatcher
from typing import Optional


# Type alias for diff row structure
DiffRow = tuple[Optional[int], str, Optional[int], str, str]


def compute_diff_rows(old_lines: list[str], new_lines: list[str]) -> list[DiffRow]:
    """Compute diff rows between two sets of lines.
    
    Args:
        old_lines: Lines from the old file
        new_lines: Lines from the new file
        
    Returns:
        List of diff rows where each row is a tuple of:
        (old_line_num, old_text, new_line_num, new_text, tag)
        
        Tags are: 'equal', 'replace', 'delete', 'insert'
        Line numbers start at 1 for the first line (header is assumed skipped by caller)
    """
    rows: list[DiffRow] = []
    sm = SequenceMatcher(None, old_lines, new_lines)
    old_idx = 1  # first displayed line number
    new_idx = 1
    
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                rows.append((old_idx, old_lines[i1 + k], new_idx, new_lines[j1 + k], 'equal'))
                old_idx += 1
                new_idx += 1
        elif tag == 'replace':
            length = max(i2 - i1, j2 - j1)
            for k in range(length):
                o_text = old_lines[i1 + k] if i1 + k < i2 else ""
                n_text = new_lines[j1 + k] if j1 + k < j2 else ""
                o_ln = old_idx if i1 + k < i2 else None
                n_ln = new_idx if j1 + k < j2 else None
                if i1 + k < i2:
                    old_idx += 1
                if j1 + k < j2:
                    new_idx += 1
                rows.append((o_ln, o_text, n_ln, n_text, 'replace'))
        elif tag == 'delete':
            for k in range(i2 - i1):
                rows.append((old_idx, old_lines[i1 + k], None, "", 'delete'))
                old_idx += 1
        elif tag == 'insert':
            for k in range(j2 - j1):
                rows.append((None, "", new_idx, new_lines[j1 + k], 'insert'))
                new_idx += 1
    
    return rows