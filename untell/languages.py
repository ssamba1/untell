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
    # How this catalogue's precision was measured, or None for "not measured yet". Defaulted so
    # `register` stays backward compatible for any caller that predates the field; `unmeasured()`
    # is what reads it. See `register` for why this is recorded rather than required.
    evidence: str | None = None


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


# The keys `score_tells` returns that a catalogue for another language must also return. Not the
# whole shape — `burstiness_cv` and the English-specific notes are not required of a Chinese
# catalogue — but the four every caller reads, so a registered scorer cannot silently omit the
# number its callers index by.
REQUIRED_KEYS = ("words", "tells", "tells_per_100w", "by_category")


def register(
    code: str,
    scorer: Callable[..., dict],
    *,
    script: str | None = None,
    label: str | None = None,
    evidence: str | None = None,
) -> None:
    """Add a language's catalogue. Re-registering a code replaces it.

    ``evidence`` is how this catalogue's precision was measured — a corpus, a command, a document.
    **CONTRIBUTING.md has always required it** ("what a catalogue needs before it ships is a
    measurement, not a word list") and nothing enforced it, so the requirement was prose: a word
    list assembled by intuition could be registered and would report tells per hundred words with
    the same authority as English, whose every category carries a precision figure against a paired
    corpus. Several English patterns that *sounded* obviously right pointed the wrong way —
    `em_dash`, the single most-cited AI tell in public discourse, fires on 0 of 400 AI documents
    across two corpora. A catalogue in a language nobody here reads has no such correction available.

    It is not made mandatory, because refusing to register an unmeasured catalogue would push
    contributors to write a fake justification rather than none. Instead ``None`` is recorded and
    surfaced: `unmeasured()` lists them, and `catalogue_for` callers can warn. An honest "not
    measured yet" is more useful than an argument nobody checked.
    """
    if not code or not code.strip():
        raise ValueError("a language needs a code")
    if not callable(scorer):
        raise TypeError(f"catalogue for {code!r} is not callable")
    _REGISTRY[code] = Catalogue(
        code=code, label=label or code, scorer=scorer, script=script, evidence=evidence
    )


def conforms(scorer: Callable[..., dict], probe: str = "one two three four five") -> list[str]:
    """Keys `REQUIRED_KEYS` names that this scorer does not return. Empty means it conforms.

    CONTRIBUTING says a catalogue has "the same shape as score_tells" and nothing checked it. A
    scorer missing `tells_per_100w` does not fail loudly — callers use `.get`, so it reports None,
    and None formats into a report as a blank where a rate belongs. Checked by calling the scorer
    rather than by inspecting it, because the shape is a property of what it returns.
    """
    try:
        result = scorer(probe)
    except Exception as exc:  # a scorer that cannot run on trivial input is not registrable
        return [f"raised {type(exc).__name__}: {str(exc)[:80]}"]
    if not isinstance(result, dict):
        return [f"returned {type(result).__name__}, not a dict"]
    return [key for key in REQUIRED_KEYS if key not in result]


def unmeasured() -> dict[str, Catalogue]:
    """Registered catalogues with no stated precision measurement.

    The list a report should consult before quoting a tells rate in that language as if it meant
    what the English one means.
    """
    return {code: cat for code, cat in _REGISTRY.items() if not cat.evidence}


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

    register(
        "en", score_tells, script=None, label="English",
        # The measurement, named rather than assumed. Every category in `tells.py` carries a
        # precision figure against a paired human/AI corpus, and `eval/data/tell_base_rates.json`
        # holds the human-side rates the caveats are computed from.
        evidence="per-category precision against paired HC3/RAID corpora; "
                 "base rates in eval/data/tell_base_rates.json",
    )


_register_english()
