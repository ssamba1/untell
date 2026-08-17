"""Tests for `untell humanize --html` — a self-contained HTML report (issue #30).

The humanize loop already has a rich terminal report and a `--diff` payload. `--html`
turns the same run into a single self-contained HTML document that can be saved and
shared. This file pins the properties the issue's acceptance depends on:

1. **Determinism** — identical inputs produce byte-identical output (no timestamp,
   no random, no process-dependent value), so the artifact is reproducible.

2. **Escaping / injection** — every value that came from the user's text (original,
   final, locked spans, rules, rationale, warning) is HTML-escaped. Text that IS
   attacker-shaped markup (a `<script>` inside the text being humanized) must render
   as inert characters, never as a live tag. Fuzzed here with several hostile shapes.

3. **Self-contained** — the document carries an inline <style> and zero
   <script>/<link> references or remote URLs, so it renders identically from a
   file:// path with no external assets and no JS.

4. **It carries the run** — pre/post scores, the seed, whether it rewrote, the
   unified --diff hunks and the per-span lock annotations (built on the explain
   machinery, same single source of truth as `lock()`).

5. **CLI contract** — `--html` prints the document on stdout (and only that, so
   redirecting to a .html file yields a clean page); `--html --json` emits a
   machine-readable envelope holding the report string plus the diff payload; the
   error path stays parseable under `--json`.
"""

from __future__ import annotations

import json

from untell import rich_output
from untell.rich_output import render_humanize_html
from untell.scripts.run import main

AI = (
    "Furthermore, artificial intelligence has fundamentally transformed numerous industries. "
    "Moreover, organizations utilize it to significantly improve operational efficiency. Overall, "
    "the impact continues to grow across various sectors according to Smith (2020), rising 47%."
)

EDITED = AI.replace("fundamentally transformed", "deeply reshaped")


def _scores(pre: float, post: float, tier: str = "lite") -> tuple[dict, dict]:
    return (
        {"max": pre, "mean": pre * 0.9, "tier": tier, "threshold": 0.30, "flagged": pre >= 0.3},
        {"max": post, "mean": post * 0.9, "tier": tier, "threshold": 0.30, "flagged": post >= 0.3},
    )


def _sample_diff(original: str, final: str) -> dict:
    from untell.scripts.explain import explain_spans

    return rich_output.humanize_diff(original, final, locked_spans=explain_spans(original))


# ---------------------------------------------------------------------------
# determinism + self-containment
# ---------------------------------------------------------------------------


def test_the_report_is_deterministic() -> None:
    a = render_humanize_html(AI, EDITED, *_scores(0.80, 0.20), 1, "converged", diff=_sample_diff(AI, EDITED), seed=7, rewrote=True)
    b = render_humanize_html(AI, EDITED, *_scores(0.80, 0.20), 1, "converged", diff=_sample_diff(AI, EDITED), seed=7, rewrote=True)
    assert a == b
    assert render_humanize_html("x", "y", *_scores(0.5, 0.5), 1, "limit", seed=1) == render_humanize_html(
        "x", "y", *_scores(0.5, 0.5), 1, "limit", seed=1
    )


def test_the_report_is_a_complete_self_contained_document() -> None:
    html = render_humanize_html(AI, EDITED, *_scores(0.80, 0.20), 1, "converged", diff=_sample_diff(AI, EDITED), seed=7, rewrote=True)
    assert html.startswith("<!DOCTYPE html>") and html.strip().endswith("</html>")
    assert "<style>" in html and "</style>" in html
    # No external assets: no JS, no stylesheet link, no remote URL anywhere.
    for marker in ("<script", "</script>", "<link ", "<img ", "src=", "href=", "http://", "https://"):
        assert marker not in html, f"external-asset marker {marker!r} present in a self-contained report"


# ---------------------------------------------------------------------------
# escaping / injection (this is a defect — fuzz it)
# ---------------------------------------------------------------------------

_HOSTILE = [
    "<script>alert(1)</script>",
    "</script><script>alert(2)</script>",
    '<img src=x onerror=alert(3)>',
    '"><script>alert(4)</script>',
    "<b>bold</b> & <i>italic</i>",
    "quote ' single \" double",
    "<svg/onload=alert(5)>",
]


def test_all_hostile_shapes_are_inert_in_the_report() -> None:
    for hostile in _HOSTILE:
        html = render_humanize_html(
            hostile,
            hostile,  # unchanged path still renders the hostile text
            *_scores(0.5, 0.5), 1, "converged",
            diff={"hunks": []}, seed=1, rewrote=False,
        )
        # The escaped spelling appears; a live tag never does. Escaping neutralises the
        # tag boundaries ("><"), so the real invariant is that no literal `tagname` opens.
        assert "&lt;" in html or "&#x27;" in html or "&quot;" in html
        for marker in ("<script", "</script", "<img", "<svg", "<b>", "<i>"):
            assert marker not in html, f"{hostile!r} leaked a live tag {marker!r}"


def test_hostile_span_and_rationale_are_escaped() -> None:
    """Locked spans and their rationale are user-carried text too — a hostile span must
    not break out of its table cell or execute."""
    diff = {
        "format": "untell-diff", "version": 1, "changed": False, "hunks": [],
        "locked_spans": [
            {"sentinel": "⟦HZ0000⟧", "span": '<script>bad()</script>', "rules": ["evil"],
             "rationale": "note <b>with</b> markup"},
        ],
        "locks_preserved": 0,
    }
    html = render_humanize_html("in", "in", *_scores(0.5, 0.5), 1, "converged", diff=diff, seed=1)
    assert "<script>bad()</script>" not in html
    assert "&lt;script&gt;bad()&lt;/script&gt;" in html
    assert "&lt;b&gt;with&lt;/b&gt;" in html


def test_hostile_warning_is_escaped() -> None:
    html = render_humanize_html(
        "a", "b", *_scores(0.8, 0.2), 1, "converged",
        warning='carried <script>warn()</script> payload', diff=_sample_diff("a", "b"), seed=1, rewrote=True,
    )
    assert "<script>warn()</script>" not in html
    assert "&lt;script&gt;warn()&lt;/script&gt;" in html


# ---------------------------------------------------------------------------
# the renderer carries the run
# ---------------------------------------------------------------------------


def test_the_report_carries_scores_seed_rewrote_and_stopped() -> None:
    pre, post = _scores(0.82, 0.19)
    html = render_humanize_html(
        AI, EDITED, pre, post, 3, "converged",
        diff=_sample_diff(AI, EDITED), seed=42, rewrote=True, tells_before=9, tells_after=3,
    )
    assert "0.8200" in html and "0.1900" in html
    assert "seed: 42" in html
    assert "Rewrote" in html
    assert "3 iterations" in html
    assert "Converged" in html  # the stopped reason, title-cased from the enum value
    assert "AI tells" in html and "9" in html and "3" in html


def test_the_report_says_when_it_did_not_rewrite() -> None:
    html = render_humanize_html(AI, AI, *_scores(0.8, 0.8), 0, "no-op", seed=3, rewrote=False, diff={"hunks": []})
    assert "Returned unchanged" in html or "no change" in html


def test_the_lock_annotations_are_present_with_rationale() -> None:
    html = render_humanize_html(AI, EDITED, *_scores(0.80, 0.20), 1, "converged", diff=_sample_diff(AI, EDITED), seed=7)
    assert "Locked spans" in html
    assert "Smith (2020)" in html and "47%" in html
    # Rationale text from the explain registry rides along.
    assert "citation" in html.lower() or "number" in html.lower()


def test_the_diff_hunks_render() -> None:
    html = render_humanize_html(AI, EDITED, *_scores(0.80, 0.20), 1, "converged", diff=_sample_diff(AI, EDITED), seed=7)
    assert "Diff" in html
    assert "@@" in html  # a unified-diff hunk header
    assert "deeply reshaped" in html


# ---------------------------------------------------------------------------
# CLI contract
# ---------------------------------------------------------------------------


class _EditRW:
    name = "edit"

    def available(self):
        return True

    def rewrite(self, text, score_result, threshold=0.30):
        return text.replace("fundamentally transformed", "deeply reshaped")


class _IdentityRW:
    name = "identity"

    def available(self):
        return True

    def rewrite(self, text, score_result, threshold=0.30):
        return text


def _fixed_score(mapping: dict, default: float = 0.8):
    def _s(text, tier="full", threshold=0.3):
        mx = mapping.get(text.strip(), default)
        return {
            "tier": tier,
            "detectors": {"perplexity_burstiness": mx},
            "max": mx,
            "mean": mx,
            "threshold": threshold,
            "flagged": mx >= threshold,
            "scored": True,
        }

    return _s


def _patch_cli(monkeypatch, rewriter, scores: dict, default: float = 0.8) -> None:
    import untell.rewriter as rewriter_mod
    import untell.scripts.run as run_mod

    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    monkeypatch.setattr(rewriter_mod, "get_rewriter", lambda prefer=None: rewriter)
    monkeypatch.setattr(run_mod, "score_text", _fixed_score(scores, default))


def test_cli_escapes_injected_text(monkeypatch, capsys) -> None:
    """A hostile document must come out of `--html` fully escaped — a defect if it
    does not, so it is asserted at the CLI surface, not only in the renderer."""
    _patch_cli(monkeypatch, _IdentityRW(), {}, default=0.8)
    hostile = "<script>alert(1)</script> AI cost $500 per Smith (2020)."
    rc = main(["--tier", "lite", "--html", "--max-iters", "1", "--best-of", "1", hostile])
    assert rc == 0
    html = capsys.readouterr().out
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_cli_html_human_output(monkeypatch, capsys) -> None:
    _patch_cli(monkeypatch, _EditRW(), {AI: 0.80, EDITED: 0.20})
    rc = main(["--tier", "lite", "--html", "--max-iters", "1", "--best-of", "1", AI])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith("<!DOCTYPE html>"), "stdout must BE the html document, not a wrapper"
    assert "Locked spans" in out and "Diff" in out and "Before" in out and "After" in out
    assert "Rewrote" in out
    assert "Smith (2020)" in out and "47%" in out
    # The standard terminal render must not also run.
    assert "--- Original ---" not in out
    assert "humanization complete (" not in out


def test_cli_html_json_envelope(monkeypatch, capsys) -> None:
    _patch_cli(monkeypatch, _EditRW(), {AI: 0.80, EDITED: 0.20})
    rc = main(["--tier", "lite", "--html", "--json", "--max-iters", "1", "--best-of", "1", AI])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["format"] == "untell-html"
    assert payload["version"] == 1
    assert payload["html"].startswith("<!DOCTYPE html>")
    assert payload["diff"]["format"] == "untell-diff"
    assert payload["rewrote"] is True and payload["seed"] is not None
    assert payload["pre"]["max"] == 0.80 and payload["post"]["max"] == 0.20
    spans = [row["span"] for row in payload["diff"]["locked_spans"]]
    assert "Smith (2020)" in spans and "47%" in spans
    assert payload["diff"]["locks_preserved"] == len(spans) == 2


def test_cli_html_json_envelope_no_change(monkeypatch, capsys) -> None:
    _patch_cli(monkeypatch, _IdentityRW(), {}, default=0.8)
    rc = main(["--tier", "lite", "--html", "--json", "--max-iters", "1", "--best-of", "1", AI])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["rewrote"] is False
    assert payload["diff"]["changed"] is False
    assert "Returned unchanged" in payload["html"] or "no change" in payload["html"]


def test_cli_html_json_error_path_holds(monkeypatch, capsys) -> None:
    """`--html --json` with no input must answer JSON and exit 2, like the other modes."""
    _patch_cli(monkeypatch, _IdentityRW(), {})
    rc = main(["--tier", "lite", "--html", "--json", "   "])
    assert rc == 2
    parsed = json.loads(capsys.readouterr().out)
    assert "error" in parsed


def test_cli_html_reports_rewriter_failure(monkeypatch, capsys) -> None:
    class _BrokenRW:
        name = "broken"

        def available(self):
            return True

        def rewrite(self, text, score_result, threshold=0.30):
            raise RuntimeError("simulated rewriter failure")

    _patch_cli(monkeypatch, _BrokenRW(), {}, default=0.9)
    rc = main(["--tier", "lite", "--html", "--max-iters", "1", "--best-of", "1", AI])
    assert rc == 1
    out = capsys.readouterr().out
    assert "ERROR" in out and "rewriter failed" in out
