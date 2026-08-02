"""Predicate-argument veto — catch rewrites that permute *who did what to whom*.

The NLI checks in :mod:`untell.scripts.entailment` catch meaning INVERSION (negation, antonymy)
and meaning LOSS (dropped claims). Measured on a fixed probe set they caught 9 of 13 bad rewrites.
Every one of the 4 they missed had the same shape — the content words are identical and only their
*roles* moved:

    "The company sued the regulator."   -> "The regulator sued the company."   entailment 0.987
    "Smoking causes lung cancer."       -> "Lung cancer causes smoking."       entailment 0.958
    "Exports rose while imports fell."  -> "Imports rose while exports fell."  entailment 0.936
    "If the sensor fails, the system shuts down."
                                        -> "The system shuts down, then the sensor fails."  0.923

A cross-encoder scores these as near-perfect paraphrases because, as bags of tokens, they are.
This is not a hypothetical failure mode for a humanizer: a neural paraphraser reordering a clause
produces exactly this, and the resulting text asserts something the source did not.

Word order alone cannot decide it — "The proposal was rejected by the committee" -> "The committee
rejected the proposal" reverses the surface order and is perfectly faithful. What distinguishes the
two is *syntax*: after normalising the passive, the faithful rewrite has the same
(subject, verb, object) triple and the swapped one does not. So this module parses both texts and
compares predicate-argument structure directly.

Three checks, each vetoing only on positive evidence:

``role swap``
    The same verb keeps the same two arguments but exchanges their subject/object slots.
``predicate reassignment``
    The same subjects and the same verbs appear, but paired differently.
``logical connective change``
    A subordinating connective whose *class* is load-bearing (cause / condition / concession /
    before / after) is dropped, added, or replaced by one of a different class. Synonyms collapse
    ("because" and "since" are both CAUSE), antonyms do not ("before" and "after" stay distinct).

Optional: needs spaCy plus ``en_core_web_sm``. Without them every function reports "unknown"
(``None``) and the veto is simply absent — a missing safety net must never become a silent veto
that rejects everything.
"""

from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# Connective classes. Members of a class are interchangeable in a faithful rewrite; members of
# different classes are not. BEFORE/AFTER/UNTIL are deliberately separate — swapping them inverts
# the claim, which is the whole point.
_CONNECTIVES: dict[str, str] = {
    "because": "CAUSE", "since": "CAUSE", "as": "CAUSE", "given": "CAUSE",
    "if": "COND", "provided": "COND", "assuming": "COND", "when": "COND", "whenever": "COND",
    "unless": "COND_NEG",
    "although": "CONCESS", "though": "CONCESS", "whereas": "CONCESS", "despite": "CONCESS",
    "before": "BEFORE", "prior": "BEFORE",
    "after": "AFTER", "once": "AFTER", "following": "AFTER",
    "until": "UNTIL", "till": "UNTIL",
}

_SUBJ = {"nsubj", "csubj", "expl"}
_PASS_SUBJ = {"nsubjpass", "nsubj:pass", "csubjpass"}
# Clausal complements count as objects. "Smoking causes lung cancer" -> "Lung cancer causes
# smoking" parses the swapped "smoking" as an xcomp rather than a dobj, so without these the one
# role swap in the probe set that involves a gerund slipped through.
_OBJ = {"dobj", "obj", "attr", "oprd", "dative", "xcomp", "ccomp"}


class _NLP:
    pipe = None
    dead = False
    warned = False


def available() -> bool:
    """True when a parser with a dependency component is loadable. Does not parse anything."""
    if _NLP.dead:
        return False
    import os

    if os.environ.get("UNTELL_DISABLE_ROLES") == "1":
        return False
    return _load() is not None


def _load():
    if _NLP.pipe is not None or _NLP.dead:
        return _NLP.pipe
    # Check for the MODEL before importing spaCy: `import spacy` costs seconds and buys nothing
    # without it (the same trap preserve.py documents for entity locking).
    import importlib.util

    if importlib.util.find_spec("en_core_web_sm") is None:
        _NLP.dead = True
        if not _NLP.warned:
            logger.info(
                "en_core_web_sm is not installed, so the predicate-argument veto is OFF — rewrites "
                "that swap subject and object will NOT be caught. Enable it with: "
                "python -m spacy download en_core_web_sm"
            )
            _NLP.warned = True
        return None
    try:
        import spacy

        # Only the tagger/parser/lemmatizer matter here; dropping NER makes this notably faster.
        # The lemmatizer stays: without it `_key` falls back to surface form, so a faithful tense
        # or number change ("runs" -> "ran") stops matching and the comparison silently weakens.
        _NLP.pipe = spacy.load("en_core_web_sm", exclude=["ner"])
    except Exception as exc:
        _NLP.dead = True
        if not _NLP.warned:
            logger.warning(
                "predicate-argument veto unavailable (%s: %s); role swaps will NOT be caught.",
                type(exc).__name__, str(exc)[:140],
            )
            _NLP.warned = True
        return None
    return _NLP.pipe


def _stem(word: str) -> str:
    """Crude suffix strip so a word matches itself across parts of speech.

    The lemmatizer is part-of-speech dependent, so the *same* word lands on different lemmas
    depending on where it sits: in "Smoking causes cancer" the subject lemmatises to ``smoking``
    (noun), while in "Cancer causes smoking" the parser reads it as a verb and lemmatises it to
    ``smoke``. Comparing raw lemmas therefore missed that exact role swap. Stemming both to
    ``smok`` makes the comparison part-of-speech independent.
    """
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            word = word[: -len(suffix)]
            break
    return word.rstrip("e") if len(word) > 4 else word


def _key(token) -> str:
    """Normalised comparison key for an argument head: stemmed lowercase lemma."""
    return _stem((token.lemma_ or token.text).lower().strip())


def _triples(doc) -> list[tuple[str, str, str | None]]:
    """(subject, verb, object) per predicate, with the passive normalised into active order.

    Normalising the passive is what keeps "The proposal was rejected by the committee" and
    "The committee rejected the proposal" identical — without it every voice change would look
    like a role swap.
    """
    out: list[tuple[str, str, str | None]] = []
    for tok in doc:
        if tok.pos_ not in ("VERB", "AUX"):
            continue
        subj = obj = None
        passive = False
        for child in tok.children:
            dep = child.dep_
            if dep in _PASS_SUBJ:
                obj, passive = _key(child), True
            elif dep in _SUBJ and subj is None:
                subj = _key(child)
            elif dep in _OBJ and obj is None:
                obj = _key(child)
            elif dep == "agent":  # "by the committee" — the real subject of a passive
                for g in child.children:
                    if g.dep_ == "pobj":
                        subj = _key(g)
        if obj is None and not passive:
            # No direct object: fall back to the object of a preposition. Many verbs take their
            # second argument that way — "benefit FROM tools", "depend ON funding", "apply TO
            # cases" — and without this the triple is (subject, verb, None) on both sides of a
            # swap, so no rule can fire. MEASURED, this evaded every gate:
            #     "Organizations may benefit from these tools."
            #  -> "These tools may benefit from organizations."
            #     contradiction 0.001, entailment 0.990, role_swap False
            # `agent` is excluded above because it is the passive's real subject, not an object.
            for child in tok.children:
                if child.dep_ == "prep":
                    for g in child.children:
                        if g.dep_ == "pobj":
                            obj = _key(g)
                            break
                if obj is not None:
                    break
        if passive and subj is None:
            subj = None  # agentless passive: the actor is genuinely unstated
        if subj is None and obj is None:
            continue
        out.append((subj or "", _stem((tok.lemma_ or tok.text).lower()), obj))
    return out


def _connectives(doc) -> set[str]:
    classes: set[str] = set()
    for tok in doc:
        if tok.dep_ in ("mark", "prep") or tok.pos_ in ("SCONJ",):
            cls = _CONNECTIVES.get(tok.text.lower())
            # "as"/"when" are heavily overloaded; only count them when they actually introduce a
            # clause, or an ordinary prepositional "as X" would read as a causal claim.
            if cls and (tok.dep_ == "mark" or tok.pos_ == "SCONJ"):
                classes.add(cls)
    return classes


@lru_cache(maxsize=16)
def _analyse(text: str) -> tuple[tuple[tuple[str, str, str | None], ...], frozenset[str]]:
    """(predicate-argument triples, connective classes) for ``text``. Parsed once per string.

    MEASURED: after the NLI pairs were cached, spaCy was the second-largest cost in a warm loop
    profile (0.278s across 7 parses in a 1.39s run). Most of that is waste — `role_swap(source,
    candidate)` re-parses the unchanged source for every candidate, so best-of-3 over 3 iterations
    parses one document nine times.

    Returns hashable, immutable structures and caches those rather than the spaCy `Doc`, which
    holds a vocab-linked token array. Deterministic: the pipeline is loaded once and parsing is
    pure, so the same string always yields the same analysis.
    """
    nlp = _load()
    doc = nlp(text)
    return tuple(_triples(doc)), frozenset(_connectives(doc))


def role_swap(a: str, b: str) -> bool | None:
    """True when ``b`` permutes ``a``'s predicate-argument structure. None if unavailable.

    None means "unknown", never "fine": callers must not read it as a pass.
    """
    nlp = _load()
    if nlp is None or not a.strip() or not b.strip():
        return None
    try:
        # Parse through a cache. The loop calls this once per candidate with the SAME source, so
        # `a` is re-parsed for every draw — best-of-3 over 3 iterations parses one unchanged
        # document nine times. Only the derived facts are cached, never the spaCy Doc: a Doc holds
        # the whole vocab-linked token array, and pinning several of those is real memory, while
        # the triples and connectives are small tuples and sets.
        ta, ca = _analyse(a)
        tb, cb = _analyse(b)
        if not ta or not tb:
            return False

        # 1. Same verb, same two arguments, slots exchanged.
        by_verb_b: dict[str, list[tuple[str, str | None]]] = {}
        for s, v, o in tb:
            by_verb_b.setdefault(v, []).append((s, o))
        for s, v, o in ta:
            # A triple whose two slots hold the SAME key cannot have been swapped — exchanging
            # identical arguments is a no-op — but it satisfies `s2 == o and o2 == s` against
            # itself, so it reported a swap for every candidate. MEASURED on an HC3 paragraph:
            # ("list", "be", "list") vetoed 9 of 9 rewrites and the loop made no progress at all.
            # Reachable because copulas constantly take a prepositional complement ("is part OF the
            # list"), which the prepositional-object fallback now fills the object slot from.
            if not s or not o or s == o:
                continue
            for s2, o2 in by_verb_b.get(v, []):
                if s2 == o and o2 == s:
                    return True

        # 2. Same subjects and same verbs overall, but paired differently. Catches the
        #    "exports rose / imports fell" -> "imports rose / exports fell" shape, where each
        #    predicate is intransitive so there is no object slot to exchange.
        pairs_a = {(s, v) for s, v, _ in ta if s}
        pairs_b = {(s, v) for s, v, _ in tb if s}
        if pairs_a != pairs_b:
            if {s for s, _ in pairs_a} == {s for s, _ in pairs_b} and {
                v for _, v in pairs_a
            } == {v for _, v in pairs_b}:
                return True

        # 3. A load-bearing connective class present in the source is MISSING from the rewrite.
        #
        # Direction matters, and vetoing any difference was measured to starve the loop. Dropping
        # or replacing a connective loses or changes a relation the source asserted ("failed
        # because the cache was stale" -> "failed and the cache was stale"; if -> because;
        # before -> after) and all three still veto, because the source class is gone either way.
        # ADDING one is the structural rewriter's main burstiness move — joining two sentences with
        # "though" or "while" is how it varies architecture — and blocking that rejected every
        # candidate it produced, leaving the loop unable to rewrite anything at all.
        if ca - cb:
            return True
        return False
    except Exception as exc:
        _NLP.dead = True
        if not _NLP.warned:
            logger.warning(
                "predicate-argument veto failed (%s: %s); role swaps will NOT be caught.",
                type(exc).__name__, str(exc)[:140],
            )
            _NLP.warned = True
        return None


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python scripts/roles.py "<original>" "<rewrite>"`` -> JSON.

    Added for the same reason as the entailment CLI: SKILL.md drives every step through
    ``python scripts/<name>.py``, so a check with no CLI is a check the flagship path cannot run.
    The predicate-argument veto catches the failure NLI is weakest on — "the cache invalidated the
    request" vs "the request invalidated the cache" keeps every word, so lexical and embedding
    metrics see near-identical text while the claim has been reversed.

    Exit codes match ``entailment.py`` so both gates branch the same way in a shell:
      0 = not rejected, 1 = roles permuted, 2 = usage error.

    ``0`` means "this check did not reject it", NOT "meaning verified" — when spaCy is missing,
    ``role_swap`` returns None and this reports ``available: false``. That is a skip, and the
    module contract is explicit that None must never be read as a pass, so a caller that needs a
    real verdict must check the ``available`` field rather than the exit code alone.
    """
    import json as _json
    import sys as _sys

    args = argv if argv is not None else _sys.argv[1:]
    if any(a in ("-h", "--help") for a in args):
        print(
            'usage: roles.py "<original>" "<rewrite>"\n\n'
            "Prints JSON: available, role_swap, rejected.\n"
            "Exit 0 if the rewrite does not permute the original's predicate-argument structure,\n"
            "1 if it does, 2 on usage error. Needs spaCy + a model; without it `available` is\n"
            "false and the check is skipped (exit 0) rather than guessed."
        )
        return 0
    if len(args) < 2:
        logger.error('usage: roles.py "<original>" "<rewrite>"')
        return 2

    swapped = role_swap(args[0], args[1])
    if swapped is None:
        print(_json.dumps({"available": False, "role_swap": None, "rejected": False,
                           "note": "spaCy model unavailable — check skipped, not passed"}))
        return 0
    print(_json.dumps({"available": True, "role_swap": swapped, "rejected": swapped}))
    return 1 if swapped else 0


if __name__ == "__main__":
    raise SystemExit(main())
