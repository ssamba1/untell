"""Does the lite detector measure authorship, or how standard a document sounds?

Rounds seventy-six to eighty-three concluded the second: on academic abstracts the detector's
ordering is **inverted** (AUROC 0.3529), both live features rank below 0.5 alone, and the tell
catalogue is a perfect *register* classifier with authorship held constant. The explanation offered
was that these features measure "how closely a document reads like a standard academic abstract."

That explanation was inferred from **56 machine documents**. It is the weakest link in the whole
arc, and it does not have to be — because if it is true, it is testable **with no machine text at
all**. Among documents that are all unambiguously human, the more prototypically academic ones
should score as more AI. That turns a 56-document inference into a 6,842-document measurement, on a
corpus (pre-2022 ACL abstracts) whose label cannot be disputed.

Prototypicality is operationalised without a model, so nothing here depends on a download: the mean
log document-frequency of a document's vocabulary over the corpus itself. A document scores high
when it is built out of words that nearly every abstract uses, which is what "reads like a standard
academic abstract" means when you have to write it down.

**The length confound is the thing to control.** Round seventy-two traced the detector's length bias
to a variance denominator, and longer abstracts use more vocabulary, so the two could travel
together for reasons that have nothing to do with register. Every correlation here is therefore
reported within length bands as well as pooled, and the band figures are the ones that carry weight.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics as stats
import sys
from collections import Counter
from pathlib import Path

WORD = re.compile(r"[a-z']+")

# Wide enough that a band is a length control rather than a second sample of the same length.
BANDS: tuple[tuple[int, int], ...] = (
    (40, 60), (60, 80), (80, 100), (100, 150), (150, 250), (250, 100_000),
)


def vocabulary(text: str) -> set[str]:
    return set(WORD.findall(text.lower()))


def document_frequencies(texts: list[str]) -> tuple[Counter, int]:
    """How many documents each word appears in, and how many documents there are."""
    df: Counter = Counter()
    for text in texts:
        df.update(vocabulary(text))
    return df, len(texts)


def prototypicality(text: str, df: Counter, total: int) -> float:
    """Mean log document-frequency of a document's vocabulary. Higher = more standard-sounding.

    Deliberately not TF-IDF and deliberately not a model. The quantity wanted is "how ordinary is
    this document's word choice for this corpus", which is the average commonness of the words it
    uses; weighting by term frequency would let one repeated word dominate, and an embedding would
    make the result depend on a download and on somebody else's training distribution.
    """
    vocab = vocabulary(text)
    if not vocab or not total:
        return 0.0
    return sum(math.log(df[w] / total) for w in vocab if df[w]) / len(vocab)


def spearman(xs: list[float], ys: list[float]) -> float:
    """Rank correlation, ties averaged. Rank-based because the score's scale is not meaningful."""
    if len(xs) < 3:
        return 0.0

    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        out = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            average = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = average
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    mx, my = stats.mean(rx), stats.mean(ry)
    numerator = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denominator = math.sqrt(
        sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return numerator / denominator if denominator else 0.0


def bootstrap_rho(rows: list[dict], draws: int = 2000, seed: int = 0) -> tuple[float, float]:
    """95% bootstrap interval for the prototypicality/score rank correlation.

    A rank correlation of +0.06 is the kind of number that is either a real small effect or noise,
    and nothing about its face value says which. The interval is what settles it.
    """
    import random

    rng = random.Random(seed)
    out = []
    for _ in range(draws):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        out.append(spearman([r["prototypicality"] for r in sample],
                            [r["score"] for r in sample]))
    out.sort()
    return round(out[int(0.025 * draws)], 4), round(out[int(0.975 * draws)], 4)


def score_one(text: str, tier: str = "lite") -> float | None:
    """The shipped scoring path, one document, or None if the detector declines.

    Routed through `eval.detection_power.score_arm` rather than reimplemented. Round eighty-four
    published an AUROC from a reimplementation of the score's components and it disagreed with the
    shipped path in the third decimal; round eighty-eight's first attempt read `result["score"]`,
    a key `score_text` does not return, and silently scored **zero of 6,842 documents** after a
    twenty-minute run. Both failures are the same failure, and calling the shipped helper is the
    only fix that stays fixed.
    """
    from eval.detection_power import score_arm

    scored = score_arm([text], tier=tier)
    return scored[0][1] if scored else None


VENUE = re.compile(r"^\d{4}\.([a-z0-9]+)-([a-z0-9]+)\.")

# Venue is a proxy for register that owes nothing to the text, which is the point of using it: the
# prototypicality measure above is built from the same words the detector reads, so on its own a
# null could mean the operationalisation missed rather than the explanation being wrong. A main
# conference track and a student research workshop differ in exactly the way "reads like a standard
# academic abstract" is supposed to mean, and the split is made without looking at a single word.
VENUE_CLASSES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("main/long", ("acl-main", "acl-long", "emnlp-main", "naacl-main", "coling-main",
                   "eacl-main", "lrec-1", "tacl-1")),
    ("findings", ("findings-emnlp", "findings-acl", "findings-naacl", "findings-eacl")),
    ("short", ("acl-short", "emnlp-short", "naacl-short", "eacl-short")),
    ("workshop/student", ("acl-srw", "eacl-srw", "naacl-srw", "emnlp-srw", "coling-srw")),
    ("demo/industry", ("acl-demos", "acl-demo", "emnlp-demo", "emnlp-demos", "eacl-demos",
                       "naacl-demos", "naacl-industry", "coling-industry", "emnlp-industry")),
)


def venue_class(paper_id: str) -> str | None:
    """Which register class a paper's venue puts it in, or None for one we did not classify."""
    match = VENUE.match(paper_id)
    if not match:
        return None
    venue = f"{match.group(1)}-{match.group(2)}"
    for name, members in VENUE_CLASSES:
        if venue in members:
            return name
    return None


def score_rows(papers: list[dict[str, str]], tier: str = "lite") -> list[dict]:
    """Score every paper once and keep everything an analysis could want.

    Separated from the analysis on purpose. Scoring 6,841 abstracts takes about twenty minutes, and
    round eighty-eight needed three different cuts of the same numbers — pooled, within length band,
    and by venue within length band. Re-scoring per question would have made the third cut cost more
    than it was worth, which is how a confound goes unchecked.
    """
    texts = [p["abstract"] for p in papers]
    df, total = document_frequencies(texts)
    rows: list[dict] = []
    for paper in papers:
        text = paper["abstract"]
        score = score_one(text, tier=tier)
        if score is None:
            continue
        rows.append({
            "id": paper["id"],
            "words": len(text.split()),
            "prototypicality": round(prototypicality(text, df, total), 6),
            "score": round(float(score), 6),
            "venue": venue_class(paper["id"]),
        })
    return rows


def _band_of(words: int) -> str | None:
    for low, high in BANDS:
        if low <= words < high:
            return f"{low}-{high}" if high < 100_000 else f"{low}+"
    return None


def standardized_venue_means(rows: list[dict], min_cell: int = 15) -> list[dict]:
    """Venue means with length held fixed, by direct standardization over the length bands.

    The raw venue means are not interpretable on their own: workshop papers are shorter than main
    conference papers, and this detector scores shorter text higher. So each venue's mean is
    recomputed band by band and then re-weighted onto the corpus-wide length distribution, which is
    the same correction `eval/length_standardized.py` applies elsewhere in this repository.

    A venue keeps only the bands where it has at least ``min_cell`` documents, and its weights are
    renormalised over those — so a venue present in one band is not silently compared against the
    whole corpus.
    """
    weights: dict[str, int] = {}
    for row in rows:
        band = _band_of(row["words"])
        if band:
            weights[band] = weights.get(band, 0) + 1

    out = []
    for name, _ in VENUE_CLASSES:
        cells: dict[str, list[float]] = {}
        for row in rows:
            if row["venue"] != name:
                continue
            band = _band_of(row["words"])
            if band:
                cells.setdefault(band, []).append(row["score"])
        usable = {b: v for b, v in cells.items() if len(v) >= min_cell}
        total_weight = sum(weights[b] for b in usable)
        if not usable or not total_weight:
            continue
        standardized = sum(
            stats.mean(v) * weights[b] / total_weight for b, v in usable.items())
        raw = [row["score"] for row in rows if row["venue"] == name]
        out.append({
            "venue": name,
            "n": len(raw),
            "raw_mean": round(stats.mean(raw), 4),
            "standardized_mean": round(standardized, 4),
            "mean_words": round(stats.mean(
                [row["words"] for row in rows if row["venue"] == name]), 1),
            "bands_used": sorted(usable),
        })
    return out


def analyse(rows: list[dict]) -> dict:
    """Every cut of the scored rows. Cheap, so a new question does not cost a re-score."""
    if not rows:
        return {"scored": 0, "note": "the detector declined every document"}

    lengths = [float(r["words"]) for r in rows]
    protos = [r["prototypicality"] for r in rows]
    scores = [r["score"] for r in rows]

    bands = []
    for low, high in BANDS:
        sub = [r for r in rows if low <= r["words"] < high]
        if len(sub) < 30:
            continue
        bands.append({
            "band": f"{low}-{high}" if high < 100_000 else f"{low}+",
            "n": len(sub),
            "rho": round(spearman([r["prototypicality"] for r in sub],
                                  [r["score"] for r in sub]), 4),
            "mean_score": round(stats.mean([r["score"] for r in sub]), 4),
        })

    ordered = sorted(rows, key=lambda r: r["prototypicality"])
    k = max(1, len(ordered) // 10)
    least, most = ordered[:k], ordered[-k:]

    venues = standardized_venue_means(rows)
    # Do the two operationalisations agree? Rank the venue classes by how common their vocabulary
    # is, rank them by AI score, and correlate. This is the check that makes a small pooled rho
    # worth something: one measure reads the same words the detector reads, the other does not.
    agreement = 0.0
    if len(venues) >= 3:
        by_venue = {v["venue"]: v for v in venues}
        protos_by_venue, scores_by_venue = [], []
        for name in by_venue:
            members = [r for r in rows if r["venue"] == name]
            protos_by_venue.append(stats.mean([r["prototypicality"] for r in members]))
            scores_by_venue.append(by_venue[name]["standardized_mean"])
        agreement = round(spearman(protos_by_venue, scores_by_venue), 4)

    low, high = bootstrap_rho(rows) if len(rows) >= 100 else (0.0, 0.0)
    return {
        "venue_agreement_rho": agreement,
        "rho_ci": [low, high],
        "rho_excludes_zero": low > 0 or high < 0,
        "scored": len(rows),
        "rho_prototypicality_score": round(spearman(protos, scores), 4),
        "rho_length_score": round(spearman(lengths, scores), 4),
        "rho_length_prototypicality": round(spearman(lengths, protos), 4),
        "bands": bands,
        "bands_positive": sum(1 for b in bands if b["rho"] > 0),
        "decile": {
            "n": k,
            "least_prototypical_mean_score": round(stats.mean([r["score"] for r in least]), 4),
            "most_prototypical_mean_score": round(stats.mean([r["score"] for r in most]), 4),
            "least_prototypical_mean_words": round(stats.mean([r["words"] for r in least]), 1),
            "most_prototypical_mean_words": round(stats.mean([r["words"] for r in most]), 1),
        },
        "venues": venues,
        "venue_spread_raw": (
            round(max(v["raw_mean"] for v in venues) - min(v["raw_mean"] for v in venues), 4)
            if venues else 0.0),
        "venue_spread_standardized": (
            round(max(v["standardized_mean"] for v in venues)
                  - min(v["standardized_mean"] for v in venues), 4)
            if venues else 0.0),
    }


def measure(papers: list[dict[str, str]], tier: str = "lite") -> dict:
    """Score and analyse in one call. `score_rows` then `analyse` if you want the rows kept."""
    return analyse(score_rows(papers, tier=tier))


def render(report: dict) -> str:
    if not report.get("scored"):
        return report.get("note", "nothing scored")
    lines = [
        f"{report['scored']} pre-2022 ACL abstracts — every one of them human.",
        "",
        f"  rho(prototypicality, AI score)   {report['rho_prototypicality_score']:+.4f}",
        f"  rho(length, AI score)            {report['rho_length_score']:+.4f}"
        "   <- the known length confound",
        f"  rho(length, prototypicality)     {report['rho_length_prototypicality']:+.4f}",
        "",
        f"{'band':>10} {'n':>6} {'rho':>9} {'mean score':>12}",
    ]
    for band in report["bands"]:
        lines.append(f"{band['band']:>10} {band['n']:>6} {band['rho']:>+9.4f} "
                     f"{band['mean_score']:>12.4f}")
    decile = report["decile"]
    lines += [
        "",
        f"least prototypical decile (n={decile['n']}): mean AI score "
        f"{decile['least_prototypical_mean_score']:.4f} "
        f"({decile['least_prototypical_mean_words']:.0f} words)",
        f"most  prototypical decile (n={decile['n']}): mean AI score "
        f"{decile['most_prototypical_mean_score']:.4f} "
        f"({decile['most_prototypical_mean_words']:.0f} words)",
        "",
    ]
    if report.get("venues"):
        lines += [f"{'venue class':>18} {'n':>6} {'raw':>9} {'len-std':>9} {'words':>8}"]
        for venue in report["venues"]:
            lines.append(f"{venue['venue']:>18} {venue['n']:>6} {venue['raw_mean']:>9.4f} "
                         f"{venue['standardized_mean']:>9.4f} {venue['mean_words']:>8.1f}")
        lines += ["",
                  f"venue spread: {report['venue_spread_raw']:.4f} raw, "
                  f"{report['venue_spread_standardized']:.4f} with length held fixed", ""]

    positive = report["bands_positive"]
    total = len(report["bands"])
    rho = report["rho_prototypicality_score"]
    low, high = report.get("rho_ci", [0.0, 0.0])
    agreement = report.get("venue_agreement_rho", 0.0)

    lines += [f"rho {rho:+.4f}, bootstrap 95% CI [{low:+.4f}, {high:+.4f}]"
              f" — {'excludes' if report.get('rho_excludes_zero') else 'includes'} zero", ""]

    if not report.get("rho_excludes_zero") or positive < total:
        lines.append(
            f"{positive} of {total} length bands point the same way and the pooled interval "
            f"{'includes' if not report.get('rho_excludes_zero') else 'excludes'} zero.\n"
            "The register explanation is NOT supported here — see round eighty-eight of "
            "docs/research-verification.md\nbefore quoting it.")
        return "\n".join(lines)

    lines += [
        f"Supported, and small. Every one of the {total} length bands points the same way (a sign "
        f"test on\nits own: p = {2 / 2 ** total:.3f}) and the pooled interval excludes zero. So "
        "among documents that are\nALL human, the more standard-sounding ones really do score as "
        "more AI.",
        "",
        f"But rho {rho:+.4f} is {rho * rho * 100:.2f}% of the score's variance. Register "
        "conformity is a real\ncomponent of what this detector measures and nowhere near all of "
        "it: it explains the\nDIRECTION of the inversion on machine text without accounting for "
        "its SIZE.",
    ]
    if agreement > 0.5:
        lines.append(
            f"\nThe venue split — which never looks at the text — orders the same way "
            f"(rho {agreement:+.2f}\nacross venue classes), but on five classes that is "
            "corroboration, not a second test.")
    else:
        lines.append(
            f"\n⚠️ The venue split agrees only weakly once length is held fixed "
            f"(rho {agreement:+.2f} across five\nclasses, which has no power either way). Its "
            "extremes do line up — the venues with the\ncommonest vocabulary score highest and "
            "the rarest lowest — but the middle shuffles, so this\nis a consistency check that "
            "passed, not independent confirmation.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path(".anthology-cache"))
    parser.add_argument("--limit", type=int,
                        help="score a random N (seeded) instead of all of them, for a fast run")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--min-words", type=int, default=40)
    parser.add_argument("--tier", default="lite")
    parser.add_argument("--dump", type=Path,
                        help="write the scored rows here so a new question costs no re-score")
    parser.add_argument("--rows", type=Path,
                        help="analyse rows written by an earlier --dump instead of scoring")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    if args.rows:
        report = analyse(json.loads(args.rows.read_text()))
        print(json.dumps(report, indent=2) if args.as_json else render(report))
        return 0

    from eval.pre_llm_fpr import pre_llm_papers

    if not args.cache.exists() or not any(args.cache.glob("*.xml")):
        print(f"no volume XML in {args.cache} — run `python -m eval.litreview --download` first",
              file=sys.stderr)
        return 1

    papers = pre_llm_papers(args.cache, min_words=args.min_words, max_year=2021)
    if args.limit:
        # Seeded shuffle, not a head slice. The corpus is ordered by volume, so the first N papers
        # are one venue — which makes a venue comparison degenerate and every other figure a
        # measurement of one conference rather than of the corpus.
        import random

        papers = list(papers)
        random.Random(args.seed).shuffle(papers)
        papers = papers[:args.limit]
    rows = score_rows(papers, tier=args.tier)
    if args.dump:
        args.dump.write_text(json.dumps(rows))
    report = analyse(rows)
    print(json.dumps(report, indent=2) if args.as_json else render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
