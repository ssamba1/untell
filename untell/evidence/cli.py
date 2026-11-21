"""Command-line entry points for the evidence commands.

    untell brief        one document, one detector -> an evidence brief (md / html / json)
    untell stability    does the verdict on this text survive formatting-only edits?
    untell variants     write the variants to files, to score by hand in any web UI
    untell flagmath     what a flag implies: Bayes + per-person false-flag risk
    untell report-card  a detector over a human (and optionally AI) corpus, dated and versioned
    untell drift        compare two report cards for a silent model change
    untell capsule      build a pre-LLM human corpus from a git repository's history
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DETECTOR_HELP = (
    "who produced the verdict: 'local' / 'local:lite' (untell's own ensemble), a detector name "
    "('gptzero', 'pangram', 'originality', 'copyleaks', 'winston', 'sapling', 'zerogpt'; needs "
    "its API key), 'cmd:<command>' (text on stdin, score on stdout), or 'manual:<scores.csv>' "
    "(scores you recorded by hand, keyed base,N1,N2,...)"
)


def _read_text(args: argparse.Namespace) -> str:
    if getattr(args, "file", None):
        return Path(args.file).read_text(encoding="utf-8")
    if getattr(args, "text", None):
        return args.text
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("give the text as an argument, with --file, or on stdin")


def _write(out: str | None, content: str) -> None:
    if out:
        Path(out).write_text(content, encoding="utf-8")
        print(f"wrote {out}", file=sys.stderr)
    else:
        sys.stdout.write(content)


def _tiers(s: str) -> tuple[str, ...]:
    t = tuple(x.strip() for x in s.split(",") if x.strip())
    bad = set(t) - {"null", "light", "rewrite"}
    if bad:
        raise argparse.ArgumentTypeError(f"unknown tier(s): {', '.join(sorted(bad))}")
    return t


# --- brief -----------------------------------------------------------------------------------------

def brief_main(argv: list[str] | None = None) -> int:
    from .brief import build_brief, render_html, render_markdown
    from .scorers import resolve_scorer
    from .stability import measure_stability

    ap = argparse.ArgumentParser(
        prog="untell brief",
        description="Evidence brief for one detector verdict on one document: stability under "
                    "formatting-only edits, the detector's published error rates, and what a flag "
                    "implies. Measures the detector, not the writer.")
    ap.add_argument("text", nargs="?", help="the document text (or use --file / stdin)")
    ap.add_argument("--file", "-f", help="read the document from a file")
    ap.add_argument("--detector", "-d", default=None, help=DETECTOR_HELP)
    ap.add_argument("--name", help="detector name to print and look up published rates for "
                    "(defaults to --detector; use it with cmd:/manual: specs, e.g. --name turnitin)")
    ap.add_argument("--detector-version", help="model/version string, if known")
    ap.add_argument("--score", type=float, help="the score the detector gave (if not re-running it)")
    ap.add_argument("--flagged", choices=("yes", "no"), help="the verdict the detector gave")
    ap.add_argument("--threshold", type=float, help="score at or above which a text is flagged")
    ap.add_argument("--tiers", type=_tiers, default=("null", "light"),
                    help="variant tiers to test: null,light,rewrite (default null,light)")
    ap.add_argument("--fpr", type=float, help="false-positive rate to use instead of the published one")
    ap.add_argument("--tpr", type=float, default=0.90, help="assumed true-positive rate (default 0.90)")
    ap.add_argument("--documents", type=int, default=1,
                    help="how many documents this writer submitted (for the per-person risk)")
    ap.add_argument("--format", choices=("md", "html", "json"), default="md")
    ap.add_argument("--out", "-o", help="write to this file instead of stdout")
    args = ap.parse_args(argv)

    text = _read_text(args)
    name = args.name or args.detector or "unspecified"
    stability = None
    if args.detector:
        scorer = resolve_scorer(args.detector, args.threshold)
        stability = measure_stability(text, scorer, tiers=args.tiers).to_dict()
    b = build_brief(
        text, name, detector_version=args.detector_version, stability=stability,
        observed_score=args.score,
        observed_flagged=None if args.flagged is None else args.flagged == "yes",
        fpr=args.fpr, tpr=args.tpr, documents=max(1, args.documents))
    render = {"md": render_markdown, "html": render_html,
              "json": lambda x: json.dumps(x, indent=2) + "\n"}[args.format]
    _write(args.out, render(b))
    return 0


# --- stability --------------------------------------------------------------------------------------

def stability_main(argv: list[str] | None = None) -> int:
    from .scorers import resolve_scorer
    from .stability import measure_stability

    ap = argparse.ArgumentParser(
        prog="untell stability",
        description="Re-score a document under edits that cannot change its authorship and report "
                    "how often the verdict changes.")
    ap.add_argument("text", nargs="?")
    ap.add_argument("--file", "-f")
    ap.add_argument("--detector", "-d", default="local", help=DETECTOR_HELP)
    ap.add_argument("--threshold", type=float)
    ap.add_argument("--tiers", type=_tiers, default=("null", "light"))
    ap.add_argument("--json", action="store_true", help="print the full JSON result")
    args = ap.parse_args(argv)
    res = measure_stability(_read_text(args), resolve_scorer(args.detector, args.threshold),
                            tiers=args.tiers).to_dict()
    if args.json:
        print(json.dumps(res, indent=2))
        return 0
    b = res["base"]
    print(f"detector: {res['scorer']['name']}  base score: "
          f"{'n/a' if b['score'] is None else round(b['score'], 4)}  flagged: {b['flagged']}")
    for r in res["variants"]:
        if r["noop"]:
            continue
        mark = " <- FLIP" if (r["flagged"] is not None and b["flagged"] is not None
                              and r["flagged"] != b["flagged"]) else ""
        sc = "n/a" if r["score"] is None else f"{r['score']:.4f}"
        print(f"  {r['id']:4} {r['tier']:6} {r['label'][:38]:38} {sc:>7}{mark}")
    print()
    print(res["summary"]["finding"])
    return 0


# --- variants ---------------------------------------------------------------------------------------

def variants_main(argv: list[str] | None = None) -> int:
    from .perturb import all_variants

    ap = argparse.ArgumentParser(
        prog="untell variants",
        description="Write formatting-only and light-edit variants of a document to a folder, plus "
                    "a scores.csv template. Paste each into the detector under test, fill in the "
                    "CSV, then run: untell brief --file DOC --detector manual:FOLDER/scores.csv")
    ap.add_argument("text", nargs="?")
    ap.add_argument("--file", "-f")
    ap.add_argument("--out", "-o", default="untell-variants", help="output folder")
    ap.add_argument("--tiers", type=_tiers, default=("null", "light"))
    args = ap.parse_args(argv)
    text = _read_text(args)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "base.txt").write_text(text, encoding="utf-8")
    rows = ["id,score,flagged,label", "base,,,original"]
    n = 0
    for v in all_variants(text, args.tiers):
        if v.noop:
            continue
        (out / f"{v.id}.txt").write_text(v.text, encoding="utf-8")
        rows.append(f"{v.id},,,{v.label}")
        n += 1
    (out / "scores.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"wrote base.txt + {n} variants and scores.csv to {out}/")
    return 0


# --- flagmath ---------------------------------------------------------------------------------------

def flagmath_main(argv: list[str] | None = None) -> int:
    from . import stats as S
    from .rates import best_fpr_estimate

    ap = argparse.ArgumentParser(
        prog="untell flagmath",
        description="What a detector flag implies: P(AI | flagged) by Bayes, and the chance an "
                    "honest writer is falsely flagged at least once across k documents.")
    ap.add_argument("--detector", help="look up a published false-positive rate for this detector")
    ap.add_argument("--fpr", type=float, help="false-positive rate per document")
    ap.add_argument("--tpr", type=float, default=0.90)
    ap.add_argument("--prior", type=float, action="append",
                    help="share of screened work that is AI-written (repeatable)")
    ap.add_argument("--documents", "-k", type=int, default=10)
    ap.add_argument("--cohort", type=int, default=1000)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    fpr, source = args.fpr, "given"
    if fpr is None and args.detector:
        est = best_fpr_estimate(args.detector)
        if est:
            fpr, source = est["fpr"], est["source"]
    if fpr is None:
        raise SystemExit("need --fpr, or a --detector with a published rate on file")
    priors = args.prior or [0.01, 0.05, 0.10, 0.25, 0.50]
    out = {
        "fpr": fpr, "fpr_source": source, "tpr_assumed": args.tpr,
        "by_prior": [{"prior": p, "p_ai_given_flag": S.posterior_ai_given_flag(fpr, args.tpr, p)}
                     for p in priors],
        "honest_writer": S.honest_writer_table(fpr, ks=sorted({1, 5, args.documents, 20, 40}),
                                               cohort=args.cohort),
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"false-positive rate {fpr:.4f} ({source}); true-positive rate assumed {args.tpr:.2f}\n")
    print("if this share is AI-written   P(AI | flagged)   P(human | flagged)")
    for r in out["by_prior"]:
        print(f"  {100 * r['prior']:>6.1f}%                    {100 * r['p_ai_given_flag']:>6.1f}%"
              f"            {100 * (1 - r['p_ai_given_flag']):>6.1f}%")
    print(f"\ndocuments per honest writer   P(>=1 false flag)   flagged per {args.cohort}")
    for r in out["honest_writer"]:
        print(f"  {r['documents']:>4}                        {100 * r['p_at_least_one_false_flag']:>6.1f}%"
              f"            {r[f'flagged_per_{args.cohort}']:>6.0f}")
    return 0


# --- report card / drift / capsule ------------------------------------------------------------------

def report_card_main(argv: list[str] | None = None) -> int:
    from .corpus import load_corpus
    from .report_card import render_report_card_markdown, run_report_card
    from .scorers import resolve_scorer

    ap = argparse.ArgumentParser(
        prog="untell report-card",
        description="Measure a detector on a corpus of human writing (and optionally AI writing): "
                    "false-positive rate by slice with 95% intervals, per-person risk, verdict "
                    "stability, recall at capped FPR. Dated, versioned, fingerprinted.")
    ap.add_argument("--detector", "-d", default="local", help=DETECTOR_HELP)
    ap.add_argument("--detector-version")
    ap.add_argument("--threshold", type=float)
    ap.add_argument("--human", action="append", required=True,
                    help="human corpus: .jsonl/.json/.csv or a folder of .txt/.md (repeatable)")
    ap.add_argument("--ai", action="append", default=[], help="AI corpus, same formats (repeatable)")
    ap.add_argument("--name", default=None, help="corpus name for the report")
    ap.add_argument("--stability-sample", type=int, default=20)
    ap.add_argument("--json-out", help="write the full JSON report card here (needed for drift)")
    ap.add_argument("--out", "-o", help="write the Markdown summary here")
    args = ap.parse_args(argv)
    docs = []
    for p in args.human:
        docs += load_corpus(p, label="human")
    for p in args.ai:
        docs += load_corpus(p, label="ai")
    scorer = resolve_scorer(args.detector, args.threshold)

    def prog(i: int, n: int) -> None:
        if i == n or i % 10 == 0:
            print(f"  scored {i}/{n}", file=sys.stderr)

    card = run_report_card(scorer, docs, corpus_name=args.name or Path(args.human[0]).stem,
                           detector_version=args.detector_version,
                           stability_sample=args.stability_sample, progress=prog)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.json_out}", file=sys.stderr)
    _write(args.out, render_report_card_markdown(card))
    return 0


def drift_main(argv: list[str] | None = None) -> int:
    from .report_card import drift

    ap = argparse.ArgumentParser(
        prog="untell drift",
        description="Compare two report cards (JSON) for the same detector. Exit 1 if anything "
                    "changed significantly (non-overlapping 95% intervals, or any document's "
                    "verdict flipping on an identical corpus).")
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    d = drift(json.loads(Path(args.old).read_text(encoding="utf-8")),
              json.loads(Path(args.new).read_text(encoding="utf-8")))
    if args.json:
        print(json.dumps(d, indent=2))
    else:
        print(f"{d['old']['generated_at']} (v {d['old']['version']}) -> "
              f"{d['new']['generated_at']} (v {d['new']['version']}); same corpus: {d['same_corpus']}")
        for c in d["changes"]:
            star = "  SIGNIFICANT" if c["significant"] else ""
            print(f"  {c['metric']}: {100 * c['old']:.1f}% -> {100 * c['new']:.1f}%{star}")
        if d.get("documents_whose_verdict_changed"):
            print(f"  {len(d['documents_whose_verdict_changed'])} document(s) changed verdict")
        print("DRIFT" if d["significant"] else "no significant drift")
    return 1 if d["significant"] else 0


def capsule_main(argv: list[str] | None = None) -> int:
    from .corpus import CHATGPT_RELEASE, git_time_capsule

    ap = argparse.ArgumentParser(
        prog="untell capsule",
        description="Build a human corpus whose provenance is a timestamp: prose from a git "
                    "repository as it stood before a cut-off (default: ChatGPT's release, "
                    f"{CHATGPT_RELEASE}). Writes JSONL with commit and date on every record.")
    ap.add_argument("repo", nargs="+", help="local git repositories to read")
    ap.add_argument("--before", default=CHATGPT_RELEASE)
    ap.add_argument("--min-words", type=int, default=150)
    ap.add_argument("--max-words", type=int, default=800)
    ap.add_argument("--limit", type=int, help="max documents per repository")
    ap.add_argument("--out", "-o", default="capsule.jsonl")
    args = ap.parse_args(argv)
    n = 0
    with open(args.out, "w", encoding="utf-8") as fh:
        for repo in args.repo:
            for d in git_time_capsule(repo, before=args.before, min_words=args.min_words,
                                      max_words=args.max_words, limit=args.limit):
                fh.write(json.dumps(d, ensure_ascii=False) + "\n")
                n += 1
    print(f"wrote {n} documents to {args.out}")
    return 0
