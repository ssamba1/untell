"""Break the code on purpose and check that a test notices.

`tests/test_audit_mutation_guards.py` documents the repository's existing practice: run a mutation
sweep, then write a killing test for every survivor. This makes that sweep repeatable for the
statistical machinery, where a surviving mutant is worst — a detector that scores slightly wrong is
visible, an interval that is slightly too narrow turns an honest negative into a finding.

It found three survivors on its first run, all in code written the same day:

  * `outlier_scores` median -> mean, and MAD -> standard deviation. The robustness test asserted only
    that an odd document scored above 1.0, a bar a non-robust implementation clears easily. Both
    substitutions survived, which means the test was checking that the function returned a number.
  * the margin cut off by one. Every assertion in that file was about rates and signs, and none
    about how many documents landed on each side, so a cut that took 21 documents instead of 20
    changed nothing any test looked at.

Usage:  python scripts/mutation_sweep.py [--list]

Refuses to run on a dirty working tree: it edits source files and restores them from memory, so a
crash between the two would otherwise lose real work.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent

# (file, original, mutated, tests that must fail, what the mutation means)
MUTANTS: tuple[tuple[str, str, str, str, str], ...] = (
    ("eval/outlier_fairness.py",
     "med = statistics.median(values)", "med = statistics.fmean(values)",
     "tests/test_outlier_fairness_measures_margins_without_labels.py",
     "robust centre -> mean: outliers set the scale they are measured against"),
    ("eval/outlier_fairness.py",
     "mad = statistics.median([abs(v - med) for v in values]) or 1e-9",
     "mad = statistics.pstdev(values) or 1e-9",
     "tests/test_outlier_fairness_measures_margins_without_labels.py",
     "robust scale -> standard deviation"),
    ("eval/outlier_fairness.py",
     "cut = sorted(distances, reverse=True)[max(1, int(len(distances) * quantile)) - 1]",
     "cut = sorted(distances, reverse=True)[max(1, int(len(distances) * quantile))]",
     "tests/test_outlier_fairness_measures_margins_without_labels.py",
     "off-by-one in the margin cut"),
    ("eval/outlier_fairness.py",
     'keys = [k for k in rows[0] if k != "words"] + ["words"]',
     'keys = [k for k in rows[0] if k != "words"]',
     "tests/test_outlier_fairness_measures_margins_without_labels.py",
     "silently drop length from the feature set"),
    ("eval/length_standardized.py",
     'expected = sum(w / coverage * band_rates[b]["fpr"] for b, w in usable.items())',
     'expected = sum(w * band_rates[b]["fpr"] for b, w in usable.items())',
     "tests/test_length_standardization_compares_like_with_like.py",
     "drop the coverage renormalisation: standardized rates silently deflate"),
    ("untell/scripts/score.py",
     '"majority": flagging * 2 > total,', '"majority": flagging * 2 >= total,',
     "tests/test_the_aggregation_rules_obey_their_own_arithmetic.py",
     "majority becomes 'at least half', breaking the rule ordering"),
    ("untell/scripts/score.py",
     '"unanimous": flagging == total,', '"unanimous": flagging >= total - 1,',
     "tests/test_the_aggregation_rules_obey_their_own_arithmetic.py",
     "unanimous becomes 'all but one'"),
    ("eval/pre_llm_fpr.py",
     "margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator",
     "margin = z * math.sqrt(p * (1 - p) / total) / denominator",
     "tests/test_wilson_intervals_are_arithmetically_sound.py",
     "drop Wilson's continuity term: intervals narrow toward the normal approximation"),
    ("eval/pre_llm_fpr.py",
     "centre = (p + z * z / (2 * total)) / denominator", "centre = p / denominator",
     "tests/test_wilson_intervals_are_arithmetically_sound.py",
     "drop Wilson's centre shift"),
)


def _dirty() -> bool:
    out = subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                         capture_output=True, text=True).stdout
    return any(line for line in out.splitlines() if not line.startswith("??"))


def run(mutants=MUTANTS) -> int:
    survivors = []
    for path, old, new, testfile, label in mutants:
        source = REPO / path
        original = source.read_text(encoding="utf-8")
        if old not in original:
            print(f"STALE     {label}\n          pattern no longer in {path}")
            survivors.append(label)
            continue
        source.write_text(original.replace(old, new, 1), encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", testfile, "-q", "-x", "-p", "no:randomly"],
                cwd=REPO, capture_output=True, text=True, timeout=900)
            killed = result.returncode != 0
        finally:
            source.write_text(original, encoding="utf-8")
        print(f"{'KILLED  ' if killed else 'SURVIVED'}  {label}")
        if not killed:
            survivors.append(label)
    print(f"\n{len(mutants) - len(survivors)}/{len(mutants)} killed")
    if survivors:
        print("\nSurvivors need a killing test, not an exemption:")
        for s in survivors:
            print(f"  - {s}")
    return 1 if survivors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--list", action="store_true", help="show the mutants without running them")
    args = parser.parse_args(argv)
    if args.list:
        for path, _old, _new, _t, label in MUTANTS:
            print(f"{path:<32} {label}")
        return 0
    if _dirty():
        print("refusing to run on a dirty working tree: this edits source files and restores them "
              "from memory, so a crash between the two would lose uncommitted work.", file=sys.stderr)
        return 2
    return run()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
