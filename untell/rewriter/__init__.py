"""Optional hosted-LLM rewriters.

The skill itself uses the running Claude as the rewriter (no key needed). This package adds an
*optional* programmatic rewriter so the loop can run fully headless — e.g. in the eval harness or
a server — by calling a hosted LLM API (Anthropic or OpenAI). Everything degrades gracefully:
with no SDK installed and no API key set, ``get_rewriter()`` returns ``None`` and callers fall
back to the deterministic scripted rewriter.
"""

from __future__ import annotations

from .base import Rewriter, get_rewriter
from .prompts import build_rewrite_prompt
from .surgical import SurgicalRewriter

__all__ = ["Rewriter", "get_rewriter", "build_rewrite_prompt", "SurgicalRewriter"]
