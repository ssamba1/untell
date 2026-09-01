"""Turn a human-only corpus into a threshold with a *bounded* false-positive rate.

This repo's headline result is that vendor thresholds produce false-positive rates nobody would
accept if they saw them measured: 19.47% of pre-LLM abstracts, 44.44% under the union rule in the
published literature. The obvious next question — *then what threshold should I use?* — had no
answer here, which made the result a complaint rather than a tool.

Conformal prediction answers it. Zhu et al. (`ACL 2025 <https://aclanthology.org/2025.acl-long.601/>`_)
make the argument for this field directly: "most existing detection methods focus excessively on
detection accuracy, often neglecting the societal risks posed by high false positive rates", and
conformal prediction "effectively constrains the upper bound of FPRs" — at a cost in detection
performance that their multiscale variant then works to recover.

The mechanism is one line of statistics and needs no model. Score ``n`` documents you *know* are
human, sort the scores, and take the ``ceil((n + 1)(1 - alpha))``-th smallest as the threshold. Under
exchangeability, a genuinely human document scores above it with probability at most ``alpha``. The
``n + 1`` is the finite-sample correction and it is the whole difference between a guarantee and a
guess: the plain ``(1 - alpha)`` quantile of the calibration set under-covers on small samples,
which is exactly the regime an institution calibrating on its own corpus is in.

**Ties break the bound, and ``calibration_fpr`` is how you see it.** The guarantee assumes
continuous scores. A detector that returns coarse or repeated values — several documents at exactly
0.5 — can flag more than ``alpha`` of the calibration set, because ``>= threshold`` catches the whole
tie. The returned ``calibration_fpr`` is the *realised* rate on the calibration data, so a caller can
compare it against the ``alpha`` they asked for instead of assuming they got it.

**What the guarantee does and does not say.** It bounds false positives on text drawn like the
calibration set. It says nothing about detection power — a threshold that flags nothing satisfies it
perfectly — so :func:`calibrate` reports how much of the calibration set it would still flag, and
returns ``None`` when the sample is too small to support the requested ``alpha`` at all rather than
returning a number that looks authoritative and guarantees nothing.

    >>> calibrate([0.1, 0.2, 0.15, 0.3, 0.05], alpha=0.2) is None  # five documents buy nothing
    True
    >>> human_scores = [i / 100 for i in range(1, 21)]  # twenty is the floor for any alpha
    >>> calibrate(human_scores, alpha=0.2)['threshold']  # 17th smallest: ceil(21 * 0.8)
    0.17
"""

from __future__ import annotations

import functools
import math

# Below this, no alpha is meaningfully supportable and the arithmetic starts returning thresholds
# that guarantee nothing. Stated rather than silently produced: ceil((n+1)(1-alpha)) exceeds n
# whenever n < 1/alpha - 1, so alpha=0.01 needs 99 samples before it means anything at all.
MIN_CALIBRATION = 20


def required_samples(alpha: float) -> int:
    """Smallest calibration set for which ``alpha`` is achievable at all.

    ``ceil((n + 1)(1 - alpha)) <= n`` requires ``n >= 1 / alpha - 1``. Below that the conformal
    threshold is +infinity — the only way to bound the false-positive rate that hard is to flag
    nothing — and a caller asking for 1% control with 40 documents deserves to be told that rather
    than handed a threshold.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    return max(MIN_CALIBRATION, math.ceil(1.0 / alpha - 1.0))


def _beta_cdf(x: float, a: int, b: int) -> float:
    """``P(Beta(a, b) <= x)``, for integer shapes, via the binomial identity.

    ``P(Beta(a, b) <= x) = sum_{k=a}^{a+b-1} C(a+b-1, k) x^k (1-x)^(a+b-1-k)``. Summed in log space
    because ``a + b`` here is a calibration-set size — 6,810 in this repo's own corpus — and the
    binomial coefficients overflow a float long before that.
    """
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    m = a + b - 1
    log_x, log_1x = math.log(x), math.log1p(-x)
    log_m = math.lgamma(m + 1)
    terms = [log_m - math.lgamma(k + 1) - math.lgamma(m - k + 1) + k * log_x + (m - k) * log_1x
             for k in range(a, m + 1)]
    peak = max(terms)
    return min(1.0, math.exp(peak) * sum(math.exp(t - peak) for t in terms))


def _beta_quantile(p: float, a: int, b: int) -> float:
    """Inverse of :func:`_beta_cdf` by bisection. Monotone, so 60 halvings suffice."""
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if _beta_cdf(mid, a, b) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


@functools.lru_cache(maxsize=256)
def _coverage_spread_cached(n: int, alpha: float) -> tuple[tuple[str, float], ...] | None:
    """Backing store for :func:`coverage_spread`.

    The distribution depends on ``n`` and ``alpha`` alone, and the closed form costs about
    half a second at this repo's own corpus size — enough that recomputing it inside a loop
    over calibration sets dominates the loop. Cached as a tuple of pairs so the dict handed
    to callers is theirs to mutate.
    """
    if n < required_samples(alpha):
        return None
    rank = math.ceil((n + 1) * (1.0 - alpha))
    if rank > n:
        return None
    a, b = n + 1 - rank, rank
    return (
        ("n_calibration", n),
        ("alpha", alpha),
        ("mean", a / (a + b)),
        ("median", _beta_quantile(0.5, a, b)),
        ("p5", _beta_quantile(0.05, a, b)),
        ("p95", _beta_quantile(0.95, a, b)),
        ("exceeds_alpha", 1.0 - _beta_cdf(alpha, a, b)),
    )


def coverage_spread(n: int, alpha: float = 0.05) -> dict | None:
    """What a threshold calibrated on ``n`` documents will *actually* do on new ones.

    **This is the number the conformal guarantee does not give you, and the one callers assume it
    does.** The split-conformal bound is marginal: it says the false-positive rate is at most
    ``alpha`` *averaged over calibration sets*. Conditional on the particular set you calibrated on —
    the only one you have — the realised rate is a random quantity, ``Beta(n + 1 - rank, rank)``
    distributed, whose mean is ``alpha`` and which therefore lands above ``alpha`` roughly half the
    time.

    That is not a defect and not a broken calibration. It is what "bounded in expectation" means, and
    it has a consequence nobody states: **a larger calibration set does not make you less likely to
    exceed alpha.** ``exceeds_alpha`` converges to ~50%, not to zero. What shrinks is the *amount* by
    which you exceed it — the p5-p95 band — which is the property actually worth buying more data for.

    MEASURED against 400 random splits of this repo's 6,810 pre-LLM abstracts, the closed form below
    reproduces the simulation: at n = 599 it predicts a median realised rate of 4.95% and a 47.8%
    chance of exceeding 5%, against 4.96% and 49.2% measured.

        >>> spread = coverage_spread(599, alpha=0.05)
        >>> round(spread['median'], 4)
        0.0495
        >>> spread['exceeds_alpha'] > 0.4
        True

    Returns ``None`` for an ``n`` that cannot support ``alpha`` at all, matching :func:`calibrate`.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    cached = _coverage_spread_cached(n, alpha)
    return None if cached is None else dict(cached)


def calibrate(human_scores: list[float], alpha: float = 0.05) -> dict | None:
    """Threshold bounding the false-positive rate at ``alpha`` on human-like text.

    ``human_scores`` must come from documents known to be human — ``eval/pre_llm_fpr.py`` builds
    such a corpus from pre-2022 publications, where the ground truth cannot be disputed.

    Returns ``None`` when the sample cannot support ``alpha``; see :func:`required_samples`.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    scores = sorted(float(s) for s in human_scores)
    n = len(scores)
    if n < required_samples(alpha):
        return None
    rank = math.ceil((n + 1) * (1.0 - alpha))
    if rank > n:  # defensive: required_samples() should already have excluded this
        return None
    threshold = scores[rank - 1]
    # How much of the calibration set this threshold still flags. A bound is not worth anything if
    # the caller cannot see what it cost, and the honest failure mode of FPR control is a threshold
    # so high it never fires.
    retained = sum(1 for s in scores if s >= threshold)
    return {
        "threshold": round(threshold, 4),
        "alpha": alpha,
        "n_calibration": n,
        "rank": rank,
        "calibration_flagged": retained,
        "calibration_fpr": round(retained / n, 4),
        # What this threshold will do on documents it has not seen. `calibration_fpr` is the rate on
        # the data that produced the threshold and is therefore optimistic by construction; this is
        # the honest one. See coverage_spread() for why it straddles alpha rather than sitting under
        # it.
        "expected_fpr": coverage_spread(n, alpha),
    }


def calibrate_by_length(
    samples: list[tuple[int, float]], alpha: float = 0.05, bands: tuple[int, ...] = (0, 50, 100, 200)
) -> dict:
    """Per-length-band thresholds, because one threshold across all lengths is one average.

    This repo measured 30.0% false positives at 50 words or fewer against 21.7% at 50-100 on the
    same corpus and detector. A single threshold set on the mixture is too strict for long documents
    and too loose for short ones, and it is short documents where a wrong verdict is least
    recoverable.

    ``samples`` are ``(word_count, score)`` pairs from known-human text. Bands with too few samples
    report ``None`` rather than an unsupported threshold.
    """
    edges = list(bands) + [10**9]
    out: dict[str, dict | None] = {}
    for low, high in zip(edges, edges[1:]):
        scores = [s for words, s in samples if low <= words < high]
        label = f"{low}-{high}" if high < 10**9 else f"{low}+"
        out[label] = calibrate(scores, alpha) if scores else None
    return out
