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

# ---------------------------------------------------------------------------
# Word-level patterns (additional to SurgicalRewriter's synonym map)
# ---------------------------------------------------------------------------

# High-frequency AI hedging — strip the second word, keep the modal.
_HEDGE_RE = re.compile(
    r"\b(could|may|might|would|can)\s+(potentially|eventually|possibly|likely|arguably)\b",
    re.IGNORECASE,
)

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
            if first_word not in subjects and first_word[0].isupper() if first_word else False:
                # Add a varied opener
                s = f"{random.choice(openers)} {s[0].lower() + s[1:]}"
        out.append(s)
    return out


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
