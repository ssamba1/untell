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
    {"surgical", "structural", "composite", "targeted", "neural", "ensemble", "max",
     "t5_paraphrase", "mt_pivot"}
)


_TIERS = ("lite", "full", "heavy", "commercial")


# Module level, not nested in `_server`, so the checks are testable without the optional `mcp`
# package installed — otherwise every test of them skips on exactly the machines that run the
# suite, which is the same as not having them.
def _bad_args(**checks) -> dict | None:
    """Reject an out-of-range argument the way this file already rejects an unknown style.

    These parameters were plain `str`/`float`/`int` annotations, so an MCP client could send
    anything: `tier="fulll"` matches no tier and falls back to the lite heuristic, answering
    with a lite-shaped result and no sign the requested tier was never honoured, and
    `threshold=50` produces a verdict in which nothing can ever be flagged, because the scores
    it is compared against live in [0, 1]. The CLI rejects both at parse time and the REST
    surface now answers 422; this was the third surface, still silent.

    Named-and-returned rather than raised, matching the unknown-style and unknown-rewriter
    errors above — an MCP client reads the dict.
    """
    for name, (value, kind) in checks.items():
        if kind == "tier" and value not in _TIERS:
            return {"error": f"unknown tier {value!r} — valid: {', '.join(_TIERS)}. "
                             "It would have silently fallen back to the lite heuristic."}
        if kind == "probability" and not (0.0 <= float(value) <= 1.0):
            return {"error": f"{name}={value!r} is outside [0, 1]. Detector scores are "
                             "probabilities, so a value above 1 can never be reached."}
        if kind == "count" and not (1 <= int(value) <= 100):
            return {"error": f"{name}={value!r} is outside 1..100."}
    return None


def _server():
    from mcp.server.fastmcp import FastMCP

    from untell.attacks import count_hidden, scrub_hidden
    from untell.rewriter.prompts import STYLE_NAMES
    from untell.scripts.run import untell_text
    from untell.scripts.score import score_text
    from untell.scripts.sentences import score_sentences
    from untell.scripts.tells import score_tells
    from untell.scripts.verify import verify

    server = FastMCP("untell")

    @server.tool()
    def score(text: str, tier: str = "full", threshold: float = 0.30) -> dict:
        """Score text for AI-likelihood: max + ai_percent 0-100 + per-detector breakdown.

        `tier` defaults to "full" to match POST /score on the REST API — the same named operation
        returned a different answer depending on which surface a caller reached it through, because
        this one ran a single stdlib heuristic and that one ran the four-detector ensemble.
        `threshold` was missing entirely here, so `flagged` was frozen at the 0.30 default and a
        caller could not ask the question they meant to ask.
        """
        bad = _bad_args(tier=(tier, "tier"), threshold=(threshold, "probability"))
        return bad or score_text(text, tier=tier, threshold=threshold)

    @server.tool()
    def sentences(text: str, tier: str = "lite", threshold: float = 0.30) -> dict:
        """Per-sentence AI scores and the list of sentences flagged as AI (the worst ~third)."""
        bad = _bad_args(tier=(tier, "tier"), threshold=(threshold, "probability"))
        return bad or score_sentences(text, tier=tier, threshold=threshold)

    @server.tool()
    def tells(text: str, include_matches: bool = False) -> dict:
        """Count AI writing tells (the machine-writing catalog). Lower is more human-reading.
        Returns tells total, tells_per_100w, burstiness_cv, and per-category breakdown."""
        return score_tells(text, include_matches=include_matches)

    # NOT decorated inline: `server.tool()` snapshots __doc__ as the advertised description at
    # registration time, so patching the style list in afterwards had no effect on what a client
    # actually sees. Patch first, register second.
    def untell(
        text: str,
        # "full", matching the CLI's --tier default and POST /humanize. The loop OPTIMISES against
        # whatever tier it is given, so lite meant driving a single stdlib heuristic the README calls
        # "weak — a demo signal, not an evasion claim", and returning a "passed" verdict the CLI's
        # four-detector ensemble would have rejected. Same shape as the best_of=1 default below.
        tier: str = "full",
        threshold: float = 0.30,
        style: str | None = None,
        max_iters: int = 5,
        # "composite", matching the CLI's default, NOT "auto". MEASURED: calling this tool with
        # defaults returned {"error": "no rewriter configured"} on any install without an API key.
        # "auto" is not in _FREE_REWRITERS, so it fell through unresolved, and untell_text's
        # auto-select declines to pick a backend when no key is set — even though `composite` is
        # free, always available, and the documented zero-dependency path. The flagship MCP tool
        # failed out of the box while the identical CLI invocation worked.
        rewriter: str = "composite",
        # 3, matching the CLI's `untell humanize --best-of` default. MEASURED over 6 real HC3
        # paragraphs, this is the difference between the strong path and the weak one:
        #     best_of=1  mean 0.601 -> 0.293, 33% still flagged
        #     best_of=3  mean 0.601 -> 0.256,  0% still flagged
        # The CLI moved to 3 after best-of-1 was identified as a root cause of understated
        # evasion. MCP and the REST API were left on 1, so every non-CLI caller got the weak
        # path. (The `ceiling` tool below stays at 1 — that matches ITS cli, eval/ceiling.py,
        # where measuring the single-draw baseline is the point.)
        best_of: int = 3,
        margin: float = 0.0,
        # Exposed because the REST API's /humanize does. `untell_text` was always called with the
        # default polish=False here, so the same loop reached through MCP produced a strictly
        # weaker result than through HTTP, with nothing to indicate a knob was missing.
        polish: bool = False,
        # The CLI takes a FILE path; over MCP the sample travels as text. Tie-break only.
        voice_sample: str | None = None,
    ) -> dict:
        """Run the closed untell loop: score -> rewrite -> re-score until the hardest
        detector passes or max_iters is hit. Needs an LLM rewriter key, or pass
        rewriter='surgical' for the free deterministic word-substitution rewriter ($0, no key).

        Args:
            text: The AI-sounding text to humanize.
            tier: Detector tier (lite, full, heavy, commercial).
            threshold: Max P(AI) to pass (default 0.30).
            style: Optional voice. See STYLE_NAMES — the list is appended to this docstring at
                import time rather than written out here, because the hand-copied version had
                drifted to 6 of the 14 and this docstring is what an MCP client reads to learn
                the valid values.
            max_iters: Max rewrite iterations (default 5).
            rewriter: free no-key backend ('composite' best default, 'neural' = T5+structural+surgical
                strongest but needs .[full], 'surgical'/'structural'/'t5_paraphrase'/'mt_pivot'), or
                'auto' (hosted LLM if a key is set, else fail).
            best_of: Draw N candidates per iteration, keep the best-scoring one.
            margin: Safety margin below threshold for a comfortable pass.
            polish: Run a final word-level substitution pass over the result, adopted only if it
                lowers the score without un-passing it. Matches /humanize on the REST API.
            voice_sample: A sample of the user's own writing (150+ words). Among candidate rewrites
                already tied on AI tells, prefer the one whose sentence length, rhythm and comma
                rate sit closest to it. A tie-break only, so it never costs evasion or
                naturalness — and it scores only those three habits, because those are the ones a
                free rewriter measurably moves.
        """
        from untell.rewriter import get_rewriter

        bad = _bad_args(
            tier=(tier, "tier"),
            threshold=(threshold, "probability"),
            margin=(margin, "probability"),
            max_iters=(max_iters, "count"),
            best_of=(best_of, "count"),
        )
        if bad:
            return bad

        # An unknown style is looked up in the STYLES dict, missed, and silently ignored — so a
        # caller asked for a voice and got a rewrite with no style applied and nothing saying so.
        # `untell humanize --style` rejects the same input at parse time (argparse `choices`), and
        # POST /humanize now returns 422. The vocabulary comes from STYLE_NAMES, the same list this
        # tool's own docstring is generated from, so the check cannot drift from what is advertised.
        if style is not None and style not in STYLE_NAMES:
            return {
                "error": f"unknown style {style!r} — it would have been silently ignored. "
                f"Valid styles: {', '.join(STYLE_NAMES)}."
            }

        rw = None
        if rewriter not in _FREE_REWRITERS and rewriter != "auto":
            # An unknown name fell through as None and was then silently auto-selected, so a typo
            # ran a DIFFERENT technique and the result was reported as if it were the requested
            # one. untell_text resolves names itself now and refuses to substitute, so hand it
            # the name and let it produce a clear error.
            rw = rewriter
        elif rewriter in _FREE_REWRITERS:
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
            polish=polish,
            voice_sample=voice_sample,
        )

    # Put the real style list into the tool's advertised description. Generated, not restated, so
    # it cannot drift out of sync with `--style` the way the hand-written list did.
    if untell.__doc__:
        untell.__doc__ = untell.__doc__.replace(
            "See STYLE_NAMES", f"one of {', '.join(STYLE_NAMES)}"
        )
    server.tool()(untell)

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
        if rewriter not in _FREE_REWRITERS and rewriter != "auto":
            # An unknown name fell through as None and was then silently auto-selected, so a typo
            # ran a DIFFERENT technique and the result was reported as if it were the requested
            # one. untell_text resolves names itself now and refuses to substitute, so hand it
            # the name and let it produce a clear error.
            rw = rewriter
        elif rewriter in _FREE_REWRITERS:
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
