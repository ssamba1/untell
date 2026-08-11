"""Humanness score — a unified 0-100 metric combining AI-tells + detector scores.

A single number that answers "how human does this text read?" by fusing:

* **AI-tells density** (from ``score_tells``) — mechanical markers per 100 words.
* **Detector ensemble max** (from ``score_text``) — the hardest detector's P(AI).
* **Burstiness** — sentence-length coefficient of variation.

The formula::

    humanness = 100 - (w_tells * normalized_tells + w_detector * detector_max + w_bursty * bursty_penalty)

Bands recalibrated 2026-08-07 against HC3 **and** RAID: on 80 pairs at the full tier the classes
are fully separable (lowest human 75.6, highest AI 72.0), so the human/AI boundary sits at 75. See
:func:`classification` for the measurement and the failure it fixes.

Usage::

    from untell.humanness import humanness

    score = humanness("Your text here")  # e.g. 73
    print(f"Humanness: {score}/100")
"""

from __future__ import annotations

import logging
import re

from untell.scripts.score import score_text
from untell.scripts.tells import score_tells

logger = logging.getLogger(__name__)

# Weights for the three signal components (sum ≈ 1.0).
_W_TELLS = 0.30       # AI-tells density contribution
_W_DETECTOR = 0.50    # Detector ensemble contribution (strongest weight)
_W_BURSTY = 0.20      # Burstiness / sentence-length variation

# Calibration constants.
_MAX_TELLS_PER_100W = 25.0  # Approximate ceiling for tells/100w
_BURSTY_IDEAL = 0.70        # Ideal burstiness CV (high variation = human)
_MAX_BURSTY_PENALTY = 0.30  # Max penalty from low burstiness

# Below this word count none of the three signals carries information. Matches the detector's own
# `_MIN_WORDS_FOR_SIGNAL` in detectors/perplexity_burstiness.py, which abstains on the same grounds.
_MIN_WORDS_FOR_SIGNAL = 5
_WORD_RE = re.compile(r"[A-Za-z']+")
_WARNED_TOO_SHORT = False


def _warn_too_short() -> None:
    """Say once that the input was too short to score, rather than returning a confident number."""
    global _WARNED_TOO_SHORT
    if _WARNED_TOO_SHORT:
        return
    _WARNED_TOO_SHORT = True
    logger.warning(
        "text is shorter than %d words — humanness cannot be measured at that length and is "
        "reported as 50 (undetermined), not as a verdict.",
        _MIN_WORDS_FOR_SIGNAL,
    )


_WARNED_UNSUPPORTED_LANGUAGE = False


def _warn_unsupported_language() -> None:
    """Say the catalogue does not cover this script, rather than that the text is too short."""
    global _WARNED_UNSUPPORTED_LANGUAGE
    if _WARNED_UNSUPPORTED_LANGUAGE:
        return
    _WARNED_UNSUPPORTED_LANGUAGE = True
    logger.warning(
        "the text is mostly a script this English-only catalogue cannot match, so humanness is "
        "reported as 50 (undetermined) rather than as a verdict. See untell/languages.py for how "
        "a catalogue for another language would be registered."
    )


_WARNED_INVISIBLE = False


def _warn_about_invisibles(warning: str | None) -> None:
    """Pass through only the invisible-character caveat, once, and drop the rest."""
    global _WARNED_INVISIBLE
    if not warning or "invisible character" not in warning or _WARNED_INVISIBLE:
        return
    _WARNED_INVISIBLE = True
    # They no longer shift the score, which is what this used to say. Detector input is scrubbed, so
    # this number is now the number for the text a reader sees — measured identical at 90.8 with and
    # without a soft hyphen between every character. The caveat is still worth emitting, because the
    # characters are still IN the caller's text and every other tool they reach is unhardened: the
    # same paragraph took an external detector from 0.0002 to 0.7900 depending only on those bytes.
    logger.warning(
        "the text carries invisible characters. They do not move this score — detector input is "
        "scrubbed — but they are still in your text, and tools that do not scrub will read it "
        "differently. Run `untell scrub` to remove them, or `untell score` for the details."
    )


def humanness(text: str, tier: str = "full") -> float:
    """Return a humanness score in [0, 100] — higher = more human-like.

    Args:
        text: The text to evaluate.
        tier: Detector tier to use (default ``"full"``).

    Returns:
        Float in [0, 100]. **The bands are not tier-independent, and the number is not comparable
        across tiers.** Half the weight is the detector term and ``tier`` is what selects the
        detectors, so the same text moves bands on the flag alone. MEASURED on 6 real HC3 AI texts:
        lite gives mean 62.8 and calls all six "mostly human"; full gives mean 43.4 and calls all
        six "mixed". Always report the tier next to the score — the CLI does.

        **Nor is it comparable across LENGTHS**, which is the same caveat one axis over. MEASURED
        on 24 corpus texts of 220+ words, truncated to a series of windows and compared against
        their own 220-word score:

            window            60w    100w   140w   180w
            mean |delta|      8.9     7.3    5.1    2.5
            max  |delta|     21.1    23.4   22.8    9.4

        **15 of the 24 change BAND** somewhere across that range, and not only toward the answer
        more evidence would give: one human text reads "human" at 100 words and "mixed" at 220
        (79.7 -> 56.3), another goes "mixed" at 60 and "mostly human" at 220. So two documents of
        different lengths cannot be ranked against each other by this number, and the same document
        cannot be spot-checked on an excerpt.

        **50.0 is returned by abstention AND reachable by computation.** Empty text, text under
        ``_MIN_WORDS_FOR_SIGNAL`` and unreadable scripts all return a literal 50.0, and so does a
        text whose three terms happen to sum there — MEASURED on a 100-word HC3 answer with the
        detector ensemble at P(AI) = 0.9992, near-zero tells and healthy burstiness, returned as a
        dead tie. A caller holding the bare float cannot distinguish the two. Nothing shipped
        branches on ``== 50.0`` and ``tests/test_the_abstention_value_is_also_a_real_score.py``
        keeps it that way; the CLI reads the band, which is an honest "mixed" either way.

        The bands are the ones :func:`classification` actually implements, recalibrated
        2026-08-07 against HC3 and RAID (see that function for the measurement):
        - ≥ 75: human
        - 60–75: mostly human
        - 45–60: mixed
        - 30–45: likely AI
        - < 30: AI
    """
    if not text or not text.strip():
        return 50.0  # Neutral for empty text

    # Too short to score. MEASURED, without this guard:
    #     "Hello"     -> 100.0  "human"
    #     "It works." -> 100.0  "human"
    # Both at full confidence, from a headline command that advertises "how human does it read".
    # None of the three signals means anything at that length: burstiness needs two sentences, a
    # single tell would read as 100 per 100 words, and the detector already abstains below its own
    # `_MIN_WORDS_FOR_SIGNAL` — humanness was ignoring that abstention and scoring anyway.
    #
    # 50.0 is the same "cannot tell" answer empty text gets, and lands in the `mixed` band. That is
    # the honest reading: a confident 100 on one word is noise reported as certainty.
    if len(_WORD_RE.findall(text)) < _MIN_WORDS_FOR_SIGNAL:
        # Distinguish "too short" from "not English". `_WORD_RE` is [A-Za-z']+, so a 40-character
        # Chinese paragraph has zero words by this count and used to be reported as "shorter than 5
        # words" — true of the regex, absurd to the reader, and it points them at the wrong fix
        # (write more) instead of the real limit (the catalogue is English-only). Both answers are
        # 50, which is correct either way; only the reason was wrong.
        if not score_tells(text).get("language_supported", True):
            _warn_unsupported_language()
        else:
            _warn_too_short()
        return 50.0

    # 1. AI-tells signal
    tells_result = score_tells(text)
    tells_per_100w = tells_result.get("tells_per_100w", 0.0)
    # Normalize to [0, 1] where 0 = no tells (human), 1 = max tells (AI).
    normalized_tells = min(tells_per_100w / _MAX_TELLS_PER_100W, 1.0)

    # 2. Detector ensemble signal.
    #
    # `.get("max", 0.5)` could never fire: score_text ALWAYS returns a "max" key, and when nothing
    # scored that key is a 0.0 PLACEHOLDER — which reads as "no detector thinks this is AI" and,
    # at weight 0.50, lifted the humanness score by fifty points. A broken ML stack therefore
    # reported ordinary AI text as clearly human. score_text sets `scored: False` and a warning
    # for exactly this case; the fix is to read them.
    detector_result = score_text(text, tier=tier)
    # `humanness` returns a bare float, so every caveat `score_text` produced is discarded here.
    # Most of them are about the detector configuration and the caller can look them up. One is
    # not: invisible characters. They USED to move the detector component without changing anything
    # a reader can see — measured on a 37-word paragraph with a zero-width space between every
    # character, the score drifted 62.5 -> 64.8, upward, making the text look more human.
    #
    # That is fixed: detector input is scrubbed, and the same paragraph now measures 90.8 with and
    # without a soft hyphen between every character. The warning stays, with its wording corrected,
    # because the characters are still in the CALLER's text and every unhardened tool downstream
    # still reads them — the same text took an external detector from 0.0002 to 0.7900 on those
    # bytes alone. This surface returns a bare float, so a log line is the only channel it has.
    _warn_about_invisibles(detector_result.get("warning"))
    detector_scored = detector_result.get("scored") is not False
    detector_max = float(detector_result.get("max", 0.0)) if detector_scored else None
    if not detector_scored:
        logger.warning(
            "no detector produced a score, so the humanness number reflects only the mechanical "
            "signals (tells + burstiness) — treat it as weaker evidence, not a clean verdict."
        )

    # 3. Burstiness signal
    cv = tells_result.get("burstiness_cv")
    bursty_penalty = 0.0
    if cv is not None:
        # CV near 0.7 is ideal human prose; penalize both low (uniform) and
        # extremely high (erratic) burstiness, but low is the real tell.
        if cv < 0.35:
            bursty_penalty = _MAX_BURSTY_PENALTY  # uniform=AI tell
        elif cv < 0.50:
            bursty_penalty = _MAX_BURSTY_PENALTY * (0.50 - cv) / 0.15
        elif cv > 1.0:
            bursty_penalty = _MAX_BURSTY_PENALTY * 0.5  # erratic, but less penalized

    # 4. Composite. With no detector signal, its weight is REDISTRIBUTED across the signals that
    # did produce something rather than being scored as 0 — dropping a term whose weight is half
    # the total is not the same as that term reporting "human".
    #
    # KNOWN CALIBRATION GAP, measured on 30 labelled HC3 pairs. The blended score RANKS perfectly
    # (AUROC 1.000, human mean 89.2 vs AI mean 43.7 on the full tier) but the BANDS understate:
    # not one of thirty real ChatGPT samples reached "likely AI", and on the lite tier 27 of 30
    # landed in "mostly human". A user pasting obvious AI text is told it is mixed, or mostly human.
    #
    # The cause was read as signal quality. Per-signal AUROC as originally recorded:
    #     detector  1.000     (weight 0.50)
    #     bursty    0.896     (weight 0.25)
    #     tells     0.523     (weight 0.25)   <- chance; human 0.026 vs ai 0.023
    #
    # THAT DIAGNOSIS WAS AN ARTEFACT OF A BUG IN score_tells, now fixed. Its em-dash category was
    # counting a spaced hyphen inside space-tokenized compounds ("oscar - winning") and list
    # bullets, which fired 190 times on HC3's human side and 0 on its AI side — enough on its own
    # to flatten the whole term. Re-measured on 60 HC3 pairs after the fix:
    #     bursty    0.843     human mean 0.097  ai mean 0.268
    #     tells     0.789     human mean 0.100  ai mean 0.540
    # The tells term is not at chance and never was; it separates about as well as burstiness. It
    # also runs the other way from what the old note claimed: AI text now carries roughly five
    # times the catalogued tells of human text, so the term pushes AI text DOWN, as intended.
    #
    # RE-DERIVED 2026-08-10, because the figures above predate the two repetition tells and those
    # moved the catalogue hard (its overall AUROC went 0.638 -> 0.9555 on RAID for the same reason).
    # 60 pairs per corpus:
    #
    #                     HC3      RAID
    #     tells          0.890    0.935     human mean 0.029 / 0.035, ai mean 0.273 / 0.455
    #     bursty         0.856    0.791
    #
    # This does not just refresh a number, it reverses the ordering the paragraph above rests on.
    # "About as well as burstiness" was true at 0.789 against 0.843; the tells term now separates
    # BETTER than burstiness on both corpora, and by a wide margin on RAID. It is the second
    # strongest of the three signals and carries the same 0.25 weight as the weakest.
    #
    # Still not refitted, for the reason below, which the new numbers do not touch: choosing weights
    # against these corpora is fitting to 2022-era ChatGPT and to RAID's particular generators. What
    # changed is that the argument for leaving them alone can no longer include "tells is the weak
    # term" — it is not.
    #
    # BANDS NOW RECALIBRATED (2026-08-07) — the objection below was that refitting against one
    # dated corpus trades a real signal for a better benchmark number. That objection is answered:
    # the same failure replicated on RAID (multi-domain, multi-generator, exact pairing) with ai
    # mean 47.8 and 0/40 reaching "likely AI", against HC3's 43.4 and 0/60. Two corpora, two eras,
    # and AUROC 1.0000 on RAID — the score was right and the LABELS were wrong. See
    # :func:`classification`.
    #
    # The WEIGHTS are still not refitted, for the reason that survives. The bands
    # continue to understate — see the measurement above this comment — and raising the detector
    # weight to 0.70 would move AI into "likely AI" while leaving human in "human". That is fitting
    # three weights to one dated corpus: HC3 is 2022-era ChatGPT and predates most of the
    # vocabulary the catalogue targets ("delve", "tapestry", "leverage"). Doing it properly needs a
    # labelled sample of MODERN generated text; until then the gap stays documented, not tuned.
    weights = {"tells": _W_TELLS, "detector": _W_DETECTOR, "bursty": _W_BURSTY}
    parts = {"tells": normalized_tells, "bursty": bursty_penalty}
    if detector_max is not None:
        parts["detector"] = detector_max
    live = sum(weights[k] for k in parts) or 1.0
    ai_score = sum(weights[k] * v for k, v in parts.items()) / live
    # Clamp to [0, 1] then scale to [0, 100].
    human_score = max(0.0, min(1.0, 1.0 - ai_score))
    return round(human_score * 100.0, 1)


def classification(score: float) -> str:
    """Return a human-readable classification for a humanness score.

    RECALIBRATED 2026-08-07 against **two** corpora, which is what this module said it was waiting
    for. The old boundaries (80 / 55 / 35 / 15) were never fitted to anything, and measured on the
    full tier they never once produced an AI verdict about AI text:

        HC3,  n=60   ai mean 43.4   ->  0/60 reached "likely AI"
        RAID, n=40   ai mean 47.8   ->  0/40 reached "likely AI"

    Both times the ranking was perfect — AUROC 1.0000 on RAID — so the score was right and the
    LABELS were wrong. A user pasting obvious AI text was told "mixed".

    The classes turn out to be fully separable at the full tier. On 80 pairs across both corpora:

        lowest HUMAN score  75.6      highest AI score  72.0

    A boundary at 75 therefore misclassifies **0 of 80 in either direction**, and the bands below
    are placed around it rather than around round numbers. Measured against that same 80-pair set,
    75 of 80 AI texts now land in "mixed" or lower against 0 before.

    **THAT SEPARABILITY DOES NOT HOLD, and it was never a property of both corpora.** Re-measured
    2026-08-11 on the same protocol, 40 pairs each from HC3 and RAID:

        corpus   lowest HUMAN   highest AI   human below 75   AI at or above 75
        RAID          79.2         44.0           0 / 40            0 / 40
        HC3           41.0         44.0          14 / 40            0 / 40
        combined      41.0         44.0          14 / 80            0 / 80

    The claim survives on RAID and fails on HC3, where 35% of genuine human answers land below the
    boundary — in "mixed" or "likely AI". Worse than a moved boundary: at 41.0 against 44.0 the two
    ranges now OVERLAP, so no cut separates them and "fully separable" is not recoverable by
    retuning. Averaging the two corpora is what hid this; the combined minimum is HC3's alone.

    The boundary is NOT moved, for a reason worth stating. Every error is in one direction: no AI
    text reached 75 in either corpus (0 of 80), so nothing here calls AI writing human. What it does
    is decline to confirm a third of real HC3 answers as human, and the honest fix for that is a
    caveat rather than a cut that would start passing AI text to buy it back.

    Why HC3 and not RAID: HC3 human answers are short, conversational forum replies — the register
    this scale's own components read as least "human", since burstiness needs sentences and the tell
    catalogue fires on 7 of 20 categories there against 9 on RAID. Same lesson as the ceiling
    figures: a number measured across pooled corpora is not a number about either one.

    WHICH TERM IS RESPONSIBLE, decomposed over those same 40 HC3 human texts:

                        detector max   tells/100w   burstiness cv   words
        below 75 (14)       0.987         0.84          0.517        274
        at/above (26)       0.154         0.43          0.538        178

    The detector term is the entire difference — 6.4x apart, while burstiness is flat (0.517 against
    0.538) and both tell rates are near zero. So this scale mislabels human writing exactly when the
    detector ensemble false-positives on it, and nothing is wrong with the naturalness half. Anyone
    trying to fix the 35% should start at the ensemble's own false-positive rate (the README records
    40-42% of human text flagged at the full tier, driven by `mage`), not at these bands.

    The word counts differ too, but that is NOT a length effect: binned over the same texts, the
    flag rate is 11/23 under 150 words, 3/11 at 150-250, then 2/4 and 1/2 above. Non-monotonic, and
    the upper bins are too small to carry a claim. Recorded so the 274-against-178 above is not read
    as one.

    Scoped to the FULL tier, deliberately. The lite tier compresses the range (its own scores flag
    57-65% of human text at the shipped detector threshold — see the tier table in the README), so
    a lite score sits higher than a full one for the same text. That is why the CLI prints the tier
    next to the verdict.
    """
    if score >= 75:
        return "human"
    if score >= 60:
        return "mostly human"
    if score >= 45:
        return "mixed"
    if score >= 30:
        return "likely AI"
    return "AI"


def _dominant_signal(text: str, tier: str) -> str | None:
    """Name the signal that moved the score most, in words a reader can act on.

    The score is a blend of three things and the CLI printed only the total, so a passage of
    genuinely human writing could come back "46.6/100 (mixed)" with nothing to indicate why or
    whether to believe it. The components are already computed; withholding them turns a
    diagnosable result into an opaque verdict.

    A worked case, and the reason this exists — the same three sentences, rewritten with varied
    sentence lengths and nothing else changed:

        "The kettle boiled while I read the last few pages. Rain had started again and the
         window fogged at the corners. I put the book down and went to find a coat."
            burstiness cv 0.044  ->  46.6  "mixed"

        same content, uneven rhythm
            burstiness cv 1.003  ->  90.3  "human"

    Nothing about the first passage is machine-written, and the number is not wrong either: three
    sentences of near-identical length is the uniform rhythm the burstiness term exists to catch.
    But "46.6, mixed" invites the reader to conclude their writing looks synthetic, where
    "uniform sentence rhythm" tells them what the measurement actually saw.

    Returns None when nothing stands out, rather than inventing an explanation.
    """
    # Uses the module-level imports rather than re-importing locally: the local copies shadowed the
    # names, so a caller could not substitute them and the "never breaks the command" guarantee
    # below was untestable.
    try:
        tells = score_tells(text)
        cv = tells.get("burstiness_cv")
        per_100w = tells.get("tells_per_100w") or 0.0
        detector_max = (score_text(text, tier=tier) or {}).get("max")
    except Exception:  # noqa: BLE001 — an explanation must never break the command
        return None

    if not tells.get("language_supported", True):
        return ("the tell catalogue is English-only and this text is mostly another script, "
                "so the mechanical half of this score saw nothing")

    # Rank by what the reader can DO about it, not by raw contribution.
    #
    # Two wrong versions preceded this one. A first-match ladder reported "uniform sentence rhythm"
    # for a passage stuffed with delve / tapestry / Moreover, because that test happened to sit at
    # the top. Ranking by contribution instead put the detector term first on every input — it
    # carries half the weight, so it usually wins — and "the detector says 0.78" tells a reader
    # nothing they can act on.
    #
    # The tells and rhythm terms are actionable: remove the phrases, vary the sentence lengths. The
    # detector term is not, so it is reported only when neither of the others is doing real work —
    # and in that case it IS the useful message, because "reads clean and still scores as machine-
    # written" is exactly the situation a tell catalogue cannot explain.
    actionable: list[tuple[float, str]] = []

    if cv is not None:
        if cv < 0.35:
            penalty = _MAX_BURSTY_PENALTY
        elif cv < 0.50:
            penalty = _MAX_BURSTY_PENALTY * (0.50 - cv) / 0.15
        elif cv > 1.0:
            penalty = _MAX_BURSTY_PENALTY * 0.5
        else:
            penalty = 0.0
        if penalty > 0:
            shape = "uniform" if cv < _BURSTY_IDEAL else "erratic"
            actionable.append((
                penalty * _W_BURSTY,
                f"driven by {shape} sentence rhythm (burstiness {cv:.2f}; human prose sits near "
                f"{_BURSTY_IDEAL:.2f}) — varying sentence length changes this more than word "
                f"choice does",
            ))

    if per_100w > 0:
        worst = max(tells.get("by_category", {}).items(), key=lambda kv: kv[1], default=None)
        named = f", mostly {worst[0]}" if worst else ""
        actionable.append((
            min(per_100w / _MAX_TELLS_PER_100W, 1.0) * _W_TELLS,
            f"driven by {per_100w:.1f} AI tells per 100 words{named}",
        ))

    # 0.02 of the blended score. Below that the term is not moving the number enough to be worth
    # naming, and naming it anyway puts a confident-sounding cause on a result that is just middling.
    strong = [c for c in actionable if c[0] >= 0.02]
    if strong:
        return max(strong, key=lambda c: c[0])[1]

    if detector_max is not None and detector_max >= 0.5:
        return (f"driven by the detector ensemble ({detector_max:.2f} max) rather than by any "
                f"catalogued tell — nothing mechanical to fix here, which is the honest answer "
                f"rather than a to-do list")
    return None


def main(argv: list[str] | None = None) -> int:
    """CLI: ``untell humanness \"text\"`` → JSON with humanness score and classification."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    import argparse
    import json
    import sys

    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()
    parser = argparse.ArgumentParser(
        prog="untell-humanness",
        description="Score text 0-100: how human does it read? (combines tells + detectors)",
    )
    parser.add_argument("text", nargs="?", help="text to score")
    parser.add_argument("--file", "-f", help="read text from this file")
    # Derived from the loader's own table, not restated. The hand-written list here omitted
    # "commercial", so `untell-humanness --tier commercial` exited 2 while every other CLI accepted
    # it and `humanness(text, tier="commercial")` worked from Python — this function passes the tier
    # straight to score_text, which has always supported it.
    from untell.detectors.base import _TIER_RANK

    parser.add_argument("--tier", default="full", choices=list(_TIER_RANK))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.file:
        # read_file(): BOM-aware, sniffs UTF-16/cp1252, handles docx/pdf, rejects binaries.
        # A naive utf-8 open turned a UTF-16 document into mojibake and scored THAT.
        from untell.scripts.io_utils import read_file_or_exit

        text = read_file_or_exit(args.file)
    elif args.text:
        text = args.text
    else:
        text = sys.stdin.read()
    if not text.strip():
        print(json.dumps({"error": "empty input"}))
        return 2

    score = humanness(text, tier=args.tier)
    cls = classification(score)
    # Report the tier alongside the number. Half the score is the detector term, and the detector
    # term is what the tier selects, so the same text gets a materially different verdict depending
    # on a flag the output did not mention. MEASURED on 6 real HC3 AI texts:
    #     lite  mean 62.8  ->  all six "mostly human"
    #     full  mean 43.4  ->  all six "mixed"
    # A 19.4-point swing and a different band, from the tier alone. A bare "Humanness: 62.8/100
    # (mostly human)" is not a fact about the text; it is a fact about the text AND the tier, and
    # only one of those was on screen.
    result = {"score": score, "classification": cls, "tier": args.tier}
    driver = _dominant_signal(text, args.tier)
    if driver:
        result["driver"] = driver
    if args.json:
        print(json.dumps(result, ensure_ascii=True))
    else:
        print(f"Humanness: {score}/100  ({cls})  [tier={args.tier}]")
        if driver:
            print(f"  {driver}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
