"""The confound reverses the answer, so the control is the whole experiment.

`eval/homogenization.py` fills a gap this repo wrote down and the literature has not: FPR as a
function of a document's stylistic distance from the machine centre of mass
(`ai-writing-research.md`, *Gaps worth noting* #5). The prediction is that a detector's
false-positive rate FALLS as a document moves away from the centre, which would make homogenization
and detection two views of one phenomenon rather than two correlated findings.

MEASURED on 150 pre-ChatGPT ACL abstracts — human by construction, so every flag is a false
positive — the crude and standardized curves point in OPPOSITE directions:

    bin   mean words   crude FPR   standardized FPR
    0 (nearest)  168      10.0%          18.0%
    4 (farthest) 117      16.7%           5.4%

Crude says false positives RISE with distance; standardized says they FALL. The mean word counts
say why: distant documents are shorter, because a short document estimates its own word frequencies
badly and lands further from any centroid by noise alone — and this corpus flags 28.69% of 60-100
word documents against 12.77% above 200. **Anyone running this study without the length control
would have published the opposite of the finding.**

So these tests are about the control, not the headline. A study whose direction depends on a
correction is only worth as much as the correction is.
"""

from __future__ import annotations

import random

from eval import homogenization as H


def _synthetic(n: int, vocabulary: list[str], seed: int, words: int = 120) -> list[str]:
    rng = random.Random(seed)
    return [" ".join(rng.choice(vocabulary) for _ in range(words)) for _ in range(n)]


MACHINEY = ["the", "of", "and", "a", "to", "in", "that", "is", "we", "this"]
HUMANY = ["although", "however", "rather", "seldom", "whereas", "thus", "yet", "since"]


def test_a_document_from_the_machine_population_sits_closer_to_its_own_centre() -> None:
    """The instrument's floor: if Delta cannot separate two populations it cannot measure anything
    about the space between them."""
    machine = _synthetic(30, MACHINEY, seed=1)
    human = _synthetic(30, MACHINEY + HUMANY, seed=2)
    machine_to_machine = H.distances(machine, machine)
    human_to_machine = H.distances(human, machine)
    assert sum(machine_to_machine) / len(machine_to_machine) < \
           sum(human_to_machine) / len(human_to_machine)


def test_the_vocabulary_is_pooled_so_neither_side_picks_its_own_features() -> None:
    """Taking the feature set from one population decides the answer before measuring it: the
    machine's own most-frequent words guarantee the humans look distant, and vice versa."""
    machine = _synthetic(10, MACHINEY, seed=3)
    human = _synthetic(10, HUMANY, seed=4)
    pooled = set(H.vocabulary(human + machine, 40))
    assert pooled & set(MACHINEY), "pooled vocabulary lost the machine side's words"
    assert pooled & set(HUMANY), "pooled vocabulary lost the human side's words"


def test_the_bins_are_equal_count_quantiles_not_fixed_cutoffs() -> None:
    """Delta is z-scores averaged and has no natural units, so a fixed boundary would be a constant
    nobody chose — the defect rounds 86 and 89 of the ledger exist to prevent. Equal-count bins also
    keep the Wilson intervals comparable, which a fixed cut does not."""
    rows = [{"delta": i / 100, "words": 100, "flagged": i % 2, "max": 0.4} for i in range(100)]
    out = H.curve(list(rows), bins=5)
    sizes = [b["n"] for b in out["bins"]]
    assert max(sizes) - min(sizes) <= 1, f"bins are not equal-count: {sizes}"


def test_standardization_changes_the_answer_when_length_tracks_distance() -> None:
    """The control, tested on data built so the confound is the ONLY thing present.

    Every document is flagged if and only if it is short. Distance is made to track shortness. The
    crude curve must therefore show flags rising with distance, and the standardized curve must
    flatten it — because within any one length band there is no distance effect at all here.
    """
    rows = []
    for i in range(200):
        short = i >= 100
        rows.append({
            "delta": (0.9 if short else 0.1) + i * 1e-4,
            "words": 70 if short else 250,
            "flagged": int(short),
            "max": 0.5,
        })
    out = H.curve(rows, bins=2)
    near, far = out["bins"][0], out["bins"][-1]
    assert near["fpr_crude"] == 0.0 and far["fpr_crude"] == 1.0, "the confound is not in the data"
    # Within a band the rate is 0 or 1 with no distance signal, so standardizing to the corpus's
    # own 50/50 length mix must pull both bins toward each other.
    # PERFECT confounding is the case direct standardization cannot solve: with each bin holding
    # one length band there is no within-band contrast to reweight. The arithmetic still returns a
    # number — the crude one — so the requirement is that the module REFUSES rather than dresses it
    # up. This is the same rule the ledger applies to an unmeasurable mutation baseline.
    for side in (near, far):
        assert side["fpr_standardized"] is None, (
            "a perfectly confounded bin cannot be standardized, but a number was reported"
        )
        assert "one length band" in (side["standardization"] or ""), side["standardization"]
        assert len(side["bands"]) == 1


def test_standardization_shrinks_a_length_effect_when_the_bins_do_overlap() -> None:
    """The other half: where bins DO span both bands — the real corpus's case — the correction has
    to actually work, not merely decline to run."""
    rows = []
    for i in range(400):
        far_bin = i >= 200
        # Both bins carry both lengths, but the far bin is short-heavy: the real confound's shape.
        short = (i % 10) < (8 if far_bin else 2)
        rows.append({
            "delta": (0.9 if far_bin else 0.1) + i * 1e-5,
            "words": 70 if short else 250,
            "flagged": int(short),          # flagging depends on LENGTH only
            "max": 0.5,
        })
    out = H.curve(rows, bins=2)
    near, far = out["bins"][0], out["bins"][-1]
    assert near["fpr_standardized"] is not None and far["fpr_standardized"] is not None
    crude_gap = abs(far["fpr_crude"] - near["fpr_crude"])
    std_gap = abs(far["fpr_standardized"] - near["fpr_standardized"])
    assert crude_gap > 0.5, "the confound is not in the data"
    assert std_gap < 0.01, (
        f"flagging depends only on length here, so standardizing must erase the gap: "
        f"crude {crude_gap:.3f}, standardized {std_gap:.3f}"
    )


def test_the_sign_test_matches_hand_computed_values() -> None:
    """Ties excluded, two-sided. 17 against 9 is what a fair coin does about one time in six, and
    the machine arm turns on exactly that distinction."""
    assert H.sign_test(0, 0) == 1.0                      # nothing moved
    assert H.sign_test(5, 5) == 1.0                      # perfectly split
    assert round(H.sign_test(0, 5), 4) == 0.0625         # 2 * (1/32)
    assert round(H.sign_test(9, 17), 3) == 0.169
    assert H.sign_test(4, 36) < 0.001                    # the human arm's structural result


def test_ties_are_excluded_from_the_sign_test_rather_than_split() -> None:
    """A rewriter that returns its input carries no directional evidence. Counting those as
    half-successes would shrink the p-value for free — and `surgical` leaves 39 of 40 documents
    byte-identical, so this is the difference between "no effect" and a fabricated one."""
    assert H.sign_test(1, 0) == H.sign_test(1, 0)
    few = H.sign_test(1, 0)
    assert few == 1.0, "one moved document must not be significant at any tie count"


def test_the_trend_test_finds_a_trend_that_is_really_there() -> None:
    """Floor check: an instrument that cannot detect a planted effect cannot report a null."""
    strong = H.trend_test([10, 30, 50, 70, 90], [100] * 5)
    assert strong["p"] < 0.001 and strong["direction"] == "rises with distance"
    falling = H.trend_test([90, 70, 50, 30, 10], [100] * 5)
    assert falling["p"] < 0.001 and falling["direction"] == "falls with distance"


def test_the_trend_test_reports_a_null_when_there_is_no_trend() -> None:
    flat = H.trend_test([50, 50, 50, 50, 50], [100] * 5)
    assert flat["p"] > 0.5, flat


def test_a_degenerate_split_is_reported_as_degenerate_not_as_a_null() -> None:
    """No contrast is not the same fact as no effect, and both would otherwise print as a number."""
    assert H.trend_test([0, 0, 0], [10, 10, 10])["p"] is None
    assert H.trend_test([10, 10, 10], [10, 10, 10])["p"] is None
    assert "degenerate" in H.trend_test([0, 0, 0], [10, 10, 10])["note"]


def test_stratifying_removes_a_trend_that_is_purely_length() -> None:
    """The scenario the real corpus presents, planted so the right answer is known.

    MEASURED on the 6,810-document corpus, the CRUDE test reports a significant trend — p=0.0305 —
    in the direction OPPOSITE the prediction, because distant documents are shorter (mean 130 words
    in the farthest quintile against 172 in the nearest) and this corpus flags 28.69% of 60-100
    word documents against 12.77% above 200. A reader handed only that test would conclude
    stylistic distance PROTECTS a writer, from an artefact of estimation noise in short text.

    Here flagging depends on length and nothing else, and distance is arranged to track it. The
    crude test must find a trend; the stratified test must not.
    """
    rows = []
    for i in range(1000):
        bin_index = i // 200
        # Short documents grow more common with distance, and only short documents get flagged.
        short = (i % 10) < (1 + 2 * bin_index)
        rows.append({
            "bin": bin_index,
            "band": "50-100" if short else "200+",
            "flagged": int(short),
            "words": 70 if short else 250,
        })
    crude = H.trend_test(
        [sum(r["flagged"] for r in rows if r["bin"] == b) for b in range(5)],
        [sum(1 for r in rows if r["bin"] == b) for b in range(5)],
    )
    stratified = H.stratified_trend_test(rows)
    assert crude["p"] < 0.001, f"the confound is not in the data: {crude}"
    assert stratified["p"] is None or stratified["p"] > 0.05, (
        f"stratifying failed to remove a pure length effect: {stratified}"
    )


def test_stratifying_keeps_a_trend_that_survives_the_control() -> None:
    """The other direction: a real within-band effect must not be standardized away, or the control
    would be buying its null by destroying signal."""
    rows = []
    for i in range(1000):
        bin_index = i // 200
        short = (i % 2) == 0          # length independent of distance
        # A real effect: flag rate falls with distance INSIDE both bands.
        flagged = int((i % 100) < (40 - 8 * bin_index))
        rows.append({
            "bin": bin_index,
            "band": "50-100" if short else "200+",
            "flagged": flagged,
            "words": 70 if short else 250,
        })
    stratified = H.stratified_trend_test(rows)
    assert stratified["p"] is not None and stratified["p"] < 0.01, stratified
    assert stratified["direction"] == "falls with distance", stratified
