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

So this is deliberately mechanical, like :mod:`untell.scripts.numbers`. It asks one question per
class: the source hedged this claim somehow — does the rewrite still hedge it *somehow*? Any term
from the same class counts, so "may" -> "might" and "some" -> "a handful of" are fine. Only
dropping the class entirely is a veto.

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
        "accused", "claims", "claim", "claimed", "argues", "argue", "argued", "estimates",
        "estimated", "believed", "thought", "considered", "according to", "evidence",
        "suspected", "purported", "supposedly", "said to",
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
    "degree": (
        "slightly", "marginally", "modestly", "somewhat", "a bit", "a little", "moderately",
        "mildly", "partially", "partly", "slight", "small", "minor", "narrowly", "fractionally",
        "fraction", "a touch", "a tad", "tad", "minimally", "negligibly", "marginal",
        "edged", "ticked", "inched", "dipped", "nudged", "crept",
    ),
    # intended vs done
    "intention": (
        "plans", "plan", "planned", "aims", "aim", "aimed", "intends", "intend", "intended",
        "expects", "expect", "expected", "hopes", "hope", "hoped", "proposes", "proposed",
        "seeks", "seek", "sought", "will", "going to", "set to", "due to", "plans to",
    ),
}

_CLASS_RES: dict[str, re.Pattern[str]] = {
    name: re.compile(r"(?<!\w)(?:" + "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True)) + r")(?!\w)", re.IGNORECASE)
    for name, terms in _CLASSES.items()
}


def _classes_present(text: str) -> set[str]:
    return {name for name, rx in _CLASS_RES.items() if rx.search(text)}


def dropped_hedges(source: str, candidate: str) -> list[str]:
    """Hedge classes present in ``source`` but absent from ``candidate``.

    A dropped class means the rewrite states more firmly than the source did.
    """
    return sorted(_classes_present(source) - _classes_present(candidate))


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
