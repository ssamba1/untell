"""Sweep the numbers `lite_score` is built from, on the corpus that produced this repo's headline.

Rounds eighty-six and eighty-seven each swept one unchosen parameter in the literature survey and
found the conclusion robust. This asks the same question of something far more load-bearing.

**Every published figure in this repository is a function of five numbers that nobody defended, and
four of them are not even named constants.** `lite_score` ends:

    common_signal = clamp01((common - 0.30) / 0.30)
    burst_signal  = clamp01((0.55 - burst) / 0.55)
    return clamp01(max(rep, 0.6 * burst_signal + 0.4 * common_signal))

They are named constants now — `_COMMON_MID`, `_COMMON_SCALE`, `_BURST_MID`, `_BURST_SCALE`,
`_BURST_WEIGHT` — and this module imports them rather than restating them, so a change to the
detector cannot leave the sweep measuring numbers the detector no longer uses. Naming them changed
no score: MEASURED, 6,912 documents scored under both trees, 0 differ.

The 30.4% false-positive rate, the AUROC 0.3529 inversion, the register finding of round
eighty-eight — all of them are that expression evaluated on a corpus. A census of module-level
constants (`eval/constant_census.py`) cannot see any of these, because they are inline literals in
an expression rather than assignments. That is not a gap in the census; it is the reason a census
alone is not enough.

**The sweep is affordable because scoring is separated from featurising.** `features()` runs the
detector's own helpers once per document; `score_from()` rebuilds the score arithmetically under any
parameters. So a six-dimensional sweep costs one pass over the corpus rather than one pass per
setting — the same move that made round eighty-eight's third cut possible, applied harder.

`score_from(features(t), DEFAULTS)` is asserted equal to `lite_score(t)` for every document before
any sweep runs. Without that gate this module would be measuring a reimplementation, which is
exactly the defect round eighty-four found and round eighty-eight repeated.

⚠️ **This sweep reports AUROC 0.3538 at the shipped values, and the repository's published figure is
0.3529. Both are right and the difference is not drift.** Round eighty-four established it: 0.3529
is `score_text`, the shipped detector, and 0.3538 is `lite_score`, the function underneath it —
`score_text` adds clamping and a `max` across detectors. This module sweeps `lite_score`'s own
constants, so `lite_score` is the correct level to measure at, and MEASURED on these same arms the
two differ by 9 parts in 10,000. **Quote 0.3529 for the detector and 0.3538 only for this sweep.**
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, replace
from pathlib import Path

from untell.detectors.perplexity_burstiness import (
    _BURST_MID,
    _BURST_SCALE,
    _BURST_WEIGHT,
    _COMMON_MID,
    _COMMON_SCALE,
    _MIN_WORDS_FOR_SIGNAL,
    _WORD,
    _burstiness,
    _common_ratio,
    _repetition_signal,
    _sentences,
    _single_sentence_signal,
    clamp01,
    lite_score,
)


@dataclass(frozen=True)
class Params:
    """The five numbers in `lite_score`'s final expression, named for the first time.

    `burst_weight` and its complement are one parameter, not two: they are written `0.6` and `0.4`
    in the source and must sum to one, and letting them drift apart would change the score's range
    rather than its shape.
    """

    common_mid: float = _COMMON_MID
    common_scale: float = _COMMON_SCALE
    burst_mid: float = _BURST_MID
    burst_scale: float = _BURST_SCALE
    burst_weight: float = _BURST_WEIGHT


DEFAULTS = Params()


@dataclass(frozen=True)
class Features:
    """Everything `lite_score` derives from the text, extracted once."""

    words: int
    sentences: int
    rep: float
    common: float
    burst: float
    single: float | None


def features(text: str) -> Features | None:
    """The detector's own helpers, run once. None where `lite_score` returns None."""
    if not text or not text.strip():
        return None
    if len(_WORD.findall(text)) < _MIN_WORDS_FOR_SIGNAL:
        return None
    sents = _sentences(text)
    nonempty = [s for s in sents if _WORD.findall(s)]
    common = _common_ratio(text)
    single = None
    if len(nonempty) < 2:
        # `_single_sentence_signal` takes the mapped common signal as its fallback, so it has to be
        # recomputed per parameter set rather than cached. Store the raw text's contribution by
        # calling it at the default and again at sweep time; here we only note the branch.
        single = -1.0
    return Features(
        words=len(_WORD.findall(text)),
        sentences=len(nonempty),
        rep=_repetition_signal(text),
        common=common,
        burst=_burstiness(sents) if len(nonempty) >= 2 else 0.0,
        single=single,
    )


def score_from(feat: Features, params: Params = DEFAULTS, text: str | None = None) -> float:
    """`lite_score`'s arithmetic, with its five numbers supplied instead of written in.

    Mirrors the shipped function branch for branch, including the single-sentence path — which is
    not a detail: that branch was the subject of its own correction (a "neutral" 0.5 that put every
    single-sentence input exactly on the decision threshold), and a sweep that quietly skipped it
    would be sweeping a different function from the one that ships.
    """
    common_signal = clamp01((feat.common - params.common_mid) / params.common_scale)
    if feat.sentences < 2:
        if text is None:
            raise ValueError("single-sentence scoring needs the text")
        return clamp01(max(feat.rep, _single_sentence_signal(text, common_signal)))
    burst_signal = clamp01((params.burst_mid - feat.burst) / params.burst_scale)
    blended = params.burst_weight * burst_signal + (1.0 - params.burst_weight) * common_signal
    return clamp01(max(feat.rep, blended))


def auroc(machine: list[float], human: list[float]) -> float:
    """P(a machine document outranks a human one), ties counted as half.

    Above 0.5 means the detector orders the arms correctly. Below 0.5 means it is pointed the wrong
    way — which is what this corpus produces, and the thing the sweep is asking about.
    """
    if not machine or not human:
        return 0.5
    wins = sum(
        1.0 if m > h else 0.5 if m == h else 0.0
        for m in machine
        for h in human
    )
    return wins / (len(machine) * len(human))


def verify_reimplementation(texts: list[str], limit: int | None = 400) -> dict:
    """`score_from(features(t), DEFAULTS)` must equal `lite_score(t)`. Everything else depends on it."""
    checked = mismatched = 0
    worst = 0.0
    example = None
    for text in texts[:limit] if limit else texts:
        feat = features(text)
        shipped = lite_score(text)
        if feat is None or shipped is None:
            if (feat is None) != (shipped is None):
                mismatched += 1
                example = example or text[:80]
            continue
        mine = score_from(feat, DEFAULTS, text=text)
        checked += 1
        gap = abs(mine - shipped)
        if gap > worst:
            worst = gap
        if gap > 1e-9:
            mismatched += 1
            example = example or text[:80]
    return {"checked": checked, "mismatched": mismatched, "worst_gap": worst,
            "example": example, "faithful": mismatched == 0}


# One-at-a-time sweeps around each shipped value. Deliberately wide: the question is not "is the
# score stable under jitter" — of course it is — but "does the repository's headline finding depend
# on a number nobody chose", and only a wide range can answer that.
SWEEPS: dict[str, tuple[float, ...]] = {
    "common_mid": (0.10, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50),
    "common_scale": (0.10, 0.20, 0.30, 0.40, 0.50, 0.70),
    "burst_mid": (0.35, 0.45, 0.55, 0.65, 0.75, 0.90),
    "burst_scale": (0.25, 0.40, 0.55, 0.70, 0.90),
    "burst_weight": (0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
}


def _scored(arm: list[tuple[Features, str]], params: Params) -> list[float]:
    return [score_from(f, params, text=t) for f, t in arm]


def sweep(machine: list[tuple[Features, str]], human: list[tuple[Features, str]],
          threshold: float = 0.45) -> dict:
    """Every parameter varied one at a time, reporting AUROC and both arms' flag rates.

    AUROC is the headline because it is threshold-free: a parameter that shifts every score up
    changes both flag rates and no ordering, and reporting only rates would read that as an
    improvement. Round seventy-seven made exactly that mistake and had to retract it, so the flag
    rates are reported beside the AUROC rather than instead of it.
    """
    base = {
        "auroc": round(auroc(_scored(machine, DEFAULTS), _scored(human, DEFAULTS)), 4),
        "machine_flag_rate": None,
        "human_flag_rate": None,
    }
    m0, h0 = _scored(machine, DEFAULTS), _scored(human, DEFAULTS)
    base["machine_flag_rate"] = round(100.0 * sum(s >= threshold for s in m0) / len(m0), 1)
    base["human_flag_rate"] = round(100.0 * sum(s >= threshold for s in h0) / len(h0), 1)

    out: dict[str, list[dict]] = {}
    for name, values in SWEEPS.items():
        rows = []
        for value in values:
            params = replace(DEFAULTS, **{name: value})
            ms, hs = _scored(machine, params), _scored(human, params)
            rows.append({
                "value": value,
                "shipped": value == getattr(DEFAULTS, name),
                "auroc": round(auroc(ms, hs), 4),
                "machine_flag_rate": round(100.0 * sum(s >= threshold for s in ms) / len(ms), 1),
                "human_flag_rate": round(100.0 * sum(s >= threshold for s in hs) / len(hs), 1),
            })
        out[name] = rows

    inverted = [
        {"parameter": name,
         "shipped_auroc": next(r["auroc"] for r in rows if r["shipped"]),
         "best_auroc": max(r["auroc"] for r in rows),
         "worst_auroc": min(r["auroc"] for r in rows),
         "any_above_half": any(r["auroc"] > 0.5 for r in rows)}
        for name, rows in out.items()
    ]
    return {
        "n_machine": len(machine),
        "n_human": len(human),
        "threshold": threshold,
        "base": base,
        "sweeps": out,
        "summary": inverted,
        "inversion_survives_every_setting": not any(s["any_above_half"] for s in inverted),
    }


def build_arms(cache: Path, limit: int | None = None,
               min_words: int = 40, max_words: int = 100) -> tuple[list, list]:
    """The same two arms as `eval/detection_power.py`, featurised once.

    Length-matched on both sides, because the machine arm tops out near 220 words and an unbounded
    human arm would make this a comparison of length rather than of authorship — `eval/arms.py`.
    """
    from eval.data.generated_abstracts import ABSTRACTS
    from eval.pre_llm_fpr import pre_llm_abstracts

    def featurise(texts: list[str]) -> list[tuple[Features, str]]:
        out = []
        for text in texts:
            flat = " ".join(text.split())
            if not min_words <= len(flat.split()) < max_words:
                continue
            feat = features(flat)
            if feat is not None:
                out.append((feat, flat))
        return out

    human_texts = pre_llm_abstracts(cache, min_words=min_words, max_year=2021)
    if limit:
        human_texts = human_texts[:limit]
    return featurise(list(ABSTRACTS)), featurise(human_texts)


def render(report: dict) -> str:
    base = report["base"]
    lines = [
        f"machine {report['n_machine']}  human {report['n_human']}  "
        f"threshold {report['threshold']}",
        f"shipped: AUROC {base['auroc']:.4f}  machine flags {base['machine_flag_rate']}%  "
        f"human flags {base['human_flag_rate']}%",
        "",
    ]
    for name, rows in report["sweeps"].items():
        lines.append(f"{name}")
        lines.append(f"  {'value':>8} {'AUROC':>8} {'machine%':>9} {'human%':>8}")
        for row in rows:
            mark = " <- shipped" if row["shipped"] else ""
            lines.append(f"  {row['value']:>8.2f} {row['auroc']:>8.4f} "
                         f"{row['machine_flag_rate']:>8.1f}% {row['human_flag_rate']:>7.1f}%{mark}")
        lines.append("")
    if report["inversion_survives_every_setting"]:
        lines.append(
            "The inversion is not a calibration artefact: NO setting of any of these five numbers\n"
            "brings the AUROC above 0.5. The detector is pointed the wrong way on this register for\n"
            "reasons the constants cannot reach.")
    else:
        culprits = [s["parameter"] for s in report["summary"] if s["any_above_half"]]
        lines.append(
            f"⚠️ The inversion DOES depend on a constant nobody chose: {', '.join(culprits)}.\n"
            "Some setting of it puts the AUROC above 0.5, so the headline finding is a statement\n"
            "about this calibration and not about the detector. Read round eighty-nine of\n"
            "docs/research-verification.md before quoting the inversion again.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path(".anthology-cache"))
    parser.add_argument("--limit", type=int, help="cap the human arm for a fast run")
    parser.add_argument("--threshold", type=float, default=0.45)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    if not args.cache.exists() or not any(args.cache.glob("*.xml")):
        print(f"no volume XML in {args.cache} — run `python -m eval.litreview --download` first",
              file=sys.stderr)
        return 1

    machine, human = build_arms(args.cache, limit=args.limit)
    check = verify_reimplementation([t for _, t in machine] + [t for _, t in human], limit=None)
    if not check["faithful"]:
        print(f"REFUSING TO SWEEP: score_from disagrees with lite_score on "
              f"{check['mismatched']} of {check['checked']} documents "
              f"(worst gap {check['worst_gap']:.2e}). Fix score_from first — a sweep over a "
              f"reimplementation measures the reimplementation.", file=sys.stderr)
        return 1

    report = sweep(machine, human, threshold=args.threshold)
    report["faithfulness"] = check
    print(json.dumps(report, indent=2) if args.as_json else render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
