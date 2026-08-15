"""A verb-POS antecedent must not be dropped from a conditional.

roles.py:269: `if antecedent.pos_ not in ("VERB", "AUX") and antecedent.dep_ !=
"advcl": continue` — the comment documents why: in "If the server restarts,
the data is lost", spaCy can tag `restarts` as a NOUN, so the POS alone must
not gate; the dependency is the sound signal. The mutation not in -> in skips
a VERB-pos antecedent with a non-advcl dep, dropping the conditional entirely
((None, None) instead of ('restart', 'is')). Prior 'needs real spaCy parses'
note wrong — _load is patchable and the token shape is fake-able.
"""
from unittest.mock import patch

from untell.scripts.roles import _conditional_pair


class _Tok:
    def __init__(self, text, pos, dep, head=None):
        self.text = text
        self.pos_ = pos
        self.dep_ = dep
        self.head = head if head is not None else self

    def lower(self):
        return self.text.lower()


class _Doc:
    def __init__(self, toks):
        self.toks = toks

    def __iter__(self):
        return iter(self.toks)


def test_verb_pos_antecedent_is_kept():
    root = _Tok("is", "AUX", "ROOT")
    restarts = _Tok("restarts", "VERB", "csubj", head=root)
    if_tok = _Tok("if", "SCONJ", "mark", head=restarts)
    doc = _Doc([if_tok, restarts, root])

    with patch("untell.scripts.roles._load", return_value=lambda text: doc):
        assert _conditional_pair("if the server restarts") == ("restart", "is")
