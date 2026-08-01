"""MCP server — expose the humanizer as tools to Claude Desktop and other MCP clients.

Run: ``untell-mcp`` (after ``pip install -e ".[mcp]"``). Register it in your MCP client's config.
Tools: ``score``, ``sentences``, ``tells``, ``untell``, ``verify``, ``compare``, ``ceiling``, ``scrub``.

The ``mcp`` package is imported lazily so this module imports fine without it (the server build needs
it). Keeping logic thin: each tool delegates to the same functions the CLIs use.
"""

from __future__ import annotations

import logging

# Free, no-key rewriter backends selectable via the ``rewriter`` arg; anything else (e.g. "auto")
# routes to a hosted/local-policy backend via prefer=None.
_FREE_REWRITERS = frozenset(
    {"surgical", "structural", "composite", "neural", "ensemble", "max", "t5_paraphrase", "mt_pivot"}
)


def _server():
    from mcp.server.fastmcp import FastMCP

    from untell.attacks import count_hidden, scrub_hidden
    from untell.scripts.run import untell_text
    from untell.scripts.score import score_text
    from untell.scripts.sentences import score_sentences
    from untell.scripts.tells import score_tells
    from untell.scripts.verify import verify

    server = FastMCP("untell")

    @server.tool()
    def score(text: str, tier: str = "lite") -> dict:
        """Score text for AI-likelihood: max + ai_percent 0-100 + per-detector breakdown."""
        return score_text(text, tier=tier)

    @server.tool()
    def sentences(text: str, tier: str = "lite", threshold: float = 0.30) -> dict:
        """Per-sentence AI scores and the list of sentences flagged as AI (the worst ~third)."""
        return score_sentences(text, tier=tier, threshold=threshold)

    @server.tool()
    def tells(text: str, include_matches: bool = False) -> dict:
        """Count AI writing tells (the machine-writing catalog). Lower is more human-reading.
        Returns tells total, tells_per_100w, burstiness_cv, and per-category breakdown."""
        return score_tells(text, include_matches=include_matches)

    @server.tool()
    def untell(
        text: str,
        tier: str = "lite",
        threshold: float = 0.30,
        style: str | None = None,
        max_iters: int = 5,
        rewriter: str = "auto",
        best_of: int = 1,
        margin: float = 0.0,
    ) -> dict:
        """Run the closed untell loop: score -> rewrite -> re-score until the hardest
        detector passes or max_iters is hit. Needs an LLM rewriter key, or pass
        rewriter='surgical' for the free deterministic word-substitution rewriter ($0, no key).

        Args:
            text: The AI-sounding text to humanize.
            tier: Detector tier (lite, full, heavy, commercial).
            threshold: Max P(AI) to pass (default 0.30).
            style: Optional voice (casual, professional, academic, blunt, storytelling, journalistic).
            max_iters: Max rewrite iterations (default 5).
            rewriter: free no-key backend ('composite' best default, 'neural' = T5+structural+surgical
                strongest but needs .[full], 'surgical'/'structural'/'t5_paraphrase'/'mt_pivot'), or
                'auto' (hosted LLM if a key is set, else fail).
            best_of: Draw N candidates per iteration, keep the best-scoring one.
            margin: Safety margin below threshold for a comfortable pass.
        """
        from untell.rewriter import get_rewriter

        rw = None
        if rewriter in _FREE_REWRITERS:
            rw = get_rewriter(prefer=rewriter)
            if rw is None:
                # Do NOT fall through with rewriter=None. untell_text would then call get_rewriter()
                # with no preference, which returns the first AVAILABLE backend — the hosted
                # Anthropic/OpenAI rewriter when a key is set. A caller who explicitly asked for a
                # free no-key backend (mt_pivot / t5_paraphrase need the .[full] extra) would have
                # their API silently BILLED, with nothing in the result to reveal the substitution.
                # The ceiling tool already guards this; the asymmetry was the bug.
                return {
                    "error": f"rewriter '{rewriter}' is unavailable — it needs the '.[full]' extra "
                    "(pip install -e '.[full]'). Refusing to silently fall back to a paid rewriter; "
                    "pass rewriter='composite' for the zero-dependency free path."
                }
        return untell_text(
            text,
            tier=tier,
            threshold=threshold,
            style=style,
            max_iters=max_iters,
            rewriter=rw,
            best_of=best_of,
            margin=margin,
        )

    @server.tool()
    def verify_commercial(
        text: str,
        threshold: float = 0.30,
        tier: str = "full",
        sandbox: bool = False,
        browser: str | None = None,
    ) -> dict:
        """Pass/fail vs every configured commercial checker (needs API keys) plus the
        local detector ensemble. Returns per-checker scores and overall verdict.

        Args:
            text: Text to check.
            threshold: Max P(AI) to pass.
            tier: Local detector tier to include (default full; pass 'commercial' for API-only).
            sandbox: Use Copyleaks free mock mode (not real scores).
            browser: Comma-separated free-web-UI checkers (e.g. 'zerogpt').
        """
        browser_list = [s.strip() for s in browser.split(",")] if browser else None
        tier_arg: str | None = None if (tier or "").lower() in ("commercial", "") else tier
        return verify(text, threshold=threshold, sandbox=sandbox, browser=browser_list, tier=tier_arg)

    @server.tool()
    def ceiling(
        tier: str = "full",
        threshold: float = 0.30,
        max_iters: int = 5,
        rewriter: str = "surgical",
        best_of: int = 1,
        n: int = 3,
    ) -> dict:
        """Measure untell's inference-only evasion ceiling against the LOCAL detector ensemble.
        Reports before/after flagged rate and mean max P(AI).

        Args:
            tier: Detector tier.
            threshold: Pass threshold.
            max_iters: Max iterations per sample.
            rewriter: 'surgical' (free, default) or 'auto' (needs API key).
            best_of: Candidates per iteration.
            n: Number of test paragraphs (from the built-in sample).
        """
        from eval.ceiling import measure_ceiling
        from untell.rewriter import get_rewriter

        rw = None
        if rewriter in _FREE_REWRITERS:
            rw = get_rewriter(prefer=rewriter)
            if rw is None:
                return {"error": f"{rewriter} rewriter unavailable (needs .[full] extra)"}
        # `n` was declared and documented but never forwarded: measure_ceiling has no n parameter,
        # so texts=None always meant "use the whole built-in sample" and the result came back with
        # n=3 regardless — making it look like the caller's value had been honoured. Slice the
        # sample here so the parameter does what its docstring says.
        from eval.ceiling import _SAMPLE

        texts = list(_SAMPLE)[: max(1, n)]
        return measure_ceiling(
            texts,
            tier=tier,
            threshold=threshold,
            max_iters=max_iters,
            rewriter=rw,
            best_of=best_of,
        )

    @server.tool()
    def compare(tier: str = "lite") -> dict:
        """Head-to-head comparison of humanizer techniques: synonym-swap vs back-translation
        vs blind paraphrase vs the closed loop. Returns per-technique scores and AI-tell counts.
        """
        from eval.compare_humanizers import compare

        return compare(tier=tier)

    @server.tool()
    def scrub(text: str) -> dict:
        """Strip hidden watermark / zero-width / homoglyph characters from text, returning
        the cleaned text and the count of characters removed."""
        return {"clean": scrub_hidden(text), "hidden_chars_removed": count_hidden(text)}

    return server


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    _server().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
