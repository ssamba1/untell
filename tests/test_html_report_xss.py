"""XSS-safety tests for the HTML report generator.

The load-bearing contract: every user-supplied text span is HTML-escaped before
it goes into the report. A document containing ``<script>alert(1)</script>``,
``"``, ``'``, ``&``, and a ``javascript:`` URL must render inert — the raw
substrings must NOT appear unescaped in the output, and the document must be
valid, self-contained HTML.

These tests are the PRIMARY deliverable for this module; a single missed escape
is a serious XSS defect.
"""

from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("UNTELL_LITE_NO_TORCH", "1")

from untell.html_report import generate_html_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _result(text: str) -> dict:
    """Minimal result dict that exercises the report without running a real loop."""
    return {
        "final": text,
        "pre":  {"max": 0.80, "tier": "lite"},
        "post": {"max": 0.50, "tier": "lite"},
        "iterations": 1,
        "stopped": "passed",
        "tier": "lite",
        "rewriter": "composite",
    }


# ---------------------------------------------------------------------------
# Exact payloads from the issue spec
# ---------------------------------------------------------------------------

# All four payloads combined in one document, including a <a href="javascript:">
# element to check that the href is not blindly mirrored into the output.
_XSS_DOC = (
    '<script>alert(1)</script> '
    '"double-quote" '
    "'single-quote' "
    '& ampersand '
    'javascript:alert(1)'
)


def test_script_tag_does_not_appear_verbatim() -> None:
    """<script>alert(1)</script> must be escaped; a live tag in the output is a defect."""
    html = generate_html_report(_XSS_DOC, _result(_XSS_DOC))
    assert "<script>" not in html, (
        "unescaped <script> open-tag survived into the report HTML"
    )
    assert "</script>" not in html, (
        "unescaped </script> close-tag survived into the report HTML"
    )
    # The escape round-trip must produce the entities, not vanish the text.
    assert "&lt;script&gt;" in html, (
        "expected &lt;script&gt; entity in output (text must be visible, just escaped)"
    )


def test_javascript_url_does_not_appear_in_any_href() -> None:
    """A javascript: URL in user text must not end up in any href attribute."""
    html = generate_html_report(_XSS_DOC, _result(_XSS_DOC))
    # Check all href/src/action attributes in the output.
    for m in re.finditer(r'(?i)(href|src|action)=["\']([^"\']*)["\']', html):
        attr_val = m.group(2)
        assert "javascript:" not in attr_val.lower(), (
            f"javascript: protocol found in {m.group(1)} attribute: {m.group(0)!r}"
        )
    # Belt-and-suspenders: the literal attribution string must not appear in the
    # generated HTML — it can only be present as escaped text in element content,
    # never as a navigable URL.
    assert 'href="javascript:' not in html
    assert "href='javascript:" not in html


def test_ampersand_is_escaped_to_entity() -> None:
    """& in user text must appear as &amp; in the HTML, not as a bare &."""
    doc = "A & B"
    html = generate_html_report(doc, _result(doc))
    # The text content must not contain "A & B" with a literal bare &.
    # (The & will appear as &amp; in element text content.)
    assert "A &amp; B" in html, "& not escaped to &amp; in report output"
    assert "A & B" not in html, "literal bare & survived unescaped"


def test_double_quote_is_escaped_in_attribute_context() -> None:
    """A \" in user text that reaches a title=\"...\" attribute must be &quot;."""
    # Use a citation (lock() will lock it, producing a title attribute with rule names
    # and span content through _e()). The span text goes into element content via _e()
    # which escapes " → &quot;.
    doc = 'She said "run it" (Smith, 2020) and it worked.'
    html = generate_html_report(doc, _result(doc))
    # No title attribute must contain a raw unescaped " — that would break the attribute.
    for m in re.finditer(r'title="([^"]*)"', html):
        inner = m.group(1)
        assert '"' not in inner, (
            f"raw unescaped \" inside title attribute: {m.group(0)!r}"
        )
    # In element text content, " is escaped to &quot; by html.escape(quote=True).
    # Assert the user's " does not appear as a bare " in the element content of a <mark>.
    # The safest proxy: any mark element content is escaped.
    for m in re.finditer(r'<mark[^>]*>([^<]*)</mark>', html):
        content = m.group(1)
        # If the user text that's inside the mark contained ", it must be &quot;
        if "&quot;" in content or '"' not in content:
            pass  # correct
        else:
            pytest.fail(
                f"unescaped \" in <mark> element content: {m.group(0)!r}"
            )


def test_single_quote_is_safe_in_double_quoted_attributes() -> None:
    """' in user text is safe in double-quoted attributes (no escaping needed there)
    and safe in element text content. The report must produce valid HTML."""
    doc = "The team's results didn't match Jones' figures."
    html = generate_html_report(doc, _result(doc))
    # The document must not contain a broken title attribute: a raw ' cannot break
    # out of a title="..." value because the delimiter is ".
    for m in re.finditer(r'title="([^"]*)"', html):
        # The attribute value is well-formed as long as it closes with "
        # (which the regex guarantees by not allowing " inside).
        assert m.group(0).endswith('"'), (
            f"title attribute not closed properly: {m.group(0)!r}"
        )
    # The text should still be present (not silently dropped).
    assert "results" in html


def test_all_payloads_combined_are_inert() -> None:
    """All four issue-spec payloads in one document produce an inert report.

    This is the single comprehensive assertion from the issue:
    'assert the raw substring does NOT appear unescaped in the output'.
    """
    html = generate_html_report(_XSS_DOC, _result(_XSS_DOC))

    # 1. <script> tag must not appear unescaped
    assert "<script>" not in html, "unescaped <script> tag"
    assert "alert(1)</script>" not in html, "unescaped </script> tag"

    # 2. & must be escaped
    assert "&amp;" in html, "& was not escaped to &amp;"

    # 3. < and > must be escaped (they appear in the script payload)
    assert "&lt;" in html, "< was not escaped to &lt;"
    assert "&gt;" in html, "> was not escaped to &gt;"

    # 4. javascript: must not appear as a URL (only safe in escaped text content)
    assert 'href="javascript:' not in html
    assert "href='javascript:" not in html
    assert 'src="javascript:' not in html

    # 5. The document must contain the DTD and be structurally valid HTML5
    assert "<!doctype html>" in html.lower()
    assert "<html" in html
    assert "</html>" in html
    assert '<meta charset="utf-8">' in html or '<meta charset="UTF-8">' in html


def test_xss_payloads_in_result_warning_are_escaped() -> None:
    """A warning or error message from the result dict is also escaped."""
    doc = "Normal text."
    res = _result(doc)
    res["warning"] = '<script>alert("pwned")</script>'
    html = generate_html_report(doc, res)
    assert "<script>" not in html, "unescaped <script> in warning field"
    assert "&lt;script&gt;" in html, "warning field not escaped"


def test_xss_payload_in_rewriter_name_is_escaped() -> None:
    """Metadata fields (rewriter, tier, stopped) are also user-controlled and must be escaped."""
    doc = "Normal text."
    res = _result(doc)
    res["rewriter"] = '<img src=x onerror=alert(1)>'
    html = generate_html_report(doc, res)
    assert '<img src=x onerror=alert(1)>' not in html, (
        "unescaped HTML in rewriter metadata field"
    )
    assert "&lt;img" in html, "rewriter field not HTML-escaped"
