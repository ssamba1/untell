"""Every "too short to measure" floor in untell/, in one place, with what decided it.

Seven constants gate a text-length decision, each derived on its own, in seven modules that do not
reference each other. Result 79 was a collision between two of them: `voice_warning` was gated on
`voice.MIN_SAMPLE_WORDS` (150) while the behaviour it described was gated on
`run._MIN_VOICE_SAMPLE_WORDS` (20), so the message named a real constant, correctly, and still
described an event that had not happened.

Nothing enumerated them, so nothing could notice. This test is that enumeration. It fails when a
floor moves or a new one appears, which is the point — each of these is a published number that
some result in docs/free-ceiling-measured.md was measured against, and a silent change to one
invalidates that result without touching the document.

The values are not expected to agree with each other. They gate different measurements and a single
shared floor would be wrong: five words is enough to refuse a perplexity score, and nowhere near
enough to profile six style features. What must not happen is one of them changing by accident.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent

# module path -> {constant: (value, why this number)}
FLOORS: dict[str, dict[str, tuple[float, str]]] = {
    "untell/detectors/perplexity_burstiness.py": {
        "_MIN_WORDS_FOR_SIGNAL": (5, "burstiness is a variance over sentences; under five words "
                                     "there is no distribution to take a variance of"),
    },
    "untell/humanness.py": {
        "_MIN_WORDS_FOR_SIGNAL": (5, "matches the detector's own abstention, deliberately — "
                                     "humanness must not claim a score where its input abstained"),
    },
    "untell/scripts/run.py": {
        "_MIN_VOICE_SAMPLE_WORDS": (20, "below this the style profile is near-flat and the "
                                        "tie-break inverts toward degenerate output; measured at "
                                        "2.5225/0.8329/0.1282 on a whitespace-only sample"),
    },
    "untell/scripts/score.py": {
        "_MIN_WORDS_FOR_A_VERDICT": (40, "the detectors' scores separate at length; under 40 words "
                                         "the verdict is a coin flip dressed as a probability"),
    },
    "untell/scripts/tells.py": {
        "_MIN_WORDS_FOR_REPETITION": (60, "a repetition rate needs enough text for a repeat to be "
                                          "evidence rather than coincidence"),
        "_MIN_WORDS_FOR_A_RATE": (14, "100/14 = 7.1 per-100w, just under the 7.335 AI corpus mean: "
                                      "at 13 words a single tell already outranks average AI text"),
    },
    "untell/scripts/voice.py": {
        "MIN_SAMPLE_WORDS": (150, "where the same-author/cross-author AUROC of 0.680 was measured"),
    },
}

CASES = [(mod, name, value) for mod, d in FLOORS.items() for name, (value, _) in d.items()]


def _module_constants(rel: str) -> dict[str, float]:
    tree = ast.parse((REPO / rel).read_text(encoding="utf-8"))
    out: dict[str, float] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            v = node.value.value
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        out[t.id] = float(v)
    return out


@pytest.mark.parametrize(("rel", "name", "expected"), CASES, ids=lambda x: str(x)[:34])
def test_the_floor_is_where_it_was_measured(rel: str, name: str, expected: float) -> None:
    consts = _module_constants(rel)
    assert name in consts, f"{rel} no longer defines {name}; the census is stale"
    assert consts[name] == expected, (
        f"{rel}:{name} moved {expected} -> {consts[name]}. Every result measured against the old "
        "number is now unverified — update docs/free-ceiling-measured.md, then this census."
    )


def test_the_two_signal_floors_still_agree() -> None:
    """These two are the same concept in two modules, not two concepts that happen to share a value.

    `humanness` abstains where its detector abstains. If the detector's floor moved alone, humanness
    would report a score built on an input that had declined to produce one.
    """
    detector = _module_constants("untell/detectors/perplexity_burstiness.py")["_MIN_WORDS_FOR_SIGNAL"]
    wrapper = _module_constants("untell/humanness.py")["_MIN_WORDS_FOR_SIGNAL"]
    assert detector == wrapper, (
        f"humanness abstains at {wrapper} words but its detector abstains at {detector}; between "
        "them is a band where a score is reported over an abstention"
    )


def test_no_length_floor_is_missing_from_the_census() -> None:
    """The census is only useful if adding an eighth floor breaks it.

    Without this, a new module could introduce its own minimum and collide with an existing one
    exactly as Result 79 did, and every test above would still pass.
    """
    found: set[tuple[str, str]] = set()
    for path in sorted(REPO.glob("untell/**/*.py")):
        rel = path.relative_to(REPO).as_posix()
        for name in _module_constants(rel):
            upper = name.upper()
            if "MIN" not in upper and "MAX" not in upper:
                continue
            if not any(k in upper for k in ("WORD", "SAMPLE", "SENT")):
                continue
            found.add((rel, name))

    known = {(mod, name) for mod, d in FLOORS.items() for name in d}
    assert found == known, (
        f"length-floor census out of date.\n  new: {sorted(found - known)}\n"
        f"  gone: {sorted(known - found)}\n"
        "A new floor needs a derivation in FLOORS above, and a check that it does not contradict "
        "one already there."
    )
