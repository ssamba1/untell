"""Explain WHY each span the preserve lock would freeze is locked.

The closed loop masks citations, numbers, quotes, code and every other protected span
before a rewrite, then restores them verbatim. A user who sees a span come back
unchanged has no way to ask *why* — the mask is opaque by design, and the machinery's
own comments name over-locking as the expensive failure mode ("a frozen span is prose
the rewriter cannot improve, silently, forever"). This module is the inspection
surface for that mask: given the same text the loop would lock, it reports every
locked span, the rule(s) that matched it, and why each rule exists.

    from untell.scripts.explain import explain_spans

    for row in explain_spans("See Smith (2020); it cost $500."):
        print(row["sentinel"], row["span"], row["rules"])

    # ⟦HZ0000⟧ (2020) ['citation']
    # ⟦HZ0001⟧ $500 ['number']

CLI: ``untell explain "text"`` prints a table; ``--json`` prints the machine-readable
list. The same call `lock()` makes — every span here is exactly what the rewriter
will be forbidden to touch — so ``explain`` and ``lock`` cannot disagree: the labeled
collection is defined once in ``preserve`` and both build on it, and the consistency
test pins the sentinel/span mapping of the two to be identical.

The rationale registry is itself checked: a test fails if any rule in ``_PATTERNS``
lacks a rationale, or if any rationale names no rule. Adding a pattern without
explaining it is the same drift this file exists to prevent, made visible instead of
silent.
"""

from __future__ import annotations

import json
import logging

# Run-as-file support (zero-dep lite tier): when this file is executed directly
# rather than imported as part of the `untell` package, put the directory that
# *contains* the package on sys.path so `import untell` resolves from any cwd.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

from untell.scripts.preserve import _collect_labeled_spans

logger = logging.getLogger(__name__)

# Why each rule exists. Every label used by a pattern in `preserve._PATTERNS` must
# appear here, and every key here must name a rule that exists — `test_explain.py`
# enforces both directions so a new pattern without a rationale fails the suite.
# The content is condensed from the MEASURED evidence recorded beside each pattern
# in preserve.py; the full measurements live there.
RATIONALES: dict[str, str] = {
    "sentinel": (
        "The input already contains a ⟦HZxxxx⟧ sentinel. Locking it first keeps "
        "lock() from reusing the token for a real span, which would corrupt the "
        "round-trip: restore() would then rewrite the user's literal token too."
    ),
    "code": (
        "Code is data, not prose: a rewrite that 'improves the flow' of a code "
        "block destroys it. Covers fenced and inline code, HTML <code>/<pre>/<kbd>/"
        "<samp>/<tt>/<var> tags, bare paths (src/main.py), callables (parse_json()), "
        "snake_case identifiers, long CLI flags (--tier) and SCREAMING_SNAKE "
        "environment variables. MEASURED: 12 of 12 HTML code spans were damaged "
        "before this rule existed."
    ),
    "latex_math": (
        "Inline and display math must survive byte-for-byte — renaming a variable "
        "in an equation is damage, not improvement. The rule is guarded so a "
        "currency '$' earlier in the sentence cannot pair with a math '$' and "
        "expose the equation. MEASURED before the guard: 'The budget was $500 while "
        "$E=mc^2$ is the formula.' locked '$500 while $' and left 'E=mc^2$' free."
    ),
    "latex_env": (
        "The CONTENT of maths, floats and captions, theorem-like blocks, verbatim, "
        "tabular and the abstract is data. Container environments whose content is "
        "the prose the user came here to humanize (document, itemize, quote, "
        "center) are NOT locked. MEASURED before the split: every environment was "
        "locked, so a four-paragraph paper masked to two sentinels and the loop "
        "returned the input unchanged."
    ),
    "latex_cite": (
        "Citation, reference and label commands — \\citep{...}, \\ref{...}, "
        "\\label{...} — must survive verbatim: a changed citation key or reference "
        "points at nothing. MEASURED before these rules: lock() protected 0 spans "
        "of a sentence containing \\citep, \\ref and inline math."
    ),
    "latex_cmd": (
        "Any other LaTeX command with a braced argument (\\textbf{...}, "
        "\\includegraphics{...}) or a bare command (\\LaTeX) is structure, not "
        "prose. The lookbehind keeps the rule off Windows paths, which are full of "
        "backslash-letter sequences."
    ),
    "citation": (
        "Citations are the headline promise: [12], (Smith, 2020), (see Smith 2019; "
        "Jones 2020, p. 4) and Smith (2020) must survive whole. MEASURED through "
        "the shipped loop before the multi-work forms were covered: 8 of 16 runs "
        "came back damaged — '(Smith, 2019; Jones, 2020)' became '(Smith, 2019. "
        "Jones, 2020)', a rewrite editing INSIDE the citation."
    ),
    "url": (
        "A URL or DOI is a locator, not prose: one altered character points at "
        "nothing, and readers copy these verbatim."
    ),
    "quote": (
        "Quoted material is someone else's words, in any quotation style — "
        "straight, curly-double, single and curly-single. A rewrite that edits a "
        "quotation falsifies the person quoted. MEASURED before the single-quote "
        "rule: 'single quotes' survived 0 of 2 runs while double and curly quotes "
        "survived 2 of 2."
    ),
    "email": (
        "An email address is a fact a rewrite must never 'tidy' — one changed "
        "character severs the contact."
    ),
    "version": (
        "Version strings and dependency pins (v1.2.3-rc4, untell==0.2.0, "
        "numpy>=1.24) — a version that reads as 1.2.3 and installs as something "
        "else is wrong in the way nobody catches by eye. MEASURED before this "
        "rule: 'untell==0.2.0' locked '0.2' and left '.0' rewritable."
    ),
    "path": (
        "File paths (C:\\Users\\me\\file.txt, src/main.py) are copied verbatim by "
        "readers; rewriting a directory or a filename silently breaks the "
        "reference. MEASURED before this rule: 'C:\\Users\\me\\file.txt' locked only "
        "the final component."
    ),
    "number": (
        "Numeric facts must survive: currencies, clock times with meridiem, "
        "fractions, comparisons (p<0.05), ranges (10-20), scientific notation, "
        "negatives and number+unit pairs (5 mg, 16 GB). MEASURED before the "
        "ordering was fixed, 7 of 28 fact types locked only PARTIALLY — the worst "
        "possible outcome, because a sentinel appears and the span looks protected "
        "while the rest stays mutable ('3.5%' locked '3.5' and left '%' free to "
        "become ' percent')."
    ),
    "date": (
        "Calendar dates: the month or weekday NAME carries as much of the fact as "
        "the digits. MEASURED before this rule: 'March 15, 2024' locked '15' and "
        "'2024' as separate spans and left 'March' freely rewritable to April."
    ),
    "dotted": (
        "Dotted identifiers — bare semantic versions (1.26.4), IPv4 addresses "
        "(192.168.1.24), section numbers (2.3.1), word.number identifiers "
        "(np.float64). The decimal rule stops at the second component, so without "
        "this rule '192.168.1.24' masked to '⟦HZ0000⟧.⟦HZ0001⟧' and a rewrite could "
        "turn 1.26.4 into 1.26.7 with every sentinel intact."
    ),
    "phone": (
        "Phone numbers in every format: a rewrite that changes one digit while the "
        "sentinel survives intact is the worst possible outcome for a contact "
        "fact."
    ),
    "coordinate": (
        "Latitude/longitude pairs — '37.7749° N, 122.4194° W', DMS '0°7′W', a leading "
        "N/S form — lock as one span. Before the rule the hemisphere letter and the "
        "DMS parts were free, so a rewriter could reassemble a location from its "
        "pieces and the fact would survive byte-for-byte while being wrong. The "
        "terminator is the hemisphere letter, not the punctuation, so a following "
        "sentence boundary still splits."
    ),
    "hexid": (
        "Hex literals and identifiers — 0xFF, \\x1B, URL percent-encoding, git "
        "short shas, MD5/SHA digests: one altered character makes them point at "
        "nothing. The long form requires a digit AND a letter so ordinary "
        "hex-shaped words ('defaced') stay rewritable; MEASURED over 240 real "
        "texts, 0 corpus locks from that shape."
    ),
    "ratio": (
        "Ratios and scales in words — '1 in 5', '4 out of 5', '3 per 100': both "
        "numbers AND the connective must move together, or the ratio inverts "
        "while looking protected."
    ),
    "reference": (
        "Numbered cross-references and legal citations — 'Section 3.2', '42 U.S.C. "
        "1983', '§ 5(a)'. MEASURED before this rule: 'Section 3.2' locked '3.2' "
        "alone, so the label could become 'Chapter'."
    ),
    "identifier": (
        "Alphanumeric identifiers — chemical formulae (H2O2), gene symbols "
        "(BRCA1), model and standard names (GPT4, ISO 9001), hex colours "
        "(#1a2b3c), and polarity-carrying forms (CD4+ / CD4-): the digits carry "
        "the meaning. A trailing +/- is part of the identifier, not punctuation — "
        "MEASURED: 'CD4+' masked to '⟦HZ0000⟧+' while 'CD8-' masked whole, so the "
        "two behaved differently inside one sentence."
    ),
    "entity": (
        "Named entities (people, organisations, places, works of art, laws, "
        "products) via spaCy NER when the model is installed. Single-token "
        "common-word persons ('Email', 'May', 'Will') are deliberately excluded — "
        "MEASURED on en_core_web_sm, capitalised common words were tagged PERSON, "
        "and freezing the verb 'Email' would remove it from the rewriter's reach "
        "forever."
    ),
}


def _merge_labeled(
    spans: list[tuple[str, int, int]],
) -> list[tuple[int, int, list[str]]]:
    """Merge labeled spans into (start, end, labels) with the SAME algorithm as lock().

    ``preserve._merge`` sorts by (start, end) and merges spans that overlap or
    touch, keeping the union. This mirrors that exactly — sort is non-decreasing in
    ``start`` regardless of the label tie-break, so the merged interval list is
    identical to the one ``lock()`` builds — while accumulating the labels of every
    contributor. The identity is pinned by a test: the sentinels and spans reported
    here must equal ``lock(text)``'s mapping byte for byte.
    """
    if not spans:
        return []
    # Dedupe exact (label, start, end) triples, then sort by POSITION with the
    # label as a tie-break. Sorting by label first would let a later span with an
    # earlier label sort ahead of an earlier span, and the union arithmetic below
    # corrupts the merged interval when processing order is not non-decreasing in
    # start — FOUND by the lock-consistency test, which is exactly why it exists.
    spans = sorted(set(spans), key=lambda t: (t[1], t[2], t[0]))
    merged: list[tuple[int, int, set[str]]] = [
        (spans[0][1], spans[0][2], {spans[0][0]})
    ]
    for label, start, end in spans[1:]:
        last_start, last_end, labels = merged[-1]
        if start <= last_end:  # overlap or touch — same rule as preserve._merge
            merged[-1] = (last_start, max(last_end, end), labels | {label})
        else:
            merged.append((start, end, {label}))
    return [(start, end, sorted(labels)) for start, end, labels in merged]


def explain_spans(text: str) -> list[dict]:
    """Every span ``lock()`` would freeze, with the rule(s) that locked it and why.

    Returns one dict per merged span, in sentinel order:

    ``sentinel``  the ⟦HZxxxx⟧ token ``lock()`` substitutes for this span
    ``span``      the original text that will survive verbatim
    ``start``/``end``  character offsets in ``text``
    ``rules``     sorted labels of every pattern that matched (a merged span can
                  have several — e.g. a version string inside a citation)
    ``rationale`` the joined why-this-must-survive text for those rules

    Deterministic: the same input returns the same list in the same order, which is
    what the reproducibility of the lock itself depends on.
    """
    merged = _merge_labeled(_collect_labeled_spans(text))
    rows: list[dict] = []
    for i, (start, end, labels) in enumerate(merged):
        span = text[start:end]
        rows.append(
            {
                "sentinel": f"⟦HZ{i:04d}⟧",
                "span": span,
                "start": start,
                "end": end,
                "rules": labels,
                "rationale": " ".join(RATIONALES.get(label, "") for label in labels).strip(),
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    """CLI: explain the preserve lock on text, from argv, --file or stdin.

    ``untell explain "See Smith (2020); the fix ships in v1.2.3-rc4."``
    ``untell explain --file draft.txt --json``
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    import argparse

    from untell.scripts.io_utils import configure_utf8_io, read_file_or_exit, read_stdin_or_none

    configure_utf8_io()  # UTF-8 stdin/stdout/stderr (Windows defaults to cp1252)

    parser = argparse.ArgumentParser(
        prog="untell-explain",
        description="Show every span the preserve lock would freeze, which rule "
        "locked it, and why the rule exists.",
    )
    parser.add_argument("text", nargs="?", help="text whose locked spans to explain")
    parser.add_argument("--file", "-f", help="read the text from a file")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    if args.file:
        text = read_file_or_exit(args.file)
    elif args.text:
        text = args.text
    else:
        piped = read_stdin_or_none()
        if piped is None:
            print(json.dumps({"error": "no input: pass text, --file PATH, or pipe to stdin"}))
            return 2
        text = piped
    if not text.strip():
        print(json.dumps({"error": "empty input"}))
        return 2

    rows = explain_spans(text)
    if args.json:
        print(json.dumps(rows, ensure_ascii=True, indent=2))
        return 0

    if not rows:
        print("No spans locked — the rewriter may touch every word of this text.")
        return 0

    for i, row in enumerate(rows):
        rules = ", ".join(row["rules"])
        print(f"[{i}] {rules}")
        print(f"    {row['span']}")
        if row["rationale"]:
            print(f"    why: {row['rationale']}")
        print()
    print(f"{len(rows)} span(s) locked — each will survive a rewrite verbatim. "
          "Run with --json for the machine-readable list.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
