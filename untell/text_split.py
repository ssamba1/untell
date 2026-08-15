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

import difflib
import re

# A sentence may end INSIDE a quotation or bracket, so the terminal punctuation is not always the
# last character: `He said "Done." Then he left.` puts a closing quote between the period and the
# space. A bare `(?<=[.!?])\s+` sees `"` there, refuses to split, and returns the two sentences as
# one. MEASURED on the HC3 corpus: 23 of 800 texts contain at least one such boundary, and every one
# of them was a silent under-count — which feeds the burstiness CV (two sentences merged into one
# long one is exactly the statistic burstiness measures), per-sentence scoring, and the targeted
# rewriter's unit of work.
#
# Two alternated lookbehinds rather than one optional group, because `re` requires each lookbehind
# to be fixed-width. Consuming the closer as part of the separator would work for splitting and
# then delete it from the output, so it stays behind the split point.
# Up to two closers, so a quote nested in a bracket — `(He said "Done.") Next up.` — still ends.
# Three would be a citation style nobody writes; the fallback for it is the old under-split.
_CLOSERS = "\"'”’)]}»"
_C = re.escape(_CLOSERS)
_SENT_SPLIT = re.compile(rf"(?<=[.!?])\s+|(?<=[.!?][{_C}])\s+|(?<=[.!?][{_C}][{_C}])\s+")

# Abbreviations whose trailing period is not a sentence end.
_ABBREVIATIONS = {
    "dr", "mr", "mrs", "ms", "prof", "sr", "jr", "st", "rev", "hon", "gen", "col", "sgt", "lt",
    "vs", "etc", "al", "cf", "approx", "est", "dept", "univ", "inc", "ltd", "co", "corp",
    "fig", "figs", "eq", "no", "nos", "vol", "vols", "ch", "chap", "sec", "pp", "ed", "eds",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
    "mon", "tue", "wed", "thu", "fri", "sat", "sun",
    "e.g", "i.e", "a.m", "p.m", "u.s", "u.k", "u.s.a", "u.s.s.r", "ph.d", "m.d", "b.a", "m.a", "d.c",
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
    if not word or len(word.replace(".", "")) > 4 or any(len(p) > 1 for p in parts):
        return False
    # A single letter, or dotted initials: "J.", "J.R.R.", "U.S.A.", "U.S.S.R."
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


# Titles and name prefixes. The capital after one of these is the name, not a new sentence:
# "Dr. Smith arrived." must stay one sentence. `jr`/`sr` are deliberately absent — "John Smith
# Jr. He left." is two sentences, and "Jr." is followed by a lowercase verb in the common case
# ("John Smith Jr. is a doctor."), which merges under the case rule anyway.
_TITLE_PREFIXES = frozenset(
    {"dr", "mr", "mrs", "ms", "prof", "st", "rev", "hon", "gen", "col", "sgt", "lt"}
)


def _ends_in_a_name_prefix(fragment: str) -> bool:
    """True when the fragment's final abbreviation is followed by a name, not a sentence.

    Four shapes keep the unconditional merge the abbreviation rule has always had:

    - a lone initial (``J.`` in ``J. R. R. Tolkien``) — the capital after it is the surname;
    - a compact dotted initialism (``J.R.R.``, ``U.S.S.R.``, ``N.A.T.O.``) — same; the old
      3-character cap cut ``The U.S.S.R. collapsed.`` into ``The U.S.S.R.`` + ``collapsed.``,
      a dangling fragment followed by a lowercase fragment that cannot open a sentence;
    - a title from the dictionary (``Dr.``, ``Prof.``) — the capital after it is the name;
    - a digit marker (``1.``, ``3.5.``) — a list or section number whose item follows.

    A multi-character dictionary abbreviation (``p.m.``, ``U.S.A.``, ``et al.``) has no such
    obligation — the capital after one of those opens a new sentence, decided by the case rule.
    """
    tail = fragment.rstrip().rsplit(" ", 1)[-1] if fragment.strip() else ""
    if not tail.endswith("."):
        return False
    word = tail[:-1].strip("([\"'“‘").lower()
    if word in _TITLE_PREFIXES:
        return True
    if len(word.replace(".", "")) <= 1:
        return True
    parts = [p for p in word.split(".") if p]
    if (
        word not in _ABBREVIATIONS
        and parts
        and all(p.isalpha() and len(p) == 1 for p in parts)
    ):
        return True
    return bool(parts) and all(p.isdigit() for p in parts) and tail == fragment.strip()


def _continues_after_abbreviation(previous: str, nxt: str) -> bool:
    """The fragment ends in an abbreviation: merge the next piece unless it clearly starts a sentence.

    ``The meeting is at 3 p.m. Then we left.`` used to come back as ONE sentence. The splitter's
    abbreviation rule is what caused it: ``p.m.`` is in the dictionary, so the merge that protects
    ``Dr. Smith`` and ``e.g. hammers`` also swallowed a real boundary — the period after ``p.m.``
    ended the sentence, and the capital ``Then`` opens the next one. Same for ``U.S.A.``,
    ``et al.`` and every other multi-character abbreviation: on the HC3 register the capital after
    one of those is a new sentence, and the under-count feeds burstiness CV, per-sentence scoring
    and the targeted rewriter's unit of work.

    Name prefixes (``Dr.``, ``J.R.R.``, ``1.``) are exempt — see :func:`_ends_in_a_name_prefix`.
    Everything else merges only when the continuation cannot open a sentence — lowercase, or a
    non-letter start (``et al. (2020)``, ``et al. 2020`` are citations, not sentences).
    """
    if not ends_with_abbreviation(previous):
        return False
    if _ends_in_a_name_prefix(previous):
        return True
    return not nxt.lstrip()[:1].isupper()


# An ellipsis is a pause, not a terminator. `_SENT_SPLIT` looks behind for `[.!?]`, so the last dot
# of "..." ends a sentence and the rest of the clause becomes its own "sentence" — starting in
# lowercase, with no subject. MEASURED, splitting then rewriting at intensity 1.0:
#
#     "He paused... then continued with the analysis."
#       -> "He paused... Then continued with the analysis."     (3 of 3 probes)
#
# The transform is behaving correctly on what it was handed; the split was wrong. And the damage is
# invisible to every gate: no word changed, so similarity, NLI and the role check all pass, and a
# fragment is clean to a tell catalogue.
#
# The test is the NEXT word's case. A genuine sentence after an ellipsis is capitalised
# ("It works... Mostly."); a continuation is not. Narrow on purpose — a real sentence boundary
# after an ellipsis still splits.
_ELLIPSIS_END_RE = re.compile(r"(?:\.{2,}|…)[\"'”’)\]}»]*$")

def _first_alpha_is_lower(nxt: str) -> bool:
    """The continuation's first LETTER is lowercase, skipping leading quotes and brackets.

    ``He paused... "and continued."`` put the opening quote before the first word, so the plain
    ``nxt.lstrip()[:1].islower()`` test saw ``"`` — not a letter, so ``islower()`` is False — and
    treated the lowercase continuation as a new sentence. The quote is not the signal; the first
    word is. A digit still counts as sentence-opening, so ``... 5 minutes later.`` is unchanged.
    """
    for ch in nxt.lstrip():
        if ch.isalpha():
            return ch.islower()
        if ch.isdigit():
            return False
    return False


# A period inside a closing quote: `He said "stop." and left.` — the quote's period is a REAL
# sentence end only when a new sentence follows it. The splitter cannot know, but a LOWERCASE
# continuation is decisive: "and left" cannot open a new sentence, so the period-in-quote was
# mid-sentence. `He said "Done." Then he left.` keeps its split (capital "Then" opens a new
# sentence). Same shape as the ellipsis rule above — the continuation's case decides.
_QUOTED_PERIOD_END_RE = re.compile(r'[.!?]["\'”’)}»\]]\s*$')


def _continues_after_ellipsis(previous: str, nxt: str) -> bool:
    return bool(_ELLIPSIS_END_RE.search(previous.rstrip())) and _first_alpha_is_lower(nxt)


def _continues_after_a_quoted_period(previous: str, nxt: str) -> bool:
    return bool(_QUOTED_PERIOD_END_RE.search(previous.rstrip())) and _first_alpha_is_lower(nxt)


def split_sentences(text: str) -> list[str]:
    """Split on sentence-final punctuation, keeping abbreviations, initials and ellipses intact."""
    parts = [s for s in _SENT_SPLIT.split(text.strip()) if s.strip()]
    merged: list[str] = []
    for part in parts:
        if merged and (
            _continues_after_abbreviation(merged[-1], part)
            or _continues_after_ellipsis(merged[-1], part)
            or _continues_after_a_quoted_period(merged[-1], part)
        ):
            merged[-1] = f"{merged[-1].rstrip()} {part.strip()}"
        else:
            merged.append(part.strip())
    return [s for s in merged if s]


# --- paired chunking -----------------------------------------------------------------------------
# Both meaning gates score (original, rewrite) with a transformer that truncates its input, so
# neither of them was reading the end of a long document. Measured:
#
#   entailment  a negation 143 words in scored 0.0179 — the value for two IDENTICAL strings
#   similarity  replacing a whole sentence with unrelated text 280 words in scored 1.0000
#
# Both gates therefore need the same thing: cut the pair into corresponding pieces small enough to
# survive tokenisation, score each piece, and take the worst. It lives here rather than in either
# gate because two copies of an alignment rule is how they drift apart.
CHUNK_WORDS = 90


def aligned_chunks(a: str, b: str) -> list[tuple[str, str]]:
    """Pair up ``a`` and ``b`` piecewise so neither side reaches the tokeniser's cut.

    Cut points come from ``difflib``, not from proportion. Cutting each side into k equal pieces
    was tried first and drifts: the rewriter merges and splits sentences, so by the third chunk the
    two sides are a sentence apart and the gate compares text that was never meant to correspond.
    Measured, that produced false vetoes on faithful rewrites —

        SRC chunk: "Our results demonstrate that the attention mechanism improves ..."
        OUT chunk: "We also perform a series of ablation studies ... Our results show that ..."

    A rewrite keeps most of its words, so the longest matching word blocks between the two are a
    direct anchor. Each source cut point is mapped through those blocks to the corresponding place
    in the rewrite, and both sides are then cut at genuinely corresponding positions.
    """
    aw, bw = a.split(), b.split()
    longest = max(len(aw), len(bw))
    k = max(1, -(-longest // CHUNK_WORDS))
    if k == 1 or len(aw) < 2 or len(bw) < 2:
        return [(a, b)]

    # difflib's SequenceMatcher is worst-case O(n*m). Measured on identical inputs it
    # doubles ~4.1x per doubling: 1k words 0.56s, 2k 2.12s, 4k 8.77s, 8k 36.1s — a 40k-word
    # document (~900s) would pin an API worker. Past this size the exact matcher costs more
    # than the correspondence it buys; proportional cuts (the fallback below) still bound
    # both sides under CHUNK_WORDS and the gates only need pieces small enough to tokenise.
    _EXACT_ALIGN_LIMIT = 6000  # ~18s today, under the exact path; proportional beyond
    if longest > _EXACT_ALIGN_LIMIT:
        cuts_a = [round(len(aw) * n / k) for n in range(1, k)]
        bounds_a = [0, *cuts_a, len(aw)]
        bounds_b = [0, *cuts_a, len(bw)]
        out: list[tuple[str, str]] = []
        for n in range(k):
            ca = " ".join(aw[bounds_a[n] : bounds_a[n + 1]])
            cb = " ".join(bw[bounds_b[n] : bounds_b[n + 1]])
            if ca.strip() and cb.strip():
                out.append((ca, cb))
        return out or [(a, b)]

    matcher = difflib.SequenceMatcher(a=aw, b=bw, autojunk=False)
    blocks = matcher.get_matching_blocks()  # ends with a zero-length sentinel
    # No real matching blocks (the "replaced a whole sentence with unrelated text" case, or a
    # completely disjoint pair): every cut would map through the sentinel to len(bw), collapsing
    # all target chunks into one and leaving the source truncated at the first window — MEASURED:
    # a 300-word source vs a 300-word disjoint target produced ONE chunk of 75 source words vs
    # all 300 target words. The proportional fallback below is the same one the over-6000-word
    # path uses: it bounds BOTH sides under CHUNK_WORDS, which is all the gates need.
    if len([b for b in blocks if b.size > 0]) == 0:
        cuts = [round(len(aw) * n / k) for n in range(1, k)]
        bounds_a = [0, *cuts, len(aw)]
        bounds_b = [0, *[round(len(bw) * n / k) for n in range(1, k)], len(bw)]
        out: list[tuple[str, str]] = []
        for n in range(k):
            ca = " ".join(aw[bounds_a[n] : bounds_a[n + 1]])
            cb = " ".join(bw[bounds_b[n] : bounds_b[n + 1]])
            if ca.strip() and cb.strip():
                out.append((ca, cb))
        return out or [(a, b)]

    def map_index(i: int) -> int:
        """Where in ``b`` does word ``i`` of ``a`` correspond to?"""
        for blk in blocks:
            if blk.a <= i < blk.a + blk.size:
                return blk.b + (i - blk.a)
            if blk.a > i:  # fell in a gap — anchor to the start of the next matching block
                return blk.b
        return len(bw)

    cuts_a = [round(len(aw) * n / k) for n in range(1, k)]
    bounds_a = [0, *cuts_a, len(aw)]
    bounds_b = [0, *[map_index(c) for c in cuts_a], len(bw)]
    # Monotonicity is not guaranteed if a block anchor jumps backwards; enforce it rather than
    # emitting a reversed slice, which would silently produce an empty chunk.
    for n in range(1, len(bounds_b)):
        bounds_b[n] = max(bounds_b[n], bounds_b[n - 1])

    out: list[tuple[str, str]] = []
    for n in range(k):
        ca = " ".join(aw[bounds_a[n] : bounds_a[n + 1]])
        cb = " ".join(bw[bounds_b[n] : bounds_b[n + 1]])
        if ca.strip() and cb.strip():
            out.append((ca, cb))
    return out or [(a, b)]


# Unicode space separators (category Zs) other than the plain space. A non-breaking space is
# visually identical to a space and is what a paste out of Word, a web page or a PDF contains —
# but nothing treats it as one: no tokeniser, and no regex written with a literal " ".
#
# Lives here rather than in either caller because it went wrong twice independently, in the two
# places that both needed it:
#
#   scoring   MEASURED on 10 HC3 pairs, full tier, every space replaced with U+00A0: human text
#             went 5/10 -> 9/10 flagged, mean P(AI) 0.4322 -> 0.7801, hc3_roberta moving 0.9990.
#   tells     the catalogue's multi-word patterns are written with literal spaces, so
#             "in conclusion" stops matching "in\u00a0conclusion". MEASURED on a 37-word AI
#             paragraph: 5 tells -> 3, and humanness 37.4 -> 43.9.
#
# One rule, one place. `untell/scripts/score.py` had a normaliser written for exactly this class
# and scoped to `[ \t]{2,}`; scoping is how a fix for a class misses most of the class.
_UNICODE_SPACE_RE = re.compile("[\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]")


def fold_unicode_spaces(text: str) -> str:
    """Replace every non-ASCII Unicode space separator with a plain space.

    Deliberately does NOT collapse runs or strip anything else: callers that want run-collapsing
    do it themselves, and a caller that only wants the characters comparable should not have its
    layout changed underneath it.
    """
    return _UNICODE_SPACE_RE.sub(" ", text)
