"""No table entry may emit a "<conjunction>," sentence opener. Checked over the whole table.

Result 89 fixed one instance: `however,` -> `But,` / `Though,`, forms that occur ZERO times in 240
HC3 and RAID texts against 95 for "However,". This asserts the category is closed rather than that
one case is fixed — a new `_SYN` entry, or a headword leaving `_TRANSITIONS_RE`, would otherwise
reopen it silently.

Two things already prevent it, and they are different mechanisms for different reasons:

  * `_TRANSITIONS_RE` — the headword is DELETED at a sentence start rather than substituted, which
    is right for `moreover` and `furthermore`, words that carry nothing but the join.
  * `_COMMA_UNSAFE` — the headword is substituted, but conjunctions are filtered out of the option
    list. This is what `however` needs, because deleting it would lose a contrast.

A headword with a conjunction substitute and NEITHER protection is the bug.

Deliberately not a zero-frequency rule. A sweep of every emittable "<substitute>," opener found many
at zero — `still,`, `yet,`, `even so,` — and those are ordinary English that a 240-text corpus simply
does not happen to contain. Sparsity is not evidence of a fingerprint. What separates the real cases
is grammatical: a coordinating conjunction cannot take that comma at all.
"""

from __future__ import annotations

import pytest

from untell.attacks.word_importance import _SYN
from untell.rewriter.structural import _COMMA_UNSAFE, _TRANSITIONS_RE

# Words that cannot stand as "<word>," at the head of a sentence.
COORDINATORS = frozenset({"but", "and", "or", "nor", "yet", "so", "though"})


def _conjunction_substitutes(head: str) -> list[str]:
    """Substitutes that would become a bare "<conjunction>," opener.

    The first word is what inherits the comma, but only a SINGLE-word substitute is bare — "plus
    points" and "by contrast" open a phrase, and a phrase before a comma is fine.
    """
    return [
        s for s in _SYN.get(head, []) if " " not in s and s.split()[0].lower() in COORDINATORS
    ]


AT_RISK = sorted(head for head in _SYN if " " not in head and _conjunction_substitutes(head))


def test_the_scan_finds_something_to_check() -> None:
    """Guards the guard. If the extraction breaks, every test below passes over an empty list."""
    assert AT_RISK, "no headword offers a bare conjunction substitute; the scan has drifted"
    assert "however" in AT_RISK, "the headword this rule came from is no longer in the scan"


@pytest.mark.parametrize("head", AT_RISK)
def test_every_conjunction_substitute_is_prevented_at_a_sentence_start(head: str) -> None:
    deleted_instead = bool(_TRANSITIONS_RE.match(head + ", x"))
    filtered = set(_conjunction_substitutes(head)) <= {
        s.lower() for s in _COMMA_UNSAFE.get(head, frozenset())
    }
    assert deleted_instead or filtered, (
        f"{head!r} can emit {_conjunction_substitutes(head)} as a bare \"<word>,\" opener. Either "
        f"add it to _TRANSITIONS_RE (delete it, right when the word carries only the join) or to "
        f"_COMMA_UNSAFE (filter the option, right when the word carries meaning)."
    )


def test_the_two_mechanisms_are_not_interchangeable() -> None:
    """`however` is the case that needs the second one, and recording why keeps a later tidy-up from
    collapsing them: deleting "However," drops a contrast the sentence is making, where deleting
    "Moreover," drops nothing but a join."""
    assert not _TRANSITIONS_RE.match("however, x"), (
        "however is now deleted at a sentence start, which loses the contrast it carries"
    )
    assert "however" in _COMMA_UNSAFE
