"""Ensemble detector scoring — the skill's eyes on the text.

Loads every detector available at the requested tier, scores the text with each, and emits
JSON the skill (Claude) reads as feedback:

    {
      "tier": "lite",
      "detectors": {"perplexity_burstiness": 0.71, ...},
      "max": 0.71,          # the proxy the loop drives below threshold (multi-detector evasion)
      "mean": 0.71,
      "threshold": 0.30,          # what the rewrite LOOP drives toward
      "verdict_threshold": 0.45,  # the calibrated bar `flagged` is decided on
      "flagged": true       # max >= verdict_threshold => report this to the user
    }

``flagged`` is NOT the loop's stop condition. It compares against ``verdict_threshold``, which is
raised on the stdlib perplexity path, while ``threshold`` stays where the rewriter is optimising.
Between the two there is a band where ``max >= threshold`` and ``flagged`` is still ``false``: keep
rewriting there if there is budget, but do not tell the user their text is flagged, because it is
not. Drive the loop on ``max < threshold`` and report ``flagged``.

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

# RUN DIRECTLY (`python .../untell/scripts/score.py`) rather than imported as part of the package,
# put the directory that *contains* the package on sys.path so `import untell` resolves regardless
# of the current working directory.
#
# This block sat BELOW the `from untell...` imports, where it could never run: the import raised
# `ModuleNotFoundError: No module named 'untell'` first, so the bootstrap was unreachable code.
# Every developer machine hides it, because an editable install puts `untell` on sys.path anyway —
# it only appears on a bare interpreter, which is exactly the zero-dependency path the skill
# installer creates and the README leads with. CI caught it on both the Linux and Windows installer
# jobs; running the same command inside a venv with the package installed passes.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

from untell.detectors.base import _TIER_RANK, load_detectors, resolved_tier  # noqa: E402
from untell.text_split import fold_unicode_spaces  # noqa: E402

logger = logging.getLogger(__name__)


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
    out = []
    for t in texts:
        one = _score_with_detectors(detectors, _truncate(t), tier, threshold)
        dropped = _truncation_warning(t)
        if dropped:
            one["warning"] = (
                f'{dropped} Also: {one["warning"]}' if one.get("warning") else dropped
            )
        out.append(one)
    return out


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


def _truncation_warning(text: str) -> str | None:
    """Say when the verdict is about a PREFIX of what was handed in.

    `_truncate` silently returns `text[:50_000]`, so a longer document gets a number about its
    first 50,000 characters presented as a number about the document. MEASURED on a 67,200-char
    input: `score_text` returns a max identical to the first 50,000 characters scored alone, to
    machine precision — the last 26% contributes nothing and nothing said so.

    Two things made it worth a caveat rather than a shrug. `score_tells` does NOT truncate, so the
    same document reports 10,774 tells against the scorer's view of 8,010 — two surfaces of the
    same tool describing different documents. And the rewrite loop rewrites the WHOLE text while
    scoring the prefix, so `post` is a verdict on 74% of what it hands back.

    The REST surface rejects oversized input with a 422 instead, which is the other reasonable
    answer; the CLI and the Python API cannot refuse work a caller has already asked for, so they
    say what they did.
    """
    normalised = _normalise_ws(text)
    if len(normalised) <= _MAX_INPUT_CHARS:
        return None
    dropped = len(normalised) - _MAX_INPUT_CHARS
    return (
        f"scored the first {_MAX_INPUT_CHARS:,} characters only — {dropped:,} more "
        f"({dropped / len(normalised):.0%} of the text) were not seen by any detector. The tell "
        f"catalogue is NOT truncated, so a tells count for this text covers more of it than this "
        f"score does."
    )


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
#
# THE 17% ABOVE IS A POOLED NUMBER, and the lite warning further down this file quotes 30% for what
# looks like the same quantity. Both are right; they differ because they are measured on different
# corpora, which is not something a reader can work out from two figures 200 lines apart.
# Re-measured per corpus, n=100 paired texts each, stdlib path forced:
#
#     corpus    FP > 0.30   FP > 0.45   TP > 0.45
#     HC3          64%         30%         83%
#     RAID         59%         10%         54%
#     MAGE         46%          6%         46%
#
# HC3 at n=100 reproduces the warning's 64%/30% exactly, and pooling HC3 with RAID lands near the
# 17% recorded above. Nothing is stale; "the" false-positive rate of this cut simply does not exist
# independently of the corpus.
#
# What the table does show, and the FP-only view hid: the cautious cut costs most of the AI side
# away from HC3. TP falls from 83% to about half, so on RAID or MAGE this path clears roughly one
# AI text in two — the same failure the lite warning now reports from the other end. That is still
# the right trade here (a false accusation is the worse error, and the loop optimises against the
# low threshold regardless) but it is a trade, not a free win.
#
# At n=40 the HC3 figures came out 52%/18% rather than 64%/30%. Same corpus, same code, first 40
# pairs instead of first 100 — a reminder that these percentages carry a sampling error wide enough
# to swallow the gap that prompted the whole re-measurement.
#
# MARKDOWN SCAFFOLDING LOWERS THIS PATH FURTHER, systematically rather than by corpus luck. The
# same prose wrapped in a heading, three list items and a fenced code block — prose untouched, only
# structure added — over 10 HC3 documents:
#
#     scoring             mean max   flagged at 0.30   cleared at the 0.45 verdict cut
#     flat                  0.5747        10/10                    —
#     wrapped               0.3101         6/10                   9 of 9
#     prose blocks only     0.4624        10/10                    —
#
# A technical writer working in markdown is therefore under-flagged on the path a clean install
# runs, and the last row names the cause: this module scores the RAW document, scaffolding
# included, while `sentences.py` already splits with `layout.blocks()` first because scaffolding is
# not prose. Scoring the prose blocks restores every flag.
#
# THE MARKDOWN IS NOT THE MECHANISM, which the first version of this note implied. Separating the
# two, same 8 documents:
#
#     flat                          0.5804   8/8 flagged
#     scaffolding + blank lines     0.3039   4/8
#     scaffolding, no blank lines   0.3039   4/8      <- identical, so blank lines are not it
#     blank lines only              0.3128   2/8      <- and scaffolding is not it either
#
# Either transform alone produces nearly the whole drop and they do not compound. What they share
# is SHORT SEGMENTS: a heading, a list item and a one-sentence paragraph are all short, and half of
# this path's score is burstiness — the variation in sentence length — so re-segmenting the text
# re-computes the spread it is scored on.
#
# The DIRECTION is a property of the document, not of the transform, which a mean hides. On 12 HC3
# documents paragraph splitting moved the score down 12 times out of 12 (mean -0.2616, largest
# -0.3912) — but a short hand-written fixture of five long, uniform sentences moved the other way,
# 0.5331 -> 0.6627. Splitting raises the spread when the sentences were uniform and lowers it when
# they were already varied. "Structure makes text look more human" is therefore the corpus
# behaviour and not a rule, and a test asserting the direction on a synthetic fixture fails.
#
# Checked against the alternatives rather than assumed: hard wrapping at 60 columns, double spaces
# after full stops, leading indentation, tab indentation, CRLF endings, trailing spaces and
# collapsing to one long line all move the mean by EXACTLY 0.0000 over the same documents.
# Whitespace normalisation absorbs them. Segment structure is the one axis that moves this score.
#
# WHICH MEANS THE LOOP'S OWN GAIN ON THIS PATH RIDES LARGELY ON SEGMENTATION. The rewriter splits
# and merges sentences as part of its job, and that is the same axis. Over 16 HC3 documents at one
# seed, correlating the score improvement against what changed:
#
#     corr(gain, sentences added)   +0.79
#     corr(gain, tells removed)     +0.30
#     corr(tells removed, added)    -0.18      <- the two are nearly independent
#
# Tells do fall — 19->15, 30->26, 4->0 on individual documents — so the rewriter is doing real
# work. But on this path the number that MOVES is mostly tracking how the text was cut into
# sentences, not how much machine phrasing was removed.
#
# The full tier cannot arbitrate. Its gain is exactly 0.0000 on 4 of 4 documents because three of
# five detectors saturate at 1.0000, so there is no movement there to attribute either way.
#
# Limits, since this is a correlation: n=16, one corpus, one seed, one rewriter. It says where to
# look, not what to conclude.
#
# THE MIXED DOCUMENT IS THE CASE THIS PATH CANNOT SEE. A 207-word AI section inside 567 words of
# human writing, scored whole:
#
#     position of the AI block      stdlib      full tier
#     alone, no filler              0.6239        1.0000
#     at the start                  0.2657        1.0000
#     in the middle                 0.2657        1.0000
#     at the end                    0.2657        0.9999
#     (human filler alone)          0.2586        0.0936
#
# On the stdlib path the AI section is invisible — 0.2657 is below both the 0.30 loop threshold and
# the 0.45 verdict cut, and it barely moves off the human filler's own 0.2586. Position makes no
# difference because both terms are document-wide aggregates. The full tier flags it wherever it
# sits, which is what `windowed_max` is for.
#
# THE TWO TIERS THEN FAIL IN OPPOSITE DIRECTIONS on that document, which is worth knowing before
# recommending either. Running the loop on it:
#
#     tier      what happens
#     stdlib    rewrites=0, changed=False — the diluted 0.2657 is under the 0.30 threshold, so the
#               loop declares "passed" and the AI section stays exactly as it was
#     full      changed=True, 6 draws — and it edits BOTH halves at similar rates: 10 of 13 human
#               sentences survive verbatim (77%) against 5 of 7 AI sentences (71%)
#
# The full tier's behaviour follows from sentence-level targeting precision of 0.444 (see
# `sentences.py`): half the flagged spans are human writing, so half the edits land there. Meaning
# is still held — the human half measured 0.9929 similarity before and after — so what a user loses
# is their own phrasing, not their content.
#
# Neither is a defect with a local fix. The first is dilution, the second is the detectors not
# separating sentences on this corpus; both are measured limits rather than mistakes.
#
# This is the shape a real user brings: a mostly-human document with a generated paragraph in it.
# NOT a bug to fix by windowing this path — that was measured and rejected, and the note in
# `perplexity_burstiness.score` records why: windowing took FPR from 30% to 90% on 3-paragraph
# documents while buying no true positives, because burstiness across a document is exactly the
# quantity windows destroy. The honest answer is the tier, not the window.
#
# NOT changed here. Switching to block-scoring moves every stdlib figure in this repository — the
# 64%/30% above, the per-corpus table, and the perplexity midpoints, which were fitted against
# raw-document distributions — so it needs its own measurement pass rather than a drive-by edit.
# The full tier is unaffected: 6 of 6 documents stayed at exactly 1.0000 when wrapped, so the
# model-backed detectors see straight through the scaffolding.
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
    result = _score_with_detectors(load_detectors(tier), _truncate(text), tier, threshold)
    # Prepended, not appended. The ordering note further down keeps rare and actionable caveats
    # first and the standing ones last; "you got a number about a quarter less than you sent" is
    # the rarest and most actionable of them.
    dropped = _truncation_warning(text)
    if dropped:
        result["warning"] = (
            f'{dropped} Also: {result["warning"]}' if result.get("warning") else dropped
        )
    return result


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
# RE-DERIVED, same command and corpus, and the human column is now far worse:
#
#     words   human flagged (then -> now)
#         5      98% -> 100%
#        10      62% ->  88%
#        20      40% ->  80%
#        40      28% ->  98%
#        80      17% ->  78%
#
# One detector accounts for essentially all of it. At 80 words, per detector on the human half:
#
#     mage 70%   perplexity_burstiness 15%   roberta_openai 8%   fast_detectgpt 2%   hc3_roberta 2%
#
# The ensemble takes `max`, so mage alone sets the ensemble's false-positive rate. And mage is not
# uniformly bad — it is bad on SHORT text specifically, non-monotonically so:
#
#     mage on human text   20w 57%   40w 100%   80w 63%   160w 27%   200w 17%   full 27%
#
# 100% at 40 words against 17% at 200. So the short-text warning below is right and understates its
# own cause: the problem is not that short text is hard for the ensemble in general, it is that the
# strongest member of the ensemble is worst exactly where the ensemble is weakest, and `max`
# propagates it. Left as a measurement rather than a change — excluding mage below some length is a
# tier-composition decision with its own trade, and the abstention this comment introduced already
# tells a caller not to trust the number.
#
# At five words a human paragraph and an AI paragraph are indistinguishable, and the API answers
# "a" with P(AI) = 0.9987 and flagged=True. `humanness()` already refuses to answer below five
# words; the primary scoring path did not, and it is the one behind /score, /tells and the CLI.
#
# The verdict itself is left alone deliberately. `max` is the raw ensemble output and callers store
# and compare it; silently zeroing or withholding it would break them for a reason they cannot see.
# What was missing is the thing the lite-tier stdlib path already does — say, with the measured
# number, that this configuration is not one to trust.
# RE-MEASURED 2026-08-11 BY NATURAL LENGTH, and the two bands a user is most likely to hit are
# understated by roughly 3x. Bucketing 120 HC3 human texts by their OWN word count rather than
# truncating longer ones:
#
#     10-20 words   86% flagged        (this table says <=20 -> 40%)
#     20-40 words   90% flagged        (this table says <=40 -> 28%)
#     40-80 words   70%
#     80-160 words  52%
#     160+ words    23%
#
# The bands are cumulative, so the <=40 band spans the two rows at 86% and 90% — it should read
# near 88%, not 28%. The direction is the one that matters: this string exists to tell a caller
# their verdict is unreliable, and it is currently reassuring them at three times the rate it
# should.
#
# NOT rewritten here, for a methodological reason that has to be settled first. These figures come
# from naturally-short texts — complete short answers — while the originals were taken over "40 HC3
# pairs at this threshold" and may have been TRUNCATED longer ones. A truncated 20-word excerpt is a
# fragment and a naturally 20-word answer is not, and the detectors do not treat them alike (see the
# whole-sentence padding note in roles.py for the same trap). Replacing measured numbers with
# differently-measured numbers would swap one unstated method for another.
#
# Corpus-scoped as well, like every other false-positive figure in this repo: the same sweep over
# RAID human text gives 5% at 80-160 words and 4% above 160, against HC3's 52% and 23%. Whatever
# replaces these bands has to say which corpus it describes.
# SETTLED 2026-08-11 by measuring BOTH ways. Neither reproduces the old numbers, so they were not
# a different-but-valid methodology — they were stale. 40 HC3 human texts (mean 212 words):
#
#     band   old      truncated to N words   naturally <= N words
#       5    98%           100%              (no natural texts this short)
#      10    62%            85%              (n=1, not quotable)
#      20    40%            85%              71%  (n=14)
#      40    28%           100%              86%  (n=51)
#
# Only the 5-word band survived. Everything below it understated by two to three and a half times,
# in the same direction: this string exists to tell a caller their verdict is unreliable, and it was
# reassuring them instead.
#
# Ranges rather than points, deliberately. The two methods disagree because they measure different
# things — a 20-word truncation of a 212-word answer is a fragment, a naturally 20-word answer is a
# complete short reply — and both are things a user might paste. A range says "this is unreliable"
# more honestly than a false precision, which is the whole job of the sentence it appears in.
# Truncated figures are the upper bound, natural the lower; the 5 and 10 rows carry the truncated
# number alone because natural HC3 text does not go that short.
# RE-MEASURED 2026-08-13 with the scoring path PINNED, which the settled run did not record. That
# was the one unknown standing between a failed reproduction and a refutation, and it is now closed:
#
#     band   shipped     stdlib path   gpt2 path      sample: 40 HC3 human texts, 120-320 words
#       5    ~100%            0%          5%          (mean 188; the settled run used mean 212)
#      10    ~85%            18%          5%
#      20    71-85%          50%          8%
#      40    86-100%         65%         10%
#
# The stdlib path is unambiguously the one the settled run used: it rises with length exactly as the
# shipped table does, while the GPT-2 path is flat and three to six times lower. So the shape was
# right and the level was not — every band is 20 to 35 points low except the 5-word row, which is
# 100 points low and cannot be a sampling difference.
#
# The bands below are the range across BOTH lite paths, because either can run and nothing in the
# result says which did. The method is stated in full here for the reason the note under this one
# gives: numbers whose method is unrecorded cannot be argued with, only replaced.
#
# STILL UNMEASURED: the naturally-short arm. These are truncations of long answers, and a naturally
# 20-word reply is a different object — which is the distinction the previous note was built around
# and the reason it quoted ranges. Whoever measures it should widen these rather than replace them.
#
# Re-run of the TRUNCATED arm, 40 HC3 human texts of mean 332 words (the settled run used mean 212),
# counting `max >= 0.30`, on both lite paths — because the lite tier silently uses GPT-2 when torch
# is importable and the stdlib heuristic otherwise, and nothing in the settled note says which ran:
#
#     band   shipped      stdlib path   gpt2 path
#       5    ~100%             0%           0%
#      10    ~85%             10%           8%
#      20    71-85%           35%          10%
#      40    86-100%          62%          22%
#
# Every band is lower, on both paths, and the 5-word row is not abstention: a five-word text returns
# a real 0.0 rather than declining to score. Two of the three variables are known to differ (sample
# length, scoring path) and one is not (which path the settled run used), so this is a failed
# reproduction rather than a refutation — but it is large enough that the shipped figures should not
# be quoted as settled until someone re-runs it with the path pinned.
#
# The sentence they appear in stays true either way: at 40 words 22-62% of HUMAN text is above the
# loop threshold, which is ample reason to distrust a short verdict. What the re-run suggests is that
# the direction may be the other one for the shortest inputs — a five-word text scoring 0.0 makes a
# CLEAR verdict the uninformative one, not the flag.
_SHORT_TEXT_BANDS = ((5, "0-5%"), (10, "5-18%"), (20, "8-50%"), (40, "10-65%"))
_MIN_WORDS_FOR_A_VERDICT = 40


# Characters with no visible width that nonetheless change every tokenisation: zero-width space,
# ZWNJ/ZWJ, word joiner, bidi marks, BOM, and the soft hyphen that justified PDF text is full of.
# U+2028/U+2029 added 2026-08-13: categories Zl and Zp, so they sat outside every class here and
# in `scrub`. MEASURED, inserted after every "e" in a two-sentence paragraph: 0.6735 -> 0.5545,
# unscrubbed and unwarned -- a score-moving invisible in the direction that reads AI as human.
_INVISIBLE_RE = re.compile(
    "[" + "\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\u00ad\u2028\u2029" + "]"
)


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


def _is_all_confusable(word: str) -> bool:
    """A word with no Latin letters whose every letter has an ASCII lookalike.

    Built on the scrubber's own `_UNHOMOGLYPH` map so the two cannot disagree about what a
    confusable is — a second hand-written list is how a detector and its remedy drift apart.
    """
    from untell.attacks.unicode_tricks import _UNHOMOGLYPH

    letters = [c for c in word if c.isalpha()]
    if not letters or any("a" <= c.lower() <= "z" for c in letters):
        return False
    return all(c in _UNHOMOGLYPH for c in letters)


def _homoglyph_warning(text: str) -> str | None:
    """Warn when Cyrillic or Greek letters sit inside Latin words.

    MEASURED on 15 HC3 pairs, mapping a/e/o/p/c to their Cyrillic lookalikes: AI text moved
    -0.2884 and its verdict flipped to clean on **13 of 15**; human text moved -0.2407 and
    flipped on 4. A stronger evasion than the zero-width case, and invisible to a reader.

    `score_tells` is already immune — it scrubs, and scrubbing maps these back to ASCII. This
    surface deliberately does not scrub (see `_invisible_char_warning`), so it has to say so.
    """
    mixed = [w for w in text.split() if _LATIN.search(w) and _CONFUSABLE_SCRIPT.search(w)]
    # A word converted ENTIRELY mixes nothing, so the test above cannot see it. "саре" — c, a, p, e
    # all Cyrillic — reads as "cape" and returned None. That word carries exactly the risk this
    # warning exists for: it is still in the text, and another tool may not normalise it.
    #
    # The signal is CONFUSABILITY, not script. Flagging any non-Latin word would fire on a Russian
    # quotation inside an English document, which is ordinary multilingual text and not an attack.
    # A converted word is one where every letter has an ASCII lookalike, so the test is membership
    # in `_UNHOMOGLYPH` — the scrubber's own map, rather than a second list that could drift from
    # it. Genuine Cyrillic words contain letters with no Latin twin (п, и, в, ...) and do not match.
    converted = [w for w in text.split() if _is_all_confusable(w)]
    if not mixed and not converted:
        return None
    if converted and not mixed:
        return (
            f"{len(converted)} word(s) are written entirely in Cyrillic/Greek letters that look "
            f"like ASCII — {', '.join(repr(w) for w in converted[:3])}. That is homoglyph "
            f"substitution, not another language. Run `untell scrub` to restore plain ASCII."
        )
    return (
        f"{len(mixed) + len(converted)} word(s) mix Latin with Cyrillic/Greek letters — the "
        f"signature of homoglyph "
        f"substitution. The score is unaffected (the detectors normalise confusables, verified at "
        f"0.0000 movement), but the substitution is still in your text and another tool may not "
        f"normalise it. Run `untell scrub` to restore plain ASCII."
    )


def _short_text_warning(text: str) -> str | None:
    """Warn when the text is too short for the flag to mean anything, with the measured rate.

    "Too short" and "not English" are different problems with the same symptom here, and saying
    the wrong one sends the reader at the wrong fix. `str.split()` counts whitespace-delimited
    runs, so a 46-character Chinese paragraph is **one word** by that measure and was reported as
    "1 word: too short for a reliable verdict ... Score longer text" — advice that cannot help,
    for a limit that is not length. `humanness` already draws this distinction; this is the same
    branch, on the same flag, so the two cannot say different things about one input.
    """
    words = len(text.split())
    if words >= _MIN_WORDS_FOR_A_VERDICT:
        return None
    if text.strip():
        try:
            from untell.scripts.tells import score_tells

            if not score_tells(text).get("language_supported", True):
                return (
                    "this text is not in a script these detectors were trained on. The score is "
                    "not a verdict about it — the models are English-only, and the tell catalogue "
                    "abstains. Length is not the limit here, so writing more will not help."
                )
        except Exception:
            pass  # a diagnostic must never break the scoring it describes
    rate = next(pct for bound, pct in _SHORT_TEXT_BANDS if words <= bound)
    return (
        f"{words} word{'' if words == 1 else 's'}: too short for a reliable verdict. MEASURED on 40 "
        # HUMAN in caps deliberately: the percentage is a false-positive rate, and a reader who
        # misses what it is a percentage OF reads it as an accuracy figure. The Result 207 rewrite
        # lowercased it and a test that asserts the emphasis caught it — the only word in the
        # sentence carrying that distinction.
        f"HC3 HUMAN texts truncated to this length, {rate} score above the loop threshold "
        f"(the range spans the two lite scoring paths). At this length the score collapses toward "
        f"its floor as the text gets shorter, so a CLEAR verdict carries as little information as a "
        f"flagged one. Score longer text, or treat this as no evidence either way."
    )


def _single_sentence_warning(text: str, detectors: list, modes: dict | None = None) -> str | None:
    """Warn when the only detector scoring this text needs sentences it does not have.

    The stdlib heuristic is half perplexity and half BURSTINESS, and burstiness is the variation in
    sentence length — undefined on one sentence. MEASURED over 60 real HC3 sentences, scoring the
    first sentence alone against the first two together:

        single-sentence scores      8 distinct values of 60, and 82% are exactly 0.2500
        |delta| from one more       median 0.406, mean 0.367, range 0.000-0.672
        share moving by >0.30       67%

    0.2500 is what falls out when the burstiness term has no variance to measure — a placeholder
    wearing the shape of a score. (The first version of this note quoted 0.68 from a single hand-
    picked pair; the pair used in the test moves 0.063, which is why the range is stated.)

    The existing short-text guard does not catch this: it is a WORD count, and a 71-word single
    sentence clears its 40-word bar and still scores exactly 0.2500 with nothing said. Length and
    sentence count are different limits and a long run-on has only the second one.

    This is also the mechanism behind the per-sentence result: `score_sentences` on the stdlib path
    returns 6 distinct values across 100 sentences, 91 of them 0.250, AUROC 0.515. The detector is
    not weak at sentence granularity, it is undefined there — and at DOCUMENT granularity it is
    fine, 119 distinct values across 120 documents, AUROC 0.864 on HC3.
    """
    if any(getattr(d, "name", "") != "perplexity_burstiness" for d in detectors):
        return None  # a model-backed detector is scoring this and does not need sentence variation
    # The name is not enough, for the same reason `_verdict_threshold` above stopped trusting it:
    # `perplexity_burstiness` is TWO scoring paths under one label. Everything this warning says —
    # half burstiness, 82% landing on exactly 0.2500 — is a fact about the stdlib heuristic. On the
    # GPT-2 path the detector ranks lone sentences at AUROC ~0.97 (measured, see
    # `_single_sentence_signal`), so the warning was announcing a limitation that did not apply and
    # crediting it to a heuristic that had not run. Same source of truth as the verdict cut: the
    # detector's own `mode()`, which reports the path TAKEN rather than the one predicted.
    if (modes or {}).get("perplexity_burstiness") == "gpt2":
        return None
    if modes is None:
        for d in detectors:
            get_mode = getattr(d, "mode", None)
            if callable(get_mode):
                try:
                    if get_mode() == "gpt2":
                        return None
                except Exception:  # a diagnostic must never break scoring
                    pass
    from untell.text_split import split_sentences

    if len([s for s in split_sentences(text) if s.strip()]) >= 2:
        return None
    return (
        "one sentence: the stdlib heuristic is half burstiness, which is the variation in sentence "
        "length and is undefined here. MEASURED over 60 HC3 sentences, 82% of single sentences "
        "score exactly 0.2500 and adding one more moves the score by a median of 0.41 — this is a "
        "placeholder, not a verdict. Score a paragraph, or install .[full]."
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
    tier_note: str | None = None
    if tier not in _TIER_RANK:
        tier_note = (
            f"unknown tier '{tier}' — no tier matched, so only the always-on '{effective}' "
            f"detectors ran. Valid tiers: {', '.join(_TIER_RANK)}."
        )
    # The lite tier running its stdlib path is the one configuration where "flagged" is close to
    # meaningless, and nothing said so. MEASURED on 100 held-out HC3 pairs at the 0.30 default:
    # 69% of HUMAN text flags, against 6% when torch is importable and the same detector uses GPT-2
    # instead. Only warn when that path is the whole verdict — with other detectors live, the max
    # is not its to decide.
    #
    # BOTH DIRECTIONS, because the warning used to cover only one. "Treat a flag as a prompt to
    # re-run" describes the harmless error: a false flag costs a re-run. The error that costs
    # something is the reverse — this path calling AI text clean, after which nobody re-runs
    # anything. MEASURED on the AI side, lite verdict against full verdict, each at its own
    # published verdict_threshold:
    #
    #     corpus        full flags   lite clears it anyway
    #     HC3 (n=30)      30/30           3  = 10%
    #     RAID (n=30)     30/30          21  = 70%
    #
    # Every one of those 24 misses is against a full-tier score of 1.000 — not borderline text,
    # the ensemble's maximum confidence. The 7x spread between corpora is why the sentence names
    # both: a single figure here would be a property of whichever corpus produced it.
    elif effective == "lite" and modes.get("perplexity_burstiness") == "stdlib" and len(numeric) == 1:
        tier_note = (
            "lite tier on the stdlib path. Re-measured on 100 HC3 pairs: 64% of HUMAN text scores "
            "above the 0.30 loop threshold, and 30% is FLAGGED — `flagged` uses the 0.45 verdict "
            "threshold, not the loop one, so the two numbers answer different questions. It misses "
            "the other way too: of AI text the full ensemble flags, this path clears 10% (HC3, "
            "n=30) and 70% (RAID, n=30), every miss against a full-tier score of 1.000. Weak "
            "evidence in both directions — re-run at --tier full before trusting a flag OR a clear."
        )
    # Loudly flag a silent downgrade: full requested, but the ML stack didn't produce scores.
    elif _TIER_RANK.get(tier, 0) > _TIER_RANK.get(effective, 0):
        tier_note = (
            f"requested tier '{tier}' but only '{effective}' produced scores"
            + (f"; failed to load: {', '.join(failed)}" if failed else "")
            + f". The reported numbers reflect the '{effective}' tier only "
            "(commonly a NumPy 2.x / torch mismatch — see the README troubleshooting section)."
        )
    else:
        # The tier did NOT downgrade — and the roster can still be short. A detector that declines
        # by configuration is simply not selected, so `effective == tier`, no branch above fires,
        # and the verdict is drawn from fewer members with nothing saying so.
        #
        # MEASURED on one paragraph at `--tier full`, the only difference being an environment
        # variable the README's own reproduce command sets:
        #
        #     complete ensemble        5 detectors    max 1.0000    flagged True
        #     UNTELL_DISABLE_MAGE=1    4 detectors    max 0.1722    flagged False
        #
        # The same text, definitely-AI to clear. `max` over fewer members can only fall, so the
        # whole error runs toward NOT flagged — the direction that tells someone their AI text
        # reads as human, which is the failure `_bypass_rate` and the abstention note already guard
        # for detectors that error. A detector that never loaded took neither path.
        #
        # Only for the tiers where a full roster is the point. On lite, "the others are absent" is
        # the definition of the tier rather than news.
        tier_note = _short_roster_note(tier, effective, scores)
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
    # SITUATIONAL caveats first, the always-on tier caveat last.
    #
    # MEASURED over 120 corpus texts (HC3 and RAID, both halves) at `tier=lite`:
    #
    #     texts with an empty warning        0 / 120
    #     warning length                     median 503, p90 882, max 882
    #     `ensemble_warning` (tier caveat) 120 / 120
    #     human-false-positive note         46 / 120
    #     every other caveat                 0 / 120
    #
    # The tier caveat is right and it fires on every single run, which makes it wallpaper. With it
    # in front, a reader who stops after the first sentence — which is what people do with a note
    # they have seen a hundred times — never reaches the one that is specific to their input. The
    # threshold caveat added alongside this is the worst case: it says the caller's setting passes
    # everything, and it was arriving 500 characters in, behind "Also:".
    #
    # Ordering is the whole change. Nothing is dropped, shortened or conditioned; the rare and
    # actionable note simply goes first and the standing one keeps the last word.
    for extra in (_non_english_warning(text), _threshold_range_warning(threshold),
                  _short_text_warning(text),
                  _single_sentence_warning(text, detectors, modes), _invisible_char_warning(text),
                  _homoglyph_warning(text), _no_prose_warning(text),
                  _mostly_locked_warning(text), _line_per_sentence_warning(text),
                  _human_false_positive_warning(result), ensemble_warning, tier_note):
        if extra:
            result["warning"] = (
                f'{result["warning"]} Also: {extra}' if result.get("warning") else extra
            )
    return result



# A person checking their OWN writing is the input this tool is most likely to be handed by mistake,
# and a flagged verdict on it should not arrive bare.
#
# The lite path already says so loudly — "64% of HUMAN text scores above the 0.30 loop threshold".
# The FULL path, the one the README tells people to install, said nothing at all. MEASURED on 30
# genuine human texts per corpus at tier=full:
#
#     corpus   flagged (>=0.45)   above the loop bar (>=0.30)   mean max   carrying a warning
#     HC3        5 / 30  (17%)          5 / 30                    0.259           0
#     RAID       0 / 30  ( 0%)          0 / 30                    0.141           0
#
# Two of those HC3 answers scored **0.9922 and 0.9862** — reported as `ai_percent` 99.2 and 98.6 with
# `warning: None`. Genuine human writing, told it is 99% machine, with nothing beside it.
#
# The corpus split is the substance rather than a caveat on it. HC3 human answers are casual forum
# Q&A, which is the register someone pastes when checking their own prose; RAID's are paper
# abstracts. So the rate a user should expect is the higher one, and quoting a single pooled number
# would understate exactly the case that matters.
#
# Only when `flagged` is true. An unflagged verdict needs no false-positive note, and a warning on
# every call is a warning nobody reads — the same reasoning the pinned-max note in `rich_output`
# records for staying silent when nothing is pinned.
_HUMAN_FP_NOTE = (
    "a flagged verdict is not proof of AI authorship. MEASURED on genuine human text at this tier: "
    "5 of 30 HC3 forum answers were flagged (17%), two of them at 0.9922 and 0.9862, against 0 of "
    "30 RAID abstracts. Conversational writing is the register that false-positives, so if this is "
    "your own prose the number may be telling you about the detector rather than about the text."
)


def _human_false_positive_warning(result: dict) -> str | None:
    """Say what a flagged verdict is worth, on the tier that was previously silent."""
    return _HUMAN_FP_NOTE if result.get("flagged") else None



# A document with no prose is one the rewriter provably cannot touch, and the verdict on it describes
# a kind of text the detectors were never built for. MEASURED at tier=lite on a 272-word Python
# fence: `flagged: True`, `stopped: max_iters`, `changed: False` — the loop ran every iteration,
# adopted nothing, and reported an AI verdict with no hint that there was nothing to rewrite.
#
# The discriminator already exists. `layout._prose_line_mask` marks which lines the rewriter may
# touch, and that module is stdlib-only with no intra-package imports, so this costs a scan:
#
#     pure code fence     0 of 62 lines prose
#     ordinary prose      1 of 1
#     prose + a fence     1 of 64
#
# MEASURED on 120 corpus texts (HC3 and RAID, both halves): **0** have zero prose lines, so it
# cannot fire on real writing.
#
# What it covers, stated rather than implied: fenced code, markdown tables and YAML front matter —
# what someone pastes out of a README. It does NOT fire on a bullet list or a bare URL list, because
# `_prose_line_mask` counts list items as prose and the rewriter does rewrite them. That is the right
# call for bullets and merely a miss for URLs; a caveat firing on every list would be noise on the
# most common markdown there is.
_NO_PROSE_NOTE = (
    "this document contains no prose lines — it is code, a table or front matter — so the score "
    "describes text the detectors were not built for and the rewriter has nothing it may touch. "
    "Treat the verdict as undefined for this input rather than as a judgement about the writing."
)


def _no_prose_warning(text: str) -> str | None:
    """Say when the input is entirely non-prose, which makes the verdict undefined."""
    try:
        from untell.layout import _prose_line_mask

        mask = _prose_line_mask(text)
    except Exception:  # a caveat must never break the score it qualifies
        return None
    return _NO_PROSE_NOTE if mask and not any(mask) else None



# Most of a document can be material the rewriter is forbidden to touch, and the verdict then covers
# text the user did not write. MEASURED at tier=lite on a two-quotation witness statement:
#
#     locked 321/357 characters (90%), 2 spans
#     flagged: True   changed: False   stopped: max_iters
#
# The loop ran every iteration, adopted nothing — only a tenth of the document was editable — and
# said nothing about it. This is the same shape as the no-prose note above reached by a completely
# different mechanism: there the rewriter had no prose lines, here it has prose it may not alter.
#
# It is arguably the worse case of the two, because the detectors scored the quotations as well, so
# the number describes somebody else's words.
#
# MEASURED over 120 corpus texts (HC3 and RAID, both halves), locked character share:
#
#     median 0.023    p90 0.072    p99 0.137    max 0.177
#
# against 0.899 for the probe. Nothing in the corpus passes 0.30, so 0.50 sits in a wide empty gap
# and means what it says: more than half the document is off-limits.
#
# "Preserved material" rather than "quotations": `lock` also holds citations, figures, dates and
# URLs, and a note that named only quotes would misdescribe a statistics-dense paragraph.
_LOCKED_SHARE_BAR = 0.50

_MOSTLY_LOCKED_NOTE = (
    "more than half of this document is preserved material — quotations, citations, figures or "
    "URLs — which the rewriter may not alter and the detectors scored anyway. The verdict is "
    "largely about text this tool cannot change, and in the case of quoted matter about words "
    "somebody else wrote."
)


def _mostly_locked_warning(text: str) -> str | None:
    """Say when the rewriter is forbidden to touch most of the input."""
    try:
        from untell.scripts.preserve import lock

        _, mapping = lock(text)
    except Exception:  # a caveat must never break the score it qualifies
        return None
    if not mapping or not text:
        return None
    share = sum(len(v) for v in mapping.values()) / len(text)
    return _MOSTLY_LOCKED_NOTE if share > _LOCKED_SHARE_BAR else None


# A block of one sentence has no PAIR, and merge, split, restatement-drop and burstiness targeting
# all need one. They are correctly gated — merging across a paragraph boundary would weld two
# paragraphs together and destroy a transcript, a bullet list or a changelog — so this is a limit of
# the input's shape rather than a defect to fix in the rewriter.
#
# It is worth saying out loud because it costs the user real ground. MEASURED on 8 HC3 documents at
# `tier=lite`, the SAME text with the only difference being one sentence per paragraph:
#
#     as written              0.5501 -> 0.5097   (-0.0404)    flagged 6/8
#     one sentence per para   0.5501 -> 0.5349   (-0.0152)    flagged 7/8
#
# The `pre` scores are identical — detectors do not read paragraph breaks — so the whole difference
# is what the rewriter was able to do. **2.7x less improvement**, and one document crossed back over
# the verdict threshold: 0.434 (clear) as written, 0.539 (flagged) split. Sentence-length variance
# tells the same story: document CV reaches 0.374 at three sentences a paragraph and 0.319 at one,
# against a measured human 0.484.
#
# MEASURED over 120 corpus texts (HC3 and RAID, both halves), share of prose blocks holding exactly
# one sentence: median 0.000, p90 0.500, p99 0.667, max 0.667. Restricted to the 61 texts with three
# or more prose blocks the max is the same 0.667, and **0** exceed 0.80. Six real documents re-laid
# out one sentence per line all score 1.00 across 7 to 10 blocks, so the bar sits in a wide gap.
#
# The three-block floor keeps this off short input, where a single one-sentence block is 1.00 by
# arithmetic and `_short_text_warning` is the note that actually applies.
_LONE_BLOCK_SHARE_BAR = 0.80
_MIN_BLOCKS_FOR_LONE_NOTE = 3
_LINE_PER_SENTENCE_NOTE = (
    "this document is laid out roughly one sentence per paragraph, so the transforms that need two "
    "adjacent sentences — merging, restatement removal and sentence-length variation — could not "
    "run. The score is real, but the rewriter reached less of the text than it would have on the "
    "same words in ordinary paragraphs."
)


# Detector scores are probabilities: every checker in the registry returns a value clamped to
# [0, 1]. A threshold outside that range is therefore not a strict setting, it is an unreachable one,
# and the failure is silent and one-directional.
#
# MEASURED on the same AI paragraph, across all three surfaces:
#
#     threshold   score.flagged   untell.flagged   verify.passes_all
#         0.30          True             True            False
#         0.45          True             True            False
#         1.50          False            False           True
#        45.00          False            False           True
#        -1.00          True             True            False
#
# A caller who types `45` meaning 45 per cent gets a clean verdict from every surface, including
# `verify`, which is the CI-facing one that exits 0 on a pass. Nothing said a word: the only warning
# present was the generic lite caveat, byte-identical at 0.30 and at 45.00 — and it quotes "the 0.30
# loop threshold", a number the caller did not use.
#
# A warning rather than a refusal, matching how this tool treats an unknown tier and an unknown
# style: the run still happens and the caller is told what their setting actually did.
_THRESHOLD_RANGE_NOTE_HIGH = (
    "the threshold {value} is above 1.0, and detector scores are probabilities in [0, 1] — no text "
    "can ever reach it, so this run passes everything. If you meant a percentage, divide by 100."
)
_THRESHOLD_RANGE_NOTE_LOW = (
    "the threshold {value} is below 0.0, and detector scores are probabilities in [0, 1] — every "
    "text is above it, so this run flags everything and the rewrite loop can never stop."
)


# Detectors that are absent BY DEFAULT and arrive only when asked for. Their absence is the shipped
# configuration, not a reduced ensemble, so naming them would put a caveat on every full-tier run —
# which the first version of this note did, reporting "ran without radar" on a complete ensemble.
#
# The distinction is opt-IN versus opt-OUT. `mage` ships enabled and leaves via
# `UNTELL_DISABLE_MAGE=1`; `radar` and the local judge arrive via `UNTELL_ENABLE_RADAR` and
# `UNTELL_ENABLE_LOCAL_JUDGE`. Only the first kind is a member that went missing.
_OPT_IN_DETECTORS = frozenset({"radar", "local_judge"})


def _short_roster_note(tier: str, effective: str, scores: dict) -> str | None:
    """Name detectors the requested tier expects that did not turn up.

    Distinct from `failed_detectors` (loaded, then raised) and from the abstention note (loaded,
    then returned None). This is the third way to be absent: never selected, because `available()`
    said no — a missing model file, a missing key, or a documented opt-out like
    `UNTELL_DISABLE_MAGE=1`.
    """
    if tier not in ("full", "heavy"):
        return None
    try:
        from untell.detectors.base import _tier_at_most, all_detectors

        missing = sorted(
            d.name
            for d in all_detectors()
            if _tier_at_most(d.tier, tier)
            and d.name not in scores
            and d.name not in _OPT_IN_DETECTORS
            and not d.available()
        )
    except Exception:  # a caveat must never break the score it qualifies
        return None
    if not missing:
        return None
    return (
        f"the '{tier}' ensemble ran without {', '.join(missing)}: not installed, not configured, or "
        "switched off. `max` is taken over the detectors that did run, and fewer members can only "
        "lower it, so a short roster can only make text look MORE human than the complete "
        "ensemble would. MEASURED on one paragraph: the same text scored 1.0000 with every "
        "detector present and 0.1722 without one of them."
    )


def _non_english_warning(text: str) -> str | None:
    """The rewrite path refuses non-English text and says so. The scoring path did neither.

    `untell_text` calls `looks_non_english` and returns the text unchanged with a caveat ending
    "any score here is not a verdict about this text". `score_text` is a separate public surface —
    the CLI's `score`, the MCP tool, the REST endpoint — and never consulted that check, so a German
    paragraph came back with a `flagged` verdict and caveats about its LENGTH and its TIER and
    nothing at all about its language.

    MEASURED on one paragraph of the same content in five languages, lite tier:

        english   0.7495  flagged=True    rewritten, 1 candidate adopted
        german    0.4788  flagged=True    returned unchanged, no language caveat here
        spanish   0.2680  flagged=False   returned unchanged, no language caveat here
        french    0.2364  flagged=False   returned unchanged, no language caveat here
        japanese  0.0000  flagged=False   non-Latin script, already caveated

    The German row is the one that matters: a confident-looking AI verdict, produced by
    English-only models, on text the rest of the pipeline had already declined to process.

    First in the caveat order, ahead of the threshold note, because it invalidates the number the
    other caveats are qualifying rather than qualifying it.
    """
    from untell.scripts.tells import looks_non_english

    if not text.strip() or not looks_non_english(text):
        return None
    return (
        "this text reads as a Latin-script language other than English. The detectors and the tell "
        "catalogue are English-only, so the score above is not a verdict about this text — treat a "
        "flag and a clear alike as no evidence. The rewriter returns such text unchanged for the "
        "same reason."
    )


def _threshold_range_warning(threshold: float | None) -> str | None:
    """Say when the bar is outside the range any score can occupy."""
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
        return None
    if threshold > 1.0:
        return _THRESHOLD_RANGE_NOTE_HIGH.format(value=threshold)
    if threshold < 0.0:
        return _THRESHOLD_RANGE_NOTE_LOW.format(value=threshold)
    return None


def _line_per_sentence_warning(text: str) -> str | None:
    """Say when the input's shape, not the text, is what limited the rewrite."""
    try:
        from untell.layout import apply_per_block
        from untell.text_split import split_sentences

        blocks: list[str] = []
        apply_per_block(text, lambda block: (blocks.append(block), block)[1])
        prose = [b for b in blocks if b.strip()]
    except Exception:  # a caveat must never break the score it qualifies
        return None
    if len(prose) < _MIN_BLOCKS_FOR_LONE_NOTE:
        return None
    lone = sum(1 for b in prose if len([s for s in split_sentences(b) if s.strip()]) <= 1)
    return _LINE_PER_SENTENCE_NOTE if lone / len(prose) > _LONE_BLOCK_SHARE_BAR else None


def _read_input(args: argparse.Namespace) -> str | None:
    if args.file:
        # read_file(): BOM-aware, sniffs UTF-16/cp1252, handles docx/pdf, rejects binaries.
        # A naive open(encoding="utf-8", errors="replace") turns a UTF-16 document into mojibake
        # peppered with NUL bytes and scores THAT, silently. Same bug already fixed in run.py and
        # tells.py; it was still open at every other --file entry point.
        from untell.scripts.io_utils import read_file_or_exit

        return read_file_or_exit(args.file)
    if args.text:
        return args.text
    # None means stdin is a terminal; reading it would block with no prompt and no output. The
    # caller's own empty-input branch turns that into the usage message and exit 2.
    from untell.scripts.io_utils import read_stdin_or_none

    return read_stdin_or_none()


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
        # Range-checked, like `untell humanize` and `untell verify`. A threshold outside [0, 1]
        # cannot be reached by a probability, so `--threshold 5` reported `flagged: false` on text
        # this same command rates 0.826 — a verdict that cannot ever be true, delivered without
        # complaint. The REST and MCP surfaces already refuse it.
        #
        # Imported inside the parser rather than at module scope: one definition of the bound, and
        # `--help` does not pay for loading the loop.
    from untell.scripts.run import _PROBABILITY

    parser.add_argument(
        "--threshold",
        "-t",
        type=_PROBABILITY,
        default=DEFAULT_THRESHOLD,
        help=f"Max-proxy P(AI) below which text is considered human-passing (default: {DEFAULT_THRESHOLD}).",
    )
    args = parser.parse_args(argv)

    from untell._env import load_env

    load_env()  # pick up commercial keys from a .env file if present (for --tier commercial)

    text = _read_input(args)
    if text is None:
        print(json.dumps({"error": "no input: pass text, --file PATH, or pipe to stdin"}))
        return 2
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
    # 2 when NOTHING produced a score, the same code and the same reasoning `untell-verify` uses:
    # nothing ran is a configuration problem, not a verdict about the text, and 1 is reserved for a
    # verdict a caller might act on by rewriting.
    #
    # MEASURED with every detector broken on purpose: this command printed `"scored": false`,
    # `"max": 0.0`, `"flagged": false` and exited **0**. The JSON carries the diagnosis and a shell
    # branching on the exit code sees success — a score of 0.0 reads as "not AI". That is the defect
    # `untell-verify` fixed one commit earlier, in the sibling command, and its comment applies
    # verbatim: "Exit 0 means PASS to everything that reads it."
    #
    # `flagged` deliberately does NOT change the exit code. This command is a report, not a gate:
    # `untell-verify` is the gate and returns 1 for a failing verdict. Two commands disagreeing
    # about what exit 1 means would be worse than the silence this replaces.
    return 2 if result.get("scored") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())


DETECTOR_ERROR_SUFFIX = "__error"

# Which nested keys of a result are themselves score dicts. `untell_text` returns two, and they were
# the ones a network client actually received unnormalised.
_NESTED_SCORE_KEYS = ("pre", "post")


def split_detector_errors(result: dict) -> dict:
    """Move the ``name__error`` sidecars out of ``detectors``, including nested score dicts.

    Internally a score result carries a failure message inside the same mapping as the scores —
    ``{"hc3_roberta": None, "hc3_roberta__error": "..."}`` — and every in-repo consumer knows to
    filter keys ending in ``__error``. That is a deliberate internal convention.

    It is not a reasonable thing to hand a network client. ``max(detectors.values())`` raises
    ``TypeError: '>' not supported between instances of 'str' and 'float'``, and nothing in the
    response says so: the field looks like a map of numbers because in every other response it is
    one.

    This lived in `api_server` and was applied to ``/score`` alone. MEASURED with three detectors
    broken on purpose:

        /score      detectors all numeric-or-null, detector_errors populated
        /humanize   post.detectors -> {'perplexity_burstiness': 0.1111, 'roberta_openai': None,
                    'roberta_openai__error': 'broken on purpose', ...}, detector_errors None
                    — mixed types float / NoneType / str, and TWO such dicts per response

    So the surface that returns two score dicts was the one that normalised neither, and the MCP
    server normalised nothing at all. Shared here so all three read one definition.
    """
    if not isinstance(result, dict):
        return result
    out = result
    detectors = result.get("detectors")
    if isinstance(detectors, dict):
        errors = {
            k[: -len(DETECTOR_ERROR_SUFFIX)]: v
            for k, v in detectors.items()
            if k.endswith(DETECTOR_ERROR_SUFFIX)
        }
        if errors:
            out = dict(result)
            out["detectors"] = {
                k: v for k, v in detectors.items() if not k.endswith(DETECTOR_ERROR_SUFFIX)
            }
            out["detector_errors"] = errors
    for key in _NESTED_SCORE_KEYS:
        nested = out.get(key)
        if isinstance(nested, dict):
            cleaned = split_detector_errors(nested)
            if cleaned is not nested:
                if out is result:
                    out = dict(result)
                out[key] = cleaned
    return out
