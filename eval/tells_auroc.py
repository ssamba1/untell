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
import re
import sys

from untell.scripts.tells import score_tells

# Cannot fire without line structure.
LAYOUT_CATEGORIES = frozenset({"markdown_artifact", "title_case_heading", "diff_anchored"})

_WHITESPACE_RUN = re.compile(r"\s+")


def collapse_layout(text: str) -> str:
    return _WHITESPACE_RUN.sub(" ", text).strip()


def auroc(ai: list[float], human: list[float]) -> float | None:
    """P(a random AI text scores above a random human one), ties as half."""
    if not ai or not human:
        return None
    return sum((a > h) + 0.5 * (a == h) for a in ai for h in human) / (len(ai) * len(human))


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

    m = measure(pairs)
    print(json.dumps({"dataset": args.dataset, **m}, indent=2) if args.json else render(args.dataset, m))
    return 0


if __name__ == "__main__":
    sys.exit(main())
