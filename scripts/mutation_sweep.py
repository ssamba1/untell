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
    # --- second sweep -----------------------------------------------------------------------
    ("untell/calibrate.py",
     "rank = math.ceil((n + 1) * (1.0 - alpha))", "rank = math.ceil(n * (1.0 - alpha))",
     "tests/test_calibrate_bounds_the_false_positive_rate.py",
     "drop the finite-sample correction: the conformal bound stops holding"),
    ("untell/calibrate.py",
     "threshold = scores[rank - 1]", "threshold = scores[rank]",
     "tests/test_calibrate_bounds_the_false_positive_rate.py",
     "off-by-one in the conformal threshold"),
    ("untell/scripts/score.py",
     '"degenerate": total == 1,', '"degenerate": total == 0,',
     "tests/test_the_aggregation_rules_obey_their_own_arithmetic.py",
     "degenerate never fires: a single-detector run stops warning it is one measurement"),
    ("untell/scripts/score.py",
     "flagging = sum(1 for v in numeric if v >= verdict_threshold)",
     "flagging = sum(1 for v in numeric if v > verdict_threshold)",
     "tests/test_agreement_reports_the_aggregation_spread.py",
     "threshold boundary becomes exclusive, disagreeing with `flagged`"),
    ("eval/assisted_fairness.py",
     '"length_matched": worst < 0.15,', '"length_matched": worst < 1.5,',
     "tests/test_the_fairness_arms_check_for_the_length_confound.py",
     "length-balance bar loosened tenfold: nothing is ever unmatched"),
    ("eval/outlier_fairness.py",
     '"ttr": len(set(words)) / len(words),', '"ttr": len(words) / len(words),',
     "tests/test_outlier_fairness_measures_margins_without_labels.py",
     "type-token ratio becomes a constant"),
    ("eval/length_standardized.py",
     "if low <= words < high:", "if low <= words <= high:",
     "tests/test_length_standardization_compares_like_with_like.py",
     "band boundaries overlap: a document counts in two bands and weights exceed 1"),
    ("eval/pre_llm_fpr.py",
     "if len(paper[\"abstract\"].split()) >= min_words:",
     "if len(paper[\"abstract\"].split()) >= 0:",
     "tests/test_the_pre_llm_report_says_which_corpus_it_describes.py",
     "the corpus word floor stops filtering"),
    # --- third sweep: the download guard, the evidence surface, the survey filter -------------
    ("eval/litreview.py",
     "if papers == 0:", "if papers < 0:",
     "tests/test_litreview_download_survives_a_truncated_transfer.py",
     "stop rejecting paperless volumes: 743-byte stubs cache as real volumes again"),
    ("eval/litreview.py",
     "if len(body) < 200:", "if len(body) < 0:",
     "tests/test_litreview_download_survives_a_truncated_transfer.py",
     "drop the byte floor: an error page caches as a volume"),
    ("untell/scripts/score.py",
     '"any": flagging >= 1,', '"any": flagging >= 0,',
     "tests/test_the_aggregation_rules_obey_their_own_arithmetic.py",
     "union always fires: every text is flagged under the rule `flagged` reports"),
    ("untell/scripts/sentences.py",
     'row["evidence"] = _evidence_for(s)', 'row["evidence"] = {"tells": 0, "matches": {}}',
     "tests/test_per_sentence_evidence_is_corroboration_not_explanation.py",
     "per-sentence evidence returns nothing: markers silently disappear"),
    ("untell/scripts/sentences.py",
     "if evidence:", "if not evidence:",
     "tests/test_per_sentence_evidence_is_corroboration_not_explanation.py",
     "evidence attaches when NOT asked for, and not when asked"),
    ("eval/outlier_fairness.py",
     "kept_texts.append(text)", "pass",
     "tests/test_outlier_fairness_measures_margins_without_labels.py",
     "_score_all stops returning kept texts: the alignment bug comes back"),
    ("untell/calibrate.py",
     "if n < required_samples(alpha):", "if n < 0:",
     "tests/test_calibrate_bounds_the_false_positive_rate.py",
     "calibrate stops refusing samples too small for the requested alpha"),
    ("eval/assisted_fairness.py",
     "if len(text.split()) < min_words:", "if len(text.split()) < 0:",
     "tests/test_the_fairness_arms_check_for_the_length_confound.py",
     "the length-balance check stops applying its own word floor"),
)


# The coarse companion to MUTANTS. A mutant asks whether a test notices ONE broken line; this asks
# whether a test file notices its module being broken ENTIRELY. It cannot catch a weak assertion —
# one alert test carries the file — but it catches the failure this session hit four rounds running:
# a test that passes for a reason unrelated to what it is testing, because it patched the wrong
# constant, or scored a fixture the code under test never saw.
VACUITY_PAIRS: tuple[tuple[str, str], ...] = (
    ("tests/test_outlier_fairness_measures_margins_without_labels.py", "eval/outlier_fairness.py"),
    ("tests/test_length_standardization_compares_like_with_like.py", "eval/length_standardized.py"),
    ("tests/test_wilson_intervals_are_arithmetically_sound.py", "eval/pre_llm_fpr.py"),
    ("tests/test_the_aggregation_rules_obey_their_own_arithmetic.py", "untell/scripts/score.py"),
    ("tests/test_the_fairness_arms_check_for_the_length_confound.py", "eval/assisted_fairness.py"),
    ("tests/test_per_sentence_evidence_is_corroboration_not_explanation.py",
     "untell/scripts/sentences.py"),
    ("tests/test_the_pre_llm_report_says_which_corpus_it_describes.py", "eval/pre_llm_fpr.py"),
    ("tests/test_litreview_download_survives_a_truncated_transfer.py", "eval/litreview.py"),
    ("tests/test_the_headline_number_says_what_kind_of_number_it_is.py", "untell/api_server.py"),
    ("tests/test_the_dead_function_check_is_fast_and_still_works.py", "untell/scripts/audit.py"),
    ("tests/test_every_corpus_the_evals_need_can_still_be_built.py", "eval/litreview.py"),
)


def sabotage(source: str) -> str:
    """Replace every public function body — module level AND inside classes — with a raise.

    Methods matter as much as functions here, and for a while this walked only `tree.body`. Most of
    this repository's detectors and rewriters are CLASSES, so their substance was never touched: the
    sweep reported `test_binoculars_dead_latch.py` as passing against a "broken"
    `untell/detectors/binoculars.py` when `BinocularsDetector` had not been altered at all. Twelve
    of the thirty-two apparent survivors were that.

    Dunders are left alone deliberately. `__init__` and `__getattr__` are how a module and its
    objects load, so breaking them turns "the test noticed" into "nothing could import", which is a
    different and much weaker signal.
    """
    import ast

    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    edits = []

    def collect(body):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("__"):
                    continue
                start = node.body[0].lineno - 1
                indent = len(lines[start]) - len(lines[start].lstrip())
                edits.append((start, node.body[-1].end_lineno,
                              " " * indent + 'raise AssertionError("sabotaged")\n'))
            elif isinstance(node, ast.ClassDef):
                collect(node.body)

    collect(tree.body)
    for start, end, replacement in sorted(edits, reverse=True):
        lines[start:end] = [replacement]
    return "".join(lines)


def vacuity(pairs=VACUITY_PAIRS) -> int:
    vacuous = []
    for testfile, module in pairs:
        source = REPO / module
        original = source.read_text(encoding="utf-8")
        try:
            source.write_text(sabotage(original), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "pytest", testfile, "-q", "-p", "no:randomly", "-x"],
                cwd=REPO, capture_output=True, text=True, timeout=900)
            noticed = result.returncode != 0
        finally:
            source.write_text(original, encoding="utf-8")
        print(f"{'NOTICED ' if noticed else 'VACUOUS '} {pathlib.Path(testfile).name:<62} "
              f"<- {module}")
        if not noticed:
            vacuous.append(testfile)
    print(f"\n{len(pairs) - len(vacuous)}/{len(pairs)} noticed")
    if vacuous:
        print("\nThese test files pass with their module completely broken:")
        for v in vacuous:
            print(f"  - {v}")
    return 1 if vacuous else 0


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
    parser.add_argument("--vacuity", action="store_true",
                        help="coarse check: break each module entirely, require its test file to "
                             "fail")
    args = parser.parse_args(argv)
    if args.list:
        for path, _old, _new, _t, label in MUTANTS:
            print(f"{path:<32} {label}")
        return 0
    if _dirty():
        print("refusing to run on a dirty working tree: this edits source files and restores them "
              "from memory, so a crash between the two would lose uncommitted work.", file=sys.stderr)
        return 2
    return vacuity() if args.vacuity else run()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
