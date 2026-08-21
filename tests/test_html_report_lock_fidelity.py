"""Lock-fidelity tests for the HTML report generator.

The HTML report must derive locked spans from the REAL ``lock()`` machinery —
the same ``_collect_labeled_spans()`` call ``lock()`` itself uses, via
``explain_spans()`` — rather than re-detecting them heuristically.

Two properties are pinned here:

1. **Source of truth**: the locked spans shown in the report are exactly those
   that ``explain_spans()`` (and therefore ``lock()``) identify. A citation
   locked by ``lock()`` must appear inside a ``<mark class="locked">`` element
   in the report.

2. **Completeness**: the count of locked spans in the report's metadata matches
   ``len(explain_spans(original))``.
"""

from __future__ import annotations

import os
import re

os.environ.setdefault("UNTELL_LITE_NO_TORCH", "1")

from untell.html_report import generate_html_report
from untell.scripts.explain import explain_spans
from untell.scripts.preserve import lock

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _result(original: str, final: str | None = None) -> dict:
    """Minimal result dict."""
    return {
        "final": final if final is not None else original,
        "pre":  {"max": 0.80, "tier": "lite"},
        "post": {"max": 0.50, "tier": "lite"},
        "iterations": 1,
        "stopped": "passed",
        "tier": "lite",
        "rewriter": "composite",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_citation_locked_by_lock_appears_in_report() -> None:
    """A citation that lock() protects must appear inside a <mark class="locked"> in the report."""
    doc = "As shown by Smith (2020), the method is effective."
    spans = explain_spans(doc)
    # Confirm lock() does lock something in this text.
    assert spans, "explain_spans returned nothing for a text with a citation"

    html = generate_html_report(doc, _result(doc))

    # At least one locked span must produce a <mark class="locked"> in the output.
    assert '<mark class="locked"' in html, (
        "no <mark class=\"locked\"> in the report, but explain_spans found locked spans"
    )

    # The citation span text must be inside a mark element.
    citation_span = next((r["span"] for r in spans if "citation" in r.get("rules", [])), None)
    if citation_span is not None:
        # The span text is HTML-escaped in the mark; check the escaped form is inside a mark.
        import html as _html
        escaped = _html.escape(citation_span, quote=True)
        marks = re.findall(r'<mark class="locked"[^>]*>(.*?)</mark>', html, re.DOTALL)
        contents = "".join(marks)
        assert escaped in contents, (
            f"citation span {citation_span!r} (escaped: {escaped!r}) not found "
            "inside any <mark class=\"locked\"> element"
        )


def test_locked_span_count_matches_explain_spans() -> None:
    """The 'Locked spans: N' badge must match len(explain_spans(original))."""
    doc = (
        "The results (García, 2020; Jones 2019) show a 47% increase. "
        "The URL is https://example.com/paper and version v1.2.3 was used."
    )
    n_expected = len(explain_spans(doc))
    html = generate_html_report(doc, _result(doc))
    # The metadata badge reads "Locked spans: N"
    m = re.search(r"Locked spans:\s*(\d+)", html)
    assert m is not None, "'Locked spans: N' badge not found in report"
    n_reported = int(m.group(1))
    assert n_reported == n_expected, (
        f"report says {n_reported} locked span(s) but explain_spans found {n_expected}"
    )


def test_locked_span_count_in_panel_label_matches_explain_spans() -> None:
    """The 'N span(s) locked' label in the Original panel header must be accurate."""
    doc = "See Smith (2020) for details; it costs $500 and uses 3.5 MB."
    n_expected = len(explain_spans(doc))
    html = generate_html_report(doc, _result(doc))
    # The panel label reads "N span(s) locked" or "N spans locked"
    m = re.search(r"(\d+)\s+spans?\s+locked", html)
    assert m is not None, "'N span(s) locked' label not found in Original panel"
    n_reported = int(m.group(1))
    assert n_reported == n_expected, (
        f"panel label says {n_reported} locked span(s) but explain_spans found {n_expected}"
    )


def test_number_locked_by_lock_appears_marked() -> None:
    """A numeric fact that lock() protects must appear in a <mark class="locked"> element."""
    doc = "Accuracy reached 94.7% with p<0.05 significance."
    spans = explain_spans(doc)
    number_spans = [r for r in spans if "number" in r.get("rules", [])]
    assert number_spans, "no 'number' spans locked in a text containing 94.7% and p<0.05"

    html = generate_html_report(doc, _result(doc))
    assert '<mark class="locked"' in html, (
        "no locked mark elements for a document with numeric facts"
    )


def test_zero_locked_spans_when_text_has_no_protected_patterns() -> None:
    """Plain prose with no citations, numbers or code produces zero locked spans."""
    doc = "The sky is blue and the grass is green today."
    n_expected = len(explain_spans(doc))
    html = generate_html_report(doc, _result(doc))

    # The metadata badge must say "Locked spans: 0" (or the small count)
    m = re.search(r"Locked spans:\s*(\d+)", html)
    assert m is not None
    assert int(m.group(1)) == n_expected

    # No mark.locked elements should appear when nothing is locked.
    if n_expected == 0:
        assert '<mark class="locked"' not in html


def test_round_trip_spans_match_lock_mapping() -> None:
    """Spans shown in the report == spans that lock() actually froze.

    Cross-checks that explain_spans() and lock() agree on which spans are protected:
    the text of every explain_spans() row must appear in lock()'s mapping values.
    """
    doc = (
        "According to Brown et al. (2020), see Table 3.2 for the 15% figure. "
        "The fix ships in v2.3.1 at https://example.com."
    )
    _masked, mapping = lock(doc)
    locked_values = set(mapping.values())
    explained = explain_spans(doc)

    for row in explained:
        span_text = row["span"]
        assert span_text in locked_values, (
            f"explain_spans() reported {span_text!r} as locked, "
            "but it does not appear in lock()'s mapping values — "
            "the two are out of sync"
        )


def test_changed_text_is_marked_in_final_panel() -> None:
    """Text that changed between original and final appears in <mark class="changed">."""
    original = "The method is quite good and works well."
    final = "The approach is excellent and performs well."
    html = generate_html_report(original, _result(original, final))
    assert '<mark class="changed"' in html, (
        "no <mark class=\"changed\"> elements despite original and final differing"
    )


def test_unchanged_text_produces_no_diff_marks() -> None:
    """When original == final, the final panel must contain no <mark class="changed"> elements."""
    doc = "The method is quite good."
    html = generate_html_report(doc, _result(doc, doc))
    assert '<mark class="changed"' not in html, (
        "spurious <mark class=\"changed\"> elements when original and final are identical"
    )
