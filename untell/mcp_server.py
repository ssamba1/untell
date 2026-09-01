"""MCP server — expose the humanizer as tools to Claude Desktop and other MCP clients.

Run: ``untell-mcp`` (after ``pip install -e ".[mcp]"``). Register it in your MCP client's config.
Tools: ``score``, ``sentences``, ``tells``, ``untell``, ``verify_commercial``, ``compare``,
``ceiling``, ``scrub`` — the authoritative list is ``_TOOL_NAMES`` below, and ``untell-mcp
--list-tools`` prints it. (This line said ``verify``; no such tool has ever been registered.)

The ``mcp`` package is imported lazily so this module imports fine without it (the server build needs
it). Keeping logic thin: each tool delegates to the same functions the CLIs use.
"""

from __future__ import annotations

import argparse
import logging

# Free, no-key rewriter backends selectable via the ``rewriter`` arg; anything else (e.g. "auto")
# routes to a hosted/local-policy backend via prefer=None.
_FREE_REWRITERS = frozenset(
    {"surgical", "structural", "composite", "targeted", "neural", "ensemble", "max",
     "t5_paraphrase", "mt_pivot"}
)


_TIERS = ("lite", "full", "heavy", "commercial")

# The tools this server registers. A literal rather than a derived list because `_server()`
# needs the optional `mcp` package, and `--help` must work on an install that does not have it.
# tests/test_mcp_server.py asserts this matches what the server actually registers, so the two
# cannot drift apart silently.
_TOOL_NAMES = ("score", "sentences", "tells", "untell", "verify_commercial",
               "ceiling", "compare", "scrub")


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
        if kind in ("probability", "count", "count_or_zero", "top", "seed"):
            # A non-numeric string crashes the conversions below, and the whole point of this
            # guard is that an MCP client can send ANYTHING (the docstring above says so). The
            # tier check is a string membership test and cannot raise; the numeric kinds convert
            # with float()/int(), which raise on garbage. Caught here and returned as a refusal
            # dict like every other out-of-range answer — a traceback is what this function
            # exists to prevent. MEASURED before: _bad_args(threshold=("abc", "probability"))
            # raised ValueError instead of refusing.
            #
            # `None` is a MEANING for top/seed (the documented "use the default" for an
            # optional int), not an out-of-range number, so it skips the conversion entirely
            # and falls through to the range checks below, which already exempt it
            # (`value is not None`). Converting it would raise TypeError and reject the
            # default — the sentences tool answers {"error": "top=None is not a number"}
            # to an ordinary call that omits top. MEASURED: _bad_args(top=(None, "top"))
            # rejected the default until the conversion was skipped.
            #
            # The other kinds have no None default and still refuse it: a threshold of None
            # is not a probability, so _bad_args(threshold=(None, "probability")) must
            # keep answering a refusal dict, not None.
            if value is None and kind in ("top", "seed"):
                continue
            try:
                if kind == "probability":
                    float(value)
                else:
                    int(value)
            except (TypeError, ValueError, OverflowError):
                # OverflowError is real: int(float('inf')) raises it, and a JSON client can
                # send 1e999, which Python's json parses as inf. The three exceptions are the
                # full set int()/float() can raise on a non-whole argument.
                return {"error": f"{name}={value!r} is not a number; expected a "
                                 f"{'probability in [0, 1]' if kind == 'probability' else 'whole number'}."}
        if kind == "probability" and not (0.0 <= float(value) <= 1.0):
            return {"error": f"{name}={value!r} is outside [0, 1]. Detector scores are "
                             "probabilities, so a value above 1 can never be reached."}
        if kind == "count" and not (1 <= int(value) <= 100):
            return {"error": f"{name}={value!r} is outside 1..100."}
        # Zero is a MEANING for some counts, not an out-of-range value. `confirm=0` is the default
        # and says "do not re-confirm"; validating it as a "count" rejected the default, so the
        # flagship tool answered {"error": "confirm=0 is outside 1..100."} to every ordinary call.
        # Caught by testing the boundary rather than the middle. REST models the same field as
        # ge=0, le=32.
        if kind == "count_or_zero" and not (0 <= int(value) <= 32):
            return {"error": f"{name}={value!r} is outside 0..32."}
        # Optional, and 0 is a meaning ("flag none") rather than an out-of-range value.
        if kind == "top" and value is not None and not (0 <= int(value) <= 10_000):
            return {"error": f"{name}={value!r} is outside 0..10000. A negative value is not "
                             "'fewer' — it slices from the end, so -1 flags all but one."}
        # A seed names a stream, so two seeds that differ must name different streams. CPython's
        # `random.seed()` takes the ABSOLUTE value of an int, so -1 and 1 are one stream: measured
        # byte-identical output for both where 0, 2, 7 and 12345 each differed. `None` is the
        # default and means "derive it from the text", so it is not out of range.
        if kind == "seed" and value is not None and not (0 <= int(value) <= 2**64 - 1):
            return {"error": f"{name}={value!r} is outside 0..2**64-1. A negative seed is not a "
                             "different stream — random.seed() reads its absolute value, so -1 "
                             "and 1 give byte-identical output."}
    return None


def _text_too_long(text: str, name: str = "text") -> dict | None:
    """Refuse an oversized text the way the REST surface refuses it with 422.

    MEASURED through the real engine: `tells` accepted a 1,018,136-character payload and
    occupied the worker for 230 s before returning. REST rejects the same shape at the
    edge — every request model bounds `text` at MAX_INPUT_CHARS, and api_server.py's
    comment explains why: "Rejecting at the edge turns an unbounded request into a 422
    instead of a tied-up worker". MCP is equally a network surface with an untrusted
    caller, and the mcp SDK runs sync tool functions DIRECTLY in the event loop, so an
    unbounded payload blocks every other call and cannot be interrupted by a client
    disconnect — the megabyte case is not a slow answer, it is a wedged server.

    The bound is the SAME constant REST imports (untell.scripts.score.MAX_INPUT_CHARS),
    so the two surfaces cannot drift apart; the CLI truncates with a warning instead,
    because it is not a network surface (documented in api_server.py).
    """
    from untell.scripts.score import MAX_INPUT_CHARS

    if len(text) > MAX_INPUT_CHARS:
        return {
            "error": f"{name} is {len(text)} characters; the maximum is {MAX_INPUT_CHARS}. "
                     "The REST API rejects the same input with 422 — an unbounded text ties "
                     "up the worker (measured: 230 s for a 1 MB tells call)."
        }
    return None


def _server():
    from mcp.server.fastmcp import FastMCP

    from untell.attacks import count_hidden, scrub_hidden
    from untell.rewriter.prompts import STYLE_NAMES
    from untell.scripts.run import untell_text
    from untell.scripts.score import score_text, split_detector_errors
    from untell.scripts.sentences import score_sentences
    from untell.scripts.tells import score_tells
    from untell.scripts.verify import verify

    server = FastMCP("untell")

    @server.tool()
    def score(text: str, tier: str = "full", threshold: float = 0.30) -> dict:
        """Score text for AI-likelihood: max + ai_percent 0-100 + per-detector breakdown.

        `max` and `ai_percent` are PER-DOCUMENT SCORES for the text passed in — not the fraction of
        that text which is AI-written, and not the share of a corpus that would be flagged. The
        distinction is not pedantry: four published studies this repo audits reported a mean
        per-document score inside a table of false-positive rates, which is how "83.8% human" comes
        to be read as "16% of applicants used AI".

        `tier` defaults to "full" to match POST /score on the REST API — the same named operation
        returned a different answer depending on which surface a caller reached it through, because
        this one ran a single stdlib heuristic and that one ran the four-detector ensemble.
        `threshold` was missing entirely here, so `flagged` was frozen at the 0.30 default and a
        caller could not ask the question they meant to ask.
        """
        bad = _bad_args(tier=(tier, "tier"), threshold=(threshold, "probability"))
        bad = bad or _text_too_long(text)
        # Same normalisation the REST surface applies: a failed detector's message travels in
        # `detector_errors` rather than inside `detectors`, where it makes a map of numbers hold a
        # string. MEASURED with three detectors broken, this surface returned
        # {'roberta_openai': None, 'roberta_openai__error': 'broken on purpose', ...} — mixed
        # float / None / str — because the fix lived in api_server and only /score called it.
        return bad or split_detector_errors(score_text(text, tier=tier, threshold=threshold))

    @server.tool()
    def sentences(
        text: str,
        tier: str = "lite",
        threshold: float = 0.30,
        # The CLI's `--top`, absent here and from REST. It decides WHICH sentences come back
        # flagged — the whole output of this tool — so a client could not ask the question the
        # CLI answers and always got the worst-third default. Unset keeps that default.
        top: int | None = None,
    ) -> dict:
        """Per-sentence AI scores and the list of sentences flagged as AI (the worst ~third).

        `top` caps how many come back flagged; unset means the worst ~third.
        """
        bad = _bad_args(
            tier=(tier, "tier"), threshold=(threshold, "probability"), top=(top, "top")
        )
        return bad or _text_too_long(text) or score_sentences(text, tier=tier, threshold=threshold, top=top)

    @server.tool()
    def tells(text: str, include_matches: bool = False) -> dict:
        """Count AI writing tells (the machine-writing catalog). Lower is more human-reading.
        Returns tells total, tells_per_100w, burstiness_cv, and per-category breakdown."""
        return _text_too_long(text) or score_tells(text, include_matches=include_matches)

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
        # Same reason `best_of` and `polish` above are here: a knob that reaches the loop from one
        # surface and not another means the same request answers differently by protocol.
        seed: int | None = None,
        # The last two the REST /humanize body models and this tool did not. Enumerated rather than
        # guessed: comparing the three surfaces knob by knob, MCP was missing exactly `confirm` and
        # `detector_thresholds`, and the five others absent here (browser, progress, scrub, sim_bar,
        # veto_contradictions) are absent from REST too — a deliberate line, since those drive
        # Playwright, write to stdout, or are internals.
        #
        # Both change the VERDICT, which is why the REST comment calls dropping them quietly worse
        # than refusing them: `confirm` re-scores a pass N more times and keeps "passed" only if
        # every re-scan clears — the guard against a noisy detector re-flagging — and
        # `detector_thresholds` holds named detectors to their own stricter gates on top of the
        # global threshold. An MCP client could ask for neither.
        confirm: int = 0,
        detector_thresholds: dict[str, float] | None = None,
        # Per-candidate rejection log (issue #33). When True, result["inspect"] carries a list
        # of dicts describing for each sentence whether it was rewritten, which AI tells fired,
        # and which gate rejected each candidate. Zero overhead when False (the default). The
        # CLI exposes this as --inspect and renders it on stderr; over MCP the log rides in the
        # returned dict, where a programmatic caller can consume it. Same library knob as REST.
        inspect: bool = False,
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
            seed: Fix the random stream. Unset derives it from the text, so the same input
                already reproduces; pass an int to compare two settings on one stream.
            voice_sample: A sample of the user's own writing (150+ words). Among candidate rewrites
                already tied on AI tells, prefer the one whose sentence length, rhythm and comma
                rate sit closest to it. A tie-break within the 0.02 detector noise band: it
                never costs AI tells, and can cost up to 0.02 of detector score (measured 0.009 at
                worst, on 3 of 12 texts). It scores only those three habits, because those are the
                ones a free rewriter measurably moves.
        """
        from untell.rewriter import get_rewriter

        bad = _bad_args(
            tier=(tier, "tier"),
            threshold=(threshold, "probability"),
            margin=(margin, "probability"),
            max_iters=(max_iters, "count"),
            best_of=(best_of, "count"),
            confirm=(confirm, "count_or_zero"),
            seed=(seed, "seed"),
        )
        if bad:
            return bad
        bad = _text_too_long(text)
        if voice_sample:
            # The REST /humanize body bounds voice_sample at the same MAX_INPUT_CHARS; a
            # megabyte "sample" would otherwise sit in memory through the whole loop.
            bad = bad or _text_too_long(voice_sample, "voice_sample")
        if bad:
            return bad

        # `detector_thresholds` values must be probabilities in [0, 1], for the same reason the
        # global `threshold` must be. A value above 1 can never be reached by a detector score
        # (all scores are P(AI) in [0, 1]), so {"hc3_roberta": 50} silently makes the hc3_roberta
        # gate unreachable — the text always passes for that detector even at score=1.0. The
        # global `threshold` is already refused above via `_bad_args`; per-detector overrides were
        # the one path that bypassed the same check. MEASURED: a caller who set threshold=0.5 and
        # detector_thresholds={"hc3_roberta": 50.0} got a 200 response where hc3_roberta never
        # contributed to the flagged verdict, silently.
        if detector_thresholds:
            for _dt_name, _dt_val in detector_thresholds.items():
                try:
                    _dt_f = float(_dt_val)
                except (TypeError, ValueError):
                    return {
                        "error": f"detector_thresholds[{_dt_name!r}]={_dt_val!r} is not a number; "
                                 "expected a probability in [0, 1]."
                    }
                if not (0.0 <= _dt_f <= 1.0):
                    return {
                        "error": f"detector_thresholds[{_dt_name!r}]={_dt_val!r} is outside [0, 1]. "
                                 "Detector scores are probabilities; a value above 1 can never be "
                                 "reached, so this per-detector gate would never fire."
                    }

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
        # `pre` and `post` are score dicts of their own, so they carry the same `name__error`
        # sidecars — two per response, on the surface a client is most likely to read numerically.
        result = split_detector_errors(untell_text(
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
            seed=seed,
            confirm=confirm,
            detector_thresholds=detector_thresholds,
            inspect=inspect,
        ))
        # untell_text answers an unknown/unavailable rewriter with {"error": ..., "final":
        # <original UNCHANGED>, "seed": ...} (run.py returns that dict before the loop runs).
        # Nothing was rewritten, but the shape reads as a successful humanization to a client
        # that checks `final` — the key this tool's own docstring advertises as "the humanized
        # text". MEASURED before this guard: untell(rewriter='does_not_exist') came back with
        # the caller's text verbatim in `final`. The CLI refuses the name at parse time
        # (argparse choices) and REST answers 422; on MCP there is no status code, so the
        # refusal must be the pure error dict every other guard on this surface returns
        # (_bad_args, style, ceiling-rewriter) — an unchanged original must never pass for a
        # rewrite, and `seed` on a refusal is meaningless.
        if "error" in result:
            return {"error": result["error"]}
        return result

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
            tier: Local detector tier to include (default full; pass 'commercial' or '' for API-only).
            sandbox: Use Copyleaks free mock mode (not real scores).
            browser: Comma-separated free-web-UI checkers (e.g. 'zerogpt').
        """
        # The one tool _bad_args was written for and never wired into. MEASURED before this guard:
        # threshold=50 returned passes_all=True with only a warning string saying nothing could
        # ever fail, and tier='bogus' ran the lite tier and said so only inside a warning. REST
        # /verify rejects both with 422 (its threshold is a pydantic [0,1] probability and its tier
        # a Literal) and the CLI rejects the tier at parse time. A VERIFICATION tool answering
        # "passes_all: True" to an impossible threshold is the worst place to be lenient — the
        # whole job of this tool is an honest verdict.
        if tier not in _TIERS and tier != "":
            return {
                "error": f"unknown tier {tier!r} — valid: {', '.join(_TIERS)} (or '' for "
                         "commercial-only, which skips the local ensemble). It would have silently "
                         "fallen back to the lite heuristic."
            }
        bad = _bad_args(threshold=(threshold, "probability"))
        bad = bad or _text_too_long(text)
        if bad:
            return bad
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

        # The tool `_bad_args` was written for and never wired into. Its docstring names both of
        # these and says "this was the third surface, still silent" — `ceiling` was the fourth, and
        # it validated the rewriter name while letting the tier and the threshold through.
        # MEASURED before this, one sample:
        #
        #     tier="bogus"      result reports tier: "bogus", only perplexity_burstiness ran
        #     threshold=50.0    pre_flagged_rate 0.0, post_flagged_rate 0.0, no warning
        #
        # The second is the worse one on a MEASUREMENT tool. A threshold above 1 cannot be reached
        # by a probability, so nothing is ever flagged and the answer reads as a perfect result —
        # 0% flagged before and after — when in fact nothing was measured at all.
        bad = _bad_args(
            tier=(tier, "tier"),
            threshold=(threshold, "probability"),
            max_iters=(max_iters, "count"),
            best_of=(best_of, "count"),
            n=(n, "count"),
        )
        if bad:
            return bad

        if rewriter not in _FREE_REWRITERS and rewriter != "auto":
            # MEASURED: this used to hand the name to measure_ceiling, whose aggregation DROPS
            # the per-text `{"error": ...}` dicts untell_text returns for an unknown name
            # (eval/ceiling.py: `if "error" not in res and "post" in res`). The result then
            # reported `"rewriter": "wat"` — a name that does not exist — as the rewriter that
            # produced the numbers, after running the whole measurement (106 s on full tier).
            # The CLI refuses the same name at parse time (argparse `choices`) and REST answers
            # 422 "unknown rewriter {name}"; this was the hole.
            return {
                "error": f"unknown rewriter {rewriter!r} — it would have run a full measurement "
                         "that reports a rewriter by that name while nothing by that name ran "
                         f"(per-text refusals are dropped in the aggregation). Valid: "
                         f"{', '.join(sorted(_FREE_REWRITERS))}, auto."
            }

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
        vs blind paraphrase vs the closed loop. Returns per-technique scores and AI-tell counts,
        over the built-in sample corpus (named in the result's `corpus` field).
        """
        # `texts` and `corpus`, because the underlying function requires both and this tool passed
        # neither. It called `compare(tier=tier)` against a signature of
        # `compare(texts, tier=..., threshold=..., corpus=...)`, so EVERY invocation raised
        # TypeError: compare() missing 1 required positional argument: 'texts'. The tool was dead
        # on a shipped surface, and an MCP client got a traceback rather than a refusal it could
        # act on — the same class of gap `_bad_args` exists to close for the other tools.
        #
        # The corpus label is not decorative. `_render` reads `result["corpus"]` and the function's
        # own docstring records that calling it directly produced a report headed "corpus=unknown";
        # nine results in this repository once generalised from a demo corpus, so a comparison that
        # cannot name its own is unquotable. The CLI passes "built-in sample" for this corpus and
        # this tool now says the same thing rather than inventing a second name for it.
        from eval.compare_humanizers import _SAMPLE, compare

        bad = _bad_args(tier=(tier, "tier"))
        if bad:
            return bad
        return compare(list(_SAMPLE), tier=tier, corpus="built-in sample")

    @server.tool()
    def scrub(text: str) -> dict:
        """Strip hidden watermark / zero-width / homoglyph characters from text, returning
        the cleaned text and the count of characters removed."""
        return _text_too_long(text) or {
            "clean": scrub_hidden(text), "hidden_chars_removed": count_hidden(text)
        }

    return server


def build_parser() -> argparse.ArgumentParser:
    """Every other console script in this package answers ``--help``; this one did not.

    ``main`` ignored ``argv`` entirely and went straight to ``_server().run()``, which speaks the
    MCP protocol over stdin/stdout. So ``untell-mcp --help`` printed nothing and exited 0 — and any
    mistyped flag silently started a server that then blocked waiting for JSON-RPC on a terminal.
    Silence is the worst possible response to ``--help``: it is indistinguishable from a broken
    install, and the thing it actually did was invisible.
    """
    p = argparse.ArgumentParser(
        prog="untell-mcp",
        description=(
            "Run the untell MCP server. It speaks JSON-RPC over stdin/stdout and is meant to be "
            "launched by an MCP client (Claude Desktop and similar), not run by hand — started "
            "from a terminal it will simply wait for input. Register it in your client's config "
            "instead. Tools exposed: " + ", ".join(_TOOL_NAMES) + "."
        ),
        epilog="Requires the optional dependency: pip install -e \".[mcp]\"",
    )
    p.add_argument(
        "--list-tools",
        action="store_true",
        help="print the tool names this server exposes and exit, without starting it",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_tools:
        print("\n".join(_TOOL_NAMES))
        return 0
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    _server().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
