"""Unit tests for syntax_check.py — language-agnostic syntax dispatcher."""
from __future__ import annotations

import syntax_check as sc


def test_check_json_stdlib_happy_path(tmp_path):
    p = tmp_path / "ok.json"
    p.write_text('{"a": 1}\n')
    code, msg, method = sc.check_json_stdlib(p)
    assert code == 0
    assert msg == ""


def test_check_json_stdlib_invalid(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json\n")
    code, msg, _ = sc.check_json_stdlib(p)
    assert code == 1
    assert "JSON parse error" in msg


def test_check_utf8_happy_path(tmp_path):
    p = tmp_path / "ok.txt"
    p.write_text("clean utf-8 content\n")
    code, msg, method = sc.check_utf8(p)
    assert code == 0
    assert method == "utf8_fallback"


def test_check_utf8_invalid(tmp_path):
    p = tmp_path / "bad.bin"
    p.write_bytes(b"\xff\xfe\xfd not utf-8")
    code, msg, _ = sc.check_utf8(p)
    assert code == 1
    assert "not valid UTF-8" in msg


def test_checkers_table_has_expected_extensions():
    assert ".py" in sc.CHECKERS
    assert ".js" in sc.CHECKERS
    assert ".go" in sc.CHECKERS
    assert ".rb" in sc.CHECKERS
    # JSON handled by stdlib, not the CHECKERS table
    assert ".json" not in sc.CHECKERS
