"""The surgical adoption loop must count each candidate's tells exactly once.

The `prefer_tells` path of `surgical_substitute` ranks synonym candidates by
`_tell_count(candidate)` — a full-text catalogue pass that costs ~1 s per pass on a 51 KB
document and ~10 s on 1 MB. The loop used to count the SAME candidate twice: once in the sort
key and once in the accept test. That was pure waste (the value is identical) and it scaled the
waste with the text. The dedup is behavior-preserving; these tests pin both halves:

* output is byte-identical to the pre-dedup algorithm (reference loop inlined below), and
* each candidate text is passed to `_tell_count` exactly once.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from untell.attacks import word_importance as wi

TELL_HEAVY = (
    "Moreover, it is important to note that this groundbreaking paradigm significantly enhances "
    "the overall landscape of our framework. Additionally, leveraging robust solutions showcases "
    "a testament to innovation. We delve into the intricacies of the pivotal tapestry, underscoring "
    "its vital role. Furthermore, it stands as a beacon, fostering a vibrant ecosystem, "
    "demonstrating our commitment to excellence."
)

PLAIN = (
    "The Statistical Institute of Catalonia was established in 1989 to collect and publish "
    "regional statistics independently from Spain's national statistics office. It publishes "
    "quarterly reports on employment, prices, and demographic change, and its data feeds into "
    "both regional planning and academic research."
)

# The pre-dedup adoption loop, verbatim from before the fix (git HEAD). The reference for the
# differential test: if the two loops ever disagree on any decision, the outputs diverge.
_OLD_HEADER = """        cur_tells = _tell_count(cur)
        ranked = sorted(
            zip(candidates, cand_scores), key=lambda cs: (_tell_count(cs[0]), float(cs[1]["max"]))
        )
        for cand, s in ranked:
"""
_OLD_ACCEPT = "if score < cur_score or (_tell_count(cand) < cur_tells and score <= floor + _TELLS_EPS):"


def _reference_substitute(text: str, tier: str = "lite", threshold: float = 0.30,
                          max_subs: int = 8, prefer_tells: bool = False) -> dict:
    """Copy of `surgical_substitute` with the OLD (double-counting) adoption loop.

    Built from the current source so the reference tracks the surrounding code; only the
    adoption loop is swapped back to the pre-dedup form.
    """
    import inspect

    src = inspect.getsource(wi.surgical_substitute)
    new_header = """        cur_tells = _tell_count(cur)
        triples = [(cand, s, _tell_count(cand)) for cand, s in zip(candidates, cand_scores)]
        ranked = sorted(triples, key=lambda cs: (cs[2], float(cs[1]["max"])))
        for cand, s, cand_tells in ranked:
"""
    new_accept = "if score < cur_score or (cand_tells < cur_tells and score <= floor + _TELLS_EPS):"
    assert new_header in src, "adoption loop header moved — update the reference in this test"
    assert new_accept in src, "adoption loop accept test moved — update the reference in this test"
    old_src = src.replace(new_header, _OLD_HEADER, 1).replace(new_accept, _OLD_ACCEPT, 1)
    namespace: dict = {}
    exec(compile(old_src, "<reference surgical_substitute>", "exec"), dict(wi.__dict__), namespace)
    return namespace["surgical_substitute"](text, tier=tier, threshold=threshold,
                                            max_subs=max_subs, prefer_tells=prefer_tells)


@pytest.mark.parametrize(
    "text",
    [TELL_HEAVY, PLAIN,
     "Fast. Simple. Effective. Clean. Sharp. Direct. Bold. Quick.",
     "Furthermore, the implementation of this strategy will utilize state-of-the-art techniques "
     "to facilitate the seamless integration of multiple components, thereby ensuring a robust "
     "and comprehensive solution."],
)
def test_deduped_adoption_loop_changes_no_decisions(text: str) -> None:
    kwargs = dict(tier="lite", threshold=0.30, max_subs=12, prefer_tells=True)
    assert wi.surgical_substitute(text, **kwargs) == _reference_substitute(text, **kwargs)


def test_dedup_removes_the_duplicate_tell_passes(stdlib_lite) -> None:
    """The deduped loop must call `_tell_count` fewer times than the pre-dedup one, with
    identical output.

    The pre-dedup loop counted every candidate twice (sort key + accept test); the deduped one
    counts each once. The cleanest observable from outside is the total number of full-text
    tell passes over the whole call, compared against the reference implementation.

    `stdlib_lite` pins UNTELL_LITE_NO_TORCH=1 for the test: on the model-backed path the
    detector IS sensitive to synonym substitution, so `score < cur_score` short-circuits the
    accept test, the old loop's second `_tell_count` never runs, and the two totals are equal
    (the differential collapses). The stdlib path is the one the dedup was measured on — and
    the fixture's cache_clear also isolates the content-addressed score cache, whose warm
    entries from earlier tests in a long session can shift candidate scores.
    """
    calls_new: dict[str, int] = {}
    calls_old: dict[str, int] = {}
    real = wi._tell_count

    def make_counter(store: dict[str, int]):
        def counting(text: str) -> int:
            store[text] = store.get(text, 0) + 1
            return real(text)

        return counting

    kwargs = dict(tier="lite", threshold=0.30, max_subs=12, prefer_tells=True)
    with patch.object(wi, "_tell_count", side_effect=make_counter(calls_new)):
        new_res = wi.surgical_substitute(TELL_HEAVY, **kwargs)
    with patch.object(wi, "_tell_count", side_effect=make_counter(calls_old)):
        old_res = _reference_substitute(TELL_HEAVY, **kwargs)

    assert new_res == old_res, "dedup changed the substitution decisions"
    total_new = sum(calls_new.values())
    total_old = sum(calls_old.values())
    assert total_new < total_old, (
        f"deduped loop should count fewer tells (new={total_new}, old={total_old})"
    )
