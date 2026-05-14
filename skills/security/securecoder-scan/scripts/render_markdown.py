#!/usr/bin/env python3
"""Render a securecoder run as a Markdown report.

Reads findings.jsonl and manifest.json from a run directory and emits a
human-readable markdown report. Designed for the slice 02 SAST-only path;
the compliance posture section is a placeholder filled in by slice 07,
and the cross-run trend section is filled in by slice 04.

Stdlib only.

Usage:
    python3 render_markdown.py <findings-jsonl> \\
        --manifest <manifest-json> \\
        [--output <path>]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


SEV_ORDER = ["critical", "high", "medium", "low", "info"]
SEV_LABEL = {
    "critical": "CRITICAL",
    "high":     "HIGH    ",
    "medium":   "MEDIUM  ",
    "low":      "LOW     ",
    "info":     "INFO    ",
}


def load_findings(path: Path) -> list[dict]:
    findings: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            findings.append(json.loads(line))
    return findings


def severity_rank(sev: str) -> int:
    try:
        return SEV_ORDER.index(sev)
    except ValueError:
        return len(SEV_ORDER)


def render(findings: list[dict], manifest: dict) -> str:
    out: list[str] = []

    out.append(f"# securecoder scan report — `{manifest.get('run_id', '')}`\n")
    out.append(f"- **Project root:** `{manifest.get('repo_root', '')}`")
    out.append(f"- **Repo commit:** `{manifest.get('repo_sha', 'no-git')}`")
    out.append(f"- **Started:** {manifest.get('started_at', '')}")
    out.append(f"- **Finished:** {manifest.get('finished_at', '')}")
    out.append(f"- **Schema version:** {manifest.get('schema_version', '1.0')}")
    out.append("")

    # --- Summary
    out.append("## Summary\n")
    sev_counts = Counter(f.get("severity", "info") for f in findings)
    total = len(findings)
    out.append(f"- **Total findings:** {total}")
    if total > 0:
        for sev in SEV_ORDER:
            if sev_counts.get(sev):
                out.append(f"  - {sev}: {sev_counts[sev]}")
    source_counts = Counter(f.get("source", "unknown") for f in findings)
    if source_counts:
        out.append("- **By source:**")
        for src, n in sorted(source_counts.items(), key=lambda kv: -kv[1]):
            out.append(f"  - {src}: {n}")
    out.append("")

    # --- Phase data (token usage, durations)
    phases = manifest.get("phases", {}) or {}
    if phases:
        out.append("## Phases\n")
        for phase, data in phases.items():
            dur = data.get("duration_s", 0)
            phase_findings = data.get("findings", 0)
            in_toks = data.get("input_tokens", 0)
            out_toks = data.get("output_tokens", 0)
            extras = ""
            if in_toks or out_toks:
                extras = f"; tokens in/out: {in_toks}/{out_toks}"
            out.append(
                f"- **{phase}** — {dur}s, {phase_findings} findings{extras}"
            )
        out.append("")

    # --- Compliance posture (placeholder; populated in slice 07)
    posture = manifest.get("compliance_posture") or {}
    if posture:
        out.append("## Compliance posture\n")
        for framework, scores in posture.items():
            evald = scores.get("controls_evaluated", 0)
            passing = scores.get("controls_passing", 0)
            with_findings = scores.get("controls_with_findings", 0)
            score = scores.get("posture_score", 0.0)
            out.append(
                f"- **{framework}** — {passing}/{evald} controls passing "
                f"({with_findings} with findings); score: {score:.2f}"
            )
        out.append("")

    # --- Trend (placeholder; populated in slice 04)
    trend = manifest.get("trend") or {}
    if trend:
        out.append("## Trend\n")
        out.append(f"- **New since last run:** {len(trend.get('new', []))}")
        out.append(
            f"- **Resolved since last run:** {len(trend.get('resolved', []))}"
        )
        out.append(
            f"- **Persistent across runs:** {len(trend.get('persistent', []))}"
        )
        out.append("")

    # --- Findings
    if findings:
        by_file: dict[str, list[dict]] = defaultdict(list)
        for f in findings:
            by_file[f.get("file", "(unknown)")].append(f)

        def file_rank(items: list[dict]) -> int:
            return min(severity_rank(f.get("severity", "info")) for f in items)

        out.append("## Findings\n")
        sorted_files = sorted(
            by_file.keys(),
            key=lambda p: (file_rank(by_file[p]), -len(by_file[p]), p),
        )
        for filepath in sorted_files:
            items = by_file[filepath]
            items.sort(key=lambda f: (
                severity_rank(f.get("severity", "info")),
                (f.get("lines") or {}).get("start", 0),
            ))
            count_label = f"{len(items)} finding{'s' if len(items) != 1 else ''}"
            out.append(f"### `{filepath}` — {count_label}\n")
            for f in items:
                sev_label = SEV_LABEL.get(f.get("severity", "info"), "INFO")
                lines = f.get("lines") or {}
                start = lines.get("start")
                end = lines.get("end")
                if start and end and end != start:
                    line_disp = f"L{start}-{end}"
                elif start:
                    line_disp = f"L{start}"
                else:
                    line_disp = "(no line)"

                title = f.get("title") or f.get("source_rule_id", "")
                out.append(f"- `{sev_label}`  **{title}**  ({line_disp})")
                desc = (f.get("description") or "").replace("\n", " ").strip()
                if desc:
                    out.append(f"  - {desc}")
                cwe = f.get("cwe") or []
                if cwe:
                    out.append(f"  - CWE: {', '.join(cwe)}")
                fr = f.get("framework_refs") or []
                if fr:
                    parts = []
                    for ref in fr:
                        ctrl = ref.get("control") or ref.get("category") or ""
                        parts.append(f"{ref.get('framework', '?')} {ctrl}")
                    out.append(f"  - Frameworks: {', '.join(parts)}")
                evidence = f.get("evidence", "").strip()
                if evidence:
                    truncated = evidence.replace("\n", " ⏎ ")
                    if len(truncated) > 160:
                        truncated = truncated[:160] + "…"
                    out.append(f"  - Evidence: `{truncated}`")
                hint = (f.get("remediation_hint") or "").strip()
                if hint:
                    out.append(f"  - Remediation: {hint}")
                out.append(
                    f"  - Rule: `{f.get('source_rule_id', '')}`  ·  "
                    f"ID: `{f.get('id', '')[:12]}…`  ·  "
                    f"confidence: {f.get('confidence', '?')}"
                )
                out.append("")
    else:
        out.append("## Findings\n")
        out.append("No findings. Clean scan.\n")

    # --- Manifest footer
    out.append("## Manifest\n")
    tools = manifest.get("tools") or {}
    if tools:
        out.append("**Tools:**")
        for name, ver in tools.items():
            out.append(f"  - {name}: `{ver}`")
    rule_packs = manifest.get("rule_packs") or {}
    if rule_packs:
        out.append("**Rule packs:**")
        for name, sha in rule_packs.items():
            short = sha[:12] if isinstance(sha, str) and len(sha) >= 12 else sha
            out.append(f"  - {name} @ `{short}`")
    frameworks = manifest.get("frameworks") or {}
    if frameworks:
        out.append("**Frameworks:**")
        for name, ver in frameworks.items():
            out.append(f"  - {name}: `{ver}`")
    out.append("")
    out.append("---")
    out.append(
        f"Generated by securecoder. Run directory: "
        f"`.securecoder/runs/{manifest.get('run_id', '')}/`"
    )

    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("findings", help="Path to findings.jsonl")
    ap.add_argument("--manifest", required=True,
                    help="Path to manifest.json")
    ap.add_argument("--output", "-o",
                    help="Write markdown here instead of stdout")
    args = ap.parse_args()

    findings = load_findings(Path(args.findings))
    with open(args.manifest, encoding="utf-8") as f:
        manifest = json.load(f)

    rendered = render(findings, manifest)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)


if __name__ == "__main__":
    main()
