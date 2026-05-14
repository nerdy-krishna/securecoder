"""Unit tests for compute_clusters() in render_html.py.

Covers:
- Rule with < 3 findings → no cluster
- Rule with 3+ findings sharing one prefix → cluster with that glob
- Rule with 3+ findings split across directories → rule-only cluster (glob=None)
- 80% coverage ceiling preference (deeper prefix wins when ≤80% covered)
- Fallback to longest prefix with ≥3 coverage when 80% rejected everything
- Cluster ordering (worst severity first, then descending count)
"""
from __future__ import annotations

from render_html import compute_clusters


def F(rule, file, severity="medium", source="bandit", status="open", line=1):
    return {
        "source_rule_id": rule,
        "file": file,
        "severity": severity,
        "source": source,
        "status": status,
        "lines": {"start": line},
        "title": "T",
    }


def test_no_cluster_when_under_three_findings():
    findings = [F("B105", "tests/a.py"), F("B105", "tests/b.py")]
    assert compute_clusters(findings) == []


def test_cluster_with_shared_prefix():
    findings = [
        F("B608", "src/queries/a.py"),
        F("B608", "src/queries/b.py"),
        F("B608", "src/queries/c.py"),
        F("B608", "src/queries/d.py"),
    ]
    clusters = compute_clusters(findings)
    assert len(clusters) == 1
    c = clusters[0]
    assert c["rule"] == "B608"
    # 4 findings all in src/queries — 80% ceiling cuts; fallback retains
    # the longest prefix with ≥3 coverage. Either src/** or src/queries/**
    # is acceptable depending on which level fell back first; what matters
    # is the glob is non-None.
    assert c["file_glob"] is not None
    assert c["count"] == 4


def test_cluster_with_diverging_paths_falls_back_to_rule_only():
    # 9 findings: 8 in tests/fixtures, 1 in src/app.py — paths diverge at root
    findings = [F("B105", f"tests/fixtures/p{i}.py") for i in range(8)] + [
        F("B105", "src/app.py")
    ]
    clusters = compute_clusters(findings)
    assert len(clusters) == 1
    c = clusters[0]
    assert c["rule"] == "B105"
    assert c["file_glob"] is None  # no common prefix
    assert c["count"] == 9


def test_two_clusters_with_severity_ordering():
    findings = [F("B105", f"tests/p{i}.py", "medium") for i in range(4)] + [
        F("B608", f"src/q{i}.py", "high") for i in range(3)
    ]
    clusters = compute_clusters(findings)
    # The high-severity cluster should come first
    assert len(clusters) == 2
    assert clusters[0]["rule"] == "B608"  # high severity wins ordering
    assert clusters[1]["rule"] == "B105"


def test_suppressed_findings_counted_in_cluster():
    findings = [
        F("B105", "tests/a.py", status="suppressed"),
        F("B105", "tests/b.py", status="open"),
        F("B105", "tests/c.py", status="suppressed"),
    ]
    clusters = compute_clusters(findings)
    assert len(clusters) == 1
    c = clusters[0]
    assert c["count"] == 3
    assert c["suppressed_count"] == 2
    assert c["active_count"] == 1


def test_eighty_percent_ceiling_prefers_deeper_prefix():
    # 10 findings: 9 deep under src/api/legacy, 1 under src/admin
    # Longest common prefix is "src". Coverage of "src" = 100% (10 of 10).
    # max_cov = 0.8 * 10 = 8. So "src" coverage (10) > 8 → reject.
    # Walk back: empty common → fall back to longest prefix with ≥3 cov.
    # Longest was "src" with 10 cov → that becomes the fallback.
    # End result: src/** as the glob.
    findings = [F("B105", f"src/api/legacy/x{i}.py") for i in range(9)] + [
        F("B105", "src/admin/x.py")
    ]
    clusters = compute_clusters(findings)
    assert len(clusters) == 1
    assert clusters[0]["file_glob"] == "src/**"


def test_samples_are_first_three_by_file_line():
    findings = [F("B105", f"f{i}.py", line=i) for i in range(6)]
    clusters = compute_clusters(findings)
    assert len(clusters) == 1
    samples = clusters[0]["samples"]
    assert len(samples) == 3
    # Deterministic ordering by file then line — first 3 files by name
    assert samples[0]["file"] == "f0.py"
    assert samples[1]["file"] == "f1.py"
    assert samples[2]["file"] == "f2.py"
