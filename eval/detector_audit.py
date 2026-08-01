"""Audit every detector for silent-failure modes — the check that would have caught a dead detector.

`fast_detectgpt` shipped with logistic calibration constants inherited from the paper
(``_CAL_MID = 1.0``) that sat entirely outside the range its scoring model actually produces. It
squashed **every** input to ~0.30 regardless of content: a detector contributing no signal to the
ensemble, which then looked like an "immovable wall" in the ceiling measurements. Nothing about the
code looked wrong. Only measuring its output against known-human and known-AI text exposed it.

This module makes that measurement a first-class, repeatable check. For each detector it scores a
fixed set of human-written and AI-style paragraphs and classifies the result:

``DEAD``
    Output range < ``MIN_RANGE`` across wildly different inputs — the detector emits a constant and
    contributes nothing. This is the ``fast_detectgpt`` failure.
``INVERTED``
    Human text scores materially *higher* than AI text — the sign or label convention is backwards,
    so the detector actively misleads the loop.
``WEAK``
    Responds and points the right way, but the distributions do not separate. Not a bug; a genuine
    limitation worth knowing about.
``OK``
    Responds and separates in the correct direction.

``DEAD`` and ``INVERTED`` are real bugs. ``WEAK`` is information.

    untell-detector-audit            # human-readable table
    untell-detector-audit --json     # machine-readable
"""

from __future__ import annotations

import argparse
import json

# Run-as-file support: put the package parent on sys.path when executed directly.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

# A detector whose output varies by less than this across the probe set is emitting a constant.
MIN_RANGE = 0.05
# A gap this negative means human text scores higher than AI text — the convention is backwards.
INVERT_GAP = -0.05
# Below this the detector responds but does not meaningfully separate the two classes.
WEAK_GAP = 0.05

# Human-written prose: specific, uneven, incidental detail. Deliberately NOT "polished".
HUMAN_PROBES = [
    "I went to the store yesterday and forgot my wallet again. Third time this month.",
    "My grandmother kept every letter my grandfather sent during the war, tied with brown string.",
    "The bus was late so I walked. Rain the whole way. My shoes are still wet by the radiator.",
    "He never did learn to swim properly, just sort of thrashed until he got where he was going.",
    "We argued about the thermostat for six years and then she moved out and I set it wherever.",
]

# Formulaic AI-style prose: the genre these detectors are trained to catch.
AI_PROBES = [
    "Furthermore, artificial intelligence has fundamentally transformed numerous industries.",
    "In today's rapidly evolving digital landscape, cybersecurity has become paramount.",
    "Climate change represents one of the most pressing challenges of our time.",
    "Moreover, organizations increasingly leverage these technologies to optimize efficiency.",
    "It is important to note that a comprehensive strategy is essential for sustainable success.",
]

# (key, module path, class name) for every locally-runnable detector.
_SPECS = [
    ("perplexity_burstiness", "untell.detectors.perplexity_burstiness", "PerplexityBurstinessDetector"),
    ("roberta_openai", "untell.detectors.roberta_openai", "RobertaOpenAIDetector"),
    ("hc3_roberta", "untell.detectors.hc3_roberta", "HC3RobertaDetector"),
    ("fast_detectgpt", "untell.detectors.fast_detectgpt", "FastDetectGPTDetector"),
    ("mage", "untell.detectors.mage", "MageDetector"),
]


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def audit_detector(name: str, det) -> dict:
    """Score the probe sets through one detector and classify its behaviour."""
    try:
        if not det.available():
            return {"detector": name, "verdict": "UNAVAILABLE"}
    except Exception as exc:
        return {"detector": name, "verdict": f"AVAIL_ERR:{type(exc).__name__}"}

    try:
        human = [det.score(t) for t in HUMAN_PROBES]
        ai = [det.score(t) for t in AI_PROBES]
    except Exception as exc:
        # A detector that cannot load is excluded from the ensemble, which is correct behaviour —
        # report it rather than treating it as a defect.
        return {"detector": name, "verdict": f"SCORE_ERR:{type(exc).__name__}"}

    human = [x for x in human if isinstance(x, (int, float))]
    ai = [x for x in ai if isinstance(x, (int, float))]
    if not human or not ai:
        return {"detector": name, "verdict": "RETURNED_NONE"}

    hm, am = _mean(human), _mean(ai)
    gap = am - hm
    rng = max(human + ai) - min(human + ai)

    if rng < MIN_RANGE:
        verdict = "DEAD"
    elif gap < INVERT_GAP:
        verdict = "INVERTED"
    elif gap < WEAK_GAP:
        verdict = "WEAK"
    elif min(ai) > max(human):
        verdict = "OK_SEPARATED"
    else:
        verdict = "OK"

    return {
        "detector": name,
        "verdict": verdict,
        "human_mean": round(hm, 4),
        "ai_mean": round(am, 4),
        "gap": round(gap, 4),
        "range": round(rng, 4),
    }


def audit_all() -> dict:
    """Audit every locally-runnable detector. ``broken`` lists the ones that are real bugs."""
    rows = []
    for key, module, cls in _SPECS:
        try:
            mod = __import__(module, fromlist=[cls])
            rows.append(audit_detector(key, getattr(mod, cls)()))
        except Exception as exc:
            rows.append({"detector": key, "verdict": f"IMPORT_ERR:{type(exc).__name__}"})
    broken = [r["detector"] for r in rows if r["verdict"] in ("DEAD", "INVERTED")]
    return {"results": rows, "broken": broken}


def render(report: dict) -> str:
    lines = [
        f"{'detector':24} {'verdict':14} {'human':>7} {'ai':>7} {'gap':>7} {'range':>7}",
        "-" * 72,
    ]
    for r in report["results"]:
        if "human_mean" not in r:
            lines.append(f"{r['detector']:24} {r['verdict']:14}")
        else:
            lines.append(
                f"{r['detector']:24} {r['verdict']:14} {r['human_mean']:7.3f} "
                f"{r['ai_mean']:7.3f} {r['gap']:+7.3f} {r['range']:7.3f}"
            )
    lines.append("")
    if report["broken"]:
        lines.append(f"BROKEN (dead or inverted): {', '.join(report['broken'])}")
    else:
        lines.append("BROKEN: none — every available detector responds in the correct direction.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="untell-detector-audit", description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the full report as JSON")
    args = parser.parse_args(argv)

    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()
    report = audit_all()
    print(json.dumps(report, ensure_ascii=True, indent=2) if args.json else render(report))
    return 1 if report["broken"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
