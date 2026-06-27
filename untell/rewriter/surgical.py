"""Free, no-key surgical rewriter — word-importance substitution as a ``Rewriter`` backend.

The free-ceiling report's **Move #2**: promote PWWS / TextFooler-style word-importance substitution
into the closed loop. Unlike the hosted (Anthropic/OpenAI) and local-policy rewriters, this needs
**no API key, no GPU, and no model download** — it is pure stdlib plus the lite detector. That makes
the whole closed loop runnable at $0, which is what lets the eval harness (``eval/ceiling.py``)
*measure* untell's inference-only evasion ceiling against the local ensemble — the data point the
literature is missing (see ``docs/free-ceiling-report.md``).

It rewrites by ranking each word by how much it drives the detector score, then swapping the
highest-importance words for score-lowering synonyms (``untell.attacks.surgical_substitute``). Minimal
surface change, so the meaning-similarity gate in the loop is easy to hold; deterministic, so the
measurement is reproducible. Weak on its own (a small synonym map, ``max_subs`` swaps) — it is the
*floor* of the free regime, not the ceiling, and the report says so.
"""

from __future__ import annotations

_SCOREABLE = ("lite", "full", "heavy", "commercial")


class SurgicalRewriter:
    """Deterministic CPU rewriter backed by ``surgical_substitute``. Always ``available()``."""

    name = "surgical"
    # Deterministic: identical input -> identical output. The loop uses this to stop early once an
    # iteration stops changing the text (re-running would be a guaranteed no-op).
    deterministic = True

    def __init__(self, max_subs: int = 12):
        self.max_subs = max_subs

    def available(self) -> bool:
        # Pure stdlib + the lite detector — runnable anywhere, no key, no heavy deps.
        return True

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        from untell.attacks import surgical_substitute

        # Target the tier the loop is actually scoring against so the swaps lower the RIGHT signal.
        # Composite labels (e.g. a browser scorer's "browser:zerogpt") aren't directly scoreable;
        # fall back to the full local ensemble, or lite if full isn't implied.
        tier = score_result.get("tier", "lite")
        if tier not in _SCOREABLE:
            tier = "full" if "full" in str(tier) else "lite"
        return surgical_substitute(text, tier=tier, threshold=threshold, max_subs=self.max_subs)["text"]
