"""Predicate-argument veto: the class of bad rewrite that NLI scores as a perfect paraphrase.

Measured on the fixed probe set, contradiction + bidirectional entailment caught 9 of 13 bad
rewrites. All four misses had the same shape — identical content words, permuted roles:

    "The company sued the regulator."  -> "The regulator sued the company."   entailment 0.987
    "Smoking causes lung cancer."      -> "Lung cancer causes smoking."       entailment 0.958
    "Exports rose while imports fell." -> "Imports rose while exports fell."  entailment 0.936
    "If the sensor fails, the system shuts down."
                                       -> "The system shuts down, then the sensor fails."  0.923

Surface word order cannot separate these from a faithful voice change, which reverses order too.
Syntax can, and these tests pin both halves: the swaps are caught AND the faithful rewrites that
also reorder are not.
"""

from __future__ import annotations

import json

import pytest

from untell.scripts import roles
from untell.scripts.roles import available, role_swap

pytestmark = pytest.mark.skipif(
    not available(), reason="needs spaCy + en_core_web_sm (python -m spacy download en_core_web_sm)"
)

ROLE_SWAPS = [
    ("subject/object", "The company sued the regulator over the ruling.",
     "The regulator sued the company over the ruling."),
    ("causation", "Smoking causes lung cancer according to the study.",
     "Lung cancer causes smoking according to the study."),
    ("predicate reassignment", "Exports rose sharply while imports fell.",
     "Imports rose sharply while exports fell."),
    ("conjoined agents", "Alice wrote the report and Bob reviewed it.",
     "Bob wrote the report and Alice reviewed it."),
    ("beneficiary", "The teacher praised the student for the essay.",
     "The student praised the teacher for the essay."),
    ("conditional dropped", "If the sensor fails, the system shuts down.",
     "The system shuts down, and then the sensor fails."),
    ("cause dropped", "The build failed because the cache was stale.",
     "The build failed and the cache was stale."),
    ("condition -> cause", "If the request times out, the client retries.",
     "Because the request times out, the client retries."),
    ("before -> after", "The policy takes effect before the audit begins.",
     "The policy takes effect after the audit begins."),
]

FAITHFUL = [
    ("passive -> active", "The proposal was rejected by the committee last week.",
     "The committee rejected the proposal last week."),
    ("active -> passive", "The committee rejected the proposal last week.",
     "The proposal was rejected by the committee last week."),
    ("clause reorder", "Because the sensor failed, the system shut down automatically.",
     "The system shut down automatically because the sensor failed."),
    ("because -> since", "The build failed because the cache was stale.",
     "The build failed since the cache was stale."),
    ("although -> though", "Although the test passed, the coverage dropped.",
     "Though the test passed, the coverage dropped."),
    ("if clause moved", "If the sensor fails, the system shuts down.",
     "The system shuts down if the sensor fails."),
    ("sentence split", "The trial enrolled 240 patients and reported no serious adverse events.",
     "The trial enrolled 240 patients. It reported no serious adverse events."),
    ("synonym swap", "The findings underscore the pivotal role of early intervention.",
     "The findings highlight how crucial early intervention is."),
    ("register shift", "It is important to note that the results demonstrate a significant improvement.",
     "The results show a real improvement, which matters."),
    ("contraction", "The company did not anticipate the regulatory change.",
     "The company didn't see the rule change coming."),
    ("de-AI-ification", "Furthermore, the organization leverages robust methodologies to optimize outcomes.",
     "The team also uses solid methods to get better results."),
    ("hedge preserved", "The results suggest the treatment may help some patients.",
     "The results hint that the treatment could help certain patients."),
    ("voice change", "The team deployed the fix on Tuesday morning.",
     "The fix was deployed by the team on Tuesday morning."),
]


@pytest.mark.parametrize("label,src,rewrite", ROLE_SWAPS, ids=[c[0] for c in ROLE_SWAPS])
def test_role_permutation_is_vetoed(label, src, rewrite):
    assert role_swap(src, rewrite) is True, f"{label}: role permutation not caught"


@pytest.mark.parametrize("label,src,rewrite", FAITHFUL, ids=[c[0] for c in FAITHFUL])
def test_faithful_rewrite_is_not_vetoed(label, src, rewrite):
    """A veto that fires on ordinary paraphrase starves the loop — it would reject the very
    rewrites the humanizer exists to make."""
    assert role_swap(src, rewrite) is not True, f"{label}: faithful rewrite falsely vetoed"


def test_unavailable_parser_reports_unknown_not_a_veto(monkeypatch):
    """None means "unknown". Reading it as a veto would reject every candidate the moment the
    optional model is missing — a missing safety net turning into a total outage."""
    import untell.scripts.roles as r

    monkeypatch.setattr(r._NLP, "pipe", None)
    monkeypatch.setattr(r._NLP, "dead", True)
    assert r.role_swap("The cat sat on the mat.", "The mat sat on the cat.") is None
    assert r.available() is False


def test_meaning_gate_rejects_role_swaps_end_to_end():
    """The veto has to be wired into the gate the loop actually calls, not merely exist."""
    from untell.scripts.entailment import available as nli_available
    from untell.scripts.entailment import meaning_preserved

    if not nli_available():
        pytest.skip("needs the NLI model")
    src = "The company sued the regulator over the ruling."
    swapped = "The regulator sued the company over the ruling."
    # A high similarity that would sail past every other check in the gate.
    assert meaning_preserved(src, swapped, sim=0.995, strict_sim_bar=0.76) is False
    assert meaning_preserved(src, src, sim=1.0, strict_sim_bar=0.76) is True


class TestRolesCLI:
    """SKILL.md runs every step as `python scripts/<name>.py`, so a gate with no CLI is a gate the
    flagship path cannot run. This one earns its place: the reversal it catches passes BOTH of the
    other gates (similarity 0.994, entailment 0.988) because every word is preserved."""

    def test_help_exits_zero(self, capsys):
        assert roles.main(["--help"]) == 0
        assert "usage" in capsys.readouterr().out.lower()

    def test_missing_args_is_usage_error(self):
        assert roles.main([]) == 2
        assert roles.main(["only one"]) == 2

    def test_exit_code_matches_rejected_field(self, capsys):
        """Exit code is the shell contract — it must never disagree with the JSON."""
        for a, b in [
            ("The cache invalidated the request.", "The request invalidated the cache."),
            ("The cache invalidated the request.", "The request was invalidated by the cache."),
        ]:
            code = roles.main([a, b])
            payload = json.loads(capsys.readouterr().out)
            assert code == (1 if payload["rejected"] else 0)

    def test_unavailable_parser_skips_rather_than_rejects(self, capsys, monkeypatch):
        """None means unknown. It must not become a rejection (which would block every rewrite when
        spaCy is missing) and the JSON must say so, since exit 0 alone would read as verified."""
        monkeypatch.setattr(roles, "role_swap", lambda a, b: None)
        assert roles.main(["anything", "something else"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["available"] is False and payload["rejected"] is False

    def test_exit_codes_agree_with_entailment_cli(self):
        """Both gates are documented as branching identically in a shell; keep the codes aligned."""
        from untell.scripts import entailment

        assert roles.main([]) == entailment.main([]) == 2

    @pytest.mark.skipif(not available(), reason="spaCy model not installed")
    def test_rejects_swap_that_survives_the_other_gates(self, capsys):
        assert roles.main(["The cache invalidated the request.",
                           "The request invalidated the cache."]) == 1
        assert json.loads(capsys.readouterr().out)["role_swap"] is True

    @pytest.mark.skipif(not available(), reason="spaCy model not installed")
    def test_passive_voice_is_not_a_swap(self, capsys):
        assert roles.main(["The cache invalidated the request.",
                           "The request was invalidated by the cache."]) == 0


class TestPrepositionalObjectSwaps:
    """A verb's second argument is often a prepositional object, and those swaps evaded everything.

    `_triples` only captured DIRECT objects, so "Organizations may benefit from these tools." and
    "These tools may benefit from organizations." both reduced to (subject, verb, None). With the
    object slot empty on both sides no swap rule can fire, and NLI is no help either — MEASURED
    contradiction 0.001, entailment 0.990. Every gate passed a reversed claim.
    """

    @pytest.mark.parametrize(
        ("source", "candidate"),
        [
            ("Organizations may benefit from these tools.", "These tools may benefit from organizations."),
            ("The team depends on the vendor.", "The vendor depends on the team."),
            ("The rule applies to contractors.", "Contractors apply to the rule."),
            ("Funding comes from the state.", "The state comes from funding."),
        ],
    )
    @pytest.mark.skipif(not available(), reason="spaCy model not installed")
    def test_prepositional_swap_is_caught(self, source, candidate):
        assert role_swap(source, candidate) is True

    @pytest.mark.parametrize(
        ("source", "candidate", "label"),
        [
            ("Organizations may benefit from these tools.", "These tools may help organizations.", "recast"),
            ("Organizations may benefit from these tools.", "Companies might gain from this software.", "synonyms"),
            ("The team depends on the vendor.", "The team relies on the vendor.", "verb swap"),
            ("The rule applies to contractors.", "Contractors are covered by the rule.", "voice recast"),
            ("Funding comes from the state.", "The state provides the funding.", "reworded"),
            ("The proposal was rejected by the committee.", "The committee rejected the proposal.", "passive->active"),
            ("Sales rose in Europe last year.", "Last year, sales grew across Europe.", "adjunct reorder"),
        ],
    )
    @pytest.mark.skipif(not available(), reason="spaCy model not installed")
    def test_faithful_rewrites_are_not_vetoed(self, source, candidate, label):
        """The prepositional fallback must not turn ordinary adjuncts into false swaps — "in Europe"
        and "by the committee" are not the verb's second argument in the relevant sense."""
        assert role_swap(source, candidate) is not True, label


class TestSelfReferentialTripleIsNotASwap:
    """A triple whose two slots hold the SAME key vetoed every candidate.

    Exchanging identical arguments is a no-op, but ("list", "be", "list") satisfies
    `s2 == o and o2 == s` against ITSELF, so rule 1 reported a swap for every rewrite. Reachable
    because copulas constantly take a prepositional complement ("is part OF the list"), which the
    prepositional-object fallback fills the object slot from.

    MEASURED on a real HC3 paragraph: 9 of 9 candidates vetoed, the loop made zero progress
    (0.616 -> 0.616, stopped=max_iters). Across 8 paragraphs the loop reached 0.358 mean max P(AI)
    with the bug and 0.301 without it, and the flagged rate went 50% -> 25%.
    """

    @pytest.mark.skipif(not available(), reason="spaCy model not installed")
    def test_identical_slots_do_not_veto(self):
        src = "The list is part of the list of approved items."
        assert role_swap(src, "The list forms part of the list of approved entries.") is not True

    @pytest.mark.skipif(not available(), reason="spaCy model not installed")
    @pytest.mark.parametrize(
        ("source", "candidate"),
        [
            ("The cache invalidated the request.", "The request invalidated the cache."),
            ("Organizations may benefit from these tools.", "These tools may benefit from organizations."),
            ("The team depends on the vendor.", "The vendor depends on the team."),
            ("The rule applies to contractors.", "Contractors apply to the rule."),
        ],
    )
    def test_real_swaps_still_caught(self, source, candidate):
        """The guard must not weaken detection — only drop the degenerate self-match."""
        assert role_swap(source, candidate) is True
