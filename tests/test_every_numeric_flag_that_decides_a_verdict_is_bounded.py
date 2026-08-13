"""A threshold a probability cannot reach is a verdict that cannot be wrong.

`untell verify --threshold 5` certified any text as passing. Sweeping every argparse numeric
argument in the package found 25 bare casts of 31 arguments, and three more of them decide a
verdict:

    untell score     --threshold 5   ->  "flagged": false      on text it rates 0.826
    untell sentences --threshold 5   ->  0 of 1 sentences flagged
    untell humanize  --confirm -5    ->  accepted; `range(-5)` never runs, so the re-scan guard
                                         is silently off
    untell sentences --top -1        ->  2 of 3 sentences flagged, MORE than `--top 1` flags

All four are the same shape as the verify defect: a value outside the range the quantity can take,
accepted without complaint, producing an answer that looks like a clean result. The REST and MCP
surfaces already refuse the first three.

`--top` was missed by the original sweep because it is a count rather than a threshold, and a
count reads as harmless. It is not: `order[:top]` makes a negative value a slice from the END, so
`--top -1` selects n-1 sentences instead of raising, and `--top -5` selects none — the same
"nothing to rewrite" answer `--threshold 5` produced. It has no REST or MCP twin to compare
against, which is why nothing else caught it.

The remaining bare casts are in `eval/` harnesses (`--n`, `--repeats`, `--workers`, `--pairs`) and
`untell-server --port`. Those are developer tools where a bad value fails loudly and immediately
rather than quietly changing a verdict, so they are left alone deliberately rather than swept up.

One definition per bound: the validators come from `run.py`, which derives them from the API types
in `api_server.py`. A second copy is how four surfaces came to disagree in the first place.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

TEXT = "Moreover, the framework leverages robust methodologies to deliver outcomes at scale."


def _run(module: str, args: list[str]) -> subprocess.CompletedProcess:
    env = dict(os.environ, UNTELL_LITE_NO_TORCH="1", PYTHONIOENCODING="utf-8")
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        capture_output=True, text=True, timeout=300, env=env, input="",
    )


UNREACHABLE = [
    ("untell.scripts.score", ["--threshold", "5"]),
    ("untell.scripts.score", ["--threshold", "-0.1"]),
    ("untell.scripts.sentences", ["--threshold", "5"]),
    ("untell.scripts.verify", ["--threshold", "5"]),
    ("untell.scripts.run", ["--confirm", "-5", "--max-iters", "1"]),
    ("untell.scripts.run", ["--confirm", "99", "--max-iters", "1"]),
    ("untell.scripts.sentences", ["--top", "-1"]),
    ("untell.scripts.sentences", ["--top", "-5"]),
]


@pytest.mark.parametrize(
    "module,args", UNREACHABLE, ids=[f"{m.rsplit('.', 1)[1]}{a}" for m, a in UNREACHABLE]
)
def test_an_out_of_range_value_is_refused(module: str, args: list[str]):
    result = _run(module, [TEXT, "--tier", "lite", *args] if "run" not in module
                  else [TEXT, "--tier", "lite", *args])

    assert result.returncode == 2, (
        f"{module} {args} exited {result.returncode}; a value outside the range the quantity can "
        f"take must be refused, not silently obeyed. stdout: {result.stdout[:200]}"
    )


REACHABLE = [
    ("untell.scripts.score", ["--threshold", "0"]),
    ("untell.scripts.score", ["--threshold", "1"]),
    ("untell.scripts.sentences", ["--threshold", "0.3"]),
    ("untell.scripts.run", ["--confirm", "0", "--max-iters", "1"]),
    # 0 means "flag none" and a count far above the sentences present means "flag all" — both are
    # usable answers, and a bound that refused either would be its own bug.
    ("untell.scripts.sentences", ["--top", "0"]),
    ("untell.scripts.sentences", ["--top", "99"]),
]


@pytest.mark.parametrize(
    "module,args", REACHABLE, ids=[f"{m.rsplit('.', 1)[1]}{a}" for m, a in REACHABLE]
)
def test_the_ends_of_the_range_are_still_accepted(module: str, args: list[str]):
    """A bound that refuses 0, 1 or the default would be its own bug.

    `--confirm 0` is the DEFAULT and means "do not re-confirm", so validating it as a count of at
    least 1 would reject every ordinary run — which is exactly what happened when this bound was
    first added to the MCP surface.
    """
    result = _run(module, [TEXT, "--tier", "lite", *args])
    assert result.returncode == 0, result.stderr[-200:]


def test_the_bounds_come_from_one_place():
    """Four surfaces disagreed because each declared its own. Keep one definition."""
    import inspect

    from untell.scripts import run, score, sentences, verify

    # `score` and `sentences` build their parser inside `main`; `verify` and `run` have a separate
    # `build_parser`. Checked per module rather than assuming one convention.
    for module, func in ((score, "main"), (sentences, "main"), (verify, "build_parser")):
        source = inspect.getsource(getattr(module, func))
        assert "_PROBABILITY" in source, (
            f"{module.__name__}.{func} declares its own threshold bound instead of importing the "
            "shared validator"
        )

    assert "_CONFIRM" in inspect.getsource(run.build_parser)
    assert "_TOP" in inspect.getsource(sentences.main), (
        "sentences declares its own --top bound instead of importing the shared validator"
    )


class TestTopIsACountNotASlice:
    """`--top` is guarded at the CLI, but `score_sentences` is importable and was the thing
    actually holding the defect. Both ends are checked so a future caller cannot reach the slice
    by going around argparse."""

    TEXT = (
        "Moreover, it is important to note that the system delivers value. "
        "The cat sat on the mat. "
        "Furthermore, this comprehensive solution leverages synergies to unlock potential."
    )

    def _flagged(self, top):
        from untell.scripts.sentences import score_sentences

        return len(score_sentences(self.TEXT, tier="lite", top=top)["flagged"])

    @pytest.mark.parametrize("top", [-1, -2, -5])
    def test_a_negative_count_is_refused(self, top: int):
        from untell.scripts.sentences import score_sentences

        with pytest.raises(ValueError, match="0 or greater"):
            score_sentences(self.TEXT, tier="lite", top=top)

    def test_the_count_never_exceeds_what_was_asked(self):
        """The property the negative slice broke: asking for k cannot return more than k. `--top -1`
        returned 2 of 3 — more than `--top 1` — which is the observable symptom."""
        for top in (0, 1, 2, 3, 99):
            assert self._flagged(top) <= top, f"--top {top} flagged more than {top} sentences"

    def test_asking_for_none_flags_none(self):
        assert self._flagged(0) == 0
