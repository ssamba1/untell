"""Ensemble detector scoring — the skill's eyes on the text.

Loads every detector available at the requested tier, scores the text with each, and emits
JSON the skill (Claude) reads as feedback:

    {
      "tier": "lite",
      "detectors": {"perplexity_burstiness": 0.71, ...},
      "max": 0.71,          # the proxy the loop drives below threshold (multi-detector evasion)
      "mean": 0.71,
      "threshold": 0.30,
      "flagged": true       # max >= threshold => still looks AI, keep rewriting
    }

The ``max`` aggregation targets the hardest detector in the ensemble (report gap #3): a rewrite
only "passes" when *every* detector is under threshold.

CLI / console entry (`untell-score`):
    untell-score "<text>"
    untell-score --file path.txt --tier full --threshold 0.3
    echo "text" | untell-score
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys

from untell.detectors.base import _TIER_RANK, load_detectors, resolved_tier
from untell.text_split import fold_unicode_spaces

logger = logging.getLogger(__name__)
# (`python scripts/score.py`) rather than imported as part of the `untell` package,
# put the directory that *contains* the package on sys.path so `import untell`
# resolves regardless of the current working directory.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break


DEFAULT_THRESHOLD = 0.30


# Cap input length to avoid OOM. This used to be justified with "detectors truncate at 512 tokens
# anyway" — that was true, and it was the bug: the detectors now WINDOW long text instead of
# discarding it (see detectors/base.py `windowed_max`), so this cap is the only truncation left and
# it bounds cost rather than hiding content.
_MAX_INPUT_CHARS = 50_000
# Public alias so network surfaces can reject oversized input at the edge instead of discovering
# the bound halfway through a request. Same aliasing pattern as preserve.SENTINEL_RE: one constant,
# two names, no second copy to drift.
MAX_INPUT_CHARS = _MAX_INPUT_CHARS


def batch_score_texts(
    texts: list[str],
    tier: str = "full",
    threshold: float = DEFAULT_THRESHOLD,
) -> list[dict]:
    """Score multiple texts with the detector ensemble, loading detectors ONCE for the batch.

    Each text gets the same result dict shape as ``score_text``. Use this when you have many
    short texts (e.g. sentences) to score — avoids re-initialising detectors per call.
    """
    if not texts:
        return []
    detectors = load_detectors(tier)
    return [_score_with_detectors(detectors, _truncate(t), tier, threshold) for t in texts]


_WS_RUN_RE = re.compile(r"[ \t]{2,}")
_BLANK_RUN_RE = re.compile(r"\n{3,}")


def _normalise_ws(text: str) -> str:
    """Collapse runs of spaces/tabs and 3+ blank lines, for SCORING only.

    The perplexity detectors tokenise whatever they are given, and GPT-2 encodes "  " differently
    from " ", so the same words scored materially differently depending on spacing. MEASURED on HC3
    documents, doubling every space:

        0.730 -> 0.649    0.459 -> 0.586    0.572 -> 0.667

    Swings of up to 0.13 on identical content, enough to flip a borderline verdict. Text pasted out
    of a PDF or an editor with hard-wrapped columns routinely carries runs like this.

    This affects only the string handed to the detectors. Nothing here touches the text the caller
    gets back, so document layout — which the rewriters now go to some trouble to preserve — is
    unaffected. It is a no-op on ordinary prose: verified byte-identical on the HC3 sample, so it
    cannot disturb the detector calibrations fitted against that corpus.
    """
    # Unicode spaces are folded FIRST, so a run of them collapses like any other run.
    #
    # MEASURED on 10 HC3 pairs at full tier, replacing every space with U+00A0: human text
    # went from 5/10 flagged to 9/10, mean P(AI) 0.4322 -> 0.7801, and hc3_roberta alone
    # moved by 0.9990. AI text was unaffected (10/10 either way), so the whole effect landed
    # on human writers — and a non-breaking space is not exotic input, it is what a paste out
    # of Word or a web page contains. `scrub_hidden` already normalises these, so the rewrite
    # loop was safe; the scoring path a user hits directly with `untell score` was not.
    return _BLANK_RUN_RE.sub("\n\n", _WS_RUN_RE.sub(" ", fold_unicode_spaces(text)))


def _truncate(text: str) -> str:
    """Normalise whitespace, then truncate absurdly long input so detectors don't OOM."""
    text = _normalise_ws(text)
    if len(text) > _MAX_INPUT_CHARS:
        return text[:_MAX_INPUT_CHARS]
    return text


# Verdict thresholds for scoring paths whose distribution the shipped default does not fit.
#
# `perplexity_burstiness` runs GPT-2 when torch is importable and a stdlib heuristic otherwise, and
# the two need different cut points. MEASURED over 100 human / 100 AI texts pooled from HC3 and
# RAID, sweeping the threshold:
#
#     path      thr 0.30            optimum          at the optimum
#     gpt2      FP  3%  TP 100%     0.30  J 0.970    unchanged — the shipped value IS the optimum
#     stdlib    FP 60%  TP  93%     0.40-0.45  J 0.517    FP 27%/17%, TP 78%/68%
#
# So the default is not wrong for "the lite tier" — it is wrong for the stdlib SUB-PATH of it,
# which is what runs on a clean install. At 0.30 that path tells three users in five that their own
# writing reads as AI. 0.45 is taken from the plateau's cautious end: this number decides whether a
# human is accused, and the cost of a miss (under-flagging AI) is borne by the loop, which still
# optimises against the low `threshold` and is unaffected by anything here.
_STDLIB_PERPLEXITY_VERDICT_THRESHOLD = 0.45


def modes_of(live) -> dict:
    """Which scoring path each detector would take, when it has more than one."""
    modes: dict = {}
    for d in live:
        get_mode = getattr(d, "mode", None)
        if callable(get_mode):
            try:
                modes[d.name] = get_mode()
            except Exception:  # a diagnostic must never break scoring
                pass
    return modes


def _verdict_threshold(threshold: float, scores: dict, modes: dict) -> float:
    """The cut point for the reported verdict, which is not always the loop's target.

    Only raised when the stdlib perplexity path is the WHOLE verdict. With any model-backed
    detector present the ensemble max is driven by a well-calibrated member and the default holds;
    the stdlib heuristic alone is the case the default does not fit.
    """
    if modes.get("perplexity_burstiness") != "stdlib":
        return threshold
    scoring = {k for k, v in scores.items() if isinstance(v, (int, float)) and "__" not in k}
    if scoring != {"perplexity_burstiness"}:
        return threshold
    return max(threshold, _STDLIB_PERPLEXITY_VERDICT_THRESHOLD)


def score_text(text: str, tier: str = "full", threshold: float = DEFAULT_THRESHOLD) -> dict:
    """Score ``text`` with the available detector ensemble; return the result dict.

    A detector that fails to load or score (e.g. a broken ML env) is **excluded** from the
    aggregate — it is never folded in as a neutral ``0.5``, which would silently pin ``max`` at
    a meaningless value. The reported ``tier`` reflects the detectors that actually produced a
    number, so a full-tier run whose ML stack is broken honestly reports ``lite`` (plus a
    ``warning`` and a ``failed_detectors`` list), instead of looking like a real full-tier score.
    """
    return _score_with_detectors(load_detectors(tier), _truncate(text), tier, threshold)


# How badly the ensemble misreads SHORT text. MEASURED on 40 HC3 pairs at the 0.30 default, full
# tier, truncating both halves of each pair to the first N words and asking what fraction of the
# HUMAN half flags:
#
#     words   human flagged   AI flagged
#         5             98%         100%     <- no discrimination at all
#        10             62%          95%
#        20             40%         100%
#        40             28%         100%
#        80             17%         100%
#
# At five words a human paragraph and an AI paragraph are indistinguishable, and the API answers
# "a" with P(AI) = 0.9987 and flagged=True. `humanness()` already refuses to answer below five
# words; the primary scoring path did not, and it is the one behind /score, /tells and the CLI.
#
# The verdict itself is left alone deliberately. `max` is the raw ensemble output and callers store
# and compare it; silently zeroing or withholding it would break them for a reason they cannot see.
# What was missing is the thing the lite-tier stdlib path already does — say, with the measured
# number, that this configuration is not one to trust.
_SHORT_TEXT_BANDS = ((5, "98%"), (10, "62%"), (20, "40%"), (40, "28%"))
_MIN_WORDS_FOR_A_VERDICT = 40


# Characters with no visible width that nonetheless change every tokenisation: zero-width space,
# ZWNJ/ZWJ, word joiner, bidi marks, BOM, and the soft hyphen that justified PDF text is full of.
_INVISIBLE_RE = re.compile("[" + "\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\u00ad" + "]")


def _invisible_char_warning(text: str) -> str | None:
    """Say when the text carries invisible characters, because they move the score a long way.

    Not stripped here, deliberately, and this is the opposite call from the one `score_tells` makes.
    A tell count describes the WRITING, and "889 words" for a 209-word text is simply false, so
    there the characters are removed. This number describes what a DETECTOR would say about the
    exact string the user is about to submit — and a real detector will see those characters too.
    Scrubbing them would report a score for a document that does not exist.

    MEASURED on 6 HC3 texts with a zero-width space between every character: mean |dP(AI)| 0.2176,
    and the flagged verdict flipped on 6 of 6. That is far too large to leave unexplained.
    """
    n = len(_INVISIBLE_RE.findall(text))
    if not n:
        return None
    return (
        f"{n} invisible character(s) present (zero-width, bidi or soft hyphen). They no longer "
        f"affect the score — the detectors normalise them, verified at 0.0000 movement on both "
        f"tiers — but they are still IN YOUR TEXT and will travel with it wherever you send it. "
        f"They were a working evasion until the detectors were fixed, so anywhere else may still "
        f"read them differently. Run `untell scrub` to remove them."
    )


# A word containing BOTH Latin and Cyrillic/Greek letters. Legitimate multilingual text does not
# mix scripts INSIDE a word — quoting Russian puts whole Russian words in, not a Cyrillic 'a' in
# the middle of an English one. So this is a precise signature for homoglyph substitution, and
# it costs almost nothing in false positives.
_LATIN = re.compile("[A-Za-z]")
_CONFUSABLE_SCRIPT = re.compile("[\u0400-\u04ff\u0370-\u03ff]")


def _homoglyph_warning(text: str) -> str | None:
    """Warn when Cyrillic or Greek letters sit inside Latin words.

    MEASURED on 15 HC3 pairs, mapping a/e/o/p/c to their Cyrillic lookalikes: AI text moved
    -0.2884 and its verdict flipped to clean on **13 of 15**; human text moved -0.2407 and
    flipped on 4. A stronger evasion than the zero-width case, and invisible to a reader.

    `score_tells` is already immune — it scrubs, and scrubbing maps these back to ASCII. This
    surface deliberately does not scrub (see `_invisible_char_warning`), so it has to say so.
    """
    mixed = [w for w in text.split() if _LATIN.search(w) and _CONFUSABLE_SCRIPT.search(w)]
    if not mixed:
        return None
    return (
        f"{len(mixed)} word(s) mix Latin with Cyrillic/Greek letters — the signature of homoglyph "
        f"substitution. The score is unaffected (the detectors normalise confusables, verified at "
        f"0.0000 movement), but the substitution is still in your text and another tool may not "
        f"normalise it. Run `untell scrub` to restore plain ASCII."
    )


def _short_text_warning(text: str) -> str | None:
    """Warn when the text is too short for the flag to mean anything, with the measured rate."""
    words = len(text.split())
    if words >= _MIN_WORDS_FOR_A_VERDICT:
        return None
    rate = next(pct for bound, pct in _SHORT_TEXT_BANDS if words <= bound)
    return (
        f"{words} word{'' if words == 1 else 's'}: too short for a reliable verdict. MEASURED on 40 HC3 pairs at this "
        f"threshold, {rate} of HUMAN text this length also flags. Score longer text, or treat this "
        f"as no evidence either way."
    )


def _score_with_detectors(
    detectors: list,
    text: str,
    tier: str = "full",
    threshold: float = DEFAULT_THRESHOLD,
) -> dict:
    """Score ``text`` against a *pre-loaded* detector list (avoids re-initialisation)."""
    scores: dict[str, float | None] = {}
    live = []  # detectors that produced a genuine numeric score
    out_of_range_raw: dict[str, float] = {}  # name -> the raw value before clamping
    for d in detectors:
        try:
            val = d.score(text)
        except Exception as exc:  # a flaky/broken detector must not crash or skew the loop
            scores[d.name] = None  # type: ignore[assignment]
            scores[f"{d.name}__error"] = str(exc)[:140]  # type: ignore[assignment]
            continue
        if val is None:  # detector explicitly produced no signal -> exclude, don't fake a 0.5
            scores[d.name] = None  # type: ignore[assignment]
            continue
        # Defensive clamp at the AGGREGATION layer, not just in each adapter. A detector is supposed
        # to return P(AI) in [0, 1], but this session found three adapters shipping wrong values, and
        # an out-of-range score does real damage here: a commercial API answering on a 0-100 scale
        # makes ai_percent read 8500.0, and the common "-1 means error" sentinel reads as MORE human
        # than any real text, so broken-detector output would look like a perfect result. Clamping is
        # the safe direction; the raw value is surfaced so the adapter bug is still visible.
        # The conversion is INSIDE its own guard: `float()` on a non-numeric value raises, and this
        # line sits outside the try above, so an adapter handing back an error string instead of a
        # number took down the whole scoring call rather than excluding itself.
        try:
            raw = float(val)
        except (TypeError, ValueError):
            scores[d.name] = None  # type: ignore[assignment]
            scores[f"{d.name}__error"] = f"non-numeric score {val!r}"  # type: ignore[assignment]
            continue
        # NaN is neither < 0 nor > 1, so it slips through the clamp below untouched and then
        # poisons everything downstream: max and mean become NaN, `NaN >= threshold` is False so
        # `flagged` reads False — a confident "this is human" produced by a broken detector — and
        # json.dumps emits a bare NaN, which is not valid JSON for any API client.
        if raw != raw:
            scores[d.name] = None  # type: ignore[assignment]
            scores[f"{d.name}__error"] = "detector returned NaN"  # type: ignore[assignment]
            continue
        clamped = 0.0 if raw < 0.0 else (1.0 if raw > 1.0 else raw)
        if clamped != raw:
            # Recorded OUTSIDE the detectors dict on purpose. Every consumer that iterates
            # `detectors` filters sidecars by `endswith("__error")` — run.py, verify.py and
            # training/reward.py all do — so adding a differently-suffixed FLOAT key here silently
            # broke them: reward.py folded the raw 100.0 from a 0-100-scale API into its weighted
            # mean as a phantom detector, turning a correct ~0.75 reward into -49.5. Keeping the
            # diagnostic out of the dict removes that trap for every present and future consumer.
            out_of_range_raw[d.name] = round(raw, 4)
        scores[d.name] = round(clamped, 4)
        live.append(d)

    numeric = [v for v in scores.values() if isinstance(v, (int, float))]
    mx = max(numeric) if numeric else 0.0
    mean = sum(numeric) / len(numeric) if numeric else 0.0
    effective = resolved_tier(live) if live else "lite"
    failed = [k[: -len("__error")] for k in scores if k.endswith("__error")]
    result: dict = {
        "tier": effective,
        "tier_requested": tier,
        "detectors": scores,
        "max": round(mx, 4),
        "mean": round(mean, 4),
        "ai_percent": round(mx * 100, 1),  # 0-100 AI-likelihood (the headline number competitors show)
        "threshold": threshold,
    }
    # The VERDICT threshold is not always the loop's target. `threshold` is what the rewrite loop
    # optimises toward, and a low value there is correct — stopping early is under-rewriting. But
    # the same number also decided `flagged`, i.e. what a user is TOLD about their text, and on one
    # scoring path that made it wrong three times in five.
    verdict_threshold = _verdict_threshold(threshold, scores, modes_of(live))
    result["verdict_threshold"] = verdict_threshold
    result["flagged"] = bool(numeric) and mx >= verdict_threshold
    if failed:
        result["failed_detectors"] = failed
    # Some detectors have more than one scoring path under one name, and which one ran changes the
    # verdict. `perplexity_burstiness` silently uses GPT-2 when torch is importable and a stdlib
    # heuristic otherwise; MEASURED on 100 held-out HC3 pairs at this threshold, that is FPR 6.0%
    # against 69.0% — an 11.5x difference decided by an optional dependency, reported under the same
    # detector name and the same tier label. Record it the way `corpus` and `rewriter` are recorded
    # on the ceiling result: a number whose meaning depends on a hidden variable has to carry it.
    modes = modes_of(live)
    if modes:
        result["detector_modes"] = modes
    if out_of_range_raw:
        result["out_of_range_detectors"] = sorted(out_of_range_raw)
        result["out_of_range_raw"] = out_of_range_raw
    if not numeric:
        # NOTHING was scored. max/mean are 0.0 placeholders, and 0.0 otherwise reads as a confident
        # "definitely human" — the most misleading value this function could return. Say so
        # explicitly rather than letting a caller mistake an unscored result for a clean one.
        result["scored"] = False
        result.setdefault(
            "warning", "no detector produced a score — max/mean are placeholders, not a verdict"
        )
    # An unrecognised tier is the ONE downgrade the check below structurally cannot catch. "lite"
    # ranks 0 and `.get(tier, 0)` also returns 0 for an unknown name, so `0 > 0` is False and a
    # typo produced a lite-tier answer labelled with no warning at all — quieter than a genuine
    # full->lite fallback, which does warn. Name it as a caller error rather than a downgrade,
    # and take the vocabulary from _TIER_RANK so it cannot drift from what load_detectors honours.
    if tier not in _TIER_RANK:
        result["warning"] = (
            f"unknown tier '{tier}' — no tier matched, so only the always-on '{effective}' "
            f"detectors ran. Valid tiers: {', '.join(_TIER_RANK)}."
        )
    # The lite tier running its stdlib path is the one configuration where "flagged" is close to
    # meaningless, and nothing said so. MEASURED on 100 held-out HC3 pairs at the 0.30 default:
    # 69% of HUMAN text flags, against 6% when torch is importable and the same detector uses GPT-2
    # instead. Only warn when that path is the whole verdict — with other detectors live, the max
    # is not its to decide.
    elif effective == "lite" and modes.get("perplexity_burstiness") == "stdlib" and len(numeric) == 1:
        result["warning"] = (
            "lite tier on the stdlib path. Re-measured on 100 HC3 pairs: 64% of HUMAN text scores "
            "above the 0.30 loop threshold, and 30% is FLAGGED — `flagged` uses the 0.45 verdict "
            "threshold, not the loop one, so the two numbers answer different questions. Either "
            "way this path is weak evidence: treat a flag as a prompt to re-run at --tier full."
        )
    # Loudly flag a silent downgrade: full requested, but the ML stack didn't produce scores.
    elif _TIER_RANK.get(tier, 0) > _TIER_RANK.get(effective, 0):
        result["warning"] = (
            f"requested tier '{tier}' but only '{effective}' produced scores"
            + (f"; failed to load: {', '.join(failed)}" if failed else "")
            + f". The reported numbers reflect the '{effective}' tier only "
            "(commonly a NumPy 2.x / torch mismatch — see the README troubleshooting section)."
        )
    # A detector that loaded and then produced nothing shrinks the ensemble the verdict is drawn
    # from, and `max` over fewer members can only fall — so the whole error is toward NOT flagged,
    # which is telling someone their AI text reads as human. MEASURED with the strongest member of
    # a four-detector full-tier ensemble returning None on a real AI paragraph:
    #
    #     all four live    max 0.6566   flagged True
    #     one silent       max 0.1058   flagged False
    #
    # Both ways of producing nothing count. `failed_detectors` names the ones that RAISED, and says
    # nothing about what their absence did to the verdict; the ones that merely returned None had no
    # top-level trace at all — the verdict flipped and the only sign was a `null` nested inside
    # `detectors`, which is a `null` in the JSON an API client has no reason to inspect once
    # `flagged` answered the question. This is the shape `commercial.py` already warns about on
    # stderr: a provider changes its response format, its adapter starts returning None, and the
    # detector quietly leaves the ensemble on a service the user is being billed for.
    #
    # Rare enough to be worth saying: MEASURED over 80 real HC3 texts at >=60 words, partial
    # abstentions were 0/80. This does not fire on healthy scoring.
    absent = [
        name
        for name, val in scores.items()
        if val is None and not name.endswith("__error") and name not in failed
    ]
    ensemble_warning = None
    if (absent or failed) and numeric:
        gone = ", ".join(sorted(absent) + [f"{n} (errored)" for n in sorted(failed)])
        ensemble_warning = (
            f"{len(numeric)} of {len(numeric) + len(absent) + len(failed)} detectors produced a "
            f"score; {gone} returned nothing. `max` is taken over the survivors, so a missing "
            "detector can only lower it — this verdict errs toward NOT flagged."
        )
    # Appended rather than folded into the chain above: length and tier are independent problems,
    # and a short text scored on a downgraded tier has both. An elif would have reported whichever
    # one happened to be checked first and hidden the other.
    for extra in (ensemble_warning, _short_text_warning(text), _invisible_char_warning(text),
                  _homoglyph_warning(text)):
        if extra:
            result["warning"] = (
                f'{result["warning"]} Also: {extra}' if result.get("warning") else extra
            )
    return result


def _read_input(args: argparse.Namespace) -> str:
    if args.file:
        # read_file(): BOM-aware, sniffs UTF-16/cp1252, handles docx/pdf, rejects binaries.
        # A naive open(encoding="utf-8", errors="replace") turns a UTF-16 document into mojibake
        # peppered with NUL bytes and scores THAT, silently. Same bug already fixed in run.py and
        # tells.py; it was still open at every other --file entry point.
        from untell.scripts.io_utils import read_file_or_exit

        return read_file_or_exit(args.file)
    if args.text:
        return args.text
    return sys.stdin.read()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()  # UTF-8 stdin/stdout/stderr (Windows defaults to cp1252)
    parser = argparse.ArgumentParser(
        prog="untell-score",
        description="Score text with the local AI-detector ensemble and print JSON.",
    )
    parser.add_argument("text", nargs="?", help="Text to score (or use --file / stdin).")
    parser.add_argument("--file", "-f", help="Read text from this file.")
    parser.add_argument(
        "--tier",
        default="full",
        choices=["lite", "full", "heavy", "commercial"],
        help="Max detector tier to attempt; auto-degrades to what is installed/configured "
        "(default: full). 'commercial' adds the paid API checkers whose keys are set.",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="suppress the stderr progress/tier notices (stdout JSON is unaffected)",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Max-proxy P(AI) below which text is considered human-passing (default: {DEFAULT_THRESHOLD}).",
    )
    args = parser.parse_args(argv)

    from untell._env import load_env

    load_env()  # pick up commercial keys from a .env file if present (for --tier commercial)

    text = _read_input(args)
    if not text.strip():
        print(json.dumps({"error": "empty input"}))
        return 2

    # Say what is about to happen BEFORE it happens. The full tier loads real transformer models —
    # measured at ~19s cold on CPU — during which the only output is raw HuggingFace weight-loading
    # bars and HF Hub warnings. That reads as a hang, and nothing told the user there is an instant
    # alternative. stderr keeps stdout pure JSON for the skill to parse.
    if args.tier in ("full", "heavy") and not args.quiet:
        print(
            f"[untell-score] loading the '{args.tier}' detector tier — real models, ~20s on first "
            "run (cached after). Use --tier lite for an instant zero-dependency heuristic.",
            file=sys.stderr,
        )

    result = score_text(text, tier=args.tier, threshold=args.threshold)
    # Log which tier actually ran to stderr (stdout stays pure JSON for the skill to parse). A direct
    # stderr write (not logging) so it survives the root logger sitting at WARNING and is captured by
    # the current sys.stderr under test.
    if not args.quiet:
        print(f"[untell-score] tier requested={args.tier} ran={result['tier']}", file=sys.stderr)
    # ensure_ascii=True: detector error strings may carry non-ASCII; never crash a Windows stdout.
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
