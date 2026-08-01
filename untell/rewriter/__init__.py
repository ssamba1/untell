"""Optional hosted-LLM rewriters.

The skill itself uses the running Claude as the rewriter (no key needed). This package adds an
*optional* programmatic rewriter so the loop can run fully headless — e.g. in the eval harness or
a server — by calling a hosted LLM API (Anthropic or OpenAI). Everything degrades gracefully:
with no SDK installed and no API key set, ``get_rewriter()`` returns ``None`` and callers fall
back to the deterministic scripted rewriter.

Three built-in rewriters are always available (no key, no GPU):

* ``StructuralRewriter`` (``prefer="structural"``) — sentence-level transforms (transitions,
  burstiness, participial trailers). The strongest free signal mover.
* ``SurgicalRewriter`` (``prefer="surgical"``) — word-level synonym substitution.
* **Composite** (chain both) — ``prefer="composite"`` runs structural THEN surgical,
  giving the free $0 path the most leverage.
"""

from __future__ import annotations

from .base import Rewriter, get_rewriter
from .composite import CompositeRewriter
from .ensemble import EnsembleRewriter
from .mt_pivot import MTPivotRewriter
from .prompts import build_rewrite_prompt
from .structural import StructuralRewriter
from .surgical import SurgicalRewriter
from .t5_paraphrase import T5ParaphraseRewriter

__all__ = [
    "Rewriter",
    "get_rewriter",
    "build_rewrite_prompt",
    "StructuralRewriter",
    "SurgicalRewriter",
    "CompositeRewriter",
    "MTPivotRewriter",
    "T5ParaphraseRewriter",
    "EnsembleRewriter",
]
