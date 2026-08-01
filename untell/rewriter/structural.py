"""Structural rewriter — sentence-level transformations without an LLM.

The surgical rewriter (``SurgicalRewriter``) does word-level synonym substitution. This rewriter
does **structural** transformations: it strips formulaic transitions, merges/splits sentences,
flattens participial trailers, breaks negated contrasts, and varies sentence openings — all
without an API key, GPU, or model download.

These are the exact transformations that move the needle on the local detector ensemble
(perplexity/burstiness respond to sentence-length variance; supervised detectors respond to
formulaic structure). Combining structural + surgical transforms gives the free $0 path
**far more leverage** than either alone.

Always ``available()``. Deterministic (identical input → identical output for a given seed).
"""

from __future__ import annotations

import random
import re

from untell.rewriter.base import Rewriter

# ---------------------------------------------------------------------------
# Sentence-level patterns
# ---------------------------------------------------------------------------

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

# Abbreviations whose trailing period is NOT a sentence end. Without these, "Dr. Smith published
# the results" split into "Dr." and "Smith published the results", and the sentence merger then
# rejoined them as "Dr, though smith published the results" — an abbreviation destroyed and a
# surname lowercased, in a tool whose entire promise is that facts survive the rewrite.
_ABBREVIATIONS = {
    "dr", "mr", "mrs", "ms", "prof", "sr", "jr", "st", "rev", "hon", "gen", "col", "sgt", "lt",
    "vs", "etc", "al", "cf", "approx", "est", "dept", "univ", "inc", "ltd", "co", "corp",
    "fig", "figs", "eq", "no", "nos", "vol", "vols", "ch", "chap", "sec", "pp", "ed", "eds",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
    "mon", "tue", "wed", "thu", "fri", "sat", "sun",
    "e.g", "i.e", "a.m", "p.m", "u.s", "u.k", "ph.d", "m.d", "b.a", "m.a", "d.c",
}

# Words it is safe to lowercase when a sentence becomes a subordinate clause. Anything outside this
# set is left capitalised and the merge is SKIPPED, because the alternative — lowercasing whatever
# happens to start the sentence — turns "Smith published" into "smith published" and "NASA
# confirmed" into "nASA confirmed". Fewer merges is a cheap price for never mangling a name.
_SAFE_TO_LOWERCASE = {
    # function words and determiners
    "the", "this", "that", "these", "those", "a", "an", "it", "its", "they", "their", "them",
    "he", "his", "him", "she", "her", "we", "our", "us", "you", "your", "i", "my", "there",
    "here", "some", "many", "most", "much", "all", "each", "every", "both", "few", "several",
    "one", "two", "three", "no", "not", "if", "when", "while", "after", "before", "since",
    "because", "although", "though", "unless", "until", "as", "but", "and", "or", "so", "yet",
    "in", "on", "at", "for", "from", "with", "without", "by", "to", "into", "over", "under",
    "such", "other", "another", "any", "who", "which", "what", "how", "why", "where",
    # ordinary nouns that routinely open a sentence in expository prose
    "people", "operators", "users", "results", "data", "studies", "research", "researchers",
    "companies", "organizations", "organisations", "businesses", "students", "customers",
    "patients", "developers", "engineers", "teams", "systems", "models", "tools", "machine",
    "software", "hardware", "technology", "technologies", "industries", "governments",
    "scientists", "doctors", "workers", "employees", "managers", "leaders", "experts",
    "evidence", "analysis", "performance", "efficiency", "productivity", "growth", "costs",
    "benefits", "risks", "challenges", "problems", "solutions", "changes", "effects",
    "impact", "adoption", "training", "testing", "development", "production", "demand",
    "supply", "prices", "revenue", "profits", "sales", "markets", "users", "clients",
    "documents", "files", "records", "reports", "papers", "articles", "books", "sources",
    "methods", "approaches", "techniques", "strategies", "policies", "practices", "processes",
    "exercise", "nutrition", "health", "treatment", "symptoms", "patients", "trials",
    "climate", "energy", "emissions", "pollution", "temperatures", "weather", "sea",
    "education", "schools", "teachers", "learning", "knowledge", "skills", "experience",
    # common adjectives and adverbs in the same position
    "artificial", "regular", "effective", "modern", "current", "recent", "further", "additional",
    "similar", "different", "specific", "general", "overall", "typical", "common", "important",
    "significant", "large", "small", "high", "low", "new", "old", "good", "better", "best",
    "worse", "worst", "early", "late", "fast", "slow", "long", "short", "clear", "likely",
    "unlike", "despite", "given", "based", "using", "according",
}

# Capitalisation that is never sentence-position capitalisation: an internal capital (NASA, iPhone,
# McDonald) always signals a name or acronym, whatever the word list says.
_INTERNAL_CAPS_RE = re.compile(r"^[A-Za-z][a-z]*[A-Z]")

def _safe_to_lowercase(word: str, context: str = "") -> bool:
    """Can this sentence-initial word be lowercased without mangling a name or acronym?

    Three sources of evidence, cheapest first — no model, so the free path stays dependency-free:
      * an internal or full capital ("NASA", "iPhone") is never sentence-position capitalisation;
      * a curated list of words that routinely open an expository sentence;
      * the word appearing in lower case elsewhere in the same text, which is strong evidence it is
        an ordinary word that merely happens to sit at a sentence start here.
    """
    bare = word.strip(",;:.!?\"'()").lower()
    if not bare:
        return False
    if word.isupper() and len(word) > 1:
        return False
    if _INTERNAL_CAPS_RE.match(word.strip(",;:.!?\"'()")):
        return False
    if bare in _SAFE_TO_LOWERCASE:
        return True
    return bool(context) and re.search(rf"(?<![.!?]\s)\b{re.escape(bare)}\b", context) is not None


# Discourse markers that may survive at the start of the second clause. Joining with ", and " when
# the clause already opens with one produced "and plus,", "while and," and "and and," — visible
# garbage in the primary free rewriter's output.
_LEADING_MARKER_RE = re.compile(
    r"^(?:and|but|or|so|yet|plus|also|then|however|moreover|furthermore|additionally|"
    r"overall|therefore|thus|hence|indeed|besides|meanwhile|still)\b,?\s+",
    re.IGNORECASE,
)

# Formulaic transitions that OPEN a sentence (§3, §8 from ai-tells.md).
_TRANSITIONS_RE = re.compile(
    r"^(Moreover|Furthermore|Additionally|Overall|In conclusion|In summary|"
    r"Notably|Importantly|Consequently|Therefore|Thus|Hence|"
    r"Ultimately|Nevertheless|Nonetheless|Accordingly|Subsequently|"
    r"Arguably|Indeed|Essentially|In essence),?\s+",
    re.IGNORECASE,
)

# Participial-phrase trailers: sentence ending with ", [verb]ing ...".
# Map of participial verb → simple present tense for the flatten transform.
_PARTICIPIAL_VERBS: dict[str, str] = {
    "underscoring": "underscores", "underlining": "underlines",
    "marking": "marks", "reflecting": "reflects",
    "highlighting": "highlights", "showcasing": "showcases",
    "emphasizing": "emphasizes", "signaling": "signals",
    "cementing": "cements", "solidifying": "solidifies",
    "paving": "paves", "ensuring": "ensures",
    "demonstrating": "demonstrates", "reinforcing": "reinforces",
    "suggesting": "suggests", "indicating": "indicates",
    "revealing": "reveals", "confirming": "confirms",
}
_PARTICIPIAL_RE = re.compile(
    r",\s+(" + r"|".join(re.escape(v) for v in _PARTICIPIAL_VERBS) + r")\b[^.!?]*[.!?]",
    re.IGNORECASE,
)

# Negated contrast: "It's not X, it's Y" / "Not only X but also Y".
# These are complex patterns; the flatten function below handles each case.
_NEGATED_CONTRAST_RE = re.compile(
    r"\bit'?s not\s+.+?,?\s+it'?s\s+\w+[^.]*\.?"
    r"|not only\b[^.]{0,60}\bbut also\b"
    r"|isn'?t about\b[^.;]{0,50};?\s+it'?s about\b"
    r"|not\s+just\b[^.]{0,40}\bbut\b",
    re.IGNORECASE | re.DOTALL,
)

# Inflated copula: verbs an AI reaches for where plain "is" would do. "marks" is dropped — it is
# usually a genuine transitive verb ("marks the score"/"marks the spot"), not a copula, so flattening
# it to "is" corrupts meaning. "boasts" flattens to "has", not "is" ("the city boasts a museum" ->
# "the city has a museum", never "is a museum") and is handled separately below.
_INFLATED_COPULA_RE = re.compile(
    r"\b(serves as|represents|epitomizes|exemplifies)\b",
    re.IGNORECASE,
)
_BOASTS_RE = re.compile(r"\bboasts\b", re.IGNORECASE)

# Vague attribution: "studies show", "research suggests".
_VAGUE_ATTR_RE = re.compile(
    r"\b(studies show|research suggests?|experts? (?:believe|say|agree)|scientists? believe|"
    r"it is (?:widely )?believed|many believe|some argue)\b",
    re.IGNORECASE,
)

# Semicolons used as rhythm crutch.
_SEMICOLON_RE = re.compile(r";\s+")

# Low-content AI scaffolding openers — pure filler that precedes the real sentence. Strip the phrase
# and keep the clause. "It is worth noting that X" -> "X"; "It should be noted that X" -> "X".
_FILLER_OPENER_RE = re.compile(
    r"(?P<lead>^|(?<=[.!?]\s))\s*"
    r"(?:it (?:is|'s) (?:worth (?:noting|mentioning)|important to (?:note|mention|highlight|remember)) that"
    r"|it should be noted that"
    r"|one (?:thing|point) (?:to note|worth noting) is that"
    r"|(?:it is|there is) no (?:doubt|denying) that"
    r"|needless to say,?"
    r"|as (?:we|previously) (?:noted|mentioned|discussed),?)\s+(?P<rest>\S.*?)?(?=$|[.!?])",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Word-level patterns (additional to SurgicalRewriter's synonym map)
# ---------------------------------------------------------------------------

# High-frequency AI hedging — strip the second word, keep the modal.
_HEDGE_RE = re.compile(
    r"\b(could|may|might|would|can)\s+(potentially|eventually|possibly|likely|arguably)\b",
    re.IGNORECASE,
)

# Contraction injection. AI text contracts far less than human writing (a strong, cheap function-word
# / formality signal). Each (pattern -> contraction) is applied case-preserving for a sentence-initial
# capital. Ordered longest-first so "it is not" contracts the negation before "it is". Verb+not forms
# are safe; ambiguous ones ("she's" = she is / she has) are left out to avoid changing meaning.
_CONTRACTIONS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(can)not\b", re.I), r"\1't"),      # cannot -> can't (special: one word)
    (re.compile(r"\bdo not\b", re.I), "don't"),
    (re.compile(r"\bdoes not\b", re.I), "doesn't"),
    (re.compile(r"\bdid not\b", re.I), "didn't"),
    (re.compile(r"\bis not\b", re.I), "isn't"),
    (re.compile(r"\bare not\b", re.I), "aren't"),
    (re.compile(r"\bwas not\b", re.I), "wasn't"),
    (re.compile(r"\bwere not\b", re.I), "weren't"),
    (re.compile(r"\bwill not\b", re.I), "won't"),
    (re.compile(r"\bwould not\b", re.I), "wouldn't"),
    (re.compile(r"\bshould not\b", re.I), "shouldn't"),
    (re.compile(r"\bcould not\b", re.I), "couldn't"),
    (re.compile(r"\bcan not\b", re.I), "can't"),
    (re.compile(r"\bhave not\b", re.I), "haven't"),
    (re.compile(r"\bhas not\b", re.I), "hasn't"),
    (re.compile(r"\bhad not\b", re.I), "hadn't"),
    (re.compile(r"\bit is\b", re.I), "it's"),
    (re.compile(r"\bthat is\b", re.I), "that's"),
    (re.compile(r"\bthere is\b", re.I), "there's"),
    (re.compile(r"\bhere is\b", re.I), "here's"),
    (re.compile(r"\bwhat is\b", re.I), "what's"),
    (re.compile(r"\bwho is\b", re.I), "who's"),
    (re.compile(r"\bthey are\b", re.I), "they're"),
    (re.compile(r"\bwe are\b", re.I), "we're"),
    (re.compile(r"\byou are\b", re.I), "you're"),
    (re.compile(r"\bthey will\b", re.I), "they'll"),
    (re.compile(r"\bwe will\b", re.I), "we'll"),
    (re.compile(r"\byou will\b", re.I), "you'll"),
    (re.compile(r"\bit will\b", re.I), "it'll"),
    (re.compile(r"\blet us\b", re.I), "let's"),
    (re.compile(r"\bI am\b"), "I'm"),
    (re.compile(r"\bI will\b"), "I'll"),
    (re.compile(r"\bI have\b"), "I've"),
]

# ---------------------------------------------------------------------------
# Structural transforms
# ---------------------------------------------------------------------------


def _ends_with_abbreviation(fragment: str) -> bool:
    """True when this fragment's final period belongs to an abbreviation or an initial."""
    tail = fragment.rstrip().rsplit(" ", 1)[-1] if fragment.strip() else ""
    if not tail.endswith("."):
        return False
    word = tail[:-1].strip("([\"'“‘").lower()
    if word in _ABBREVIATIONS:
        return True
    # A single letter, or dotted initials: "J.", "J.R.R.", "U.S.A."
    return bool(word) and len(word.replace(".", "")) <= 3 and all(
        len(part) <= 1 for part in word.split(".") if part
    )


def _split_sentences(text: str) -> list[str]:
    """Split on sentence-final punctuation, keeping abbreviations intact."""
    parts = [s for s in _SENT_SPLIT.split(text.strip()) if s.strip()]
    merged: list[str] = []
    for part in parts:
        if merged and _ends_with_abbreviation(merged[-1]):
            merged[-1] = f"{merged[-1].rstrip()} {part.strip()}"
        else:
            merged.append(part.strip())
    return [s for s in merged if s]


def _strip_transitions(sentences: list[str], rate: float = 1.0) -> list[str]:
    """Strip formulaic openers from a fraction of sentences (``rate`` in [0, 1])."""
    out: list[str] = []
    for _i, s in enumerate(sentences):
        if random.random() < rate:
            s = _TRANSITIONS_RE.sub("", s)
            if s and s[0].islower():
                s = s[0].upper() + s[1:]
        out.append(s)
    return out


def _merge_sentences(sentences: list[str], rate: float = 0.33) -> list[str]:
    """Merge adjacent sentence pairs into compound sentences (raises burstiness)."""
    if len(sentences) < 2:
        return sentences
    out: list[str] = []
    i = 0
    while i < len(sentences):
        if i + 1 < len(sentences) and random.random() < rate:
            a = sentences[i].rstrip(".")
            b = sentences[i + 1].strip()
            # A clause that already opens with a discourse marker cannot take another connector:
            # ", and " + "plus, it improves..." reads "and plus, it improves". Strip the marker
            # first — the connector about to be added does the same job.
            b = _LEADING_MARKER_RE.sub("", b, count=1)
            merged_ok = bool(b) and (
                b[0].islower() or _safe_to_lowercase(b.split()[0], " ".join(sentences))
            )
            if b and merged_ok:
                b = b.strip(".")
                b = b[0].lower() + b[1:] if b and b[0].isupper() else b
                connectors = [", and ", ", but ", ", while ", "; ", ", though "]
                conn = random.choice(connectors)
                out.append(f"{a}{conn}{b}.")
                i += 2
                continue
            # Not safe to demote to a subordinate clause (a name, an acronym, an unknown noun):
            # leave both sentences alone rather than lowercasing something that must stay capital.
            out.append(sentences[i])
            i += 1
        else:
            out.append(sentences[i])
            i += 1
    return out


def _split_long_sentences(sentences: list[str], max_words: int = 28, rate: float = 0.25) -> list[str]:
    """Split sentences longer than ``max_words`` words at a suitable break point."""
    out: list[str] = []
    for s in sentences:
        words = s.split()
        if len(words) > max_words and random.random() < rate:
            # Find a good split: after a comma, semicolon, or at a natural midpoint.
            mid = len(words) // 2
            # Look for a comma around the midpoint.
            split_at = mid
            for offset in range(mid):
                for pos in (mid + offset, mid - offset):
                    if 0 < pos < len(words) and words[pos].endswith(","):
                        split_at = pos + 1
                        break
                if split_at != mid:
                    break
            first = " ".join(words[:split_at]).rstrip(",")
            second = " ".join(words[split_at:])
            if second:
                second = second[0].lower() + second[1:] if second[0].isupper() else second
                # Check if we broke mid-clause (second starts with a conjunction)
                if second.split()[0].lower() in ("and", "or", "but", "while", "because", "since", "although", "though"):
                    out.append(f"{first}, {second}.")
                else:
                    out.append(f"{first}. {second[0].upper() + second[1:] if second else second}.")
            else:
                out.append(s)
        else:
            out.append(s)
    return out


def _flatten_participial_trailers(text: str) -> str:
    """Convert ', underscoring its importance' → '. This underscores its importance'."""
    def _replace(m: re.Match) -> str:
        verb_ing = m.group(1).lower()  # e.g. "underscoring"
        present = _PARTICIPIAL_VERBS.get(verb_ing, verb_ing.rstrip("ing") + "s")
        # Everything after the participial verb, sliced by the match's own group offsets so any amount
        # of whitespace (", underscoring", ",  underscoring", ",\nunderscoring") is handled correctly.
        after = m.group(0)[m.end(1) - m.start(0):]  # " its importance." — keeps the leading space
        after = after.rstrip(".!?")                 # drop the trailing terminator, keep leading space
        return f". This {present}{after}."

    return _PARTICIPIAL_RE.sub(_replace, text)


def _flatten_negated_contrast(text: str) -> str:
    """Convert 'It's not X, it's Y' → 'It's Y' preserving the positive statement."""
    def _replace(m: re.Match) -> str:
        full = m.group(0)
        # Pattern: "It's not X, it's Y" — extract the Y part after the second "it's"
        if "it's not" in full.lower() and "it's" in full.lower():
            # Find the last "it's" and take everything after it
            idx = full.lower().rindex("it's")
            after = full[idx + len("it's"):].strip().strip(".,;!?")
            return f"It's {after}."

        if "not only" in full.lower() and "but also" in full.lower():
            parts = full.split("but also", 1)
            if len(parts) == 2:
                return parts[1].strip().lstrip(",").strip()

        if "isn't about" in full.lower():
            parts = full.split(";", 1)
            if len(parts) >= 2:
                return parts[-1].strip()

        if "not just" in full.lower():
            parts = full.split("but", 1)
            if len(parts) == 2:
                return parts[1].strip()

        return full

    return _NEGATED_CONTRAST_RE.sub(_replace, text)


def _inject_contractions(text: str, rate: float = 1.0) -> str:
    """Contract formal verb phrases ("do not" -> "don't", "it is" -> "it's"). Case-preserving.

    AI text contracts far less than human writing; injecting contractions shifts the function-word /
    formality distribution toward human. ``rate`` in [0, 1] applies to each candidate match.
    """
    for pat, repl in _CONTRACTIONS:
        def _sub(m: re.Match, _repl: str = repl) -> str:
            if rate < 1.0 and random.random() > rate:
                return m.group(0)
            out = m.expand(_repl)
            if m.group(0)[:1].isupper():
                out = out[0].upper() + out[1:]
            return out

        text = pat.sub(_sub, text)
    return text


def _strip_filler_openers(text: str) -> str:
    """Remove low-content AI scaffolding openers ("It is worth noting that ...") and keep the clause,
    re-capitalizing the sentence start that the strip exposes."""
    # Capitalise ONLY the clause each strip exposes — never the whole text. The previous
    # implementation ran `re.sub(r"(^|[.!?]\s+)([a-z])", ...)` over the entire string after the
    # strip, which capitalises any lowercase word following ANY sentence-ending punctuation. That
    # includes the period inside an abbreviation, so text this function never touched came back
    # corrupted:
    #     "The study used e.g. three methods."  -> "... e.g. Three methods."
    #     "We met at 3 p.m. tomorrow"           -> "... 3 p.m. Tomorrow"
    # The abbreviation guard in _split_sentences does not help here, because this runs on raw text
    # before any sentence splitting. Folding the capitalisation into the substitution itself means
    # nothing outside a matched filler can be altered.
    def _strip_and_capitalise(m: re.Match) -> str:
        lead = m.group("lead") or ""
        rest = m.group("rest") or ""
        return lead + (rest[:1].upper() + rest[1:] if rest else "")

    return _FILLER_OPENER_RE.sub(_strip_and_capitalise, text)


# Sentinel spans (⟦HZxxxx⟧) must never be touched by a word-level substitution.
_SENTINEL_SPAN_RE = re.compile(r"⟦HZ\d{4,}⟧")


def _plain_register(text: str, intensity: float = 1.0) -> str:
    """Swap formal / AI-inflected vocabulary for the words people actually use.

    A 180-entry formal->plain map already existed, but only the *surgical* rewriter used it, ranked
    by detector-importance and capped by ``max_subs`` — so most swaps never fired, and the ones that
    did were chosen to move a score rather than to change register.

    Register change is the single most natural humanizing move ("utilize" -> "use", "demonstrates"
    -> "shows"), and until now the loop could not use it at all: the meaning gate scored cosine
    similarity, which PENALISES register change, and rejected 6/6 faithful formal->casual rewrites.
    With the NLI gate carrying fidelity instead, those rewrites are finally adoptable — so it is
    worth making them wholesale rather than incidentally.

    ``intensity`` scales how many eligible words are swapped, which also gives best-of-N draws real
    diversity instead of near-identical variants.
    """
    if not text.strip():
        return text
    from untell.attacks.word_importance import _SYN

    # Protect locked spans: mask them out, substitute, then restore.
    spans: list[str] = []

    def _stash(m: re.Match) -> str:
        spans.append(m.group(0))
        return f"\x00{len(spans) - 1}\x00"

    masked = _SENTINEL_SPAN_RE.sub(_stash, text)

    def _swap(m: re.Match) -> str:
        word = m.group(0)
        options = _SYN.get(word.lower())
        if not options or random.random() > intensity:
            return word
        choice = random.choice(options)
        # Preserve the original capitalisation so sentence starts survive the swap.
        if word[:1].isupper():
            choice = choice[:1].upper() + choice[1:]
        return choice

    masked = re.sub(r"[A-Za-z]+", _swap, masked)
    return re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], masked)


def _flatten_copula(text: str) -> str:
    """Flatten inflated copulas: 'serves as'/'represents'/... → 'is', and 'boasts' → 'has'."""
    text = _BOASTS_RE.sub("has", text)
    text = _INFLATED_COPULA_RE.sub("is", text)
    return text


def _flatten_vague_attribution(text: str) -> str:
    """Replace 'studies show' with concrete alternatives."""
    text = _VAGUE_ATTR_RE.sub("evidence suggests", text)
    return text


def _vary_openers(sentences: list[str], rate: float = 0.3) -> list[str]:
    """Vary sentence openings by prepending transitional phrases or restructuring."""
    openers = [
        "Actually,", "In practice,", "Broadly,", "In short,", "Looking at this,",
        "As it turns out,", "Put simply,", "Realistically,",
    ]
    subjects = ["The", "This", "It", "That", "There"]
    out: list[str] = []
    for s in sentences:
        if random.random() < rate:
            first_word = s.split()[0] if s.split() else ""
            if first_word and first_word[0].isupper() and first_word not in subjects:
                # Prepend the opener, and lowercase what follows ONLY when that word is safe to
                # lowercase. Doing it unconditionally produced "In short, dr. Smith published the
                # results" — the abbreviation destroyed by the very transform meant to vary rhythm.
                # "In short, Dr. Smith published ..." is correct English; nothing needs demoting.
                if _safe_to_lowercase(first_word, " ".join(sentences)):
                    s = f"{random.choice(openers)} {s[0].lower() + s[1:]}"
                else:
                    s = f"{random.choice(openers)} {s}"
        out.append(s)
    return out


_CONJ = ("and", "but", "which", "because", "so", "while", "although", "though", "since")


def _cv(lengths: list[int]) -> float:
    if len(lengths) < 2:
        return 0.0
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return 0.0
    var = sum((x - mean) ** 2 for x in lengths) / len(lengths)
    return (var**0.5) / mean


def _split_one(s: str) -> list[str] | None:
    """Split one long sentence into two at a comma or coordinating conjunction near the midpoint.
    Redistributes words only — no content added. Returns [first, second] or None if no clean split."""
    words = s.split()
    if len(words) < 12:
        return None
    mid = len(words) // 2
    best: int | None = None
    for off in range(mid):  # nearest comma to the midpoint
        for pos in (mid + off, mid - off):
            if 0 < pos < len(words) - 1 and words[pos].endswith(","):
                best = pos + 1
                break
        if best is not None:
            break
    if best is None:  # else a coordinating conjunction
        for off in range(mid):
            for pos in (mid + off, mid - off):
                if 0 < pos < len(words) - 1 and words[pos].lower() in _CONJ:
                    best = pos
                    break
            if best is not None:
                break
    if best is None:
        return None
    first = " ".join(words[:best]).rstrip(",")
    tail = words[best:]
    if tail and tail[0].lower() in _CONJ:  # drop a leading conjunction for a clean second sentence
        tail = tail[1:]
    if not first or not tail:
        return None
    second = " ".join(tail)
    second = second[0].upper() + second[1:]
    if not first.endswith((".", "!", "?")):
        first += "."
    if not second.endswith((".", "!", "?")):
        second += "."
    return [first, second]


def _merge_pair(sents: list[str], j: int) -> list[str]:
    """Merge sentences j and j+1 into one compound sentence, or leave them if that is unsafe."""
    a = sents[j].rstrip(".!?")
    b = _LEADING_MARKER_RE.sub("", sents[j + 1].strip(), count=1)
    # Same rule as _merge_sentences: only demote a sentence to a clause when its opening word can
    # be lowercased without mangling a name or an acronym.
    if not b or not (b[0].islower() or _safe_to_lowercase(b.split()[0], " ".join(sents))):
        return sents
    b = b[0].lower() + b[1:] if b[0].isupper() else b
    return sents[:j] + [f"{a}, and {b}"] + sents[j + 2 :]


def _target_burstiness(sentences: list[str], target_cv: float = 0.45, max_moves: int = 12) -> list[str]:
    """Raise sentence-length variance toward the human range (CV ~0.45-0.55; AI sits ~0.3).

    The single most reliable human/AI stylometric differentiator (research: human academic std ~8
    words vs AI ~4-5). Greedy hill-climb: each round it tries splitting the longest sentence and
    merging the lowest-combined-length adjacent pair, and keeps whichever move raises CV the most.
    Only redistributes existing words — no content added/removed — so meaning is preserved.
    """
    sents = list(sentences)
    for _ in range(max_moves):
        lengths = [len(s.split()) for s in sents]
        cur_cv = _cv(lengths)
        if len(sents) < 2 or cur_cv >= target_cv:
            break

        candidates: list[tuple[float, list[str]]] = []

        # Candidate A: split the longest sentence.
        li = max(range(len(sents)), key=lambda i: lengths[i])
        if lengths[li] >= 14:
            parts = _split_one(sents[li])
            if parts:
                cand = sents[:li] + parts + sents[li + 1 :]
                candidates.append((_cv([len(s.split()) for s in cand]), cand))

        # Candidate B: merge the adjacent pair with the smallest combined length (<=45 words).
        if len(sents) >= 2:
            j = min(range(len(sents) - 1), key=lambda i: lengths[i] + lengths[i + 1])
            if lengths[j] + lengths[j + 1] <= 45:
                cand = _merge_pair(sents, j)
                candidates.append((_cv([len(s.split()) for s in cand]), cand))

        # Keep the move that raises CV the most; stop if none improves.
        candidates = [c for c in candidates if c[0] > cur_cv + 1e-6]
        if not candidates:
            break
        sents = max(candidates, key=lambda c: c[0])[1]
    return sents


# ---------------------------------------------------------------------------
# Main rewrite pipeline
# ---------------------------------------------------------------------------


def structural_rewrite(text: str, intensity: float = 0.5, seed: int | None = None) -> str:
    """Run the full structural rewrite pipeline. ``intensity`` in [0, 1].

    Higher intensity = more aggressive restructuring. Pass ``seed`` for reproducible
    output; leave as ``None`` (default) for varied results on each call.
    """
    if seed is not None:
        random.seed(seed)

    # 0. Strip low-content scaffolding openers (pure filler)
    text = _strip_filler_openers(text)

    # 1. Flatten participial trailers (always, these are pure tell)
    text = _flatten_participial_trailers(text)

    # 2. Flatten negated contrast
    text = _flatten_negated_contrast(text)

    # 3. Flatten inflated copula
    text = _flatten_copula(text)

    # 4. Flatten vague attribution
    text = _flatten_vague_attribution(text)

    # 5. Hedge removal — always, these are pure tell
    text = _HEDGE_RE.sub(r"\1", text)

    # 5b. Contraction injection — always (pure human-signal function-word shift)
    text = _inject_contractions(text)

    # 5c. Plain-register vocabulary — formal/AI-inflected words to the words people actually use.
    text = _plain_register(text, intensity=intensity)

    # 6. Semicolon → period (semiconductors are a tell)
    text = _SEMICOLON_RE.sub(". ", text)

    # 7. Sentence-level transforms — scaled by intensity.
    sents = _split_sentences(text)
    if len(sents) >= 2:
        # At intensity 1.0: strip ALL transitions, merge ~60% of pairs,
        # split ~50% of long sentences, vary ~60% of openers.
        strip_rate = min(1.0, 0.3 + intensity * 0.7)
        sents = _strip_transitions(sents, rate=strip_rate)

        merge_rate = min(0.7, intensity * 0.6)
        sents = _merge_sentences(sents, rate=merge_rate)

        split_rate = min(0.6, intensity * 0.5)
        sents = _split_long_sentences(sents, rate=split_rate)

        open_rate = min(0.6, intensity * 0.6)
        sents = _vary_openers(sents, rate=open_rate)

        # 8. Burstiness targeting — drive sentence-length variance toward the human range. The single
        # most reliable stylometric differentiator; only redistributes existing words (meaning-safe).
        sents = _target_burstiness(sents)

    result = " ".join(sents)

    return result


class StructuralRewriter(Rewriter):
    """No-LLM, no-key sentence-level rewriter. Always ``available()``.

    Transforms AI-sounding sentence structures: formulaic transitions, uniform
    sentence length, participial trailers, negated contrast, inflated copula.

    Combine with ``SurgicalRewriter`` (word-level synonym substitution) for the
    most effective free $0 path: structural first, then surgical polish.
    """

    name = "structural"

    def __init__(self, intensity: float = 0.7):
        self.intensity = intensity

    def available(self) -> bool:
        return True

    def rewrite(self, text: str, score_result: dict, threshold: float = 0.30) -> str:
        return structural_rewrite(text, intensity=self.intensity)
