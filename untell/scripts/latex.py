"""LaTeX support: prose extraction for scoring, and citation verification.

Two problems that only appear on real `.tex` input, both found by running the tool on a
four-paragraph paper rather than on a paragraph of prose.

**Scoring the source under-reads the prose.** The loop scores the RESTORED text, which is correct
in general — that is what a detector sees. But for markup the restored text is the *source*, and
nobody is judged on source. MEASURED on a four-paragraph paper: the raw `.tex` scores **0.0949**
while the prose inside it scores **0.6261**. The loop read 0.09, concluded the text already passed,
and returned the document untouched. A user with an AI-written paper got a no-op and a green
verdict.

**A rewrite can silently break the bibliography.** Citation commands are preserve-locked, so a key
cannot be *edited* — but a whole sentence can be dropped or merged, and with it a `\\cite`. The
document still compiles; the claim that needed the source is simply no longer attributed. Nothing
in the loop was checking, and this is the one repository whose stated niche is documents where that
matters.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Signals that a string is LaTeX rather than prose that happens to contain a backslash. Two of
# these must appear: a lone `\alpha` in an otherwise plain paragraph is not a document.
_LATEX_SIGNALS = (
    re.compile(r"\\documentclass\b"),
    re.compile(r"\\begin\{document\}"),
    re.compile(r"\\(?:section|subsection|chapter|paragraph)\*?\{"),
    re.compile(r"\\begin\{(?:abstract|figure|table|equation|align|theorem)\*?\}"),
    re.compile(r"\\(?:cite[a-zA-Z]*|ref|label)\{"),
    re.compile(r"\\usepackage\b"),
)

# THE list of environments whose content must not be rewritten. One definition, used twice:
# `preserve.lock` masks them so the rewriter cannot touch them, and `prose_only` drops them so the
# SCORE does not include prose the loop is unable to change.
#
# Those two had separate lists for about an hour, and in that hour `prose_only` scored the abstract
# and the theorem — text the loop is forbidden to edit — which is the same defect as scoring the
# masked string: optimising a number nothing can move. Four other duplicated lists in this
# repository have drifted, each caught only after it produced a visible bug, so this one is
# imported rather than copied.
LOCKED_ENVIRONMENTS = (
    "abstract",
    r"equation\*?", r"align\*?", r"gather\*?", r"multline\*?", r"eqnarray\*?",
    "displaymath", "math",
    r"figure\*?", r"table\*?", r"tabular\*?", "tabularx", "longtable", "wrapfigure", "subfigure",
    "theorem", "lemma", "corollary", "proposition", "definition", "proof", "remark", "example",
    "axiom",
    "verbatim", "lstlisting", "minted", "Verbatim", "alltt", r"algorithm\*?", "algorithmic",
    "thebibliography", "tikzpicture",
)
ENV_ALTERNATION = "|".join(LOCKED_ENVIRONMENTS)
_NON_PROSE_ENV = re.compile(
    r"\\begin\{(" + ENV_ALTERNATION + r")\}.*?\\end\{\1\}", re.DOTALL
)
_COMMENT = re.compile(r"(?<!\\)%.*?$", re.MULTILINE)
_MATH = re.compile(r"\$\$.+?\$\$|\\\[.+?\\\]|\$[^$\n]{1,200}\$", re.DOTALL)
# A command with a braced argument whose argument IS prose the reader sees (\textbf{...}) —
# unwrap it rather than dropping it, or the sentence loses words it actually contains.
_KEEP_ARG = re.compile(
    r"\\(?:textbf|textit|emph|texttt|textsc|underline|text|mbox|title|author)\{([^{}]*)\}"
)
_DROP_ARG = re.compile(r"\\[a-zA-Z@]+\*?(?:\[[^\]]*\])*\{[^{}]*\}")
_BARE_CMD = re.compile(r"\\[a-zA-Z@]+\*?")
_ENV_MARK = re.compile(r"\\(?:begin|end)\{[^}]*\}")

# `cite[a-zA-Z]*` matched only commands that START with "cite", which is natbib and APA.
# biblatex is the modern standard and puts the stem in the middle: \parencite,
# \textcite, \footcite, \autocite. Those returned NO keys, so `--against` reported
# "keeps every citation" on a rewrite that had destroyed all of them, and no key was ever
# checked against the .bib. `preserve.lock()` was never fooled — it masks LaTeX commands
# structurally and all three forms survive a rewrite byte-exact — so the byte-locking promise
# held while the REPORTING on it was blind.
#
# The starred forms (\citep*, \parencite*) failed for a second reason: the star sits between
# the command and its optional argument.
CITE = re.compile(r"\\(?:[a-zA-Z]*cite[a-zA-Z]*|nocite)\*?(?:\[[^\]]*\])*\{([^}]*)\}")
_BIB_ENTRY = re.compile(r"@\w+\s*\{\s*([^,\s}]+)", re.MULTILINE)


def is_latex(text: str) -> bool:
    """Does this look like a LaTeX document rather than prose containing a stray backslash?"""
    return sum(1 for p in _LATEX_SIGNALS if p.search(text)) >= 2


def prose_only(text: str) -> str:
    """What a reader of the compiled document actually reads.

    Used for SCORING, never for output — the loop still emits valid LaTeX. Detectors judge prose,
    and a `.tex` source is full of markup that dilutes every signal they measure.
    """
    out = _COMMENT.sub("", text)
    out = _NON_PROSE_ENV.sub(" ", out)
    out = _MATH.sub(" ", out)
    out = _ENV_MARK.sub(" ", out)
    # Unwrap before dropping, so \textbf{important} keeps the word "important".
    for _ in range(3):  # nested \textbf{\emph{x}} needs more than one pass
        new = _KEEP_ARG.sub(r"\1", out)
        if new == out:
            break
        out = new
    out = _DROP_ARG.sub(" ", out)
    out = _BARE_CMD.sub(" ", out)
    out = out.replace("{", " ").replace("}", " ").replace("~", " ")
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)
    return re.sub(r"[ \t]+", " ", out).strip()


def cite_keys(text: str) -> list[str]:
    """Every citation key referenced, in order, with duplicates preserved."""
    keys: list[str] = []
    for group in CITE.findall(text):
        keys.extend(k.strip() for k in group.split(",") if k.strip())
    return keys


def bib_keys(bib_text: str) -> set[str]:
    """Every entry key defined in a .bib file."""
    return {m.strip() for m in _BIB_ENTRY.findall(bib_text)}


def dropped_citations(source: str, rewritten: str) -> list[str]:
    """Keys the rewrite lost. A dropped citation still compiles and is still wrong.

    Counts multiplicity: a paper citing the same key twice and coming back with one is reported,
    because the second reference was attached to a claim that no longer has one.
    """
    from collections import Counter

    before, after = Counter(cite_keys(source)), Counter(cite_keys(rewritten))
    lost: list[str] = []
    for key, n in before.items():
        missing = n - after.get(key, 0)
        lost.extend([key] * missing)
    return sorted(lost)


def unresolved_citations(text: str, bib_text: str) -> list[str]:
    """Keys cited in the document that no .bib entry defines — an undefined reference at compile."""
    defined = bib_keys(bib_text)
    return sorted({k for k in cite_keys(text) if k not in defined})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="untell-latex",
        description=(
            "Inspect a LaTeX document the way the humanizer sees it: the prose a reader reads, "
            "and whether its citations survive."
        ),
    )
    p.add_argument("path", help="a .tex file")
    p.add_argument("--bib", help="a .bib file; every cited key must be defined in it")
    p.add_argument(
        "--against",
        help="a rewritten .tex to compare against PATH; reports any citation the rewrite lost",
    )
    p.add_argument("--prose", action="store_true", help="print the extracted prose and exit")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    src = Path(args.path)
    if not src.exists():
        print(f"no such file: {src}", file=sys.stderr)
        return 2
    text = src.read_text(encoding="utf-8")

    if args.prose:
        print(prose_only(text))
        return 0

    problems = 0
    keys = cite_keys(text)
    print(f"{src.name}: {len(keys)} citation references, {len(set(keys))} distinct")
    print(f"  prose extracted: {len(prose_only(text).split())} words of "
          f"{len(text.split())} in source")
    print(f"  looks like LaTeX: {is_latex(text)}")

    if args.bib:
        bib = Path(args.bib)
        if not bib.exists():
            print(f"no such file: {bib}", file=sys.stderr)
            return 2
        unresolved = unresolved_citations(text, bib.read_text(encoding="utf-8"))
        if unresolved:
            problems += len(unresolved)
            print(f"  UNRESOLVED against {bib.name}: {', '.join(unresolved)}")
        else:
            print(f"  every cited key is defined in {bib.name}")

    if args.against:
        other = Path(args.against)
        if not other.exists():
            print(f"no such file: {other}", file=sys.stderr)
            return 2
        lost = dropped_citations(text, other.read_text(encoding="utf-8"))
        if lost:
            problems += len(lost)
            print(f"  CITATIONS LOST in {other.name}: {', '.join(lost)}")
        else:
            print(f"  {other.name} keeps every citation")

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
