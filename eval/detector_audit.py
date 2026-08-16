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
import re

# Run-as-file support: put the package parent on sys.path when executed directly.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

from untell.scripts.score import DEFAULT_THRESHOLD  # noqa: E402  (after the sys.path shim above)

# A detector whose output varies by less than this across the probe set is emitting a constant.
MIN_RANGE = 0.05
# A gap this negative means human text scores higher than AI text — the convention is backwards.
INVERT_GAP = -0.05
# Below this the detector responds but does not meaningfully separate the two classes.
WEAK_GAP = 0.05
# AUROC below this is an inverted detector; below WEAK_AUROC it responds but barely separates.
INVERT_AUROC = 0.45
WEAK_AUROC = 0.65
# Fraction of HUMAN documents a detector may flag at the default threshold before the calibration
# is the problem rather than the discrimination. A tool that tells people their own writing is
# machine-generated is worse than useless to them, and the ensemble takes `max`, so one badly-scaled
# detector sets the floor for every tier that includes it. 20% is generous — the two detectors this
# check was added for were sitting at 92% and 32% with AUROC 0.999+.
MAX_FPR = 0.20

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


# --- sentence granularity -----------------------------------------------------------------------
# `sentences.py` scores each sentence IN ISOLATION to decide which spans to rewrite, so a detector
# can be healthy on paragraphs and broken on the input it is actually fed there. That is not
# hypothetical: perplexity_burstiness measured AUROC 0.000 on these exact probes — perfectly
# inverted — while passing the paragraph audit, because burstiness is undefined for one sentence
# and the fallback term was calibrated backwards for modern AI prose. Per-sentence targeting was
# therefore aimed at whichever sentences read most human, and nothing detected it.
# A sentence row counts as broken only at or below this AUROC. Chance is 0.5 on 36 pairs; a real
# inversion of the kind found in perplexity_burstiness scored 0.000. Anything between is reported
# for information but must not fail a build.
SENTENCE_BROKEN_AUROC = 0.20

# Cap on sentences drawn per class when --pairs derives them from the labelled corpus. 30 gives
# 900 pairs for the AUROC — ample to tell 0.5 from 0.9, which is the distinction these verdicts
# turn on — against 36 pairs from the packaged probes.
#
# Kept deliberately low because runtime here is dominated by `local_judge` at ~3.7s per call, so
# every extra probe costs two of those. Raising it buys precision this audit does not need.
_MAX_SENTENCE_PROBES = 30

SENTENCE_HUMAN_PROBES = [
    "I went to the store and forgot the milk again.",
    "The build broke because someone bumped the pinned version.",
    "She said it was fine, but her face said otherwise.",
    "We tried it twice and it still didn't work.",
    "Turns out the cable was loose the whole time.",
    "He emailed me back three days later with one line.",
]
SENTENCE_AI_PROBES = [
    "Furthermore, artificial intelligence has fundamentally transformed numerous industries.",
    "Moreover, organizations increasingly leverage these technologies to optimize efficiency.",
    "This robust framework enables stakeholders to seamlessly navigate complex challenges.",
    "In today's rapidly evolving landscape, businesses must delve into innovative solutions.",
    "It is important to note that this underscores the importance of robust solutions.",
    "Additionally, this serves as a testament to the transformative power of innovation.",
]


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


_WHITESPACE_RUN = re.compile(r"\s+")
_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def collapse_layout(text: str) -> str:
    """Put both halves of a corpus on one layout convention: every whitespace run becomes a space.

    Line breaks are how a corpus was *stored*, not how its text was written. Collapsing them is what
    stops a paired measurement scoring the scrape instead of the prose — see `layout_shortcut`.
    """
    return _WHITESPACE_RUN.sub(" ", text).strip()


def _layout_only_auroc(human: list[str], ai: list[str]) -> float | None:
    """AUROC reachable from newline density alone — the words discarded entirely.

    This is the ceiling a detector could hit on this corpus without reading anything. Near 0.5 means
    layout carries no class information and the corpus is safe to score as supplied. Near 1.0 (or
    near 0.0, which is the same shortcut pointing the other way) means it is not.
    """
    if not human or not ai:
        return None

    def density(t: str) -> float:
        return 1000 * t.count("\n") / max(len(_WORD_RE.findall(t)), 1)

    au = auroc([density(t) for t in ai], [density(t) for t in human])
    return None if au is None else max(au, 1 - au)


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

    # What the USER experiences is `max >= threshold`, not a ranking. AUROC is threshold-free and
    # therefore blind to a detector that separates the classes perfectly while reporting them on a
    # scale that puts ordinary human writing over the line. Two detectors shipped exactly that and
    # this audit called both healthy at AUROC 0.999+ the whole time:
    #   fast_detectgpt          human mean 0.510, 92% of human documents flagged
    #   perplexity_burstiness   human mean 0.244, 32% flagged
    # Both were fixed by moving a logistic midpoint; neither moved AUROC by more than 0.001.
    fpr = sum(1 for x in human if x >= DEFAULT_THRESHOLD) / len(human)
    tpr = sum(1 for x in ai if x >= DEFAULT_THRESHOLD) / len(ai)

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
    elif fpr > MAX_FPR:
        # Separation is fine; the scale is not. Distinct from WEAK on purpose — the fix is a
        # calibration constant, not a better detector.
        verdict = "MISCALIBRATED"
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
        "fpr": round(fpr, 4),
        "tpr": round(tpr, 4),
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
    layout_shortcut = None
    if pairs > 0:
        from eval.datasets import load_pairs

        loaded = load_pairs(dataset, pairs)
        if loaded:
            # Layout is collapsed on BOTH halves before anything is scored.
            #
            # MEASURED, and this is not a precaution: on RAID, newline density ALONE — every word
            # discarded, the count of "\n" per 1,000 words used as the entire score — separates the
            # two halves at AUROC 1.0000. A detector that reads nothing and counts line breaks is
            # perfect on this corpus. RAID's human documents are hard-wrapped scrapes (84.52 single
            # newlines per 1,000 words) and its machine continuations are unwrapped (2.79); double
            # newlines run 0.00 against 14.50. That is how the corpus was assembled, not a way that
            # human writing differs from machine writing, and real assistant output is full of
            # blank lines.
            #
            # With a perfect shortcut available, an AUROC over as-supplied text cannot be claimed to
            # measure authorship — it can only be an upper bound. What the detectors actually took
            # from it was smaller than that ceiling implies, which is worth recording because it is
            # the reassuring direction and was not guaranteed (60 pairs):
            #
            #     perplexity_burstiness   1.0000 -> 0.9983
            #     roberta_openai          0.9406 -> 0.8875   <- the one that leaned on it
            #     hc3_roberta             0.9975 -> 0.9881
            #     mage                    1.0000 -> 1.0000
            #     fast_detectgpt          1.0000 -> 1.0000
            #
            # so the published RAID figures were inflated by up to 0.053 rather than fabricated.
            #
            # This is applied to every corpus rather than special-cased to RAID, because RAID is not
            # the only one affected and the collapse is provably free where it is not needed:
            #
            #     layout-only AUROC   RAID 1.0000   HC3 0.9667   MAGE 0.5000
            #
            # HC3 carries nearly the same shortcut (its ChatGPT half is newline-formatted, its human
            # half is not) though no detector took more than 0.0017 from it. MAGE is clean at chance,
            # and there the collapse moves all five detectors by exactly 0.0000 — which is the
            # evidence that this cannot damage a corpus that did not need it.
            #
            # `layout_shortcut` below reports the ceiling for whichever corpus is in use, so a
            # future corpus with the same defect announces itself instead of being trusted.
            human_raw = [h for h, _ in loaded]
            ai_raw = [a for _, a in loaded]
            layout_shortcut = _layout_only_auroc(human_raw, ai_raw)
            probes = (
                [collapse_layout(h) for h in human_raw],
                [collapse_layout(a) for a in ai_raw],
            )
            source = f"{dataset} labelled pairs (n={len(loaded)}, layout collapsed)"
        else:
            source = f"{dataset} unavailable — fell back to packaged probes"

    rows = []
    for key, module, cls in _SPECS:
        try:
            mod = __import__(module, fromlist=[cls])
            rows.append(audit_detector(key, getattr(mod, cls)(), probes))
        except Exception as exc:
            rows.append({"detector": key, "verdict": f"IMPORT_ERR:{type(exc).__name__}"})
    # Audit the same detectors on single sentences.
    #
    # With --pairs, DERIVE the sentence probes from the same labelled corpus rather than falling
    # back to the six hand-written ones. The label carries over — a sentence lifted from a ChatGPT
    # answer is machine-written — and this is exactly how the 0.915 / 0.995 figures cited above
    # were obtained. Without it, `--pairs 60` produced a report whose paragraph rows rested on 60
    # labelled pairs while its sentence rows still rested on 6 hand-written probes, and the flag
    # that exists to turn this into a real measurement silently covered only half the table.
    #
    # Sentences under 10 words are dropped: the lite heuristic returns no signal below five, and
    # short fragments are where the small-sample false alarms above came from.
    sentence_probes = (SENTENCE_HUMAN_PROBES, SENTENCE_AI_PROBES)
    if probes is not None:
        from untell.text_split import split_sentences

        def _sentences_from(paragraphs: list[str]) -> list[str]:
            out: list[str] = []
            for para in paragraphs:
                out += [s for s in split_sentences(para) if len(s.split()) >= 10]
            return out[:_MAX_SENTENCE_PROBES]

        derived = (_sentences_from(probes[0]), _sentences_from(probes[1]))
        if len(derived[0]) >= 10 and len(derived[1]) >= 10:
            sentence_probes = derived
    for key, module, cls in _SPECS:
        try:
            mod = __import__(module, fromlist=[cls])
            row = audit_detector(key, getattr(mod, cls)(), sentence_probes)
        except Exception as exc:
            row = {"detector": key, "verdict": f"IMPORT_ERR:{type(exc).__name__}"}
        row["detector"] = f"{key} [sentence]"
        row["granularity"] = "sentence"
        rows.append(row)

    # Sentence rows are held to a STRICTER bar before counting as broken, because six probes per
    # class is 36 pairs and an AUROC near 0.5 is chance, not evidence.
    #
    # MEASURED, after this audit first called fast_detectgpt "INVERTED" on these probes (AUROC
    # 0.444): re-run on 40 human + 40 AI sentences taken from real HC3 pairs, fast_detectgpt scores
    # 0.915 and hc3_roberta 0.995+. Both are healthy at sentence granularity; the verdict was a
    # small-sample false alarm, and gating CI on it would have turned the build red over noise.
    # perplexity_burstiness's real defect scored 0.000 on the same probes — a perfect inversion,
    # which 36 pairs cannot produce by chance. That is the gap this bar is set to catch.
    # MISCALIBRATED counts as broken at paragraph granularity: the detector works, but at the
    # threshold the product actually uses it flags human writing, and `max` aggregation spreads
    # that to every tier containing it. Sentence rows are excluded for the same small-sample reason
    # as below — a handful of short probes is not evidence about a false-positive rate.
    broken = [
        r["detector"]
        for r in rows
        if r["verdict"] in ("DEAD", "INVERTED", "MISCALIBRATED")
        and (
            r.get("granularity") != "sentence"
            or r.get("auroc") is None
            or r["auroc"] <= SENTENCE_BROKEN_AUROC
        )
    ]
    return {
        "results": rows,
        "broken": broken,
        "source": source,
        "layout_shortcut": (
            round(layout_shortcut, 4) if layout_shortcut is not None else None
        ),
    }


# Above this, layout alone separates the corpus well enough that an as-supplied AUROC would be
# measuring the scrape. RAID sits at 1.0000. Layout is always collapsed, so this is a statement
# about the corpus rather than a caveat on the numbers below — but a reader comparing these figures
# with someone else's, taken over raw text, needs to know the two are not the same measurement.
LAYOUT_SHORTCUT_WARN = 0.70


def render(report: dict) -> str:
    shortcut = report.get("layout_shortcut")
    lines = [
        f"probe set: {report.get('source', 'packaged probes')}",
    ]
    if shortcut is not None:
        note = "" if shortcut < LAYOUT_SHORTCUT_WARN else "  <- layout alone nearly separates this corpus"
        lines.append(f"layout-only AUROC (newline density, no words): {shortcut:.4f}{note}")
    lines += [
        "",
        f"{'detector':24} {'verdict':14} {'AUROC':>7} {'human':>7} {'ai':>7} {'gap':>7} "
        f"{'FPR':>6} {'TPR':>6}",
        "-" * 88,
    ]
    for r in report["results"]:
        if "human_mean" not in r:
            lines.append(f"{r['detector']:24} {r['verdict']:14}")
        else:
            au = f"{r['auroc']:7.3f}" if r.get("auroc") is not None else "      -"
            # FPR/TPR at the default threshold, alongside AUROC. AUROC alone is threshold-free and
            # cannot see a detector that ranks correctly but reports on a scale that flags most
            # human writing — which is what two of these were doing at AUROC 0.999+.
            fpr = f"{r['fpr']:6.0%}" if r.get("fpr") is not None else "     -"
            tpr = f"{r['tpr']:6.0%}" if r.get("tpr") is not None else "     -"
            lines.append(
                f"{r['detector']:24} {r['verdict']:14} {au} {r['human_mean']:7.3f} "
                f"{r['ai_mean']:7.3f} {r['gap']:+7.3f} {fpr} {tpr}"
            )
    lines.append("")
    # Sentence rows with a bad verdict but an AUROC above the small-sample bar are EXCLUDED from
    # `broken` on purpose — see the comment beside that list. Saying so here is the point: the
    # table printed `fast_detectgpt [sentence]  INVERTED  0.444` directly above
    # "every available detector responds in the correct direction", and a reader cannot reconcile
    # those two lines without opening the source. The summary was true of its own computation and
    # misleading beside the data it summarises.
    excused = [
        r["detector"]
        for r in report["results"]
        if r.get("granularity") == "sentence"
        and r["verdict"] in ("DEAD", "INVERTED", "MISCALIBRATED")
        and r.get("auroc") is not None
        and r["auroc"] > SENTENCE_BROKEN_AUROC
    ]
    if report["broken"]:
        # The label must name what is actually in the list. MISCALIBRATED is a real member
        # (mage ships that way on HC3), and printing "dead or inverted" beside a table whose
        # mage row says MISCALIBRATED is the same summary-contradicts-table defect the
        # footnote below was written to prevent.
        if any(r.get("verdict") == "MISCALIBRATED" for r in report["results"]
               if r["detector"] in report["broken"]):
            lines.append(f"BROKEN (dead, inverted, or miscalibrated): {', '.join(report['broken'])}")
        else:
            lines.append(f"BROKEN (dead or inverted): {', '.join(report['broken'])}")
    else:
        lines.append("BROKEN: none — every available detector responds in the correct direction.")
    if excused:
        # The probe count the bar is justified by must be the count this run actually used.
        # With the packaged probes that is six per class (36 pairs); with --pairs the sentence
        # probes are DERIVED from the labelled corpus (up to _MAX_SENTENCE_PROBES per class),
        # so "six probes per class is 36 pairs" printed beside a table whose sentence rows
        # show n=30 is a contradiction the reader cannot resolve without opening the source.
        n = next(
            (r.get("n") for r in report["results"]
             if r.get("granularity") == "sentence" and r.get("n")),
            None,
        )
        if n is not None and n > len(SENTENCE_HUMAN_PROBES):
            lines.append(
                f"  Not counted: {', '.join(excused)} — a bad verdict at sentence granularity "
                f"needs AUROC <= {SENTENCE_BROKEN_AUROC} to count, and the small-sample bar was "
                f"set for six probes per class. These probes were DERIVED from the labelled "
                f"corpus ({n} per class, {n * n} pairs), so the verdicts above are real "
                "measurements at sentence granularity, not 36-pair noise."
            )
        else:
            lines.append(
                f"  Not counted: {', '.join(excused)} — a bad verdict at sentence granularity needs "
                f"AUROC <= {SENTENCE_BROKEN_AUROC} to count, because six probes per class is 36 pairs "
                "and a value near chance is noise. Re-measured on 40 real HC3 sentence pairs, these "
                "score 0.9+."
            )
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
