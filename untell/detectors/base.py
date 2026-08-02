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

from typing import Protocol, runtime_checkable

# Tier ordering: a request for "full" also includes "lite" detectors, etc.
Tier = str  # "lite" | "full" | "heavy" | "commercial"
_TIER_RANK = {"lite": 0, "full": 1, "heavy": 2, "commercial": 3}


def clamp01(x: float) -> float:
    """Clamp a probability into [0, 1] (guards against numerical drift)."""
    if x != x:  # NaN
        return 0.5
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else float(x)


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
