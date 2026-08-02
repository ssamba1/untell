"""Sentence splitting — one implementation, because three drifted apart.

``(?<=[.!?])\\s+`` was written out separately in the per-sentence scorer, the structural rewriter
and the perplexity detector. It treats the period in "Dr. Smith published the results" as a
sentence end, and each copy did so independently, so fixing one left the other two wrong:

  scorer     scored the fragment "Dr." as a sentence and flagged it as AI
  rewriter    merged the halves back as "Dr, though smith published the results"
  detector    computed per-sentence surprisal over a one-token "sentence"

Stdlib only and free of any intra-package import, so the zero-dependency lite path and the
detectors can both use it without pulling anything heavy or creating a cycle.
"""

from __future__ import annotations

import re

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

# Abbreviations whose trailing period is not a sentence end.
_ABBREVIATIONS = {
    "dr", "mr", "mrs", "ms", "prof", "sr", "jr", "st", "rev", "hon", "gen", "col", "sgt", "lt",
    "vs", "etc", "al", "cf", "approx", "est", "dept", "univ", "inc", "ltd", "co", "corp",
    "fig", "figs", "eq", "no", "nos", "vol", "vols", "ch", "chap", "sec", "pp", "ed", "eds",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
    "mon", "tue", "wed", "thu", "fri", "sat", "sun",
    "e.g", "i.e", "a.m", "p.m", "u.s", "u.k", "ph.d", "m.d", "b.a", "m.a", "d.c",
}


def ends_with_abbreviation(fragment: str) -> bool:
    """True when this fragment's final period belongs to an abbreviation or an initial."""
    tail = fragment.rstrip().rsplit(" ", 1)[-1] if fragment.strip() else ""
    if not tail.endswith("."):
        return False
    word = tail[:-1].strip("([\"'“‘").lower()
    if word in _ABBREVIATIONS:
        return True
    parts = [p for p in word.split(".") if p]
    if not word or len(word.replace(".", "")) > 3 or any(len(p) > 1 for p in parts):
        return False
    # A single letter, or dotted initials: "J.", "J.R.R.", "U.S.A."
    if all(p.isalpha() for p in parts):
        return True
    # All-digit, e.g. "1." or "3.5.". The old test was length-only, and "3.5" satisfies "every
    # dot-separated part is at most one character" exactly as well as "J.R" does — so a sentence
    # ending in a single digit or a single-digit decimal was read as an abbreviation and never
    # ended. MEASURED before this split:
    #     "The mean was 3.5. Variance was low."           -> ONE sentence
    #     "The answer is 3. The next question is harder."  -> ONE sentence
    # This is the splitter the whole pipeline runs on, so the miscount propagated into burstiness
    # CV, per-sentence scoring, and the targeted rewriter's unit of work.
    #
    # Digits still have one legitimate use here: an ordered-list or section marker ("1. First item",
    # "3.5. Methods"), where the number really does not end a sentence. That case is exactly the one
    # where the number is the WHOLE fragment; a sentence-final number always has words before it.
    return all(p.isdigit() for p in parts) and tail == fragment.strip()


def split_sentences(text: str) -> list[str]:
    """Split on sentence-final punctuation, keeping abbreviations and initials intact."""
    parts = [s for s in _SENT_SPLIT.split(text.strip()) if s.strip()]
    merged: list[str] = []
    for part in parts:
        if merged and ends_with_abbreviation(merged[-1]):
            merged[-1] = f"{merged[-1].rstrip()} {part.strip()}"
        else:
            merged.append(part.strip())
    return [s for s in merged if s]
