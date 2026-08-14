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

_NUMBER_RE = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?")

# Spelled-out forms a faithful rewrite may legitimately substitute for a numeral. Only the small
# integers matter: nobody rewrites "1,234" as words, and if they do, the numeral is still gone in a
# way worth flagging.
_WORDS = {
    "0": ("zero", "no", "none"), "1": ("one", "a single"), "2": ("two", "both", "a pair"),
    "3": ("three",), "4": ("four",), "5": ("five",), "6": ("six",), "7": ("seven",),
    "8": ("eight",), "9": ("nine",), "10": ("ten",), "11": ("eleven",), "12": ("twelve", "a dozen"),
    "13": ("thirteen",), "14": ("fourteen",), "15": ("fifteen",), "16": ("sixteen",),
    "17": ("seventeen",), "18": ("eighteen",), "19": ("nineteen",), "20": ("twenty",),
    "30": ("thirty",), "40": ("forty",), "50": ("fifty",),
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
# Magnitude words, and the reason they are shared by both extraction paths below.
#
# The spelled path already multiplied by "thousand" and "million"; the DIGIT path ignored the word
# entirely, so the same semantic change was caught in one notation and missed in the other:
#
#     "Losses hit five million." -> "Losses hit five billion."   caught
#     "Losses hit 5 million."    -> "Losses hit 5 billion."      MISSED
#
# and digit-plus-magnitude is the far more common way to write it. `billion` and `trillion` were
# not known at all, so "five billion" read as 5. Folding the magnitude into the value also makes
# the two notations agree — "5 million" and "5,000,000" both normalise to 5000000, so a rewrite
# that expands the notation is not flagged as dropping a number.
#
# The spelled multiplier branch in `_SPELLED_RE` carries the same list, so the two paths fold the
# same words. MEASURED before they were aligned: "Losses hit five billion." read as ['5'], and a
# rewrite that changed billion to trillion passed `numbers_kept` with nothing missing — the digit
# path had billion/trillion and the spelled path did not, the exact two-copies drift this file
# exists to prevent.
_SCALES: dict[str, int] = {
    "thousand": 1_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
    "trillion": 1_000_000_000_000,
}
_DIGIT_MAGNITUDE_RE = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s+(" + "|".join(_SCALES) + r")\b", re.IGNORECASE
)

# Spelled decimals: "twelve point four" is the English word form of 12.4, and the module's
# contract is that a numeral counts "as a numeral or as its English word". MEASURED before this
# pattern existed, both directions were vetoed:
#
#     "The fund returned 12.4%." -> "The fund returned twelve point four percent."   VETOED
#     "twelve point four"        -> "12.4"   reads as ['12', '4'], both reported missing
#
# `_SPELLED_RE` read "twelve" and "four" as two separate integers, and `_WORDS` has no decimal
# entry, so the value 12.4 could never match. The fold runs BEFORE the digit scan (like the
# magnitude fold), replacing the words with a literal "12.4" that `_NUMBER_RE` then picks up —
# and consuming the words, so they are not counted twice.
#
# The integer part allows zero and one as well as the units/teens/tens: "zero point five" (0.5)
# and "one point five" (1.5) are unambiguous BECAUSE the "point" follows — the same reason "one"
# alone is not read out. The fraction is one or more single digit words ("three point one four").
# A multiplier compound integer ("five million point five") is deliberately out of scope: it is
# vanishingly rare, and this is the documented boundary the way `test_thousands_combined_with_
# hundreds_are_a_known_limit` pins its own.
_DECIMAL_DIGIT = r"(?:zero|one|" + "|".join(_UNITS) + r")"
_SPELLED_DECIMAL_RE = re.compile(
    r"(?<![\w-])"
    r"(?:zero|one|" + "|".join(_UNITS) + r"|" + "|".join(_TEENS)
    + r"|(?:" + "|".join(_TENS) + r")(?:[-\s]+(?:one|" + "|".join(_UNITS) + r"))?)"
    r"[-\s]+point[-\s]+" + _DECIMAL_DIGIT + r"(?:[-\s]+" + _DECIMAL_DIGIT + r")*"
    r"(?![\w-])",
    re.IGNORECASE,
)


# Tens-and-units compounds are matched FIRST, so "twenty-four" reads as 24 rather than as 20 and 4
# — which would demand the candidate contain both and veto the perfectly faithful "24".
#
# Spelled numbers are a chain of scale groups: each group is a head (a/one/unit/teen/tens)
# followed by "hundred" and/or a scale word. The group chain is what the OLD regex got wrong:
# it allowed exactly ONE scale group plus ONE trailing tens/units, so "three thousand two
# hundred" matched only "three thousand two" (3002) and left the "hundred" dangling — a
# faithful rewrite of 3,200 was vetoed, and "thousand" -> "thousand two hundred" (a real
# +200 change) was missed. "two hundred three thousand" (203000) and "two million three
# hundred thousand" (2300000) failed for the same reason. MEASURED before the rewrite:
#
#     "three thousand two hundred"        -> ['3002']   (should be 3200)
#     "two hundred three thousand"        -> ['203']    (should be 203000)
#     "two million three hundred thousand" -> ['2000300'] (should be 2300000)
#
# The grammar below accepts any number of groups in either order, with an optional trailing
# tens/units tail. `_spelled_value` already sums the chain correctly; the regex just had to
# carry the whole span instead of stopping at the first group.
_SMALL_TAIL = (
    r"(?:(?:" + "|".join(_TENS) + r")(?:[\-\s]+(?:one|" + "|".join(_UNITS) + r"))?"
    r"|(?:" + "|".join(_TEENS) + r")|(?:one|" + "|".join(_UNITS) + r"))"
)
_GROUP_HEAD = r"(?:a|one|" + "|".join(_UNITS) + r"|" + "|".join(_TEENS) + r"|" + "|".join(_TENS) + r")"
# One scale group: "two hundred", "three thousand", "two hundred thousand", "fifteen hundred".
_GROUP = (
    r"(?:" + _GROUP_HEAD + r")[\-\s]+"
    r"(?:hundred(?:[\-\s]+(?:hundred|" + "|".join(_SCALES) + r"))?|" + "|".join(_SCALES) + r")"
)
_SPELLED_RE = re.compile(
    r"(?<![\w-])(?:"
    # A chain of scale groups, then an optional "and" + tens/units tail.
    r"(?:" + _GROUP + r"(?:[\-\s]+" + _GROUP + r")*"
    r"(?:[\-\s]+and)?(?:[\-\s]+" + _SMALL_TAIL + r")?"
    # A bare tens/units compound with no scale word.
    r"|" + _SMALL_TAIL + r")"
    r")(?![\w-])",
    re.IGNORECASE,
)


def _canonical(value: str) -> str:
    """One spelling per quantity, so equal numbers compare equal.

    Comparison here is by STRING, and "5.0" and "5" are different strings — so a rewrite that
    tidied a trailing zero was reported as dropping the number, in both directions:

        "5.0 per 100" -> "5 per 100"      vetoed, missing ['5.0']
        "5 per 100"   -> "5.0 per 100"    vetoed, missing ['5']
        "5.50"        -> "5.5"            vetoed, missing ['5.50']

    A false veto costs the loop a legitimate candidate, and this one fires on ordinary tidying of
    exactly the kind a rewriter does. Trailing zeros after a decimal point carry no value, so they
    are stripped before comparison; an integer is left alone, and a value that does not parse is
    returned untouched rather than guessed at.
    """
    if "." not in value:
        return value
    try:
        float(value)
    except ValueError:
        return value
    trimmed = value.rstrip("0").rstrip(".")
    return trimmed and "0"


def _says_word(haystack: str, word: str) -> bool:
    """True when `word` stands alone in `haystack`, not inside a larger number word.

    This was a bare `word in haystack`, and every compound spelled number slipped through it:

        source 5    candidate "twenty-five cases"   "five" is a substring      passed
        source 9    candidate "ninety cases"        "nine" is a substring      passed
        source 1    candidate "twenty-one cases"    "one" is a substring       passed
        source 100  candidate "three hundred"       "hundred" is a substring   passed

    Each of those is a changed quantity admitted by the gate whose contract is that every number
    the source states must survive. The value path already reads compounds correctly — `_SPELLED_RE`
    carries these same boundaries and `_spelled_value` sums them — so the fallback only has to stop
    claiming a match inside a word it is not.

    Hyphen is a boundary character here as well as a word character, because "twenty-five" is one
    numeral written with a hyphen and a bare word boundary alone would happily match its tail.
    """
    return re.search(r"(?<![\w-])" + re.escape(word) + r"(?![\w-])", haystack) is not None


def _spelled_value(match: str) -> str:
    """The integer a spelled-out number names, including hundreds and thousands.

    Purely additive summing reads "two hundred and forty" as 2 + 40 = 42, so a source saying 240
    and a rewrite spelling it out looked like a dropped quantity — and the module docstring
    promises a numeral counts "as a numeral or as its English word". MEASURED: 5, 12, 20 and 100
    all round-tripped, and 240 did not, because the small values are covered by the exact word
    forms and 100 by the loose-synonym map while anything compound fell through both.

    Multipliers scale what precedes them and the running total carries across them, which is how
    "one thousand two hundred and forty" reaches 1240 rather than 1000 + 200 + 40 by luck.
    """
    total = chunk = 0
    for part in re.split(r"[-\s]+", match.strip().lower()):
        if part in ("and", ""):
            continue
        if part == "hundred":
            chunk = (chunk or 1) * 100
            continue
        if part in _SCALES:
            total += (chunk or 1) * _SCALES[part]
            chunk = 0
            continue
        value = _TENS.get(part) or _TEENS.get(part) or _UNITS.get(part) or (1 if part == "one" else 0)
        chunk += value
    return str(total + chunk)


def _decimal_fold(match: re.Match) -> str:
    """Replace a spelled decimal ("twelve point four") with its digit form ("12.4").

    Runs before the digit scan, so `_NUMBER_RE` picks the value up as one number and the
    component words are consumed rather than counted twice. The integer part reuses
    `_spelled_value` (units, teens, tens, compounds); the fraction is one digit char per
    word, so "three point one four" becomes 3.14.
    """
    words = re.split(r"[-\s]+", match.group(0).strip().lower())
    idx = words.index("point")
    int_value = _spelled_value(" ".join(words[:idx]))
    digit = {"zero": "0", "one": "1", **{w: str(v) for w, v in _UNITS.items()}}
    frac = "".join(digit[w] for w in words[idx + 1:])
    return f" {int_value}.{frac} "


def _numbers(text: str) -> list[str]:
    """Every number in ``text`` as a normalised digit string — digits and spelled-out alike."""
    without_structure = _LIST_MARKER_RE.sub(" ", SENTINEL_RE.sub(" ", text))

    # Spelled decimals FIRST, so "one point five million" folds to "1.5 million" and the
    # magnitude fold below then reaches 1500000 in one pass.
    without_structure = _SPELLED_DECIMAL_RE.sub(_decimal_fold, without_structure)

    # Fold "5 million" into 5000000 BEFORE the plain digit scan, so the magnitude word cannot be
    # dropped on the floor and the value matches however it is written.
    def _fold(match: re.Match) -> str:
        digits = match.group(1).replace(",", "")
        scaled = float(digits) * _SCALES[match.group(2).lower()]
        return f" {int(scaled) if scaled.is_integer() else scaled} "

    without_structure = _DIGIT_MAGNITUDE_RE.sub(_fold, without_structure)

    out = [_canonical(n.replace(",", "")) for n in _NUMBER_RE.findall(without_structure)]
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
        if n in cand_values or any(_says_word(cand_lower, w) for w in _WORDS.get(n, ())):
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
