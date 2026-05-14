"""Unit tests for compute_trend.py — new/resolved/persistent finding diff."""
from __future__ import annotations

import json
from pathlib import Path

import compute_trend as ct


def _write_findings(path: Path, ids: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for fid in ids:
            f.write(json.dumps({"id": fid}) + "\n")


def test_load_finding_ids_basic(tmp_path):
    p = tmp_path / "findings.jsonl"
    _write_findings(p, ["a", "b", "c"])
    assert ct.load_finding_ids(p) == {"a", "b", "c"}


def test_load_finding_ids_handles_missing_file(tmp_path):
    p = tmp_path / "missing.jsonl"
    assert ct.load_finding_ids(p) == set()


def test_load_finding_ids_skips_blank_and_malformed_lines(tmp_path):
    p = tmp_path / "findings.jsonl"
    p.write_text('{"id": "a"}\n\n{"id": "b"}\nnot-json\n{"id": "c"}\n')
    assert ct.load_finding_ids(p) == {"a", "b", "c"}


def test_find_prior_run_picks_latest_chronological(tmp_path):
    runs_dir = tmp_path / "runs"
    for run_id in ["20260101T000000Z", "20260201T000000Z", "20260301T000000Z"]:
        _write_findings(runs_dir / run_id / "findings.jsonl", ["x"])
    prior = ct.find_prior_run(runs_dir, "20260401T000000Z")
    assert prior == "20260301T000000Z"


def test_find_prior_run_excludes_current(tmp_path):
    runs_dir = tmp_path / "runs"
    for run_id in ["20260101T000000Z", "20260201T000000Z"]:
        _write_findings(runs_dir / run_id / "findings.jsonl", ["x"])
    # If we ask about 20260101, no prior exists
    assert ct.find_prior_run(runs_dir, "20260101T000000Z") is None


def test_find_prior_run_skips_runs_without_findings(tmp_path):
    runs_dir = tmp_path / "runs"
    # Run 1 has findings, run 2 is crashed (no findings.jsonl)
    _write_findings(runs_dir / "20260101T000000Z" / "findings.jsonl", ["x"])
    (runs_dir / "20260201T000000Z").mkdir(parents=True)
    # Asking about a later run — should still find 20260101 (skip the empty one)
    prior = ct.find_prior_run(runs_dir, "20260301T000000Z")
    assert prior == "20260101T000000Z"


def test_find_prior_run_handles_missing_dir(tmp_path):
    missing = tmp_path / "no-such-dir"
    assert ct.find_prior_run(missing, "20260101T000000Z") is None
