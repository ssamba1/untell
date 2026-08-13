"""Markdown's backticks were covered. Their exact HTML equivalent was not.

`` `parse_json()` `` locks; `<code>parse_json()</code>` did not, so any document written in HTML — a
README rendered from it, a docs page, an issue body, anything pasted out of a CMS — had its code free
for the rewriter. MEASURED through the shipped loop, 6 tags x 2 styles, with the semicolon-to-sentence
transform:

    <code>run a; then b</code>  ->  <code>run a. Then b</code>      12 of 12 DAMAGED
    <pre>, <kbd>, <samp>, <tt>, <var>                               all likewise

    12 of 12 before. 0 of 12 after.

Every tag in the family, both styles, no exceptions — a whole notation missing rather than an edge
case within one. Found by sweeping every preserve category for variants that fail to lock, after the
same sweep found the citation gap in Result 215.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.preserve import lock, restore
from untell.scripts.run import untell_text

TAGS = ["code", "pre", "kbd", "samp", "tt", "var"]
INNER = "run a; then b"
PROSE = (
    "Moreover, it is important to note that the follow-up work found the same pattern in every "
    "cohort. Furthermore, this underscores the robustness of the result across the sites."
)
# Tags that mark up PROSE. Locking these would freeze ordinary text — the expensive error for a
# widened pattern, and one nothing in the output would ever reveal.
PROSE_TAGS = ["p", "em", "strong", "b", "i", "span", "li", "h2"]


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.mark.parametrize("tag", TAGS)
def test_html_code_locks_as_one_span(tag: str) -> None:
    item = f"<{tag}>{INNER}</{tag}>"
    _, spans = lock(f"The manual said {item} when the job fails at night.")
    assert item in spans.values(), spans


@pytest.mark.parametrize("tag", TAGS)
@pytest.mark.parametrize("style", ["default", "academic"])
def test_html_code_survives_the_shipped_loop(tag: str, style: str) -> None:
    item = f"<{tag}>{INNER}</{tag}>"
    doc = f"The manual said {item} when the job fails at night. " + PROSE
    final = untell_text(doc, tier="lite", max_iters=3, style=style)["final"]
    assert item in final, final[:200]


def test_attributes_do_not_break_the_lock() -> None:
    """Real HTML carries classes and language hints; a pattern that only matched the bare tag would
    cover the toy case and miss every document that came out of a renderer."""
    item = '<code class="language-bash" data-lang="sh">run a; then b</code>'
    _, spans = lock(f"The manual said {item} when the job fails.")
    assert item in spans.values(), spans


@pytest.mark.parametrize("tag", PROSE_TAGS)
def test_a_prose_tag_is_not_frozen(tag: str) -> None:
    """Guards the guard. `<p>` and `<em>` mark up sentences the rewriter is supposed to improve."""
    item = f"<{tag}>Moreover, it is important to note that this matters</{tag}>"
    _, spans = lock(f"The page said {item} in its opening section.")
    assert not [v for v in spans.values() if "<" in v], spans


def test_prose_inside_a_document_with_code_still_changes() -> None:
    """End to end for the same guard: the lock must take the code and leave the sentence."""
    doc = f"The manual said <code>{INNER}</code> when the job fails at night. " + PROSE
    final = untell_text(doc, tier="lite", max_iters=3)["final"]
    assert final != doc
    assert "Moreover, it is important to note" not in final


def test_a_mismatched_tag_does_not_match() -> None:
    """The backreference is what stops `<code>x</pre>` from locking, and with it a runaway match
    that would swallow everything between two unrelated tags."""
    _, spans = lock("The manual said <code>run a; then b</pre> when the job fails at night.")
    assert not [v for v in spans.values() if "<code>" in v], spans


@pytest.mark.parametrize("tag", TAGS)
def test_the_lock_round_trips(tag: str) -> None:
    doc = f"The manual said <{tag}>{INNER}</{tag}> when the job fails at night."
    masked, spans = lock(doc)
    assert restore(masked, spans) == doc
