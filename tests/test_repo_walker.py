"""Unit tests for repo_walker.py — file inventory + language detection."""
from __future__ import annotations

import os

import pytest

import repo_walker as rw


def _make_project(tmp_path, files: dict):
    """Helper: write a dict of {relative_path: content} into tmp_path."""
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def test_language_detection_by_extension(tmp_path):
    _make_project(tmp_path, {
        "app.py": "print('hi')\n",
        "main.js": "console.log('hi');\n",
        "lib.go": "package main\n",
    })
    records = rw.walk(tmp_path)
    by_path = {r["path"]: r["language"] for r in records}
    assert by_path["app.py"] == "python"
    assert by_path["main.js"] == "javascript"
    assert by_path["lib.go"] == "go"


def test_skip_dirs_pruned(tmp_path):
    _make_project(tmp_path, {
        "src/app.py": "code\n",
        "node_modules/lib/x.js": "should be skipped\n",
        ".venv/site-packages/x.py": "should be skipped\n",
        ".git/HEAD": "ref: refs/heads/main\n",
    })
    paths = {r["path"] for r in rw.walk(tmp_path)}
    assert "src/app.py" in paths
    assert not any("node_modules" in p for p in paths)
    assert not any(".venv" in p for p in paths)
    assert not any(".git" in p for p in paths)


def test_minified_files_skipped(tmp_path):
    _make_project(tmp_path, {
        "app.js": "good\n",
        "bundle.min.js": "minified\n",
        "styles.min.css": "minified\n",
    })
    paths = {r["path"] for r in rw.walk(tmp_path)}
    assert "app.js" in paths
    assert "bundle.min.js" not in paths
    assert "styles.min.css" not in paths


def test_large_files_skipped(tmp_path):
    _make_project(tmp_path, {
        "ok.py": "x = 1\n",
        "big.py": "y = 1\n" * 100_000,  # > 200 KB
    })
    paths = {r["path"] for r in rw.walk(tmp_path)}
    assert "ok.py" in paths
    assert "big.py" not in paths


def test_unrecognized_extensions_skipped(tmp_path):
    _make_project(tmp_path, {
        "data.csv": "a,b,c\n",
        "img.png.txt": "not really an image\n",  # .txt unrecognized
        "real.py": "x = 1\n",
    })
    paths = {r["path"] for r in rw.walk(tmp_path)}
    assert "real.py" in paths
    assert "data.csv" not in paths
    assert "img.png.txt" not in paths
