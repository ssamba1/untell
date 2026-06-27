"""Preserve-lock: mask spans that must survive a rewrite verbatim, then restore them.

The untell loop rewrites prose freely but must NOT alter citations, numeric facts, quoted
material, or named entities. We replace each such span with an opaque sentinel before the
rewrite and substitute the originals back afterward. This is the citation/meaning-integrity
differentiator (report gap #5).

API:
    lock(text)      -> (masked_text, mapping)   # mapping: sentinel -> original span
    restore(masked, mapping) -> text            # exact inverse of lock

Sentinels look like ``⟦HZ0007⟧`` — unlikely to occur in prose and stable across a rewrite as a
single unbreakable token (the skill instructs Claude to keep them intact). Entity masking uses
spaCy NER when installed; otherwise regex-only locking still covers citations/numbers/quotes.

Round-trip guarantee: ``restore(*lock(t)) == t`` for any text ``t`` — including text that already
contains literal ``⟦HZxxxx⟧`` sentinels, which are themselves locked so they survive a rewrite
verbatim instead of being rewritten by ``restore`` (asserted in tests).
"""

from __future__ import annotations

import re

# 4-OR-MORE digits: lock() numbers sentinels with f"⟦HZ{i:04d}⟧" (minimum width 4), which overflows
# to 5 digits past 9999 locked spans. Matching exactly \d{4} would make restore()/find_sentinels miss
# those, silently dropping the locked citation/fact on restore — so the round-trip must accept \d{4,}.
_SENTINEL_RE = re.compile(r"⟦HZ\d{4,}⟧")

# Ordered, non-overlapping patterns. Earlier patterns win on overlap (handled by interval merge).
_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Sentinel literals already present in the INPUT must themselves be locked. Otherwise lock()
    # may reuse the same ⟦HZxxxx⟧ token for a real span, and restore() would then rewrite the
    # user's literal token too — corrupting the round-trip. Lock them first so each maps uniquely.
    ("sentinel", _SENTINEL_RE),
    # Bracketed numeric citations: [12], [3, 4], [1-5]
    ("citation", re.compile(r"\[\d+(?:\s*[-,]\s*\d+)*\]")),
    # Parenthetical author-year (APA/MLA): (Smith, 2020), (Smith & Lee, 2019, p. 4)
    ("citation", re.compile(r"\([A-Z][A-Za-z'’.-]+(?:\s+(?:&|and|et al\.?)\s*[A-Za-z'’.-]*)*,?\s*\d{4}[a-z]?(?:,\s*pp?\.?\s*\d+)?\)")),
    # Narrative author-year: Smith (2020), Smith et al. (2019)
    ("citation", re.compile(r"[A-Z][A-Za-z'’.-]+(?:\s+et al\.?)?\s+\(\d{4}[a-z]?\)")),
    # DOIs and URLs
    ("url", re.compile(r"https?://\S+|doi:\s*\S+", re.IGNORECASE)),
    # Quoted spans (straight or curly double quotes)
    ("quote", re.compile(r"[\"“][^\"”]{1,400}[\"”]")),
    # Significant numbers only — avoid locking bare single digits ("5 days" locks via the unit, but
    # a lone "5" does not). Matches currency, decimals, comma-grouped thousands, number+unit, and
    # integers of 2+ digits: $5, 3.14, 1,000, 42%, 10kg, 2020.
    (
        "number",
        re.compile(
            r"[$€£]\s?\d[\d,]*(?:\.\d+)?"  # currency
            r"|\b\d[\d,]*\.\d+\b"  # decimals
            r"|\b\d{1,3}(?:,\d{3})+\b"  # comma-grouped thousands
            r"|\b\d+\s*(?:%|kg|km|cm|mm|mol|°[CF]?|years?|days?|hours?|minutes?)\b"  # number + unit
            r"|\b\d{2,}\b"  # standalone integers of 2+ digits
        ),
    ),
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


def find_sentinels(text: str) -> set[str]:
    """Return the set of sentinel tokens (``⟦HZxxxx⟧``) present in ``text``.

    Used by the loop to mechanically enforce the lock: a rewrite is only accepted if it still
    contains *exactly* the sentinels it was given — neither dropping one (which would silently
    lose a locked citation/number/fact on restore) nor inventing one.
    """
    return set(_SENTINEL_RE.findall(text))


def main(argv: list[str] | None = None) -> int:
    """CLI for lock (default) and restore.

    Lock:    ``python -m untell.scripts.preserve "text"`` -> JSON {masked, mapping}
    Restore: ``python -m untell.scripts.preserve --restore --mapping '<json>' "masked text"``
             (or ``--mapping-file path.json``) -> the restored text
    """
    import argparse
    import json
    import sys

    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()  # UTF-8 stdin/stdout/stderr (Windows defaults to cp1252)

    parser = argparse.ArgumentParser(prog="untell.scripts.preserve")
    parser.add_argument("text", nargs="?", help="text to lock, or masked text to restore")
    parser.add_argument("--restore", action="store_true", help="restore sentinels using --mapping")
    parser.add_argument("--mapping", help="JSON object {sentinel: original} for --restore")
    parser.add_argument("--mapping-file", help="path to a JSON mapping file for --restore")
    args = parser.parse_args(argv)

    text = args.text if args.text is not None else sys.stdin.read()

    if args.restore:
        mapping: dict[str, str] = {}
        if args.mapping_file:
            with open(args.mapping_file, encoding="utf-8") as fh:
                mapping = json.load(fh)
        elif args.mapping:
            mapping = json.loads(args.mapping)
        missing = set(mapping) - find_sentinels(text)
        if missing:  # a locked span was dropped during rewriting — make it loud, don't lose it silently
            print(
                f"[preserve] WARNING: {len(missing)} locked span(s) are missing from the text and will "
                f"NOT appear in the output (dropped during rewriting): {', '.join(sorted(missing))}",
                file=sys.stderr,
            )
        print(restore(text, mapping))
        return 0

    masked, mapping = lock(text)
    # ensure_ascii=True so the U+27E6 sentinels survive a non-UTF-8 (Windows cp1252) stdout;
    # they decode back to the real characters when the skill json-parses this output.
    print(json.dumps({"masked": masked, "mapping": mapping}, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
