"""Diff computation utilities for Delta Vision.

This module provides text comparison functionality using Python's difflib
to generate line-by-line diff data suitable for UI rendering.
"""

from difflib import SequenceMatcher
from typing import Optional

# Type alias for diff row structure
DiffRow = tuple[Optional[int], str, Optional[int], str, str]


def compute_diff_rows(old_lines: list[str], new_lines: list[str]) -> list[DiffRow]:
    """Compute diff rows between two sets of lines - orchestrator for diff computation.

    Args:
        old_lines: Lines from the old file
        new_lines: Lines from the new file

    Returns:
        List of diff rows where each row is a tuple of:
        (old_line_num, old_text, new_line_num, new_text, tag)

        Tags are: 'equal', 'replace', 'delete', 'insert'
        Line numbers start at 1 for the first line (header is assumed skipped by caller)
    """
    state = _initialize_diff_state(old_lines, new_lines)

    for opcode in state["matcher"].get_opcodes():
        _process_opcode(opcode, state)

    return state["rows"]


def _initialize_diff_state(old_lines: list[str], new_lines: list[str]) -> dict:
    """Initialize state for diff computation."""
    return {
        "rows": [],
        "matcher": SequenceMatcher(None, old_lines, new_lines),
        "old_lines": old_lines,
        "new_lines": new_lines,
        "old_idx": 1,
        "new_idx": 1
    }


def _process_opcode(opcode: tuple, state: dict):
    """Process a single opcode and dispatch to appropriate handler."""
    tag, i1, i2, j1, j2 = opcode

    if tag == 'equal':
        _handle_equal_lines(i1, i2, j1, j2, state)
    elif tag == 'replace':
        _handle_replace_lines(i1, i2, j1, j2, state)
    elif tag == 'delete':
        _handle_delete_lines(i1, i2, state)
    elif tag == 'insert':
        _handle_insert_lines(j1, j2, state)


def _handle_equal_lines(i1: int, i2: int, j1: int, j2: int, state: dict):
    """Handle equal lines in both files."""
    for k in range(i2 - i1):
        row = _create_equal_row(i1 + k, j1 + k, state)
        state["rows"].append(row)
        _increment_both_indices(state)


def _handle_replace_lines(i1: int, i2: int, j1: int, j2: int, state: dict):
    """Handle replaced lines between files."""
    length = max(i2 - i1, j2 - j1)

    for k in range(length):
        row = _create_replace_row(i1, i2, j1, j2, k, state)
        state["rows"].append(row)
        _update_indices_for_replace(i1, i2, j1, j2, k, state)


def _handle_delete_lines(i1: int, i2: int, state: dict):
    """Handle deleted lines from old file."""
    for k in range(i2 - i1):
        row = _create_delete_row(i1 + k, state)
        state["rows"].append(row)
        _increment_old_index(state)


def _handle_insert_lines(j1: int, j2: int, state: dict):
    """Handle inserted lines in new file."""
    for k in range(j2 - j1):
        row = _create_insert_row(j1 + k, state)
        state["rows"].append(row)
        _increment_new_index(state)


def _create_equal_row(old_pos: int, new_pos: int, state: dict) -> DiffRow:
    """Create a row for equal lines."""
    return (
        state["old_idx"],
        state["old_lines"][old_pos],
        state["new_idx"],
        state["new_lines"][new_pos],
        'equal'
    )


def _create_replace_row(i1: int, i2: int, j1: int, j2: int, k: int, state: dict) -> DiffRow:
    """Create a row for replaced lines."""
    o_text = state["old_lines"][i1 + k] if i1 + k < i2 else ""
    n_text = state["new_lines"][j1 + k] if j1 + k < j2 else ""
    o_ln = state["old_idx"] if i1 + k < i2 else None
    n_ln = state["new_idx"] if j1 + k < j2 else None

    return (o_ln, o_text, n_ln, n_text, 'replace')


def _create_delete_row(old_pos: int, state: dict) -> DiffRow:
    """Create a row for deleted lines."""
    return (state["old_idx"], state["old_lines"][old_pos], None, "", 'delete')


def _create_insert_row(new_pos: int, state: dict) -> DiffRow:
    """Create a row for inserted lines."""
    return (None, "", state["new_idx"], state["new_lines"][new_pos], 'insert')


def _increment_both_indices(state: dict):
    """Increment both old and new line indices."""
    state["old_idx"] += 1
    state["new_idx"] += 1


def _increment_old_index(state: dict):
    """Increment only the old line index."""
    state["old_idx"] += 1


def _increment_new_index(state: dict):
    """Increment only the new line index."""
    state["new_idx"] += 1


def _update_indices_for_replace(i1: int, i2: int, j1: int, j2: int, k: int, state: dict):
    """Update indices for replace operation."""
    if i1 + k < i2:
        _increment_old_index(state)
    if j1 + k < j2:
        _increment_new_index(state)

