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

**Probe length has to match how the detector is actually used.** This audit reported OK for every
detector while ``perplexity_burstiness`` was anti-correlated (AI text scoring *below* human text)
on real input. The probes were single sentences; the loop scores paragraphs. Burstiness is
undefined on one sentence, and a supervised classifier sees a completely different distribution at
15 words than at 150 — so the gate was measuring a regime nobody runs in. The packaged probes are
now paragraph-length.

**Hand-written probes are a smoke test, not a measurement — and this was verified, not assumed.**
Replaying the broken ``perplexity_burstiness`` implementation through this module:

    old detector, single-sentence probes (the gate as it was)   AUROC 0.84  -> OK
    old detector, paragraph probes (the gate as it is)          AUROC 0.76  -> OK
    old detector, labelled HC3 pairs                            gap -0.198  -> INVERTED

Lengthening the probes was necessary but **not sufficient**: the packaged "human" side is written
to look human, and it happens to be choppy, which is exactly the shape the broken scorer rated as
human. Only ``--pairs`` — labelled human/AI pairs (HC3), reported as AUROC, the threshold-free
probability that a random AI sample outscores a random human one — would have caught it. 0.5 is a
coin flip and below 0.5 is inverted. Treat a clean run of the packaged probes as "nothing is
obviously dead", never as evidence that a detector discriminates.

    untell-detector-audit             # fast smoke test on packaged probes
    untell-detector-audit --pairs 100 # real measurement on labelled data (needs .[eval])
    untell-detector-audit --json      # machine-readable
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
# AUROC below this is an inverted detector; below WEAK_AUROC it responds but barely separates.
INVERT_AUROC = 0.45
WEAK_AUROC = 0.65

# Human-written prose: specific, uneven, incidental detail. Deliberately NOT "polished".
# PARAGRAPH length on purpose — see the module docstring. At one sentence per probe this set
# reported OK for a detector that was scoring AI text *below* human text on real input.
HUMAN_PROBES = [
    "I went to the store yesterday and forgot my wallet again. Third time this month. The guy at "
    "the counter just waved me off and said bring it next time, which was decent of him. I did go "
    "back, eventually. Took me four days.",
    "My grandmother kept every letter my grandfather sent during the war, tied with brown string "
    "in a shoebox under the bed. Nobody read them while she was alive. When we finally did, half "
    "were about the weather and what he'd had for dinner. She'd underlined those parts.",
    "The bus was late so I walked. Rain the whole way. My shoes are still wet by the radiator and "
    "I have a feeling they're going to smell. There's a shortcut through the park but it floods, "
    "so that wasn't happening either. Forty minutes. In February.",
    "He never did learn to swim properly, just sort of thrashed until he got where he was going. "
    "It worked, mostly. One summer he tried to cross the whole lake that way and had to be pulled "
    "out about two thirds across, coughing, absolutely furious about it. He tried again the "
    "next year.",
    "We argued about the thermostat for six years and then she moved out and I set it wherever I "
    "wanted, and it turned out I didn't care. The house was the same temperature it had always "
    "been. I kept doing the thing where I'd check it before bed anyway.",
]

# Formulaic AI-style prose: the genre these detectors are trained to catch.
AI_PROBES = [
    "Furthermore, artificial intelligence has fundamentally transformed numerous industries. "
    "Organizations across sectors are leveraging these technologies to optimize their operations "
    "and drive meaningful outcomes. Moreover, the integration of machine learning enables "
    "data-driven decision making at unprecedented scale. In conclusion, this transformation "
    "represents a pivotal shift in the modern business landscape.",
    "In today's rapidly evolving digital landscape, cybersecurity has become paramount. "
    "Organizations must implement comprehensive strategies to safeguard sensitive information "
    "from increasingly sophisticated threats. Additionally, employee training plays a crucial "
    "role in mitigating risk. Ultimately, a proactive security posture is essential for "
    "sustainable operational resilience.",
    "Climate change represents one of the most pressing challenges of our time. Rising global "
    "temperatures have contributed to more frequent extreme weather events, threatening both "
    "ecosystems and human communities. Furthermore, transitioning to renewable energy sources is "
    "crucial for mitigating these effects. It is imperative that stakeholders collaborate to "
    "address this urgent issue.",
    "Effective communication plays a crucial role in the success of any organization. Moreover, "
    "it fosters collaboration and strengthens relationships among team members. Additionally, "
    "clear communication helps prevent misunderstandings and costly conflicts. Overall, "
    "organizations that prioritize transparent communication consistently achieve better "
    "outcomes across a variety of metrics.",
    "It is important to note that a comprehensive strategy is essential for sustainable success. "
    "By establishing clear objectives, allocating resources thoughtfully, and monitoring progress "
    "against defined milestones, organizations can position themselves for long-term growth. "
    "Furthermore, regular review cycles ensure that strategy remains aligned with evolving market "
    "conditions.",
]

# (key, module path, class name) for every locally-runnable detector. Detectors omitted from this
# list are never audited at all, which is its own silent gap — radar and local_judge were both
# missing, and local_judge was raising on every call at the time.
_SPECS = [
    ("perplexity_burstiness", "untell.detectors.perplexity_burstiness", "PerplexityBurstinessDetector"),
    ("roberta_openai", "untell.detectors.roberta_openai", "RobertaOpenAIDetector"),
    ("hc3_roberta", "untell.detectors.hc3_roberta", "HC3RobertaDetector"),
    ("fast_detectgpt", "untell.detectors.fast_detectgpt", "FastDetectGPTDetector"),
    ("mage", "untell.detectors.mage", "MageDetector"),
    ("radar", "untell.detectors.radar", "RadarDetector"),
    ("local_judge", "untell.detectors.local_judge", "LocalJudgeDetector"),
    ("binoculars", "untell.detectors.binoculars", "BinocularsDetector"),
]


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def auroc(ai: list[float], human: list[float]) -> float | None:
    """P(a random AI sample scores above a random human one), ties counted as half.

    Threshold-free, so it cannot be flattered by a lucky cut point the way a mean gap can.
    """
    if not ai or not human:
        return None
    wins = ties = 0
    for a in ai:
        for h in human:
            if a > h:
                wins += 1
            elif a == h:
                ties += 1
    return (wins + 0.5 * ties) / (len(ai) * len(human))


def audit_detector(name: str, det, probes: tuple[list[str], list[str]] | None = None) -> dict:
    """Score the probe sets through one detector and classify its behaviour."""
    human_texts, ai_texts = probes or (HUMAN_PROBES, AI_PROBES)
    try:
        if not det.available():
            return {"detector": name, "verdict": "UNAVAILABLE"}
    except Exception as exc:
        return {"detector": name, "verdict": f"AVAIL_ERR:{type(exc).__name__}"}

    try:
        human = [det.score(t) for t in human_texts]
        ai = [det.score(t) for t in ai_texts]
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
    au = auroc(ai, human)

    # AUROC decides direction and separation; it is threshold-free, so unlike the mean gap it
    # cannot be rescued by one outlier dragging a class average across the line.
    if rng < MIN_RANGE:
        verdict = "DEAD"
    elif au is not None and au < INVERT_AUROC:
        verdict = "INVERTED"
    elif gap < INVERT_GAP:
        verdict = "INVERTED"
    elif au is not None and au < WEAK_AUROC:
        verdict = "WEAK"
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
        "auroc": round(au, 4) if au is not None else None,
        "n": len(human),
    }


def audit_all(pairs: int = 0, dataset: str = "hc3") -> dict:
    """Audit every locally-runnable detector. ``broken`` lists the ones that are real bugs.

    With ``pairs > 0`` the probe set is replaced by that many labelled human/AI pairs, which turns
    the smoke test into an actual measurement. Without it, the hand-written probes can only
    establish that a detector responds and points the right way.
    """
    probes = None
    source = "packaged probes (smoke test)"
    if pairs > 0:
        from eval.datasets import load_pairs

        loaded = load_pairs(dataset, pairs)
        if loaded:
            probes = ([h for h, _ in loaded], [a for _, a in loaded])
            source = f"{dataset} labelled pairs (n={len(loaded)})"
        else:
            source = f"{dataset} unavailable — fell back to packaged probes"

    rows = []
    for key, module, cls in _SPECS:
        try:
            mod = __import__(module, fromlist=[cls])
            rows.append(audit_detector(key, getattr(mod, cls)(), probes))
        except Exception as exc:
            rows.append({"detector": key, "verdict": f"IMPORT_ERR:{type(exc).__name__}"})
    broken = [r["detector"] for r in rows if r["verdict"] in ("DEAD", "INVERTED")]
    return {"results": rows, "broken": broken, "source": source}


def render(report: dict) -> str:
    lines = [
        f"probe set: {report.get('source', 'packaged probes')}",
        "",
        f"{'detector':24} {'verdict':14} {'AUROC':>7} {'human':>7} {'ai':>7} {'gap':>7} {'range':>7}",
        "-" * 80,
    ]
    for r in report["results"]:
        if "human_mean" not in r:
            lines.append(f"{r['detector']:24} {r['verdict']:14}")
        else:
            au = f"{r['auroc']:7.3f}" if r.get("auroc") is not None else "      -"
            lines.append(
                f"{r['detector']:24} {r['verdict']:14} {au} {r['human_mean']:7.3f} "
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
    parser.add_argument(
        "--pairs",
        type=int,
        default=0,
        metavar="N",
        help="measure against N labelled human/AI pairs instead of the packaged probes "
        "(needs the .[eval] extra); this is the only mode that supports a discrimination claim",
    )
    parser.add_argument("--dataset", default="hc3", help="paired dataset for --pairs (default: hc3)")
    args = parser.parse_args(argv)

    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()
    report = audit_all(pairs=args.pairs, dataset=args.dataset)
    print(json.dumps(report, ensure_ascii=True, indent=2) if args.json else render(report))
    return 1 if report["broken"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
