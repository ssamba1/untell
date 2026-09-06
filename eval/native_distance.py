"""Do non-native writers sit further from the function-word norm? The hypothesis, finally tested.

Round one hundred and fourteen measured false-positive rate against stylistic distance and found it
RISES: text further from a norm is falsely flagged more often, in function-word space, z=+3.91.
Round one hundred and twenty confirmed it against a second centre, z=+6.55. Both rounds wrote down
the same tempting next step and refused to take it:

    It is tempting to close the loop on §4 by saying non-native writers sit far out in function-word
    space — article and preposition use is exactly that signal — which would make the L2
    false-positive result an instance of this effect. That is a hypothesis, not a result: there is
    no non-native corpus here, every document is an ACL abstract, and nothing in this study measures
    a writer's background.

There is now. `eval/assisted_fairness`'s corpus (Pratama, MIT-licensed, fetched from
raw.githubusercontent.com — reachable where huggingface.co is not) carries a **self-declared author
status** on every row: **36 Native and 36 Non-Native**, balanced, mean 183 words. That is the
missing arm, and it makes the hypothesis a measurement rather than a story.

WHAT IS AND IS NOT BEING TESTED. The claim under test is narrow: *do the two groups differ in
function-word distance from their own corpus's centre?* It is NOT "are detectors biased against
non-native writers" — this repo already measures that directly in `assisted_fairness`, and this
module cannot improve on it. What it can do is say whether the DISTANCE mechanism is a plausible
route for that bias, by checking the one link the earlier rounds could not: that the population the
fairness literature is about is in fact the population sitting further out.

⚠️ **n=36 per group, one field, self-declared status.** A permutation test is used rather than a
t-test because it assumes nothing about the shape of a Delta distribution, and the effect is
reported with its interval. A null here is weak evidence of no difference, and a positive is one
corpus's worth of evidence for a mechanism, not a demonstration that it drives the fairness result.

⚠️ **Length is the confound that has already faked this exact study once.** Round one hundred and
fourteen's crude curve reported a significant effect in the WRONG direction purely because distant
documents were shorter. The word counts of both groups are reported beside the distances, and the
test is repeated on a length-matched subsample.

    python -m eval.native_distance
    python -m eval.native_distance --json
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# The stylistic reading, deliberately. Round 114's sweep showed the sign of the FPR-versus-distance
# effect flips as the vocabulary grows from function words into content words, so a test of the
# FUNCTION-WORD hypothesis has to stay at the small end. 50 is inside the band where that curve is
# significantly positive (z=+3.70 at 50, +3.91 at 30) and is not tuned here; `--vocab` moves it.
FUNCTION_WORD_VOCAB = 50
PERMUTATIONS = 20000


def _profiles(texts: list[str], size: int):
    from eval.homogenization import centroid, delta, profile, vocabulary

    vocab = vocabulary(texts, size)
    profs = [profile(t, vocab) for t in texts]
    centre = centroid(profs)
    means = [statistics.fmean(p[i] for p in profs) for i in range(len(vocab))]
    stdevs = [statistics.pstdev([p[i] for p in profs]) for i in range(len(vocab))]
    return [delta(p, centre, means, stdevs) for p in profs]


def permutation_test(a: list[float], b: list[float], rounds: int = PERMUTATIONS,
                     seed: int = 0) -> dict:
    """Two-sided permutation test on the difference of means. Assumes nothing about the shape.

    A Delta distribution is a mean of absolute z-scores and has no reason to be normal, and at n=36
    per group a t-test's assumptions are doing real work. Permutation makes none: it asks how often
    a label shuffle produces a gap this large, which is exactly the question.
    """
    if not a or not b:
        return {"observed": None, "p": None, "note": "a group is empty"}
    observed = statistics.fmean(a) - statistics.fmean(b)
    pool = list(a) + list(b)
    rng = random.Random(seed)
    cut = len(a)
    hits = 0
    for _ in range(rounds):
        rng.shuffle(pool)
        gap = statistics.fmean(pool[:cut]) - statistics.fmean(pool[cut:])
        if abs(gap) >= abs(observed):
            hits += 1
    return {
        "observed": round(observed, 4),
        # (hits + 1) / (rounds + 1): the standard correction. A p of exactly 0 is not a p-value —
        # it says "no shuffle beat it in the ones we tried", and the smallest honest claim at 20,000
        # permutations is 1/20001.
        "p": round((hits + 1) / (rounds + 1), 5),
        "permutations": rounds,
    }


def required_n(a: list[float], b: list[float], power: float = 0.80,
               alpha: float = 0.05) -> dict:
    """Per-group n needed to detect an effect this size, if it is real.

    "Under-powered" is a word; this is the number behind it, and it is what turns a null into a
    specification. Standard two-sample formula, `n = 2(z_a/2 + z_b)^2 / d^2` with `d` the observed
    Cohen's d — which is itself a noisy estimate at this sample size, so the answer is an order of
    magnitude rather than a target.

    The honest framing this repository has used for every other null: a result that does not reach
    significance is not evidence of no effect, and the useful output is what it would take to find
    out.
    """
    if len(a) < 2 or len(b) < 2:
        return {"cohens_d": None, "n_per_group": None}
    pooled = math.sqrt(
        ((len(a) - 1) * statistics.variance(a) + (len(b) - 1) * statistics.variance(b))
        / (len(a) + len(b) - 2)
    )
    if pooled == 0:
        return {"cohens_d": None, "n_per_group": None, "note": "no variance to standardise by"}
    d = (statistics.fmean(a) - statistics.fmean(b)) / pooled
    if d == 0:
        return {"cohens_d": 0.0, "n_per_group": None, "note": "no observed difference to power for"}
    # z for a two-sided alpha and the given power.
    z_alpha, z_power = 1.959964, 0.841621 if abs(power - 0.80) < 1e-9 else 1.281552
    return {
        "cohens_d": round(d, 4),
        "n_per_group": math.ceil(2 * (z_alpha + z_power) ** 2 / d ** 2),
        "power": power,
    }


def _matched(rows: list[dict], key: str, tolerance: int = 25) -> list[dict]:
    """A length-matched subsample: each non-native abstract paired with the nearest unused native one.

    The confound control, and the one this study needs most — round one hundred and fourteen's crude
    curve reported a significant effect in the WRONG direction purely because distant documents were
    shorter. Greedy nearest-neighbour matching on word count, each control used once, pairs beyond
    `tolerance` words dropped rather than stretched.
    """
    native = sorted((r for r in rows if r["status"] == "Native"), key=lambda r: r["words"])
    other = [r for r in rows if r["status"] != "Native"]
    used: set[int] = set()
    out: list[dict] = []
    for row in other:
        best, best_gap = None, None
        for index, candidate in enumerate(native):
            if index in used:
                continue
            gap = abs(candidate["words"] - row["words"])
            if best_gap is None or gap < best_gap:
                best, best_gap = index, gap
        if best is None or best_gap > tolerance:
            continue
        used.add(best)
        out.extend([row, native[best]])
    return out


def measure(cache: Path, vocab: int = FUNCTION_WORD_VOCAB, tier: str = "lite") -> dict:
    """Function-word distance by author status, with the length control and the flag rates."""
    from eval.assisted_fairness import fetch, load_rows
    from untell.scripts.score import score_text

    path = fetch(cache)
    raw = load_rows(path)
    texts = [r["Abstract"].strip() for r in raw]
    deltas = _profiles(texts, vocab)

    rows = []
    for source, text, distance in zip(raw, texts, deltas):
        result = score_text(text, tier=tier)
        values = [v for v in result["detectors"].values() if isinstance(v, (int, float))]
        rows.append({
            "status": source["Status"].strip(),
            "words": len(text.split()),
            "delta": distance,
            # None, never 0.0, when nothing scored — the placeholder trap this repo has now found at
            # eight sites.
            "max": (max(values) if values and result.get("scored") is not False else None),
            "flagged": (None if not values or result.get("scored") is False
                        else int(max(values) >= result["verdict_threshold"])),
        })

    def _arm(subset: list[dict], status: str) -> dict:
        group = [r for r in subset if r["status"] == status]
        flags = [r["flagged"] for r in group if r["flagged"] is not None]
        return {
            "n": len(group),
            "mean_delta": round(statistics.fmean(r["delta"] for r in group), 4) if group else None,
            "median_words": round(statistics.median(r["words"] for r in group), 1) if group else None,
            "flagged": sum(flags) if flags else 0,
            "n_scored": len(flags),
            "fpr": round(sum(flags) / len(flags), 4) if flags else None,
        }

    def _compare(subset: list[dict], label: str) -> dict:
        non = [r["delta"] for r in subset if r["status"] == "Non-Native"]
        nat = [r["delta"] for r in subset if r["status"] == "Native"]
        return {
            "arm": label,
            "Non-Native": _arm(subset, "Non-Native"),
            "Native": _arm(subset, "Native"),
            # Positive = non-native sits FURTHER from the corpus centre, which is the hypothesis.
            "test": permutation_test(non, nat),
            "power": required_n(non, nat),
        }

    matched = _matched(rows, "words")
    return {
        "vocab": vocab,
        "tier": tier,
        "n": len(rows),
        "hypothesis": "non-native authors sit further from the corpus's function-word centre",
        "all": _compare(rows, "all documents"),
        "length_matched": _compare(matched, "length-matched pairs"),
    }


def _render(report: dict) -> str:
    lines = [
        "Function-word distance from the corpus centre, by author status.",
        f"{report['n']} abstracts, self-declared status, vocabulary {report['vocab']}, "
        f"tier={report['tier']}.",
        "",
        f"{'arm':<22}{'group':<12}{'n':>4}{'mean Δ':>9}{'median words':>14}{'flagged':>9}{'FPR':>8}",
    ]
    for key in ("all", "length_matched"):
        block = report[key]
        for status in ("Non-Native", "Native"):
            a = block[status]
            fpr = f"{a['fpr']:.1%}" if a["fpr"] is not None else "n/a"
            lines.append(
                f"{block['arm']:<22}{status:<12}{a['n']:>4}{a['mean_delta']:>9.4f}"
                f"{a['median_words']:>14.0f}{a['flagged']:>9}{fpr:>8}"
            )
        t = block["test"]
        verdict = ("further out" if (t["p"] or 1) < 0.05 and (t["observed"] or 0) > 0 else
                   "closer in" if (t["p"] or 1) < 0.05 else "NO separation")
        lines.append(f"{'':<22}permutation: diff={t['observed']:+.4f}, p={t['p']} — {verdict}")
        power = block["power"]
        if power.get("n_per_group"):
            lines.append(
                f"{'':<22}effect d={power['cohens_d']}, so settling it at 80% power needs "
                f"~{power['n_per_group']} per group (have {block['Non-Native']['n']})"
            )
        lines.append("")
    lines += [
        "The hypothesis rounds 114 and 120 wrote down and refused to assert: that non-native writers",
        "sit further out in function-word space, which would make the L2 false-positive result an",
        "instance of the distance effect. Positive diff = non-native further from the centre.",
        "",
        "n=36 per group, one field, self-declared status. A null here is weak evidence of no",
        "difference; a positive is one corpus's worth of evidence for a mechanism, not proof that it",
        "drives the fairness result — which `eval/assisted_fairness` measures directly.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cache", type=Path, default=REPO / ".assisted-cache")
    parser.add_argument("--vocab", type=int, default=FUNCTION_WORD_VOCAB)
    parser.add_argument("--tier", default="lite")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    report = measure(args.cache, args.vocab, args.tier)
    print(json.dumps(report, indent=2) if args.as_json else _render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
