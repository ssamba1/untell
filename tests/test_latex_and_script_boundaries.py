"""Two boundaries the rewriter must not cross: LaTeX markup, and scripts it cannot read.

Both were defect-table rows. Re-deriving them found the LaTeX fix sound and the CJK fix sound in
substance but wrong in its message — a 40-character Chinese paragraph was reported as "shorter than
5 words", which is true of the word regex and absurd to the reader. These tests hold both.
"""

from __future__ import annotations

import logging

import pytest

from untell.humanness import humanness
from untell.scripts.latex import cite_keys
from untell.scripts.preserve import lock, restore
from untell.scripts.tells import score_tells

PAPER = (
    r"\section{Results} We evaluate on five datasets following \citet{smith2023}, and compare "
    r"against the baseline of \citep{jones2022}. Our method improves accuracy by 12.4\% over "
    r"\cite{li2024mage}, averaged over 3 seeds, with $\alpha = 0.01$ throughout. Table \ref{tab:main} "
    r"reports the full breakdown, and \autoref{eq:loss} gives the objective."
)

# Every token whose corruption would break the paper. Citation keys and refs stop resolving; a
# mangled number or math expression states something the authors did not measure.
MUST_SURVIVE = [
    r"\cite{li2024mage}",
    r"\citet{smith2023}",
    r"\citep{jones2022}",
    r"\ref{tab:main}",
    r"12.4",
    r"\%",
    r"$\alpha = 0.01$",
    "3 seeds",
    "five datasets",
]


def test_lock_holds_the_markup_of_a_real_paper_paragraph() -> None:
    """The row read "LaTeX entirely unprotected — lock() held 0 spans"."""
    masked, spans = lock(PAPER)
    assert len(spans) >= 8, f"only {len(spans)} spans locked in a paragraph full of markup"
    assert restore(masked, spans) == PAPER, "lock/restore does not round-trip"
    # The point of masking: the rewriter sees prose, not markup.
    assert r"\cite" not in masked
    assert "$" not in masked


def test_cite_keys_finds_every_citation_form() -> None:
    assert sorted(cite_keys(PAPER)) == ["jones2022", "li2024mage", "smith2023"]


@pytest.mark.parametrize("token", MUST_SURVIVE, ids=lambda t: t[:18])
def test_markup_survives_a_real_rewrite(token: str) -> None:
    """lock/restore round-tripping in isolation is not the claim; surviving the pipeline is.

    A single seed proves nothing here — the rewriter is stochastic, and the failure mode this row
    described is intermittent by nature. Several seeds, and the token must survive every one.

    Two things have to be forced for that claim to be tested at all, and neither was:

    ``rewriter="composite"`` — without it the loop resolves no rewriter unless an API key happens to
    be configured, and returns ``{"error": ..., "final": PAPER}``. The token then survived because
    nothing had touched it. On a machine with no key, which is CI, this ran five seeds of nothing.

    ``threshold=0.0`` — the fixture already scores clean, so even with a rewriter the loop stops at
    ``"passed"`` before the first draw. An unreachable threshold is what keeps it rewriting.

    The assertion on ``rewrites`` is the guard: if either condition regresses, this fails instead of
    quietly going hollow again.
    """
    import random

    from untell.scripts.run import untell_text

    assert token in PAPER, "the fixture no longer contains the token under test"
    for seed in range(5):
        # `untell_text` takes no seed; the rewriter draws from the global RNG, so seeding it here
        # is what makes each iteration a distinct draw rather than five identical ones.
        random.seed(seed)
        result = untell_text(
            PAPER, tier="lite", max_iters=1, rewriter="composite", threshold=0.0
        )
        assert result.get("rewrites"), (
            f"seed {seed}: the loop never rewrote, so nothing about survival was tested "
            f"(stopped={result.get('stopped') or result.get('error')})"
        )
        assert token in result["final"], f"seed {seed} destroyed {token!r}:\n{result['final']}"


def test_cjk_is_undetermined_not_clean() -> None:
    """0 tells on Chinese means the English patterns did not apply, not that the text reads human."""
    chinese = "此外，该框架利用强大的方法在规模上提供成果，并且显著提高了整体效率和准确性。"
    result = score_tells(chinese)
    assert result["tells"] == 0
    assert result["language_supported"] is False, (
        "a 0 with no caveat is a false all-clear on text the catalogue cannot read"
    )
    assert humanness(chinese, tier="lite") == 50.0


def test_cjk_is_not_reported_as_too_short(caplog: pytest.LogCaptureFixture) -> None:
    """The message, not the number. `_WORD_RE` is [A-Za-z']+, so CJK has zero words by that count
    and used to be blamed on length — pointing the reader at "write more" instead of at the real
    limit. Both paths return 50; only one of them explains why."""
    import untell.humanness as mod

    mod._WARNED_UNSUPPORTED_LANGUAGE = False
    mod._WARNED_TOO_SHORT = False
    with caplog.at_level(logging.WARNING, logger=mod.logger.name):
        humanness("此外，该框架利用强大的方法在规模上提供成果，并且显著提高了整体效率。", tier="lite")
    text = caplog.text.lower()
    assert "script" in text or "english-only" in text, f"no language warning: {caplog.text!r}"
    assert "shorter than" not in text, f"still blaming length for a script problem: {caplog.text!r}"


def test_genuinely_short_english_still_says_short(caplog: pytest.LogCaptureFixture) -> None:
    """Guards the guard above: routing everything to the language message would also pass it."""
    import untell.humanness as mod

    mod._WARNED_UNSUPPORTED_LANGUAGE = False
    mod._WARNED_TOO_SHORT = False
    with caplog.at_level(logging.WARNING, logger=mod.logger.name):
        humanness("Hi there.", tier="lite")
    assert "shorter than" in caplog.text.lower(), caplog.text
