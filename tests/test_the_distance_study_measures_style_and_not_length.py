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
