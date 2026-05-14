"""Unit tests for apply_patch.py — SEARCH/REPLACE block parsing + atomic apply."""
from __future__ import annotations

import apply_patch as ap


def test_parse_single_block():
    patch = """\
Some preamble.

<<<<<<< SEARCH
def old():
    return 1
=======
def new():
    return 2
>>>>>>> REPLACE

Trailing note.
"""
    blocks = ap.parse_blocks(patch)
    assert len(blocks) == 1
    assert blocks[0]["search"] == "def old():\n    return 1"
    assert blocks[0]["replace"] == "def new():\n    return 2"


def test_parse_multiple_blocks_in_order():
    patch = """\
<<<<<<< SEARCH
a
=======
A
>>>>>>> REPLACE

<<<<<<< SEARCH
b
=======
B
>>>>>>> REPLACE
"""
    blocks = ap.parse_blocks(patch)
    assert len(blocks) == 2
    assert blocks[0]["search"] == "a"
    assert blocks[1]["search"] == "b"


def test_apply_blocks_happy_path():
    content = "x = 1\ny = 2\nz = 3\n"
    blocks = [{"search": "y = 2", "replace": "y = 99"}]
    new_content, details = ap.apply_blocks(content, blocks)
    assert "y = 99" in new_content
    assert "y = 2" not in new_content
    assert details[0]["status"] == "ok"


def test_apply_blocks_no_match_aborts():
    content = "x = 1\n"
    blocks = [{"search": "not-in-file", "replace": "y = 99"}]
    new_content, details = ap.apply_blocks(content, blocks)
    # Atomicity: file unchanged
    assert new_content == content
    assert details[0]["status"] == "no_match"


def test_apply_blocks_multiple_match_aborts():
    content = "y = 2\ny = 2\nz = 3\n"
    blocks = [{"search": "y = 2", "replace": "y = 99"}]
    new_content, details = ap.apply_blocks(content, blocks)
    # Atomicity: file unchanged when SEARCH is ambiguous
    assert new_content == content
    assert details[0]["status"] == "multiple_match"
    assert details[0]["match_count"] == 2


def test_apply_blocks_atomic_across_multiple():
    content = "a\nb\nc\n"
    blocks = [
        {"search": "a", "replace": "A"},  # would succeed
        {"search": "not-here", "replace": "X"},  # fails
    ]
    new_content, details = ap.apply_blocks(content, blocks)
    # Atomicity: if any block fails, NO blocks land
    assert new_content == content
    assert details[0]["status"] == "ok"
    assert details[1]["status"] == "no_match"


def test_parse_blocks_returns_empty_on_no_blocks():
    assert ap.parse_blocks("just some prose, no markers") == []
