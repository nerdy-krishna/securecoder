"""Unit tests for scan_annotations.py — annotation parsing + target-line
resolution.
"""
from __future__ import annotations

import scan_annotations as sa


def test_line_only_annotation_targets_next_code_line():
    content = "\n".join([
        "def f():",
        "    # securecoder: ignore reason=\"validated upstream\"",
        "    return db.execute(query)",
        "",
    ])
    entries = sa.scan_file("a.py", content)
    assert len(entries) == 1
    e = entries[0]
    assert e["match"]["file"] == "a.py"
    assert e["match"]["lines"] == {"start": 3, "end": 3}
    assert e["reason"] == "validated upstream"
    assert e["source"] == "annotation"
    assert e["created_by"] == "<annotation>"


def test_inline_annotation_targets_same_line():
    content = "    PASSWORD = 'sup3r'  # securecoder: ignore reason=\"dev-only\"\n"
    entries = sa.scan_file("conf.py", content)
    assert len(entries) == 1
    e = entries[0]
    assert e["match"]["lines"] == {"start": 1, "end": 1}
    assert e["reason"] == "dev-only"


def test_annotation_without_reason_falls_back_to_marker():
    content = "x = 1  # securecoder: ignore\n"
    entries = sa.scan_file("a.py", content)
    assert len(entries) == 1
    assert entries[0]["reason"] == "(in-source annotation)"


def test_expires_attribute_parsed():
    content = (
        "# securecoder: ignore reason=\"x\" expires=\"2027-01-01\"\n"
        "y = 2\n"
    )
    entries = sa.scan_file("a.py", content)
    assert len(entries) == 1
    assert entries[0]["expires_at"] == "2027-01-01"


def test_js_double_slash_comment_supported():
    content = "function f() { return x; } // securecoder: ignore reason=\"safe\"\n"
    entries = sa.scan_file("app.js", content)
    assert len(entries) == 1
    assert entries[0]["reason"] == "safe"


def test_line_only_at_end_of_file_skipped():
    content = "code\n# securecoder: ignore reason=\"dangling\"\n"
    entries = sa.scan_file("a.py", content)
    # No code line after the annotation → entry not emitted
    assert len(entries) == 0


def test_multiple_annotations_per_file():
    content = "\n".join([
        "x = 1  # securecoder: ignore reason=\"a\"",
        "y = 2",
        "# securecoder: ignore reason=\"b\"",
        "z = 3",
        "# securecoder: ignore reason=\"c\"",
        "",
        "# a normal comment",
        "w = 4",
    ])
    entries = sa.scan_file("a.py", content)
    assert len(entries) == 3
    assert entries[0]["match"]["lines"]["start"] == 1
    assert entries[0]["reason"] == "a"
    assert entries[1]["match"]["lines"]["start"] == 4
    assert entries[1]["reason"] == "b"
    # Third annotation: comment-only line 5, blank line 6, normal comment 7,
    # then code at line 8.
    assert entries[2]["match"]["lines"]["start"] == 8
    assert entries[2]["reason"] == "c"


def test_no_annotations_returns_empty_list():
    content = "# regular comment\nx = 1\n"
    assert sa.scan_file("a.py", content) == []
