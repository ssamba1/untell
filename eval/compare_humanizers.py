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
import logging

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


def _ai_max(text: str, tier: str) -> float | None:
    """Max P(AI), or None when there is nothing to measure.

    score_text returns ``max: 0.0`` as a placeholder when no detector produced a number. Folding
    that in as a real score would credit every technique in the table with perfect evasion on a
    broken stack — 0.0 P(AI), 0% flagged — which is the exact shape of the result the tool exists
    to find.
    """
    if not text.strip():
        return None
    res = score_text(text, tier=tier)
    return None if res.get("scored") is False else float(res["max"])


def _techniques(tier: str, threshold: float):
    """Return {name: rewrite_fn}. Heavy/optional deps imported lazily so lite still runs."""

    def synonym_swap(t: str) -> str:
        from untell.attacks import surgical_substitute

        return surgical_substitute(t, tier=tier, threshold=threshold, max_subs=10)["text"]

    def back_translation(t: str) -> str:
        from untell.attacks import back_translate

        return back_translate(t)

    def _ours(prefer: str, best_of: int):
        def run(t: str) -> str:
            from untell.rewriter import get_rewriter
            from untell.scripts.run import untell_text

            res = untell_text(
                t, tier=tier, threshold=threshold, max_iters=5,
                rewriter=get_rewriter(prefer=prefer), best_of=best_of,
            )
            # `untell_text` reports a configuration failure — an unavailable rewriter, a missing
            # key — as {"error": ..., "final": <the input, unchanged>}. Reading `final` without
            # checking `error` turns that into a silent no-op row, and this is the script that
            # compares us against competitors: our own tool would be reported as changing nothing
            # and losing, with the cause nowhere in the output. Raise instead, because a comparison
            # run that cannot run one of its arms has no result to report for it.
            if "error" in res:
                raise RuntimeError(f"untell_text({prefer!r}) failed: {res['error']}")
            return res.get("final", t)

        return run

    # Two of our rows, for two different questions.
    #
    # The surgical row is the apples-to-apples control: `synonym_swap` above IS
    # `attacks.surgical_substitute`, so this asks "does wrapping that same technique in the closed
    # loop beat running it once?" Keeping it is the honest comparison against that technique class.
    #
    # But it was the ONLY row we had, and it is not what anyone runs. MEASURED on these samples:
    #
    #     synonym_swap                    P(AI) 0.2736   tells/100w 7.02
    #     ours_loop (surgical)            P(AI) 0.2736   tells/100w 7.02   <- identical
    #     back_translation                P(AI) 0.2416   tells/100w 4.94   <- "beats" us
    #     ours_loop (composite, DEFAULT)  P(AI) 0.0408   tells/100w 0.79
    #
    # So the table answering "are we better than the free humanizers" was reporting our weakest
    # backend, tying with the technique it was supposed to improve on, and losing to
    # back-translation — while the rewriter the CLI actually defaults to scores ~7x lower P(AI) and
    # ~9x fewer tells. Understating the tool by that much is the same measurement error this repo
    # keeps correcting, pointed at ourselves.
    #
    # best_of matches the CLI default (3) for the default row, and stays 1 for the control so the
    # comparison against a single synonym_swap pass remains single-draw on both sides.
    return {
        "none (raw AI)": lambda t: t,
        "synonym_swap": synonym_swap,
        "back_translation": back_translation,
        "ours_loop (surgical)": _ours("surgical", 1),
        "ours_loop (composite)": _ours("composite", 3),
    }


def compare(
    texts: list[str],
    tier: str = "full",
    threshold: float = DEFAULT_THRESHOLD,
    corpus: str = "unspecified",
) -> dict:
    """Score every technique over ``texts``. ``corpus`` labels what they came from.

    The label is a parameter rather than something the caller bolts on afterwards, because
    `_render` already reads ``result["corpus"]`` and `compare` never set it — so calling this
    function directly produced a report headed ``corpus=unknown``, which is precisely the
    unquotable comparison the note in `main` warns about. Only the CLI happened to fill it in.

    It matters more here than in most places: the ranking this function produces is not stable
    across corpora. On 6 HC3 answers at the lite tier, back-translation comes out BEST
    (`ai_max_mean` 0.5149 against the composite loop's 0.5596, and the only technique to move the
    flagged rate off 1.00), while `docs/free-ceiling-measured.md` records it as the worst method
    tested and "made one text more detectable than the input it was given". Both are real; they
    are measurements of different corpora, and a row with no corpus attached cannot tell them
    apart.
    """
    if not texts:  # no corpus -> nothing to score (the per-technique means would divide by zero)
        return {"n": 0, "tier": tier, "threshold": threshold, "techniques": {}, "corpus": corpus}
    from untell.scripts.quality import similarity

    rows: dict[str, dict] = {}
    for name, fn in _techniques(tier, threshold).items():
        ai_scores, tell_rates, tell_counts, sims = [], [], [], []
        changed_any = False
        for t in texts:
            try:
                out = fn(t)
            except Exception as exc:  # a missing optional dep (e.g. marian) -> skip that technique
                rows[name] = {"error": f"{type(exc).__name__}: {str(exc)[:120]}"}
                break
            if out.strip() != t.strip():
                changed_any = True
            ai_scores.append(_ai_max(out, tier))
            tl = score_tells(out)
            tell_rates.append(tl["tells_per_100w"])
            tell_counts.append(tl["tells"])
            sims.append(similarity(t, out) if name != "none (raw AI)" else 1.0)
        else:
            if not changed_any and name != "none (raw AI)":
                # The technique returned its input unchanged on EVERY sample. That is not a result,
                # it is an unavailable technique: back_translate (and the other optional-dep paths)
                # degrade to a silent no-op rather than raising when transformers/torch/sentencepiece
                # are missing, so the `except` guard above never fires. Recording the numbers anyway
                # publishes the raw-AI baseline — sim_mean 1.0, identical ai/tells — as if it were a
                # real measurement of the technique, which is exactly what the docs then quote.
                rows[name] = {
                    "error": "technique made NO change to any sample — treated as unavailable "
                    "(optional dependency missing?), not as a measurement"
                }
                continue
            n = len(texts)
            measured = [s for s in ai_scores if s is not None]
            rows[name] = {
                # Detector-independent columns keep the full denominator; the P(AI) columns are
                # averaged over what actually scored, and say so when that is not everything.
                "ai_max_mean": round(sum(measured) / len(measured), 4) if measured else None,
                "tells_per_100w_mean": round(sum(tell_rates) / n, 2),
                "tells_total": sum(tell_counts),
                "sim_mean": round(sum(sims) / n, 3),
                "flagged_rate": (
                    round(sum(1 for s in measured if s > threshold) / len(measured), 3)
                    if measured else None
                ),
                "unscored": n - len(measured),
            }
    return {
        "n": len(texts),
        "tier": tier,
        "threshold": threshold,
        "corpus": corpus,
        "techniques": rows,
    }


def _render(r: dict) -> str:
    lines = [
        f"humanizer technique comparison — corpus={r.get('corpus', 'unknown')} "
        f"tier={r['tier']} n={r['n']} threshold={r['threshold']}",
        "",
        f"  {'technique':24} {'AI P(AI)':>9} {'flagged':>8} {'tells/100w':>11} {'meaning':>8}",
        f"  {'-' * 24} {'-' * 9:>9} {'-' * 8:>8} {'-' * 11:>11} {'-' * 8:>8}",
    ]
    for name, m in r["techniques"].items():
        if "error" in m:
            lines.append(f"  {name:24} (skipped: {m['error']})")
            continue
        # "n/a" rather than a number when no detector scored: an empty cell cannot be misread as
        # a result, a 0.0 can.
        ai = "n/a" if m.get("ai_max_mean") is None else m["ai_max_mean"]
        flagged = "n/a" if m.get("flagged_rate") is None else m["flagged_rate"]
        note = f"  ({m['unscored']}/{r['n']} unscored)" if m.get("unscored") else ""
        lines.append(
            f"  {name:24} {ai:>9} {flagged:>8} "
            f"{m['tells_per_100w_mean']:>11} {m['sim_mean']:>8}{note}"
        )
    lines += [
        "",
        "  AI P(AI): local-ensemble max (evasion proxy; lower=better, but it anti-correlates w/ human-ness).",
        "  tells/100w: catalogued AI tells per 100 words (detector-INDEPENDENT; lower = reads more human).",
        "  meaning: semantic similarity to the source (higher=better; <0.76 = meaning drift).",
    ]
    return "\n".join(lines)


def _read_corpus(path: str) -> list[str]:
    with open(path, encoding="utf-8", errors="replace") as fh:
        blocks = [b.strip() for b in fh.read().split("\n\n")]
    return [b for b in blocks if b]


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()
    parser = argparse.ArgumentParser(prog="untell-compare", description=__doc__)
    parser.add_argument("--file", "-f", help="corpus file (paragraphs separated by blank lines)")
    # The head-to-head is this repository's central competitive artifact, and it ran on three
    # built-in paragraphs — which the report itself calls "a demo, and measurably easier than real
    # AI output". A comparison anyone can reproduce has to run on a corpus anyone can fetch.
    parser.add_argument(
        "--dataset",
        choices=["hc3", "raid", "mage"],
        help="run on real AI text from a public corpus instead of the built-in samples (needs .[eval])",
    )
    parser.add_argument("--n", type=int, default=8, help="samples to draw from --dataset")
    parser.add_argument("--tier", default="full", choices=["lite", "full", "heavy", "commercial"])
    parser.add_argument("--threshold", "-t", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    # Same validation as untell-ceiling (eval/ceiling.py _validate): --n 0 / --threshold 2.5
    # silently run a comparison with degenerate settings — measured exit 0 with a threshold
    # where nothing can ever flag. Reject here so the head-to-head artifact cannot be quoted
    # from a nonsense configuration.
    if args.n <= 0:
        parser.error(f"--n must be >= 1, got {args.n}")
    if not 0.0 <= args.threshold <= 1.0:
        parser.error(f"--threshold must be in [0, 1], got {args.threshold}")

    if args.file:
        texts = _read_corpus(args.file)
        corpus = args.file
    elif args.dataset:
        from eval.datasets import load_pairs

        pairs = load_pairs(args.dataset, args.n)
        if not pairs:
            print(json.dumps({"error": f"no pairs available from {args.dataset}; pip install .[eval]"}))
            return 2
        texts = [ai for _human, ai in pairs][: args.n]
        corpus = f"{args.dataset} n={len(texts)}"
    else:
        texts = _SAMPLE
        corpus = "built-in sample"
    if not texts:
        print(json.dumps({"error": "empty corpus"}))
        return 2
    # Which corpus produced these numbers. Nine results in this repository once generalised
    # from a demo corpus, so a comparison that does not name its own is unquotable. Passed in
    # rather than assigned afterwards, so a library caller gets the same guarantee the CLI does.
    result = compare(texts, tier=args.tier, threshold=args.threshold, corpus=corpus)
    print(json.dumps(result, ensure_ascii=True, indent=2) if args.json else _render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
