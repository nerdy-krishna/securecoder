"""Pytest configuration — adds the scan skill's scripts dir to sys.path so
test modules can import apply_suppressions, compute_clusters, etc.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_SCRIPTS = REPO_ROOT / "skills" / "security" / "securecoder-scan" / "scripts"
SUPPRESS_SCRIPTS = REPO_ROOT / "skills" / "security" / "securecoder-suppress" / "scripts"
REVIEW_SCRIPTS = REPO_ROOT / "skills" / "security" / "securecoder-review" / "scripts"
FIX_SCRIPTS = REPO_ROOT / "skills" / "security" / "securecoder-fix" / "scripts"

for p in (SCAN_SCRIPTS, SUPPRESS_SCRIPTS, REVIEW_SCRIPTS, FIX_SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
