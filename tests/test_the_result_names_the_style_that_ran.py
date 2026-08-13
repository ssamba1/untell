"""A style that demonstrably ran was reported as `None`, and a style that never ran said nothing.

FOUND by asking whether user-supplied names fail loudly or silently — the generalisation of Result
179, where a tier typo would have removed a detector without a word. Three names were probed:

    tier      'lyte'      -> warns: "unknown tier 'lyte' — no tier matched"          loud
    rewriter  'structual' -> returns {"error": ..., "final": text}                   loud
    style     'acadmic'   -> silently neutral, nothing said                          SILENT

MEASURED at seed 5 on the same text, `style="academic"` produced different output from `style=None`
— the academic profile keeps the transitions the neutral one strips — so the parameter plainly
works. And `post["style"]` was `None` for `academic`, for `casual`, and for `None` alike.

Two defects, one place.

**The report never named the style.** `best_score` is replaced wholesale when a candidate is adopted,
rescored or polished, and `style` is set at the TOP of an iteration — the same construction that lost
`flagged_sentences` in Result 176. That fix recomputed one field and left its neighbour, which is
recorded here rather than quietly tidied.

**An unrecognised style was silently ignored.** `style_profile` maps an unknown name to the neutral
default by design. `api_server.py` records this exact failure for REST and fixed it there by
constraining the field to `STYLE_NAMES` — an unrecognised name "received a rewrite with no style
applied and nothing saying so" — and the CLI has `choices=STYLE_NAMES`. The library entry point, the
one the MCP server and every embedding caller use, had neither guard.

A warning rather than an exception: the fallback is documented behaviour and a caller may be passing
a name from a newer version, so refusing the run would be harsher than the mistake deserves.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.run import _effective_style, _unknown_style_warning, untell_text

TEXT = (
    "Moreover, the framework leverages a robust approach to delivery at scale. "
    "Furthermore, it is important to note that this underscores the pivotal integration. "
    "In conclusion, organizations must harness these seamless solutions today."
)
KWARGS = dict(tier="lite", threshold=0.3, max_iters=1, rewriter="structural", best_of=1, seed=5)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_the_style_parameter_actually_changes_the_output() -> None:
    """The premise, and the reason the reporting defect mattered. If `style` did nothing, `None`
    would have been an honest answer."""
    academic = untell_text(TEXT, style="academic", **KWARGS).get("final")
    neutral = untell_text(TEXT, style=None, **KWARGS).get("final")
    assert academic != neutral


@pytest.mark.parametrize("style", ["academic", "casual", "technical"])
def test_a_style_that_ran_is_named(style: str) -> None:
    assert untell_text(TEXT, style=style, **KWARGS)["post"]["style"] == style


def test_no_style_reports_none_and_says_nothing() -> None:
    result = untell_text(TEXT, style=None, **KWARGS)
    assert result["post"]["style"] is None
    assert "not a known style" not in (result.get("warning") or "")


@pytest.mark.parametrize("style", ["acadmic", "zzz", "Academic Writing"])
def test_an_unrecognised_style_reports_none_and_warns(style: str) -> None:
    """Both halves matter. Reporting the requested name back would tell the caller `acadmic` ran;
    reporting `None` without a word would leave them wondering why the style did nothing."""
    result = untell_text(TEXT, style=style, **KWARGS)
    assert result["post"]["style"] is None
    assert "not a known style" in (result.get("warning") or "")


def test_the_warning_names_the_alternatives() -> None:
    """A caveat a reader cannot act on is decoration. This one has to carry the valid names,
    because the whole failure is that the caller believed they had used one."""
    warning = _unknown_style_warning("acadmic") or ""
    assert "acadmic" in warning
    assert "academic" in warning and "casual" in warning


def test_case_and_padding_are_accepted() -> None:
    """`style_profile` lower-cases and strips before its lookup, so the report must agree with it —
    otherwise ` Academic ` runs the academic profile and is reported as unrecognised."""
    assert _effective_style("  ACADEMIC  ") == "academic"
    assert _unknown_style_warning("  ACADEMIC  ") is None


def test_every_declared_style_name_is_recognised() -> None:
    """Guards the guard from the other side: the warning must not fire on a name the CLI and REST
    surfaces both advertise. A profile deleted without updating STYLE_NAMES would show up here."""
    from untell.rewriter.prompts import STYLE_NAMES

    unrecognised = [name for name in STYLE_NAMES if _effective_style(name) is None]
    assert not unrecognised, unrecognised


def test_a_broken_profile_table_does_not_break_the_result(monkeypatch) -> None:
    """A reporting field must never break the result it rides in."""
    import untell.rewriter.structural as structural

    monkeypatch.delattr(structural, "_STYLE_PROFILES", raising=False)
    assert _effective_style("academic") is None
    assert untell_text(TEXT, style="academic", **KWARGS).get("final")
