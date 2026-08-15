"""Tests for `untell explain` — why each span the preserve lock freezes is locked.

The capability is new, so these tests do three jobs:

1. **Consistency with lock()** — the explainer and the locker must never disagree
   about what is protected. `explain_spans(text)` reports exactly the sentinels and
   spans `lock(text)` produces, byte for byte. This pinned a real bug during
   development: the labeled merge sorted by rule label first, so a later-position
   span with an earlier label sorted ahead of an earlier span and the merged
   interval corrupted — the consistency assertion caught it before anything else.

2. **Registry integrity** — every rule label in `preserve._PATTERNS` (plus the
   `entity` label from NER) must have a rationale, and every rationale must name a
   rule. A pattern added without an explanation is the drift this module exists to
   make visible.

3. **Attribution** — the rules reported for representative spans are the ones the
   evidence in `preserve.py` documents.
"""

from __future__ import annotations

import json

import pytest

from untell.scripts.explain import RATIONALES, explain_spans
from untell.scripts.explain import main as explain_main
from untell.scripts.preserve import _PATTERNS, lock, restore


def _consistency(text: str) -> None:
    """explain's sentinel->span map must be lock's mapping, in the same order."""
    rows = explain_spans(text)
    reported = {row["sentinel"]: row["span"] for row in rows}
    masked, mapping = lock(text)
    assert reported == mapping, f"explain and lock disagree on {text!r}"
    # Sentinel numbering is load-bearing: lock() names sentinels by merged-span
    # order, and the loop verifies sentinel survival by exact token. If explain's
    # order ever diverged, the sentinel a user sees in output would name the wrong
    # span.
    assert [row["sentinel"] for row in rows] == list(mapping)


_BATTERY = [
    "A perfectly ordinary sentence with no protected spans at all.",
    "The effect was robust [12] and replicated in later work [3, 4].",
    "As Smith (2020) argued, and others agreed (Lee & Park, 2019, p. 4).",
    "The sample of 1,024 subjects showed a 42% increase over 3.5 years.",
    'She said "this changes everything" and cited https://example.com/x?y=1.',
    r"Open C:\Users\me\file.txt and run `parse_json()`; ships in v1.2.3-rc4.",
    r"Use $E = mc^2$ and \citep{smith2020}; see Section 3.2 and 42 U.S.C. 1983.",
    "Call +1-555-013-4567 or mail a.b@c.co before March 15, 2024.",
    "About 1 in 5 users saw 12 ± 3 errors; commit 4f2a91c fixed H2O2 levels.",
    "Host 192.168.1.24 runs untell==0.2.0 with UNTELL_LITE_NO_TORCH=1.",
    "Keep \u27e6HZ0000\u27e7 intact when rewriting.",
    "Set ENABLE_CACHE=false when debugging the 5 mg dose at 9:30 AM.",
]


@pytest.mark.parametrize("text", _BATTERY)
def test_explain_matches_lock_byte_for_byte(text: str) -> None:
    _consistency(text)


def test_round_trip_survives_the_collector_refactor() -> None:
    # The labeled collector is the new single source of truth for lock(); the
    # round-trip guarantee is what the refactor must not have disturbed.
    for text in _BATTERY:
        masked, mapping = lock(text)
        assert restore(masked, mapping) == text


def test_every_rule_has_a_rationale() -> None:
    used = {label for label, _pat in _PATTERNS} | {"entity"}
    missing = sorted(used - set(RATIONALES))
    assert not missing, f"rules without a rationale: {missing}"


def test_every_rationale_names_a_rule() -> None:
    used = {label for label, _pat in _PATTERNS} | {"entity"}
    dead = sorted(set(RATIONALES) - used)
    assert not dead, f"rationales naming no rule: {dead}"


def _rules_of(text: str) -> set[str]:
    return {rule for row in explain_spans(text) for rule in row["rules"]}


def test_number_attribution() -> None:
    assert "number" in _rules_of("The sample grew by 42% in 2024.")


def test_citation_attribution() -> None:
    rows = explain_spans("As Smith (2020) argued, it holds [12].")
    assert "citation" in _rules_of("As Smith (2020) argued, it holds [12].")
    # both the author-year and the bracketed form are citations
    assert len([r for r in rows if "citation" in r["rules"]]) == 2


def test_url_attribution() -> None:
    rows = explain_spans("See https://example.com/x.")
    assert "url" in rows[0]["rules"]


def test_quote_attribution() -> None:
    assert "quote" in _rules_of('She said "this changes everything".')


def test_code_and_version_attribution() -> None:
    text = "Run `parse_json()` first; install untell==0.2.0."
    rows = explain_spans(text)
    assert "code" in rows[0]["rules"]  # the backtick span
    assert "version" in _rules_of(text)
    # a merged span reports EVERY rule that matched it, not one winner
    assert {"number", "version"} <= set(rows[1]["rules"])


def test_latex_attribution() -> None:
    assert "latex_math" in _rules_of(r"We use $E = mc^2$ and \citep{smith2020}.")
    assert "latex_cite" in _rules_of(r"We use $E = mc^2$ and \citep{smith2020}.")
    env = "\\begin{verbatim}\nx=1\n\\end{verbatim}"
    assert "latex_env" in _rules_of(env)


def test_path_attribution() -> None:
    rows = explain_spans(r"Open C:\Users\me\file.txt now.")
    assert "path" in rows[0]["rules"]


def test_phone_attribution() -> None:
    assert "phone" in _rules_of("Call +1-555-013-4567 today.")


def test_hexid_attribution() -> None:
    assert "hexid" in _rules_of("commit 4f2a91c landed")


def test_date_attribution() -> None:
    assert "date" in _rules_of("Due March 15, 2024.")


def test_ratio_attribution() -> None:
    assert "ratio" in _rules_of("About 1 in 5 users")


def test_reference_attribution() -> None:
    assert "reference" in _rules_of("See Section 3.2 and 42 U.S.C. 1983.")


def test_identifier_attribution() -> None:
    assert "identifier" in _rules_of("H2O2 and BRCA1 matter")


def test_dotted_attribution() -> None:
    assert "dotted" in _rules_of("Host 192.168.1.24")


def test_email_attribution() -> None:
    assert "email" in _rules_of("Mail a.b@c.co")


def test_input_sentinel_locked_as_sentinel() -> None:
    rows = explain_spans("Keep \u27e6HZ0000\u27e7 intact.")
    assert "sentinel" in rows[0]["rules"]
    assert rows[0]["span"] == "\u27e6HZ0000\u27e7"


def test_deterministic() -> None:
    text = "See Smith (2020); the fix ships in v1.2.3-rc4 at https://example.com/x."
    assert explain_spans(text) == explain_spans(text)


def test_rationale_present_for_merged_span() -> None:
    rows = explain_spans("install untell==0.2.0")
    assert rows[0]["rationale"]  # joined rationale for number + version
    assert "version" in rows[0]["rationale"]
    assert "Numeric facts" in rows[0]["rationale"]


# ---------------------------------------------------------------------------
# CLI behaviour
# ---------------------------------------------------------------------------


def test_cli_table_output(capsys) -> None:
    rc = explain_main(["See Smith (2020); it cost $500."])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Smith (2020)" in out
    assert "citation" in out
    assert "why:" in out
    assert "span(s) locked" in out


def test_cli_json_output(capsys) -> None:
    rc = explain_main(["--json", "See Smith (2020); it cost $500."])
    assert rc == 0
    rows = json.loads(capsys.readouterr().out)
    assert isinstance(rows, list) and rows
    assert {"sentinel", "span", "start", "end", "rules", "rationale"} <= set(rows[0])
    assert rows[0]["span"] == "Smith (2020)"


def test_cli_no_spans(capsys) -> None:
    rc = explain_main(["plain prose with nothing to lock"])
    assert rc == 0
    assert "No spans locked" in capsys.readouterr().out


def test_cli_empty_input_exit_2(capsys, tmp_path) -> None:
    # An empty positional string is falsy and falls through to stdin (the same
    # convention as the other commands), so the empty-input branch is reached
    # through --file with an empty file.
    f = tmp_path / "empty.txt"
    f.write_text("", encoding="utf-8")
    rc = explain_main(["--file", str(f)])
    assert rc == 2
    assert json.loads(capsys.readouterr().out) == {"error": "empty input"}


def test_cli_no_input_exit_2(capsys, monkeypatch) -> None:
    # main() imports read_stdin_or_none from io_utils at call time, so the patch
    # must land on io_utils, not on this module's namespace.
    monkeypatch.setattr(
        "untell.scripts.io_utils.read_stdin_or_none", lambda: None
    )
    rc = explain_main([])
    assert rc == 2
    assert "error" in json.loads(capsys.readouterr().out)


def test_cli_file_input(capsys, tmp_path) -> None:
    f = tmp_path / "draft.txt"
    f.write_text("See Smith (2020).", encoding="utf-8")
    rc = explain_main(["--file", str(f), "--json"])
    assert rc == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["span"] == "Smith (2020)"


def test_cli_subcommand_dispatch(capsys) -> None:
    """`untell explain ...` must reach this module through the unified CLI."""
    from untell.scripts.cli import main as cli_main

    rc = cli_main(["explain", "See Smith (2020)."])
    assert rc == 0
    assert "Smith (2020)" in capsys.readouterr().out
