"""Edits that cannot change who wrote a text.

Every function here returns a variant of the input with the SAME words in the same order. Only
typography and layout move: quote style, spacing after a full stop, dash style, line wrapping,
invisible characters. If a detector's verdict changes across these variants, the verdict was
never a statement about the words, and therefore not about their author.

That is the whole argument of the stability test, and it only holds if the "same words" claim is
true, so it is checked mechanically (:func:`same_words`) for every null variant rather than
trusted. A variant that fails the check is dropped, not reported.

A second, clearly separated tier ("light") makes edits a human editor makes without a second
thought — expanding a contraction, toggling an Oxford comma, US/UK spelling. Those change
characters inside words, so they do not pass ``same_words``; they are reported separately and
never mixed into the null-tier flip rate.

The in-browser evidence kit (``docs/brief.html``) uses the same variant IDs for the same edits,
so a brief produced on the command line and one produced in a browser name the same tests. The
light-tier heuristics differ in small ways between the two (the browser's Oxford-comma rule is
more conservative); null-tier edits are word-identical in both, which is the property that matters.
"""

from __future__ import annotations

import re
import textwrap
import unicodedata
from dataclasses import dataclass

__all__ = ["Variant", "same_words", "null_variants", "light_variants", "all_variants", "words_of"]


@dataclass(frozen=True)
class Variant:
    id: str
    tier: str  # "null" | "light"
    label: str
    description: str
    text: str
    noop: bool  # identical to the input: excluded from flip-rate denominators

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tier": self.tier,
            "label": self.label,
            "description": self.description,
            "noop": self.noop,
            "chars_changed": None,  # filled by the caller that knows the source
        }


# --- the same-words check ------------------------------------------------------------------------

_QUOTE_FOLD = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "′": "'", "″": '"'})
_INVISIBLE = re.compile("[\u00ad\u200b-\u200d\u2060\ufeff\u202a-\u202e\u2066-\u2069]")
_WORD = re.compile(r"[^\W_]+(?:'[^\W_]+)*", re.UNICODE)


def words_of(text: str) -> list[str]:
    """Lower-cased word sequence with typography folded away."""
    t = unicodedata.normalize("NFKC", _INVISIBLE.sub("", text)).translate(_QUOTE_FOLD).lower()
    return _WORD.findall(t)


def same_words(a: str, b: str) -> bool:
    """True when ``a`` and ``b`` contain exactly the same words in the same order."""
    return words_of(a) == words_of(b)


# --- null tier -------------------------------------------------------------------------------------

def _curly(text: str) -> str:
    # Double quotes: opening after start/space/open-bracket, closing otherwise.
    out = re.sub(r'(^|[\s(\[{\u2014-])"', "\\1\u201c", text)
    out = out.replace('"', "\u201d")
    # Apostrophes inside words and closing singles -> right single; opening singles -> left.
    out = re.sub(r"(^|[\s(\[{\u2014-])'", "\\1\u2018", out)
    return out.replace("'", "\u2019")


def _straight(text: str) -> str:
    return text.translate({0x201C: '"', 0x201D: '"', 0x2018: "'", 0x2019: "'"})


def _double_space(text: str) -> str:
    return re.sub(r"([.!?][\"'\u201d\u2019)]?) (?=[A-Z\u201c\"'(])", r"\1  ", text)


def _dashes(text: str) -> str:
    if "\u2014" in text:
        if re.search(r" \u2014 ", text):
            return re.sub(r" \u2014 ", "\u2014", text)
        return text.replace("\u2014", " \u2014 ")
    if "--" in text:
        return text.replace("--", "\u2014")
    return text


def _ellipsis(text: str) -> str:
    if "\u2026" in text:
        return text.replace("\u2026", "...")
    return text.replace("...", "\u2026")


def _paragraphs(text: str) -> list[str]:
    return re.split(r"\n\s*\n", text.replace("\r\n", "\n"))


def _hard_wrap(text: str, width: int = 72) -> str:
    paras = _paragraphs(text)
    wrapped = [
        textwrap.fill(" ".join(p.split()), width=width, break_long_words=False,
                      break_on_hyphens=False)
        for p in paras
    ]
    return "\n\n".join(wrapped)


def _unwrap(text: str) -> str:
    return "\n\n".join(" ".join(p.split()) for p in _paragraphs(text))


def _nfkc_clean(text: str) -> str:
    t = _INVISIBLE.sub("", text)
    t = t.replace("\u00a0", " ").replace("\u202f", " ")
    return unicodedata.normalize("NFKC", t)


def _no_blank_lines(text: str) -> str:
    return "\n".join(p.strip("\n") for p in _paragraphs(text))


def _strip_trailing(text: str) -> str:
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in t.split("\n")).strip("\n")


def _french_spacing(text: str) -> str:
    """A space before ; : ! ? — French typographic convention, and a common typing habit."""
    if re.search(r"\S [;:!?]", text):
        return re.sub(r"(\S) ([;:!?])", r"\1\2", text)
    return re.sub(r"(?<=[^\s;:!?])([;:!?])(?=\s|$)", r" \1", text)


_NULL_EDITS = (
    ("N1", "Curly quotes", "straight quotes and apostrophes become typographic ones", _curly),
    ("N2", "Straight quotes", "typographic quotes and apostrophes become straight ones", _straight),
    ("N3", "Two spaces after full stops", "the typewriter convention many people still use",
     _double_space),
    ("N4", "Dash style", "em dash spacing / double-hyphen style switched", _dashes),
    ("N5", "Ellipsis style", "the single ellipsis character and three full stops swapped",
     _ellipsis),
    ("N6", "Hard-wrapped at 72 columns", "what an email client or plain-text editor produces",
     _hard_wrap),
    ("N7", "Unwrapped lines", "line breaks inside paragraphs joined", _unwrap),
    ("N8", "Unicode-normalised", "NFKC, non-breaking spaces, zero-width and bidi characters removed",
     _nfkc_clean),
    ("N9", "No blank lines between paragraphs", "paragraphs separated by a single newline",
     _no_blank_lines),
    ("N10", "Trailing whitespace stripped", "line endings normalised to LF", _strip_trailing),
    ("N11", "Space before ; : ! ?", "French typographic spacing (or its removal)", _french_spacing),
)


def null_variants(text: str) -> list[Variant]:
    """The formatting-only variants of ``text`` — every one verified to keep the same words."""
    out: list[Variant] = []
    for vid, label, desc, fn in _NULL_EDITS:
        v = fn(text)
        if not same_words(text, v):  # a bug in an edit must never reach a report
            continue
        out.append(Variant(vid, "null", label, desc, v, noop=(v == text)))
    return out


# --- light tier ------------------------------------------------------------------------------------

_CONTRACTIONS = {
    "it's": "it is", "don't": "do not", "can't": "cannot", "won't": "will not", "i'm": "I am",
    "they're": "they are", "we're": "we are", "isn't": "is not", "doesn't": "does not",
    "didn't": "did not", "i've": "I have", "you're": "you are", "that's": "that is",
}
_EXPANSIONS = {v.lower(): k for k, v in _CONTRACTIONS.items()}

_SPELLING = {
    "color": "colour", "behavior": "behaviour", "organize": "organise", "analyze": "analyse",
    "center": "centre", "favorite": "favourite", "realize": "realise", "colors": "colours",
    "organized": "organised", "analyzed": "analysed", "realized": "realised",
}
_SPELLING_REV = {v: k for k, v in _SPELLING.items()}


def _match_case(src: str, repl: str) -> str:
    if src[:1].isupper():
        return repl[:1].upper() + repl[1:]
    return repl


def _swap_words(text: str, table: dict[str, str]) -> str:
    keys = sorted(table, key=len, reverse=True)
    alts = "|".join(re.escape(k).replace("'", "['\u2019]") for k in keys)
    pat = re.compile(r"\b(" + alts + r")\b", re.IGNORECASE)

    def rep(m: re.Match) -> str:
        w = m.group(0)
        r = table.get(w.lower().replace("\u2019", "'"))
        if r is None:
            return w
        return r if r.startswith("I ") else _match_case(w, r)

    return pat.sub(rep, text)


def _expand(text: str) -> str:
    return _swap_words(text, _CONTRACTIONS)


def _contract(text: str) -> str:
    keys = sorted(_EXPANSIONS, key=len, reverse=True)
    pat = re.compile(r"\b(" + "|".join(re.escape(k) for k in keys) + r")\b", re.IGNORECASE)
    return pat.sub(lambda m: _match_case(m.group(0), _EXPANSIONS[m.group(0).lower()]), text)


# "A, B and C": the first item must follow a lower-case word, so a sentence-initial adverbial
# ("However, the cat and dog") is never mistaken for a list. Items may be up to three words.
_ITEM = r"[\w-]+(?: [\w-]+){0,2}"
_OXFORD_ADD = re.compile(rf"(?<=[a-z] )([\w-]+, {_ITEM}) (and|or) (?=\w)")
_OXFORD_DEL = re.compile(rf"(?<=[a-z] )([\w-]+, {_ITEM}), (and|or) (?=\w)")


def _oxford(text: str) -> str:
    if _OXFORD_DEL.search(text):
        return _OXFORD_DEL.sub(r"\1 \2 ", text)
    return _OXFORD_ADD.sub(r"\1, \2 ", text)


def _spelling(text: str) -> str:
    us = sum(len(re.findall(rf"\b{w}\b", text, re.I)) for w in _SPELLING)
    uk = sum(len(re.findall(rf"\b{w}\b", text, re.I)) for w in _SPELLING_REV)
    table = _SPELLING if us >= uk else _SPELLING_REV
    keys = sorted(table, key=len, reverse=True)
    pat = re.compile(r"\b(" + "|".join(keys) + r")\b", re.IGNORECASE)
    return pat.sub(lambda m: _match_case(m.group(0), table[m.group(0).lower()]), text)


_LIGHT_EDITS = (
    ("L1", "Contractions expanded", "it's -> it is, don't -> do not, ...", _expand),
    ("L2", "Contractions used", "it is -> it's, do not -> don't, ...", _contract),
    ("L3", "Oxford comma toggled", "'A, B and C' <-> 'A, B, and C'", _oxford),
    ("L4", "US/UK spelling", "color <-> colour, organize <-> organise, ...", _spelling),
)


def light_variants(text: str) -> list[Variant]:
    """Human-editor-grade variants. Not word-identical, so never mixed into null-tier results."""
    return [
        Variant(vid, "light", label, desc, (v := fn(text)), noop=(v == text))
        for vid, label, desc, fn in _LIGHT_EDITS
    ]


def all_variants(text: str, tiers: tuple[str, ...] = ("null", "light")) -> list[Variant]:
    out: list[Variant] = []
    if "null" in tiers:
        out += null_variants(text)
    if "light" in tiers:
        out += light_variants(text)
    return out
