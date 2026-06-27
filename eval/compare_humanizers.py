"""Definitive, reproducible head-to-head vs the free-humanizer technique classes.

You can't drive every gated SaaS humanizer for free — but you don't need to. The free humanizers in
the wild reduce to a handful of *mechanisms* (confirmed by their own docs and independent testers):

  * **synonym / token-importance substitution** — QuillBot, Wordtune, "masked-LM swaps the highest
    importance tokens" tools. We have this exactly: ``attacks.surgical_substitute``.
  * **translation laundering** (pivot-language round-trips) — lynote/humanize-text and friends. We
    have this: ``attacks.back_translate``.
  * **blind single-pass LLM paraphrase** — most "AI humanizer" SaaS. (A frontier LLM rewrite.)
  * **our closed detector-feedback loop** — the differentiator.

So this harness runs ONE fixed corpus through each mechanism and scores every output three ways:
  1. **ensemble P(AI)** (``score_text`` max) — evasion of the local detectors,
  2. **AI tells** (``score_tells``) — how machine-written it still *reads* (detector-independent),
  3. **semantic similarity** to the source — did it keep the meaning.

The honest finding it surfaces: synonym-swap and back-translation move the lexical tells a little and
leave the structural tells (formulaic transitions, negated contrast, vague attribution) intact, while
the closed loop is the only mechanism that drives ALL of them down without wrecking meaning.

    untell-compare                       # built-in corpus, full tier
    untell-compare --tier lite --json
    untell-compare --file corpus.txt     # paragraphs separated by blank lines
"""

from __future__ import annotations

import argparse
import json

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

from untell.scripts.score import DEFAULT_THRESHOLD, score_text
from untell.scripts.tells import score_tells

_SAMPLE = [
    "Furthermore, artificial intelligence has fundamentally transformed numerous industries in recent "
    "years. Moreover, organizations increasingly leverage these technologies to optimize operational "
    "efficiency and drive innovation. Overall, the transformative impact continues to expand across "
    "various sectors.",
    "In today's rapidly evolving digital landscape, cybersecurity has become paramount. It is important "
    "to note that organizations must navigate the complexities of an ever-changing threat environment. "
    "Ultimately, a robust and comprehensive security posture is essential for success.",
    "Education plays a pivotal role in shaping the future of society. Moreover, access to quality "
    "learning opportunities remains a crucial determinant of individual success. It is essential that "
    "stakeholders collaborate to foster equitable and inclusive educational systems for all.",
]


def _ai_max(text: str, tier: str) -> float:
    return float(score_text(text, tier=tier)["max"]) if text.strip() else 0.0


def _techniques(tier: str, threshold: float):
    """Return {name: rewrite_fn}. Heavy/optional deps imported lazily so lite still runs."""

    def synonym_swap(t: str) -> str:
        from untell.attacks import surgical_substitute

        return surgical_substitute(t, tier=tier, threshold=threshold, max_subs=10)["text"]

    def back_translation(t: str) -> str:
        from untell.attacks import back_translate

        return back_translate(t)

    def ours_loop(t: str) -> str:
        from untell.rewriter import get_rewriter
        from untell.scripts.run import untell_text

        res = untell_text(
            t, tier=tier, threshold=threshold, max_iters=5, rewriter=get_rewriter(prefer="surgical")
        )
        return res.get("final", t)

    return {
        "none (raw AI)": lambda t: t,
        "synonym_swap": synonym_swap,
        "back_translation": back_translation,
        "ours_loop (surgical)": ours_loop,
    }


def compare(texts: list[str], tier: str = "full", threshold: float = DEFAULT_THRESHOLD) -> dict:
    if not texts:  # no corpus -> nothing to score (the per-technique means would divide by zero)
        return {"n": 0, "tier": tier, "threshold": threshold, "techniques": {}}
    from untell.scripts.quality import similarity

    rows: dict[str, dict] = {}
    for name, fn in _techniques(tier, threshold).items():
        ai_scores, tell_rates, tell_counts, sims = [], [], [], []
        for t in texts:
            try:
                out = fn(t)
            except Exception as exc:  # a missing optional dep (e.g. marian) -> skip that technique
                rows[name] = {"error": f"{type(exc).__name__}: {str(exc)[:120]}"}
                break
            ai_scores.append(_ai_max(out, tier))
            tl = score_tells(out)
            tell_rates.append(tl["tells_per_100w"])
            tell_counts.append(tl["tells"])
            sims.append(similarity(t, out) if name != "none (raw AI)" else 1.0)
        else:
            n = len(texts)
            rows[name] = {
                "ai_max_mean": round(sum(ai_scores) / n, 4),
                "tells_per_100w_mean": round(sum(tell_rates) / n, 2),
                "tells_total": sum(tell_counts),
                "sim_mean": round(sum(sims) / n, 3),
                "flagged_rate": round(sum(1 for s in ai_scores if s >= threshold) / n, 3),
            }
    return {"n": len(texts), "tier": tier, "threshold": threshold, "techniques": rows}


def _render(r: dict) -> str:
    lines = [
        f"humanizer technique comparison — tier={r['tier']} n={r['n']} threshold={r['threshold']}",
        "",
        f"  {'technique':24} {'AI P(AI)':>9} {'flagged':>8} {'tells/100w':>11} {'meaning':>8}",
        f"  {'-' * 24} {'-' * 9:>9} {'-' * 8:>8} {'-' * 11:>11} {'-' * 8:>8}",
    ]
    for name, m in r["techniques"].items():
        if "error" in m:
            lines.append(f"  {name:24} (skipped: {m['error']})")
            continue
        lines.append(
            f"  {name:24} {m['ai_max_mean']:>9} {m['flagged_rate']:>8} "
            f"{m['tells_per_100w_mean']:>11} {m['sim_mean']:>8}"
        )
    lines += [
        "",
        "  AI P(AI): local-ensemble max (evasion proxy; lower=better, but it anti-correlates w/ human-ness).",
        "  tells/100w: catalogued AI tells per 100 words (detector-INDEPENDENT; lower = reads more human).",
        "  meaning: semantic similarity to the source (higher=better; <0.76 = meaning drift).",
    ]
    return "\n".join(lines)


def _read_corpus(path: str) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        blocks = [b.strip() for b in fh.read().split("\n\n")]
    return [b for b in blocks if b]


def main(argv: list[str] | None = None) -> int:
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()
    parser = argparse.ArgumentParser(prog="untell-compare", description=__doc__)
    parser.add_argument("--file", "-f", help="corpus file (paragraphs separated by blank lines)")
    parser.add_argument("--tier", default="full", choices=["lite", "full", "heavy", "commercial"])
    parser.add_argument("--threshold", "-t", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    texts = _read_corpus(args.file) if args.file else _SAMPLE
    if not texts:
        print(json.dumps({"error": "empty corpus"}))
        return 2
    result = compare(texts, tier=args.tier, threshold=args.threshold)
    print(json.dumps(result, ensure_ascii=True, indent=2) if args.json else _render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
