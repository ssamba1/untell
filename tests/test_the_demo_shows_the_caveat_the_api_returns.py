"""The web demo showed a percentage and a "Human" badge with no caveat at all.

`docs/demo.html` is the front-end the README links, and it always scores at `tier: 'lite'`. That
tier's stdlib path is documented as weak in BOTH directions — 64% of human text scores above the
0.30 threshold, and it clears 10-70% of AI text depending on corpus — and `/score` returns a
`warning` saying so on every such response.

The page never read it. MEASURED: `score_text(..., tier="lite")` on the stdlib path returns
`max=0.6495` with a warning present, and `grep -c warning docs/demo.html` was 0. So the most
public surface in the project reported a bare number where the CLI printed the caveat in full —
the same gap `humanness` had, one surface further out.

This is the reassuring direction, which is the one worth fixing first: a user who sees "12% —
Human" and no caveat has been told something the tool does not know.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parents[1] / "docs" / "demo.html"


@pytest.fixture(scope="module")
def html() -> str:
    return DEMO.read_text(encoding="utf-8")


def test_the_page_reads_the_warning_field(html: str):
    assert "post.warning" in html or "pre.warning" in html, (
        "the demo never reads the `warning` the API returns, so it shows a bare percentage on the "
        "weakest scoring path"
    )


def test_there_is_somewhere_to_show_it(html: str):
    """A field read and never rendered would be the same defect with extra steps."""
    assert 'id="scoreCaveat"' in html
    assert ".caveat" in html, "no style rule for the caveat element"


def test_the_caveat_is_hidden_until_there_is_one(html: str):
    """Always-on caveat text is furniture; users stop reading it."""
    block = html[html.index('id="scoreCaveat"') - 200: html.index('id="scoreCaveat"') + 200]
    assert "display:none" in block.replace(" ", ""), block


def test_the_caveat_is_cleared_between_runs(html: str):
    """A stale caveat from a previous run is worse than none — it describes the wrong text."""
    assert re.search(r"caveat\.style\.display\s*=\s*'none'", html), (
        "the caveat is shown but never hidden again, so it persists across runs"
    )


def test_the_demo_still_scores_at_lite(html: str):
    """The premise. If it moved to the full tier the caveat would rarely apply and this file is stale."""
    assert "tier: 'lite'" in html or 'tier: "lite"' in html


def test_the_api_really_returns_a_warning_on_that_path(monkeypatch):
    """Guards the guard: if the API stopped warning, the page would have nothing to show."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    from untell.scripts.score import score_text

    result = score_text(
        "Moreover, the framework leverages robust methodologies to deliver outcomes at scale "
        "and improves overall efficiency across the evaluated corpus.",
        tier="lite",
    )
    assert result.get("warning"), "the stdlib path stopped warning; the demo has nothing to surface"
