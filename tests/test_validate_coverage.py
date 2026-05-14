"""Unit tests for validate_coverage.py — coverage matrix validation."""
from __future__ import annotations

import validate_coverage as vc


def test_extract_chapter_controls():
    md = """
| # | Description | Level |
| :---: | :--- | :---: |
| **1.1.1** | First control | 2 |
| **1.1.2** | Second control | 2 |
| **1.2.1** | Third control | 1 |
"""
    assert vc.extract_chapter_controls(md) == ["1.1.1", "1.1.2", "1.2.1"]


def test_extract_response_controls_from_table_only():
    response = """
Some prose mentioning 1.1.1 outside a table.

| Control | Lines | Verdict | Rationale |
| V1.1.1 | 5-10 | Fail | quoted |
| 1.1.2  | —    | Pass | satisfied |
| 1.2.1  | —    | N/A  | not applicable |

More prose: 1.1.3 should not be counted (no table row).
"""
    found = vc.extract_response_controls(response)
    # Both V-prefixed and bare forms parse to the bare control id
    assert sorted(found) == ["1.1.1", "1.1.2", "1.2.1"]


def test_extract_response_controls_handles_v_prefix():
    response = "| V1.1.1 | x | x | x |\n"
    found = vc.extract_response_controls(response)
    assert "1.1.1" in found


def test_extract_response_controls_skips_non_table_lines():
    response = "1.1.1 appears in prose but not in any table line.\n"
    found = vc.extract_response_controls(response)
    assert found == []
