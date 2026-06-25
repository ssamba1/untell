"""Preserve-lock: mask spans that must survive a rewrite verbatim, then restore them.

The humanize loop rewrites prose freely but must NOT alter citations, numeric facts, quoted
material, or named entities. We replace each such span with an opaque sentinel before the
rewrite and substitute the originals back afterward. This is the citation/meaning-integrity
differentiator (report gap #5).

API:
    lock(text)      -> (masked_text, mapping)   # mapping: sentinel -> original span
    restore(masked, mapping) -> text            # exact inverse of lock

Sentinels look like ``⟦HZ0007⟧`` — unlikely to occur in prose and stable across a rewrite as a
single unbreakable token (the skill instructs Claude to keep them intact). Entity masking uses
spaCy NER when installed; otherwise regex-only locking still covers citations/numbers/quotes.

Round-trip guarantee: ``restore(*lock(t)) == t`` for any ``t`` whose locked spans don't already
contain a sentinel (asserted in tests).
"""

from __future__ import annotations

import re

_SENTINEL_RE = re.compile(r"⟦HZ\d{4}⟧")

# Ordered, non-overlapping patterns. Earlier patterns win on overlap (handled by interval merge).
_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Bracketed numeric citations: [12], [3, 4], [1-5]
    ("citation", re.compile(r"\[\d+(?:\s*[-,]\s*\d+)*\]")),
    # Parenthetical author-year (APA/MLA): (Smith, 2020), (Smith & Lee, 2019, p. 4)
    ("citation", re.compile(r"\([A-Z][A-Za-z'’.-]+(?:\s+(?:&|and|et al\.?)\s*[A-Za-z'’.-]*)*,?\s*\d{4}[a-z]?(?:,\s*p+\.?\s*\d+)?\)")),
    # Narrative author-year: Smith (2020), Smith et al. (2019)
    ("citation", re.compile(r"[A-Z][A-Za-z'’.-]+(?:\s+et al\.?)?\s+\(\d{4}[a-z]?\)")),
    # DOIs and URLs
    ("url", re.compile(r"https?://\S+|doi:\s*\S+", re.IGNORECASE)),
    # Quoted spans (straight or curly double quotes)
    ("quote", re.compile(r"[\"“][^\"”]{1,400}[\"”]")),
    # Numbers with optional units/percent/currency/decimals/commas: 3.14, 1,000, 42%, $5, 10kg
    ("number", re.compile(r"[$€£]?\d[\d,]*(?:\.\d+)?\s*(?:%|kg|km|m|cm|mm|g|mol|°[CF]?|years?|days?)?")),
]


def _spacy_entity_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) spans for named entities via spaCy, or [] if spaCy is absent."""
    try:
        import spacy
    except Exception:
        return []
    try:
        nlp = _spacy_entity_spans._nlp  # type: ignore[attr-defined]
    except AttributeError:
        try:
            nlp = spacy.load("en_core_web_sm")
        except Exception:
            try:
                nlp = spacy.blank("en")  # no NER pipeline -> yields nothing, but stays safe
            except Exception:
                return []
        _spacy_entity_spans._nlp = nlp  # type: ignore[attr-defined]
    try:
        doc = nlp(text)
    except Exception:
        return []
    keep = {"PERSON", "ORG", "GPE", "LOC", "WORK_OF_ART", "LAW", "PRODUCT", "EVENT", "NORP", "FAC"}
    return [(e.start_char, e.end_char) for e in getattr(doc, "ents", []) if e.label_ in keep]


def _collect_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for _label, pat in _PATTERNS:
        for m in pat.finditer(text):
            if m.start() != m.end():
                spans.append((m.start(), m.end()))
    spans.extend(_spacy_entity_spans(text))
    return spans


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Sort and merge overlapping/adjacent spans so masks never collide."""
    if not spans:
        return []
    spans = sorted(set(spans))
    merged = [spans[0]]
    for start, end in spans[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:  # overlap or touch
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def lock(text: str) -> tuple[str, dict[str, str]]:
    """Replace protected spans with sentinels. Returns (masked_text, mapping)."""
    spans = _merge(_collect_spans(text))
    mapping: dict[str, str] = {}
    out: list[str] = []
    cursor = 0
    for i, (start, end) in enumerate(spans):
        out.append(text[cursor:start])
        sentinel = f"⟦HZ{i:04d}⟧"
        mapping[sentinel] = text[start:end]
        out.append(sentinel)
        cursor = end
    out.append(text[cursor:])
    return "".join(out), mapping


def restore(masked: str, mapping: dict[str, str]) -> str:
    """Inverse of :func:`lock` — substitute each sentinel with its original span."""
    def _sub(m: re.Match) -> str:
        return mapping.get(m.group(0), m.group(0))

    return _SENTINEL_RE.sub(_sub, masked)


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m humanize.scripts.preserve "text"`` prints masked text + mapping JSON."""
    import json
    import sys

    args = argv if argv is not None else sys.argv[1:]
    text = args[0] if args else sys.stdin.read()
    masked, mapping = lock(text)
    print(json.dumps({"masked": masked, "mapping": mapping}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
