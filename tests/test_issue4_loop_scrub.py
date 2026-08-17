"""Issue #4 — wire scrub_hidden + surgical_substitute into the loop (defense pins).

The issue proposed two integrations for the headless loop: scrub hidden characters on INPUT
(free and safe), and reach surgical substitution as a cheap polish stage. This file pins the
first defense at the LOOP level — the unit tests (test_no_hidden_character_survives_a_scrub.py
and friends) cover `scrub_hidden` itself, but nothing covered the loop shipping clean text out —
and the second defense this fix adds: the OUTPUT side of the same scrub.

MEASURED at HEAD 127e782 (probe, C:/Users/Admin/AppData/Local/Temp/w5-8/probe_issue4.py):

* input vector (default scrub=True): a paragraph with a zero-width space between every one of
  its 238 characters came out of the loop with **0** hidden characters — the input scrub at the
  top of `_untell_text` already worked, and nothing pinned it.
* output vector (open at HEAD): a rewriter that welds a zero-width space into its output (the
  hosted-LLM echo shape) shipped those characters into `final` with scrub=True and nothing
  saying so. The input scrub cannot see characters that did not exist at input time, so the
  defense has to run on both sides of the loop. This file's
  `test_loop_scrubs_hidden_characters_a_rewriter_introduces` failed at HEAD and passes with the
  output scrub in place.
* polish stage: reachable via `polish=True` on every surface (CLI --polish, REST, MCP) and
  gated on a strict score improvement plus the meaning bar; `surgical_substitute` fires on the
  FINAL (restored) text, so the stage is pinned here to run on exactly that string.

Run: part of the fast suite, lite tier, no torch/keys/network.
"""

from __future__ import annotations

from untell.attacks import count_hidden
from untell.scripts.run import main, untell_text

AI = (
    "Furthermore, artificial intelligence has fundamentally transformed numerous industries. "
    "Moreover, organizations utilize it to significantly improve operational efficiency. Overall, "
    "the impact continues to grow across various sectors."
)

# A carrier class the loop-level probes exercise. Built with chr() so no invisible character
# ever appears in this file's source (same rule as test_count_hidden_agrees_with_scrub_hidden.py).
ZWSP = chr(0x200B)


def _with_zwsp_between_every_char(text: str) -> str:
    return ZWSP.join(text)


class _HiddenInjectingRewriter:
    """A rewriter that welds a zero-width space into a word — the hosted-LLM echo shape.

    Injection ONLY, no other edit: the detectors normalise invisible characters before scoring
    (Result 67), so the candidate scores IDENTICALLY to its source and the loop's
    ``cand <= best`` adoption guard admits it. Verified at seeds 7/102/105: adopted=1 every
    time, so the assertions genuinely exercise the scrub rather than a rejected candidate.
    """

    name = "hidden_injector"
    deterministic = True

    def available(self) -> bool:
        return True

    def rewrite(self, text, score_result, threshold=0.30):
        return text.replace("leverage", "lever" + ZWSP + "age").replace(
            "utilize", "util" + ZWSP + "ize"
        )


_INJECTOR_SRC = (
    "Furthermore, the organization leverages robust methodologies to optimize outcomes. "
    "Moreover, teams utilize novel approaches to streamline workflows and improve efficiency."
)


def test_loop_scrubs_hidden_characters_on_input() -> None:
    """Default loop (scrub=True): hidden characters the caller's text carried must not survive.

    MEASURED at HEAD: 238 zero-width spaces in -> 0 in `final`. This test pins that defense at
    the level the issue asked about (the headless loop), not just at the scrub_hidden unit level.
    """
    src = _with_zwsp_between_every_char(AI)
    assert count_hidden(src) > 0, "fixture must actually carry hidden characters"

    result = untell_text(src, tier="lite", max_iters=2, seed=101)
    assert "error" not in result
    assert count_hidden(result["final"]) == 0
    assert result["final"] != src, "the loop should have rewritten the text, not just scrubbed it"
    assert result["changed"] is True


def test_loop_scrubs_hidden_characters_a_rewriter_introduces() -> None:
    """NEW DEFENSE (this fix): scrubbing the input is not enough when a REWRITER introduces a
    hidden character — the input scrub cannot see a char that did not exist at input time.

    FAILED at HEAD 127e782 (probe): the injected zero-width space shipped into `final` with
    scrub=True and nothing saying so. With the output-side scrub it lands clean. The candidate
    scores identically (detectors normalise invisible chars), so the loop ADMITS it and the
    assertion really exercises the scrub.
    """
    result = untell_text(_INJECTOR_SRC, tier="lite", max_iters=2, seed=102,
                         rewriter=_HiddenInjectingRewriter(), scrub=True)
    assert "error" not in result
    assert result["adopted"] >= 1, "the injected candidate must be admitted for this test to bite"
    assert count_hidden(result["final"]) == 0
    assert "leverage" in result["final"], (
        "the injected word must survive the scrub as itself — scrubbed clean, not deleted"
    )


def test_loop_scrub_false_keeps_rewriter_introduced_hidden_chars() -> None:
    """scrub=False is the caller saying 'leave my characters alone', and that has to hold on the
    output side too — scrubbing would silently ignore the flag. The characters travel with the
    result and the carried_payload warning says so.
    """
    result = untell_text(_INJECTOR_SRC, tier="lite", max_iters=2, seed=103,
                         rewriter=_HiddenInjectingRewriter(), scrub=False)
    assert "error" not in result
    assert count_hidden(result["final"]) >= 1, "scrub=False must honor the flag and keep the chars"
    assert result.get("warning"), "the carried characters must be reported, not silent"


def test_loop_scrub_false_keeps_input_hidden_chars_and_warns() -> None:
    """Same honor-the-flag contract for the input side: scrub=False keeps the caller's hidden
    characters in the output and says so in `warning`.
    """
    src = _with_zwsp_between_every_char(AI)
    result = untell_text(src, tier="lite", max_iters=2, seed=104, scrub=False)
    assert "error" not in result
    assert count_hidden(result["final"]) == count_hidden(src)
    assert "invisible" in (result.get("warning") or "")


class _Identity:
    """Returns the input unchanged. The loop then has only ONE surgical_substitute caller left
    in the run: the polish stage itself (the default composite rewriter calls it internally too,
    which is why the reachability pin cannot use composite)."""

    name = "identity"
    deterministic = True

    def available(self) -> bool:
        return True

    def rewrite(self, text, score_result, threshold=0.30):
        return text


def test_polish_stage_reaches_surgical_substitute_on_the_final_text(monkeypatch) -> None:
    """The issue's second proposal: surgical substitution reachable as a polish stage. It must run
    on the FINAL (restored, already-scrubbed) text — not on masked text, not on the source — and
    only when polish=True.

    The adoption guard (strict score improvement + meaning bar) is pinned by the existing
    test_polish_never_trades_a_pass_for_a_tie / test_polish_is_still_adopted_when_it_genuinely_helps;
    this test pins the reachability and the argument it is handed.
    """
    import untell.attacks as attacks_mod

    calls: list[str] = []

    def _spy(text, **kwargs):
        calls.append(text)
        return {"text": text, "substitutions": 0, "pre": 0.0, "post": 0.0}

    monkeypatch.setattr(attacks_mod, "surgical_substitute", _spy)

    out_on = untell_text(AI, tier="lite", max_iters=2, seed=105, polish=True,
                         rewriter=_Identity())
    assert "error" not in out_on
    assert calls == [out_on["final"]], (
        "polish=True must invoke surgical_substitute exactly once, on the final text the "
        "caller receives (not on masked or intermediate text)"
    )

    calls.clear()
    out_off = untell_text(AI, tier="lite", max_iters=2, seed=105, polish=False,
                          rewriter=_Identity())
    assert "error" not in out_off
    assert calls == [], "polish=False must not invoke surgical_substitute"


def test_cli_wires_polish_and_no_scrub_into_the_loop(monkeypatch, capsys) -> None:
    """The CLI flags the issue's knobs land on: --polish and --no-scrub must reach the loop as
    polish/scrub, not be parsed and dropped. Unpinned before this test (grep found no test
    exercising either flag end to end).
    """
    import untell.scripts.run as run_mod

    captured: dict = {}

    def _fake_untell_text(text, **kwargs):
        captured.update(kwargs)
        return {"final": text, "pre": {"max": 0.9}, "post": {"max": 0.9},
                "flagged": True, "changed": False, "iterations": 0, "rewrites": 0,
                "adopted": 0, "similarity": 1.0, "tier": "lite", "sim_bar": 0.76,
                "stopped": "passed", "seed": 0}

    monkeypatch.setattr(run_mod, "untell_text", _fake_untell_text)

    rc = main(["--polish", "--no-scrub", "Some text.", "--json"])
    assert rc == 0
    assert captured.get("polish") is True
    assert captured.get("scrub") is False

    captured.clear()
    rc = main(["Some text.", "--json"])
    assert rc == 0
    assert captured.get("polish") is False
    assert captured.get("scrub") is True
