"""Only comparison prepositions emit comparison triples.

roles.py:218: `if tok.dep_ != "prep" or tok.text.lower() not in _COMPARISON_PREPS:
continue` — a prep like "during" is NOT a comparison preposition and must not
emit a (subject, prep, object) triple. The mutation or -> and makes the skip
require BOTH conditions, so a non-comparison prep with a pobj child falsely
emits ('alic', 'during', 'bob'). Prior 'spaCy parse-shape, needs real parses'
note wrong — fake tokens with dep_/text/children drive the path.
"""
from untell.scripts.roles import _triples


class _Tok:
    def __init__(self, text, pos, dep, children=()):
        self.text = text
        self.pos_ = pos
        self.dep_ = dep
        self.children = list(children)
        self.lemma_ = text.lower()

    def lower(self):
        return self.text.lower()


class _Sent:
    def __init__(self, toks):
        self.toks = toks

    def __iter__(self):
        return iter(self.toks)


class _Doc:
    def __init__(self, sents):
        self.sents = sents
        self._all = [t for s in sents for t in s]

    def __iter__(self):
        return iter(self._all)


def _doc_with_prep(prep_text):
    subj = _Tok("Alice", "NOUN", "nsubj")
    verb = _Tok("talked", "VERB", "ROOT")
    pobj = _Tok("Bob", "NOUN", "pobj")
    prep = _Tok(prep_text, "ADP", "prep", children=[pobj])
    return _Doc([_Sent([subj, verb, prep])])


def test_non_comparison_prep_emits_no_triple():
    assert _triples(_doc_with_prep("during")) == []


def test_comparison_prep_emits_triple():
    result = _triples(_doc_with_prep("than"))
    assert result == [("alic", "than", "bob")]
