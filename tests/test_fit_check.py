"""Unit tests for fit_check.py — framework fit scoring."""
from __future__ import annotations

import fit_check as fc


def test_language_profile_counts_and_total():
    repo_map = {"files": [
        {"language": "c"}, {"language": "c"}, {"language": "python"},
    ]}
    counts, total = fc.language_profile(repo_map)
    assert counts == {"c": 2, "python": 1}
    assert total == 3


def test_language_profile_empty_repo():
    counts, total = fc.language_profile({"files": []})
    assert counts == {}
    assert total == 0


def test_fit_pct_all_languages_is_100():
    fw = {"target_languages": ["all"]}
    assert fc.fit_pct(fw, {"c": 5}, 5) == 100.0


def test_fit_pct_no_overlap_is_zero():
    fw = {"target_languages": ["python", "javascript"]}
    assert fc.fit_pct(fw, {"c": 10}, 10) == 0.0


def test_fit_pct_partial_overlap():
    fw = {"target_languages": ["python"]}
    # 3 of 10 files are python
    assert fc.fit_pct(fw, {"python": 3, "c": 7}, 10) == 30.0


def test_fit_pct_empty_repo_is_zero():
    fw = {"target_languages": ["python"]}
    assert fc.fit_pct(fw, {}, 0) == 0.0


def test_has_signal_file_finds_marker(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    fw = {"signal_globs": ["package.json", "requirements.txt"]}
    assert fc.has_signal_file(fw, tmp_path)


def test_has_signal_file_finds_nested_marker(tmp_path):
    sub = tmp_path / "service"
    sub.mkdir()
    (sub / "go.mod").write_text("module x\n")
    fw = {"signal_globs": ["go.mod"]}
    assert fc.has_signal_file(fw, tmp_path)


def test_has_signal_file_glob_pattern(tmp_path):
    (tmp_path / "App.csproj").write_text("<Project/>")
    fw = {"signal_globs": ["*.csproj"]}
    assert fc.has_signal_file(fw, tmp_path)


def test_has_signal_file_no_match(tmp_path):
    (tmp_path / "main.c").write_text("int main(){}")
    fw = {"signal_globs": ["package.json", "go.mod"]}
    assert not fc.has_signal_file(fw, tmp_path)


def test_has_signal_file_no_globs_is_false(tmp_path):
    assert not fc.has_signal_file({}, tmp_path)
    assert not fc.has_signal_file({"signal_globs": []}, tmp_path)
