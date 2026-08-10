"""The loop's sentinel net, exercised through the loop rather than asserted about.

Three rewriters check sentinel survival themselves (mt_pivot, t5_paraphrase, targeted) and the rest
do not, which is the scoping shape that has failed repeatedly elsewhere in this repo. It is safe
here because `run.py` rejects any candidate whose sentinel multiset differs from the masked
source's — every rewriter is covered whether or not it checks itself.

That net is worth testing with adversaries rather than trusting, because losing a sentinel is
silent: `restore` is a substitution, so a dropped ⟦HZ0000⟧ simply means the citation is not written
back, and the output reads perfectly well without it.

Multiset, not set: a set compare passes text that DUPLICATED a sentinel, which restores the citation
twice. The mt_pivot docstring described the set version until this was checked.

Every test here forces ``threshold=0.0`` and then ASSERTS the rewriter actually ran. The first draft
did neither: the probe text scores 0.0041, so the loop stopped with ``stopped="passed"`` after zero
rewrites, the adversary was never called, and three tests passed while proving nothing at all. A
test for a rejection path has to establish that there was something to reject.
"""

from __future__ import annotations

import pytest

from untell.scripts.preserve import SENTINEL_RE
from untell.scripts.run import untell_text

_TEXT = (
    "Smith (2020) reported 42 kg across 1,250 samples in the trial, and the follow-up by "
    "Jones (2021) confirmed the result at doi:10.1000/xyz with 97 percent agreement across "
    "every site that took part in the study."
)
_MUST_SURVIVE = ["Smith (2020)", "42 kg", "1,250", "doi:10.1000/xyz"]


class _Adversary:
    """A rewriter that corrupts the sentinel multiset in one specific way.

    Counts its own calls so a test cannot pass by never invoking it.
    """

    deterministic = False

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.name = f"adversary-{mode}"
        self.calls = 0

    def available(self) -> bool:
        return True

    def rewrite(self, masked: str, score_result=None, threshold=None) -> str:
        self.calls += 1
        found = SENTINEL_RE.findall(masked)
        if not found:
            return masked
        if self.mode == "drop":
            return masked.replace(found[0], "", 1)
        if self.mode == "duplicate":
            return masked.replace(found[0], found[0] + " " + found[0], 1)
        if self.mode == "alter":  # renumber it to a sentinel that was never locked
            return masked.replace(found[0], "⟦HZ9999⟧", 1)
        if self.mode == "swap":  # valid sentinels, wrong places — multiset is unchanged
            a, b = found[0], found[-1]
            return masked.replace(a, "\x00TMP\x00").replace(b, a).replace("\x00TMP\x00", b)
        raise AssertionError(self.mode)


@pytest.mark.parametrize("mode", ["drop", "duplicate", "alter"])
def test_a_corrupted_candidate_never_reaches_the_output(mode: str) -> None:
    adversary = _Adversary(mode)
    # threshold=0.0 is unreachable, so the loop keeps rewriting instead of stopping at "passed".
    result = untell_text(_TEXT, rewriter=adversary, tier="lite", max_iters=2, threshold=0.0)
    assert adversary.calls > 0, "the loop never called the rewriter — this proves nothing"
    final = result.get("final", "")
    for fragment in _MUST_SURVIVE:
        assert fragment in final, f"{mode} rewriter lost {fragment!r}"


def test_the_swap_case_is_documented_as_out_of_scope() -> None:
    """A multiset compare cannot catch REORDERING — the same sentinels in different places.

    Asserted so the limit is explicit rather than assumed. Every locked span still appears exactly
    once, so nothing is lost; what a swap could do is attach the right citation to the wrong clause.
    The meaning gate is what stands between that and the output, not this check.
    """
    adversary = _Adversary("swap")
    result = untell_text(_TEXT, rewriter=adversary, tier="lite", max_iters=1, threshold=0.0)
    assert adversary.calls > 0
    final = result.get("final", "")
    for fragment in _MUST_SURVIVE:
        assert fragment in final, "a swap must not DELETE anything"


def test_a_faithful_rewriter_is_not_rejected() -> None:
    """The other half: a net that rejects everything would pass the tests above and be useless."""

    class Faithful:
        name = "faithful"
        deterministic = False

        def __init__(self) -> None:
            self.calls = 0

        def available(self) -> bool:
            return True

        def rewrite(self, masked: str, score_result=None, threshold=None) -> str:
            self.calls += 1
            return masked.replace("confirmed the result", "backed it up")

    faithful = Faithful()
    result = untell_text(_TEXT, rewriter=faithful, tier="lite", max_iters=1, threshold=0.0)
    assert faithful.calls > 0
    final = result.get("final", "")
    assert "backed it up" in final, "a valid rewrite was rejected by the sentinel net"
    for fragment in _MUST_SURVIVE:
        assert fragment in final
