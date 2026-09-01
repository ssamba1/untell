"""Make two corpora's false-positive rates comparable by holding document length constant.

Rounds thirty-six and thirty-seven established that **length is the dominant nuisance variable** in
every false-positive comparison this project makes. Detectors flag short text far more often —
MEASURED here, **30.0% at <=50 words against 13.3% at 200+** — so a corpus of short answers and a
corpus of theses get different false-positive rates from the same detector at the same threshold,
before anything about their authors is considered. Round thirty-six is what happens when that is
ignored: an outlier gap that separated its intervals at five of seven cut-offs on 6,810 documents
turned out to be length.

Epidemiology solved this problem a century ago and the answer is **direct standardization**. Crude
mortality is higher in Florida than in Alaska because Florida is older, not because Florida is
dangerous; age-standardizing removes the composition difference and leaves the part worth comparing.
This module does the same with word counts.

**What it is for.** A program director comparing their flag rate against a published one is comparing
two corpora with different length profiles, and the difference between "our applicants are flagged
more than the study's" and "our applicants write shorter statements than the study's" is the whole
question. This says which.

**What it cannot do.** Standardizing removes the length composition difference and nothing else. Two
corpora matched on length can still differ by domain, generator, editing history, prompt and
aggregation rule — the other five terms this repository insists a false-positive rate depends on.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from eval.pre_llm_fpr import LENGTH_BANDS, _band, pre_llm_abstracts, wilson_interval


def length_profile(texts: list[str]) -> dict[str, float]:
    """What share of a corpus falls in each word-count band."""
    counts: dict[str, int] = {_band(low): 0 for low, _ in LENGTH_BANDS}
    for text in texts:
        words = len(text.split())
        for low, high in LENGTH_BANDS:
            if low <= words < high:
                counts[_band(low)] += 1
                break
    total = sum(counts.values())
    return {band: (n / total if total else 0.0) for band, n in counts.items()}


def standardize(band_rates: dict[str, dict], profile: dict[str, float]) -> dict:
    """Apply one corpus's band-specific rates to another corpus's length profile.

    The result answers: *if our detector behaved on your documents the way it behaves on ours, band
    for band, what false-positive rate would your corpus see?* Any remaining difference between that
    and your crude rate is not length.

    Bands with no measured rate are dropped and the profile is renormalised over what is left, with
    `coverage` reporting how much of the corpus that accounted for — a standardized rate computed
    over 40% of a corpus is not a rate, and the caller has to be able to see that.
    """
    usable = {b: w for b, w in profile.items()
              if b in band_rates and band_rates[b].get("fpr") is not None}
    coverage = sum(usable.values())
    if coverage <= 0:
        return {"standardized_fpr": None, "coverage": 0.0,
                "error": "no band in this corpus has a measured rate"}
    expected = sum(w / coverage * band_rates[b]["fpr"] for b, w in usable.items())
    return {
        "standardized_fpr": round(expected, 4),
        "coverage": round(coverage, 4),
        "bands_used": sorted(usable),
        "bands_dropped": sorted(set(profile) - set(usable)),
    }


def rates_by_natural_length(texts: list[str], tier: str = "lite") -> dict[str, dict]:
    """Band rates on documents scored WHOLE, each assigned to the band its own length falls in.

    Deliberately not `pre_llm_fpr.probe_by_length`, which truncates every abstract to the top of
    every band it reaches, so a 150-word abstract contributes a scored sample to 0-50, 50-100 AND
    100-200. That is the right design for its question — *how does this detector behave as length
    varies, holding the text fixed* — and the wrong one here. Standardization weights band rates by
    the share of documents whose NATURAL length falls in each band, so the rates have to come from
    the same population the weights describe.

    Mixing the two is not a subtle error: it inflated the first version of this module's crude rate
    to 20.4% against a standardized 11.2% on two halves of ONE corpus, which should agree.
    """
    from untell.scripts.score import score_text

    bands: dict[str, list[int]] = {}
    for text in texts:
        words = len(text.split())
        band = next((_band(low) for low, high in LENGTH_BANDS if low <= words < high), None)
        if band is None:
            continue
        result = score_text(text, tier=tier)
        if not result.get("agreement"):
            continue
        bands.setdefault(band, []).append(int(bool(result["flagged"])))

    out = {}
    for band, hits in bands.items():
        low, high = wilson_interval(sum(hits), len(hits))
        out[band] = {"flagged": sum(hits), "n": len(hits),
                     "fpr": round(sum(hits) / len(hits), 4) if hits else None,
                     "ci95": [round(low, 4), round(high, 4)]}
    return out


def compare(reference: list[str], target: list[str], tier: str = "lite") -> dict:
    """Crude against length-standardized, for a target corpus measured on reference band rates."""
    reference_rates = rates_by_natural_length(reference, tier=tier)
    target_rates = rates_by_natural_length(target, tier=tier)

    crude_hits = sum(r["flagged"] for r in target_rates.values())
    crude_n = sum(r["n"] for r in target_rates.values())
    low, high = wilson_interval(crude_hits, crude_n)
    profile = length_profile(target)
    result = standardize(reference_rates, profile)
    crude = round(crude_hits / crude_n, 4) if crude_n else None
    return {
        "tier": tier,
        "reference_bands": reference_rates,
        "target_profile": profile,
        "crude_fpr": crude,
        "crude_ci95": [round(low, 4), round(high, 4)],
        "crude_n": crude_n,
        **result,
        # The number the whole module exists to produce.
        "length_explains": (
            None if crude is None or result.get("standardized_fpr") is None
            else round(crude - result["standardized_fpr"], 4)
        ),
        "note": (
            "Standardizing removes the length composition difference and nothing else. Two corpora "
            "matched on length can still differ by domain, generator, editing history, prompt and "
            "aggregation rule."
        ),
    }



def decompose_length_gap(
    samples: list[tuple[int, float]], threshold: float,
    short: tuple[int, int] = (0, 100), long: tuple[int, int] = (200, 10**9),
) -> dict | None:
    """How much of the short-vs-long flag gap is a shifted mean, and how much is a wider spread.

    The distinction decides the fix. **Extra variance** at short lengths means the detector cannot
    tell, and the honest response is abstention — say so and score nothing. **A shifted mean** means
    it can tell and is systematically wrong, and the response is a per-length threshold, because the
    signal is there and the bar is in the wrong place.

    Two counterfactuals on the short band, one variable at a time: give it the long band's mean while
    keeping its own spread, then its spread while keeping its own mean. Whichever closes more of the
    gap is the mechanism.

    MEASURED on all 6,810 pre-LLM abstracts at the shipped verdict threshold of 0.45 — 60-100 words
    against 200+, a gap of 15.92 points:

        matching the mean    28.69% -> 15.75%   closes **81%** of the gap
        matching the spread  28.69% -> 25.04%   closes 23%
        matching both        28.69% -> 13.60%   against a long-band 12.77%

    **It is the mean.** Short human text is not scored more noisily, it is scored more
    machine-like — so `untell.calibrate.calibrate_by_length` is the right answer and abstention is
    not. The two closures sum past 100% because the effects are not additive; together they close
    95%.

    ⚠️ One detector, one corpus, one register. The mechanism is not claimed beyond that.

    Returns ``None`` when either band is too small to have a spread.
    """
    lows = [s for words, s in samples if short[0] <= words < short[1]]
    highs = [s for words, s in samples if long[0] <= words < long[1]]
    if len(lows) < 2 or len(highs) < 2:
        return None
    mean_low, sd_low = statistics.mean(lows), statistics.pstdev(lows)
    mean_high, sd_high = statistics.mean(highs), statistics.pstdev(highs)
    if sd_low == 0:
        return None

    def rate(values: list[float]) -> float:
        return sum(v >= threshold for v in values) / len(values)

    observed, reference = rate(lows), rate(highs)
    gap = observed - reference
    as_mean = rate([(v - mean_low) + mean_high for v in lows])
    as_spread = rate([(v - mean_low) * (sd_high / sd_low) + mean_low for v in lows])
    both = rate([(v - mean_low) * (sd_high / sd_low) + mean_high for v in lows])
    share = lambda counterfactual: (  # noqa: E731
        round((observed - counterfactual) / gap, 4) if gap else None)
    return {
        "threshold": threshold,
        "short": {"n": len(lows), "mean": round(mean_low, 4), "sd": round(sd_low, 4),
                  "flagged": round(observed, 4)},
        "long": {"n": len(highs), "mean": round(mean_high, 4), "sd": round(sd_high, 4),
                 "flagged": round(reference, 4)},
        "gap": round(gap, 4),
        "matching_mean": {"flagged": round(as_mean, 4), "closes": share(as_mean)},
        "matching_spread": {"flagged": round(as_spread, 4), "closes": share(as_spread)},
        "matching_both": {"flagged": round(both, 4), "closes": share(both)},
        # The name of the fix this implies, so a caller does not have to reason it out.
        "mechanism": ("mean shift — use a per-length threshold"
                      if (observed - as_mean) > (observed - as_spread)
                      else "variance — abstain rather than threshold"),
    }

def _render(report: dict) -> str:
    lines = [
        f"Length-standardized false positives (tier={report['tier']}).",
        "",
        f"{'band':<12} {'reference FPR':>14} {'target share':>13}",
    ]
    for band, share in report["target_profile"].items():
        ref = report["reference_bands"].get(band, {}).get("fpr")
        lines.append(f"{band:<12} {(f'{ref:.1%}' if ref is not None else '—'):>14} {share:>12.1%}")
    crude = report["crude_fpr"]
    std = report.get("standardized_fpr")
    lines += ["", f"crude          {crude:.1%}" if crude is not None else "crude          —"]
    lines.append(f"standardized   {std:.1%}" if std is not None else "standardized   —")
    if report.get("coverage", 0) < 0.9:
        lines.append(f"WARNING: only {report['coverage']:.0%} of the corpus fell in a band with a "
                     f"measured rate — this standardized figure is not a rate for the whole corpus.")
    if report.get("length_explains") is not None:
        lines += ["", f"difference attributable to length composition: "
                      f"{report['length_explains']:+.1%}"]
    lines += ["", report["note"]]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cache", type=Path, default=Path(".anthology-cache"))
    parser.add_argument("--tier", default="lite")
    parser.add_argument("--n", type=int, default=200, help="documents per corpus")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    texts = pre_llm_abstracts(args.cache)
    if len(texts) < 2 * args.n:
        print(f"need {2 * args.n} pre-LLM abstracts, have {len(texts)} — run "
              f"`python -m eval.litreview --download` first", file=sys.stderr)
        return 1
    # Split the corpus in half: the reference supplies band rates, the target is standardized
    # against them. Two halves of one corpus SHOULD agree, which makes this a self-check as well as
    # a demonstration — a large gap here would mean the band rates are unstable, not that length
    # explains anything.
    report = compare(texts[: args.n], texts[args.n: 2 * args.n], tier=args.tier)
    print(json.dumps(report, indent=2) if args.as_json else _render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
