"""Quantity retention: every number the source states must survive the rewrite.

`preserve.py` deliberately does NOT lock bare single digits — a lone "5" stays rewritable so a
rewrite can write "five", which is a normal style move and changes nothing. The cost of that
choice is that a single digit can also be rewritten into vagueness, and the meaning gate does not
reliably catch it. MEASURED:

    "Only 7 of the 19 tests passed."  ->  "Only a few of the 19 tests passed."
        similarity 0.951   contradiction 0.011   entailment 0.007   -> meaning gate PASSES

The entailment floor is 0.005, so that rewrite clears it by 0.002. Nothing else objects: no
sentinel was dropped (7 was never locked), the roles are unchanged, and cosine sees near-identical
text. A precise claim quietly became an imprecise one, in a tool whose headline promise is that
facts survive.

This check is mechanical and narrow on purpose: it asserts only that each numeral in the source is
still findable in the rewrite, as a numeral or as its English word. It makes no judgement about
meaning, which is what the NLI gate is for.

API:
    numbers_kept(source, candidate) -> bool
    missing_numbers(source, candidate) -> list[str]
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

# Numerals as written in prose: 7, 19, 3.5, 1,234. A masked text's sentinel indices must not be
# mistaken for content numbers — ⟦HZ0007⟧ contains "0007" — so sentinels are stripped first. The
# pattern is imported rather than re-declared: preserve.py owns it, and a second copy that drifts
# would silently start reading sentinel indices as facts.
from untell.scripts.preserve import SENTINEL_RE  # noqa: E402

_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

# Spelled-out forms a faithful rewrite may legitimately substitute for a numeral. Only the small
# integers matter: nobody rewrites "1,234" as words, and if they do, the numeral is still gone in a
# way worth flagging.
_WORDS = {
    "0": ("zero", "no", "none"), "1": ("one", "a single"), "2": ("two", "both", "a pair"),
    "3": ("three",), "4": ("four",), "5": ("five",), "6": ("six",), "7": ("seven",),
    "8": ("eight",), "9": ("nine",), "10": ("ten",), "11": ("eleven",), "12": ("twelve", "a dozen"),
    "13": ("thirteen",), "14": ("fourteen",), "15": ("fifteen",), "16": ("sixteen",),
    "17": ("seventeen",), "18": ("eighteen",), "19": ("nineteen",), "20": ("twenty",),
    "30": ("thirty",), "40": ("forty",), "50": ("fifty",), "100": ("hundred",),
    "1000": ("thousand",), "1000000": ("million",),
}


# List markers ("1.", "2)", at the start of a line) are document structure, not quantities.
# MEASURED: a numbered HC3 paragraph rewritten into prose ("There are a few reasons why...") was
# vetoed for "dropping" the 3 in "\n3. HD channels also require...". Converting a list to flowing
# prose is a legitimate rewrite — the marker carries no fact — and this was 2 of 30 paragraph-scale
# rewrites, the gate's entire false-veto rate.
#
# Capped at two digits so a line that genuinely opens with a year and a full stop ("2024. That was
# the turning point.") keeps its number checked; list markers past 99 are vanishingly rare.
_LIST_MARKER_RE = re.compile(r"(?m)^[ \t]*\d{1,2}[.)](?=\s)")


def _numbers(text: str) -> list[str]:
    without_structure = _LIST_MARKER_RE.sub(" ", SENTINEL_RE.sub(" ", text))
    return _NUMBER_RE.findall(without_structure)


def _present(number: str, candidate: str, candidate_lower: str) -> bool:
    if number in candidate:
        return True
    # "1,234" may reasonably be rewritten "1234" (or the reverse); treat separators as cosmetic.
    bare = number.replace(",", "")
    if bare and bare in candidate.replace(",", ""):
        return True
    return any(w in candidate_lower for w in _WORDS.get(bare, ()))


def missing_numbers(source: str, candidate: str) -> list[str]:
    """Numerals stated in ``source`` that are absent from ``candidate``, in source order.

    Duplicates are reported once: a source that says "42" twice and a rewrite that says it once has
    not dropped the fact.
    """
    cand_lower = candidate.lower()
    seen: set[str] = set()
    missing: list[str] = []
    for n in _numbers(source):
        key = n.replace(",", "")
        if key in seen:
            continue
        seen.add(key)
        if not _present(n, candidate, cand_lower):
            missing.append(n)
    return missing


def numbers_kept(source: str, candidate: str) -> bool:
    """True when every numeral in ``source`` survives in ``candidate``."""
    return not missing_numbers(source, candidate)


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python scripts/numerals.py "<original>" "<rewrite>"`` -> JSON.

    Exit 0 when every number survived, 1 when one was dropped, 2 on usage error — the same contract
    as ``entailment.py`` and ``roles.py`` so all three branch identically in a shell.
    """
    import json

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    args = argv if argv is not None else sys.argv[1:]
    if any(a in ("-h", "--help") for a in args):
        print(
            'usage: numerals.py "<original>" "<rewrite>"\n\n'
            "Prints JSON: missing (numerals dropped by the rewrite), kept (bool).\n"
            "Exit 0 if every number in the original survives — as a numeral or its English word —\n"
            "1 if any was dropped, 2 on usage error."
        )
        return 0
    if len(args) < 2:
        logger.error('usage: numerals.py "<original>" "<rewrite>"')
        return 2

    missing = missing_numbers(args[0], args[1])
    print(json.dumps({"missing": missing, "kept": not missing}, ensure_ascii=True))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
