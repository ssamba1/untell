"""The arithmetic of an accusation.

A detector score is a measurement with an error rate, and almost every argument about one goes
wrong in the same few places: a false-positive rate quoted without its sample size, a flag read as
"the probability this is AI" when it is "the probability a human would be flagged", and a per-
document rate applied to a person who submitted many documents. Each function here answers one of
those questions exactly, with no dependencies, so the numbers in an evidence brief can be checked
by hand.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

__all__ = [
    "wilson_interval",
    "rule_of_three_upper",
    "posterior_ai_given_flag",
    "p_any_false_flag",
    "expected_false_flags",
    "honest_writer_table",
    "threshold_at_fpr",
    "recall_at_fpr",
    "auroc",
    "flip_rate",
]

_Z95 = 1.959963984540054


def _check_prob(name: str, p: float) -> float:
    if not isinstance(p, (int, float)) or p != p or not 0.0 <= p <= 1.0:
        raise ValueError(f"{name} must be a probability in [0, 1], got {p!r}")
    return float(p)


def wilson_interval(k: int, n: int, z: float = _Z95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion ``k / n`` (95% by default).

    Chosen over the normal approximation because the cases that matter here are the edge ones:
    a detector that flagged 0 of 40 human essays has an observed rate of 0, and the normal
    interval says [0, 0] — "never wrong" — from forty documents. Wilson says the rate could still
    be as high as ~8.8%, which is the honest answer.
    """
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= k <= n:
        raise ValueError(f"k must be in [0, n], got k={k}, n={n}")
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def rule_of_three_upper(n: int) -> float:
    """Approximate 95% upper bound on a rate after observing 0 events in ``n`` trials (3/n)."""
    if n <= 0:
        raise ValueError("n must be positive")
    return min(1.0, 3.0 / n)


def posterior_ai_given_flag(fpr: float, tpr: float, prior: float) -> float:
    """P(the text is AI-written | the detector flagged it), by Bayes' rule.

    The prosecutor's fallacy is reading a 1% false-positive rate as "99% sure". That is
    P(flag | human), not P(human | flag), and the second depends on how common AI-written work is
    in the population being screened (``prior``). With FPR 1%, TPR 90% and a 5% base rate, a flag
    is right about 83% of the time — one flagged student in six is innocent.
    """
    fpr = _check_prob("fpr", fpr)
    tpr = _check_prob("tpr", tpr)
    prior = _check_prob("prior", prior)
    flagged = tpr * prior + fpr * (1.0 - prior)
    if flagged == 0.0:
        return float("nan")
    return tpr * prior / flagged


def p_any_false_flag(fpr: float, k: int) -> float:
    """P(an honest writer is flagged at least once across ``k`` independent documents).

    A per-document false-positive rate understates per-PERSON risk. At 1% per essay, a student
    who submits 30 essays over a degree has a 26% chance of at least one false flag. Assumes
    independence between documents, which if anything flatters the detector: a writer whose style
    triggers it once tends to trigger it again.
    """
    fpr = _check_prob("fpr", fpr)
    if k < 0:
        raise ValueError("k must be >= 0")
    return 1.0 - (1.0 - fpr) ** k


def expected_false_flags(fpr: float, k: int, cohort: int) -> float:
    """Expected number of honest writers in ``cohort`` flagged at least once over ``k`` documents."""
    if cohort < 0:
        raise ValueError("cohort must be >= 0")
    return cohort * p_any_false_flag(fpr, k)


def honest_writer_table(
    fpr: float, ks: Sequence[int] = (1, 5, 10, 20, 40), cohort: int = 1000
) -> list[dict]:
    """Rows of (documents per writer, P(≥1 false flag), expected flagged per ``cohort``)."""
    return [
        {
            "documents": k,
            "p_at_least_one_false_flag": p_any_false_flag(fpr, k),
            f"flagged_per_{cohort}": expected_false_flags(fpr, k, cohort),
        }
        for k in ks
    ]


def _finite(xs: Sequence[float | None]) -> list[float]:
    return [float(x) for x in xs if x is not None and x == x]


def threshold_at_fpr(human_scores: Sequence[float | None], max_fpr: float) -> float | None:
    """Lowest threshold whose false-positive rate on ``human_scores`` is at most ``max_fpr``.

    A score counts as flagged when ``score >= threshold``. Returns ``None`` with no usable scores.
    """
    max_fpr = _check_prob("max_fpr", max_fpr)
    hs = sorted(_finite(human_scores), reverse=True)
    if not hs:
        return None
    allowed = math.floor(max_fpr * len(hs))  # how many humans we may flag
    if allowed >= len(hs):
        return min(hs)
    # Threshold just above the (allowed)-th highest human score, so at most `allowed` reach it.
    cut = hs[allowed]
    return math.nextafter(cut, math.inf)


def recall_at_fpr(
    ai_scores: Sequence[float | None], human_scores: Sequence[float | None], max_fpr: float
) -> dict:
    """Recall on AI text at the threshold that holds human false positives to ``max_fpr``.

    This is how the strongest 2025 detector study reports results: a detector that catches 99% of
    AI text while flagging 10% of humans is worthless for accusations, and the operating point that
    matters is "how much does it catch when it is NOT allowed to accuse more than 1 in 200 humans".
    """
    thr = threshold_at_fpr(human_scores, max_fpr)
    ai = _finite(ai_scores)
    hs = _finite(human_scores)
    if thr is None or not ai:
        return {"max_fpr": max_fpr, "threshold": thr, "recall": None, "achieved_fpr": None}
    return {
        "max_fpr": max_fpr,
        "threshold": thr,
        "recall": sum(s >= thr for s in ai) / len(ai),
        "achieved_fpr": sum(s >= thr for s in hs) / len(hs),
    }


def auroc(ai_scores: Sequence[float | None], human_scores: Sequence[float | None]) -> float | None:
    """Probability a random AI text outscores a random human one (ties count half)."""
    ai, hs = _finite(ai_scores), _finite(human_scores)
    if not ai or not hs:
        return None
    pairs = [(s, 1) for s in ai] + [(s, 0) for s in hs]
    pairs.sort(key=lambda p: p[0])
    # Rank-sum (Mann-Whitney U) with average ranks for ties: O(n log n).
    ranks = [0.0] * len(pairs)
    i = 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for t in range(i, j + 1):
            ranks[t] = avg
        i = j + 1
    rank_sum_ai = sum(r for r, (_, lab) in zip(ranks, pairs) if lab == 1)
    u = rank_sum_ai - len(ai) * (len(ai) + 1) / 2.0
    return u / (len(ai) * len(hs))


def flip_rate(base_flagged: bool, variant_flagged: Sequence[bool | None]) -> dict:
    """How often a verdict changes across variants of the same text.

    ``None`` entries (the detector produced no score for that variant) are excluded from the
    denominator and counted separately — an unscored variant is not a stable one.
    """
    scored = [v for v in variant_flagged if v is not None]
    flips = sum(1 for v in scored if bool(v) != bool(base_flagged))
    n = len(scored)
    out = {
        "variants_scored": n,
        "variants_unscored": len(variant_flagged) - n,
        "flips": flips,
        "flip_rate": (flips / n) if n else None,
    }
    if n:
        lo, hi = wilson_interval(flips, n)
        out["flip_rate_ci95"] = [lo, hi]
    return out
