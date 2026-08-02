"""Certainty retention: a rewrite must not upgrade a hedged claim into a flat assertion.

MEASURED — seven of ten subtle strengthenings cleared the full meaning gate (similarity + NLI +
roles), because none of them *contradicts* the source and the entailment floor is 0.005:

    "The drug may cause drowsiness."   -> "The drug causes drowsiness."        PASSED
    "The results suggest a link."      -> "The results prove a link."          PASSED
    "Some studies found an effect."    -> "Studies found an effect."           PASSED
    "She was accused of fraud."        -> "She committed fraud."               PASSED
    "It usually works."                -> "It always works."                   PASSED
    "The company plans to expand."     -> "The company is expanding."          PASSED

Entailment is the min of both directions, so "causes" -> "may cause" should score low — and it
does, just not below 0.005. Raising that floor is the wrong lever: it was tuned to admit 7 of 8
faithful register shifts, and faithful rewrites reword heavily.

So this is deliberately mechanical, like :mod:`untell.scripts.numerals`. It asks one question
per class: the source hedged this claim somehow — does the rewrite still hedge it *somehow*?
Any term from the same class counts, so "may" -> "might" and "some" -> "a handful of" are
fine. Only dropping the class entirely is a veto.

Two rules are not class drops but the same failure reached by ADDING something:
``causal_upgrade`` (source reported an association, rewrite asserts causation) and
``intensifier_added`` (rewrite introduces "large"/"dramatically"/"collapsed" where the
source was neutral). Adding a MINIMIZER is deliberately allowed — a rewrite more cautious
than its source is not a fidelity failure.

API:
    dropped_hedges(source, candidate) -> list[str]   # class names the rewrite dropped
    certainty_kept(source, candidate) -> bool
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    for _p in Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            sys.path.insert(0, str(_p))
            break

logger = logging.getLogger(__name__)

# Each class is a way of NOT fully committing to a claim. Membership is generous on purpose: the
# check only fires when a class present in the source is absent from the rewrite, so a wider class
# means fewer false vetoes on legitimate rewording, not more.
_CLASSES: dict[str, tuple[str, ...]] = {
    # "it may happen" vs "it happens"
    "modality": (
        "may", "might", "could", "can", "would", "possibly", "perhaps", "potentially",
        "conceivably", "arguably", "presumably", "likely", "unlikely", "probably", "maybe",
        "in principle", "in theory", "if", "unless", "assuming",
    ),
    # who says so, and how firmly
    "evidential": (
        "suggests", "suggest", "suggested", "indicates", "indicate", "indicated", "appears",
        "appear", "appeared", "seems", "seem", "seemed", "reportedly", "allegedly", "alleged",
        # Base and -ing forms of the attribution verbs, not only the past/adverbial ones: the class
        # held "alleged" and "allegedly" but not "allege", so "Critics allege the firm misled
        # investors." -> "The firm misled investors." dropped the attribution and cleared the whole
        # gate — quantities, roles, NLI and similarity all pass, because removing "critics allege"
        # does not contradict the source, it just asserts more.
        "allege", "alleges", "alleging", "accuse", "accuses", "accusing",
        "accused", "claims", "claim", "claimed", "argues", "argue", "argued", "estimates",
        "estimated", "believed", "thought", "considered", "according to", "evidence",
        "suspected", "purported", "supposedly", "said to",
        # "hint" is an evidential hedge — weaker than "suggests", not stronger. Its absence made
        # "the results suggest ..." -> "the results hint ..." read as a dropped class, which is the
        # documented 1-of-13 false veto in the README: the check could not tell a lateral move
        # between two weak hedges from a genuine upgrade. "suggests" -> "proves" still drops it.
        "hint", "hints", "hinted", "hinting",
    ),
    # how often, as opposed to always
    "frequency": (
        "usually", "often", "sometimes", "typically", "generally", "frequently", "occasionally",
        "rarely", "seldom", "mostly", "commonly", "in most cases", "as a rule", "tends", "tend",
        "tended", "can be",
    ),
    # how many, as opposed to all
    "quantifier": (
        "some", "several", "many", "most", "a few", "few", "certain", "various", "a number of",
        "a handful", "part of", "portion", "subset", "minority", "majority", "not all", "much",
    ),
    # how much — "fell slightly" is a hedge on magnitude, and dropping it inflates the claim
    # ("Revenue fell slightly." -> "Revenue collapsed." cleared every other gate). Verbs that carry
    # smallness lexically (edged, ticked, inched) count as members, so compact rewordings like
    # "edged down" are not vetoed for lacking an adverb.
    # Adverbs AND their adjective forms. The list held "modestly", "moderately", "minimally" and
    # "partially" but not "modest", "moderate", "minimal", "partial" — so dropping the adjective
    # went undetected. MEASURED, each of these passed the whole gate before:
    #     "There was a modest increase."      -> "There was an increase."
    #     "The effect was moderate."          -> "The effect was present."
    #     "A partial recovery followed."      -> "A recovery followed."
    # They only appeared to be caught in an earlier probe because the rewrite ALSO added an
    # intensifier, which the separate intensifier check fired on. Dropping the hedge on its own —
    # the more natural rewrite — was invisible.
    "degree": (
        "slightly", "marginally", "modestly", "somewhat", "a bit", "a little", "moderately",
        "mildly", "partially", "partly", "slight", "small", "minor", "narrowly", "fractionally",
        "fraction", "a touch", "a tad", "tad", "minimally", "negligibly", "marginal",
        "modest", "moderate", "minimal", "partial", "limited", "slim",
        "edged", "ticked", "inched", "dipped", "nudged", "crept",
    ),
    # intended vs done
    #
    # Members must express INTENT. Four did not, and each one vetoed a whole family of faithful
    # rewrites because a class is dropped whenever the candidate contains no member of it:
    #   "due to"    means "because of" — causal, not intentional. Every swap to "because of",
    #               "owing to", "as a result of" was flagged as dropping an intention hedge.
    #   "will"      is future tense. Documentation is full of "this function will return X", and
    #               the present-tense rewrite is the single most common humanising move there.
    #   "set to"    matches assignment ("the timeout is set to 30 seconds").
    #   "going to"  matches movement ("going to the conference").
    # The real intent verbs below still carry the class, so "The company plans to expand." ->
    # "The company is expanding." is caught exactly as before.
    "intention": (
        "plans", "plan", "planned", "aims", "aim", "aimed", "intends", "intend", "intended",
        "expects", "expect", "expected", "hopes", "hope", "hoped", "proposes", "proposed",
        "seeks", "seek", "sought", "plans to",
    ),
}

_CLASS_RES: dict[str, re.Pattern[str]] = {
    name: re.compile(r"(?<!\w)(?:" + "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True)) + r")(?!\w)", re.IGNORECASE)
    for name, terms in _CLASSES.items()
}


# Association vs causation. This one is not a dropped class but an UPGRADE: the source reported
# that two things go together, the rewrite says one produced the other. MEASURED — both of these
# cleared similarity, NLI and roles, because a causal claim does not contradict an associational
# one, it just says more:
#     "Screen time is correlated with poor sleep." -> "Screen time causes poor sleep."
#     "The outage coincided with the deploy."      -> "The deploy caused the outage."
# Neither sentence locks anything in preserve.py, so nothing else in the pipeline sees it either.
_ASSOCIATION_RE = re.compile(
    # "linked" on its own, because "The two events are linked." has no "to" and was missed. But NOT
    # a bare noun "link": broadening to `link\w*` made "Click the link, which leads to the form."
    # a false veto, since a hyperlink plus any causal verb looked like an upgraded claim.
    r"(?<!\w)(?:correlat\w*|associat\w*|linked|linkage\w*|links\s+with|link\s+between|"
    r"relationship\s+between|connected\s+with|"
    # NOT "alongside": it is overwhelmingly spatial or cooperative in ordinary prose ("the clinic
    # operates alongside the hospital"), and its presence armed the whole check — after which any
    # causal word ANYWHERE in the candidate, including an unrelated clause, read as an upgrade.
    # "accompan\w*" already covers the accompaniment sense in statistical phrasing.
    r"related\s+to|coincid\w*|accompan\w*|co-?occur\w*|tied\s+to|goes?\s+together|"
    r"tracks?\s+with)(?!\w)",
    re.IGNORECASE,
)
_CAUSAL_RE = re.compile(
    r"(?<!\w)(?:caus\w*|leads?\s+to|led\s+to|results?\s+in|resulted\s+in|produc\w*|"
    r"triggers?|triggered|drives?|driven\s+by|responsible\s+for|brings?\s+about|"
    r"brought\s+about|gives?\s+rise\s+to|makes?\s+\w+\s+(?:worse|better)|"
    r"because\s+of|owing\s+to|thanks\s+to)(?!\w)",
    re.IGNORECASE,
)


# A causal word under negation is not a causal claim — "nothing causes the other" DENIES one, and
# vetoing it would punish a rewrite for being more careful than the source.
_NEGATOR_RE = re.compile(
    r"(?<!\w)(?:not|no|nothing|never|neither|nor|n't|doesn't|does\s+not|did\s+not|"
    r"cannot|can't|isn't|is\s+not|without)(?!\w)",
    re.IGNORECASE,
)
# Sentence starts, so the negator search covers the whole clause the causal verb sits in.
_SENT_START_RE = re.compile(r"(?:^|[.!?]\s+)")


def _asserts_causation(text: str) -> bool:
    """True when ``text`` makes an UNnegated causal claim."""
    for m in _CAUSAL_RE.finditer(text):
        # Search back to the start of the containing sentence rather than a fixed 30 characters.
        # A negator normally opens the sentence — "Nothing in these data shows that coffee causes
        # longer life." — and at 30 characters it was invisible whenever the subject ran longer
        # than a few words, so a rewrite that explicitly DENIED causation was vetoed for asserting
        # it. That punishes a rewrite for being more careful than its source.
        start = 0
        for b in _SENT_START_RE.finditer(text, 0, m.start()):
            start = b.end()
        if not _NEGATOR_RE.search(text[start:m.start()]):
            return True
    return False


def _causal_upgrade(source: str, candidate: str) -> bool:
    """True when the source reported an association and the rewrite asserts causation.

    Requires the source to be associational AND not already causal — a source that already says
    "causes" is free to keep saying it.
    """
    if not _ASSOCIATION_RE.search(source) or _asserts_causation(source):
        return False
    return _asserts_causation(candidate)


# Intensifiers the source did not use. The mirror of the `degree` class: that one catches a
# minimizer being DROPPED ("fell slightly" -> "collapsed"), this catches a maximizer being ADDED to
# a neutral source ("found an effect" -> "found a LARGE effect").
#
# The asymmetry is deliberate. Adding a minimizer ("fell" -> "fell somewhat") makes the rewrite more
# cautious than the source, which is not a fidelity failure. Adding an intensifier makes it claim
# more, which is. MEASURED, this is a real gap and not one NLI can close: added-content rewrites
# score bidirectional entailment 0.003-0.011 while genuinely faithful rewriter output reaches down
# to 0.012 — see the note on DEFAULT_ENTAILMENT_FLOOR in entailment.py.
_INTENSIFIER_RE = re.compile(
    # Adverbs AND their adjective forms. The list carried "significantly", "substantially" and
    # "sharply" but not "significant", "substantial", "sharp" — and the adjective is the form a
    # rewrite actually reaches for on a noun. MEASURED, each of these cleared the whole gate:
    #     "The study found an effect."        -> "The study found a significant effect."
    #     "There was an increase in cost."    -> "There was a substantial increase in cost."
    #     "There was a rise in demand."       -> "There was a sharp rise in demand."
    r"(?<!\w)(?:large|huge|massive|dramatic|dramatically|sharp|sharply|significant|significantly|"
    r"substantial|substantially|vast|vastly|enormous|enormously|major|severe|severely|drastic|"
    r"drastically|considerable|considerably|marked|markedly|greatly|hugely|steep|steeply|"
    r"soared|skyrocketed|collapsed|plummeted|plunged|surged)(?!\w)",
    re.IGNORECASE,
)


def _intensifier_added(source: str, candidate: str) -> bool:
    """True when the rewrite introduces an intensifier the source did not use."""
    return bool(_INTENSIFIER_RE.search(candidate)) and not _INTENSIFIER_RE.search(source)


def _classes_present(text: str) -> set[str]:
    return {name for name, rx in _CLASS_RES.items() if rx.search(text)}


def dropped_hedges(source: str, candidate: str) -> list[str]:
    """Hedge classes present in ``source`` but absent from ``candidate``.

    A dropped class means the rewrite states more firmly than the source did. ``causal_upgrade``
    is reported alongside them: it is the same failure (claiming more than the source) reached by
    adding a causal claim rather than by removing a hedge.
    """
    found = sorted(_classes_present(source) - _classes_present(candidate))
    if _causal_upgrade(source, candidate):
        found.append("causal_upgrade")
    if _intensifier_added(source, candidate):
        found.append("intensifier_added")
    return found


def certainty_kept(source: str, candidate: str) -> bool:
    """True when the rewrite hedges every claim class the source hedged."""
    return not dropped_hedges(source, candidate)


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python scripts/hedges.py "<original>" "<rewrite>"`` -> JSON.

    Exit 0 when no hedge class was dropped, 1 when one was, 2 on usage error — the same contract as
    ``entailment.py``, ``roles.py`` and ``numbers.py``.
    """
    import json

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    args = argv if argv is not None else sys.argv[1:]
    if any(a in ("-h", "--help") for a in args):
        print(
            'usage: hedges.py "<original>" "<rewrite>"\n\n'
            "Prints JSON: dropped (hedge classes the rewrite no longer expresses), kept (bool).\n"
            "Exit 0 if the rewrite hedges everything the original hedged, 1 if it states something\n"
            "more firmly than the original did, 2 on usage error."
        )
        return 0
    if len(args) < 2:
        logger.error('usage: hedges.py "<original>" "<rewrite>"')
        return 2

    dropped = dropped_hedges(args[0], args[1])
    print(json.dumps({"dropped": dropped, "kept": not dropped}, ensure_ascii=True))
    return 1 if dropped else 0


if __name__ == "__main__":
    raise SystemExit(main())
