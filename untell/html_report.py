"""HTML report for the untell humanize result.

Produces a self-contained single-file HTML report (no external CSS/JS/fonts — everything
is inlined) showing:

  - The ORIGINAL text with locked spans visually marked (amber background). Locked spans
    are derived from ``explain_spans()``, which calls the same ``_collect_labeled_spans()``
    that ``lock()`` itself uses, so the displayed spans are EXACTLY the ones the rewriter
    was forbidden to touch — not a re-detection, not a heuristic.

  - The FINAL (humanized) text with changed/inserted regions marked (green background),
    computed by a character-level ``SequenceMatcher`` diff of original vs final.

  - A per-sentence score table (``score_sentences(final, tier="lite")``).

Security — the LOAD-BEARING CONTRACT
--------------------------------------
Every user-supplied string that goes into the HTML is passed through
``html.escape(text, quote=True)`` before insertion. No user text reaches any
attribute context (``href``, ``src``, event handler) where a ``javascript:`` URL or other
injection could activate. The XSS test in ``tests/test_html_report_xss.py`` asserts that
the following payloads do NOT appear verbatim in the output:

    <script>alert(1)</script>    →  &lt;script&gt;alert(1)&lt;/script&gt;
    "                            →  &quot;  (in attribute contexts)
    '                            →  safe in double-quoted attributes; &amp;#x27; elsewhere
    &                            →  &amp;
    javascript:alert(1)          →  escaped text only — never in a URL attribute

Usage::

    from untell.html_report import generate_html_report

    html_text = generate_html_report(original, result, path="report.html")
    # or: html_bytes = generate_html_report(original, result)
"""

from __future__ import annotations

import difflib
import html as _html
from pathlib import Path

# ---------------------------------------------------------------------------
# Security: escaping (DO NOT call any HTML-writing function without this)
# ---------------------------------------------------------------------------

def _e(text: str) -> str:
    """HTML-escape text; ``quote=True`` also escapes \" for safe attribute embedding.

    Every user-supplied string that enters the HTML document must pass through
    this function. No exceptions.
    """
    return _html.escape(str(text), quote=True)


# ---------------------------------------------------------------------------
# Annotation: original text with locked spans
# ---------------------------------------------------------------------------

def _annotate_locked(text: str, locked_spans: list[dict]) -> str:
    """Return HTML where each locked span is wrapped in <mark class="locked">.

    All text fragments — inside and outside the spans — are HTML-escaped via
    ``_e()``. The ``title`` attribute carries the rule names (also escaped), so a
    hover tooltip explains which rule locked each span. Only the rule names go into
    the attribute; the span TEXT goes into element content — the two escape contexts
    are kept separate and both are sanitised.

    Parameters
    ----------
    text:
        The original user-supplied text (NOT yet escaped).
    locked_spans:
        The list returned by ``explain_spans(text)``. Each entry must have
        ``start``, ``end``, and ``rules`` keys.
    """
    if not locked_spans:
        return _e(text)

    # explain_spans() already returns spans in sentinel/character order; sort
    # defensively in case the caller assembled the list differently.
    spans = sorted(locked_spans, key=lambda r: r["start"])
    parts: list[str] = []
    prev = 0
    for row in spans:
        start, end = row["start"], row["end"]
        if start < prev:
            # Overlapping spans: shouldn't happen after _merge_labeled, but be safe.
            continue
        if start > prev:
            parts.append(_e(text[prev:start]))
        rules = _e(", ".join(row.get("rules", [])))
        span_text = _e(text[start:end])
        parts.append(
            f'<mark class="locked" title="{rules}">{span_text}</mark>'
        )
        prev = end
    if prev < len(text):
        parts.append(_e(text[prev:]))
    return "".join(parts)


# ---------------------------------------------------------------------------
# Annotation: final text with changed regions
# ---------------------------------------------------------------------------

def _annotate_diff_final(original: str, final: str) -> str:
    """Return HTML of ``final`` where changed/inserted characters are highlighted.

    Uses a character-level ``SequenceMatcher`` diff (``autojunk=False``). Regions
    that are equal to the original are plain escaped text; replaced/inserted regions
    are wrapped in ``<mark class="changed">``. Deleted regions have no representation
    in the final text and simply vanish.

    All characters from ``final`` are HTML-escaped before insertion. No user text
    reaches any URL or event-handler attribute.
    """
    sm = difflib.SequenceMatcher(None, original, final, autojunk=False)
    parts: list[str] = []
    for tag, _i1, _i2, j1, j2 in sm.get_opcodes():
        chunk = final[j1:j2]
        if not chunk:
            continue
        if tag == "equal":
            parts.append(_e(chunk))
        else:  # replace or insert — new content in the final
            parts.append(f'<mark class="changed">{_e(chunk)}</mark>')
    return "".join(parts)


# ---------------------------------------------------------------------------
# Per-sentence score bar
# ---------------------------------------------------------------------------

def _score_bar(score: float) -> str:
    """Inline HTML/CSS score bar; no images or external resources.

    The bar is a coloured gradient from green (low AI, left) to red (high AI,
    right). A semi-transparent overlay from the right covers the portion of the
    bar that is *above* the score, so only the relevant left segment is visible.
    """
    pct = max(0.0, min(1.0, float(score))) * 100
    fill = round(100.0 - pct, 1)
    return (
        f'<span class="score-bar" aria-hidden="true">'
        f'<span class="score-fill" style="width:{fill}%;left:{pct}%"></span>'
        f'</span>'
    )


# ---------------------------------------------------------------------------
# Sentence score table
# ---------------------------------------------------------------------------

def _sentence_table(sentences: list[dict], threshold: float) -> str:
    """Return an HTML <table> of per-sentence AI scores.

    Every sentence text is HTML-escaped. Flagged rows (score >= threshold) are
    given a visual marker and a distinct background colour.
    """
    rows: list[str] = []
    for row in sentences:
        score = row.get("ai", 0.0)
        flagged = row.get("flagged", False)
        cls = ' class="flagged-row"' if flagged else ""
        badge = (
            ' <abbr title="above threshold" style="color:#c0392b;font-weight:bold">▲</abbr>'
            if flagged else ""
        )
        rows.append(
            f"<tr{cls}>"
            f"<td>{_score_bar(score)}<span class='score-num'>{score:.3f}</span>{badge}</td>"
            f"<td>{_e(row.get('text', ''))}</td>"
            f"</tr>"
        )
    return (
        "<table>"
        "<thead><tr><th>AI Score</th><th>Sentence</th></tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


# ---------------------------------------------------------------------------
# Inline CSS (no external fonts, no CDN — all styles are in this string)
# ---------------------------------------------------------------------------

_CSS = """
*, *::before, *::after { box-sizing: border-box; }
:root {
  --locked-bg: #f5c518; --locked-fg: #1a1400;
  --changed-bg: #28a745; --changed-fg: #fff;
  --panel-bg: #f8f9fa; --border: #dee2e6;
  --text: #212529; --muted: #6c757d;
  --flag-bg: #fff3cd; --flag-border: #ffc107;
  --body-bg: #fff;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --locked-bg: #a07600; --locked-fg: #fff;
    --changed-bg: #155724; --changed-fg: #c3e6cb;
    --panel-bg: #1e1e2e; --border: #444;
    --text: #cdd6f4; --muted: #a6adc8;
    --flag-bg: #2d2500; --flag-border: #7a6000;
    --body-bg: #1a1b26;
  }
}
:root[data-theme="dark"] {
  --locked-bg: #a07600; --locked-fg: #fff;
  --changed-bg: #155724; --changed-fg: #c3e6cb;
  --panel-bg: #1e1e2e; --border: #444;
  --text: #cdd6f4; --muted: #a6adc8;
  --flag-bg: #2d2500; --flag-border: #7a6000;
  --body-bg: #1a1b26;
}
body {
  font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
  line-height: 1.65; max-width: 1100px; margin: 0 auto;
  padding: 1rem 1.5rem;
  background: var(--body-bg); color: var(--text);
}
h1 { font-size: 1.5rem; margin: 0.5rem 0 0.25rem; }
h2 {
  font-size: 1.05rem; margin: 1.75rem 0 0.6rem;
  border-bottom: 1px solid var(--border); padding-bottom: 0.3rem;
}
.meta { display: flex; gap: 0.5rem; flex-wrap: wrap; margin: 0.75rem 0 1.25rem; }
.badge {
  display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px;
  font-size: 0.82rem; background: var(--panel-bg);
  border: 1px solid var(--border); font-variant-numeric: tabular-nums;
}
.legend { display: flex; gap: 1.25rem; flex-wrap: wrap; font-size: 0.85rem; margin: 0.5rem 0 1rem; }
.legend-item { display: flex; align-items: center; gap: 0.35rem; }
.swatch {
  display: inline-block; width: 14px; height: 14px;
  border-radius: 2px; flex-shrink: 0;
}
.swatch.locked  { background: var(--locked-bg); }
.swatch.changed { background: var(--changed-bg); }
.panels {
  display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin: 0.5rem 0 1rem;
}
@media (max-width: 680px) { .panels { grid-template-columns: 1fr; } }
.panel-label {
  font-weight: 600; font-size: 0.78rem; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.06em;
  margin-bottom: 0.4rem;
}
.panel {
  background: var(--panel-bg); border: 1px solid var(--border);
  border-radius: 6px; padding: 1rem;
  white-space: pre-wrap; word-break: break-word;
  font-size: 0.92rem; min-height: 3.5rem;
  overflow-x: auto;
}
mark.locked {
  background: var(--locked-bg); color: var(--locked-fg);
  border-radius: 3px; padding: 1px 2px;
  cursor: help; text-decoration: underline dotted 1px;
  font-style: normal;
}
mark.changed {
  background: var(--changed-bg); color: var(--changed-fg);
  border-radius: 3px; padding: 1px 2px;
  font-style: normal;
}
table {
  border-collapse: collapse; width: 100%;
  margin: 0.5rem 0; font-size: 0.88rem; table-layout: fixed;
  overflow-x: auto; display: block;
}
thead { position: sticky; top: 0; }
th, td { border: 1px solid var(--border); padding: 0.35rem 0.65rem; vertical-align: top; }
th { background: var(--panel-bg); font-weight: 600; }
th:first-child, td:first-child { width: 170px; white-space: nowrap; }
td:first-child { vertical-align: middle; }
tr.flagged-row td { background: var(--flag-bg); }
.score-bar {
  display: inline-block; width: 80px; height: 9px;
  border-radius: 4px; vertical-align: middle;
  background: linear-gradient(90deg, #28a745 0%, #ffc107 50%, #dc3545 100%);
  margin-right: 0.35rem; position: relative; overflow: hidden;
}
.score-fill {
  display: block; position: absolute; top: 0; height: 100%;
  background: var(--panel-bg); opacity: 0.72;
  border-radius: 0 4px 4px 0;
}
.score-num { font-variant-numeric: tabular-nums; }
.warn-box {
  border-left: 4px solid #e74c3c; padding: 0.5rem 1rem;
  margin: 0.75rem 0; background: var(--flag-bg); border-radius: 0 4px 4px 0;
}
footer {
  margin-top: 2rem; padding-top: 0.5rem;
  border-top: 1px solid var(--border);
  font-size: 0.8rem; color: var(--muted);
}
"""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_html_report(
    original: str,
    result: dict,
    *,
    path: str | None = None,
) -> str:
    """Generate a self-contained HTML report of an ``untell_text`` result.

    Parameters
    ----------
    original:
        The original user-supplied text, BEFORE humanization.
    result:
        The dict returned by ``untell_text()``. The ``final`` key provides the
        humanized text; falls back to ``original`` on an error result.
    path:
        If given, write the HTML document to this path (UTF-8). Parent
        directories are created automatically. The same string is also returned,
        so the caller can inspect the size or content.

    Returns
    -------
    str
        The complete, self-contained HTML document.

    Security
    --------
    Every user-supplied string — ``original``, ``result["final"]``, span texts,
    sentence texts, warning messages — is passed through ``_e()`` (which calls
    ``html.escape(text, quote=True)``) before insertion. No user text reaches a
    URL attribute, event handler, or any other injection-prone context.
    """
    final = result.get("final") or original
    pre = result.get("pre") or {}
    post = result.get("post") or {}
    iterations = result.get("iterations", 0)
    stopped = (result.get("stopped") or "").replace("_", " ")
    tier = result.get("tier") or pre.get("tier") or "?"
    rewriter_name = result.get("rewriter") or "?"

    # --- Locked spans (exact same spans lock() protects: from explain_spans) ---
    try:
        from untell.scripts.explain import explain_spans
        locked_spans = explain_spans(original)
    except Exception:  # always degrade gracefully rather than crashing the report
        locked_spans = []

    # --- Per-sentence scores (lite tier: fast, stdlib-only on the common path) ---
    try:
        from untell.scripts.sentences import score_sentences
        sent = score_sentences(final, tier="lite")
        sentences = sent.get("sentences") or []
        threshold = float(sent.get("threshold") or 0.30)
    except Exception:
        sentences = []
        threshold = 0.30

    # --- Annotate original with locked spans (all text is HTML-escaped inside) ---
    original_html = _annotate_locked(original, locked_spans)

    # --- Annotate final with changed character regions (all text is HTML-escaped) ---
    final_html = _annotate_diff_final(original, final)

    # --- Metadata badges (values from result dict, escaped) ---
    pre_max = pre.get("max")
    post_max = post.get("max")

    def _fmt_max(v, label: str) -> str:
        return f"{label}: {v:.3f}" if isinstance(v, (int, float)) else f"{label}: ?"

    badges = [
        _fmt_max(pre_max, "Pre P(AI)"),
        _fmt_max(post_max, "Post P(AI)"),
        f"Iterations: {iterations}",
        f"Tier: {_e(tier)}",
        f"Rewriter: {_e(rewriter_name)}",
        f"Stopped: {_e(stopped)}",
        f"Locked spans: {len(locked_spans)}",
    ]
    badges_html = "".join(f'<span class="badge">{b}</span>' for b in badges)

    # --- Warning/error box (if any) ---
    warning = result.get("warning") or result.get("error")
    warn_html = ""
    if warning:
        warn_html = (
            f'<div class="warn-box"><strong>Note:</strong> {_e(str(warning))}</div>'
        )

    # --- Sentence table and summary ---
    flagged_count = sum(1 for r in sentences if r.get("flagged"))
    n_sents = len(sentences)
    table_html = (
        _sentence_table(sentences, threshold)
        if sentences
        else "<p><em>No sentence scores available (lite scoring requires at least one sentence).</em></p>"
    )

    # --- Lock count display string ---
    n_locked = len(locked_spans)
    lock_label = f"{n_locked} span{'s' if n_locked != 1 else ''} locked"

    # --- Assemble the complete HTML document ---
    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>untell humanize report</title>
<style>{_CSS}</style>
</head>
<body>
<h1>untell humanize report</h1>
<div class="meta">{badges_html}</div>
{warn_html}
<div class="legend">
  <span class="legend-item">
    <span class="swatch locked"></span>
    Locked span (preserved verbatim — hover for rule)
  </span>
  <span class="legend-item">
    <span class="swatch changed"></span>
    Changed text (inserted or replaced)
  </span>
</div>
<div class="panels">
  <div>
    <div class="panel-label">Original — {_e(lock_label)}</div>
    <div class="panel">{original_html}</div>
  </div>
  <div>
    <div class="panel-label">Humanized</div>
    <div class="panel">{final_html}</div>
  </div>
</div>
<h2>Per-sentence scores — {_e(str(flagged_count))} of {_e(str(n_sents))} flagged</h2>
{table_html}
<footer>
  Generated by <strong>untell</strong> &mdash; self-contained HTML, no external resources.
</footer>
</body>
</html>"""

    if path is not None:
        p = Path(path)
        if str(p.parent) not in (".", ""):
            p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(doc, encoding="utf-8")

    return doc
