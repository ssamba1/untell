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
import json
import logging
import sys
from collections import Counter

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
from untell.scripts.preserve import _SENTINEL_RE, lock, restore
from untell.scripts.quality import method, recommended_bar, similarity
from untell.scripts.score import DEFAULT_THRESHOLD, score_text
from untell.scripts.tells import score_tells

# Detector-score noise band. Among best-of-N candidates whose detector max is within this of each
# other, prefer the one with FEWER AI tells — a strictly more human-reading rewrite at no cost to
# evasion. Detectors anti-correlate with human-ness on some text, so tells are the better tie-breaker.
_TELLS_EPS = 0.02


def _voice_key(masked_candidate: str, voice_sample: str | None) -> float:
    """Distance from ``voice_sample``'s writing style, or 0.0 when no sample was given.

    Sentinels are stripped first: ``⟦HZ0007⟧`` is one token to the word regex but stands for a span
    of arbitrary length, so leaving them in would score every candidate against a phantom vocabulary
    and skew the sentence-length and comma statistics that voice matching is built on.

    Returning a constant with no sample keeps the surrounding ``min`` key byte-identical to its
    previous behaviour, so the default path is untouched rather than merely unlikely to differ.
    """
    if not voice_sample:
        return 0.0
    from untell.scripts.voice import voice_distance

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
) -> dict:
    """Run the closed loop on ``text``; return a structured result dict.

    Keys: ``final`` (humanized text, spans restored), ``iterations``, ``pre``/``post`` score dicts,
    ``similarity``, ``tier``, ``sim_bar``, ``flagged`` (final), and ``stopped`` (why it stopped).
    If no rewriter is available, returns ``{"error": ...}`` without modifying the text.

    ``browser`` (e.g. ``"zerogpt"`` or ``"zerogpt,detecting-ai"``) scores each iteration against free
    web detector(s) instead of local proxies — optimizing against the **max** across real checkers, no
    API key (slow: ~10s each/iter). ``margin`` adds headroom: the loop only declares success when the
    max score is below ``threshold - margin``, so it doesn't stop on a borderline pass that a noisy
    detector might re-flag (the practical fix for detector non-reproducibility).
    """
    if sim_bar is None:
        sim_bar = recommended_bar()
    # `rewriter` may be a rewriter object OR a name. Every caller in this repo — the CLI, the MCP
    # server, the REST API — resolves the name itself before calling, so the parameter was
    # effectively object-only while being untyped and named after the thing users type on the
    # command line. Passing the obvious `rewriter="composite"` failed deep inside the loop with
    # `AttributeError: 'str' object has no attribute 'rewrite'`, which says nothing about the cause.
    if isinstance(rewriter, str):
        name = rewriter
        rewriter = get_rewriter(prefer=name)
        # Do NOT fall back to auto-selection here. A caller who names a rewriter wants that one, and
        # silently substituting another produces results attributed to the wrong technique.
        if rewriter is None or not rewriter.available():
            return {
                "error": f"rewriter {name!r} is not available — check the name (see `untell --check` "
                "for the installed list) or install its extra",
                "final": text,
            }
    rw = rewriter if rewriter is not None else get_rewriter()
    if rw is None:
        return {
            # Name the library form too. `get_rewriter()` with no preference returns None unless an
            # API key is configured, so a caller of `untell_text(text)` — with no CLI in sight —
            # was told to pass a command-line flag they cannot pass.
            "error": "no rewriter configured — pass rewriter='composite' (or --rewriter composite "
            "on the CLI): free, $0, no key. Otherwise set ANTHROPIC_API_KEY / OPENAI_API_KEY / "
            "UNTELL_POLICY_DIR",
            "final": text,
        }

    if scrub:  # strip any hidden watermark / zero-width / homoglyph chars before we start
        from untell.attacks import scrub_hidden

        text = scrub_hidden(text)

    # A voice sample below the documented minimum yields a profile built on too few sentences to
    # mean anything, and the tie-break then runs on noise. `untell humanize --voice-sample` warns
    # about exactly this on stderr; REST and MCP take the sample as TEXT and said nothing, so the
    # two network surfaces silently used a sample the CLI would have flagged. Reported in the
    # result rather than printed, because that is the only channel those callers read.
    voice_warning = None
    if voice_sample:
        from untell.scripts.voice import _WORD, MIN_SAMPLE_WORDS

        n_words = len(_WORD.findall(voice_sample))
        if n_words < MIN_SAMPLE_WORDS:
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
        return score_text(restore(masked_text, mapping), tier=tier, threshold=threshold)

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

    pre = score(masked)
    best_masked, best_score = masked, pre
    iters = 0
    rewrites = 0
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
        # Targeted feedback: name the specific sentences that read as AI (cheap lite scoring), so the
        # rewriter fixes only those instead of re-rolling the whole text (fewer iters, less drift).
        try:
            from untell.scripts.sentences import score_sentences

            best_score = {
                **best_score,
                "flagged_sentences": score_sentences(best_masked, tier="lite", threshold=threshold)["flagged"],
                "style": style,
            }
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
        for _ in range(draws):
            try:
                candidate = rw.rewrite(best_masked, best_score, threshold)
            except Exception as exc:  # surface the failure rather than silently looping
                if drew == 0:
                    return {"error": f"rewriter failed: {type(exc).__name__}: {str(exc)[:160]}", "final": restore(best_masked, mapping)}
                break  # a later draw failed; use the candidates we already have
            drew += 1
            rewrites += 1
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
            sim = similarity(masked, candidate)
            if veto_contradictions:
                if not meaning_preserved(masked, candidate, sim, sim_bar):
                    continue
            elif sim < sim_bar:
                continue  # meaning drifted too far from the source
            cscore = score(candidate)
            valid.append((candidate, cscore, score_tells(candidate).get("tells", 0)))
        cand_best, cand_best_score = None, None
        if valid:
            # Primary objective: lowest detector max. Restrict the tells tie-break to the ADOPTABLE
            # set (candidates that would pass the outer guard) so it can never cost a real adoption;
            # if none is adoptable, fall back to the whole set for progress/stall detection.
            adoptable = [v for v in valid if v[1]["max"] <= best_score["max"]]
            pool = adoptable or valid
            min_score = min(v[1]["max"] for v in pool)
            # Among candidates within the detector noise band of the best, prefer the fewest AI tells
            # (then lowest score as the final deterministic tiebreak).
            near = [v for v in pool if v[1]["max"] <= min_score + _TELLS_EPS]
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

    # Restore sentinels to get the final human-readable text before any confirm/polish/return.
    final = restore(best_masked, mapping)

    # No re-score of `final` here: `score()` already measured restored text, so `best_score` and the
    # polish comparison below are both on the same footing as the string the caller receives.

    # Reproducibility guard: re-score the winner a few times on the FINAL (restored) text;
    # detectors are noisy and a one-off pass on masked text can re-flag once sentinels are
    # replaced by the real citations/numbers/URLs the detector might key on.
    if stopped == "passed" and confirm > 0:
        for _ in range(confirm):
            rescore = score(final)
            if rescore["max"] >= threshold - margin:
                best_score = rescore
                stopped = "passed_unconfirmed"
                break

    # Optional cheap CPU polish: surgical word-importance substitution to shave a bit more signal.
    polished_applied = False
    if polish:
        try:
            from untell.attacks import surgical_substitute

            # Optimize against the SAME signal the loop scored against (so the swaps target the real
            # objective), except in browser mode whose composite tier isn't directly scoreable -> lite.
            polish_tier = "lite" if browser_score is not None else tier
            polished = surgical_substitute(final, tier=polish_tier, threshold=threshold)["text"]
            polished_score = score(polished)
            # Polish on the restored (final) text: verify meaning preserved (vs the original) and
            # that it actually HELPS. Sentinel check is irrelevant — text is already restored.
            # Adopt only on a genuine improvement: an equal-scoring polish spends meaning-similarity
            # for nothing, and since polish optimizes the detector score alone it can raise the AI-tell
            # count while doing it. Ties therefore go to the unpolished text (same no-harm principle as
            # the composite/ensemble selectors); within the detector noise band, tells break the tie.
            better_score = polished_score["max"] < best_score["max"] - _TELLS_EPS
            tie_but_more_human = (
                abs(polished_score["max"] - best_score["max"]) <= _TELLS_EPS
                and score_tells(polished).get("tells", 0) < score_tells(final).get("tells", 0)
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
                polished_applied = True
        except Exception:
            pass

    return {
        **({"voice_warning": voice_warning} if voice_warning else {}),
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
        "post": best_score,
        # Report meaning-preservation vs the true final output. Pre-polish, ``best_masked`` restores to
        # ``final`` so the locked-text similarity is exact; polish rewrites the restored text (sentinels
        # already gone), so compare the scrubbed original against the actual final instead of stale.
        "similarity": similarity(text, final) if polished_applied else similarity(masked, best_masked),
        "tier": best_score.get("tier", tier),
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
        **_stronger_rewriter_hint(rw, best_score["flagged"], best_score.get("tier", tier)),
    }


def _meaning_gate_mode(veto_contradictions: bool) -> str:
    """Which fidelity checks were actually in force this run.

    ``"nli"`` — the full conjunction: retained quantities and claim strength (mechanical, always
    on), plus the similarity floor, contradiction veto, bidirectional entailment and the
    predicate-argument role check.
    ``"similarity-only (...)"`` — the model-backed half is absent, because NLI could not be
    imported or the veto was switched off. The mechanical checks still run; what is missing is
    every check that needs the model, and those are the ones that catch an INVERSION. Measured:
    "runs faster" -> "runs slower" scores similarity 0.983 against a 0.76 bar and is admitted here,
    rejected under ``"nli"``. The name says "similarity-only" because similarity is the only thing
    still judging the *semantics* — not because it is the only check running.
    """
    from untell.scripts.entailment import available as _nli_available

    if not veto_contradictions:
        return "similarity-only (veto disabled)"
    try:
        return "nli" if _nli_available() else "similarity-only (NLI unavailable)"
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
    """
    if not flagged or tier != "full":
        return {}
    name = getattr(rw, "name", None)
    if name not in _WEAK_ON_REAL_TEXT:
        return {}
    return {
        "suggestion": (
            f"still flagged with rewriter={name!r}. MEASURED on the same six real AI texts at "
            f"this tier: composite ends at 0.805 with 0% clearing, neural at 0.502 with 50% "
            f"clearing (hc3_roberta 0.756 vs 0.407). Try --rewriter neural — it needs the .[full] "
            f"extra, is several times slower, and trades meaning (similarity ~0.94 against ~0.99)."
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
    "max", "t5_paraphrase", "mt_pivot", "base",
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
        out[key] = value
    return out


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

    parser = argparse.ArgumentParser(prog="untell-loop", description="Run the headless untell loop.")
    parser.add_argument("text", nargs="?", help="text to untell (or --file / stdin)")
    parser.add_argument("--file", "-f", help="read text from this file")
    parser.add_argument("--tier", default=cfg["tier"], choices=["lite", "full", "heavy", "commercial"])
    parser.add_argument("--threshold", "-t", type=float, default=cfg["threshold"])
    parser.add_argument("--max-iters", type=int, default=cfg["max_iters"])
    parser.add_argument(
        "--max-rounds",
        type=int,
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
        "comma-separated (e.g. 'zerogpt,detecting-ai'); the loop must beat the MAX across all. "
        "Real checkers, no key, but slow (~10s each/iter). Needs .[browser] + playwright.",
    )
    parser.add_argument(
        "--margin",
        type=float,
        default=0.0,
        help="safety headroom: only stop when max score < threshold - margin (e.g. 0.10), so a "
        "borderline pass a noisy detector might re-flag keeps iterating. Default 0.",
    )
    parser.add_argument(
        "--confirm",
        type=int,
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
        "Only ever breaks a tie, so it never costs evasion or naturalness. See untell-voice.",
    )
    parser.add_argument(
        "--best-of",
        type=int,
        default=cfg["best_of"],
        help="draw N candidate rewrites per iteration and keep the best valid one (sentinels intact + "
        "meaning gate, lowest detector max, fewest AI tells within the noise band). Default 3 — the "
        "free rewriters are randomized, so extra draws are pure upside: measured, best-of-3 selection "
        "took roberta 0.523->0.080 mean where a single draw reached only ~0.30. Use 1 for speed.",
    )
    parser.add_argument("--json", action="store_true", help="emit the full result as JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()
    args = build_parser().parse_args(argv)

    if args.file:
        from untell.scripts.io_utils import read_file

        text = read_file(args.file)  # .txt / .docx / .pdf
    elif args.text:
        text = args.text
    else:
        text = sys.stdin.read()
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

    voice_sample = None
    if args.voice_sample:
        from untell.scripts.io_utils import read_file
        from untell.scripts.voice import _WORD, MIN_SAMPLE_WORDS

        try:
            voice_sample = read_file(args.voice_sample)
        except OSError as exc:
            print(f"ERROR: could not read --voice-sample file: {exc}")
            return 2
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
            print(f"ERROR: --detector-thresholds must be a JSON object of name:number pairs ({exc}).")
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
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    elif "error" in result:
        print(f"ERROR: {result['error']}")
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
            )
        except Exception:
            print(_render(result))
    return 1 if "error" in result else 0


if __name__ == "__main__":
    raise SystemExit(main())
