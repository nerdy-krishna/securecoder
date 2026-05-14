#!/usr/bin/env python3
"""Render a securecoder run as a self-contained HTML report.

Self-contained means: all CSS inlined in a <style> block, all JS inlined
in a <script> block, no external <link>, <script src=>, or <img src=>
elements pointing at network resources. The report opens correctly in any
modern browser with networking disabled.

Includes client-side filtering by severity, source, framework, and a
free-text search across file path / title / description / evidence.

Stdlib only.

Usage:
    python3 render_html.py <findings-jsonl> \\
        --manifest <manifest-json> \\
        [--output <path>]
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


SEV_ORDER = ["critical", "high", "medium", "low", "info"]
SEV_LABELS = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "info": "Info",
}


CSS = """
  :root {
    --bg: #0e1116;
    --bg-card: #161b22;
    --bg-elev: #1f2630;
    --fg: #e6edf3;
    --fg-mute: #9da7b3;
    --border: #2a313a;
    --accent: #58a6ff;
    --crit: #f85149;
    --high: #f0883e;
    --med:  #d29922;
    --low:  #58a6ff;
    --info: #9da7b3;
    --good: #3fb950;
  }
  @media (prefers-color-scheme: light) {
    :root {
      --bg: #f6f8fa;
      --bg-card: #ffffff;
      --bg-elev: #f0f3f6;
      --fg: #1f2328;
      --fg-mute: #59636e;
      --border: #d0d7de;
      --accent: #0969da;
      --crit: #cf222e;
      --high: #bc4c00;
      --med:  #9a6700;
      --low:  #0969da;
      --info: #59636e;
      --good: #1a7f37;
    }
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: var(--bg); color: var(--fg); }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                 "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 14px;
    line-height: 1.5;
    padding: 24px;
    max-width: 1200px;
    margin: 0 auto;
  }
  h1, h2, h3 { line-height: 1.25; }
  h1 { font-size: 22px; margin: 0 0 8px; }
  h2 { font-size: 16px; margin: 24px 0 12px; padding-bottom: 6px;
       border-bottom: 1px solid var(--border); }
  code { font-family: SFMono-Regular, Consolas, "Liberation Mono",
                     Menlo, monospace;
         font-size: 0.92em;
         background: var(--bg-elev);
         padding: 1px 5px;
         border-radius: 3px;
         color: var(--fg); }
  a { color: var(--accent); }
  header { margin-bottom: 16px; }
  .meta { color: var(--fg-mute); font-size: 13px; }
  .meta-row { display: flex; flex-wrap: wrap; gap: 16px; }
  .meta-row span { white-space: nowrap; }
  .severity-counts { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
  .badge {
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    border-radius: 12px;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border: 1px solid currentColor;
  }
  .badge.critical { color: var(--crit); }
  .badge.high { color: var(--high); }
  .badge.medium { color: var(--med); }
  .badge.low { color: var(--low); }
  .badge.info { color: var(--info); }
  .badge.zero { opacity: 0.35; }
  table { border-collapse: collapse; width: 100%; font-size: 13px;
          margin-top: 8px; }
  th, td { text-align: left; padding: 6px 12px; border-bottom: 1px solid var(--border); }
  th { font-weight: 600; color: var(--fg-mute); }
  .trend-empty { color: var(--fg-mute); font-style: italic; }
  .trend-counts { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 6px; }
  .trend-counts .item {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 8px 14px;
    font-size: 13px;
  }
  .filters {
    position: sticky;
    top: 0;
    background: var(--bg);
    padding: 12px 0;
    z-index: 10;
    margin: 16px 0;
    border-bottom: 1px solid var(--border);
  }
  .filters .row { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
  .filters label { font-size: 13px; color: var(--fg-mute); display: flex; gap: 6px; align-items: center; }
  .filters select, .filters input {
    background: var(--bg-card);
    color: var(--fg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 4px 8px;
    font: inherit;
    min-width: 120px;
  }
  .filters input { min-width: 200px; }
  .result-count { color: var(--fg-mute); font-size: 13px; margin-top: 6px; }
  details.file-group {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 6px;
    margin: 10px 0;
    overflow: hidden;
  }
  details.file-group > summary {
    cursor: pointer;
    padding: 12px 16px;
    background: var(--bg-elev);
    font-weight: 500;
    list-style: none;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  details.file-group > summary::-webkit-details-marker { display: none; }
  details.file-group > summary::before {
    content: "▸";
    color: var(--fg-mute);
    font-size: 12px;
  }
  details.file-group[open] > summary::before { content: "▾"; }
  .file-group .file-name {
    flex: 1;
    font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
    overflow-wrap: anywhere;
  }
  .file-group .file-count {
    color: var(--fg-mute);
    font-size: 12px;
    white-space: nowrap;
  }
  article.finding {
    padding: 12px 16px;
    border-top: 1px solid var(--border);
  }
  .finding-header {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-bottom: 8px;
  }
  .finding-title { font-weight: 600; }
  .finding-loc { color: var(--fg-mute); font-size: 12px; font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace; }
  .finding-body p { margin: 6px 0; }
  .finding-body .description { color: var(--fg); }
  .finding-body .meta-line { color: var(--fg-mute); font-size: 12px; }
  .finding-body pre.evidence {
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 8px 12px;
    overflow-x: auto;
    font-size: 12px;
    white-space: pre-wrap;
    word-break: break-all;
  }
  .finding-body .frameworks code,
  .finding-body .cwe code { margin-right: 4px; }
  .hidden { display: none !important; }
  footer { margin-top: 32px; padding-top: 16px; border-top: 1px solid var(--border);
           color: var(--fg-mute); font-size: 12px; }
"""


# Tiny JS payload. Pure ES5-ish for compatibility. Listens to filter
# controls and toggles a `.hidden` class on findings + file groups.
# Updates the visible count.
JS = """
(function() {
  var sevSel = document.getElementById('filter-severity');
  var srcSel = document.getElementById('filter-source');
  var fwSel  = document.getElementById('filter-framework');
  var search = document.getElementById('filter-search');
  var visibleCount = document.getElementById('visible-count');
  var findings = Array.prototype.slice.call(
    document.querySelectorAll('article.finding')
  );
  var groups = Array.prototype.slice.call(
    document.querySelectorAll('details.file-group')
  );

  function refresh() {
    var sev = sevSel.value;
    var src = srcSel.value;
    var fw  = fwSel.value;
    var q   = (search.value || '').toLowerCase().trim();
    var visible = 0;

    findings.forEach(function(el) {
      var dataSev = el.getAttribute('data-severity') || '';
      var dataSrc = el.getAttribute('data-source') || '';
      var dataFw  = el.getAttribute('data-frameworks') || '';
      var dataTxt = el.getAttribute('data-text') || '';
      var match =
        (sev === 'all' || dataSev === sev) &&
        (src === 'all' || dataSrc === src) &&
        (fw  === 'all' || dataFw.split(' ').indexOf(fw) !== -1) &&
        (q === ''      || dataTxt.indexOf(q) !== -1);
      el.classList.toggle('hidden', !match);
      if (match) visible++;
    });

    // Hide file groups whose findings are all hidden
    groups.forEach(function(g) {
      var any = g.querySelectorAll('article.finding:not(.hidden)').length > 0;
      g.classList.toggle('hidden', !any);
    });

    visibleCount.textContent = visible;
  }

  sevSel.addEventListener('change', refresh);
  srcSel.addEventListener('change', refresh);
  fwSel.addEventListener('change', refresh);
  search.addEventListener('input', refresh);
})();
"""


def esc(s) -> str:
    """Escape arbitrary text for HTML body insertion."""
    return html.escape(str(s) if s is not None else "", quote=True)


def severity_rank(sev: str) -> int:
    try:
        return SEV_ORDER.index(sev)
    except ValueError:
        return len(SEV_ORDER)


def load_findings(path: Path) -> list:
    findings: list = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            findings.append(json.loads(line))
    return findings


def collect_framework_options(findings: list) -> list:
    """Return a sorted unique list of `<framework>` tokens for the filter
    dropdown. We filter by framework name (not specific control), e.g.
    `asvs-v5` or `owasp-top-10-2021`."""
    frameworks: set = set()
    for f in findings:
        for ref in f.get("framework_refs", []) or []:
            fw = ref.get("framework")
            if fw:
                frameworks.add(fw)
    return sorted(frameworks)


def render_summary(findings: list) -> str:
    sev_counts = Counter(f.get("severity", "info") for f in findings)
    total = len(findings)
    badges: list = []
    for sev in SEV_ORDER:
        count = sev_counts.get(sev, 0)
        cls = f"badge {sev}{' zero' if count == 0 else ''}"
        badges.append(
            f'<span class="{cls}">{count} {esc(SEV_LABELS[sev])}</span>'
        )
    badge_html = "\n      ".join(badges)
    src_counts = Counter(f.get("source", "unknown") for f in findings)
    src_rows = "".join(
        f"<tr><td><code>{esc(src)}</code></td><td>{n}</td></tr>"
        for src, n in sorted(src_counts.items(), key=lambda kv: -kv[1])
    )
    return f"""
  <section>
    <h2>Summary</h2>
    <p>{total} finding{'s' if total != 1 else ''} total.</p>
    <div class="severity-counts">
      {badge_html}
    </div>
    <table>
      <thead><tr><th>Source</th><th>Findings</th></tr></thead>
      <tbody>{src_rows}</tbody>
    </table>
  </section>
"""


def render_trend(trend: dict) -> str:
    if not trend:
        return """
  <section>
    <h2>Trend vs previous run</h2>
    <p class="trend-empty">First run — no trend data yet.</p>
  </section>
"""
    prev_id = trend.get("previous_run_id")
    if not prev_id:
        return """
  <section>
    <h2>Trend vs previous run</h2>
    <p class="trend-empty">First run — no trend data yet.</p>
  </section>
"""
    s = trend.get("summary", {}) or {}
    items = [
        ("new", "New", s.get("new_count", 0), "high"),
        ("resolved", "Resolved", s.get("resolved_count", 0), "low"),
        ("persistent", "Persistent", s.get("persistent_count", 0), "info"),
    ]
    item_html = "\n      ".join(
        f'<div class="item"><span class="badge {style}">{n}</span> '
        f'<strong>{esc(label)}</strong></div>'
        for _, label, n, style in items
    )
    return f"""
  <section>
    <h2>Trend vs previous run</h2>
    <p class="meta">Compared against run <code>{esc(prev_id)}</code>.</p>
    <div class="trend-counts">
      {item_html}
    </div>
  </section>
"""


def render_phases(manifest: dict) -> str:
    phases = manifest.get("phases", {}) or {}
    if not phases:
        return ""
    rows: list = []
    for phase, data in phases.items():
        per_tool = data.get("per_tool", {}) or {}
        if per_tool:
            for tool, stats in per_tool.items():
                rows.append(
                    f"<tr>"
                    f"<td><code>{esc(phase)}</code></td>"
                    f"<td><code>{esc(tool)}</code></td>"
                    f"<td>{esc(stats.get('status', '?'))}</td>"
                    f"<td>{stats.get('findings', 0)}</td>"
                    f"<td>{stats.get('duration_s', 0)}s</td>"
                    f"</tr>"
                )
        else:
            rows.append(
                f"<tr>"
                f"<td><code>{esc(phase)}</code></td>"
                f"<td>—</td>"
                f"<td>—</td>"
                f"<td>{data.get('findings', 0)}</td>"
                f"<td>{data.get('duration_s', 0)}s</td>"
                f"</tr>"
            )
    return f"""
  <section>
    <h2>Phases &amp; tools</h2>
    <table>
      <thead>
        <tr><th>Phase</th><th>Tool</th><th>Status</th><th>Findings</th><th>Duration</th></tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </section>
"""


def render_finding(f: dict) -> str:
    severity = f.get("severity", "info")
    source = f.get("source", "unknown")
    refs = f.get("framework_refs", []) or []
    framework_names = sorted({r.get("framework", "") for r in refs if r.get("framework")})
    framework_attr = " ".join(framework_names)

    lines = f.get("lines") or {}
    start = lines.get("start")
    end = lines.get("end")
    if start and end and end != start:
        loc = f"L{start}-{end}"
    elif start:
        loc = f"L{start}"
    else:
        loc = ""

    title = f.get("title") or f.get("source_rule_id", "")
    description = (f.get("description") or "").strip()
    evidence = (f.get("evidence") or "").strip()
    remediation = (f.get("remediation_hint") or "").strip()
    cwes = f.get("cwe") or []

    # data-text contains the searchable haystack
    haystack_parts = [
        f.get("file", ""),
        title,
        description,
        evidence,
        f.get("source_rule_id", ""),
    ]
    haystack = " ".join(haystack_parts).lower()

    cwe_html = (
        "<p class=\"cwe\"><strong>CWE:</strong> "
        + " ".join(f"<code>{esc(c)}</code>" for c in cwes)
        + "</p>"
        if cwes else ""
    )
    if refs:
        fw_parts = []
        for r in refs:
            ctrl = r.get("control") or r.get("category") or ""
            fw_parts.append(
                f"<code>{esc(r.get('framework', '?'))} {esc(ctrl)}</code>"
            )
        framework_html = (
            "<p class=\"frameworks\"><strong>Frameworks:</strong> "
            + " ".join(fw_parts) + "</p>"
        )
    else:
        framework_html = ""

    evidence_html = (
        f"<pre class=\"evidence\">{esc(evidence)}</pre>" if evidence else ""
    )
    remediation_html = (
        f"<p class=\"remediation\"><strong>Remediation:</strong> {esc(remediation)}</p>"
        if remediation else ""
    )

    return f"""
  <article class="finding"
    data-severity="{esc(severity)}"
    data-source="{esc(source)}"
    data-frameworks="{esc(framework_attr)}"
    data-text="{esc(haystack)}">
    <div class="finding-header">
      <span class="badge {esc(severity)}">{esc(SEV_LABELS.get(severity, severity))}</span>
      <span class="finding-title">{esc(title)}</span>
      <span class="finding-loc">{esc(loc)}</span>
    </div>
    <div class="finding-body">
      {('<p class="description">' + esc(description) + '</p>') if description else ''}
      {cwe_html}
      {framework_html}
      {evidence_html}
      {remediation_html}
      <p class="meta-line">
        Rule: <code>{esc(f.get('source_rule_id', ''))}</code>
        &middot; ID: <code>{esc((f.get('id') or '')[:12])}…</code>
        &middot; source: <code>{esc(source)}</code>
        &middot; confidence: <code>{esc(f.get('confidence', '?'))}</code>
      </p>
    </div>
  </article>
"""


def render_findings_section(findings: list) -> str:
    if not findings:
        return """
  <section>
    <h2>Findings</h2>
    <p class="trend-empty">No findings. Clean scan.</p>
  </section>
"""
    by_file: dict = defaultdict(list)
    for f in findings:
        by_file[f.get("file", "(unknown)")].append(f)

    def file_rank(items):
        return min(severity_rank(f.get("severity", "info")) for f in items)

    sorted_files = sorted(
        by_file.keys(),
        key=lambda p: (file_rank(by_file[p]), -len(by_file[p]), p),
    )

    blocks: list = []
    for path in sorted_files:
        items = by_file[path]
        items.sort(key=lambda f: (
            severity_rank(f.get("severity", "info")),
            (f.get("lines") or {}).get("start", 0),
        ))
        body = "".join(render_finding(f) for f in items)
        count = len(items)
        plural = "s" if count != 1 else ""
        blocks.append(f"""
  <details class="file-group" open>
    <summary>
      <span class="file-name">{esc(path)}</span>
      <span class="file-count">{count} finding{plural}</span>
    </summary>
    {body}
  </details>""")
    return f"""
  <section>
    <h2>Findings</h2>
    {''.join(blocks)}
  </section>
"""


def render_manifest_footer(manifest: dict) -> str:
    tools = manifest.get("tools", {}) or {}
    rule_packs = manifest.get("rule_packs", {}) or {}
    frameworks = manifest.get("frameworks", {}) or {}

    rows: list = []
    for k, v in tools.items():
        rows.append(f"<tr><td>tool</td><td>{esc(k)}</td><td><code>{esc(v)}</code></td></tr>")
    for k, v in rule_packs.items():
        v_short = v[:12] + "…" if isinstance(v, str) and len(v) > 12 else v
        rows.append(f"<tr><td>rule pack</td><td>{esc(k)}</td><td><code>{esc(v_short)}</code></td></tr>")
    for k, v in frameworks.items():
        rows.append(f"<tr><td>framework</td><td>{esc(k)}</td><td><code>{esc(v)}</code></td></tr>")

    if not rows:
        return ""
    return f"""
  <section>
    <h2>Manifest</h2>
    <table>
      <thead><tr><th></th><th>Name</th><th>Version / SHA</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </section>
"""


def render(findings: list, manifest: dict) -> str:
    framework_options = collect_framework_options(findings)
    source_options = sorted({f.get("source", "") for f in findings if f.get("source")})

    sev_options = "".join(
        f'<option value="{s}">{SEV_LABELS[s]}</option>' for s in SEV_ORDER
    )
    src_options_html = "".join(
        f'<option value="{esc(s)}">{esc(s)}</option>' for s in source_options
    )
    fw_options_html = "".join(
        f'<option value="{esc(fw)}">{esc(fw)}</option>' for fw in framework_options
    )

    run_id = manifest.get("run_id", "")
    repo_root = manifest.get("repo_root", "")
    repo_sha = manifest.get("repo_sha", "no-git")
    started = manifest.get("started_at", "")
    finished = manifest.get("finished_at", "")
    duration = (manifest.get("totals") or {}).get("duration_s", 0)
    schema_version = manifest.get("schema_version", "1.0")

    title = f"securecoder scan — {run_id}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>{CSS}</style>
</head>
<body>
  <header>
    <h1>securecoder scan report</h1>
    <div class="meta meta-row">
      <span>Run <code>{esc(run_id)}</code></span>
      <span>Project <code>{esc(repo_root)}</code></span>
      <span>Commit <code>{esc(repo_sha)}</code></span>
      <span>Started {esc(started)}</span>
      <span>Finished {esc(finished)}</span>
      <span>Duration {esc(str(duration))}s</span>
      <span>Schema v{esc(schema_version)}</span>
    </div>
  </header>

{render_summary(findings)}
{render_trend(manifest.get("trend"))}
{render_phases(manifest)}

  <section class="filters">
    <h2>Filter findings</h2>
    <div class="row">
      <label>Severity:
        <select id="filter-severity">
          <option value="all">All</option>
          {sev_options}
        </select>
      </label>
      <label>Source:
        <select id="filter-source">
          <option value="all">All</option>
          {src_options_html}
        </select>
      </label>
      <label>Framework:
        <select id="filter-framework">
          <option value="all">All</option>
          {fw_options_html}
        </select>
      </label>
      <label>Search:
        <input id="filter-search" type="text" placeholder="file, title, evidence…" />
      </label>
    </div>
    <p class="result-count">Showing <span id="visible-count">{len(findings)}</span> of {len(findings)} finding{'s' if len(findings) != 1 else ''}</p>
  </section>

{render_findings_section(findings)}
{render_manifest_footer(manifest)}

  <footer>
    Generated by <a href="https://github.com/nerdy-krishna/securecoder">securecoder</a>.
    Run directory: <code>.securecoder/runs/{esc(run_id)}/</code>
  </footer>

  <script>{JS}</script>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("findings", help="Path to findings.jsonl")
    ap.add_argument("--manifest", required=True, help="Path to manifest.json")
    ap.add_argument("--output", "-o", help="Write HTML here instead of stdout")
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
