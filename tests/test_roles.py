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

import pytest

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
