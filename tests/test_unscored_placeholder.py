"""Cross-cutting guard: an unscored result must never be reported as a good result.

``score_text`` returns ``max: 0.0`` as a placeholder when no detector produced a number, and sets
``scored: False`` to say so. Every consumer that compares ``max`` against a threshold has the same
trap available to it — ``0.0 < threshold`` is true, so "nothing was measured" renders as the single
most flattering number the tool can print: 0% flagged, 100% bypass, P(AI) 0.000.

This has now been found and fixed at seven separate sites (humanness, report._bypass_rate,
training/reward, run._passed, eval_policy, ceiling, compare_humanizers). One-site tests did not stop
it recurring, so this module tests the *class*: it forces a fully dead detector stack and asserts
that each aggregator refuses to report a pass. New aggregators belong here.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import pytest

_UNSCORED = {"max": 0.0, "mean": 0.0, "scored": False, "detectors": {}, "flagged": False}

_ROOT = Path(__file__).resolve().parent.parent


def test_report_bypass_rate_does_not_count_unscored_as_a_pass():
    from eval.report import _bypass_rate

    class _R:
        post = _UNSCORED

    assert _bypass_rate([_R(), _R()], 0.30) == 0.0


def test_eval_policy_summary_does_not_count_unscored_as_a_bypass():
    from eval.eval_policy import _summary

    rows = [{"pre": 0.0, "post": 0.0, "sim": 0.9, "scored": False}] * 3
    out = _summary("policy", rows, 0.30)
    assert "100%" not in out
    assert "NOT MEASURED" in out


def test_ceiling_does_not_report_a_zero_flagged_rate_on_a_dead_stack():
    """A 0% post-flagged rate is the headline "we beat every detector" number."""
    import eval.ceiling as ceiling

    with patch.object(ceiling, "score_text", return_value=dict(_UNSCORED)), \
         patch.object(ceiling, "untell_text", return_value={"post": dict(_UNSCORED), "final": "x"}):
        r = ceiling.measure_ceiling(texts=["a b c", "d e f"], tier="lite")

    assert r["post_flagged_rate"] is None  # not 0.0
    assert r["pre_flagged_rate"] is None
    assert r["unscored"] == 2
    assert "WARNING" in ceiling._render(r)


def test_compare_humanizers_reports_na_not_perfect_evasion_on_a_dead_stack():
    import eval.compare_humanizers as ch

    with patch.object(ch, "score_text", return_value=dict(_UNSCORED)), \
         patch.object(ch, "_techniques", return_value={"none (raw AI)": lambda t: t}):
        r = ch.compare(texts=["Furthermore, the system leverages robust methodologies."], tier="lite")

    row = r["techniques"]["none (raw AI)"]
    assert row["ai_max_mean"] is None
    assert row["flagged_rate"] is None
    assert row["unscored"] == 1
    assert "n/a" in ch._render(r)


def test_humanness_does_not_treat_an_unscored_stack_as_human():
    from untell.humanness import humanness

    sample = "Furthermore, the system leverages robust methodologies to optimize outcomes."
    with patch("untell.scripts.score.score_text", return_value=dict(_UNSCORED)):
        dead = humanness(sample)
    with patch(
        "untell.scripts.score.score_text",
        return_value={**_UNSCORED, "scored": True, "detectors": {"fake": 0.0}},
    ):
        clean = humanness(sample)

    # A dead stack must not score *more human* than one that actively measured 0.0 P(AI).
    assert dead <= clean


def test_free_ensemble_score_raises_rather_than_returning_the_placeholder():
    """A 0.0 placeholder here became reward 1.0 — the maximum — for text nothing scored."""
    import training.reward as reward

    # RuntimeError specifically, not bare Exception. `pytest.raises(Exception)` also passes when
    # the call dies of an AttributeError or a TypeError — a rename or a signature change would keep
    # this test green while the guard it exists to protect had stopped running. The message is
    # asserted for the same reason: it is what tells an operator why their training run stopped.
    with patch.object(reward, "score_text", return_value=dict(_UNSCORED)):
        with pytest.raises(RuntimeError, match="no training signal"):
            reward.free_ensemble_score("some text", tier="lite")


# ---------------------------------------------------------------------------
# Static sweep: every new consumer must at least have considered the flag.
# ---------------------------------------------------------------------------

# Files that call score_text but legitimately never compare its max to a pass/fail bar. Each entry
# names why, because the cheap way to "fix" this test is to append to the list without thinking.
_EXEMPT = {
    # Pass the result dict straight back to a caller; the caller decides.
    "untell/api_server.py": "returns the dict verbatim, scored flag included",
    "untell/mcp_server.py": "returns the dict verbatim, scored flag included",
    "untell/scripts/score.py": "this is where scored is set",
    "eval/baselines.py": "hands pre/post dicts to eval.report, which applies the guard",
    # Relative ranking only: comparing placeholder to placeholder yields "no improvement", which
    # stalls the search honestly instead of declaring victory.
    "untell/rewriter/composite.py": "ranks candidates against each other, no threshold test",
    "untell/rewriter/ensemble.py": "ranks candidates against each other, no threshold test",
    "untell/rewriter/targeted.py": "ranks candidates against each other, no threshold test",
    "untell/attacks/word_importance.py": "ranks candidates against each other, no threshold test",
    "untell/scripts/sentences.py": "ranks sentences within one text, no pass/fail verdict",
    "untell/scripts/cli.py": "prints a demo score, makes no verdict",
    "untell/rich_output.py": "renders numbers it is handed, does not decide",
    # The scan is textual, so a DOCSTRING that names score_text trips it. This module is the
    # Rewriter Protocol: it defines the signature and documents that `score_result` is a hint
    # rather than the score of `text`. It makes no scoring call at all — verified by there being
    # no import of score_text anywhere in it.
    "untell/rewriter/base.py": "protocol definition; mentions score_text in prose, never calls it",
}


def _callers_of_score_text() -> list[str]:
    hits = []
    for path in list(_ROOT.glob("untell/**/*.py")) + list(_ROOT.glob("eval/*.py")) + list(
        _ROOT.glob("training/*.py")
    ):
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"\bscore_text\s*\(", text):
            hits.append(path.relative_to(_ROOT).as_posix())
    return sorted(hits)


def test_every_score_text_consumer_handles_or_is_exempt_from_the_placeholder():
    unhandled = []
    for rel in _callers_of_score_text():
        if rel in _EXEMPT:
            continue
        body = (_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        # Either it checks the flag, or it checks for signal some other way (run.py counts numeric
        # detector values directly, which is equivalent and predates the flag).
        if "scored" in body or "has_signal" in body or "all_checkers_failed" in body:
            continue
        unhandled.append(rel)

    assert not unhandled, (
        "these call score_text and compare its max without acknowledging the unscored placeholder: "
        f"{unhandled}. Either handle `scored is False` or add an entry to _EXEMPT explaining why "
        "the placeholder cannot be misread as a pass."
    )


def test_the_protocol_exemption_is_true():
    """`untell/rewriter/base.py` is exempt on the grounds that it never scores anything.

    An exemption that is merely asserted is a hole in the guard, so check the claim: the module
    must not import or call score_text. It trips the textual scan only because its Protocol
    docstring NAMES score_text while explaining that `score_result` is a hint rather than the score
    of `text` — a distinction that exists precisely to stop an implementer reusing it as a baseline.
    """
    body = (_ROOT / "untell" / "rewriter" / "base.py").read_text(encoding="utf-8")
    code = "\n".join(
        line for line in body.splitlines()
        if not line.lstrip().startswith(("#", '"""', "'''"))
    )
    assert "import score_text" not in code
    assert "score_text(" not in code.replace("``score_text(text)``", "")
