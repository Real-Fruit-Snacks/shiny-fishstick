"""Diff computation utilities for Delta Vision.

This module provides text comparison functionality using Python's difflib
to generate line-by-line diff data suitable for UI rendering.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum
from typing import Optional

from .io import safe_read_lines


class DiffType(Enum):
    """Enumeration of diff row types."""

    UNCHANGED = "equal"
    ADDED = "insert"
    DELETED = "delete"
    MODIFIED = "replace"


@dataclass
class DiffRow:
    """Represents a single row in a diff comparison."""

    diff_type: DiffType
    left_line_num: Optional[int]
    right_line_num: Optional[int]
    left_content: str
    right_content: str


def compute_diff_rows(old_input, new_input) -> list[DiffRow]:
    """Compute diff rows between two file paths or line lists - orchestrator for diff computation.

    Args:
        old_input: Either a file path (str) or list of lines
        new_input: Either a file path (str) or list of lines

    Returns:
        List of DiffRow objects representing the comparison
    """
    # Handle both file paths and line lists
    old_lines = _get_lines_from_input(old_input)
    new_lines = _get_lines_from_input(new_input)

    state = _initialize_diff_state(old_lines, new_lines)

    for opcode in state["matcher"].get_opcodes():
        _process_opcode(opcode, state)

    return state["rows"]


def _get_lines_from_input(input_data):
    """Get lines from either file path or list input."""
    if isinstance(input_data, str):
        # It's a file path
        try:
            result = safe_read_lines(input_data)
            if result.success:
                return result.lines
            else:
                return []  # Return empty list for failed reads
        except Exception:
            return []  # Handle any unexpected errors
    elif isinstance(input_data, list):
        # It's already a list of lines
        return input_data
    else:
        return []  # Fallback for unexpected input types


def _initialize_diff_state(old_lines: list[str], new_lines: list[str]) -> dict:
    """Initialize state for diff computation."""
    return {
        "rows": [],
        "matcher": SequenceMatcher(None, old_lines, new_lines),
        "old_lines": old_lines,
        "new_lines": new_lines,
        "old_idx": 1,
        "new_idx": 1,
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
    return DiffRow(
        diff_type=DiffType.UNCHANGED,
        left_line_num=state["old_idx"],
        left_content=state["old_lines"][old_pos],
        right_line_num=state["new_idx"],
        right_content=state["new_lines"][new_pos],
    )


def _create_replace_row(i1: int, i2: int, j1: int, j2: int, k: int, state: dict) -> DiffRow:
    """Create a row for replaced lines."""
    o_text = state["old_lines"][i1 + k] if i1 + k < i2 else ""
    n_text = state["new_lines"][j1 + k] if j1 + k < j2 else ""
    o_ln = state["old_idx"] if i1 + k < i2 else None
    n_ln = state["new_idx"] if j1 + k < j2 else None

    return DiffRow(
        diff_type=DiffType.MODIFIED, left_line_num=o_ln, left_content=o_text, right_line_num=n_ln, right_content=n_text
    )


def _create_delete_row(old_pos: int, state: dict) -> DiffRow:
    """Create a row for deleted lines."""
    return DiffRow(
        diff_type=DiffType.DELETED,
        left_line_num=state["old_idx"],
        left_content=state["old_lines"][old_pos],
        right_line_num=None,
        right_content="",
    )


def _create_insert_row(new_pos: int, state: dict) -> DiffRow:
    """Create a row for inserted lines."""
    return DiffRow(
        diff_type=DiffType.ADDED,
        left_line_num=None,
        left_content="",
        right_line_num=state["new_idx"],
        right_content=state["new_lines"][new_pos],
    )


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
