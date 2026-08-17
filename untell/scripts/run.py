"""Headless untell loop — run the full lock -> score -> rewrite -> restore loop as a CLI.

Inside Claude Code the SKILL.md procedure drives the loop with Claude as the rewriter. This module
is the *standalone* path: a `untell-loop` console command (and `untell_text` API) that runs the
same loop programmatically using a hosted-LLM rewriter (``untell.rewriter``). It reuses the exact
same scripts the skill calls — preserve-lock, the detector ensemble, and the quality gate — so the
two paths stay behaviourally identical.

A rewriter must be configured (``pip install -e ".[api]"`` + ``ANTHROPIC_API_KEY``/``OPENAI_API_KEY``);
without one this returns a clear error rather than silently no-op'ing (use the Claude skill instead).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import random
import sys
import threading
import time
from collections import Counter
from contextlib import contextmanager

# Run-as-file support (zero-dep lite tier): when this file is executed directly
# rather than imported as part of the `untell` package, put the directory that
# *contains* the package on sys.path so `import untell` resolves from any cwd.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

from untell.rewriter import get_rewriter
from untell.rewriter.prompts import STYLE_NAMES
from untell.scripts.entailment import meaning_preserved
from untell.scripts.latex import is_latex
from untell.scripts.latex import prose_only as latex_prose
from untell.scripts.preserve import _SENTINEL_RE, lock, restore
from untell.scripts.quality import method, recommended_bar, similarity
from untell.scripts.score import DEFAULT_THRESHOLD, score_text
from untell.scripts.tells import looks_non_english, score_tells

# Serialises the seeded region of `untell_text`. Reentrant, so a nested call cannot deadlock on
# itself. See the comment at its `with _RNG_LOCK` for what was measured without it.
_RNG_LOCK = threading.RLock()

# Detector-score noise band. Among best-of-N candidates whose detector max is within this of each
# other, prefer the one with FEWER AI tells — a strictly more human-reading rewrite at no cost to
# evasion. Detectors anti-correlate with human-ness on some text, so tells are the better tie-breaker.
_TELLS_EPS = 0.02

# What best-of-N ranks candidates ON. `max` over the whole tier is the shipped behaviour and stays
# the default; the alternatives exist because Result 163 measured that improving this quantity stops
# improving a detector the loop never sees. The loop optimises `max` over five correlated proxies and
# then reports `max` over the same five, so a candidate that exploits one member's quirk wins — and
# out of sample, the flagged count does not move at all (10/10 -> 4/2/3 in sample, 7/10 -> 4/4/4 held
# out, across three seeds).
#
#   max      rank on the tier max. Shipped default; every published figure uses it.
#   mean     rank on the ensemble mean, so lowering four detectors beats gaming one.
#   dropout  rank on the max over a RANDOM SUBSET of the tier, resampled each iteration. A candidate
#            cannot be selected for exploiting a member that is absent from the subset it was judged
#            on. This is the transfer hypothesis stated as a mechanism.
#
# MEASURED AND REFUTED. RAID n=10, three seeds each, held-out RADAR (`python -m eval.holdout`):
#
#     mode      held-out mean, per seed          held-out flagged
#     max       0.5035  0.4981  0.4391           4 / 4 / 4
#     mean      0.4982  0.5372  0.5121           4 / 5 / 6
#     dropout   0.4799  0.5231  0.5023           4 / 5 / 6
#
# Neither alternative improves transfer; both are slightly WORSE on the mean and more variable on
# the count. The shipped `max` holds 4 of 10 in every seed. At seed 0 alone `dropout` led (0.4799
# against 0.5035) and that inverted on replication — the same single-seed shape that has now
# produced four false findings in this project.
#
# The knob is kept because the question is worth being able to re-ask on a different corpus or a
# larger n, and because a mode that measured as no better is a result other people should not have
# to re-derive. It is not a tuning surface: `max` is the answer here.
#
# Selected with UNTELL_SELECT. Read per call rather than at import so a harness can sweep it without
# reloading the module, and so a test can set it with monkeypatch.setenv.
_SELECT_MODES = ("max", "mean", "dropout")
# Fraction of the tier each dropout draw ranks on. 0.6 of five detectors is three — enough that the
# objective is still an ensemble rather than a single member, few enough that no member is always
# present. Not tuned; stated so the next person knows it was chosen, not measured.
_DROPOUT_KEEP = 0.6


def _selection_mode() -> str:
    """The ranking objective for this call, defaulting to the shipped one."""
    mode = os.environ.get("UNTELL_SELECT", "max").strip().lower()
    return mode if mode in _SELECT_MODES else "max"


def _live_detectors(score: dict) -> dict[str, float]:
    """Detector name -> value, dropping error keys and non-numeric placeholders."""
    return {
        k: v for k, v in (score.get("detectors") or {}).items()
        if isinstance(v, (int, float)) and not str(k).endswith("__error")
    }


def _selection_subset(score: dict, rng) -> frozenset[str] | None:
    """The detector names this iteration ranks on; None means "all of them"."""
    if _selection_mode() != "dropout":
        return None
    names = sorted(_live_detectors(score))
    if len(names) < 3:  # nothing to drop out of; ranking on a subset of two is just noise
        return None
    keep = max(2, round(len(names) * _DROPOUT_KEEP))
    return frozenset(rng.sample(names, keep))


def _objective(score: dict, subset: frozenset[str] | None) -> float:
    """The number best-of-N minimises. Falls back to `max` whenever the mode cannot apply."""
    mode = _selection_mode()
    if mode == "mean":
        value = score.get("mean")
        return float(value) if isinstance(value, (int, float)) else float(score["max"])
    if subset:
        live = _live_detectors(score)
        chosen = [v for k, v in live.items() if k in subset]
        if chosen:
            return max(chosen)
    return float(score["max"])

# Exception type names already reported for the polish stage. Process-wide so a persistent failure
# warns once instead of on every call — same pattern as `_MEMBER_FAILED` in rewriter/ensemble.py.
_POLISH_FAILED: set[str] = set()

# The hosted backends, and the two separate things each one needs. `available()` answers False for
# either, and an unknown NAME also arrives here as None — so all three produced the same message,
# "check the name (see `untell --check`) or install its extra". For a correctly-spelled backend
# whose only problem is an unset key, that is advice to fix something that is not broken.
#
# The bar this repo already holds itself to is in io_utils: name the package AND the extra
# ("reading it needs python-docx: pip install 'untell[docs]'"). Same here — say which of the two
# is missing, and give the command.
_HOSTED_REQUIREMENTS = {
    "anthropic": ("ANTHROPIC_API_KEY", "anthropic", "untell[api]"),
    "openai": ("OPENAI_API_KEY", "openai", "untell[api]"),
}


def _unavailable_reason(name: str) -> str:
    """Why this rewriter cannot run, and what to do about it."""
    import importlib.util
    import os

    requirement = _HOSTED_REQUIREMENTS.get(name.lower())
    if requirement is not None:
        env_var, module, extra = requirement
        missing_key = not os.environ.get(env_var)
        missing_sdk = importlib.util.find_spec(module) is None
        if missing_key and missing_sdk:
            return (
                f"rewriter {name!r} needs two things and has neither: the {module} SDK "
                f"(pip install '{extra}') and the {env_var} environment variable."
            )
        if missing_key:
            return (
                f"rewriter {name!r} is installed but {env_var} is not set. Export it, or use a "
                f"free rewriter that needs no key (--rewriter composite)."
            )
        if missing_sdk:
            return (
                f"rewriter {name!r} has its key set but the {module} SDK is not installed: "
                f"pip install '{extra}'."
            )
        # Both present and still unavailable — say so rather than guessing at a cause.
        return (
            f"rewriter {name!r} reports itself unavailable even though {env_var} is set and "
            f"{module} is importable. Run `untell --check` for the installed list."
        )
    if name.lower() in ("local", "local-policy"):
        # The local-policy rewriter's reason is richer than the generic fallback below: it names
        # the exact missing package and the extra that installs it (issue #34). A library caller
        # passing rewriter="local" gets that instead of "check the name or install its extra".
        from untell.rewriter.local_policy import LocalPolicyRewriter

        reason = LocalPolicyRewriter().unavailable_reason()
        if reason is not None:
            return f"rewriter {name!r} is unavailable: {reason}"
    return (
        f"rewriter {name!r} is not available — check the name (see `untell --check` for the "
        "installed list) or install its extra"
    )


# At or above this the ensemble max cannot show an improvement, so `pre` and `post` being equal is
# not evidence that nothing changed. Same constant and same measurement as `rich_output`.
_SATURATED_MAX = 0.99


def _saturated_max_caveat(pre: dict, post: dict) -> str | None:
    """Say when the reported P(AI) could not have moved, whatever the rewrite did."""
    a, b = pre.get("max"), post.get("max")
    if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        return None
    if a < _SATURATED_MAX or b < _SATURATED_MAX:
        return None
    pre_mean, post_mean = pre.get("mean"), post.get("mean")
    tail = ""
    if isinstance(pre_mean, (int, float)) and isinstance(post_mean, (int, float)):
        tail = f" Ensemble mean moved {pre_mean:.4f} -> {post_mean:.4f}."
    return (
        f"the hardest detector is pinned at {b:.4f}, so the before/after P(AI) comparison cannot "
        f"show an improvement either way — read `mean` or the tell counts instead.{tail}"
    )


def _merge_warnings(*parts: str | None) -> str | None:
    """Join the caveats that apply to one run, dropping blanks and exact repeats.

    Two independent things can be worth saying at once — the text carried hidden characters AND no
    detector could score it — and an `or` between them would silently drop whichever came second.
    `score_text` composes its own warnings the same way, with "Also:" between clauses.
    """
    seen: list[str] = []
    for part in parts:
        text = (part or "").strip()
        if text and text not in seen:
            seen.append(text)
    return " Also: ".join(seen) if seen else None


# A style profile needs enough words to mean anything. Matches the floor the rest of the codebase
# uses for "too short to measure" (humanness._MIN_WORDS_FOR_SIGNAL, the detectors' own abstention),
# raised here because a profile has six features to estimate rather than one score.
_MIN_VOICE_SAMPLE_WORDS = 20
_WARNED_VOICE_SAMPLE = False
_WARNED_FREE_FALLBACK = False

# One string, two readers — the stderr line and the result field. Two copies of a caveat drifting
# apart is a defect this repo has found repeatedly.
FREE_FALLBACK_WARNING = (
    "no hosted or local-policy rewriter is configured, so the free 'composite' path ran "
    "instead. Pass rewriter='composite' to make that explicit, or set ANTHROPIC_API_KEY / "
    "OPENAI_API_KEY / UNTELL_POLICY_DIR to use a configured one."
)


def _free_fallback_warning_text() -> str:
    """The fallback warning the two readers share, tailored when UNTELL_POLICY_DIR is set.

    FREE_FALLBACK_WARNING tells a user with nothing configured to set UNTELL_POLICY_DIR. When
    they ALREADY set it and the policy still cannot run — peft (or torch/transformers) missing,
    adapter dir gone — that advice is nonsense twice over: they did the thing it asks, and the
    rewriter needs something else entirely. Name the real reason in the same slot (issue #34).
    """
    if not os.environ.get("UNTELL_POLICY_DIR"):
        return FREE_FALLBACK_WARNING
    from untell.rewriter.local_policy import LocalPolicyRewriter

    reason = LocalPolicyRewriter().unavailable_reason()
    if reason is None:
        return FREE_FALLBACK_WARNING  # policy looks runnable; the fallback is a key thing
    return (
        f"UNTELL_POLICY_DIR is set but the local-policy rewriter cannot run: {reason} "
        "so the free 'composite' path ran instead. Install the extra above to use the "
        "trained policy, or pass rewriter='composite' to make the fallback explicit."
    )


def _warn_free_rewriter_fallback() -> None:
    """Say once that no configured rewriter was found and the free path ran instead.

    Silence here would be the failure this repo keeps finding elsewhere: a weaker backend
    substituted with nothing in the result to say so. A caller who set a key and expected the hosted
    rewriter needs to know it was not reached.
    """
    global _WARNED_FREE_FALLBACK
    if _WARNED_FREE_FALLBACK:
        return
    _WARNED_FREE_FALLBACK = True
    logging.getLogger(__name__).warning(_free_fallback_warning_text())


def _warn_voice_sample_too_short(words: int) -> None:
    """Say once that the sample was ignored. Silence here is the actual bug: the user supplied a
    file, believes it is shaping the output, and it is doing nothing."""
    global _WARNED_VOICE_SAMPLE
    if _WARNED_VOICE_SAMPLE:
        return
    _WARNED_VOICE_SAMPLE = True
    logging.getLogger(__name__).warning(
        "voice sample has %d words, under the %d needed to build a style profile — voice matching "
        "is disabled for this run rather than matched against a near-empty profile, which would "
        "bias the result toward short, comma-free, contraction-free text.",
        words, _MIN_VOICE_SAMPLE_WORDS,
    )


def _voice_key(masked_candidate: str, voice_sample: str | None) -> float:
    """Distance from ``voice_sample``'s writing style, or 0.0 when no sample was given.

    Sentinels are stripped first: ``⟦HZ0007⟧`` is one token to the word regex but stands for a span
    of arbitrary length, so leaving them in would score every candidate against a phantom vocabulary
    and skew the sentence-length and comma statistics that voice matching is built on.

    Returning a constant with no sample keeps the surrounding ``min`` key byte-identical to its
    previous behaviour, so the default path is untouched rather than merely unlikely to differ.

    "No sample" has to mean *nothing to profile*, not *empty string*. ``not voice_sample`` is False
    for "   ", which is truthy, so a whitespace-only or near-empty sample file reached
    ``voice_distance`` and produced an all-zero style profile — and the tie-break then ranks
    candidates by how close they are to zero commas, zero contractions and the shortest possible
    sentences. MEASURED on three candidates with a whitespace-only sample:

        rich prose  2.5225
        medium      0.8329
        terse       0.1282   <- "It works." wins

    So pointing ``--voice-sample`` at a blank file did not disable voice matching, it silently
    inverted it, biasing the loop toward degenerate output with nothing on screen to say so. Too
    short is the same failure in weaker form: a three-word sample profiles almost as flat.
    """
    if not voice_sample or not voice_sample.strip():
        return 0.0
    from untell.scripts.voice import _WORD, voice_distance

    if len(_WORD.findall(voice_sample)) < _MIN_VOICE_SAMPLE_WORDS:
        _warn_voice_sample_too_short(len(_WORD.findall(voice_sample)))
        return 0.0

    return voice_distance(voice_sample, _SENTINEL_RE.sub(" ", masked_candidate))


def _browser_scorer(sites: list[str], mapping: dict, threshold: float):
    """Return a scorer(masked_text)->score-dict that drives one or more free web detectors (no key).

    Scores the *restored* text (what a real detector actually sees) against every available site and
    drives the **max** across them — so the loop must beat ALL configured detectors, not just the
    weakest (the closest thing to "foolproof" we can do for free). Returns None if none are available.
    """
    from untell.browser_check import get_browser_checker
    from untell.scripts.preserve import restore

    checkers = []
    for site in sites:
        chk = get_browser_checker(site)
        if chk is not None and chk.available():
            checkers.append((site, chk))
    if not checkers:
        return None

    label = "browser:" + ",".join(s for s, _ in checkers)

    def _score(masked_text: str) -> dict:
        real = restore(masked_text, mapping)
        scores: dict[str, float | None] = {}
        for name, chk in checkers:
            try:
                scores[name] = round(float(chk.check(real)), 4)
            except Exception as exc:
                scores[name] = None
                scores[f"{name}__error"] = str(exc)[:120]
        numeric = [v for v in scores.values() if isinstance(v, (int, float))]
        mx = max(numeric) if numeric else 0.5
        out = {
            "tier": label,
            "detectors": scores,
            "max": round(mx, 4),
            "mean": round(sum(numeric) / len(numeric), 4) if numeric else 0.5,
            "threshold": threshold,
            "flagged": mx >= threshold,
        }
        if not numeric:  # every checker errored this round — 0.5 is a placeholder, not a real signal
            out["all_checkers_failed"] = True
        return out

    return _score


def _inert_budget_warning(max_iters: int, best_of: int) -> str | None:
    """Say when a budget setting made the loop do nothing, or was ignored.

    The REST schema refuses both of these — `max_iters` is `Ge1,Le100` and `best_of` is `Ge1,Le32`,
    so a value below one is a 422 there. The library accepts them, which is the same split Result
    180 found for `style`: the surface a caller types by hand validates, and the one every embedding
    caller uses does not.

    MEASURED on one paragraph at `tier=lite`:

        max_iters=1  best_of=1    changed=True   iters=1  rewrites=1  adopted=1
        max_iters=0               changed=False  iters=0  rewrites=0  adopted=0   nothing said
        max_iters=-3              changed=False  iters=0  rewrites=0  adopted=0   nothing said
        best_of=0                 changed=True   iters=1  rewrites=1  adopted=1   value ignored
        best_of=-2                changed=True   iters=1  rewrites=1  adopted=1   value ignored

    Two different failures. A non-positive `max_iters` returns the input untouched and says nothing —
    `_nothing_adopted_warning` cannot cover it, because no draft was ever drawn to refuse. A
    non-positive `best_of` is not respected at all: the caller asked for zero draws and got a
    rewrite, which is the worse of the two, because the result looks like a normal run.
    """
    # The two halves are not independent, and composing them naively produced a message that
    # contradicted itself. FOUND by rendering every caveat in this repository side by side rather
    # than one at a time: at `max_iters=0, best_of=0` it read
    #
    #     "max_iters=0 means no rewriting was attempted at all ... best_of=0 ... was ignored and
    #      one draft was drawn."
    #
    # No draft was drawn — `rewrites=0` — so the second sentence was false whenever the first was
    # true. A non-positive `max_iters` stops the loop before `best_of` means anything, so it is the
    # only thing worth saying.
    if max_iters is not None and max_iters < 1:
        return (
            f"max_iters={max_iters} means no rewriting was attempted at all, so your text came back "
            "exactly as you sent it. Pass 1 or more to run the loop."
        )
    if best_of is not None and best_of < 1:
        return (
            f"best_of={best_of} is not a number of drafts, so it was ignored and one draft was "
            "drawn. Pass 1 or more to choose how many candidates the loop picks between."
        )
    return None


def _nothing_adopted_warning(
    rewrites: int, adopted: int, changed: bool, vetoed: int = 0, noop: bool = False
) -> str | None:
    """Say when the loop drew candidates and kept none of them.

    `changed: false` alone reads as "the tool did nothing", and the caller cannot tell that apart
    from "the tool tried and every draft was worse". They are different situations with different
    remedies, and the fields that distinguish them — `rewrites` and `adopted` — are the two nobody
    reads.

    MEASURED on a 406-word HC3 document, `tier=lite`, `structural`, `best_of=1`, two seeds. The
    rewriter produced a strictly better text by this tool's own tell catalogue and the loop was right
    to refuse it:

        tells          41 -> 34
        detector max   0.5987 -> 0.6203   (worse, so not adopted)
        meaning gate   passed
        result         changed=False, rewrites=2, adopted=0, 41 tells left in place

    The loop optimises the detector score, so discarding a draft that raises it is correct. What was
    missing is any account of it: the user is handed their own text back with no indication that a
    better-by-tells version existed and was rejected on score.
    """
    if changed or not rewrites or adopted:
        return None
    drafts = f"{rewrites} candidate{'s' if rewrites != 1 else ''}"
    if noop:
        # Issue #25: every draw was byte-identical to the input (the `stalled_noop` stop). The old
        # text said "every draft scored worse", which is FALSE here — a byte-identical draw never
        # scored at all. The rewriter had nothing left to change, which is a different situation
        # (correct early stop) from "it tried and everything was worse".
        return (
            f"the rewriter returned {drafts} and every one was byte-identical to your text — "
            "there was nothing left to change, so the loop stopped instead of re-drawing the same "
            "text. Your text was returned unchanged."
        )
    if vetoed >= rewrites:
        # Every draft died at the meaning gate, which `continue`s BEFORE scoring — so none of them
        # was ever compared on score, and saying they "scored worse" would describe a comparison
        # that did not happen. The remedy is different too: more draws of a rewriter that keeps
        # changing the meaning is not the answer.
        return (
            f"the rewriter produced {drafts} and the meaning gate refused every one, so your text "
            "was returned unchanged. None of them was scored — the gate runs first. That is the "
            "guard doing its job: on this text the rewriter's drafts did not say what the source "
            "said. Try a different --rewriter; more draws of the same one will keep failing here."
        )
    if vetoed:
        return (
            f"the rewriter produced {drafts} and adopted none: {vetoed} changed the meaning and "
            f"{rewrites - vetoed} scored worse than your text, so it was returned unchanged. This "
            "is the loop refusing both a worse score and a changed meaning, not a failure to run. "
            "Try --best-of 3 for more draws, a different --rewriter, or --tier full."
        )
    return (
        f"the rewriter produced {drafts} and adopted "
        "none: every draft scored worse than your text, so it was returned unchanged. This is the "
        "loop refusing to make the score worse, not a failure to run. Try --best-of 3 for more "
        "draws, a different --rewriter, or --tier full, where the score has more to respond to."
    )


def _effective_style(style: str | None) -> str | None:
    """The style that actually ran, which is not always the one that was asked for.

    `style_profile` maps an unrecognised name to the neutral default by design. That is a reasonable
    thing for a lookup to do and a bad thing for a report to repeat: echoing the request back would
    tell a caller that `acadmic` ran.
    """
    try:
        from untell.rewriter.structural import _STYLE_PROFILES

        return style.strip().lower() if style and style.strip().lower() in _STYLE_PROFILES else None
    except Exception:  # a reporting field must never break the result it rides in
        return None


def _unknown_style_warning(style: str | None) -> str | None:
    """Say when a requested style was not recognised and the neutral profile ran instead.

    `api_server.py` records this exact failure for the REST surface and fixed it there by
    constraining the field to `STYLE_NAMES`: an unrecognised name "received a rewrite with no style
    applied and nothing saying so". The CLI has `choices=STYLE_NAMES`. The library entry point — the
    one the MCP server and every embedding caller use — had neither guard, so a typo silently bought
    a neutral rewrite.

    A warning rather than an exception: `style_profile`'s fallback is documented behaviour and
    callers may be passing a name from a newer version, so refusing the whole run would be a harsher
    answer than the mistake deserves.
    """
    if not style or _effective_style(style):
        return None
    try:
        from untell.rewriter.prompts import STYLE_NAMES

        known = ", ".join(sorted(STYLE_NAMES))
    except Exception:
        known = "see STYLE_NAMES"
    return (
        f"style {style!r} is not a known style, so the neutral profile ran instead and the output "
        f"carries no style. Known styles: {known}."
    )


def _flagged_sentences_of(final: str, threshold: float) -> dict:
    """Per-sentence flags for the text the caller actually received.

    The loop computes ``flagged_sentences`` at the top of each iteration, on MASKED text, and that is
    right for the two consumers that read it there — `rewriter/prompts.py` and the targeted rewriter
    are editing masked text, and showing them a restored citation invites the model to rewrite the
    one span that has to survive byte-for-byte.

    It is wrong for the caller, in two independent ways.

    **It names sentences that are not in the output.** MEASURED on the 7 HC3 documents (of 60) whose
    per-sentence pass flags anything, each run plain and with a citation and URL welded in — 12 runs,
    6 with a non-empty list: 4 sentences carried a ``⟦HZ…⟧`` sentinel and 4 were absent from
    ``final``. It fires on plain input too, because `lock` masks entities, numbers and dates rather
    than only citations::

        'Overall, the controversy surrounding unions in ⟦HZ0001⟧ is complex and multifaceted ...'

    **And it usually is not there at all.** ``best_score`` is replaced wholesale when a candidate is
    adopted, when the result is rescored and when it is polished, so the key set at the top of the
    iteration survives only when none of those happened afterwards. Instrumented on a document whose
    per-sentence pass was forced to flag every sentence, the loop computed 5 flagged sentences twice
    and the caller received an empty list: the value describes the text as it stood at the start of
    some earlier iteration, never ``final``.

    Scoring the final text costs one extra lite per-sentence pass per call and is the only way to
    make the field mean what its name says.

    COST, measured rather than assumed, because this repository has reverted two scoring changes on
    cost grounds. Isolated, over 8 HC3 documents of 7-12 sentences, median of 3 runs each:

        this pass                     0.076 - 0.120 s
        one whole-document score_text 0.038 - 0.056 s
        ratio                         2.30x  (median)

    Against a full `untell_text` run of roughly 1.1 s that is about 9%. End to end it is not
    separable from noise: with warm-up controlled and the two arms alternated, the median ratio over
    6 documents was 0.95x with individual ratios from 0.68x to 2.53x — scatter in both directions,
    larger than the effect being looked for.

    Two earlier numbers for this were wrong and are recorded so they are not re-derived: a first
    pass reported +25% median and a second reported 23.5x on one document. Both were warm-up landing
    in whichever arm ran first.
    """
    try:
        from untell.scripts.sentences import score_sentences

        return score_sentences(final, tier="lite", threshold=threshold).get("flagged") or []
    except Exception:  # a reporting field must never break the result it rides in
        return []


# ---------------------------------------------------------------------------
# Per-phase budget tracking (issue #27)
#
# MEASURED at wave 3 (slice 6, 1MB document, full loop): the rewrite phase took
# 462.7s of a 467.4s loop — 99.5% of the wall clock — while the initial score and
# the per-draw rescore together cost ~2s. The loop's cost is the rewrite, and a
# regression in ANY phase is invisible unless each phase is reported separately.
# `--timings` / `timings=True` emits the split; a regression test pins the shape.
#
# Order is EXECUTION order: the initial score, the per-iteration sentence
# targeting, the rewrite draws, the similarity gate, the per-draw rescore, the
# tells tie-break, the optional polish — then the whole-body `total` last. The
# dict is emitted in exactly this order so a reader (or a test) can see at a
# glance whether the phases are in the order the loop actually runs them.
_PHASE_ORDER = ("score_pre", "targeting", "rewrite", "similarity", "rescore", "tells", "polish")


@contextmanager
def _timed(phase: dict[str, float], name: str):
    """Add the wall-clock seconds of the wrapped block to ``phase[name]``.

    Always runs, even when ``timings=False``: two ``perf_counter`` calls per phase
    call are noise against the detector/rewrite passes they wrap, and keeping one
    code path means the report can never describe a run that was timed differently
    from the one that happened.
    """
    t0 = time.perf_counter()
    try:
        yield
    finally:
        phase[name] += time.perf_counter() - t0


def _timings_dict(phase: dict[str, float], start: float) -> dict[str, float]:
    """Assemble the ``timings`` result payload: phases in canonical order, total last.

    ``total`` is the whole-body wall clock, so it is >= the sum of the phase
    buckets by construction (the buckets are disjoint sub-intervals of the body;
    locking, scrubbing, seeding and the restore passes are the un-bucketed rest).
    """
    report = {name: phase[name] for name in _PHASE_ORDER}
    report["total"] = time.perf_counter() - start
    return report


def _timings_report(timings: dict | None) -> str:
    """One human-readable line for ``untell humanize --timings``.

    Per-phase seconds with the share of the total, in execution order, so a
    regression shows up as a percentage shift a reader can see at a glance —
    the rewrite phase measured 99.5% of a 1MB-document loop, and a jump in any
    other phase's share is the signal this exists to surface.
    """
    if not timings:
        return ""

    def _fmt(seconds: float) -> str:
        # Sub-second phases are common on short text; a bare "0.0s" hides them.
        return f"{seconds:.2f}s" if seconds < 10 else f"{seconds:.1f}s"

    total = timings.get("total") or 0.0
    parts = []
    for name in _PHASE_ORDER:
        seconds = timings.get(name, 0.0)
        share = (seconds / total * 100.0) if total > 0 else 0.0
        parts.append(f"{name} {_fmt(seconds)} ({share:.1f}%)")
    return "[timings] " + " | ".join(parts) + f" | total {_fmt(total)}"


def untell_text(
    text: str,
    tier: str = "full",
    threshold: float = DEFAULT_THRESHOLD,
    max_iters: int = 5,
    sim_bar: float | None = None,
    rewriter=None,
    browser: str | list[str] | None = None,
    margin: float = 0.0,
    confirm: int = 0,
    scrub: bool = True,
    polish: bool = False,
    style: str | None = None,
    # 3, matching every surface that reaches this function: the CLI (`cfg["best_of"]`), the MCP
    # `humanize` tool and the REST `/humanize` endpoint. Those three were each moved to 3 after
    # best-of-1 was identified as a root cause of understated evasion — MEASURED over 6 real HC3
    # paragraphs, best_of=1 left 33% of texts flagged and best_of=3 left 0% — but the signature
    # default stayed at 1, so a direct library call still got the weak path with nothing to say so.
    # That is the same defect the MCP and REST fixes were for, one layer down.
    #
    # eval/ceiling.py is unaffected and stays at 1: measuring the single-draw baseline is its job,
    # and it passes the value explicitly.
    best_of: int = 3,
    detector_thresholds: dict[str, float] | None = None,
    veto_contradictions: bool = True,
    voice_sample: str | None = None,
    # Print a line per iteration. Default False so every programmatic caller — library, MCP, REST —
    # behaves exactly as before; the CLI opts in for its human-facing (non-JSON) path.
    progress: bool = False,
    # Per-phase wall-clock budget (issue #27): when True, the result dict gains a ``timings``
    # key with the score_pre/rewrite/rescore split (plus targeting/similarity/tells/polish and
    # the whole-body ``total``), in execution order. The loop's cost is dominated by the rewrite
    # phase (measured 462.7s of a 467.4s 1MB-document loop, 99.5%), so the split is what makes a
    # regression in any single phase visible. Off by default so every existing caller's payload
    # is byte-identical; the CLI exposes it as ``--timings``.
    timings: bool = False,
    # None derives the seed from the input text (see the block at the top of the body). Pass an int
    # to sweep seeds: several tests and harnesses vary the seed deliberately to show a knob is not
    # inert at one lucky draw, and text-derived seeding alone would have turned those sweeps into
    # the same run repeated. Setting `random.seed()` before the call no longer reaches the loop, so
    # this is the supported way to ask for a specific stream.
    seed: int | None = None,
) -> dict:
    """Run the closed loop on ``text``; return a structured result dict.

    Keys: ``final`` (humanized text, spans restored), ``iterations``, ``pre``/``post`` score dicts,
    ``similarity``, ``tier``, ``sim_bar``, ``flagged`` (final), and ``stopped`` (why it stopped).
    If no rewriter is available, returns ``{"error": ...}`` without rewriting the text. ``final`` on
    that path is still scrubbed when ``scrub=True`` (the default): the caller asked for hidden
    characters removed, and that request is independent of whether a rewriter turned up.

    ``browser`` (e.g. ``"zerogpt"`` or ``"zerogpt,detecting-ai"``) scores each iteration against free
    web detector(s) instead of local proxies — optimizing against the **max** across real checkers, no
    API key (slow: ~10s each/iter). ``margin`` adds headroom: the loop only declares success when the
    max score is below ``threshold - margin``, so it doesn't stop on a borderline pass that a noisy
    detector might re-flag (the practical fix for detector non-reproducibility).
    """
    if sim_bar is None:
        sim_bar = recommended_bar()

    if not isinstance(text, str):
        # Fuzz-found: bytes input raised 'ord() expected string of length 1' deep inside
        # the surrogate scan. Clean type error naming the contract instead.
        raise TypeError(f"text must be str, got {type(text).__name__}")
    if not isinstance(tier, str):
        # Fuzz-found: tier=["lite"] crashed deep inside load_detectors with
        # "unhashable type: 'list'" — name the contract like the text guard does.
        raise TypeError(f"tier must be str, got {type(tier).__name__}")
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
        # Fuzz-found: a non-numeric threshold (str, None, a list) reached the loop's
        # score comparisons and crashed with "not supported between instances" — the
        # typed API must name the contract like the text/tier guards do.
        raise TypeError(f"threshold must be a number, got {type(threshold).__name__}")

    # Sanitize lone surrogates up front. They are invalid Unicode that arrives from broken
    # file encodings; score_text tolerates them but spaCy's tokenizer and the seed hash both
    # raise UnicodeEncodeError on them. Replace (not strip) so positions and word counts
    # stay aligned with what the caller passed.
    if any(0xD800 <= ord(ch) <= 0xDFFF for ch in text):
        text = text.encode("utf-8", errors="replace").decode("utf-8")

    # Seed the RNG from the INPUT, so a run depends on its text and not on what the process
    # rewrote earlier.
    #
    # `structural.py` draws from the global `random` module in 27 places and nothing seeded it, so
    # the stream carried over between calls. MEASURED, one process, stdlib path, same document,
    # same tier, same max_iters, same rewriter:
    #
    #     scored first                       post 0.4003, 778 chars
    #     scored after two other documents   post 0.4325, 770 chars
    #
    # Same input, different answer, because two other texts had advanced the RNG in between. Every
    # batch number in eval/ therefore depended on iteration order, and no reported figure could be
    # reproduced without replaying the whole sequence that preceded it.
    #
    # Seeded HERE and not inside the rewriter, which matters: best-of-N calls `rw.rewrite()` N
    # times with byte-identical arguments and relies on the stream advancing to get N different
    # candidates. Seeding per rewrite would collapse all N into one draw and silently undo best-of
    # (measured at 33% -> 0% still-flagged). Seeding once per run keeps the draws different from
    # each other while making the whole sequence a function of the input.
    #
    # blake2b rather than `hash()`: string hashing is salted per process by default, which would
    # have reproduced the exact bug this fixes while looking like a fix.
    #
    # The previous state is restored on the way out. A library caller who seeded their own RNG
    # before calling should not find it moved afterwards.
    if seed is not None and seed < 0:
        # `random.seed()` takes the absolute value of an int, so -1 and 1 are one stream, not two.
        # The CLI refuses this before it arrives; refused here too because `untell_text` is the
        # public entry point and a silently aliased seed is worse than a rejected one.
        raise ValueError(f"seed must be 0 or greater, got {seed}")
    effective_seed = (
        seed if seed is not None
        else int.from_bytes(
            hashlib.blake2b(
                text.encode("utf-8", errors="replace"), digest_size=8
            ).digest(),
            "big",
        )
    )
    # Held for the whole run, because the thing being protected is the GLOBAL `random` module.
    # `structural.py` draws from it in 27 places, so seeding it is a process-wide side effect and
    # save/seed/restore is only atomic if nothing else runs in between. MEASURED without the lock,
    # three threads asking for the SAME seed they had just been given serially:
    #
    #     serial, same seed, same text        reproducible
    #     3 threads, attempt 0 / 1 / 2        1/3, 0/3, 1/3 match their serial result
    #     caller's own RNG stream afterwards  changed
    #
    # So `seed=` stopped meaning anything, and a library caller who seeded their own RNG found it
    # moved — the two guarantees the seeding was added for, both lost the moment a second thread
    # appeared. The REST server does not hit this today, but only because every endpoint is
    # `async def` and calls this function directly, so a rewrite runs ON the event loop and blocks
    # every other request; the blocking is what serialises the RNG. That is its own defect, and
    # fixing it (offloading to a threadpool) would have exposed this one.
    #
    # A lock rather than a `random.Random(seed)` instance threaded through the call. The instance
    # is the better answer and it is a 27-site change in structural.py plus its callers, which is
    # not something to do blind — this makes the existing behaviour correct and explicit, and costs
    # nothing today because the only concurrent caller already serialises. What it does cost is
    # parallel rewrites INSIDE one process, which nothing currently asks for.
    with _RNG_LOCK:
        _rng_state = random.getstate()
        random.seed(effective_seed)
        try:
            result = _untell_text(
                text, tier, threshold, max_iters, sim_bar, rewriter, browser, margin, confirm,
                scrub, polish, style, best_of, detector_thresholds, veto_contradictions,
                voice_sample, progress, timings,
            )
        finally:
            random.setstate(_rng_state)
    # Report the stream that produced this result, the way `tier` and `detector_modes` report the
    # other hidden variables a number depends on. Without it a caller holding an output has no way
    # to ask for that output again — the derived seed is not something they can work out, and
    # `--seed` would be a knob you can set but never read back.
    if isinstance(result, dict):
        result.setdefault("seed", effective_seed)
    return result


def _untell_text(
    text: str,
    tier: str,
    threshold: float,
    max_iters: int,
    sim_bar: float,
    rewriter,
    browser: str | list[str] | None,
    margin: float,
    confirm: int,
    scrub: bool,
    polish: bool,
    style: str | None,
    best_of: int,
    detector_thresholds: dict[str, float] | None,
    veto_contradictions: bool,
    voice_sample: str | None,
    progress: bool,
    timings: bool,
) -> dict:
    """The loop body. Split out only so ``untell_text`` can own the seeding above."""

    # Per-phase budget accumulator (issue #27). Always built — the cost is two
    # perf_counter calls per phase call — but only reported when `timings` is set.
    phase: dict[str, float] = {name: 0.0 for name in _PHASE_ORDER}
    _t_start = time.perf_counter()

    # Scrub BEFORE the rewriter is resolved, so the early error returns below cannot ship the
    # payload back. They used to: both of them answer `"final": text` from before this ran, and
    # "no rewriter configured" is the single most likely error there is — it is what every new user
    # without an API key hits. So the default `scrub=True` was silently skipped on the most common
    # path in the function, and the result dict said nothing, unlike the `scrub=False` branch below
    # which at least reports what it left behind.
    #
    # This is the hazard that branch already documents: 701 zero-width characters surviving into
    # `final`. Those characters flipped an AI verdict to clean on 14 of 20 texts until the
    # detectors were fixed to normalise them (Result 67); they no longer move OUR score, but
    # they still travel with the text and another tool may read them differently. A
    # caller who ignores `error` and ships `final` was shipping an evasion payload — and one who
    # pasted the text out of a PDF was shipping soft hyphens that make an unhardened detector read
    # 0.0002 where untell reports 0.9869.
    carried_payload = None
    if scrub:  # strip any hidden watermark / zero-width / homoglyph chars before we start
        from untell.attacks import scrub_hidden

        text = scrub_hidden(text)
    else:
        # `scrub=False` is a legitimate request — the caller asked for their characters left alone —
        # but it is not obvious that the OUTPUT then carries them too. MEASURED on one HC3 answer
        # with a zero-width space between every character: 701 of them survive into `final`, and the
        # result dict said nothing at all. Those characters flipped an AI verdict to clean on 14 of 20
        # texts (Result 62), so a caller shipping this output is shipping an evasion payload they
        # may not know is there. Reported, not removed: removing it would be ignoring the flag.
        from untell.scripts.score import _homoglyph_warning, _invisible_char_warning

        found = [w for w in (_invisible_char_warning(text), _homoglyph_warning(text)) if w]
        if found:
            carried_payload = (
                "scrub=False, so these are still in the output: " + " ".join(found)
            )

    # The language gate belongs HERE, not only in the rewriter, and finding that out is the point.
    #
    # `structural_rewrite` declines Latin-script text that is not English, because every transform
    # it applies is English and left to run it welds English words into German and French. That
    # gate is correct and it does not fire through this loop, because the loop hands the rewriter
    # SENTINEL-MASKED text: locking consumes real words and each `⟦HZxxxx⟧` contributes an "HZ"
    # token to the word count. MEASURED on the same paragraphs, raw against masked:
    #
    #     german   20 words, other-share 0.300  ->  18 words, 0.278   (below the 20-word floor)
    #     spanish  26 words, other-share 0.231  ->  20 words, 0.100   (below the 0.12 floor)
    #     french   26 words, other-share 0.269  ->  unchanged, nothing locked
    #
    # So the fix shipped one commit earlier worked when called directly and was bypassed in
    # production, and its end-to-end test passed for an unrelated reason — composite declining on
    # score. `looks_non_english` now ignores sentinels, which fixes the rewriter-level gate; this
    # one runs on the text as the user supplied it, before anything is masked, and is the
    # authoritative one.
    #
    # It also puts the caveat where a READER can see it. The rewriter's version only logs, which
    # on the REST and MCP surfaces means it reaches the server operator and not the caller — the
    # exact defect this repo has now fixed on six surfaces. `result["warning"]` is already
    # forwarded by all of them.
    non_english = looks_non_english(text)
    language_warning = None
    if non_english:
        language_warning = (
            "this text reads as a Latin-script language other than English, so it was returned "
            "unchanged. Every transform the rewriter applies is English — left to run it welds "
            "English words into the text (measured: an opener prepended to a German sentence, and "
            "'and' inserted as a clause joiner in German and French). The detectors and the tell "
            "catalogue are English-only too, so any score here is not a verdict about this text."
        )
        logging.getLogger(__name__).warning(language_warning)

    # `rewriter` may be a rewriter object OR a name. Every caller in this repo — the CLI, the MCP
    # server, the REST API — resolves the name itself before calling, so the parameter was
    # effectively object-only while being untyped and named after the thing users type on the
    # command line. Passing the obvious `rewriter="composite"` failed deep inside the loop with
    # `AttributeError: 'str' object has no attribute 'rewrite'`, which says nothing about the cause.
    if isinstance(rewriter, str):
        name = rewriter
        # "auto" is the CLI's spelling of "choose for me", and it is in `--rewriter`'s advertised
        # choice list. It was not a name this function accepted, so a caller who read the CLI help
        # and passed `rewriter="auto"` to `untell_text` got "rewriter 'auto' is not available" —
        # about the one value the documentation tells them is the default. Same divergence as the
        # None case below, one layer up: the CLI translates it and nothing else did.
        if name.lower() == "auto":
            # Leave it None and let the auto-selection below run — "auto" is a request FOR that
            # path, not a name to look up. Falling through to the availability check would answer
            # "rewriter 'auto' is not available", which is what it used to do.
            rewriter = None
        else:
            rewriter = get_rewriter(prefer=name)
            # Do NOT fall back to auto-selection here. A caller who names a rewriter wants that one,
            # and silently substituting another produces results attributed to the wrong technique.
            if rewriter is None or not rewriter.available():
                return {"error": _unavailable_reason(name), "final": text}
    rewriter_warning: str | None = None
    rw = rewriter if rewriter is not None else get_rewriter()
    if rw is None:
        # Fall back to the free path rather than refusing. `get_rewriter()` answers "is a HOSTED or
        # local-policy rewriter configured", and None is the right answer to that question — the
        # test pinning it stays. What was wrong is treating that as "no rewriter exists", when
        # `composite` is always available, needs no key, and is the documented zero-dependency path.
        #
        # This was the last surface still doing it. MEASURED on an install with no key:
        #
        #     untell humanize          composite   works
        #     MCP untell()             composite   works
        #     POST /humanize           composite   works
        #     untell_text(text)        None        {"error": "no rewriter configured"}
        #
        # MCP and REST were each changed to default to `composite` for exactly this reason, and
        # their own comments record it as "the flagship tool failed out of the box while the
        # identical CLI invocation worked". The library entry point is the one a Python user reaches
        # for first, and it was the only one left refusing.
        #
        # On stderr once, AND on the result every time. The voice-sample block twelve lines below
        # already made this argument and acted on it: "REST and MCP take the sample as TEXT and said
        # nothing, so the two network surfaces silently used a sample the CLI would have flagged."
        # The same sentence is true here and this branch kept only the stderr half — so a caller who
        # set a key, expected the hosted rewriter and got `composite` learned about it once per
        # process, in a log they may not be reading, on a surface that returns a dict.
        rw = get_rewriter("composite")
        _warn_free_rewriter_fallback()
        rewriter_warning = _free_fallback_warning_text()

    # A voice sample below the documented minimum yields a profile built on too few sentences to
    # mean anything, and the tie-break then runs on noise. `untell humanize --voice-sample` warns
    # about exactly this on stderr; REST and MCP take the sample as TEXT and said nothing, so the
    # two network surfaces silently used a sample the CLI would have flagged. Reported in the
    # result rather than printed, because that is the only channel those callers read.
    #
    # There are TWO floors, not one, and they mean different things. Below
    # `_MIN_VOICE_SAMPLE_WORDS` (20) `_voice_key` returns a constant, so the tie-break does not run
    # at all; below `MIN_SAMPLE_WORDS` (150) it runs on a profile whose AUROC is 0.680. One message
    # covered both, and it was the weaker claim: a 5-word sample — matching DISABLED — was reported
    # as "the voice tie-break is close to arbitrary", which says it ran and was noisy. The stderr
    # warning above gets this right and says "disabled for this run"; the structured field, which is
    # the only channel REST and MCP read, described the case that did not happen.
    voice_warning = None
    if voice_sample:
        from untell.scripts.voice import _WORD, MIN_SAMPLE_WORDS

        n_words = len(_WORD.findall(voice_sample))
        if n_words < _MIN_VOICE_SAMPLE_WORDS:
            voice_warning = (
                f"voice_sample is {n_words} words, under the {_MIN_VOICE_SAMPLE_WORDS} needed to "
                "build a style profile at all — voice matching was DISABLED for this run and the "
                "sample had no effect on the output. Supply at least "
                f"{MIN_SAMPLE_WORDS} words for a profile that measures anything."
            )
        elif n_words < MIN_SAMPLE_WORDS:
            voice_warning = (
                f"voice_sample is {n_words} words; below {MIN_SAMPLE_WORDS} its style profile is "
                "not statistically meaningful, so the voice tie-break is close to arbitrary."
            )

    masked, mapping = lock(text)

    sites = [s.strip() for s in browser.split(",")] if isinstance(browser, str) else (browser or [])
    sites = [s for s in sites if s]
    browser_score = _browser_scorer(sites, mapping, threshold) if sites else None
    if sites and browser_score is None:
        return {
            "error": f"no browser checker available from {sites} — pip install .[browser] && playwright install chromium",
            "final": text,
        }

    def score(masked_text: str) -> dict:
        # Scores the RESTORED text — what a real detector actually sees. The loop carries the masked
        # string so the sentinel-integrity check has something to check, but the masked string is not
        # the artifact anyone is judged on, and the two do not score the same. MEASURED on 14 real
        # human paragraphs (full tier): masking moved max P(AI) by up to 0.1535, mean 0.0317, and
        # flipped the verdict across the 0.30 threshold on 2 of them — there, systematically in the
        # OPTIMISTIC direction, because a sentinel is blander than the citation or number it replaced.
        #
        # That direction is a property of THAT corpus, not of masking. Re-measured on the loop's own
        # output — 12 HC3 answers, composite rewriter, full tier, of which 5 lock anything at all —
        # the gap is smaller and mostly the other way: mean +0.0056, worst +0.0144, and optimistic on
        # only 1 of 5. So the size of the misreport is not the argument for this fix; that the loop
        # was RANKING on a quantity nobody is judged on is.
        #
        # Restoring HERE rather than re-scoring the winner at the end also fixes candidate SELECTION,
        # not just the reported number: `min(near, ...)` and the adoption guard both compare masked
        # scores, so the loop could rank one draft above another on an ordering that does not survive
        # restore, and adopt a candidate that is worse than the text it replaced. It also restores the
        # `post <= pre` invariant by construction, since `pre` is now measured on the same footing.
        #
        # `restore` is a dict lookup per sentinel; the detector pass dominates by orders of magnitude.
        # Browser mode already worked this way — that path being right is what showed this one wrong.
        if browser_score is not None:
            return browser_score(masked_text)
        judged = restore(masked_text, mapping)
        # For MARKUP, the restored text is the SOURCE, and nobody is judged on source. MEASURED on
        # a four-paragraph paper: the raw .tex scores 0.0949 while the prose inside it scores
        # 0.6261, so the loop read 0.09, concluded the document already passed, and returned it
        # untouched — an AI-written paper got a no-op and a green verdict. Detectors judge the
        # prose a reader reads, so that is what is scored. Output is unaffected: the loop still
        # emits valid LaTeX, and this only changes what the score is computed ON.
        #
        # Ordinary prose is untouched by this. MEASURED over 40 HC3+RAID texts (2.8 and 7.0 locked
        # spans on average), stripping markup moves the score by +0.006 and -0.003 — no effect
        # where there is no markup, which is the shape a fix like this has to have.
        if is_latex(judged):
            judged = latex_prose(judged) or judged
        return score_text(judged, tier=tier, threshold=threshold)

    def _passed(s: dict) -> bool:
        # Per-detector gate (optional): every named detector must be below its own threshold.
        # Different detectors calibrate differently, so a single global max is a blunt instrument;
        # `detector_thresholds` lets a caller require e.g. mage<0.40 AND roberta_openai<0.25.
        if detector_thresholds:
            dets = s.get("detectors", {})
            for name, t in detector_thresholds.items():
                v = dets.get(name)
                if isinstance(v, (int, float)) and v >= t:
                    return False
        # Never declare a pass on a vacuous score: if EVERY detector errored this round there is no
        # real signal, and ``max`` is a placeholder (0.5 in browser mode, whatever the ensemble
        # defaulted to locally). Treating that as "passed" would ship un-scored text as clean.
        if s.get("all_checkers_failed"):
            return False
        dets = s.get("detectors", {})
        has_signal = any(
            isinstance(v, (int, float)) for k, v in dets.items() if not str(k).endswith("__error")
        )
        if not has_signal:
            return False
        # Comfortable pass: below threshold by the safety margin (headroom vs detector noise).
        return s["max"] < threshold - margin

    with _timed(phase, "score_pre"):
        pre = score(masked)
    best_masked, best_score = masked, pre
    iters = 0
    rewrites = 0
    # Drafts the MEANING gate refused. Counted separately because the gate `continue`s
    # BEFORE scoring, so a vetoed draft never reaches the score comparison at all — and
    # a caveat that says "every draft scored worse" would be describing a comparison
    # that did not happen. Different cause, different remedy.
    vetoed = 0
    # `rewrites` counts DRAWS, including every candidate the guards rejected — which is a fair
    # reading of "rewrites attempted" but not the question a caller is actually asking. MEASURED:
    # a text the loop could not improve came back byte-identical while the result said
    # `rewrites: 1` (and would say 3 at the default best_of=3), so the only honest indication that
    # nothing happened was `similarity: 1.0`, which reads as a *quality* number, not a no-op flag.
    # This is the same contradiction the `iters` comment below describes, one level up.
    adopted = 0
    stopped = "max_iters"
    for i in range(1, max_iters + 1):
        if _passed(best_score) and similarity(masked, best_masked) >= sim_bar:
            stopped = "passed"
            break
        # Counted AFTER the exit check, so an input that already passes reports 0 iterations rather
        # than 1. It used to be set first, so text that needed no work at all came back claiming a
        # round of rewriting had happened — with rewrites=0 beside it, contradicting itself.
        iters = i
        # Per-iteration progress. `rich_output.progress_iteration` existed, was unit-tested, and was
        # called from nowhere — dead production code carrying test coverage, which is the shape a
        # reachability audit exists to find. A full-tier iteration is several model passes, and up
        # to `max_iters` of them ran with the user seeing nothing until the end.
        #
        # Off by default so library, MCP and REST callers are byte-identical to before; the CLI
        # turns it on for its human-facing path only.
        if progress:
            try:
                from untell.rich_output import progress_iteration

                progress_iteration(i, max_iters, tier, best_score.get("max"))
            except Exception:  # a progress line must never break a run
                pass
        # Targeted feedback: name the specific sentences that read as AI (cheap lite scoring), so the
        # rewriter fixes only those instead of re-rolling the whole text (fewer iters, less drift).
        try:
            from untell.scripts.sentences import score_sentences
            from untell.text_split import split_sentences

            # Score the RESTORED sentences and hand back the MASKED ones. The rewriter matches
            # these strings against the masked text it is given, so they have to stay masked — but
            # scoring them masked points the targeting at the wrong sentences.
            #
            # MEASURED on texts that lock a span, comparing which sentence INDICES get flagged:
            #   stdlib per-sentence path   61 texts, identical on all 61, Jaccard 1.000
            #   GPT-2 per-sentence path    12 texts, differ on 3 (25%), Jaccard 0.833
            # The stdlib agreement is not reassurance — that path is AUROC 0.493, a coin flip, and
            # two coin flips agreeing says nothing. On the model-backed path, which is the one the
            # README markets, masking moves the target a quarter of the time.
            masked_sents = split_sentences(best_masked)
            restored_sents = split_sentences(restore(best_masked, mapping))
            if len(masked_sents) == len(restored_sents):
                with _timed(phase, "targeting"):
                    scored = score_sentences(
                        restore(best_masked, mapping), tier="lite", threshold=threshold
                    )["flagged"]
                flagged_idx = {i for i, s in enumerate(restored_sents) if s in scored}
                flagged = [s for i, s in enumerate(masked_sents) if i in flagged_idx]
            else:
                # Locking changed the sentence split, so the two lists cannot be paired by index.
                # Fall back rather than guess an alignment: a wrong pairing would target sentences
                # the rewriter was not asked about, which is worse than the masked score it replaces.
                with _timed(phase, "targeting"):
                    flagged = score_sentences(best_masked, tier="lite", threshold=threshold)["flagged"]
            best_score = {**best_score, "flagged_sentences": flagged, "style": style}
        except Exception:
            pass
        # Best-of-N: draw `best_of` candidates this round and keep the strongest VALID one. A
        # candidate is valid only if it (a) keeps EVERY sentinel intact — a dropped/altered sentinel
        # would silently lose a locked citation/number on restore, defeating the whole lock — and
        # (b) holds the meaning-similarity gate. Among the valid ones, pick the lowest detector max,
        # and only adopt it if it does not worsen the running best.
        prev_masked = best_masked  # to detect a stalled (no-op) iteration below
        # Collect every VALID draw (sentinels intact + meaning gate held), then select — collecting
        # first is what lets the tells tie-break be applied WITHOUT ever displacing a lower-detector
        # candidate (an online single-best tracker could keep a slightly-worse-but-fewer-tells draw
        # that the strict outer adoption guard then rejects, silently losing a real improvement).
        valid: list[tuple[str, dict, int]] = []  # (candidate, score, tells)
        drew = 0
        # A deterministic rewriter returns byte-identical output for identical input, so extra draws
        # are pure waste — and the waste is the EXPENSIVE part (a full-tier detector pass per draw).
        # Best-of-N only buys anything when the draws actually differ.
        draws = 1 if getattr(rw, "deterministic", False) else max(1, best_of)
        # Issue #25 — how many draws this iteration returned the input byte-identical. Used to
        # (a) skip the ~20-40s gate for each no-op draw and (b) drive the `noop_stall_safe` stop
        # condition at the end of the iteration.
        noop_draws = 0
        for _ in range(draws):
            try:
                with _timed(phase, "rewrite"):
                    candidate = rw.rewrite(best_masked, best_score, threshold)
            except Exception as exc:  # surface the failure rather than silently looping
                if drew == 0:
                    return {
                        "error": f"rewriter failed: {type(exc).__name__}: {str(exc)[:160]}",
                        "final": restore(best_masked, mapping),
                        **({"timings": _timings_dict(phase, _t_start)} if timings else {}),
                    }
                break  # a later draw failed; use the candidates we already have
            drew += 1
            rewrites += 1
            # Issue #25 — no-op draw short-circuit. A draw that returns the input byte-identical is
            # a fixed point for ANY rewriter: its sentinel multiset, meaning-gate verdict and
            # detector score are the incumbent's by definition (same string), so the
            # similarity+NLI-gate+rescore below (~20-40s each on the full tier — the measured
            # majority of the loop's cost on repetitive docs) is pure waste. Keep the draw in
            # `valid` with the incumbent's OWN score+tells so the tells tie-break selection below is
            # byte-identical to having run the full gate on it — a no-op entry can win that
            # tie-break today, and dropping it would change which candidate is adopted on an edge
            # doc. (A byte-identical candidate can never be vetoed: best_masked passed the gate when
            # it was adopted, or is `masked` itself when nothing was adopted, for which sim >= bar.)
            if candidate == best_masked:
                noop_draws += 1
                with _timed(phase, "tells"):
                    # The no-op draw IS the incumbent, so its tells are the incumbent's tells.
                    noop_tells = score_tells(restore(best_masked, mapping)).get("tells", 0)
                valid.append((candidate, best_score, noop_tells))
                continue
            # Multiset compare against the masked source's own sentinels — NOT Counter(mapping), whose
            # dict values ("Smith (2020)", "47") would be read as counts. A valid rewrite reproduces
            # every sentinel exactly as often as it appears in `masked`: no drop, no alter, no dup.
            if Counter(_SENTINEL_RE.findall(candidate)) != Counter(_SENTINEL_RE.findall(masked)):
                continue  # dropped/altered/DUPLICATED a locked span — reject outright
            # Meaning gate. Cosine similarity alone is wrong in BOTH directions: it penalises
            # register change (the primary humanizing move — it rejected 6/6 faithful formal->casual
            # rewrites) while being blind to negation ("runs faster" -> "runs slower" scores 0.974).
            # With NLI available, contradiction + bidirectional entailment do the fidelity judging
            # and similarity is demoted to a gross-drift floor; without it, the strict bar stands.
            # Measured on a fixed probe set: 7/8 faithful admitted and 0/11 bad, vs 2/8 and 4/11.
            # On the MASKED text, deliberately, and the cost of that is measured. The gate compares
            # strings still carrying `⟦HZ…⟧` sentinels, so an embedding model is reading opaque
            # tokens where a citation used to be — and the targeting path one screen up documents a
            # careful masked-vs-restored analysis for exactly this reason, while this comment used
            # to say nothing about it.
            #
            # A constructed citation-dense pair suggested it mattered: three locked spans in two
            # sentences moved similarity 0.8974 -> 0.9304, inflating it, which is the unsafe
            # direction. Real text is not that dense. MEASURED over 38 genuine rewrites of corpus
            # texts that DO lock a span (38 of 50 do, so this is the common case):
            #
            #     similarity masked - restored   mean -0.0014   max +0.0091   min -0.0218
            #     verdict disagreements          1 of 38, and it runs the SAFE way:
            #                                    masked rejected what restored would have admitted
            #
            # So the synthetic probe generalised from a density real documents do not have. Masking
            # is also principled here rather than merely harmless: the sentinel-integrity check
            # above has already proven every locked span appears identically on both sides, so
            # comparing them again adds nothing, and what is left is the prose the rewriter changed.
            with _timed(phase, "similarity"):
                sim = similarity(masked, candidate)
            if veto_contradictions:
                if not meaning_preserved(masked, candidate, sim, sim_bar):
                    vetoed += 1
                    continue
            elif sim < sim_bar:
                vetoed += 1
                continue  # meaning drifted too far from the source
            with _timed(phase, "rescore"):
                cscore = score(candidate)
            # Count tells on the RESTORED candidate, for the same reason `score()` scores the
            # restored text: a sentinel is not what anyone reads, and the tell catalogue's patterns
            # do not match through one. MEASURED over 120 HC3+RAID texts, 91 of which lock at least
            # one span: the masked view disagrees with the restored view on 44% of them, by a mean
            # of 3.33 tells and up to 27 — and the minimum delta is +0, so masking never
            # over-counts, only ever hides tells. The texts that lock spans are the ones carrying
            # citations and numbers, which is exactly the academic register this repo targets, so
            # the tie-break was reading its lowest-quality signal precisely where it matters most.
            #
            # Measured end to end on 14 RAID texts that lock a span, this changes the output not at
            # all: P(AI) 0.2413 and 30.14 tells either way, because the tells term only breaks ties
            # among candidates already within _TELLS_EPS of the best detector score, and that band
            # rarely holds two candidates with different counts. Kept regardless, on the same
            # grounds `score()` above gives for scoring the restored text: the size of the misreport
            # is not the argument, that the loop was RANKING on a quantity nobody is judged on is.
            with _timed(phase, "tells"):
                cand_tells = score_tells(restore(candidate, mapping)).get("tells", 0)
            valid.append((candidate, cscore, cand_tells))
        cand_best, cand_best_score = None, None
        if valid:
            # Primary objective: lowest detector max. Restrict the tells tie-break to the ADOPTABLE
            # set (candidates that would pass the outer guard) so it can never cost a real adoption;
            # if none is adoptable, fall back to the whole set for progress/stall detection.
            # The ADOPTION guard stays on `max` under every mode. A different objective is allowed to
            # reorder the candidates that are already safe; it is not allowed to adopt one that
            # worsens the number the caller is judged on. So `dropout` and `mean` can only ever pick
            # differently among non-worsening drafts — a deliberately conservative test of the
            # hypothesis, and the reason a negative result here would be informative rather than an
            # artefact of a loosened guard.
            adoptable = [v for v in valid if v[1]["max"] <= best_score["max"]]
            pool = adoptable or valid
            # Resampled per iteration, from the loop's own seeded RNG, so a run is reproducible and
            # successive iterations do not rank on the same subset.
            subset = _selection_subset(best_score, random)
            min_score = min(_objective(v[1], subset) for v in pool)
            # Among candidates within the detector noise band of the best, prefer the fewest AI tells
            # (then lowest score as the final deterministic tiebreak).
            #
            # This is a FLAT count, and in practice it is close to a single-category comparison.
            # MEASURED over 80 documents per corpus: `repeated_phrasing` fires on 48 of 80 (HC3) and
            # 61 of 80 (RAID), and where it fires it is 94% (HC3) and 83% (RAID) of the total on
            # average — above 90% in 36 of those 48 HC3 documents. So the tie-break mostly ranks
            # candidates by how much duplicated phrasing they removed.
            #
            # That sounds like a defect and is not, which took two further measurements to
            # establish. It is not costing the other categories anything, because by the time
            # candidates are compared those categories are already gone. Non-repetition tells across
            # 40 documents, source against candidate:
            #
            #     HC3    69 -> 10        RAID   272 -> 65
            #
            # and 61 of RAID's 65 are `repeated_sentence_openers`, which is itself repetition. So a
            # draw with three clichés left to clear does not exist: the flatten and substitution
            # passes remove cliche and ai_vocab outright (100%) and formulaic_transition at 93-97%.
            # After a rewrite, repetition of two kinds IS the residual.
            #
            # Both obvious repairs were tried and neither helps. Evidence-weighting (`_EVIDENCE`,
            # strong 4 / moderate 2 / weak 1) picks a different candidate in 0 of 80 documents —
            # `repeated_phrasing` is itself classed strong, so weighting multiplies the category
            # that already dominates. Per-category capping does change the pick, in 1 of 40 (HC3)
            # and 9 of 40 (RAID), but in none of those does the capped choice carry fewer
            # other-strong tells, because both choices carry zero. It moves the answer without
            # improving it.
            #
            # Left as a flat count on that evidence. The thing to fix is not the ranking function.
            # Same objective as `min_score` above, or the band is drawn around a different quantity
            # than the one that produced its centre — under `mean` that mismatch alone would decide
            # which candidates are considered tied.
            near = [v for v in pool if _objective(v[1], subset) <= min_score + _TELLS_EPS]
            # Never trade a PASS for a lower tell count. The band is +/- _TELLS_EPS (0.02), so when
            # the best candidate sits just under the threshold the band straddles it and a
            # fractionally worse, non-passing candidate with fewer tells wins the tie-break. The
            # loop then has nothing to stop on and burns every remaining iteration before reporting
            # max_iters — having had a passing candidate in hand. Identical shape to the polish
            # adoption bug; the tells preference is only ever a tie-break, never a reason to lose.
            passing = [v for v in near if _passed(v[1])]
            near = passing or near
            # Within the band: fewest AI tells, then — when the caller supplied a sample of their
            # own writing — the draft whose voice sits closest to it, then lowest ensemble MEAN (a
            # candidate that also improves the detectors below the max is genuinely better, and
            # `max` alone is blind to that), then lowest max as the final deterministic tiebreak.
            #
            # Voice sits AFTER tells and never displaces it, so the term can only ever break a tie
            # the loop was otherwise settling arbitrarily. MEASURED on 20 real HC3 texts, choosing
            # among tells-tied drafts: mean voice distance 0.744 -> 0.602 at best_of=3 and
            # 0.718 -> 0.474 at best_of=8, helping 11 and 14 of 20 texts respectively, for a total
            # tells cost of ZERO in both cases. With no sample the key is a constant and selection
            # is byte-identical to before.
            #
            # "Tie" means WITHIN `_TELLS_EPS`, not equal, and the difference is user-visible. `near`
            # holds every candidate whose detector max is within 0.02 of the best, so voice can
            # promote one that scores slightly worse on the detector. MEASURED, same seed on both
            # arms so only the tie-break differs, 12 HC3 texts:
            #
            #     voice distance   4 closer, 0 farther, 8 unchanged
            #     detector max     3 worse: +0.0019, +0.0063, +0.0094 — all inside the band
            #
            # That is the design working, not leaking: the band is defined as detector noise. It is
            # recorded because three user-facing surfaces described this as a tie-break that "never
            # costs evasion", which is true of tells and not of the detector number a caller reads.
            # Those now say what the band costs.
            cand_best, cand_best_score, _ = min(
                near,
                key=lambda v: (
                    v[2],
                    _voice_key(v[0], voice_sample),
                    v[1].get("mean", v[1]["max"]),
                    v[1]["max"],
                ),
            )
        if cand_best is not None and cand_best_score["max"] <= best_score["max"]:
            if cand_best != best_masked:
                adopted += 1
            best_masked, best_score = cand_best, cand_best_score
        if _passed(best_score):
            stopped = "passed"
            break
        # A deterministic rewriter (e.g. surgical word-substitution) fed identical input produces
        # identical output, so once an iteration leaves the working text unchanged, every remaining
        # iteration is a guaranteed no-op. Stop instead of re-running the (often expensive) rewrite
        # for the rest of max_iters. Stochastic rewriters (LLM/policy) have no such flag and keep going.
        if getattr(rw, "deterministic", False) and best_masked == prev_masked:
            stopped = "stalled"
            break
        # Issue #25 — no-op-draw stop condition for rule-based stochastic rewriters (composite).
        # They draw different seeds (so the `deterministic` guard above never fires), but their
        # DRAWS are deterministic given (input, RNG state): once an iteration's every draw returned
        # the input byte-identical AND nothing was adopted, no later draw on the same text can
        # differ — the aggressive end of the intensity sweep fires whenever an eligible item exists,
        # so all-no-op at every swept intensity means there is nothing left to change. Stop instead
        # of re-drawing the remaining iterations as guaranteed no-ops (MEASURED ~9-12 wasted
        # draws/doc on adopting docs). Only when the rewriter advertises `noop_stall_safe`; a T5 /
        # LLM / policy draw CAN differ on the next call, so they are intentionally unflagged.
        if (
            getattr(rw, "noop_stall_safe", False)
            and drew > 0
            and noop_draws == drew
            and best_masked == prev_masked
        ):
            stopped = "stalled_noop"
            break

    # Restore sentinels to get the final human-readable text before any confirm/polish/return.
    final = restore(best_masked, mapping)

    # OUTPUT scrub, and why the input scrub above is not enough (issue #4). The scrub at the top
    # of this function covers the INPUT vector: hidden characters the caller's text carried are
    # gone before lock(), so no restored span can bring them back. It does NOT cover the vector
    # where a REWRITER introduces them — a hosted LLM echoing a zero-width char from its own
    # training, a T5/mt_pivot sample, a local policy's vocabulary. MEASURED before this line with
    # an injecting rewriter (text.replace("leverage", "lever\u200bage")): the zero-width space
    # shipped into `final` with scrub=True and nothing saying so. That is the same evasion
    # payload the input scrub exists to stop, arriving one stage later, so the defense has to run
    # on both sides of the loop. Idempotent and linear; on text the rewriters left clean it is a
    # byte-identical no-op (the scrub's own contract, pinned by test_no_hidden_character_survives_a_scrub).
    #
    # Gated on `scrub` like the input half: `scrub=False` is the caller saying "leave my
    # characters alone", and scrubbing the output would silently violate that — the carried_payload
    # warning above already tells them the chars travel with the result.
    if scrub:
        final = scrub_hidden(final)

    # No re-score of `final` here: `score()` already measured restored text, so `best_score` and the
    # polish comparison below are both on the same footing as the string the caller receives.

    # Reproducibility guard: re-score the winner a few times on the FINAL (restored) text;
    # detectors are noisy and a one-off pass on masked text can re-flag once sentinels are
    # replaced by the real citations/numbers/URLs the detector might key on.
    if stopped == "passed" and confirm > 0:
        for _ in range(confirm):
            with _timed(phase, "rescore"):
                rescore = score(final)
            if rescore["max"] >= threshold - margin:
                best_score = rescore
                stopped = "passed_unconfirmed"
                break

    # Optional cheap CPU polish: surgical word-importance substitution to shave a bit more signal.
    if polish:
        try:
            from untell.attacks import surgical_substitute

            # Optimize against the SAME signal the loop scored against (so the swaps target the real
            # objective), except in browser mode whose composite tier isn't directly scoreable -> lite.
            polish_tier = "lite" if browser_score is not None else tier
            with _timed(phase, "polish"):
                polished = surgical_substitute(final, tier=polish_tier, threshold=threshold)["text"]
            with _timed(phase, "rescore"):
                polished_score = score(polished)
            # Polish on the restored (final) text: verify meaning preserved (vs the original) and
            # that it actually HELPS. Sentinel check is irrelevant — text is already restored.
            # Adopt only on a genuine improvement: an equal-scoring polish spends meaning-similarity
            # for nothing, and since polish optimizes the detector score alone it can raise the AI-tell
            # count while doing it. Ties therefore go to the unpolished text (same no-harm principle as
            # the composite/ensemble selectors); within the detector noise band, tells break the tie.
            better_score = polished_score["max"] < best_score["max"] - _TELLS_EPS
            with _timed(phase, "tells"):
                polished_tells = score_tells(polished).get("tells", 0)
                final_tells = score_tells(final).get("tells", 0)
            tie_but_more_human = (
                abs(polished_score["max"] - best_score["max"]) <= _TELLS_EPS
                and polished_tells < final_tells
            )
            # Never trade a pass for a tie. The tie band is +/- _TELLS_EPS (0.02), so a polished
            # candidate scoring UP TO 0.02 worse is adopted when it carries fewer tells — and if the
            # incumbent sits just under the threshold, that band straddles it. MEASURED: incumbent
            # 0.28 (passing), polished 0.30 with fewer tells, adopted, and the run returned
            # stopped='passed' together with flagged=True and max at the threshold. The loop said it
            # had succeeded and the same result said the text was still flagged.
            un_passes = _passed(best_score) and not _passed(polished_score)
            if (better_score or tie_but_more_human) and not un_passes \
                    and similarity(text, polished) >= sim_bar:
                final, best_score = polished, polished_score
        except Exception as exc:
            # Say it once. Swallowing this silently is correct for a transient failure — polish is
            # optional and the unpolished text is a valid answer — and wrong for a persistent one:
            # a missing similarity model or a broken substitution table disables the whole polish
            # stage on every call, output quality drops, and nothing anywhere says so. That is the
            # same silent-no-op shape as the composite selector that shipped disabled, so it gets
            # the same treatment as a failing ensemble member: one warning, then quiet.
            #
            # Per TYPE, matching `_MEMBER_FAILED` in rewriter/ensemble.py. The guard used to be
            # `if not _POLISH_FAILED` — emptiness, not membership — which let the FIRST exception
            # type (possibly a transient OOM) suppress the warning for every later type, including
            # a persistent one. A set of names whose membership is never checked dedupes nothing;
            # the type is in the message, so it must be the key.
            _name = type(exc).__name__
            if _name not in _POLISH_FAILED:
                _POLISH_FAILED.add(_name)
                logging.getLogger(__name__).warning(
                    "polish stage failed and is being skipped (%s: %s); output is the unpolished "
                    "candidate. This is logged once per process.",
                    _name, str(exc)[:120],
                )

    # Final numbers the caller reads, computed AFTER the loop so each lands in the
    # right budget bucket: the per-sentence re-flag pass is a scoring pass, the
    # reported similarity is a similarity pass, the tells delta is a tells pass.
    with _timed(phase, "rescore"):
        final_flagged = _flagged_sentences_of(final, threshold)
    with _timed(phase, "similarity"):
        final_sim = similarity(text, final)
    with _timed(phase, "tells"):
        tells_delta = _tells_delta(text, final)

    return {
        **({"voice_warning": voice_warning} if voice_warning else {}),
        # Which BACKEND ran, kept separate from `warning`, which is about how to read the numbers.
        # Same shape as `voice_warning` directly above, for the same reason it exists.
        **({"rewriter_warning": rewriter_warning} if rewriter_warning else {}),
        "final": final,
        "iterations": iters,
        # Draws attempted, INCLUDING candidates the sentinel/meaning/score guards threw away.
        "rewrites": rewrites,
        # Draws actually taken up, and whether the caller's text changed at all. `rewrites` alone
        # cannot answer "did anything happen": a rejected draft still counts as an attempt, so an
        # untouched text reports rewrites=3 at the default best_of.
        "adopted": adopted,
        "changed": final.strip() != text.strip(),
        "pre": pre,
        # Recomputed against `final`, not carried out of the loop — see `_flagged_sentences_of`.
        "post": {
            **best_score,
            "flagged_sentences": final_flagged,
            # Same defect as `flagged_sentences` above and fixed in the same place: the loop sets
            # `style` at the top of an iteration and `best_score` is then replaced wholesale when a
            # candidate is adopted, rescored or polished, so the caller was told `None` even when a
            # style demonstrably ran. MEASURED at seed 5, `style="academic"` produced different text
            # from `style=None` — the profile keeps the transitions the neutral one strips — and
            # `post["style"]` was None in both cases, and in the `casual` case too.
            "style": _effective_style(style),
        },
        # Report meaning-preservation vs the true final output, on the RESTORED text in both cases.
        #
        # This used to compare `masked` against `best_masked` whenever polish had not run, on the
        # ground that `best_masked` restores to `final` so the comparison is exact. That is true of
        # the TEXT and false of the NUMBER: a sentinel is a single token standing in for a
        # multi-word span, so both sides share a cheap exact match where the real words would have
        # to be compared, and the figure comes out flattering.
        #
        # MEASURED, reported value minus a fresh `similarity(input, final)`, over documents the loop
        # actually changed:
        #
        #     plain              6 changed   mean +0.0013   worst +0.0040   reported higher 3/6
        #     citation-dense    7 changed   mean +0.0040   worst +0.0155   reported higher 5/7
        #
        # One-directional — never below — and it grows with how much of the document is locked,
        # which is exactly the population that most needs a trustworthy meaning number. The gate's
        # own masked comparison is a separate decision, measured and deliberately kept; this is the
        # figure a caller reads and can reproduce, so it is computed the way they would compute it.
        "similarity": final_sim,
        "tier": best_score.get("tier", tier),
        # The SCORE's own caveat travels with the verdict, not just inside `post`. `carried_payload`
        # covers hidden characters and was the only thing that ever reached this field, so a caller
        # reading the documented top-level `warning` got None while `post["warning"]` said
        #
        #     "no detector produced a score — max/mean are placeholders, not a verdict"
        #
        # MEASURED on Chinese input: `changed=False`, `rewrites=3`, top-level warning None, and a
        # `flagged` boolean computed from placeholder maxima. Same shape as the `scored: False`
        # problem `_bypass_rate` already guards — the information exists on the result and the
        # summary line does not carry it. Composed rather than replaced, so a run can report a
        # scrub payload and a scoring caveat at once.
        # A pinned max is a third caveat that belongs on the same channel. MEASURED at the full
        # tier: 4 documents rewritten, tells/100w 3.80 -> 2.98, and `max` sat at 0.9997 before AND
        # after — so `pre` and `post` are identical to four decimals on text that measurably
        # improved. Over 80 corpus texts the max reaches >=0.999 on 100% of HC3 AI text against 0%
        # of human text, so this is the ordinary case for the input this tool exists for, not an
        # edge. The CLI says it too; a JSON, MCP or REST caller reads only this field.
        **({"warning": _merge_warnings(
            language_warning, carried_payload, best_score.get("warning"),
            _saturated_max_caveat(pre, best_score), _unknown_style_warning(style),
            _nothing_adopted_warning(rewrites, adopted, final.strip() != text.strip(), vetoed,
                                     stopped == "stalled_noop"),
            _inert_budget_warning(max_iters, best_of),
        )}
           if (language_warning or carried_payload or best_score.get("warning")
               or _saturated_max_caveat(pre, best_score) or _unknown_style_warning(style)
               or _nothing_adopted_warning(rewrites, adopted, final.strip() != text.strip(),
                                           vetoed, stopped == "stalled_noop")
               or _inert_budget_warning(max_iters, best_of))
           else {}),
        "sim_bar": sim_bar,
        "quality_metric": method(),
        # WHICH meaning gate ran. `quality_metric` names the similarity backend but says nothing
        # about the NLI axis, and that axis is the one that catches inversions. MEASURED on
        # "The new build runs faster" -> "...runs slower", similarity 0.983 against a 0.76 bar:
        #
        #     NLI available    meaning_preserved -> False   (rejected)
        #     NLI unavailable  meaning_preserved -> True    (ADMITTED)
        #
        # Same result shape either way, so a run on an install without the NLI extra could adopt a
        # meaning-inverted rewrite and look identical to one where the gate was fully active. Same
        # class as `detector_modes` on the score result: a guarantee that depends on an optional
        # dependency has to say whether it was in force.
        "meaning_gate": _meaning_gate_mode(veto_contradictions),
        "flagged": best_score["flagged"],
        "stopped": stopped,
        # AI tells before and after, because on a hard corpus they are the only thing that moves.
        #
        # MEASURED on 4 HC3 documents at full tier: `max` gained +0.0000 on 4 of 4 — three of five
        # detectors saturate there, with or without `mage` — while tells fell 4->0, 1->0 and 1->0.
        # The result reported the flat number and not the fall, so a user on real AI text saw
        # "P(AI) 1.00 -> 1.00, delta 0" and concluded the run did nothing, when the machine-writing
        # markers the catalogue exists to find had been removed.
        #
        # This repository already treats tells as a first-class signal: `untell tells` is a
        # command, the loop uses them to break ties between candidates within the detector noise
        # band, and `humanness` is built from them. They were reported by every surface except the
        # one that does the rewriting.
        #
        # stdlib-only and cheap, so this costs the same on every tier and cannot fail the run: a
        # broken counter must not take the humanized text down with it.
        **tells_delta,
        **_stronger_rewriter_hint(rw, best_score["flagged"], best_score.get("tier", tier)),
        # Per-phase budget (issue #27): only when asked, so every existing caller's payload is
        # byte-identical. Order is execution order — score_pre first, total last — which is what
        # the regression test pins as "phase order sane".
        **({"timings": _timings_dict(phase, _t_start)} if timings else {}),
    }


def _tells_delta(source: str, final: str) -> dict:
    """AI-tell counts before and after, for the result dict.

    On a saturating corpus this is the only thing that moves: MEASURED on 4 HC3 documents at full
    tier, `max` gained +0.0000 on 4 of 4 while tells fell 4->0, 1->0 and 1->0. `_saturated_max_caveat`
    already WARNS about that case in prose; this puts the numbers on the result so a JSON, MCP or
    REST caller can read them rather than parse a sentence.

    Never raises. A broken counter must not take the humanized text down with it, so a failure
    returns no keys at all rather than zeros — zeros would read as "no tells", which is a claim.
    """
    try:
        from untell.scripts.tells import score_tells

        before = int(score_tells(source).get("tells", 0))
        after = int(score_tells(final).get("tells", 0))
    except Exception:  # noqa: BLE001 — a diagnostic must never break the run
        return {}
    return {"tells_before": before, "tells_after": after}


def _meaning_gate_mode(veto_contradictions: bool) -> str:
    """Which fidelity checks were actually in force this run.

    ``"nli"`` — the full conjunction: retained quantities and claim strength (mechanical, always
    on), plus the similarity floor, contradiction veto, bidirectional entailment and the
    predicate-argument role check.
    ``"nli (no role check)"`` — everything above except the role check, because spaCy's model is not
    installed. Worth its own value rather than being folded into ``"nli"``: over 49 real rewrites
    the role check supplied 2 of the 3 vetoes the conjunction produced, so this is the larger of the
    two model-backed halves going missing, and it went missing silently.
    ``"similarity-only (...)"`` — the model-backed half is absent, because NLI could not be
    imported or the veto was switched off. The mechanical checks still run; what is missing is
    every check that needs the model, and those are the ones that catch an INVERSION. Measured:
    "runs faster" -> "runs slower" scores similarity 0.983 against a 0.76 bar and is admitted here,
    rejected under ``"nli"``. The name says "similarity-only" because similarity is the only thing
    still judging the *semantics* — not because it is the only check running.

    **What that costs on real output, rather than on a probe.** 49 genuine rewrites from
    `structural`, `surgical` and `composite` over 20 HC3 and RAID documents, every gate evaluated
    separately:

        numerals 0    certainty 0    polarity 0    similarity 0
        contradiction 1    role_swap 2    entailment 0

    Two gates did all the vetoing, and both are the model-backed ones. The other six are insurance
    against a rewriter that does not exist on the free path — the polarity note above says the same
    thing about its own zero.

    All three vetoed candidates scored similarity **0.969, 0.981, 0.981** against a 0.76 bar, so a
    lean install admits **3 of 3** — not "most", and not at a similarity a reader would find
    suspicious. Under ``"similarity-only"`` this conjunction has never rejected anything on measured
    corpus output.
    """
    from untell.scripts.entailment import available as _nli_available

    if not veto_contradictions:
        return "similarity-only (veto disabled)"
    try:
        if not _nli_available():
            return "similarity-only (NLI unavailable)"
        # The role check is the OTHER optional dependency, and this field used to ignore it: with
        # spaCy's model absent `role_swap` returns None — correctly, since an unavailable check must
        # not become a veto — and the mode still said "nli", the value documented above as "the full
        # conjunction ... plus the predicate-argument role check". MEASURED over 49 real rewrites,
        # role_swap supplied 2 of the 3 vetoes the whole conjunction produced, so the missing half
        # is the larger half.
        from untell.scripts.roles import parser_available

        return "nli" if parser_available() else "nli (no role check)"
    except Exception:  # a diagnostic must never break the run it describes
        return "unknown"


# Rewriters measured as unable to clear real AI text at the full tier. Naming them explicitly
# rather than testing "not neural" so a new backend does not silently inherit the advice.
_WEAK_ON_REAL_TEXT = frozenset({"composite", "surgical", "structural", "targeted"})


def _stronger_rewriter_hint(rw, flagged: bool, tier: str) -> dict:
    """Tell the caller a stronger free rewriter exists, when the one they used is known to fail.

    MEASURED with `untell-ceiling --dataset hc3 --n 6 --tier full --best-of 3 --max-iters 5` —
    the SAME six texts through both, pre_mean_max identical at 0.9994, only `--rewriter` changed:

                        post    flagged   hc3_roberta   similarity (mean/worst)
        composite      0.8052    1.00        0.7559        0.986 / 0.965
        neural         0.5017    0.50        0.4072        0.941 / 0.884

    The repo documented composite's row as the free tier's ceiling and called hc3_roberta a wall
    immovable by meaning-preserving rewriting. It is a property of the default rewriter: half the
    samples clear with a different free one, and the "immovable" detector falls to 0.407. A user
    who runs the default, gets "still flagged" and is told nothing has no way to discover that.

    Deliberately not a silent default change. `neural` needs the `.[full]` extra (a ~850MB T5
    download), costs several times the wall-clock, and trades meaning — and it is not uniformly
    better per detector, losing on roberta_openai (0.300 against composite's 0.124) while winning
    the `max` that decides the verdict. That is the user's call, so this states the numbers and
    lets them make it.

    THOSE NUMBERS NO LONGER REPRODUCE (re-measured 2026-08-11). Running the command in the table
    above, `UNTELL_DISABLE_MAGE=1 untell-ceiling --dataset hc3 --n 6 --tier full --best-of 3
    --max-iters 5 --rewriter composite`:

                        post    flagged   hc3_roberta
        recorded       0.8052    1.00        0.7559
        re-measured    0.9995    1.00        0.9992     (rewrote 6/6)

    Not the rewriter. It rewrote every sample, and the opener-dose change made in this session was
    ruled out directly — 0.9996 at the current dose against 0.9994 at the old one. The reason no
    rewriter reaches 0.8052 on this corpus is that the detectors are pinned:

        mage 1.0000 on 6/6      hc3_roberta 0.9992-0.9993 on 6/6      roberta_openai >=0.999 on 5/6

    Three of five saturate, so `max` cannot move whether mage is excluded or not. Ten commits have
    touched `untell/detectors/` since these figures were recorded, several of them closing scoring
    shortcuts — `hc3_roberta` read punctuation spacing as authorship, and collapsing newlines still
    moves `roberta_openai` by up to 0.59 on its own. A rewrite that "beat" a detector through one of
    those is not beating it any more, which is the most likely reading: the figures were true when
    taken and measured evasion of an artifact that has since been removed.

    The user-facing string therefore no longer quotes the composite/neural comparison as a fact
    about what they will get. `neural` is still worth offering — it is a genuinely different lever
    (see the repetition measurements in rewriter/composite.py) — but the size of the win is
    unverified on current code, and one run would not establish it anyway: `neural` is 4x as
    variable as composite, so it needs `--repeats >= 3`.
    """
    if not flagged or tier != "full":
        return {}
    name = getattr(rw, "name", None)
    if name not in _WEAK_ON_REAL_TEXT:
        return {}
    return {
        "suggestion": (
            f"still flagged with rewriter={name!r}. Try --rewriter neural: it paraphrases whole "
            f"clauses, which is the one axis a rule-based rewrite cannot reach (measured 2-4x less "
            f"repeated phrasing). It needs the .[full] extra, is several times slower, and trades "
            f"meaning (similarity ~0.94 against ~0.99). How much it lowers the score on YOUR text "
            f"is not something this tool can promise — the recorded comparison no longer "
            f"reproduces, and neural varies enough between runs that a single run proves little. "
            f"Measure it with `untell-ceiling --rewriter neural --repeats 3`."
        )
    }


def _render(result: dict) -> str:
    if "error" in result:
        return f"ERROR: {result['error']}"
    pre, post = result["pre"], result["post"]
    lines = ["# untell result", ""]
    lines.append(f"tier={result['tier']}  iterations={result['iterations']}  stopped={result['stopped']}")
    lines.append(f"max P(AI): {pre['max']:.3f} -> {post['max']:.3f}  (threshold {post['threshold']})")
    lines.append(f"similarity: {result['similarity']:.3f} (bar {result['sim_bar']}, {result['quality_metric']})")
    gate = result.get("meaning_gate", "unknown")
    lines.append(f"meaning gate: {gate}")
    if gate.startswith("similarity-only"):
        # The similarity bar alone admits inversions — measured 0.983 for "runs faster" ->
        # "runs slower" against a 0.76 bar. A user reading a passing result deserves to know the
        # check that would have caught that was not running.
        lines.append(
            "  WARNING: the contradiction/entailment/roles checks did NOT run. Quantities and "
            "claim strength were still checked, but semantics rested on similarity alone, which "
            "admits inversions (measured 0.983 for \"runs faster\" -> \"runs slower\" against a "
            "0.76 bar). Install torch + transformers for the full fidelity gate."
        )
    # AI tells and the result's own warning, which this renderer dropped.
    #
    # `rich` is an EXTRA, so this is what `pip install untell` prints — and it showed the number
    # with none of the caveats attached to it. MEASURED on the stdlib path: the rich table shows an
    # "AI tells" row and the score's warning, and this path showed neither, so the install with
    # fewer dependencies was also the one told less about how far to trust the answer.
    #
    # The tells pair matters most where `max` cannot move: on a saturating corpus it is the only
    # before/after that changes at all.
    before, after = result.get("tells_before"), result.get("tells_after")
    if isinstance(before, int) and isinstance(after, int):
        lines.append(f"AI tells: {before} -> {after}  ({after - before:+d})")
    if result.get("warning"):
        lines.append(f"\nNOTE: {result['warning']}")

    lines.append("\nper-detector (pre -> post):")
    for name in pre.get("detectors", {}):
        if "__error" in name:
            continue
        p = pre["detectors"].get(name)
        q = post["detectors"].get(name)
        if isinstance(p, (int, float)) and isinstance(q, (int, float)):
            lines.append(f"  {name}: {p:.3f} -> {q:.3f}")
    if result.get("suggestion"):
        # Above the text, not below it: a run that ends still flagged is the one case where the
        # next action matters more than the output, and a note under a 200-word paragraph is a
        # note nobody reads.
        lines.append("\nNOTE: " + result["suggestion"])
    lines.append("\n--- humanized text ---\n" + result["final"])
    return "\n".join(lines)


_REWRITER_NAMES = [
    "auto", "surgical", "structural", "composite", "targeted", "neural", "ensemble",
    "max", "t5_paraphrase", "mt_pivot", "base", "local",
]

# Shipped defaults, in one place so the config layer has something to fall back TO and the tests
# have something to compare against.
_CLI_DEFAULTS: dict[str, object] = {
    "tier": "full",
    "threshold": DEFAULT_THRESHOLD,
    "max_iters": 5,
    "rewriter": "composite",
    "style": None,
    "best_of": 3,
}

_CHOICES = {
    "tier": ["lite", "full", "heavy", "commercial"],
    "rewriter": _REWRITER_NAMES,
    "style": list(STYLE_NAMES),
}


def _config_defaults() -> dict[str, object]:
    """Shipped defaults, overridden by untell.yaml / [tool.untell] / UNTELL_* env.

    A value from a config file is NOT trusted into argparse unchecked. `add_argument(choices=...)`
    validates what the user types on the command line, not the `default=`, so a stray
    `tier: fulll` would sail past argparse and surface later as an empty detector list — a config
    typo turning into a mystery at scoring time. Anything outside the allowed set is dropped with a
    warning naming both the value and the alternatives, exactly as untell.config does for a file it
    cannot parse.
    """
    from untell import config

    out = dict(_CLI_DEFAULTS)
    for key, shipped in _CLI_DEFAULTS.items():
        try:
            value = config.get(key, shipped)
        except Exception:  # a broken config must never stop the CLI from starting
            continue
        if value is None or value == shipped:
            continue
        allowed = _CHOICES.get(key)
        if allowed is not None and value not in allowed:
            print(
                f"[untell] ignoring configured {key}={value!r}: not one of {', '.join(allowed)}. "
                f"Using {shipped!r}.",
                file=sys.stderr,
            )
            continue
        # Numeric RANGES need the same treatment as categorical choices, for the same reason the
        # docstring above gives — and they were missed. `add_argument(type=...)` runs on what the
        # user TYPES, never on a `default=`, so the range parsers added for the command line did
        # nothing for the other two input channels. Measured, with the bounds already enforced on
        # the CLI:
        #
        #     --threshold 50            rejected
        #     UNTELL_THRESHOLD=50       accepted
        #     untell.yaml threshold: 50 accepted
        #
        # A threshold of 50 means nothing can ever be flagged, and max_iters of -5 means the loop
        # does no work and still reports a pass. Same nonsense, three channels, one of them
        # guarded.
        bounds = _CONFIG_RANGES.get(key)
        if bounds is not None:
            low, high = bounds
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                numeric = None
            if numeric is None or not (low <= numeric <= high):
                shown_low = int(low) if isinstance(shipped, int) else low
                shown_high = int(high) if isinstance(shipped, int) else high
                print(
                    f"[untell] ignoring configured {key}={value!r}: outside "
                    f"{shown_low}..{shown_high}. Using {shipped!r}.",
                    file=sys.stderr,
                )
                continue
        out[key] = value
    return out



# --- argument ranges, shared with the REST surface -----------------------------------------------
# The API validates these and the CLI did not, so the same nonsense was a 422 over HTTP and a clean
# exit 0 on the command line. Measured:
#
#     --threshold 50      exit 0 — scores live in [0,1], so nothing can ever be flagged
#     --threshold -1      exit 0 — everything is flagged, always
#     --best-of 0         exit 0
#     --max-iters -5      exit 0 — the loop runs no iterations and reports a pass
#     --best-of 10000     ran until it was killed at 200s, genuinely generating candidates
#
# None of those are things a person means. The bounds are read off `untell._api_bounds` rather than
# repeated here, because two copies of a range is how the surfaces drifted in the first place —
# `tests/test_surface_parity.py` compares defaults and vocabularies and did not think to compare
# ranges, which is exactly why this survived. They used to be read off `untell.api_server` until
# that module imported FastAPI at top level, which cost every CLI run a full REST-stack import
# (MEASURED: `import untell.scripts.run` 0.757s -> 0.23s after moving the values to the
# stdlib-only `untell/_api_bounds.py`); the API's pydantic fields now consume the same tuples.
def _bounds(name: str, fallback: tuple[float, float]) -> tuple[float, float]:
    try:
        from untell import _api_bounds

        # Kept in the type the API declared rather than cast to float. A float cannot hold an int
        # above 2**53, and `_Seed` is bounded at 2**64 - 1: casting it rounded it UP to 2**64, so the
        # CLI advertised "between 0 and 18446744073709551616" — a bound one past the one the REST
        # surface enforces, and a number that is not the one anybody wrote. Probability bounds are
        # declared as floats and stay floats, so nothing else moves.
        low, high = getattr(_api_bounds, name)
        if low is None or high is None:
            return fallback
        return low, high
    except Exception:  # noqa: BLE001 — the bounds module is stdlib-only; any failure means the CLI must still run
        return fallback


def _ranged(name: str, cast, api_name: str, fallback: tuple[float, float]):
    low, high = _bounds(api_name, fallback)

    def parse(raw: str):
        try:
            value = cast(raw)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{name} must be a number, got {raw!r}") from None
        if not (low <= value <= high):
            shown_low = int(low) if cast is int else low
            shown_high = int(high) if cast is int else high
            raise argparse.ArgumentTypeError(
                f"{name} must be between {shown_low} and {shown_high}, got {value}"
            )
        return value

    parse.__name__ = name
    return parse


_PROBABILITY = _ranged("threshold", float, "_Probability", (0.0, 1.0))
_ITERS = _ranged("max-iters", int, "_Iters", (1, 100))
_BEST_OF = _ranged("best-of", int, "_BestOf", (1, 32))
_MARGIN = _ranged("margin", float, "_Probability", (0.0, 1.0))
# 0 is a MEANING here — "do not re-confirm" — so the low bound is 0, not 1. The MCP
# surface bounds this to 0..32 and the REST body models it as ge=0/le=32; the CLI took a
# bare int, so `--confirm -5` was accepted and `range(-5)` simply never ran, silently
# turning the guard off. Derived from the same API type as the others.
_CONFIRM = _ranged("confirm", int, "_Confirm", (0, 32))
# `--seed` is sold as "fix the random stream", and its help recommends it for comparing two
# settings on ONE stream. Negative values break that: CPython's `random.seed()` takes the ABSOLUTE
# value of an int argument, so -1 and 1 are the same stream. MEASURED end to end on the lite path,
# seven seeds through `untell_text`: -1 and 1 returned byte-identical output at post=0.0731 while
# 0, 2, 7 and 12345 each returned something different. A user comparing -1 against 1 to see whether
# a flag mattered would read that as "the flag changed nothing", which is the exact confusion the
# help text exists to prevent. The high bound matches the range of the text-derived default
# (`blake2b`, 8 bytes), so the flag can name any stream the tool picks on its own.
_SEED = _ranged("seed", int, "_Seed", (0, 2**64 - 1))
# `untell sentences --top`, the same shape one more time. A bare int made `order[:top]` a Python
# negative slice, so `--top -1` flagged n-1 sentences — MEASURED at 2 of 3, more than `--top 1`
# flags — and `--top -5` flagged 0, which reads as "nothing to rewrite". 0 is a meaning here too
# ("flag none"), so the low bound is 0. The high bound is
# above any reachable sentence count (MAX_INPUT_CHARS caps a document near 650 sentences), so it
# refuses absurd input without ever refusing a usable value: `--top 99` still means "flag all".
_TOP = _ranged("top", int, "_Top", (0, 10_000))

# The same bounds, keyed by config name, for values that arrive as argparse DEFAULTS rather
# than as typed arguments — a config file or a UNTELL_* variable. Derived from the API types
# through the same helper, so there is still one definition.
_CONFIG_RANGES: dict[str, tuple[float, float]] = {
    "threshold": _bounds("_Probability", (0.0, 1.0)),
    "max_iters": _bounds("_Iters", (1, 100)),
    "best_of": _bounds("_BestOf", (1, 32)),
}

def build_parser() -> argparse.ArgumentParser:
    """The `untell humanize` argument parser.

    Split out of ``main`` so the defaults it declares can be read without running the CLI. The REST
    and MCP surfaces restate several of them (tier, rewriter, best_of) and had drifted to weaker
    values; the tests now compare against this parser rather than against a hand-copied constant.
    """
    # Defaults come from untell.config, which layers UNTELL_* env vars over untell.yaml /
    # pyproject.toml [tool.untell] over the value passed here. Until this call existed the module
    # documented that lookup order and participated in none of it: it was imported by no CLI, no
    # server and no library path, so writing an untell.yaml changed nothing at all. A CLI flag
    # still wins, because argparse only falls back to `default` when the flag is absent.
    cfg = _config_defaults()

    parser = argparse.ArgumentParser(prog="untell-humanize", description="Run the headless untell loop.")
    parser.add_argument("text", nargs="?", help="text to untell (or --file / stdin)")
    parser.add_argument("--file", "-f", help="read text from this file")
    parser.add_argument("--tier", default=cfg["tier"], choices=["lite", "full", "heavy", "commercial"])
    parser.add_argument("--threshold", "-t", type=_PROBABILITY, default=cfg["threshold"])
    parser.add_argument("--max-iters", type=_ITERS, default=cfg["max_iters"])
    parser.add_argument(
        "--max-rounds",
        type=_ITERS,
        default=None,
        help="alias for --max-iters (rounds of rewrite). Overrides --max-iters when set.",
    )
    parser.add_argument(
        "--detector-thresholds",
        default=None,
        help='per-detector pass gate as a JSON object, e.g. \'{"mage":0.40,"roberta_openai":0.25}\'. '
        "Every named detector must fall below its own threshold to declare a pass (in addition to "
        "the global --threshold). Lets you hold the hardest detectors to a stricter bar.",
    )
    parser.add_argument(
        "--browser",
        help="score each iteration against free web detector(s) instead of local proxies — "
        "comma-separated (e.g. 'zerogpt,detecting-ai', or 'auto' for the first available); the "
        "loop must beat the MAX across all. "
        "Real checkers, no key, but slow (~10s each/iter). Needs .[browser] + playwright.",
    )
    parser.add_argument(
        "--margin",
        type=_MARGIN,
        default=0.0,
        help="safety headroom: only stop when max score < threshold - margin (e.g. 0.10), so a "
        "borderline pass a noisy detector might re-flag keeps iterating. Default 0.",
    )
    parser.add_argument(
        "--confirm",
        type=_CONFIRM,
        default=0,
        help="after a pass, re-score the result N more times; keep 'passed' only if every re-scan "
        "still clears (guards against a noisy detector re-flagging). Default 0.",
    )
    parser.add_argument(
        "--rewriter",
        choices=_REWRITER_NAMES,
        default=cfg["rewriter"],
        help="'composite' = structural + surgical chained ($0, best free path, DEFAULT); "
        "'ensemble'/'max' = run composite + mt_pivot + neural and keep the per-input detector-lowest "
        "(strongest free path; >= any single method; needs .[full] for the neural/mt members); "
        "'neural' = T5 paraphrase + structural + surgical (needs .[full]; "
        "moves detectors far more than rule-based alone; falls back to composite without the deps); "
        "'structural' = sentence-level transforms ($0); "
        "'surgical' = word-substitution rewriter ($0); "
        "'t5_paraphrase' = free neural paraphraser alone (needs .[full]); "
        "'mt_pivot' = round-trip machine translation (needs .[full]; best on watermarked input); "
        "'base' = untuned base model, no LoRA adapter (A/B baseline; needs .[full] + UNTELL_POLICY_BASE); "
                "'local' = trained LoRA policy (single-pass rewriter; needs UNTELL_POLICY_DIR + .[train] for peft); "
                "'auto' = hosted-LLM / local-policy rewriter (needs a key or UNTELL_POLICY_DIR).",
    )
    parser.add_argument("--no-scrub", action="store_true", help="skip stripping hidden watermark/unicode chars from input")
    parser.add_argument("--polish", action="store_true", help="add a cheap surgical word-substitution polish pass at the end")
    parser.add_argument(
        "--style",
        # Derived from the single source in rewriter/prompts.py rather than restated — this list
        # was one of three hand-maintained copies, and the MCP one had already drifted.
        choices=STYLE_NAMES,
        default=cfg["style"],
        help=f"bias the rewrite toward a writing style/voice ({len(STYLE_NAMES)} modes)",
    )
    parser.add_argument(
        "--voice-sample",
        metavar="FILE",
        help="file of YOUR writing (150+ words). Among candidate rewrites that already tie on AI "
        "tells, prefer the one whose sentence length, rhythm and comma rate sit closest to it. "
        "Breaks a tie among candidates whose detector max is within the 0.02 noise band, so it never costs TELLS and can cost up to 0.02 of detector score — measured 0.009 at worst over 12 texts, on 3 of them. See untell-voice.",
    )
    parser.add_argument(
        "--best-of",
        type=_BEST_OF,
        default=cfg["best_of"],
        help="draw N candidate rewrites per iteration and keep the best valid one (sentinels intact + "
        "meaning gate, lowest detector max, fewest AI tells within the noise band). Default 3 — the "
        "free rewriters are randomized, so extra draws are pure upside: measured, best-of-3 selection "
        "took roberta 0.523->0.080 mean where a single draw reached only ~0.30. Use 1 for speed.",
    )
    parser.add_argument(
        "--seed",
        type=_SEED,
        default=None,
        help="fix the random stream for this run. Unset derives it from the text, so the same "
        "input already gives the same output regardless of what was rewritten before it. Pass an "
        "int to compare two settings on ONE stream — the honest way to ask whether a flag changed "
        "anything, since two runs that differ only by chance look exactly like a flag that works.",
    )
    parser.add_argument("--json", action="store_true", help="emit the full result as JSON")
    parser.add_argument(
        "--timings",
        action="store_true",
        help="report the per-phase wall-clock budget: score_pre / rewrite / rescore (plus "
        "targeting, similarity, tells, polish) with each phase's share of the total. The loop's "
        "cost is the rewrite phase (measured 462.7s of 467.4s on a 1MB doc, 99.5%% of the loop), "
        "so a regression in any single phase is invisible without the split. With --json the "
        "timings dict rides inside the result payload instead of the one-line summary.",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="print a unified-style before/after of the humanization, showing only changed "
        "lines (deletions red, additions green). With --json, emit the machine-readable "
        "hunk payload instead. Built on the preserve-lock explainer: the payload also "
        "reports how many locked spans survived the rewrite byte-for-byte.",
    )
    return parser


def _diff_payload(text: str, result: dict) -> dict:
    """The `--diff` payload: a line diff of original vs final, annotated by the lock explainer.

    Building on the explain machinery rather than only difflib: `explain_spans` is the
    single source of truth `lock()` itself uses (pinned by test_explain.py), so the
    spans reported here are exactly the spans the loop froze. `locks_preserved` then
    checks the restore contract — every frozen span must survive byte-for-byte — on
    the surface a reader looks at to see what changed.
    """
    from untell.rich_output import humanize_diff
    from untell.scripts.explain import explain_spans

    return humanize_diff(text, result.get("final", ""), locked_spans=explain_spans(text))


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()
    args = build_parser().parse_args(argv)

    if args.file:
        from untell.scripts.io_utils import read_file_or_exit

        text = read_file_or_exit(args.file)  # .txt / .docx / .pdf
    elif args.text:
        text = args.text
    else:
        # None means stdin is a terminal. Reading it would block until the user sent EOF, with no
        # prompt and no output — the command looks hung when what they wanted was the usage line.
        from untell.scripts.io_utils import read_stdin_or_none

        piped = read_stdin_or_none()
        if piped is None:
            print(json.dumps({"error": "no input: pass text, --file PATH, or pipe to stdin"}))
            return 2
        text = piped
    if not text.strip():
        print(json.dumps({"error": "empty input"}))
        return 2

    rewriter = None
    if args.rewriter in (
        "surgical", "structural", "composite", "targeted", "neural", "ensemble", "max",
        "t5_paraphrase", "mt_pivot",
    ):
        from untell.rewriter import get_rewriter

        # --style is honoured by the rule-based path via structural's register profiles
        # (contraction injection + how much of the formal->plain map applies), and by the hosted-LLM
        # rewriter via its prompt. The purely word-level backends have no register knob to turn, so
        # say so rather than accept a flag that does nothing there.
        _STYLE_AWARE = {"composite", "structural", "targeted", "neural", "ensemble", "max", "auto"}
        if args.style and args.rewriter not in _STYLE_AWARE:
            print(
                f"[untell] --style {args.style!r} has no effect with --rewriter {args.rewriter}: "
                "that backend has no register knob. Use --rewriter composite (default) or auto.",
                file=sys.stderr,
            )
        rewriter = get_rewriter(prefer=args.rewriter)
        if rewriter is None:
            print(
                f"ERROR: --rewriter {args.rewriter} is unavailable — it needs the '.[full]' extra "
                "(pip install -e '.[full]'). Try --rewriter composite for the zero-dependency path."
            )
            return 1
    elif args.rewriter == "base":
        from untell.rewriter.local_policy import LocalPolicyRewriter

        rewriter = LocalPolicyRewriter(use_adapter=False)
        if not rewriter.available():
            print(
                "ERROR: --rewriter base needs torch + transformers (pip install -e '.[full]'); "
                "set UNTELL_POLICY_BASE to a HF model id to override the default base."
            )
            return 1
    elif args.rewriter == "local":
        # The trained LoRA policy (use_adapter=True) — the CLI half of the A/B pair whose other
        # half is "base". Unlike the free-name branch above, this one constructs the rewriter
        # directly: `get_rewriter(prefer="local")` falls through to a hosted key when the policy
        # is unavailable, and a caller who NAMED the policy wants that policy, not a substitute.
        # A missing optional dep (peft/torch/transformers) exits 2 with a message naming the
        # package and the extra that installs it, instead of the ModuleNotFoundError traceback
        # the unguarded import inside _load used to leak (issue #34).
        from untell.rewriter.local_policy import LocalPolicyRewriter

        rewriter = LocalPolicyRewriter()
        reason = rewriter.unavailable_reason()
        if reason is not None:
            message = f"--rewriter local is unavailable: {reason}"
            if args.json:
                # Same contract as every other error this command can return: under `--json`
                # stdout is JSON, because a caller parsing stdout cannot special-case one branch.
                print(json.dumps({"error": message}))
            else:
                print(f"ERROR: {message}", file=sys.stderr)
            return 2

    voice_sample = None
    if args.voice_sample:
        from untell.scripts.io_utils import read_file_or_exit
        from untell.scripts.voice import _WORD, MIN_SAMPLE_WORDS

        # `read_file_or_exit` already prints one line and exits 2 for a missing path, a directory,
        # an unreadable file or a binary one — the same treatment `--file` gets, rather than a
        # second bespoke handler here that catches only OSError and would miss the ValueError the
        # explicit guards now raise.
        voice_sample = read_file_or_exit(args.voice_sample)
        # Warn rather than refuse: a short sample still ranks candidates, it just ranks them on
        # noisier statistics, and silently ignoring the flag the user passed would be worse.
        n_words = len(_WORD.findall(voice_sample))
        if n_words < MIN_SAMPLE_WORDS:
            print(
                f"WARNING: --voice-sample is {n_words} words; below {MIN_SAMPLE_WORDS} its style "
                f"statistics are dominated by which sentences happened to be included."
            )

    detector_thresholds = None
    if args.detector_thresholds:
        try:
            detector_thresholds = {k: float(v) for k, v in json.loads(args.detector_thresholds).items()}
        except (ValueError, AttributeError) as exc:
            # Same contract as every other error this command can return: under `--json` the answer
            # is JSON, because a caller parsing stdout cannot special-case one branch. This printed
            # `ERROR: ...` as plain text on stdout regardless of the flag, so `json.loads(stdout)`
            # raised on a bad `--detector-thresholds` value — the one situation where the caller
            # most needs to read what was wrong with their argument.
            message = (
                f"--detector-thresholds must be a JSON object of name:number pairs ({exc})."
            )
            if args.json:
                print(json.dumps({"error": message}))
            else:
                print(f"ERROR: {message}", file=sys.stderr)
            return 2

    result = untell_text(
        text,
        tier=args.tier,
        threshold=args.threshold,
        max_iters=args.max_rounds if args.max_rounds is not None else args.max_iters,
        rewriter=rewriter,
        browser=args.browser,
        margin=args.margin,
        confirm=args.confirm,
        scrub=not args.no_scrub,
        polish=args.polish,
        style=args.style,
        best_of=args.best_of,
        detector_thresholds=detector_thresholds,
        voice_sample=voice_sample,
        seed=args.seed,
        # Only on the human-facing path: --json must stay parseable, so a progress line printed to
        # stdout ahead of the payload would corrupt it for every scripted caller. `--diff --json`
        # is a scripted caller too — same rule, same flag.
        progress=not args.json,
        timings=args.timings,
    )
    if args.diff:
        if "error" in result:
            # Same contract as every other error this command can return: under `--diff --json`
            # stdout is JSON, because a caller parsing stdout cannot special-case one branch.
            if args.json:
                print(json.dumps(result, ensure_ascii=True, indent=2))
            else:
                print(f"ERROR: {result['error']}")
            return 1
        if args.timings and not args.json:
            # stdout is the diff; the budget line is context, so it goes above it.
            print(_timings_report(result.get("timings")))
        payload = _diff_payload(text, result)
        if args.json:
            print(json.dumps(payload, ensure_ascii=True, indent=2))
        else:
            # No ImportError guard needed: rich_output imports unconditionally and degrades
            # to plain text internally when rich is absent (the `_RICH` flag).
            from untell.rich_output import print_humanize_diff

            print_humanize_diff(payload)
        return 0
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    elif "error" in result:
        print(f"ERROR: {result['error']}")
        if args.timings:
            # A failed run still has a budget (the failure is often IN a phase); stderr keeps
            # stdout a single parseable error line for anyone scraping it.
            print(_timings_report(result.get("timings")), file=sys.stderr)
    else:
        # Rich output when available, otherwise the standard render
        try:
            from untell.rich_output import print_humanize_result

            print_humanize_result(
                original=text,
                final=result.get("final", ""),
                pre_score=result.get("pre", {}),
                post_score=result.get("post", {}),
                iterations=result.get("iterations", 0),
                stopped=result.get("stopped", "unknown"),
                warning=result.get("warning"),
                tells_before=result.get("tells_before"),
                tells_after=result.get("tells_after"),
            )
        except ImportError:
            # Narrowed from `except Exception`. The fallback exists for a missing `rich`, which is
            # an ImportError; catching everything meant a TypeError from a wrong argument list
            # rendered as a normal degraded run, and it silently swallowed exactly that mistake
            # while this warning was being wired in. A bug in the renderer should be loud.
            print(_render(result))
        if args.timings:
            print(_timings_report(result.get("timings")))
    return 1 if "error" in result else 0


if __name__ == "__main__":
    raise SystemExit(main())
