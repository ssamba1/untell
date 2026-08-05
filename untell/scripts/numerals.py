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

# Spelled-out numbers, read from BOTH sides. Extraction used to find DIGITS only, so a quantity the
# source stated as a word was invisible and could be changed freely. MEASURED:
#
#     "Three sites took part."             ->  "Five sites took part."             PASSED
#     "The trial enrolled three patients." ->  "The trial enrolled four patients." PASSED
#
# By any ordinary reading the source states a number there, and this module's contract is that
# every number the source states must survive.
#
# This list is deliberately stricter than _WORDS above. _WORDS is the permissive side — it decides
# whether a source numeral may count as present in the candidate, so loose synonyms like "both",
# "a dozen" and "none" belong there. Reading those OUT of a source would be a false-veto machine:
# "no" in "there is no clear benefit" is not the quantity zero, and "one" in "one of the reasons"
# is not the quantity one. Only unambiguous number words are read out, and "one" only as the tail
# of a compound ("twenty-one").
_UNITS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
_TEENS = {
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}
# Tens-and-units compounds are matched FIRST, so "twenty-four" reads as 24 rather than as 20 and 4
# — which would demand the candidate contain both and veto the perfectly faithful "24".
_SPELLED_RE = re.compile(
    r"(?<![\w-])(?:(?:" + "|".join(_TENS) + r")(?:[-\s](?:one|" + "|".join(_UNITS) + r"))?"
    r"|(?:" + "|".join(_TEENS) + r")|(?:" + "|".join(_UNITS) + r"))(?![\w-])",
    re.IGNORECASE,
)


def _spelled_value(match: str) -> str:
    total = 0
    for part in re.split(r"[-\s]+", match.strip().lower()):
        total += _TENS.get(part) or _TEENS.get(part) or _UNITS.get(part) or (1 if part == "one" else 0)
    return str(total)


def _numbers(text: str) -> list[str]:
    """Every number in ``text`` as a normalised digit string — digits and spelled-out alike."""
    without_structure = _LIST_MARKER_RE.sub(" ", SENTINEL_RE.sub(" ", text))
    out = [n.replace(",", "") for n in _NUMBER_RE.findall(without_structure)]
    out += [_spelled_value(m.group(0)) for m in _SPELLED_RE.finditer(without_structure)]
    return out


def missing_numbers(source: str, candidate: str) -> list[str]:
    """Numerals stated in ``source`` that are absent from ``candidate``, in source order.

    Duplicates are reported once: a source that says "42" twice and a rewrite that says it once has
    not dropped the fact.
    """
    cand_lower = candidate.lower()
    # Compare VALUES, not substrings. The old check asked whether the source's digits appeared
    # anywhere in the candidate text, so "2" counted as present inside "1234".
    cand_values = set(_numbers(candidate))
    seen: set[str] = set()
    missing: list[str] = []
    for n in _numbers(source):
        if n in seen:
            continue
        seen.add(n)
        # Present as the same value written either way, or as one of the loose synonyms above
        # ("a dozen" for 12, "both" for 2) that are too ambiguous to read out of a source.
        if n in cand_values or any(w in cand_lower for w in _WORDS.get(n, ())):
            continue
        missing.append(n)
    return missing


def numbers_kept(source: str, candidate: str) -> bool:
    """True when every numeral in ``source`` survives in ``candidate``.

    ONE-DIRECTIONAL, deliberately. A number INVENTED where the source had only a vague quantifier
    ("Several sites joined." -> "12 sites joined.") is a meaning change and is NOT vetoed here.
    That was measured before being left alone, because the obvious fix is worse than the leak:

    - The free rewriters cannot invent a number at all. They substitute words and restructure
      sentences; there is no path that generates a digit. MEASURED over 80 runs (40 real HC3
      texts x 2 seeds, composite): **0 runs** produced a digit absent from the input. So the veto
      would never fire on the path it could be measured on.
    - It would fire on the hosted-LLM path, which cannot be measured here without a key — and that
      is exactly where the FALSE vetoes live, because an LLM renders quantities differently.
      "Half the cohort" -> "50% of the cohort", "a couple of sites" -> "2 sites", "the rate
      doubled" -> "2x", "last decade" -> "the 2010s" are all faithful and all introduce a number
      with no digit in the source. Licensing them needs a source-side loose-quantity map far larger
      than ``_WORDS``, and each entry is a new false-veto surface.

    So the trade on today's evidence is: no protection where it can be verified, real false-veto
    risk where it cannot. If the LLM path is ever measured for invented numbers, revisit — the
    check itself is easy, and ``_numbers`` already reads both sides.
    """
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
