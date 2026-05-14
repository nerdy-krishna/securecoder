"""Unit tests for diff_scoper.py — git diff → per-file changed line ranges."""
from __future__ import annotations

import diff_scoper as ds


def _parse(diff_text: str) -> list:
    return ds.parse_diff(diff_text)


def test_simple_added_lines():
    diff = """\
diff --git a/a.py b/a.py
index abc..def 100644
--- a/a.py
+++ b/a.py
@@ -1,3 +1,4 @@
 def foo():
-    return 1
+    return 2
+    # extra
     pass
"""
    files = _parse(diff)
    assert len(files) == 1
    f = files[0]
    assert f["path"] == "a.py"
    assert f["added_line_count"] == 2
    assert f["removed_line_count"] == 1
    # post-image line numbers: lines 2 and 3 are added
    assert len(f["added_ranges"]) >= 1


def test_new_file_creation():
    diff = """\
diff --git a/new.py b/new.py
new file mode 100644
index 000..abc
--- /dev/null
+++ b/new.py
@@ -0,0 +1,3 @@
+def hello():
+    return "world"
+
"""
    files = _parse(diff)
    assert len(files) == 1
    assert files[0]["path"] == "new.py"
    assert files[0]["is_new"]
    assert files[0]["added_line_count"] == 3


def test_deleted_file_filtered_out():
    diff = """\
diff --git a/gone.py b/gone.py
deleted file mode 100644
index abc..000
--- a/gone.py
+++ /dev/null
@@ -1,2 +0,0 @@
-x = 1
-y = 2
"""
    # The walker drops deleted files from its output
    files = _parse(diff)
    assert all(not f.get("is_deleted") for f in files)


def test_multi_file_diff():
    diff = """\
diff --git a/a.py b/a.py
index abc..def 100644
--- a/a.py
+++ b/a.py
@@ -1 +1,2 @@
 x = 1
+y = 2
diff --git a/b.py b/b.py
index ghi..jkl 100644
--- a/b.py
+++ b/b.py
@@ -10,2 +10,3 @@
 def f():
+    z = 3
     return
"""
    files = _parse(diff)
    assert len(files) == 2
    paths = {f["path"] for f in files}
    assert paths == {"a.py", "b.py"}


def test_context_windows_merged():
    diff = """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,1 +1,3 @@
 line1
+added2
+added3
"""
    files = _parse(diff)
    ds.add_context_windows(files, context=5)
    # The two added lines are adjacent → one window
    assert len(files[0]["context_windows"]) == 1
    w = files[0]["context_windows"][0]
    assert w["start"] == 1  # max(1, 2-5)
    assert w["end"] >= 3


def test_empty_diff():
    files = _parse("")
    assert files == []
