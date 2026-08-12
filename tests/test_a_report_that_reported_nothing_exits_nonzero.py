"""Exit 0 means "this ran" to every shell that reads it, including when nothing ran.

`untell-verify` fixed this for itself: it returned 0 when no checker was configured, so a CI job
gating on it "was told the text passed every major AI checker when not one had been consulted". Its
comment settles the vocabulary — **2 means nothing ran**, deliberately not 1, because 1 is a verdict
a caller may act on by rewriting and a configuration problem is not.

The sibling report commands had the same hole. MEASURED:

    untell-score, every detector broken   "scored": false, "max": 0.0, "flagged": false, exit 0
    untell-tells, Chinese paragraph       "language_supported": false, tells 0, words 0, exit 0

Both results carry the diagnosis in their JSON. `tells` even prints "a score of 0 tells means the
patterns did not apply, NOT that the text reads as human" — and then exited 0, which says the
opposite to anything reading the status.

**The counts and flags deliberately do NOT move the exit code.** These are reports; `untell-verify`
is the gate and owns exit 1. A document with forty tells is a report, and two commands disagreeing
about what exit 1 means would be worse than the silence this replaces.
"""

from __future__ import annotations

import logging

import pytest

import untell.humanness as humanness_module
import untell.scripts.score as score_module
import untell.scripts.sentences as sentences_module
import untell.scripts.tells as tells_module

ENGLISH = "The cat sat on the mat and then it went outside to look at the birds in the garden today."
CHINESE = "这是一段中文文字，用来测试检测器的行为，看看它会不会给出一个虚假的判断结果。"
TELL_HEAVY = (
    "It is worth noting that this pivotal approach leverages a robust and comprehensive framework, "
    "and it is crucial to underscore the transformative role of seamless methodologies here."
)


class _Boom:
    tier = "full"

    def __init__(self, name: str) -> None:
        self.name = name

    def score(self, text: str) -> float:
        raise RuntimeError("weights missing")


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_score_exits_two_when_nothing_scored(monkeypatch, capsys) -> None:
    real = score_module.load_detectors
    monkeypatch.setattr(
        score_module, "load_detectors", lambda tier: [_Boom(d.name) for d in real(tier)]
    )
    code = score_module.main([ENGLISH, "--tier", "full", "--quiet"])
    capsys.readouterr()
    assert code == 2


def test_score_exits_zero_on_a_real_score(capsys) -> None:
    """Guards the guard. If this drifted to always returning 2 the signal would be worthless."""
    code = score_module.main([ENGLISH, "--tier", "lite", "--quiet"])
    capsys.readouterr()
    assert code == 0


def test_a_flagged_score_is_still_exit_zero(capsys) -> None:
    """The line between a report and a gate. `untell-verify` owns exit 1 for a verdict."""
    code = score_module.main([TELL_HEAVY, "--tier", "lite", "--quiet", "--threshold", "0.01"])
    capsys.readouterr()
    assert code == 0


def test_tells_exits_two_on_a_script_it_cannot_read(capsys) -> None:
    code = tells_module.main([CHINESE])
    capsys.readouterr()
    assert code == 2


def test_tells_exits_zero_on_english(capsys) -> None:
    code = tells_module.main([ENGLISH])
    capsys.readouterr()
    assert code == 0


def test_a_tell_heavy_document_is_still_exit_zero(capsys) -> None:
    """Guards the guard from the other side: the COUNT must never become a verdict."""
    from untell.scripts.tells import score_tells

    assert score_tells(TELL_HEAVY)["tells"] > 0, "premise: this text must actually carry tells"
    code = tells_module.main([TELL_HEAVY])
    capsys.readouterr()
    assert code == 0


def test_humanness_exits_two_when_it_cannot_judge(capsys) -> None:
    """The same defect two commands over, found one loop after "fixing the class". This command
    printed "reported as 50 (undetermined) rather than as a verdict" and exited 0."""
    for text in (CHINESE, "Hi there"):
        code = humanness_module.main([text, "--tier", "lite"])
        capsys.readouterr()
        assert code == 2, text[:20]


def test_humanness_exits_zero_on_judgeable_text(capsys) -> None:
    code = humanness_module.main([ENGLISH, "--tier", "lite"])
    capsys.readouterr()
    assert code == 0


def test_the_undetermined_test_is_not_the_number_fifty() -> None:
    """The trap this had to avoid. 50.0 is ALSO a score humanness computes — measured on a 100-word
    HC3 answer with the detector at P(AI) = 0.9992 — so branching on the value would report the
    loudest possible AI verdict as "cannot tell". The reason function reads the INPUT."""
    import inspect

    source = inspect.getsource(humanness_module.main)
    assert "undetermined_reason" in source
    # Comments stripped first: the call site EXPLAINS the trap in prose, and a naive search for
    # "50.0" flagged the warning against it. A check that cannot tell code from the comment
    # describing it fires on the fix.
    code = "\n".join(line.split("#", 1)[0] for line in source.splitlines())
    assert "50.0" not in code and "== 50" not in code, code


def test_sentences_exits_two_on_an_unreadable_script(capsys) -> None:
    code = sentences_module.main([CHINESE])
    capsys.readouterr()
    assert code == 2


def test_a_weak_but_working_tier_is_still_exit_zero(capsys) -> None:
    """The line. The stdlib per-sentence path is near-chance and says so on the result, but
    something ran — returning 2 there would make the code mean "this tier is weak"."""
    code = sentences_module.main([ENGLISH])
    capsys.readouterr()
    assert code == 0


def test_all_four_commands_agree_on_what_two_means() -> None:
    """One vocabulary. `untell-verify` established it; a fifth meaning for 2 would make the code
    unreadable to a script."""
    import inspect

    for module in (score_module, tells_module, humanness_module, sentences_module):
        source = inspect.getsource(module.main)
        assert "return 2" in source, module.__name__
        assert (
            "nothing ran" in source or "could not read" in source or "not a verdict" in source
        ), module.__name__
