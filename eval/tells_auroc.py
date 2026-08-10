"""Separation of the tells catalogue on paired human/AI text, with layout controlled.

The detector ensemble has `eval/detector_audit.py`. The tells catalogue had nothing: its headline
figures lived only in a comment, were computed by hand, and went stale the moment a category was
added. The overall AUROC in `untell/scripts/tells.py` read 0.638 on RAID while the shipped catalogue
scored 0.9555, because the two repetition tells landed after the number was written and nothing
re-derived it. This module exists so that cannot happen quietly again.

    python -m eval.tells_auroc --dataset raid --pairs 200
    python -m eval.tells_auroc --dataset raid --pairs 200 --json

Layout is reported rather than silently removed, which is the opposite of the choice
`detector_audit` makes, and deliberately so. Three catalogue categories are line-anchored BY DESIGN
-- ``markdown_artifact``, ``title_case_heading`` and ``diff_anchored`` -- so collapsing whitespace
would not remove a bias, it would silence the tells those categories exist to carry. MEASURED at 200
pairs, collapsing layout moves the AUROC by +0.0000 on RAID, HC3 and MAGE alike: the three
categories fire on 0, 1 and 1 documents out of 200, so on these corpora there is nothing to remove.
``layout_delta`` is emitted every run so a corpus where that stops being true is visible.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys

from untell.scripts.tells import score_tells

# Cannot fire without line structure.
LAYOUT_CATEGORIES = frozenset({"markdown_artifact", "title_case_heading", "diff_anchored"})

# A 95% interval wider than this spans too much to act on. `inflated_copula` was published at
# precision 0.000 from a single firing, whose interval is [0.00, 0.79] -- consistent with the
# category being useless AND with it being one of the better ones.
UNINFORMATIVE_CI_WIDTH = 0.5

_WHITESPACE_RUN = re.compile(r"\s+")


def collapse_layout(text: str) -> str:
    return _WHITESPACE_RUN.sub(" ", text).strip()


def auroc(ai: list[float], human: list[float]) -> float | None:
    """P(a random AI text scores above a random human one), ties as half."""
    if not ai or not human:
        return None
    return sum((a > h) + 0.5 * (a == h) for a in ai for h in human) / (len(ai) * len(human))


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion.

    Wilson rather than the normal approximation because every interesting entry here is at or near
    0 or 1 with a single-digit denominator, which is exactly where the normal approximation returns
    a nonsense interval (or a width of zero).
    """
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def binom_two_sided(successes: int, n: int) -> float | None:
    """Two-sided exact binomial test against p=0.5 — "is this split further from even than chance".

    Exact rather than a normal approximation for the same reason as Wilson: n is single digits.
    Returns None for n=0. A first draft used ``0.5 ** n``, which is only the probability of EVERY
    firing landing on one class — it labelled a 3-vs-4 split as p=0.008 when the true answer is 1.0.
    """
    if n == 0:
        return None
    k = max(successes, n - successes)
    tail = sum(math.comb(n, i) for i in range(k, n + 1)) / (2**n)
    return round(min(1.0, 2 * tail), 4)


def precision_table(pairs: list[tuple[str, str]]) -> list[dict]:
    """Per-category P(text is AI | category fired), with the denominator and its interval.

    The denominator is what this exists to surface. A category's precision is quoted per *firing*,
    not per document scanned, and several categories fire fewer than ten times in 400 documents --
    at which point a headline like "0.000" is compatible with almost anything. Reporting n and a
    Wilson interval is the difference between "this pattern is useless" and "this pattern was
    barely observed".
    """
    human_hits: dict[str, int] = {}
    ai_hits: dict[str, int] = {}
    for human, ai in pairs:
        for k in score_tells(human)["by_category"]:
            human_hits[k] = human_hits.get(k, 0) + 1
        for k in score_tells(ai)["by_category"]:
            ai_hits[k] = ai_hits.get(k, 0) + 1

    rows = []
    for cat in sorted(set(human_hits) | set(ai_hits)):
        h, a = human_hits.get(cat, 0), ai_hits.get(cat, 0)
        n = h + a
        lo, hi = wilson(a, n)
        rows.append(
            {
                "category": cat,
                "human": h,
                "ai": a,
                "n": n,
                "precision": round(a / n, 3) if n else None,
                "ci_low": round(lo, 3),
                "ci_high": round(hi, 3),
                "ci_width": round(hi - lo, 3),
                # The read that survives a tiny n: the SIZE of the precision may be unpinnable
                # while its DIRECTION is not. em_dash fires 7 times across both corpora and all 7
                # land on human text -- p = 0.016, so "this leans human" is established even though
                # the interval on the rate itself spans [0.00, 0.35].
                "p_direction": binom_two_sided(max(h, a), n),
                "informative": (hi - lo) <= UNINFORMATIVE_CI_WIDTH,
            }
        )
    rows.sort(key=lambda r: (-(r["precision"] or 0), -r["n"]))
    return rows


def _rate(text: str, exclude: frozenset[str] = frozenset()) -> float:
    """Tells per 100 words, optionally dropping some categories from the numerator."""
    r = score_tells(text)
    words = max(int(r.get("words") or 0), 1)
    cats = r.get("by_category") or {}
    return 100 * sum(v for k, v in cats.items() if k not in exclude) / words


def measure(pairs: list[tuple[str, str]]) -> dict:
    human = [h for h, _ in pairs]
    ai = [a for _, a in pairs]

    hr = [_rate(t) for t in human]
    ar = [_rate(t) for t in ai]
    full = auroc(ar, hr)

    collapsed = auroc(
        [_rate(collapse_layout(t)) for t in ai], [_rate(collapse_layout(t)) for t in human]
    )
    prose_only = auroc(
        [_rate(t, LAYOUT_CATEGORIES) for t in ai], [_rate(t, LAYOUT_CATEGORIES) for t in human]
    )
    layout_fires = sum(
        1 for t in human + ai if LAYOUT_CATEGORIES & set(score_tells(t)["by_category"])
    )

    hm, am = sum(hr) / len(hr), sum(ar) / len(ar)
    return {
        "n_pairs": len(pairs),
        "auroc": round(full, 4),
        "human_mean": round(hm, 3),
        "ai_mean": round(am, 3),
        "gap": round(am - hm, 3),
        "auroc_layout_collapsed": round(collapsed, 4),
        "layout_delta": round(collapsed - full, 4),
        "auroc_without_layout_categories": round(prose_only, 4),
        "layout_categories_fire_on": layout_fires,
        "documents": len(pairs) * 2,
    }


def render(dataset: str, m: dict) -> str:
    lines = [
        f"tells catalogue separation — {dataset}, {m['n_pairs']} pairs",
        "",
        f"  AUROC                      {m['auroc']:.4f}",
        f"  tells/100w  human {m['human_mean']:.3f}   ai {m['ai_mean']:.3f}   gap {m['gap']:+.3f}",
        "",
        f"  layout collapsed           {m['auroc_layout_collapsed']:.4f}  ({m['layout_delta']:+.4f})",
        f"  without layout categories  {m['auroc_without_layout_categories']:.4f}",
        f"  layout categories fire on  {m['layout_categories_fire_on']}/{m['documents']} documents",
    ]
    if abs(m["layout_delta"]) >= 0.01:
        lines.append("")
        lines.append(
            "  NOTE: layout moves this measurement. Unlike the detector audit, layout is NOT "
            "collapsed here, because three categories are line-anchored by design — so decide "
            "whether that delta is a real formatting tell or the corpus's storage convention."
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dataset", default="raid", help="raid | hc3 | mage")
    ap.add_argument("--pairs", type=int, default=200)
    ap.add_argument("--min-words", type=int, default=60)
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--precision",
        action="store_true",
        help="per-category P(AI | fired), with the denominator and a 95%% Wilson interval",
    )
    args = ap.parse_args(argv)

    from eval.datasets import load_pairs

    pairs = load_pairs(args.dataset, args.pairs, args.min_words)
    if not pairs:
        print(
            json.dumps({"error": f"no pairs from {args.dataset}; pip install '.[eval]'"})
            if args.json
            else f"no pairs available from {args.dataset} — pip install '.[eval]'"
        )
        return 2

    if args.precision:
        rows = precision_table(pairs)
        if args.json:
            print(json.dumps({"dataset": args.dataset, "categories": rows}, indent=2))
        else:
            print(f"per-category precision — {args.dataset}, {len(pairs)} pairs\n")
            print(f"{'category':26} {'human':>6} {'ai':>4} {'n':>4} {'prec':>6}  {'95% CI':>14}  note")
            for r in rows:
                note = "" if r["informative"] else "too few firings to read"
                if not r["informative"] and r["p_direction"] and r["p_direction"] <= 0.05:
                    note = f"direction holds (p={r['p_direction']:.3f}), size does not"
                print(
                    f"{r['category']:26} {r['human']:>6} {r['ai']:>4} {r['n']:>4} "
                    f"{r['precision']:>6.3f}  [{r['ci_low']:.2f}, {r['ci_high']:.2f}]  {note}"
                )
        return 0

    m = measure(pairs)
    print(json.dumps({"dataset": args.dataset, **m}, indent=2) if args.json else render(args.dataset, m))
    return 0


if __name__ == "__main__":
    sys.exit(main())
