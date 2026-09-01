"""A checker any line break defeats is worse than none, because it reports PASS.

Round seventy found the retraction guard blind to a claim that had stood for fifty-three rounds: the
phrase `low burstiness, regular sentence length` wrapped between `regular` and `sentence`, and the
guard read one line at a time. Round seventy-one asked what else had that shape and found
`check_demo_privacy_claims` — the check that guards documents against telling users their text is
never uploaded. VERIFIED before the fix: the identical false claim FAILED written on one line and
PASSED written across two.

These documents hard-wrap. Where a phrase happens to break is a property of the paragraph, not of the
claim, so any check whose verdict depends on it is deciding by typography.

This file makes that a standing property rather than two fixed bugs: for every audit check that
matches a phrase in prose, a claim it must catch is planted **both** on one line and split across
two, and both must be caught. A check added later with the same blind spot fails here.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

import untell.scripts.audit as audit

REPO = Path(__file__).resolve().parent.parent
IGNORED = shutil.ignore_patterns(
    ".git", ".venv", "__pycache__", ".pytest_cache", "*.pyc", "node_modules", "htmlcov",
    ".anthology-cache",
)

# (check, document to plant it in, a claim that check must report)
PROBES = [
    ("check_demo_privacy_claims", "docs/index.md",
     "The demo runs entirely in your browser and nothing is sent anywhere."),
    ("check_corpus_bound_claims", "README.md",
     "The loop drives the AI-tells rate to zero while preserving meaning."),
]


def _wrapped(claim: str) -> str:
    """The claim broken at its midpoint, the way a hard-wrap would break it."""
    words = claim.split()
    middle = len(words) // 2
    return " ".join(words[:middle]) + "\n" + " ".join(words[middle:])


def _fails_with(check: str, rel: str, body: str) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "repo"
        shutil.copytree(REPO, copy, ignore=IGNORED)
        victim = copy / rel
        victim.write_text(victim.read_text(encoding="utf-8") + "\n\n" + body + "\n",
                          encoding="utf-8")
        original = audit.REPO
        audit.REPO = copy
        try:
            report = audit.Report()
            getattr(audit, check)(report)
            return bool(report.failures)
        finally:
            audit.REPO = original


@pytest.mark.parametrize("check,rel,claim", PROBES, ids=[p[0] for p in PROBES])
def test_the_same_claim_is_caught_on_one_line_and_across_two(check, rel, claim):
    on_one_line = _fails_with(check, rel, claim)
    across_two = _fails_with(check, rel, _wrapped(claim))

    # The premise. If the claim is not caught even unwrapped, the probe is wrong and the wrapped
    # case would pass vacuously — the shape round sixty-seven hit twice writing mutations.
    assert on_one_line, (
        f"{check} did not report {claim!r} on a single line, so this probe tests nothing")
    assert across_two, (
        f"{check} reported {claim!r} on one line but NOT split across two. Where a phrase wraps is "
        f"a property of the paragraph, not the claim — match against whitespace-collapsed text "
        f"(see `audit.flatten_prose`)."
    )


def test_flatten_prose_joins_a_wrap_and_strips_emphasis():
    """The helper both fixes depend on, and the two things that defeat a phrase match."""
    assert audit.flatten_prose("runs entirely in your\nbrowser") == "runs entirely in your browser"
    assert audit.flatten_prose("to **zero while preserving** meaning") == (
        "to zero while preserving meaning")
    assert audit.flatten_prose("A  B\t\tC\n\n\nD") == "a b c d"


def test_flatten_prose_does_not_invent_a_join_that_was_not_there():
    """Collapsing must not delete the separator — `your\\nbrowser` is two words, not `yourbrowser`."""
    assert "yourbrowser" not in audit.flatten_prose("your\nbrowser")
    assert audit.flatten_prose("a-\nb") == "a- b"
