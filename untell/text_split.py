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
# CJK corner brackets are closers too — without them a 「quote」 would shed its closer onto the
# next fragment.
_CLOSERS = "\"'”’)]}»「」『』"
_C = re.escape(_CLOSERS)

# Sentence terminators beyond ASCII. CJK prose (。！？) and Arabic/Urdu (؟ ۔) end their
# sentences with these and, unlike English, run the next clause straight on with no
# whitespace at all — a `\s+` requirement leaves the whole document as ONE sentence.
# MEASURED before this existed:
#
#     split_sentences('这是第一句。这是第二句！这是第三句？')  ->  ONE sentence
#     split_sentences('یہ ایک جملہ ہے۔ یہ دوسرا جملہ ہے۔')    ->  ONE sentence
#     split_sentences('هل أنت متأكد؟ نعم. ثم غادر.')          ->  '؟' not a boundary
#
# A single sentence feeds burstiness CV as 0.0 (one length, no variation), makes per-sentence
# targeting name the whole document, and hands the rewriters one giant unit of work. Hebrew
# is unaffected: it uses the ASCII period.
_UNICODE_TERMINATORS = "。！？؟۔"
_UT = re.escape(_UNICODE_TERMINATORS)

# Zero-width characters that can sit between a sentence terminator and the next word
# without being seen by `\s`: ZWSP/ZWNJ/ZWJ, word joiner, BOM, the invisible math operators
# and the variation selectors — the same carrier set `untell.attacks.unicode_tricks`
# scrubs (no legitimate variation selector follows a full stop). The splitter does NOT
# remove them — ZWJ is load-bearing inside emoji sequences — it only refuses to let an
# invisible character hide a boundary the author wrote.
_ZERO_WIDTH_BETWEEN = (
    "\u200b\u200c\u200d\u2060\ufeff"  # ZWSP, ZWNJ, ZWJ, word joiner, BOM
    "\u2061\u2062\u2063\u2064"  # invisible math operators
    "\ufe00\ufe01\ufe02\ufe03\ufe04\ufe05\ufe06\ufe07\ufe08\ufe09\ufe0a\ufe0b\ufe0c\ufe0d\ufe0e\ufe0f"  # variation selectors
)
_ZERO_WIDTH_CLASS = re.escape(_ZERO_WIDTH_BETWEEN)

# Footnote/endnote markers that may sit between a sentence terminator and the next
# sentence: "significant.[1] However" and "significant.¹ However" are boundaries, and
# the marker belongs to the sentence that ends — it stays behind the split point, the
# same way a closer does. Superscript digits (¹²³ ⁰⁴⁵⁶⁷⁸⁹) plus the dagger family
# († ‡ *) and the bracketed form up to three digits — a footnote past [999] is a
# document nobody writes, and the fallback for it is the old under-split.
_FOOTNOTE_MARKERS = "\u00b9\u00b2\u00b3\u2070\u2074\u2075\u2076\u2077\u2078\u2079\u2020\u2021*"
_FN = re.escape(_FOOTNOTE_MARKERS)

_SENT_SPLIT = re.compile(
    rf"(?<=[.!?])\s+"
    rf"|(?<=[.!?][{_C}])\s+"
    rf"|(?<=[.!?][{_C}][{_C}])\s+"
    # Non-ASCII terminators need no following whitespace — CJK runs the next clause on.
    # A negative lookahead prefers the closer alternative below, so 「好。」 keeps its closer.
    rf"|(?<=[{_UT}])(?![{_C}])"
    rf"|(?<=[{_UT}][{_C}])"
    rf"|(?<=[{_UT}][{_C}][{_C}])"
    # Zero-width carriers between the terminator and the next word. Up to two, mirroring
    # the closer bound; a third is a document nobody writes, and the fallback for it is
    # the old under-split. The same closer-preference applies: "Done.\u200b\"Next" splits
    # after the quote, not before it — and a single-ZW alternative must not fire before a
    # two-ZW run ("Done.\u200b\u200bNext" splits after the second carrier, keeping the
    # pair with the sentence that owns it).
    rf"|(?<=[.!?][{_ZERO_WIDTH_CLASS}])(?![{_C}{_ZERO_WIDTH_CLASS}])"
    rf"|(?<=[.!?][{_ZERO_WIDTH_CLASS}][{_ZERO_WIDTH_CLASS}])(?![{_C}])"
    rf"|(?<=[.!?][{_C}][{_ZERO_WIDTH_CLASS}])"
    rf"|(?<=[.!?][{_ZERO_WIDTH_CLASS}][{_C}])"
    # Footnote/endnote markers between the terminator and the next sentence. Each shape
    # is a separate fixed-width lookbehind: bracketed digits (1, 2, 3 wide), a bracketed
    # pair ("[1][2]"), a marker followed by a closer, and one or two superscript/dagger
    # markers ("¹", "††").
    rf"|(?<=[.!?]\[\d\])\s+"
    rf"|(?<=[.!?]\[\d\d\])\s+"
    rf"|(?<=[.!?]\[\d\d\d\])\s+"
    rf"|(?<=[.!?]\[\d\]\[\d\])\s+"
    rf"|(?<=[.!?]\[\d\][{_C}])\s+"
    rf"|(?<=[.!?][{_FN}])\s+"
    rf"|(?<=[.!?][{_FN}][{_FN}])\s+"
)

# Abbreviations whose trailing period is not a sentence end.
_ABBREVIATIONS = {
    "dr", "mr", "mrs", "ms", "prof", "sr", "jr", "st", "rev", "hon", "gen", "col", "sgt", "lt",
    "vs", "etc", "al", "cf", "approx", "ca", "viz", "nb", "op", "cit", "est", "dept", "univ",
    "inc", "ltd", "co", "corp",
    "fig", "figs", "eq", "no", "nos", "vol", "vols", "ch", "chap", "sec", "pp", "ed", "eds",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
    "mon", "tue", "wed", "thu", "fri", "sat", "sun",
    "e.g", "i.e", "a.m", "p.m", "u.s", "u.k", "u.s.a", "u.s.s.r", "ph.d", "m.d", "b.a", "m.a", "d.c",
}


def ends_with_abbreviation(fragment: str) -> bool:
    """True when this fragment's final period belongs to an abbreviation or an initial."""
    tail = fragment.rstrip().rsplit(" ", 1)[-1] if fragment.strip() else ""
    # A zero-width carrier after the period (a watermark shape) must not hide the
    # abbreviation: "3 p.m.\u200b" is still "p.m." to this test.
    tail = tail.rstrip(_ZERO_WIDTH_BETWEEN)
    if not tail.endswith("."):
        return False
    word = tail[:-1].strip("([\"'“‘").lower()
    if word in _ABBREVIATIONS:
        return True
    parts = [p for p in word.split(".") if p]
    if not word or len(word.replace(".", "")) > 6 or any(len(p) > 1 for p in parts):
        return False
    # A single letter, or dotted initials: "J.", "J.R.R.", "U.S.A.", "U.S.S.R.", "U.N.E.S.C.O."
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
    return all(p.isdigit() for p in parts) and tail == fragment.strip().rstrip(_ZERO_WIDTH_BETWEEN)


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
    tail = tail.rstrip(_ZERO_WIDTH_BETWEEN)
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
    return bool(parts) and all(p.isdigit() for p in parts) and tail == fragment.strip().rstrip(_ZERO_WIDTH_BETWEEN)


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
_ELLIPSIS_END_RE = re.compile(r"(?:\.{2,}|…)" "[\"'”’)\]}»" + _ZERO_WIDTH_CLASS + r"]*$")

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
# The closer is REQUIRED (one, then any number of closers/zero-width carriers): the rule must
# not fire on a plain "ten." with a lowercase follow-up, or every ordinary sentence pair
# would be welded together.
_QUOTED_PERIOD_END_RE = re.compile(
    rf'[.!?][\"\'”’)}}\]»](?:[\"\'”’)}}\]»{_ZERO_WIDTH_CLASS}])*\s*$'
)


def _continues_after_ellipsis(previous: str, nxt: str) -> bool:
    return bool(_ELLIPSIS_END_RE.search(previous.rstrip())) and _first_alpha_is_lower(nxt)


def _continues_after_a_quoted_period(previous: str, nxt: str) -> bool:
    return bool(_QUOTED_PERIOD_END_RE.search(previous.rstrip())) and _first_alpha_is_lower(nxt)


# A footnote marker between the period and the next fragment: "significant.[1] but only
# marginally." — the marker belongs to the FIRST sentence, and a lowercase continuation
# cannot open a new one, so the split must merge back, exactly like the quoted-period
# rule above. A capitalised continuation ("significant.[1] However") keeps the split.
# The marker itself is not a closer, which is why the split rule above exists and why a
# separate end-test is needed here — `_QUOTED_PERIOD_END_RE` looks for a closer right
# after the terminator and does not see through "[1]".
_FOOTNOTE_END_RE = re.compile(
    rf'[.!?](?:\[\d{{1,3}}\]|[{_FN}])+[\"\'’)}}\]{_ZERO_WIDTH_CLASS}]*\s*$'
)


def _continues_after_a_footnote(previous: str, nxt: str) -> bool:
    return bool(_FOOTNOTE_END_RE.search(previous.rstrip())) and _first_alpha_is_lower(nxt)


def split_sentences(text: str) -> list[str]:
    """Split on sentence-final punctuation, keeping abbreviations, initials and ellipses intact."""
    parts = [s for s in _SENT_SPLIT.split(text.strip()) if s.strip()]
    merged: list[str] = []
    for part in parts:
        if merged and (
            _continues_after_abbreviation(merged[-1], part)
            or _continues_after_ellipsis(merged[-1], part)
            or _continues_after_a_quoted_period(merged[-1], part)
            or _continues_after_a_footnote(merged[-1], part)
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

    # IDENTICAL WORD LISTS never need the exact matcher at all. SequenceMatcher on identical
    # input returns ONE full block, so `map_index` is the identity and the output is exactly
    # the proportional cuts below — but only after paying O(n*m) to discover that. MEASURED on
    # identical input, where the current code is quadratic:
    #
    #     words   1000    2000    4000    6000
    #     time    0.42s   1.81s   7.44s   20.06s
    #
    # Identical pairs are a real call path, not a benchmark artifact — `contradiction_score(doc,
    # doc)` (measured 0.6091 on a 301-word RAID abstract, see entailment.py) and the
    # `similarity(t, t)` recursion both land here, and every chunk short-circuits the model call
    # (`ca == cb`), so the alignment IS the whole cost of scoring a document against itself.
    # The threshold keeps the mutation guards (100/181-word identical fixtures) on the difflib
    # path; below 1000 words the exact matcher is under half a second and the guard coverage is
    # worth it.
    _IDENTICAL_FAST_PATH_MIN = 1000
    if aw == bw and len(aw) >= _IDENTICAL_FAST_PATH_MIN:
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
