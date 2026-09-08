"""Score ANOTHER humanizer's published outputs with untell's own gates.

Every comparison this repository has published against a competing humanizer was made by reading
their paper. ``docs/why-best-open-repo.md`` ranks `chengez/Adversarial-Paraphrasing` above us on
evasion and below us on completeness, and the only mention of that repo anywhere in the tree is
``tests/test_docs_claims.py`` asserting that the *documentation* names it. Nobody had run their
code, or their outputs, through anything here.

This harness closes that. It takes a source corpus and a competitor's rewrite of the same corpus,
aligned row for row, and reports what untell's gates say about the rewrite:

  * **numerals kept** (``scripts/numerals.numbers_kept``) — every quantity the source stated still
    present, as a numeral or its English word. Pure stdlib.
  * **certainty kept** (``scripts/hedges.certainty_kept``) — no hedge class dropped, no causal
    upgrade, no intensifier the source never used. Pure stdlib.
  * **AI tells** (``scripts/tells.score_tells``) — detector-independent naturalness, per 100 words.
  * **token overlap** (``scripts/quality``) — reported ONLY with the metric's own confidence, which
    on the stdlib path is ``low``. It is advisory, never a meaning verdict; see below.
  * **detector P(AI)** (``scripts/score.score_text``) — optional, off by default because it costs a
    model load per row.

**What this harness will not do is claim a meaning verdict it cannot compute.** untell's real
meaning gate is entailment + role-swap + similarity together (``references/thresholds.md``), and
the token-overlap fallback is documented there as advisory — "it cannot actually judge meaning".
When entailment or roles are unavailable, that is reported in ``gates_unavailable`` and the meaning
columns are absent rather than approximated. A harness that quietly substituted the weak metric and
published the number would be committing the exact error this repository exists to measure.

    # convert the competitor's output to jsonl first (one {"text": ...} per line, row-aligned)
    untell-head-to-head --source src.jsonl --rewrite theirs.jsonl --label adv_radar
    untell-head-to-head --source src.jsonl --rewrite theirs.jsonl --n 0 --json
"""

from __future__ import annotations

import argparse
import json
import statistics

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

from untell.scripts import entailment, quality, roles
from untell.scripts.hedges import certainty_kept
from untell.scripts.numerals import missing_numbers
from untell.scripts.tells import score_tells

DEFAULT_N = 500


def load_jsonl(path: str, field: str = "text") -> list[str]:
    """Read one document per line. A line that is not JSON is taken as the document itself."""
    out: list[str] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                out.append(line)
                continue
            out.append(obj[field] if isinstance(obj, dict) else str(obj))
    return out


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def compare(
    sources: list[str],
    rewrites: list[str],
    *,
    label: str = "rewrite",
    tier: str | None = None,
) -> dict:
    """Score ``rewrites`` against ``sources`` row for row.

    Returns per-arm rates plus the list of gates that could not run. ``tier`` enables the detector
    columns; leave it ``None`` to skip the model load entirely.
    """
    if len(sources) != len(rewrites):
        raise ValueError(
            f"row counts differ: {len(sources)} sources against {len(rewrites)} rewrites — "
            "this harness compares row i to row i and cannot align them itself"
        )
    if not sources:
        raise ValueError("nothing to compare: the corpus is empty")

    gates_run = ["numerals", "certainty", "tells", "token_overlap"]
    gates_unavailable = []
    if not entailment.available():
        gates_unavailable.append("entailment (needs .[full]; NO meaning verdict is reported)")
    if not roles.available():
        gates_unavailable.append("roles (needs spaCy; NO predicate-argument verdict is reported)")

    # A rewrite with no letters in it evades every detector ever built, and scores a perfect zero
    # on the tell catalogue because none of the patterns can apply. Counting those rows as gate
    # failures would overstate the competitor's damage; counting them as successes would overstate
    # its evasion. They are excluded from the rates and reported as their own number, because "the
    # method returned nothing for this document" is a result about the method, not a missing value.
    kept = [(s, o) for s, o in zip(sources, rewrites) if any(c.isalpha() for c in o)]
    degenerate = len(sources) - len(kept)
    if not kept:
        raise ValueError("every rewrite is empty or has no letters — nothing to score")
    sources = [s for s, _ in kept]
    rewrites = [o for _, o in kept]

    numerals_ok = certainty_ok = both_ok = 0
    dropped: list[list[str]] = []
    overlaps: list[float] = []
    tells_src: list[float] = []
    tells_out: list[float] = []
    pre: list[float] = []
    post: list[float] = []

    score_text = None
    if tier:
        from untell.scripts.score import score_text as _score_text

        score_text = _score_text
        gates_run.append(f"detector({tier})")

    for src, out in zip(sources, rewrites):
        missing = missing_numbers(src, out)
        n_ok = not missing
        c_ok = certainty_kept(src, out)
        numerals_ok += n_ok
        certainty_ok += c_ok
        both_ok += n_ok and c_ok
        if missing:
            dropped.append(missing)
        overlaps.append(quality.token_overlap(src, out))
        tells_src.append(score_tells(src)["tells_per_100w"])
        tells_out.append(score_tells(out)["tells_per_100w"])
        if score_text is not None:
            pre.append(score_text(src, tier=tier)["max"])
            post.append(score_text(out, tier=tier)["max"])

    n = len(sources)
    return {
        "label": label,
        "n": n,
        "degenerate_rewrites": degenerate,
        "numerals_kept_rate": numerals_ok / n,
        "certainty_kept_rate": certainty_ok / n,
        "both_kept_rate": both_ok / n,
        "documents_dropping_a_number": n - numerals_ok,
        "numbers_dropped_total": sum(len(d) for d in dropped),
        "token_overlap_mean": _mean(overlaps),
        "token_overlap_metric": quality.method(),
        "token_overlap_confidence": quality.confidence(),
        "tells_per_100w_source": _mean(tells_src),
        "tells_per_100w_rewrite": _mean(tells_out),
        "detector_pre": _mean(pre),
        "detector_post": _mean(post),
        "gates_run": gates_run,
        "gates_unavailable": gates_unavailable,
    }


def render(result: dict) -> str:
    """One arm as a human-readable block, caveats included rather than appended."""
    lines = [
        f"{result['label']}  (n={result['n']}"
        + (f", {result['degenerate_rewrites']} empty rewrites excluded" if result["degenerate_rewrites"] else "")
        + ")",
        f"  numerals kept        {result['numerals_kept_rate']:.1%}"
        f"   ({result['documents_dropping_a_number']} documents dropped"
        f" {result['numbers_dropped_total']} numbers)",
        f"  certainty kept       {result['certainty_kept_rate']:.1%}",
        f"  both kept            {result['both_kept_rate']:.1%}",
        f"  tells / 100w         {result['tells_per_100w_source']:.2f}"
        f" -> {result['tells_per_100w_rewrite']:.2f}",
        f"  token overlap        {result['token_overlap_mean']:.3f}"
        f"   [{result['token_overlap_metric']}, confidence"
        f" {result['token_overlap_confidence']} — advisory, NOT a meaning verdict]",
    ]
    if result["detector_pre"] is not None:
        lines.append(
            f"  detector max P(AI)   {result['detector_pre']:.4f}"
            f" -> {result['detector_post']:.4f}"
        )
    for gate in result["gates_unavailable"]:
        lines.append(f"  NOT RUN: {gate}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="untell-head-to-head", description=__doc__)
    parser.add_argument("--source", "-s", required=True, help="source corpus (jsonl)")
    parser.add_argument("--rewrite", "-r", required=True, help="competitor rewrite (jsonl)")
    parser.add_argument("--label", "-l", default="rewrite")
    parser.add_argument("--field", default="text", help="jsonl field holding the document")
    parser.add_argument(
        "--n", type=int, default=DEFAULT_N, help="rows to score; 0 scores the whole corpus"
    )
    parser.add_argument(
        "--tier",
        default=None,
        choices=["lite", "full", "heavy"],
        help="also score the detector ensemble (costs a model load per row)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    sources = load_jsonl(args.source, args.field)
    rewrites = load_jsonl(args.rewrite, args.field)
    if args.n:
        sources, rewrites = sources[: args.n], rewrites[: args.n]

    try:
        result = compare(sources, rewrites, label=args.label, tier=args.tier)
    except ValueError as exc:
        print(f"untell-head-to-head: {exc}")
        return 2

    print(json.dumps(result, indent=2) if args.json else render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
