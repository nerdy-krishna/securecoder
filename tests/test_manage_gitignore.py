"""Unit tests for manage_gitignore.py — root .gitignore reconciliation."""
from __future__ import annotations

import subprocess
from pathlib import Path

import manage_gitignore as mg


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)


# --- render_block / block_body ------------------------------------------------

def test_render_block_runs_and_reviews():
    b = mg.render_block("runs-and-reviews")
    assert b.startswith(mg.BEGIN)
    assert b.rstrip().endswith(mg.END)
    assert ".securecoder/runs/" in b
    assert ".securecoder/reviews/" in b


def test_render_block_whole_folder():
    b = mg.render_block("whole-folder")
    assert ".securecoder/\n" in b
    assert ".securecoder/runs/" not in b


# --- apply_strategy: create / append / idempotency ----------------------------

def test_apply_creates_file_when_absent(tmp_path):
    gi = tmp_path / ".gitignore"
    assert mg.apply_strategy(gi, "runs-and-reviews") == "created"
    text = gi.read_text()
    assert mg.BEGIN in text and mg.END in text
    assert ".securecoder/runs/" in text


def test_apply_appends_preserving_existing_content(tmp_path):
    gi = tmp_path / ".gitignore"
    gi.write_text("node_modules/\n*.log\n")
    assert mg.apply_strategy(gi, "runs-and-reviews") == "updated"
    text = gi.read_text()
    assert "node_modules/" in text and "*.log" in text
    # Existing rules stay above the managed block.
    assert text.index("node_modules/") < text.index(mg.BEGIN)


def test_apply_is_idempotent(tmp_path):
    gi = tmp_path / ".gitignore"
    mg.apply_strategy(gi, "runs-and-reviews")
    assert mg.apply_strategy(gi, "runs-and-reviews") == "unchanged"
    assert gi.read_text().count(mg.BEGIN) == 1


def test_apply_handles_existing_file_without_trailing_newline(tmp_path):
    gi = tmp_path / ".gitignore"
    gi.write_text("dist/")  # no trailing newline
    mg.apply_strategy(gi, "runs-and-reviews")
    text = gi.read_text()
    assert "dist/\n" in text
    assert text.count(mg.BEGIN) == 1


# --- apply_strategy: strategy change ------------------------------------------

def test_strategy_change_replaces_block(tmp_path):
    gi = tmp_path / ".gitignore"
    mg.apply_strategy(gi, "runs-and-reviews")
    assert mg.apply_strategy(gi, "whole-folder") == "updated"
    text = gi.read_text()
    assert text.count(mg.BEGIN) == 1
    assert ".securecoder/runs/" not in text
    assert ".securecoder/\n" in text


# --- apply_strategy: none -----------------------------------------------------

def test_none_removes_block_keeps_other_content(tmp_path):
    gi = tmp_path / ".gitignore"
    gi.write_text("node_modules/\n")
    mg.apply_strategy(gi, "runs-and-reviews")
    assert mg.apply_strategy(gi, "none") == "removed"
    text = gi.read_text()
    assert mg.BEGIN not in text
    assert "node_modules/" in text


def test_none_deletes_file_when_block_was_only_content(tmp_path):
    gi = tmp_path / ".gitignore"
    mg.apply_strategy(gi, "runs-and-reviews")
    assert mg.apply_strategy(gi, "none") == "removed"
    assert not gi.exists()


def test_none_unchanged_when_no_block(tmp_path):
    gi = tmp_path / ".gitignore"
    gi.write_text("node_modules/\n")
    assert mg.apply_strategy(gi, "none") == "unchanged"
    assert gi.read_text() == "node_modules/\n"


# --- git detection ------------------------------------------------------------

def test_is_git_repo_false_for_plain_dir(tmp_path):
    assert mg.is_git_repo(tmp_path) is False


def test_is_git_repo_true_for_initialised_repo(tmp_path):
    _git_init(tmp_path)
    assert mg.is_git_repo(tmp_path) is True


def test_tracked_files_detects_committed_securecoder_files(tmp_path):
    _git_init(tmp_path)
    sc = tmp_path / ".securecoder"
    sc.mkdir()
    (sc / "config.json").write_text("{}\n")
    subprocess.run(["git", "add", ".securecoder/config.json"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "add config"], cwd=tmp_path, check=True)
    assert ".securecoder/config.json" in mg.tracked_securecoder_files(tmp_path)


def test_tracked_files_empty_when_nothing_tracked(tmp_path):
    _git_init(tmp_path)
    assert mg.tracked_securecoder_files(tmp_path) == []
