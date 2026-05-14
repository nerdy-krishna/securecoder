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

  /* ─── Suppression UI (v1.1.0) ─── */
  .multiselect-checkbox {
    margin-right: 8px;
    transform: scale(1.15);
    cursor: pointer;
  }
  .multiselect-bar {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 10px 16px;
    margin: 12px 0;
    display: none;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    font-size: 13px;
  }
  .multiselect-bar.active { display: flex; }
  .multiselect-bar .count {
    font-weight: 600;
  }
  .suppress-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding-top: 8px;
    margin-top: 8px;
    border-top: 1px dashed var(--border);
  }
  .suppress-btn {
    background: transparent;
    color: var(--fg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 4px 10px;
    cursor: pointer;
    font: inherit;
    font-size: 12px;
  }
  .suppress-btn:hover { border-color: var(--accent); color: var(--accent); }
  .suppress-form {
    margin-top: 10px;
    padding: 10px;
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 4px;
    display: none;
    gap: 8px;
    flex-direction: column;
  }
  .suppress-form.open { display: flex; }
  .suppress-form textarea {
    background: var(--bg-card);
    color: var(--fg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 6px 10px;
    font: inherit;
    min-height: 50px;
    resize: vertical;
  }
  .suppress-form .form-row {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
  }
  .suppress-form input[type="date"] {
    background: var(--bg-card);
    color: var(--fg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 4px 8px;
    font: inherit;
  }
  .suppress-form .submit-btn {
    background: var(--accent);
    color: white;
    border: none;
    border-radius: 4px;
    padding: 5px 12px;
    cursor: pointer;
    font: inherit;
    font-weight: 500;
  }
  .suppress-form .submit-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .staging-banner {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--bg-card);
    border-top: 2px solid var(--accent);
    padding: 12px 24px;
    box-shadow: 0 -2px 10px rgba(0,0,0,0.15);
    display: none;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    z-index: 100;
  }
  .staging-banner.visible { display: flex; }
  .staging-banner .count {
    font-weight: 600;
  }
  .staging-banner button {
    background: transparent;
    color: var(--fg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 6px 12px;
    cursor: pointer;
    font: inherit;
  }
  .staging-banner button.primary {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
  }
  .toast {
    position: fixed;
    top: 24px;
    right: 24px;
    background: var(--good);
    color: white;
    padding: 12px 18px;
    border-radius: 4px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    z-index: 200;
    opacity: 0;
    transition: opacity 0.2s;
    font-size: 13px;
  }
  .toast.show { opacity: 1; }
  .staging-review {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.6);
    z-index: 150;
    display: none;
    align-items: center;
    justify-content: center;
  }
  .staging-review.open { display: flex; }
  .staging-review .modal {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    max-width: 800px;
    width: 92%;
    max-height: 80vh;
    overflow-y: auto;
    padding: 20px;
  }
  .staging-review .entry {
    padding: 10px 0;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    gap: 16px;
  }
  .staging-review .entry:last-child { border: 0; }
  .staging-review .entry-match {
    font-family: SFMono-Regular, Consolas, monospace;
    font-size: 12px;
    color: var(--fg-mute);
  }
  body.has-staging-banner { padding-bottom: 80px; }

  /* ─── View tabs + cluster view (v1.1.0 — slice 11.E) ─── */
  .view-tabs {
    display: flex;
    gap: 4px;
    margin: 16px 0 0 0;
    border-bottom: 2px solid var(--border);
  }
  .view-tabs button {
    background: transparent;
    color: var(--fg-mute);
    border: none;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    padding: 8px 16px;
    cursor: pointer;
    font: inherit;
    font-weight: 500;
  }
  .view-tabs button.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
  }
  .view-section.hidden { display: none; }
  details.cluster-row {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 6px;
    margin: 8px 0;
    overflow: hidden;
  }
  details.cluster-row > summary {
    cursor: pointer;
    padding: 10px 16px;
    list-style: none;
    display: grid;
    grid-template-columns: 2fr 3fr 2fr 2fr auto;
    align-items: center;
    gap: 10px;
  }
  details.cluster-row > summary::-webkit-details-marker { display: none; }
  details.cluster-row > summary::before {
    content: "▸";
    color: var(--fg-mute);
    font-size: 12px;
    margin-right: 4px;
  }
  details.cluster-row[open] > summary::before { content: "▾"; }
  .cluster-rule {
    font-family: SFMono-Regular, Consolas, monospace;
    font-size: 12px;
    font-weight: 600;
  }
  .cluster-path {
    font-family: SFMono-Regular, Consolas, monospace;
    font-size: 12px;
    color: var(--fg-mute);
    overflow-wrap: anywhere;
  }
  .cluster-count {
    font-size: 13px;
  }
  .cluster-severities {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
  .cluster-severities .badge {
    font-size: 10px;
    padding: 2px 6px;
  }
  .suppress-cluster-btn {
    background: var(--accent);
    color: white;
    border: none;
    border-radius: 4px;
    padding: 5px 10px;
    cursor: pointer;
    font: inherit;
    font-size: 12px;
    white-space: nowrap;
  }
  .cluster-body {
    background: var(--bg-elev);
    padding: 10px 16px;
    border-top: 1px solid var(--border);
  }
  .cluster-sample {
    font-family: SFMono-Regular, Consolas, monospace;
    font-size: 12px;
    padding: 3px 0;
  }
  .muted { color: var(--fg-mute); font-size: 12px; }

  /* ─── Slice 11.F polish ─── */
  article.finding.suppressed-finding {
    opacity: 0.55;
    border-left: 3px solid var(--info);
  }
  article.finding.suppressed-finding .badge {
    opacity: 0.6;
  }
  .suppression-banner {
    background: var(--bg-elev);
    border-left: 3px solid var(--info);
    padding: 6px 10px;
    margin: 6px 0;
    border-radius: 4px;
    font-size: 12px;
    color: var(--fg-mute);
  }
  .suppression-banner code { background: transparent; padding: 0; }
  .advisory-banner {
    background: var(--bg-elev);
    border: 1px solid var(--med);
    border-left: 4px solid var(--med);
    padding: 12px 16px;
    border-radius: 4px;
    margin: 12px 0;
    font-size: 13px;
  }
  .advisory-banner .title {
    font-weight: 600;
    margin-right: 8px;
    color: var(--med);
  }
  .stale-banner {
    background: var(--bg-elev);
    border: 1px solid var(--fg-mute);
    border-left: 4px solid var(--fg-mute);
    padding: 10px 16px;
    border-radius: 4px;
    margin: 12px 0;
    font-size: 13px;
  }
  .show-suppressed-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    margin: 8px 0;
    cursor: pointer;
    color: var(--fg-mute);
    user-select: none;
  }
  body.hide-suppressed article.finding.suppressed-finding { display: none; }
  /* Hidden file groups inside hide-suppressed mode also need to collapse */
  body.hide-suppressed details.file-group:not(:has(article.finding:not(.suppressed-finding))) {
    display: none;
  }
  .suppressions-section {
    margin-top: 24px;
  }
  .suppressions-section table {
    width: 100%;
  }
  .suppressions-section td.match-col {
    font-family: SFMono-Regular, Consolas, monospace;
    font-size: 12px;
  }
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

  // ─── Suppression UI (v1.1.0) ──────────────────────────────────────
  var RUN_ID = document.body.getAttribute('data-run-id') || '';
  var STORAGE_KEY = 'securecoder.staging.' + RUN_ID;

  function loadStaged() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); }
    catch (e) { return []; }
  }
  function saveStaged(list) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(list)); }
    catch (e) {}
  }
  function showToast(msg) {
    var t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(function() { t.classList.remove('show'); }, 2200);
  }
  function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        function() { showToast('Command copied to clipboard'); },
        function() { fallbackCopy(text); }
      );
    } else {
      fallbackCopy(text);
    }
  }
  function fallbackCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); showToast('Command copied'); }
    catch (e) { showToast('Copy failed — see Review for the command'); }
    document.body.removeChild(ta);
  }
  function generateCommand(entries) {
    return '/securecoder-suppress import ' + JSON.stringify(entries);
  }

  // Build a suppression entry from a finding card + scope
  function buildEntry(findingEl, scope, reason, expiresAt) {
    var id = findingEl.getAttribute('data-finding-id') || '';
    var rule = findingEl.getAttribute('data-rule') || '';
    var file = findingEl.getAttribute('data-file') || '';
    var match = {};
    if (scope === 'instance' && id) match.id = id;
    else if (scope === 'rule-here' && rule && file) {
      match.rule = rule;
      // Use the file's directory as a glob — single-file matches are usually
      // by id; rule-here implies "this rule in this file's neighborhood"
      var slash = file.lastIndexOf('/');
      match.file_glob = slash > 0 ? file.substring(0, slash) + '/**' : file;
    } else if (scope === 'rule-global' && rule) {
      match.rule = rule;
    }
    var entry = { match: match, scope: 'project', reason: reason };
    if (expiresAt) entry.expires_at = expiresAt;
    return entry;
  }

  var stagedList = loadStaged();
  var banner = document.getElementById('staging-banner');
  var bannerCount = document.getElementById('staging-count');
  var reviewModal = document.getElementById('staging-review');
  var reviewBody = document.getElementById('staging-review-body');

  function updateBanner() {
    var n = stagedList.length;
    if (n > 0) {
      banner.classList.add('visible');
      document.body.classList.add('has-staging-banner');
      bannerCount.textContent = n;
    } else {
      banner.classList.remove('visible');
      document.body.classList.remove('has-staging-banner');
    }
  }
  function stageEntry(entry) {
    stagedList.push(entry);
    saveStaged(stagedList);
    updateBanner();
  }
  function exportToAgent() {
    if (stagedList.length === 0) {
      showToast('Nothing staged');
      return;
    }
    copyToClipboard(generateCommand(stagedList));
  }
  function clearStaging() {
    if (stagedList.length === 0) return;
    if (confirm('Clear all ' + stagedList.length + ' staged suppression(s)?')) {
      stagedList = [];
      saveStaged(stagedList);
      updateBanner();
    }
  }
  function openReview() {
    reviewBody.innerHTML = '';
    if (stagedList.length === 0) {
      reviewBody.innerHTML = '<p>Nothing staged.</p>';
    } else {
      stagedList.forEach(function(e, i) {
        var div = document.createElement('div');
        div.className = 'entry';
        var matchStr = Object.keys(e.match || {}).map(function(k) {
          return k + '=' + JSON.stringify(e.match[k]);
        }).join(' AND ');
        div.innerHTML =
          '<div><div class="entry-match">' + matchStr + '</div>' +
          '<div>' + (e.reason || '(no reason)') + '</div></div>';
        var rm = document.createElement('button');
        rm.textContent = 'Remove';
        rm.onclick = function() {
          stagedList.splice(i, 1);
          saveStaged(stagedList);
          updateBanner();
          openReview();
        };
        div.appendChild(rm);
        reviewBody.appendChild(div);
      });
    }
    reviewModal.classList.add('open');
  }
  function closeReview() {
    reviewModal.classList.remove('open');
  }

  // Wire up per-finding suppress buttons
  findings.forEach(function(findingEl) {
    var actions = findingEl.querySelectorAll('.suppress-btn');
    var form = findingEl.querySelector('.suppress-form');
    if (!form) return;
    var reasonInput = form.querySelector('textarea');
    var expiresInput = form.querySelector('input[type="date"]');
    var addBtn = form.querySelector('.add-to-batch');
    var copyBtn = form.querySelector('.copy-single');
    var currentScope = 'instance';

    actions.forEach(function(btn) {
      btn.addEventListener('click', function() {
        currentScope = btn.getAttribute('data-scope') || 'instance';
        form.classList.add('open');
        reasonInput.focus();
      });
    });
    function buildCurrentEntry() {
      var reason = (reasonInput.value || '').trim();
      if (!reason) {
        showToast('A reason is required');
        reasonInput.focus();
        return null;
      }
      return buildEntry(findingEl, currentScope, reason, expiresInput.value || null);
    }
    addBtn.addEventListener('click', function() {
      var e = buildCurrentEntry();
      if (!e) return;
      stageEntry(e);
      showToast('Staged. ' + stagedList.length + ' staged.');
      reasonInput.value = '';
      form.classList.remove('open');
    });
    copyBtn.addEventListener('click', function() {
      var e = buildCurrentEntry();
      if (!e) return;
      copyToClipboard(generateCommand([e]));
      reasonInput.value = '';
      form.classList.remove('open');
    });
  });

  // Multi-select
  var selectedSet = new Set();
  var multiBar = document.getElementById('multiselect-bar');
  var multiCount = document.getElementById('multiselect-count');
  function updateMultiselectBar() {
    if (selectedSet.size > 0) {
      multiBar.classList.add('active');
      multiCount.textContent = selectedSet.size;
    } else {
      multiBar.classList.remove('active');
    }
  }
  document.querySelectorAll('.multiselect-checkbox').forEach(function(cb) {
    cb.addEventListener('change', function() {
      var id = cb.getAttribute('data-finding-id');
      if (cb.checked) selectedSet.add(id);
      else selectedSet.delete(id);
      updateMultiselectBar();
    });
  });
  document.getElementById('btn-select-all').addEventListener('click', function() {
    findings.forEach(function(f) {
      var cb = f.querySelector('.multiselect-checkbox');
      var id = f.getAttribute('data-finding-id');
      if (cb && id) { cb.checked = true; selectedSet.add(id); }
    });
    updateMultiselectBar();
  });
  document.getElementById('btn-select-filtered').addEventListener('click', function() {
    findings.forEach(function(f) {
      if (f.classList.contains('hidden')) return;
      var cb = f.querySelector('.multiselect-checkbox');
      var id = f.getAttribute('data-finding-id');
      if (cb && id) { cb.checked = true; selectedSet.add(id); }
    });
    updateMultiselectBar();
  });
  document.getElementById('btn-clear-selection').addEventListener('click', function() {
    selectedSet.clear();
    document.querySelectorAll('.multiselect-checkbox').forEach(function(cb) { cb.checked = false; });
    updateMultiselectBar();
  });
  document.getElementById('btn-suppress-selected').addEventListener('click', function() {
    if (selectedSet.size === 0) return;
    var reason = prompt('Reason for suppressing ' + selectedSet.size + ' finding(s)?');
    if (!reason || !reason.trim()) return;
    var entries = [];
    findings.forEach(function(f) {
      var id = f.getAttribute('data-finding-id');
      if (selectedSet.has(id)) {
        entries.push({ match: { id: id }, scope: 'project', reason: reason.trim() });
      }
    });
    entries.forEach(stageEntry);
    showToast('Staged ' + entries.length + ' suppressions.');
    selectedSet.clear();
    document.querySelectorAll('.multiselect-checkbox').forEach(function(cb) { cb.checked = false; });
    updateMultiselectBar();
  });

  // Show-suppressed toggle
  var showSupTog = document.getElementById('toggle-show-suppressed');
  if (showSupTog) {
    showSupTog.addEventListener('change', function() {
      if (showSupTog.checked) {
        document.body.classList.remove('hide-suppressed');
      } else {
        document.body.classList.add('hide-suppressed');
      }
      refresh();
    });
  }

  // View tab switching (flat findings ↔ clusters)
  var flatView = document.getElementById('findings-view');
  var clustersView = document.getElementById('clusters-view');
  var tabFlat = document.getElementById('tab-flat');
  var tabClusters = document.getElementById('tab-clusters');
  if (tabFlat && tabClusters && flatView && clustersView) {
    function setView(viewName) {
      if (viewName === 'flat') {
        flatView.classList.remove('hidden');
        clustersView.classList.add('hidden');
        tabFlat.classList.add('active');
        tabClusters.classList.remove('active');
      } else {
        flatView.classList.add('hidden');
        clustersView.classList.remove('hidden');
        tabFlat.classList.remove('active');
        tabClusters.classList.add('active');
      }
    }
    tabFlat.addEventListener('click', function() { setView('flat'); });
    tabClusters.addEventListener('click', function() { setView('clusters'); });
  }

  // Cluster suppress buttons
  document.querySelectorAll('.suppress-cluster-btn').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      var clusterRow = btn.closest('details.cluster-row');
      if (!clusterRow) return;
      var rule = clusterRow.getAttribute('data-rule') || '';
      var glob = clusterRow.getAttribute('data-glob') || '';
      var reason = prompt(
        'Reason for suppressing all findings in cluster:\n  rule = ' + rule +
        (glob ? '\n  file_glob = ' + glob : '')
      );
      if (!reason || !reason.trim()) return;
      var match = { rule: rule };
      if (glob) match.file_glob = glob;
      stageEntry({ match: match, scope: 'project', reason: reason.trim() });
      showToast('Cluster staged. ' + stagedList.length + ' total.');
    });
  });

  // Banner buttons
  document.getElementById('btn-export-staging').addEventListener('click', exportToAgent);
  document.getElementById('btn-clear-staging').addEventListener('click', clearStaging);
  document.getElementById('btn-review-staging').addEventListener('click', openReview);
  document.getElementById('btn-close-review').addEventListener('click', closeReview);
  reviewModal.addEventListener('click', function(e) {
    if (e.target === reviewModal) closeReview();
  });

  updateBanner();
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


def compute_clusters(findings: list) -> list:
    """Group findings by (rule_id, common path prefix) per design.md §3.9.

    Algorithm:
      1. Group by source_rule_id.
      2. Skip rule groups with < 3 findings (they remain in the flat view).
      3. For each rule group, compute path components of every file, then
         try the longest common prefix. If that prefix covers >80% of the
         group's findings, truncate it one component at a time until
         coverage is in [3 findings, 80% of group]. Falls back to no
         prefix (rule-only cluster) when nothing fits.
      4. Cluster = {rule, file_glob, count, suppressed_count,
         severities_breakdown, samples (3 random), source}.
    """
    if not findings:
        return []

    # Group by rule_id
    by_rule: dict = {}
    for f in findings:
        rule = f.get("source_rule_id", "")
        if not rule:
            continue
        by_rule.setdefault(rule, []).append(f)

    clusters: list = []
    for rule, items in by_rule.items():
        if len(items) < 3:
            continue

        # Compute longest common prefix of file paths (component-wise)
        paths = [(f.get("file", "") or "").split("/") for f in items]
        if not paths:
            continue
        common: list = []
        for components in zip(*paths):
            if len(set(components)) == 1:
                common.append(components[0])
            else:
                break

        # Walk prefix back trying to find the deepest one that satisfies
        # [3 findings ≤ coverage ≤ 0.8 × group size]. If no candidate fits the
        # 80% ceiling (e.g., all findings genuinely share one prefix),
        # fall back to the longest prefix with ≥3 coverage so the cluster
        # still makes sense.
        max_cov = max(3, int(0.8 * len(items)))
        prefix_glob = None
        fallback_glob = None
        while common:
            prefix = "/".join(common)
            cov = sum(
                1 for f in items
                if (f.get("file", "") or "").startswith(prefix + "/")
                or (f.get("file", "") or "") == prefix
            )
            if cov >= 3 and fallback_glob is None:
                fallback_glob = prefix + "/**"
            if 3 <= cov <= max_cov:
                prefix_glob = prefix + "/**"
                break
            common.pop()  # try a shorter prefix

        if prefix_glob is None:
            prefix_glob = fallback_glob  # may be None (rule-only cluster)

        sev_counts: dict = {}
        suppressed_count = 0
        sources: set = set()
        for f in items:
            sev = f.get("severity", "info")
            sev_counts[sev] = sev_counts.get(sev, 0) + 1
            if f.get("status") == "suppressed":
                suppressed_count += 1
            sources.add(f.get("source", "?"))

        # Sample up to 3 deterministically (sorted by file:line for stability)
        sorted_items = sorted(
            items,
            key=lambda x: (
                (x.get("file") or ""),
                (x.get("lines") or {}).get("start", 0)
            ),
        )
        samples = sorted_items[:3]

        clusters.append({
            "rule": rule,
            "file_glob": prefix_glob,  # may be None
            "count": len(items),
            "suppressed_count": suppressed_count,
            "active_count": len(items) - suppressed_count,
            "severities": sev_counts,
            "sources": sorted(sources),
            "samples": samples,
        })

    # Order clusters by most-severe-first then by count desc
    def cluster_sort_key(c):
        worst_sev = min(severity_rank(s) for s in c["severities"]) if c["severities"] else 99
        return (worst_sev, -c["count"])

    clusters.sort(key=cluster_sort_key)
    return clusters


def render_clusters_section(clusters: list, total_findings: int) -> str:
    if not clusters:
        return """
  <section id="clusters-view" class="view-section hidden">
    <h2>Clusters</h2>
    <p class="trend-empty">No clusters detected — every rule fires fewer than 3 times. Use the flat Findings view instead.</p>
  </section>
"""

    rows: list = []
    for i, c in enumerate(clusters):
        glob = c["file_glob"] or "(any file)"
        sev_breakdown = " ".join(
            f'<span class="badge {sev}">{n} {SEV_LABELS.get(sev, sev)}</span>'
            for sev in SEV_ORDER if c["severities"].get(sev, 0) > 0
            for n in [c["severities"][sev]]
        )
        suppressed_note = (
            f' <span class="muted">({c["suppressed_count"]} suppressed)</span>'
            if c["suppressed_count"] else ""
        )
        sample_html = "".join(
            f'<div class="cluster-sample">'
            f'<code>{esc(s.get("file", ""))}</code>: '
            f'L{(s.get("lines") or {}).get("start", "?")}'
            f' &mdash; {esc(s.get("title", ""))}'
            f'</div>'
            for s in c["samples"]
        )
        rule_esc = esc(c["rule"])
        glob_esc = esc(c["file_glob"] or "")
        rows.append(f"""
  <details class="cluster-row" data-rule="{rule_esc}" data-glob="{glob_esc}">
    <summary>
      <span class="cluster-rule">{rule_esc}</span>
      <span class="cluster-path">{esc(glob)}</span>
      <span class="cluster-count">{c["active_count"]} active{suppressed_note}</span>
      <span class="cluster-severities">{sev_breakdown}</span>
      <button class="suppress-cluster-btn" data-cluster-index="{i}" title="Stage a pattern-based suppression for this entire cluster">Suppress entire cluster</button>
    </summary>
    <div class="cluster-body">
      <p class="meta-line">Sources: {esc(", ".join(c["sources"]))}</p>
      <div class="cluster-samples">
        <strong>Sample findings (3 of {c["count"]}):</strong>
        {sample_html}
      </div>
    </div>
  </details>""")

    total_clustered = sum(c["count"] for c in clusters)
    return f"""
  <section id="clusters-view" class="view-section hidden">
    <h2>Clusters</h2>
    <p class="meta">{len(clusters)} cluster(s) covering {total_clustered} of {total_findings} findings. Findings outside clusters appear in the flat Findings view.</p>
    {''.join(rows)}
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

    fid = f.get("id") or ""
    rule_id = f.get("source_rule_id", "")
    file_path = f.get("file", "")
    status = f.get("status", "open")
    suppression_reason = f.get("suppression_reason", "")
    suppression_match = f.get("suppression_match", "")

    suppressed_cls = " suppressed-finding" if status == "suppressed" else ""
    suppression_banner = ""
    if status == "suppressed":
        suppression_banner = (
            f'<div class="suppression-banner">'
            f'<strong>Suppressed</strong> &middot; '
            f'reason: {esc(suppression_reason or "(no reason)")} '
            f'&middot; match: <code>{esc(suppression_match)}</code>'
            f'</div>'
        )

    return f"""
  <article class="finding{suppressed_cls}"
    data-severity="{esc(severity)}"
    data-source="{esc(source)}"
    data-frameworks="{esc(framework_attr)}"
    data-text="{esc(haystack)}"
    data-finding-id="{esc(fid)}"
    data-rule="{esc(rule_id)}"
    data-file="{esc(file_path)}"
    data-status="{esc(status)}">
    {suppression_banner}
    <div class="finding-header">
      <input type="checkbox" class="multiselect-checkbox" data-finding-id="{esc(fid)}" title="Select for batch suppress" />
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
        Rule: <code>{esc(rule_id)}</code>
        &middot; ID: <code>{esc(fid[:12])}…</code>
        &middot; source: <code>{esc(source)}</code>
        &middot; confidence: <code>{esc(f.get('confidence', '?'))}</code>
      </p>
      <div class="suppress-actions">
        <button class="suppress-btn" data-scope="instance" title="Suppress just this canonical-ID match">Suppress this instance</button>
        <button class="suppress-btn" data-scope="rule-here" title="Suppress {esc(rule_id)} in this file's directory">Suppress rule here</button>
        <button class="suppress-btn" data-scope="rule-global" title="Suppress {esc(rule_id)} project-wide">Suppress rule project-wide</button>
      </div>
      <div class="suppress-form" role="region" aria-label="Suppression form">
        <textarea placeholder="Why is this a false positive? Required." rows="2"></textarea>
        <div class="form-row">
          <label>Expires (optional): <input type="date" /></label>
          <button class="submit-btn add-to-batch">Add to batch</button>
          <button class="submit-btn copy-single">Copy single command</button>
        </div>
      </div>
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


def render_advisory_banner(findings: list) -> str:
    """When one severity dominates (>1000 findings of a single severity), nudge
    the user toward severity-floor adjustments or the cluster view."""
    sev_counts = Counter(f.get("severity", "info") for f in findings)
    for sev in SEV_ORDER:
        if sev_counts.get(sev, 0) > 1000:
            return (
                f'<div class="advisory-banner">'
                f'<span class="title">Heads up.</span> {sev_counts[sev]} '
                f'<strong>{SEV_LABELS.get(sev, sev)}</strong> findings dominate this report. Options:<br>'
                f'&middot; Raise <code>severity_floor</code> to <code>{sev}</code>+ in '
                f'<code>.securecoder/config.json</code><br>'
                f'&middot; Switch to <strong>Clusters</strong> view above to triage by pattern<br>'
                f'&middot; Ask <code>/securecoder-advise</code> whether {sev} findings are actionable for your team'
                f'</div>'
            )
    return ""


def render_stale_banner(manifest: dict, suppressions_entries: list) -> str:
    """Surface entries from suppressions.json that didn't match anything this
    run — likely stale and ready for cleanup."""
    by_entry = manifest.get("suppressed_by_entry", {}) or {}
    if not suppressions_entries or not by_entry:
        return ""
    stale: list = []
    for i, entry in enumerate(suppressions_entries):
        if int(by_entry.get(str(i), 0)) == 0 and not entry.get("expires_at"):
            stale.append((i, entry))
    # Note: expired entries are excluded from "stale" — they're listed separately
    # via /securecoder-suppress show expired
    if not stale:
        return ""
    items_html = "".join(
        f'<li><code>#{i}</code> {esc(", ".join(f"{k}={v}" for k, v in (e.get("match") or {}).items()))} — '
        f'<em>{esc(e.get("reason", "(no reason)"))}</em></li>'
        for i, e in stale[:5]
    )
    extra_count = max(0, len(stale) - 5)
    extra = f"<li>… and {extra_count} more</li>" if extra_count > 0 else ""
    return (
        f'<div class="stale-banner">'
        f'<strong>{len(stale)} suppression entries</strong> didn\'t match any finding this run — they may be stale.<br>'
        f'<ul style="margin: 6px 0 0 16px; padding: 0">{items_html}{extra}</ul>'
        f'Review with <code>/securecoder-suppress show stale</code>.'
        f'</div>'
    )


def render_suppressions_section(suppressions_entries: list, manifest: dict) -> str:
    """Bottom-of-report Suppressions table — every active entry with match,
    reason, audit metadata, and the count of findings it caught this run."""
    if not suppressions_entries:
        return ""
    by_entry = manifest.get("suppressed_by_entry", {}) or {}
    rows: list = []
    for i, entry in enumerate(suppressions_entries):
        match = entry.get("match") or {}
        match_str = ", ".join(f"{k}={v!r}" for k, v in match.items())
        caught = by_entry.get(str(i), 0)
        rows.append(
            f"<tr>"
            f"<td>#{i}</td>"
            f"<td class=\"match-col\">{esc(match_str)}</td>"
            f"<td>{esc(entry.get('reason', ''))}</td>"
            f"<td>{esc(entry.get('created_at', '?'))}<br><span class=\"muted\">by {esc(entry.get('created_by', '?'))}</span></td>"
            f"<td>{esc(entry.get('expires_at') or '(none)')}</td>"
            f"<td>{caught}</td>"
            f"</tr>"
        )
    return f"""
  <section class="suppressions-section">
    <h2>Suppressions ({len(suppressions_entries)} active)</h2>
    <table>
      <thead><tr><th>#</th><th>Match</th><th>Reason</th><th>Created</th><th>Expires</th><th>Caught this run</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </section>
"""


def render(findings: list, manifest: dict, suppressions_entries: list | None = None) -> str:
    suppressions_entries = suppressions_entries or []
    framework_options = collect_framework_options(findings)
    source_options = sorted({f.get("source", "") for f in findings if f.get("source")})
    clusters = compute_clusters(findings)
    cluster_count = len(clusters)
    has_any_suppressed = any(f.get("status") == "suppressed" for f in findings)

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
<body data-run-id="{esc(run_id)}" class="{'hide-suppressed' if has_any_suppressed else ''}">
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
{render_advisory_banner(findings)}
{render_stale_banner(manifest, suppressions_entries)}
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
    {f'<label class="show-suppressed-toggle"><input type="checkbox" id="toggle-show-suppressed" />Show suppressed findings ({sum(1 for fnd in findings if fnd.get("status") == "suppressed")} hidden)</label>' if has_any_suppressed else ''}
  </section>

  <div id="multiselect-bar" class="multiselect-bar">
    <span><span id="multiselect-count" class="count">0</span> finding(s) selected</span>
    <button id="btn-select-all" title="Select every finding in this report">Select all</button>
    <button id="btn-select-filtered" title="Select only currently-visible findings (filter-aware)">Select all matching filter</button>
    <button id="btn-suppress-selected" title="Stage suppression entries for the selected findings">Suppress N selected</button>
    <button id="btn-clear-selection">Clear selection</button>
  </div>

  <div class="view-tabs">
    <button id="tab-flat" class="active">Findings ({len(findings)})</button>
    <button id="tab-clusters">Clusters ({cluster_count})</button>
  </div>

  <section id="findings-view" class="view-section">
{render_findings_section(findings)}
  </section>

{render_clusters_section(clusters, len(findings))}

{render_suppressions_section(suppressions_entries, manifest)}
{render_manifest_footer(manifest)}

  <div id="toast" class="toast" role="status" aria-live="polite"></div>

  <div id="staging-banner" class="staging-banner" role="region" aria-label="Suppression staging tray">
    <span><span id="staging-count" class="count">0</span> suppression(s) staged for this run</span>
    <div>
      <button id="btn-review-staging">Review</button>
      <button id="btn-clear-staging">Clear</button>
      <button id="btn-export-staging" class="primary">Export to agent</button>
    </div>
  </div>

  <div id="staging-review" class="staging-review" role="dialog" aria-modal="true" aria-label="Staged suppressions">
    <div class="modal">
      <h2 style="margin-top: 0">Staged suppressions</h2>
      <div id="staging-review-body"></div>
      <div style="margin-top: 16px; text-align: right">
        <button id="btn-close-review">Close</button>
      </div>
    </div>
  </div>

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
    ap.add_argument("--suppressions",
                    help="Optional path to .securecoder/suppressions.json. "
                         "Populates the Suppressions section at the bottom of "
                         "the report and the stale-suppression banner near the top.")
    ap.add_argument("--output", "-o", help="Write HTML here instead of stdout")
    args = ap.parse_args()

    findings = load_findings(Path(args.findings))
    with open(args.manifest, encoding="utf-8") as f:
        manifest = json.load(f)

    suppressions_entries: list = []
    if args.suppressions:
        try:
            sup_blob = json.loads(Path(args.suppressions).read_text(encoding="utf-8"))
            suppressions_entries = sup_blob.get("entries", []) or []
        except (OSError, json.JSONDecodeError):
            pass

    rendered = render(findings, manifest, suppressions_entries)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)


if __name__ == "__main__":
    main()
