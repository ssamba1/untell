"""Quantity retention — the gap between "no sentinel was dropped" and "the fact survived".

preserve.py deliberately leaves bare single digits unlocked so a rewrite may write "five" for "5".
The cost is that a digit can also be rewritten into vagueness, and the meaning gate does not catch
it. MEASURED on the case that motivated this module:

    "Only 7 of the 19 tests passed."  ->  "Only a few of the 19 tests passed."
        similarity 0.951   contradiction 0.011   entailment 0.007   -> meaning gate PASSED

The entailment floor is 0.005, so it cleared by 0.002. No sentinel was dropped, because 7 was
never locked; roles were unchanged; cosine saw near-identical text.
"""

from __future__ import annotations

import json

import pytest

from untell.scripts import numerals as numbers
from untell.scripts.numerals import missing_numbers, numbers_kept


class TestNumbersKept:
    @pytest.mark.parametrize(
        ("source", "candidate", "label"),
        [
            ("Only 7 of the 19 tests passed.", "Just seven of the nineteen tests passed.", "spelled out"),
            ("Only 7 of the 19 tests passed.", "Only 7 of the 19 tests came back green.", "reworded"),
            ("Line one has 5 items.", "There are five things in line one.", "numeral to word"),
            ("Revenue grew 1,234 units.", "Revenue grew 1234 units.", "separator is cosmetic"),
            ("It has 2 parts.", "It has both parts.", "2 -> both"),
            ("It has 1 owner.", "It has a single owner.", "1 -> a single"),
            ("Scores: 42 and 42.", "Scores were 42 twice.", "duplicate counted once"),
            ("See ⟦HZ0001⟧ for 5 details.", "See ⟦HZ0001⟧ for five details.", "sentinel ignored"),
            ("No numbers here.", "Still no numbers.", "nothing to keep"),
        ],
    )
    def test_faithful_rewrites_pass(self, source, candidate, label):
        assert numbers_kept(source, candidate), f"{label}: {missing_numbers(source, candidate)}"

    @pytest.mark.parametrize(
        ("source", "candidate", "dropped", "label"),
        [
            ("Only 7 of the 19 tests passed.", "Only a few of the 19 tests passed.", "7", "the leak"),
            ("Line one has 5 items.", "Line one has several items.", "5", "count to vague"),
            ("We ran 240 trials.", "We ran many trials.", "240", "large number dropped"),
        ],
    )
    def test_dropped_quantities_are_caught(self, source, candidate, dropped, label):
        assert not numbers_kept(source, candidate), label
        assert dropped in missing_numbers(source, candidate)

    def test_sentinel_indices_are_not_treated_as_content(self):
        """⟦HZ0007⟧ contains "0007". Counting that as a source number would make every masked
        rewrite look like it dropped a fact."""
        assert numbers_kept("See ⟦HZ0007⟧ now.", "Look at ⟦HZ0007⟧ today.")
        assert missing_numbers("⟦HZ0042⟧ and ⟦HZ0043⟧.", "⟦HZ0042⟧ plus ⟦HZ0043⟧.") == []


class TestNumbersCLI:
    def test_help_exits_zero(self, capsys):
        assert numbers.main(["--help"]) == 0
        assert "usage" in capsys.readouterr().out.lower()

    def test_missing_args_is_usage_error(self):
        assert numbers.main([]) == 2
        assert numbers.main(["only one"]) == 2

    def test_exit_code_matches_kept_field(self, capsys):
        """Exit code is the shell contract; it must not disagree with the JSON."""
        for a, b in [
            ("Only 7 of the 19 tests passed.", "Only a few of the 19 tests passed."),
            ("Only 7 of the 19 tests passed.", "Just 7 of the 19 tests passed."),
        ]:
            code = numbers.main([a, b])
            payload = json.loads(capsys.readouterr().out)
            assert code == (0 if payload["kept"] else 1)

    def test_exit_codes_align_with_the_other_gates(self):
        from untell.scripts import entailment, roles

        assert numbers.main([]) == entailment.main([]) == roles.main([]) == 2


def test_meaning_gate_now_rejects_the_leak():
    """End to end through the gate the loop actually calls."""
    from untell.scripts.entailment import meaning_preserved
    from untell.scripts.quality import similarity

    src, bad = "Only 7 of the 19 tests passed.", "Only a few of the 19 tests passed."
    good = "Just 7 of the 19 tests passed."
    assert not meaning_preserved(src, bad, similarity(src, bad), strict_sim_bar=0.76)
    assert meaning_preserved(src, good, similarity(src, good), strict_sim_bar=0.76)


class TestListMarkersAreNotQuantities:
    """"1." at the start of a line is document structure, not a fact.

    MEASURED at paragraph scale: a numbered HC3 paragraph rewritten into flowing prose ("There are
    a few reasons why...") was vetoed for "dropping" the 3 in "\n3. HD channels also require more
    expensive equipment". Converting a list to prose is a legitimate rewrite and the marker carries
    no quantity. That single shape was the gate's entire false-veto rate — 2 of 30 rewrites, now 0.
    """

    def test_list_to_prose_is_not_a_dropped_quantity(self):
        # The lead-in says "several", not "three": the point of this case is the MARKERS, and a
        # spelled-out count in the lead-in is a real quantity that prose must keep (see the test
        # below, and `test_real_quantities_inside_a_list_are_still_checked` — same principle, the
        # marker is structure but everything else on the line is a fact).
        src = "There are several reasons:\n1. Cost is high.\n2. Speed is low.\n3. HD needs bandwidth."
        prose = "There are a few reasons: cost is high, speed is low, and HD needs bandwidth."
        assert numbers_kept(src, prose), missing_numbers(src, prose)

    def test_a_spelled_count_in_the_lead_in_is_still_a_quantity(self):
        """"three reasons" -> "a few reasons" is the module's opening example, in word form.

        Stripping the markers must not also excuse the count they were introduced by: the source
        states how many, and the rewrite makes it vague. Identical in kind to the "7 of the 19
        tests" -> "a few of the 19 tests" case the docstring opens with.
        """
        src = "There are three reasons:\n1. Cost is high.\n2. Speed is low.\n3. HD needs bandwidth."
        prose = "There are a few reasons: cost is high, speed is low, and HD needs bandwidth."
        assert not numbers_kept(src, prose)
        assert "3" in missing_numbers(src, prose)
        # ...and prose that keeps the count, in either spelling, passes.
        assert numbers_kept(src, "There are three reasons: cost, speed and bandwidth.")
        assert numbers_kept(src, "There are 3 reasons: cost, speed and bandwidth.")

    def test_paren_style_markers_too(self):
        src = "Steps:\n1) Install it.\n2) Run it."
        assert numbers_kept(src, "Install it, then run it.")

    def test_real_quantities_inside_a_list_are_still_checked(self):
        """Only the marker is structure — everything else on the line is still a fact."""
        src = "Findings:\n1. Only 7 of the 19 tests passed.\n2. Latency rose 12%."
        assert not numbers_kept(src, "Findings: a few of the 19 tests passed, latency rose 12%.")
        assert "7" in missing_numbers(src, "Findings: a few of the 19 tests passed, latency rose 12%.")
        assert numbers_kept(src, "Findings: only 7 of the 19 tests passed; latency rose 12%.")

    def test_a_year_opening_a_line_is_not_a_marker(self):
        """Capped at two digits so "2024." keeps its number checked; list markers past 99 are rare."""
        src = "2024. That was the turning point for the project."
        assert not numbers_kept(src, "That was the turning point.")
        assert "2024" in missing_numbers(src, "That was the turning point.")


class TestNumbersCLI:
    def test_help_names_the_untell_command(self, capsys):
        """The help advertised `numerals.py` — a filename, not a command on PATH — and did not
        even document that `-h`/`--help` exist. Name the command as the other subcommands do."""
        assert numbers.main(["--help"]) == 0
        out = capsys.readouterr().out
        assert "usage: untell-numbers" in out
        assert "-h, --help" in out

    def test_unknown_flag_is_a_usage_error_not_silently_swallowed(self, caplog):
        """MEASURED before the guard: `untell numbers --json "a" "b"` compared "--json" against
        "a" and exited 0 with `{"missing": [], "kept": true}` — a silent wrong answer exactly
        when the caller believed they had asked for machine output."""
        import logging

        with caplog.at_level(logging.ERROR, logger="untell.scripts.numerals"):
            rc = numbers.main(["--json", "Only 7 of the 19 tests passed.", "Only seven of the nineteen tests passed."])
        assert rc == 2
        assert any("unrecognized argument --json" in r.getMessage() and "untell-numbers" in r.getMessage()
                   for r in caplog.records)
