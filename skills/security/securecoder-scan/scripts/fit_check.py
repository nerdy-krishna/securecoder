#!/usr/bin/env python3
"""Score each overlay compliance framework's fit to a repo's language profile.

`/securecoder-scan` Phase B runs the LLM compliance pass per (file ×
chapter) pair. When the configured framework targets a domain the repo
isn't in — ASVS (web) over a C kernel routine — most controls evaluate
to N/A and the run burns tokens for little signal.

fit_check.py runs pre-flight (zero LLM tokens). For each `overlay`-layer
framework it computes:

    fit_pct = (repo source files whose language ∈ target_languages)
              / (total repo source files) × 100

`baseline`-layer frameworks (secure-coding-essentials) always run and
are reported as such — no fit question.

When an overlay's fit_pct falls below the threshold AND none of its
`signal_globs` match a file in the repo, it's flagged `poor-fit`. A
signal-glob match (e.g. a `package.json` in a mostly-C repo — a Node
C-extension) rescues a borderline case to `borderline` instead.

Non-enabled overlays whose fit_pct clears the threshold are reported in
`suggested_enable` so the scan can nudge ("this looks like a mobile
project — consider enabling MASVS").

Stdlib only.

Usage:
    python3 fit_check.py <repo_map.json> \\
        --frameworks-json <path> \\
        --active <comma-separated framework ids> \\
        --repo-root <path> \\
        [--threshold 15] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def language_profile(repo_map: dict) -> tuple:
    """Return ({language: count}, total_source_files)."""
    counts: dict = {}
    for f in repo_map.get("files", []):
        lang = f.get("language", "")
        counts[lang] = counts.get(lang, 0) + 1
    return counts, sum(counts.values())


def fit_pct(framework: dict, lang_counts: dict, total: int) -> float:
    targets = framework.get("target_languages", []) or []
    if "all" in targets:
        return 100.0
    if total == 0:
        return 0.0
    matched = sum(n for lang, n in lang_counts.items() if lang in targets)
    return round(100.0 * matched / total, 1)


def has_signal_file(framework: dict, repo_root: Path) -> bool:
    """True if any of the framework's signal_globs matches a file in the repo.

    Signal globs are bare filenames or patterns (e.g. `package.json`,
    `*.csproj`, `AndroidManifest.xml`). They rescue a borderline case —
    a low language-fit framework that's still relevant because a
    project-marker file is present.
    """
    for glob in framework.get("signal_globs", []) or []:
        # rglob from the repo root; strip a leading **/ if present
        pattern = glob[3:] if glob.startswith("**/") else glob
        for _ in repo_root.rglob(pattern):
            return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("repo_map", help="Path to repo_map.json from the walker")
    ap.add_argument("--frameworks-json", required=True,
                    help="Path to frameworks.json")
    ap.add_argument("--active", required=True,
                    help="Comma-separated list of active framework ids")
    ap.add_argument("--repo-root", required=True,
                    help="Project root (for signal-glob filesystem checks)")
    ap.add_argument("--threshold", type=float, default=15.0,
                    help="poor-fit threshold percentage (default 15)")
    ap.add_argument("--json", action="store_true",
                    help="Emit machine-readable JSON")
    args = ap.parse_args()

    with open(args.repo_map, encoding="utf-8") as f:
        repo_map = json.load(f)
    with open(args.frameworks_json, encoding="utf-8") as f:
        registry = json.load(f).get("_frameworks", {})

    repo_root = Path(args.repo_root).resolve()
    active = {a.strip() for a in args.active.split(",") if a.strip()}
    lang_counts, total = language_profile(repo_map)

    results: list = []
    poor_fit: list = []
    suggested_enable: list = []

    for fw_id, fw in registry.items():
        layer = fw.get("layer", "overlay")
        scannable = fw.get("scannable", True)
        if not scannable:
            continue

        if layer == "baseline":
            results.append({
                "id": fw_id, "layer": "baseline",
                "verdict": "baseline-always-runs",
            })
            continue

        # overlay
        pct = fit_pct(fw, lang_counts, total)
        is_active = fw_id in active
        signal = has_signal_file(fw, repo_root)

        if pct >= args.threshold:
            verdict = "good-fit"
        elif signal:
            verdict = "borderline"  # rescued by a project-marker file
        else:
            verdict = "poor-fit"

        entry = {
            "id": fw_id, "layer": "overlay", "active": is_active,
            "fit_pct": pct, "signal_file_present": signal,
            "verdict": verdict,
        }
        results.append(entry)

        if is_active and verdict == "poor-fit":
            poor_fit.append(fw_id)
        if (not is_active) and verdict == "good-fit":
            suggested_enable.append(fw_id)

    report = {
        "threshold_pct": args.threshold,
        "total_source_files": total,
        "language_profile": dict(sorted(lang_counts.items(), key=lambda kv: -kv[1])),
        "frameworks": results,
        "poor_fit": poor_fit,
        "suggested_enable": suggested_enable,
    }

    if args.json:
        sys.stdout.write(json.dumps(report, indent=2) + "\n")
    else:
        sys.stdout.write(f"Framework fit (threshold {args.threshold}%):\n")
        for r in results:
            if r["layer"] == "baseline":
                sys.stdout.write(f"  {r['id']:28s} baseline — always runs\n")
            else:
                flag = {"good-fit": "ok", "borderline": "borderline",
                        "poor-fit": "POOR FIT"}[r["verdict"]]
                sys.stdout.write(
                    f"  {r['id']:28s} {r['fit_pct']:5.1f}%  {flag}\n"
                )
        if poor_fit:
            sys.stdout.write(f"\nPoor-fit active overlays: {', '.join(poor_fit)}\n")
        if suggested_enable:
            sys.stdout.write(f"Consider enabling: {', '.join(suggested_enable)}\n")

    # Exit 1 when there's a poor-fit active overlay (so the caller can branch)
    sys.exit(1 if poor_fit else 0)


if __name__ == "__main__":
    main()
