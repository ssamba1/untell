"""Precision says how much of what a checker reports is real. Recall says how much it misses.

`eval/checkers.py` records a measured precision for all eight checkers here, each obtained by
reading every finding. **None of them has a measured recall**, and the two answer opposite questions:
precision is about the findings, recall is about the defects. A checker that reports one finding and
is right is 100% precise and may be missing forty.

Precision was measured by reading what came out. Recall has to be measured by putting defects in:
plant a known instance of exactly what a checker claims to catch, run it, and see whether it fires.

⚠️ **A malformed plant scores the checker as missing a defect that is not there.** Recall is
deflated by bad plants exactly as precision is inflated by false findings, and the fix is the same:
verify each one. MEASURED in round one hundred and six, three of six `cache_keys` plants named their
mutable global `_STATE` — upper-case, which this repository's convention and the checker's own
docstring both take to mean immutable. The checker was reported at **50% recall** and is at 100%;
the defect was in the plants. Every plant now has a paired negative case that must NOT fire, which
is the only mechanical guard against a plant that contains nothing.

⚠️ **Recall against easy cases is worthless**, for the same reason the mutation harness needs a
positive control that moves 99.6% of documents rather than one that barely moves any. Every checker
here is planted with the forms a naive implementation gets right AND the forms it gets wrong —
nested scopes, comprehensions, ternaries, reversed operands, annotated assignments. The rate is
reported per form, because a checker that catches 6 of 6 easy plants and 0 of 4 hard ones has a
recall of 60% and a shape that matters more than the number.
"""

from __future__ import annotations

import argparse
import json
import textwrap
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Plant:
    """One synthetic defect, and how hard it is to see."""

    checker: str
    name: str
    hard: bool
    source: str
    """A module body written into the synthetic tree."""


PLANTS: tuple[Plant, ...] = (
    # --- eval.result_keys: a caller reading a key its function never returns -------------------
    Plant("result_keys", "subscript", False,
          "def f():\n    r = score_text('x')\n    return r['nope']\n"),
    Plant("result_keys", "get", False,
          "def f():\n    r = score_text('x')\n    return r.get('nope')\n"),
    Plant("result_keys", "inside a branch", False,
          "def f(flag):\n    r = score_text('x')\n    if flag:\n        return r['nope']\n"),
    Plant("result_keys", "after an unrelated call", True,
          "def f():\n    r = score_text('x')\n    print(len('abc'))\n    return r['nope']\n"),
    Plant("result_keys", "inside a nested function that closes over it", True,
          "def outer():\n    r = score_text('x')\n\n    def inner():\n"
          "        return r['nope']\n    return inner\n"),
    Plant("result_keys", "inside a comprehension", True,
          "def f(items):\n    r = score_text('x')\n    return [r['nope'] for _ in items]\n"),
    Plant("result_keys", "in a loop body", False,
          "def f(items):\n    r = score_text('x')\n    for _ in items:\n        print(r['nope'])\n"),
    Plant("result_keys", "reassigned back to the producer", True,
          "def f():\n    r = {'a': 1}\n    r = score_text('x')\n    return r['nope']\n"),

    # --- eval.boundaries: a comparison against a named threshold -------------------------------
    Plant("boundaries", "constant on the right", False,
          "_FLOOR = 12\n\ndef f(n):\n    return n < _FLOOR\n"),
    Plant("boundaries", "constant on the left", True,
          "_FLOOR = 12\n\ndef f(n):\n    return _FLOOR > n\n"),
    Plant("boundaries", "inside a ternary", True,
          "_FLOOR = 12\n\ndef f(n):\n    return 'a' if n >= _FLOOR else 'b'\n"),
    Plant("boundaries", "inside a while", True,
          "_FLOOR = 12\n\ndef f(n):\n    while n < _FLOOR:\n        n += 1\n    return n\n"),
    Plant("boundaries", "inside a comprehension", True,
          "_FLOOR = 12\n\ndef f(xs):\n    return [x for x in xs if x <= _FLOOR]\n"),
    Plant("boundaries", "annotated constant", True,
          "_FLOOR: int = 12\n\ndef f(n):\n    return n < _FLOOR\n"),
    Plant("boundaries", "float threshold", False,
          "_BAR = 0.75\n\ndef f(p):\n    return p >= _BAR\n"),
    Plant("boundaries", "inside a nested function", True,
          "_FLOOR = 12\n\ndef outer():\n    def inner(n):\n        return n < _FLOOR\n"
          "    return inner\n"),

    # --- eval.constant_census: a numeric constant with no stated reason ------------------------
    Plant("constant_census", "plain int", False, "_WIDGETS = 7\n"),
    Plant("constant_census", "plain float", False, "_RATIO = 0.42\n"),
    Plant("constant_census", "negative", True, "_OFFSET = -3\n"),
    Plant("constant_census", "annotated", True, "_LIMIT: int = 9\n"),
    Plant("constant_census", "second in an undefended group", True, "_A = 1\n_B = 2\n"),
    Plant("constant_census", "after a comment that explains nothing", False,
          "# the widget count\n_WIDGETS = 7\n"),

    # --- eval.cache_keys: a cached function reading state its key does not name -----------------
    Plant("cache_keys", "reads a mutable module global", False,
          "from functools import lru_cache\n\n_state = {'n': 1}\n\n"
          "@lru_cache(maxsize=8)\ndef f(x):\n    return x + _state['n']\n"),
    Plant("cache_keys", "reads the environment", True,
          "import os\nfrom functools import lru_cache\n\n"
          "@lru_cache(maxsize=8)\ndef f(x):\n    return x + int(os.environ.get('N', '0'))\n"),
    Plant("cache_keys", "reads the clock", True,
          "import time\nfrom functools import lru_cache\n\n"
          "@lru_cache(maxsize=8)\ndef f(x):\n    return x + time.time()\n"),
    Plant("cache_keys", "reads a file", True,
          "from functools import lru_cache\nfrom pathlib import Path\n\n"
          "@lru_cache(maxsize=8)\ndef f(x):\n    return x + len(Path('a.txt').read_text())\n"),
    Plant("cache_keys", "cache decorator written as functools.cache", True,
          "import functools\n\n_state = {'n': 1}\n\n"
          "@functools.cache\ndef f(x):\n    return x + _state['n']\n"),
    Plant("cache_keys", "zero-argument cached function", False,
          "from functools import lru_cache\n\n_state = {'n': 1}\n\n"
          "@lru_cache(maxsize=1)\ndef f():\n    return _state['n']\n"),
)


# For each checker, a module that contains NO defect of its kind. A checker firing on one of these
# scores 100% recall for the wrong reason — it would fire on anything — and a plant that turns out
# to contain nothing is scored as a miss it did not commit. Round one hundred and six needed both
# halves: three `cache_keys` plants named a mutable global in upper case, which the checker's own
# documented convention reads as immutable, and the checker was reported at 50% when it was at 100%.
CLEAN: dict[str, str] = {
    "result_keys": "def f():\n    r = score_text('x')\n    return r['max']\n",
    "boundaries": (
        "# MEASURED over 100 samples: twelve is where the rate stops moving.\n"
        "_FLOOR = 12\n\n\ndef f(n):\n    return n + _FLOOR\n"
    ),
    "constant_census": (
        "# MEASURED on 6,842 abstracts: this is where the curve flattens.\n_RATIO = 0.42\n"
    ),
    "cache_keys": (
        "import re\nfrom functools import lru_cache\n\n_PATTERN = re.compile(r'x')\n\n"
        "@lru_cache(maxsize=8)\ndef f(text):\n    return bool(_PATTERN.search(text))\n"
    ),
}


def _write_tree(root: Path, plant: Plant) -> None:  # noqa: C901
    """A minimal repository containing exactly one planted defect."""
    (root / "untell").mkdir(parents=True, exist_ok=True)
    (root / "eval").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    body = textwrap.dedent(plant.source)
    if plant.checker == "result_keys":
        (root / "tests" / "test_planted.py").write_text(body)
    else:
        (root / "untell" / "planted.py").write_text(body)


def _detects(plant: Plant, root: Path) -> bool:
    from eval import boundaries, cache_keys, constant_census, result_keys

    if plant.checker == "cache_keys":
        # `findings`, not `cached` — read from the function rather than guessed. A first draft used
        # `cached` and would have scored every cache_keys plant as MISSED, which is the same
        # wrong-key failure `eval/result_keys.py` exists to catch, in the recall tool for it.
        return bool(cache_keys.audit(root)["findings"])
    if plant.checker == "result_keys":
        return bool(result_keys.reads(root, {"score_text": {"max", "flagged"}}))
    if plant.checker == "boundaries":
        return bool(boundaries.boundaries(root))
    if plant.checker == "constant_census":
        found = constant_census.named_constants(root)
        return any(not entry["justified"] for entry in found)
    raise ValueError(plant.checker)


def clean_fires(tmp_root: Path) -> dict[str, bool]:
    """Does each checker fire on a module containing no defect of its kind? It must not."""
    fired: dict[str, bool] = {}
    for checker, source in CLEAN.items():
        root = tmp_root / f"clean-{checker}"
        probe = Plant(checker, "clean control", False, source)
        _write_tree(root, probe)
        fired[checker] = _detects(probe, root)
    return fired


def measure(tmp_root: Path) -> dict:
    """Plant each defect in its own tree and record whether the checker fires."""
    results: list[dict] = []
    for index, plant in enumerate(PLANTS):
        root = tmp_root / f"plant{index}"
        _write_tree(root, plant)
        results.append({
            "checker": plant.checker, "name": plant.name, "hard": plant.hard,
            "detected": _detects(plant, root),
        })

    by_checker: dict[str, dict] = {}
    for checker in sorted({r["checker"] for r in results}):
        rows = [r for r in results if r["checker"] == checker]
        easy = [r for r in rows if not r["hard"]]
        hard = [r for r in rows if r["hard"]]
        by_checker[checker] = {
            "planted": len(rows),
            "detected": sum(1 for r in rows if r["detected"]),
            "recall": round(100.0 * sum(1 for r in rows if r["detected"]) / len(rows), 1),
            "easy": f"{sum(1 for r in easy if r['detected'])}/{len(easy)}",
            "hard": f"{sum(1 for r in hard if r['detected'])}/{len(hard)}",
            "missed": [r["name"] for r in rows if not r["detected"]],
        }
    controls = clean_fires(tmp_root)
    return {
        "clean_controls_fired": [c for c, fired in controls.items() if fired],
        "planted": len(results),
        "detected": sum(1 for r in results if r["detected"]),
        "recall": round(100.0 * sum(1 for r in results if r["detected"]) / len(results), 1),
        "by_checker": by_checker,
        "results": results,
    }


def render(report: dict) -> str:
    lines = []
    if report.get("clean_controls_fired"):
        lines += [
            "⚠️ REFUSING TO REPORT: these checkers fire on a module containing no defect of their "
            "kind, so\n   a recall of 100% would mean only that they fire on anything: "
            + ", ".join(report["clean_controls_fired"]),
            "",
        ]
    lines += [
        f"{report['planted']} defects planted, {report['detected']} detected — "
        f"recall {report['recall']}%.",
        "",
        f"  {'checker':<20} {'recall':>7} {'easy':>7} {'hard':>7}  missed",
    ]
    for checker, row in report["by_checker"].items():
        lines.append(f"  {checker:<20} {row['recall']:>6.1f}% {row['easy']:>7} {row['hard']:>7}  "
                     f"{', '.join(row['missed']) or '—'}")
    lines += [
        "",
        "Recall against easy cases only is worthless, which is why the split is reported. A checker",
        "catching every easy plant and no hard one has a shape that matters more than its rate.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import tempfile

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        report = measure(Path(tmp))
    print(json.dumps(report, indent=2) if args.as_json else render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
