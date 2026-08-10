"""Detector protocol + tier-aware registry.

Every detector exposes the same surface:

    name      -> short stable identifier used as a JSON key
    tier      -> one of "lite" | "full" | "heavy"
    available() -> bool   # are this detector's dependencies importable / models loadable?
    score(text) -> float  # P(text is AI-generated), clamped to [0, 1]

The registry (`load_detectors`) returns the *available* detectors for a requested tier,
so a machine with no ML stack transparently degrades to the lite heuristic. Adapters must
keep heavy imports inside `available()`/`score()` — never at module top level — so that
importing this package stays cheap and dependency-free.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from untell.text_split import fold_unicode_spaces

# Tier ordering: a request for "full" also includes "lite" detectors, etc.
Tier = str  # "lite" | "full" | "heavy" | "commercial"
_TIER_RANK = {"lite": 0, "full": 1, "heavy": 2, "commercial": 3}


def clamp01(x: float) -> float:
    """Clamp a probability into [0, 1] (guards against numerical drift)."""
    if x != x:  # NaN
        return 0.5
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else float(x)


# --- input whitespace normalisation -------------------------------------------------------------
# `Hello-SimpleAI/chatgpt-detector-roberta` learned a shortcut, not a style. Its training corpus is
# HC3, whose two halves were preprocessed differently: MEASURED over 300 pairs, the HUMAN half
# carries 90.33 space-before-punctuation marks per 1,000 words and the ChatGPT half 0.02 — a
# tokenisation artefact of how the corpus was built, separating the classes ~4,500:1. The model
# picked it up, so "space before punctuation" reads to it as near-proof of a human author.
#
# The effect is not subtle. On 25 RAID documents, inserting one space before each period drove
# hc3_roberta to exactly 0.000 on 25 of 25; doubling the spaces after each period did it on 20 of
# 25. Newlines and tabs do nothing — it is the literal space character. MEASURED as AUROC on 120
# pairs, AI vs human:
#
#                      raw      attacked   attacked + this fix
#     RAID           0.9784      0.1434          0.9784
#     HC3            1.0000      0.4044          1.0000
#
# 0.1434 is far below chance: the attack does not blind the detector, it inverts it. And the repair
# is free — on clean text the substitutions match nothing, so both corpora score identically to the
# raw figure, to four decimals.
#
# This is applied to detector INPUT only and never to text the user gets back. It is not a claim
# that whitespace is meaningless; it is that this model reads it as authorship when it is punctuation
# style, and a PDF extractor or a double-space-after-period habit produces it by accident.
#
# --- why nothing else is normalised -------------------------------------------------------------
# The obvious follow-up question is whether the other detectors carry shortcuts of the same kind.
# AUDITED, and the answer is no. Method: rank 28 surface features by how hard they separate the two
# halves of each corpus (the fingerprint that caught the whitespace artefact), then perturb the
# candidates against every loadable detector WITH CONTROLS, because a surface edit that also changes
# grammar cannot be told apart from real signal without one. 40 RAID pairs, AUROC:
#
#                            baseline   ", and "->"; "   control ", and "->". "
#     roberta_openai           0.8581       0.5719              0.5769
#     hc3_roberta              0.9850       0.8381              0.9613
#     fast_detectgpt           1.0000       1.0000              1.0000
#     perplexity_burstiness    0.9812       0.9688              0.9487
#
# `roberta_openai` looks catastrophically semicolon-sensitive until the control lands on the same
# number: splitting a long compound sentence is what moves it, whichever mark does the splitting.
# That is burstiness — real signal, and exactly what the structural rewriter is for. Not a shortcut.
# `fast_detectgpt` is zero-shot, so it has no training corpus to carry an artefact, and measures
# immune. `mage` is correctly oriented and sharp (2.6e-05 on a human sample, 0.99999 on an AI one).
#
# `hc3_roberta` is the exception again: for it the semicolon does something the period does not
# (0.8381 vs 0.9613), and HC3 has the matching asymmetry — 0.90 semicolons per 1,000 human words
# against 0.00 for ChatGPT. But unlike whitespace this one is NOT normalised, because it is not an
# artefact: 2022-era ChatGPT really did avoid semicolons. It is a stale style correlate, so removing
# it from the input would delete signal rather than noise. It is recorded here as a known evasion
# lever instead.
#
# One calibration point worth keeping, because it is what stops this method over-firing: a lopsided
# corpus ratio is NOT sufficient to make a shortcut. HC3's human half writes spaced contractions
# ("it 's", "does n't") at 9.34 per 1,000 words against ChatGPT's 0.00 — an infinite ratio, the same
# fingerprint as the whitespace artefact — and reproducing them costs hc3_roberta 0.033 AUROC. The
# corpus screen proposes; only the perturbation test decides.
#
# Caveat for anyone measuring ON these corpora rather than fixing a detector: RAID separates its own
# halves 30:1 on single newlines (84.52 vs 2.79 per 1,000 words) and infinitely on double newlines
# (0.00 vs 14.50). An AUROC computed over RAID with layout preserved is partly scoring formatting.
# The figures above avoid it by whitespace-joining both halves, which is a thing to do deliberately.
_HORIZONTAL_RUN = re.compile(r"[ \t]+")
_TRAILING_HORIZONTAL = re.compile(r"[ \t]+(?=\n)")
_SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([.,;:!?])")
# Unicode's own line terminators. They render as a line break and are not "\n", so a tokenizer sees
# an unknown character where a newline belongs. Word, some PDF extractors and a few web editors emit
# them routinely. MEASURED, replacing every space with U+2028 moved roberta_openai +0.9407 (0.0427
# to 0.983) and perplexity_burstiness +0.4164 — the same shape as the soft-hyphen false positive.
# They survive `scrub_hidden` correctly: it strips characters that carry NO meaning, and these carry
# "line break", so the fix is to translate them rather than to delete them.
_UNICODE_LINEBREAK = re.compile("[  ]")


def normalise_whitespace(text: str) -> str:
    """Collapse horizontal whitespace to single spaces and drop space before punctuation.

    A lone tab counts as a run of one: it is horizontal whitespace standing in for a space, so it
    normalises to a space rather than surviving as a distinct token.

    Line structure is deliberately preserved. Newlines carry paragraphing, they are not part of the
    artefact, and they were measured not to move any detector — so only whitespace *before* a
    newline is removed, and indentation after one is left as a single space rather than stripped.

    Unicode spaces are folded FIRST, via the shared helper rather than a pattern of our own. The
    first version of this function scoped itself to ``[ \\t]+`` and so missed every non-ASCII space
    separator: MEASURED, replacing each space with U+00A0 took hc3_roberta from 0.1580 to 0.0002 —
    the same collapse the ASCII fix had just closed, through a door left open beside it.
    ``fold_unicode_spaces`` documents this exact failure ("one rule, one place"; a normaliser scoped
    to ``[ \\t]{2,}`` missing most of its class) and this function had reproduced it.
    """
    out = _UNICODE_LINEBREAK.sub("\n", fold_unicode_spaces(text))
    out = _HORIZONTAL_RUN.sub(" ", out)
    out = _TRAILING_HORIZONTAL.sub("", out)
    return _SPACE_BEFORE_PUNCT.sub(r"\1", out)


def normalise_for_scoring(text: str) -> str:
    """What every detector should see: invisible characters stripped, then whitespace normalised.

    Invisible codepoints are the same class of defect as the whitespace artefact and considerably
    worse in effect. MEASURED on a human-written paragraph, inserting a soft hyphen between every
    character — which is precisely what extracting text from a justified PDF produces:

        clean          max 0.1295   flagged False
        soft-hyphened  max 1.0000   flagged True    <- mage 0.0 -> 1.0, roberta_openai 0.033 -> 1.0

    A false positive at certainty 1.0000 on somebody's own writing, reachable by pasting it out of
    a PDF. `score_tells` has scrubbed since Result 51 and is unaffected (59 words either way); the
    detector path never did, so the two halves of the product disagreed about what the input was.

    `scrub_hidden` rather than a local stripper, for the reason its own callers give: it already
    distinguishes an orphan zero-width joiner from one holding an emoji sequence together, and a
    second nearly-identical stripper is how a rule ends up applied in some places and missed in the
    rest. Imported lazily to keep importing this package cheap, matching `score_tells`.
    """
    from untell.attacks import scrub_hidden

    return normalise_whitespace(scrub_hidden(text))


# Words per scoring window. The supervised adapters cap at 512 word-piece tokens, which is roughly
# 380 English words; 320 leaves headroom for tokenizer expansion on punctuation and rare words.
WINDOW_WORDS = 320


def _split_to_width(sentence: str, width: int) -> list[str]:
    """``sentence`` as pieces of at most ``width`` words. Usually returns it unchanged.

    Only reached when one sentence is wider than a whole window, which in practice means the text
    had no sentence terminators for the splitter to find.
    """
    words = sentence.split()
    if len(words) <= width:
        return [sentence]
    return [" ".join(words[i:i + width]) for i in range(0, len(words), width)]


def windowed_max(text: str, score_window, window_words: int = WINDOW_WORDS) -> float | None:
    """Score long text in windows and return the HIGHEST window score.

    Every supervised adapter passes ``truncation=True, max_length=512``, so it reads roughly the
    first 380 words and silently discards the rest. MEASURED, that is not a rounding error — it is
    the difference between seeing a document and seeing its opening paragraph:

        1113 words of AI text appended to 797 words of human text
          roberta_openai   human alone 0.000   human + AI 0.000
          hc3_roberta      human alone 0.000   human + AI 0.000
          fast_detectgpt   human alone 0.418   human + AI 0.418

    Identical to three decimal places. An essay with a human-written opening scored clean no matter
    what followed it, and the loop's "passed" verdict meant nothing for anything longer than a few
    paragraphs — which is the primary use case.

    ``max`` is the right aggregate here and matches how the ensemble already combines detectors: if
    any part of the document reads as machine-written, the document does. A mean would let a long
    human preamble dilute an AI section below threshold, which is exactly the failure above.

    Windows break on sentence boundaries so no window starts mid-clause. Text short enough to fit is
    scored in a single call, so nothing changes for ordinary input.

    COST, measured at full tier: scoring is now linear in document length rather than flat —
    207 words 0.87s, 552 words 2.41s, 896 words 4.17s, where before every length cost the same as
    the first window. That is the price of reading the document instead of its opening, and it is
    paid per candidate inside the rewrite loop, so long inputs are markedly slower end to end.
    A worthwhile follow-up: during candidate evaluation a substitution changes exactly one window,
    so the other windows' scores could be cached and reused. Not done here because it needs its own
    correctness check — the ensemble max may come from a window the edit never touched.
    """
    from untell.text_split import split_sentences

    # Normalised HERE because this is the one function every windowing adapter routes its input
    # through, and doing it per adapter is how six get it and the seventh does not. The word count
    # below depends on it too: a soft hyphen between every character turned a 209-word document
    # into 889 "words", which re-windows the text as well as corrupting the score.
    text = normalise_for_scoring(text)

    if len(text.split()) <= window_words:
        return score_window(text)

    windows: list[str] = []
    current: list[str] = []
    count = 0
    for sentence in split_sentences(text) or [text]:
        # A "sentence" wider than the whole window can never be packed into one — the `current and`
        # guard below skips the size test for it — so it used to pass through whole and the
        # adapter's own truncation=True discarded everything past ~380 words. That is not an exotic
        # case: any text without sentence terminators is a single "sentence", which covers
        # transcripts, bullet lists, headings-only outlines, semicolon run-ons and one very long
        # sentence. MEASURED before, at a 320-word window:
        #     1600-word bullet list      -> 1 window of 1600 words
        #     1200-word transcript       -> 1 window of 1200 words
        #      900-word run-on sentence  -> 1 window of  900 words
        # Each was then read only as far as the adapter's truncation allowed, and scored
        # confidently on that fraction — the exact failure windowing exists to prevent.
        for piece in _split_to_width(sentence, window_words):
            n = len(piece.split())
            if current and count + n > window_words:
                windows.append(" ".join(current))
                current, count = [], 0
            current.append(piece)
            count += n
    if current:
        windows.append(" ".join(current))

    scores = [s for s in (score_window(w) for w in windows if w.strip()) if s is not None]
    return max(scores) if scores else None


@runtime_checkable
class Detector(Protocol):
    """Structural type every detector adapter satisfies."""

    name: str
    tier: Tier

    def available(self) -> bool:
        """True when this detector can actually score (deps importable, models loadable)."""
        ...

    def score(self, text: str) -> float | None:
        """Return P(AI-generated) in [0, 1], or ``None`` to opt out of the ensemble for this text
        (empty/too-short input, or this detector produced no usable signal). ``score_text`` excludes
        a ``None`` from the max/mean rather than folding it in as a fake neutral 0.5."""
        ...


def _tier_at_most(detector_tier: Tier, requested: Tier) -> bool:
    return _TIER_RANK.get(detector_tier, 99) <= _TIER_RANK.get(requested, 0)


def all_detectors() -> list[Detector]:
    """Instantiate every known adapter (cheap; no heavy imports / network happen here)."""
    from .binoculars import BinocularsDetector
    from .commercial import commercial_detectors
    from .fast_detectgpt import FastDetectGPTDetector
    from .hc3_roberta import HC3RobertaDetector
    from .llm_judge import LLMJudgeDetector
    from .local_judge import LocalJudgeDetector
    from .mage import MageDetector
    from .perplexity_burstiness import PerplexityBurstinessDetector
    from .radar import RadarDetector
    from .roberta_openai import RobertaOpenAIDetector

    return [
        PerplexityBurstinessDetector(),
        RobertaOpenAIDetector(),
        HC3RobertaDetector(),
        MageDetector(),
        FastDetectGPTDetector(),
        RadarDetector(),  # opt-in (UNTELL_ENABLE_RADAR=1); robust-to-paraphrase, non-commercial
        BinocularsDetector(),
        LocalJudgeDetector(),  # open LLM as a detector (full/heavy tier); no API key
        LLMJudgeDetector(),  # commercial tier: the frontier LLM as a detector (key-gated); strong free signal
        *commercial_detectors(),
    ]


def load_detectors(tier: Tier = "full") -> list[Detector]:
    """Return the available detectors at or below ``tier``.

    Falls back to the lite heuristic if nothing else is installed, so the returned list is
    never empty (the lite detector has no dependencies and is always available).
    """
    selected = [
        d
        for d in all_detectors()
        if _tier_at_most(d.tier, tier) and d.available()
    ]
    if not selected:
        # Guarantee the documented invariant: the lite heuristic is dependency-free and always
        # available, so the registry never returns an empty list (which would silently zero-score).
        from .perplexity_burstiness import PerplexityBurstinessDetector

        selected = [PerplexityBurstinessDetector()]
    return selected


def resolved_tier(detectors: list[Detector]) -> Tier:
    """The effective tier actually running = the highest tier present among `detectors`."""
    if not detectors:
        return "lite"
    return max((d.tier for d in detectors), key=lambda t: _TIER_RANK.get(t, 0))
