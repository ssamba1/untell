"""Per-language tell catalogues: the registry, not the catalogues.

32% of the 435 profiled repos target a language other than English, and that is understated — 49
census reads died on a spend limit, almost all Spanish, Portuguese, French, Russian and Ukrainian.
Four of the eight largest tools in the field are Chinese or Korean. Everything in this repo is
English-only: the catalogue, the voice matcher's constants, every measurement.

The roadmap's position on this is that **the architecture is the contribution**, and that the
catalogues themselves must be written by people who speak the languages — Korean 번역체 calques and
Chinese academic-register tells are not something to guess at from the outside. This module is that
architecture and nothing more. It ships with exactly one entry, English, pointing at the catalogue
that already exists.

Deliberately additive. `untell/scripts/tells.py` is not restructured, not moved, and not imported
differently by anything; adding `zh` means writing a new module and calling `register()`, and
touching no existing file. The roadmap marks the restructuring version of this as a decision rather
than a task, and it is — so this does the part that is not.

What a contributor has to provide, and what they do not:

    from untell.languages import register

    def score_zh(text: str, *, include_matches: bool = False) -> dict:
        ...
    register("zh", score_zh, script="Han", label="Chinese")

The scorer must return the same shape `score_tells` does — at minimum ``words``, ``tells``,
``tells_per_100w``, ``by_category``. Nothing here validates the *content* of a catalogue, because
nothing here can: whether "然而" is over-used by machines is an empirical question about Chinese
prose, and the only honest answer is a measurement on a paired Chinese corpus, exactly as the
English figures in `tells.py` were earned.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Callable, Protocol


class Scorer(Protocol):
    def __call__(self, text: str, *, include_matches: bool = False) -> dict: ...


@dataclass(frozen=True)
class Catalogue:
    """One language's tell catalogue."""

    code: str
    label: str
    scorer: Scorer
    script: str | None  # a Unicode script name, or None for Latin-script languages


_REGISTRY: dict[str, Catalogue] = {}

# Script detection by codepoint block. Deliberately coarse: it decides which catalogue to try, and
# being wrong costs a fallback to English rather than a wrong answer.
_SCRIPT_RANGES: tuple[tuple[str, int, int], ...] = (
    ("Han", 0x4E00, 0x9FFF),
    ("Han", 0x3400, 0x4DBF),
    ("Hangul", 0xAC00, 0xD7AF),
    ("Hangul", 0x1100, 0x11FF),
    ("Hiragana", 0x3040, 0x309F),
    ("Katakana", 0x30A0, 0x30FF),
    ("Cyrillic", 0x0400, 0x04FF),
    ("Arabic", 0x0600, 0x06FF),
    ("Hebrew", 0x0590, 0x05FF),
    ("Devanagari", 0x0900, 0x097F),
    ("Thai", 0x0E00, 0x0E7F),
    ("Greek", 0x0370, 0x03FF),
)

_LATIN = re.compile(r"[A-Za-z]")


def register(
    code: str,
    scorer: Callable[..., dict],
    *,
    script: str | None = None,
    label: str | None = None,
) -> None:
    """Add a language's catalogue. Re-registering a code replaces it."""
    if not code or not code.strip():
        raise ValueError("a language needs a code")
    _REGISTRY[code] = Catalogue(
        code=code, label=label or code, scorer=scorer, script=script
    )


def registered() -> dict[str, Catalogue]:
    """Every catalogue currently available, by code."""
    return dict(_REGISTRY)


def dominant_script(text: str) -> str:
    """The script most of this text is written in: a Unicode script name, or "Latin".

    Counts characters rather than guessing from the first few, so an English paragraph quoting one
    Chinese phrase stays "Latin" — the same rule `_language_supported` already applies, and it has
    to agree with it or a text could be called unsupported and then routed nowhere.
    """
    counts: dict[str, int] = {}
    for ch in text:
        if not ch.isalpha():
            continue
        point = ord(ch)
        for name, low, high in _SCRIPT_RANGES:
            if low <= point <= high:
                counts[name] = counts.get(name, 0) + 1
                break
        else:
            if _LATIN.match(ch):
                counts["Latin"] = counts.get("Latin", 0) + 1
            else:
                # Everything else the ranges above do not enumerate.
                try:
                    name = unicodedata.name(ch).split()[0].title()
                except ValueError:
                    continue
                counts[name] = counts.get(name, 0) + 1
    if not counts:
        return "Latin"
    return max(counts.items(), key=lambda kv: kv[1])[0]


def catalogue_for(text: str) -> Catalogue | None:
    """The registered catalogue for this text's script, or None if nobody has written one.

    None is the honest answer and the caller must say so rather than substituting English. Running
    an English catalogue over Korean is what `language_supported: false` exists to prevent: it
    reports "no catalogued tells found", which reads as a clean bill of health for text nothing
    examined.
    """
    script = dominant_script(text)
    if script == "Latin":
        return _REGISTRY.get("en")
    for catalogue in _REGISTRY.values():
        if catalogue.script == script:
            return catalogue
    return None


def _register_english() -> None:
    """English is registered here rather than in `tells.py`, so that module keeps knowing nothing
    about the registry and this one stays deletable."""
    from untell.scripts.tells import score_tells

    register("en", score_tells, script=None, label="English")


_register_english()
