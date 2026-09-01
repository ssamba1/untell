"""A flag-rate comparison between two groups is unreadable unless they are length-matched.

Round thirty-six: this repository's outlier fairness arm produced a gap that separated its intervals
at five of seven cut-offs on 6,810 documents — and it was largely a length artefact. The group being
compared was selected on stylometry, stylometry is not length-neutral, and this repo had already
measured detectors flagging short text far more often (30.0% at <=50 words against 13.3% at 200+).

`eval/assisted_fairness.py` compares native against non-native authors, and inherits exactly that
risk. MEASURED, it happens to be safe: the corpus is matched by design, 36 documents per group per
arm, with medians of 180 against 176 words for the human arm and 136 against 135 for the assisted
one. **That is worth checking rather than assuming**, and worth re-checking automatically whenever
the corpus changes — which is what these tests are for. A future corpus that is not matched must make
the report say so, not quietly produce a comparable-looking table.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eval import assisted_fairness as af

CACHE = Path(".assisted-cache/pratama_abstracts.csv")
needs_corpus = pytest.mark.skipif(
    not CACHE.exists(), reason="Pratama corpus not cached (run `python -m eval.assisted_fairness`)"
)


def _rows(pairs: list[tuple[str, int]]) -> list[dict[str, str]]:
    """Rows with a given status and abstract length, for the columns `ARMS` reads."""
    column = next(iter(af.ARMS))
    return [{"Status": status, "Abstract": "word " * words, column: "word " * words}
            for status, words in pairs]


def test_a_matched_corpus_is_reported_as_matched():
    rows = _rows([("Native", 200)] * 10 + [("Non-Native", 198)] * 10)
    report = af.length_balance(rows)
    assert report["length_matched"] is True
    assert report["worst_relative_gap"] < 0.05


def test_an_unmatched_corpus_is_caught():
    """The failure the check exists for: one group systematically shorter than the other. Without
    this, the flag-rate table would look exactly the same and mean something else."""
    rows = _rows([("Native", 220)] * 10 + [("Non-Native", 90)] * 10)
    report = af.length_balance(rows)
    assert report["length_matched"] is False
    assert report["worst_relative_gap"] > 0.5


def test_the_rendering_warns_when_the_groups_are_not_matched():
    text = af._render({
        "tier": "lite", "arms": {},
        "false_accusation_arms": list(af.HUMAN_AUTHORED),
        "length_balance": {"by_arm": {}, "worst_relative_gap": 0.62,
                           "length_matched": False, "note": "n/a"},
    })
    assert "NOT length-matched" in text
    assert "may be document length rather than author status" in text


def test_the_rendering_says_so_when_they_are():
    text = af._render({
        "tier": "lite", "arms": {},
        "false_accusation_arms": list(af.HUMAN_AUTHORED),
        "length_balance": {"by_arm": {}, "worst_relative_gap": 0.06,
                           "length_matched": True, "note": "n/a"},
    })
    assert "ARE length-matched" in text


@needs_corpus
def test_the_real_corpus_is_still_length_matched():
    """If this ever fails, the arm's published subgroup rates have stopped being comparable and the
    finding built on them needs re-reading, not re-running."""
    report = af.length_balance(af.load_rows(CACHE))
    assert report["length_matched"], (
        f"the Pratama corpus is no longer length-matched "
        f"(worst median gap {report['worst_relative_gap']:.1%}) — subgroup flag rates from it are "
        f"confounded with document length"
    )


@needs_corpus
def test_the_balance_check_travels_with_the_rates():
    """A confound check in a separate command is a confound check nobody runs."""
    rows = af.load_rows(CACHE)[:4]
    assert "length_balance" in af.evaluate(rows, tier="lite")
