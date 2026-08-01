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

# Inflated copula: "serves as", "marks", "represents", "boasts" used for plain "is"/"has".
_INFLATED_COPULA_RE = re.compile(
    r"\b(serves as|marks|represents|boasts|epitomizes|exemplifies)\b",
    re.IGNORECASE,
)

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
    r"(?:^|(?<=[.!?]\s))\s*"
    r"(?:it (?:is|'s) (?:worth (?:noting|mentioning)|important to (?:note|mention|highlight|remember)) that"
    r"|it should be noted that"
    r"|one (?:thing|point) (?:to note|worth noting) is that"
    r"|(?:it is|there is) no (?:doubt|denying) that"
    r"|needless to say,?"
    r"|as (?:we|previously) (?:noted|mentioned|discussed),?)\s+",
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


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text.strip()) if s.strip()]


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
            if b:
                b = b.strip(".")
                b = b[0].lower() + b[1:] if b and b[0].isupper() else b
                connectors = [", and ", ", but ", ", while ", "; ", ", though "]
                conn = random.choice(connectors)
                out.append(f"{a}{conn}{b}.")
            else:
                out.append(sentences[i])
            i += 2
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
        rest = m.group(0)
        # Extract the object after the verb: ", underscoring its importance." → " its importance."
        after = rest[len(f", {verb_ing}"):]  # " its importance." — note the leading space
        after = after.strip(".")              # " its importance" — keep leading space
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
    out = _FILLER_OPENER_RE.sub("", text)
    return re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), out)


def _flatten_copula(text: str) -> str:
    """Replace 'serves as', 'boasts', etc. with plain 'is'."""
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
                # Add a varied opener
                s = f"{random.choice(openers)} {s[0].lower() + s[1:]}"
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
    """Merge sentences j and j+1 into one compound sentence."""
    a = sents[j].rstrip(".!?")
    b = sents[j + 1].strip()
    b = b[0].lower() + b[1:] if b and b[0].isupper() else b
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
