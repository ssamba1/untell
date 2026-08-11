"""`verify` is a verdict surface, so it must use the calibrated cut — `score` already does.

`score_text` publishes `verdict_threshold` because the swept optimum differs by scoring path: on
the stdlib lite path it is 0.45, while the rewrite loop keeps optimising against 0.30 so stronger
rewriting is not traded away for a kinder verdict. That fix landed in `score` and not in `verify`,
and `verify` is the command that exits non-zero.

MEASURED over 40 human HC3 texts on the stdlib lite path, before:

    raw max >= 0.30          21/40  (52%)
    score_text "flagged"      7/40  (18%)
    verify "not passing"     21/40  (52%)

Two commands in one tool disagreeing about the same text, the CI-facing one nearly three times
more likely to call human writing AI. After: verify matches score exactly, 7/40.
"""

from __future__ import annotations

import pytest

from untell.scripts.score import DEFAULT_THRESHOLD, score_text
from untell.scripts.verify import verify

# Scores 0.3255 on the stdlib lite path — above the loop's 0.30, below the calibrated 0.45.
IN_THE_BAND = (
    "I went down to the shop on Tuesday because we had run out of the good coffee again, "
    "and the woman behind the counter said they had stopped stocking it back in March."
)


@pytest.fixture(autouse=True)
def _stdlib_path(monkeypatch: pytest.MonkeyPatch):
    """Pin the scoring path. The two lite paths have different swept optima, which is the whole
    reason `verdict_threshold` is per-path rather than a constant."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


def _local_max(result: dict) -> dict:
    return next(v for k, v in result["results"].items() if k.startswith("local:max"))


def test_verify_agrees_with_score_on_the_same_text():
    """The invariant. Two verdict surfaces, one answer."""
    scored = score_text(IN_THE_BAND, tier="lite")
    verified = verify(IN_THE_BAND, tier="lite")
    assert _local_max(verified)["passes"] == (not scored["flagged"])


def test_the_two_surfaces_agree_across_real_corpus_text():
    """The measurement this file exists for, on real data rather than one hand-written probe.

    Before the fix these disagreed on 14 of 40 human HC3 texts — every one sitting between the
    loop's 0.30 target and the calibrated 0.45 verdict.
    """
    try:
        from eval.datasets import load_pairs

        pairs = load_pairs("hc3", n=40, min_words=60)
    except Exception as exc:  # pragma: no cover - environment without the corpus
        pytest.skip(f"corpus unavailable: {exc}")
    if not pairs:  # pragma: no cover
        pytest.skip("corpus returned no pairs")

    in_band = 0
    for human, _ai in pairs:
        scored = score_text(human, tier="lite")
        if DEFAULT_THRESHOLD <= scored["max"] < scored["verdict_threshold"]:
            in_band += 1
        assert _local_max(verify(human, tier="lite"))["passes"] == (not scored["flagged"])
    assert in_band, "premise: some human text must fall between the two cuts, or this proves nothing"


def test_the_calibrated_cut_is_the_one_applied():
    scored = score_text(IN_THE_BAND, tier="lite")
    assert scored["verdict_threshold"] != DEFAULT_THRESHOLD, "premise: the path must be calibrated"
    row = _local_max(verify(IN_THE_BAND, tier="lite"))
    assert row["verdict_threshold"] == scored["verdict_threshold"]


def test_a_text_between_the_two_cuts_now_passes():
    """The band this fix is about: above the loop's target, below the calibrated verdict.

    Found in real corpus text rather than hoped for from a fixed probe. The first version pinned a
    hand-written paragraph and skipped, because that paragraph scores 0.2500 on the stdlib path and
    0.3255 on the torch one — a test that skips proves nothing. A stub detector cannot stand in
    either: `verdict_threshold` is selected from the scoring PATH, so a fake detector drops it back
    to 0.30 and the band closes. It has to be real text through the real path.
    """
    try:
        from eval.datasets import load_pairs

        pairs = load_pairs("hc3", n=40, min_words=60)
    except Exception as exc:  # pragma: no cover - environment without the corpus
        pytest.skip(f"corpus unavailable: {exc}")

    for human, _ai in pairs:
        scored = score_text(human, tier="lite")
        if DEFAULT_THRESHOLD <= scored["max"] < scored["verdict_threshold"]:
            assert scored["flagged"] is False, "the calibrated cut clears it"
            assert verify(human, tier="lite")["passes_all"] is True
            return
    pytest.fail("no human text landed between the two cuts; the band this fix targets is empty")


def test_an_explicit_threshold_is_still_honoured():
    """A caller who chose a number gets it. Substituting another would be its own dishonesty."""
    row = _local_max(verify(IN_THE_BAND, tier="lite", threshold=0.01))
    assert row["verdict_threshold"] == 0.01
    assert row["passes"] is False


def test_an_explicit_permissive_threshold_is_also_honoured():
    row = _local_max(verify(IN_THE_BAND, tier="lite", threshold=0.99))
    assert row["verdict_threshold"] == 0.99
    assert row["passes"] is True


def test_unscored_text_still_fails_rather_than_fabricating_a_pass():
    """The guard that must survive: a placeholder max must never read as a clean pass."""
    row = _local_max(verify("", tier="lite"))
    assert row["passes"] is False
    assert row["ai"] is None
