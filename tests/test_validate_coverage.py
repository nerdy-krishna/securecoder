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


# ─── per-framework regex (v1.3.0) ───


def test_extract_chapter_controls_sce_format():
    md = """
| # | Description | CWE |
| **SCE-MEM-1** | Verify bounds | CWE-787 |
| **SCE-MEM-2** | Verify reads | CWE-125 |
"""
    regex = r"\*\*(SCE-[A-Z]+-\d+)\*\*"
    assert vc.extract_chapter_controls(md, regex) == ["SCE-MEM-1", "SCE-MEM-2"]


def test_extract_response_controls_sce_format():
    response = "| Control | Verdict |\n| SCE-MEM-1 | Fail |\n| SCE-INT-3 | Pass |\n"
    regex = r"\b(SCE-[A-Z]+-\d+)\b"
    found = vc.extract_response_controls(response, regex)
    assert sorted(found) == ["SCE-INT-3", "SCE-MEM-1"]


def test_extract_chapter_controls_masvs_format():
    md = "| **MASVS-STORAGE-1** | x |\n| **MASVS-CRYPTO-2** | y |\n"
    regex = r"\*\*(MASVS-[A-Z]+-\d+)\*\*"
    assert vc.extract_chapter_controls(md, regex) == ["MASVS-CRYPTO-2", "MASVS-STORAGE-1"]


def test_default_regexes_still_asvs():
    # Backwards-compat: calling without a regex arg uses the ASVS form
    md = "| **1.2.1** | x |\n"
    assert vc.extract_chapter_controls(md) == ["1.2.1"]
