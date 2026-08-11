"""Rewriter protocol + provider factory.

Two providers are supported, both optional: Anthropic (``ANTHROPIC_API_KEY``) and OpenAI
(``OPENAI_API_KEY``). A rewriter is *available* only when its SDK is importable and its key is
set; otherwise ``get_rewriter`` returns ``None`` and the caller falls back to the scripted
rewriter. Network calls live behind ``rewrite`` so importing this module stays cheap and offline.
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from untell._retry import retry

from .prompts import build_rewrite_prompt

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


@runtime_checkable
class Rewriter(Protocol):
    """A programmatic rewriter that turns flagged text into a humanized rewrite."""

    name: str

    def available(self) -> bool:
        """True when the SDK is importable and an API key is configured."""
        ...

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        """Return a rewritten version of ``text`` guided by ``score_result``.

        ``score_result`` is a HINT, **not the score of** ``text``. Two in-tree callers pass a
        score computed from something else, deliberately:

        - ``CompositeRewriter`` chains structural into surgical and passes the ORIGINAL text's
          score alongside the already-restructured string.
        - ``TargetedRewriter`` rewrites one sentence at a time and passes the WHOLE document's
          score alongside a single sentence.

        Both are fine, because the field is used to steer a rewrite (which detectors are hot, what
        tier is live), not as a measurement of the argument. But it means an implementation must
        NOT treat it as ``score_text(text)`` — e.g. reusing it as the baseline in a
        "only adopt a candidate that beats the original" comparison would silently compare against
        the wrong text. ``EnsembleRewriter`` re-scores the input for exactly that reason, and the
        redundant-looking call is deliberate. The one field that IS safe to read is ``tier``:
        every caller passes the tier the loop is actually judging on.
        """
        ...


class AnthropicRewriter:
    name = "anthropic"

    def __init__(self, model: str = DEFAULT_ANTHROPIC_MODEL):
        self.model = model

    def available(self) -> bool:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return False
        try:
            import anthropic  # noqa: F401
        except Exception:
            return False
        return True

    def _client(self):
        import anthropic

        return anthropic.Anthropic()

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        prompt = build_rewrite_prompt(text, score_result, threshold)
        resp = retry(
            self._client().messages.create,
            kw={"model": self.model, "max_tokens": 2048, "messages": [{"role": "user", "content": prompt}]},
            max_attempts=3,
        )
        # content is a list of blocks; concatenate the text blocks.
        parts = [getattr(b, "text", "") for b in resp.content]
        return "".join(parts).strip()


class OpenAIRewriter:
    name = "openai"

    def __init__(self, model: str = DEFAULT_OPENAI_MODEL):
        self.model = model

    def available(self) -> bool:
        if not os.environ.get("OPENAI_API_KEY"):
            return False
        try:
            import openai  # noqa: F401
        except Exception:
            return False
        return True

    def _client(self):
        import openai

        return openai.OpenAI()

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        prompt = build_rewrite_prompt(text, score_result, threshold)
        resp = retry(
            self._client().chat.completions.create,
            kw={"model": self.model, "messages": [{"role": "user", "content": prompt}]},
            max_attempts=3,
        )
        return (resp.choices[0].message.content or "").strip()


def get_rewriter(prefer: str | None = None) -> Rewriter | None:
    """Return the first available rewriter, or ``None`` if none are configured.

    ``prefer`` (``"anthropic"`` | ``"openai"`` | ``"local"`` | ``"surgical"`` |
    ``"structural"`` | ``"composite"``) forces a provider order.

    * ``"surgical"`` — deterministic word-substitution rewriter (always available, $0).
    * ``"structural"`` — sentence-level structural rewriter (always available, $0).
    * ``"composite"`` — structural + surgical chained (always available, $0).
    * ``"local"`` — trained LoRA policy if available.
    * ``"anthropic"`` or ``"openai"`` — hosted LLM (needs API key).

    A trained local policy (``UNTELL_POLICY_DIR`` set + adapter present) is preferred by
    default — it's the moat: local, no key, single forward pass. ``prefer="surgical"`` returns the
    deterministic no-key word-substitution rewriter, making the loop runnable at $0.
    """
    from .composite import CompositeRewriter
    from .local_policy import LocalPolicyRewriter
    from .structural import StructuralRewriter
    from .surgical import SurgicalRewriter

    # Always-available free rewriters.
    if prefer == "surgical":
        return SurgicalRewriter()
    if prefer == "structural":
        return StructuralRewriter()
    if prefer == "composite":
        return CompositeRewriter()
    if prefer == "neural":
        # Neural composite: T5 paraphrase front-stage + structural + surgical. Falls back to the
        # plain rule-based composite when T5's deps (.[full]) are absent, so it is never None.
        return CompositeRewriter(use_t5=True)
    if prefer == "targeted":
        # Rewrite ONLY the sentences that read as AI; leave human-reading ones byte-identical.
        from .targeted import TargetedRewriter

        return TargetedRewriter()
    if prefer in ("ensemble", "max"):
        # Best-of-all-free-methods selector: runs composite + mt_pivot + neural (whichever are
        # available) and keeps the per-input detector-lowest. Strongest free path; never None.
        #
        # "max" is an ALIAS, not a second technique — both names build the same EnsembleRewriter
        # with the same defaults. Worth stating because they are listed side by side in --rewriter
        # choices, the README and the MCP docstring, which invites reading a benchmark row for each
        # as two data points. They are one, and the spread between them is the run-to-run variance
        # of a single stochastic method. MEASURED at n=3 on real HC3 text, full tier: "max" 0.748
        # and "ensemble" 0.485 from identical code — a 0.263 spread, which is larger than the gap
        # to standalone neural (0.322) that spread was briefly taken as evidence about.
        #
        # The "keeps the per-input detector-lowest" guarantee is scoped to ONE call: within a
        # single rewrite() every member sees the same input and the lowest scorer wins, so the
        # result cannot be worse than any single member on that draw. It does NOT extend to a
        # best_of>1 loop run. There the outer loop draws N times from each rewriter, and standalone
        # neural spends all N draws on independent stochastic T5 samples while the ensemble spends
        # each draw on an internal contest its deterministic composite member can win — so the
        # ensemble's N candidates can be far less diverse. Do not read "the ensemble is >= any
        # single method" as "ensemble beats neural at --best-of 3"; that is unproven, and at n=3
        # the same-code variance above swamps it.
        from .ensemble import EnsembleRewriter

        return EnsembleRewriter()
    if prefer == "mt_pivot":
        from .mt_pivot import MTPivotRewriter

        rw = MTPivotRewriter()
        return rw if rw.available() else None
    if prefer == "t5_paraphrase":
        from .t5_paraphrase import T5ParaphraseRewriter

        rw = T5ParaphraseRewriter()
        return rw if rw.available() else None

    # Hosted / local-policy rewriters.
    local = LocalPolicyRewriter()
    candidates = [AnthropicRewriter(), OpenAIRewriter()]
    if prefer == "openai":
        candidates = [OpenAIRewriter(), AnthropicRewriter()]
    if prefer == "local":
        candidates = [local, *candidates]
    elif local.available() and prefer is None:
        candidates = [local, *candidates]
    for rw in candidates:
        if rw.available():
            return rw
    return None


def selection_key(result: dict) -> tuple[float, float]:
    """Rank a candidate by ``(max, mean)`` — max is the objective, mean breaks ties it cannot see.

    Selecting on `max` alone silently disables this rewriter on the input it exists for. `max` is a
    single detector's number, and a saturating member pins it: MEASURED over 6 real HC3 AI answers
    at >=90 words, every baseline scored **exactly 1.000000** because `mage` returns exactly 1.0 on
    that genre. All 3 candidates per document were genuinely different text, and 0 of 3 satisfied
    `cand < baseline` — because `1.0 < 1.0` is false. So `composite`, the DEFAULT rewriter, returned
    its input byte-identical on 6 of 6 documents while `structural`, `surgical` and `targeted` each
    changed the same text. The rewriting was never the problem; the selector threw all of it away.

    The mean separates what the max cannot. Same 6 documents, 18 candidates:

        base mean 0.8661 -> 0.8193 / 0.8437 / 0.8226
        base mean 0.8337 -> 0.6789 / 0.6008 / 0.8046
        base mean 0.8944 -> 0.8774 / 0.6700 / 0.6490      (18 of 18 improved)

    This is NOT the reverted "consolation rewrite", which adopted a candidate that scored WORSE on
    the theory that changing the text was worth something. A tie on max plus a strict improvement on
    mean is a real measured gain on a real axis; a candidate that ties on both, or loses on either,
    is still rejected and the original still wins. Lexicographic order gives exactly that.
    """
    mx = float(result["max"])
    # `score_text` already publishes `mean`, computed before the per-detector values are rounded to
    # 4dp, and `EnsembleRewriter._rank` ranks on exactly this pair. Prefer it: recomputing from the
    # rounded `detectors` dict double-rounds (measured, it disagrees by ~4e-5 on 5 of 6 documents)
    # and would let two selectors in the same codebase order the same candidates differently.
    # The fallback stays for score dicts that carry no `mean` — non-numeric entries and bools are
    # excluded there because `isinstance(True, int)` is True and a flag must not enter a score mean.
    if isinstance(result.get("mean"), (int, float)) and not isinstance(result.get("mean"), bool):
        return (mx, float(result["mean"]))
    vals = [
        float(v)
        for v in result.get("detectors", {}).values()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    ]
    return (mx, sum(vals) / len(vals) if vals else mx)
