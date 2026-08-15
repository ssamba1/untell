"""A comma split must still respect the can't-start-a-sentence guard.

structural.py:2654 (row 2667): the comma-split condition chain includes
`and not _inside_quotes(words, pos + 1)` between `not list_like` and the
sentence-openability guards. The mutation and -> or at that position
short-circuits the chain (Python precedence: the or-group makes the later
`and not _cannot_start_a_sentence` / `and not _orphans_a_subordinate_clause`
guards unreachable whenever the earlier conditions hold), so a comma whose
continuation cannot open a clause is split anyway — the most common fragment
class the comment block documents. Original returns None; mutant splits.
"""
from untell.rewriter.structural import _split_one

WORDS = [
    "the", "manager", "said", "the", "plan", "is", "quite", "good,",
    "and", "everyone", "agrees", "with", "her", "today", "now", "ok",
]
TEXT = " ".join(WORDS)


def test_comma_with_unopenable_continuation_is_not_split():
    assert _split_one(TEXT) is None
