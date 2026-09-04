"""Precision says how much of what a checker reports is real. Recall says how much it misses.

`eval/checkers.py` records a measured precision for every checker here, each obtained by reading
every finding. Precision and recall answer opposite questions: precision is about the findings,
recall is about the defects. A checker reporting one finding and being right is 100% precise and may
be missing forty.

Precision is measured by reading what came out. Recall has to be measured by putting defects in.

## Why every plant is a PAIR

Round one hundred and six planted six defects for `cache_keys`, got **50% recall with the easy cases
missed**, and nearly published it. A gating checker missing the most basic form of what it exists to
catch is a headline. It was wrong: three plants named their mutable global `_STATE`, and
`"_STATE".isupper()` is **True**, which this repository's convention and the checker's own docstring
both take to mean *immutable*. **The plants contained no defect.** The checker was at 100%.

Precision is inflated by a false finding; recall is deflated by a false plant. Same error mirrored.
What caught it was disbelief and a docstring — a judgement, not a mechanism — and round one hundred
and six said so and left the problem open.

**This is the mechanism.** Every plant is a *minimal edit of its own control*: two sources differing
only by the defect. That makes four outcomes distinguishable where before there were two:

| checker fires on | means |
|---|---|
| defective only | correct — the edit is a real defect and the checker sees it |
| neither | **the plant is empty** — the edit introduced nothing |
| both | **the control is dirty** — the clean side already had a defect |
| clean only | the checker is inverted |

Round one hundred and six's error was the second row, and it was indistinguishable from a miss.
Written as a pair it cannot be: the `cache_keys` plants below differ from their controls **only in
the case of the global's name**, which is exactly the distinction that was got wrong, and writing
the pair forces the author to say which side of the convention each is on.

⚠️ **Recall against easy cases is worthless**, for the same reason the mutation harness needs a
positive control that moves 99.6% of documents rather than one that barely moves any. Each pair is
labelled easy or hard and the split is reported: a checker catching every easy plant and no hard one
has a recall of 60% and a shape that matters more than the number.
"""

from __future__ import annotations

import argparse
import difflib
import json
import textwrap
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Pair:
    """A defect and the clean source it is a minimal edit of."""

    checker: str
    name: str
    hard: bool
    clean: str
    defective: str

    def edit_lines(self) -> int:
        """How many lines differ. A pair differing everywhere isolates nothing."""
        a = textwrap.dedent(self.clean).splitlines()
        b = textwrap.dedent(self.defective).splitlines()
        return sum(1 for line in difflib.ndiff(a, b) if line[:1] in {"+", "-"})


PAIRS: tuple[Pair, ...] = (
    # --- eval.result_keys — the edit is the key name, documented vs not --------------------------
    Pair("result_keys", "subscript", False,
         "def f():\n    r = score_text('x')\n    return r['max']\n",
         "def f():\n    r = score_text('x')\n    return r['nope']\n"),
    Pair("result_keys", "get", False,
         "def f():\n    r = score_text('x')\n    return r.get('max')\n",
         "def f():\n    r = score_text('x')\n    return r.get('nope')\n"),
    Pair("result_keys", "inside a branch", False,
         "def f(flag):\n    r = score_text('x')\n    if flag:\n        return r['max']\n",
         "def f(flag):\n    r = score_text('x')\n    if flag:\n        return r['nope']\n"),
    Pair("result_keys", "in a loop body", False,
         "def f(items):\n    r = score_text('x')\n    for _ in items:\n        print(r['max'])\n",
         "def f(items):\n    r = score_text('x')\n    for _ in items:\n        print(r['nope'])\n"),
    Pair("result_keys", "after an unrelated call", True,
         "def f():\n    r = score_text('x')\n    print(len('abc'))\n    return r['max']\n",
         "def f():\n    r = score_text('x')\n    print(len('abc'))\n    return r['nope']\n"),
    Pair("result_keys", "inside a closure over the result", True,
         "def outer():\n    r = score_text('x')\n\n    def inner():\n"
         "        return r['max']\n    return inner\n",
         "def outer():\n    r = score_text('x')\n\n    def inner():\n"
         "        return r['nope']\n    return inner\n"),
    Pair("result_keys", "inside a comprehension", True,
         "def f(items):\n    r = score_text('x')\n    return [r['max'] for _ in items]\n",
         "def f(items):\n    r = score_text('x')\n    return [r['nope'] for _ in items]\n"),
    Pair("result_keys", "reassigned back to the producer", True,
         "def f():\n    r = {'a': 1}\n    r = score_text('x')\n    return r['max']\n",
         "def f():\n    r = {'a': 1}\n    r = score_text('x')\n    return r['nope']\n"),

    # --- eval.boundaries — the edit turns arithmetic into an ordering comparison -----------------
    Pair("boundaries", "constant on the right", False,
         "_FLOOR = 12\n\n\ndef f(n):\n    return n + _FLOOR\n",
         "_FLOOR = 12\n\n\ndef f(n):\n    return n < _FLOOR\n"),
    Pair("boundaries", "constant on the left", True,
         "_FLOOR = 12\n\n\ndef f(n):\n    return _FLOOR + n\n",
         "_FLOOR = 12\n\n\ndef f(n):\n    return _FLOOR > n\n"),
    Pair("boundaries", "inside a ternary", True,
         "_FLOOR = 12\n\n\ndef f(n):\n    return 'a' if n == _FLOOR else 'b'\n",
         "_FLOOR = 12\n\n\ndef f(n):\n    return 'a' if n >= _FLOOR else 'b'\n"),
    Pair("boundaries", "inside a while", True,
         "_FLOOR = 12\n\n\ndef f(n):\n    while n != _FLOOR:\n        n += 1\n    return n\n",
         "_FLOOR = 12\n\n\ndef f(n):\n    while n < _FLOOR:\n        n += 1\n    return n\n"),
    Pair("boundaries", "inside a comprehension", True,
         "_FLOOR = 12\n\n\ndef f(xs):\n    return [x for x in xs if x == _FLOOR]\n",
         "_FLOOR = 12\n\n\ndef f(xs):\n    return [x for x in xs if x <= _FLOOR]\n"),
    Pair("boundaries", "annotated constant", True,
         "_FLOOR: int = 12\n\n\ndef f(n):\n    return n + _FLOOR\n",
         "_FLOOR: int = 12\n\n\ndef f(n):\n    return n < _FLOOR\n"),
    Pair("boundaries", "float threshold", False,
         "_BAR = 0.75\n\n\ndef f(p):\n    return p + _BAR\n",
         "_BAR = 0.75\n\n\ndef f(p):\n    return p >= _BAR\n"),
    Pair("boundaries", "inside a nested function", True,
         "_FLOOR = 12\n\n\ndef outer():\n    def inner(n):\n        return n + _FLOOR\n"
         "    return inner\n",
         "_FLOOR = 12\n\n\ndef outer():\n    def inner(n):\n        return n < _FLOOR\n"
         "    return inner\n"),

    # --- eval.constant_census — the edit removes the stated reason -------------------------------
    Pair("constant_census", "plain int", False,
         "# MEASURED on 400 samples: seven is where the curve flattens.\n_WIDGETS = 7\n",
         "_WIDGETS = 7\n"),
    Pair("constant_census", "plain float", False,
         "# MEASURED on 6,842 abstracts: 0.42 is the median.\n_RATIO = 0.42\n",
         "_RATIO = 0.42\n"),
    Pair("constant_census", "after a comment that explains nothing", False,
         "# MEASURED: three is the smallest count the estimator accepts.\n_WIDGETS = 7\n",
         "# the widget count\n_WIDGETS = 7\n"),
    Pair("constant_census", "negative", True,
         "# MEASURED: the offset the corpus needs.\n_OFFSET = -3\n",
         "_OFFSET = -3\n"),
    Pair("constant_census", "annotated", True,
         "# MEASURED over 100 runs: nine is the ceiling.\n_LIMIT: int = 9\n",
         "_LIMIT: int = 9\n"),
    Pair("constant_census", "second in an undefended group", True,
         "# MEASURED: both values come from the same fit.\n_A = 1\n_B = 2\n",
         "_A = 1\n_B = 2\n"),

    # --- eval.cache_keys — THE EDIT IS THE CASE OF THE NAME --------------------------------------
    # Upper-case means immutable by this repository's convention and by the checker's own docstring,
    # so the case IS the defect. Round 106 wrote only the defective side, wrote it upper-case, and
    # measured the checker as missing something that was not there. As a pair it is unwritable.
    Pair("cache_keys", "reads a mutable module global", False,
         "from functools import lru_cache\n\n_STATE = {'n': 1}\n\n\n"
         "@lru_cache(maxsize=8)\ndef f(x):\n    return x + _STATE['n']\n",
         "from functools import lru_cache\n\n_state = {'n': 1}\n\n\n"
         "@lru_cache(maxsize=8)\ndef f(x):\n    return x + _state['n']\n"),
    Pair("cache_keys", "zero-argument cached function", False,
         "from functools import lru_cache\n\n_STATE = {'n': 1}\n\n\n"
         "@lru_cache(maxsize=1)\ndef f():\n    return _STATE['n']\n",
         "from functools import lru_cache\n\n_state = {'n': 1}\n\n\n"
         "@lru_cache(maxsize=1)\ndef f():\n    return _state['n']\n"),
    Pair("cache_keys", "cache decorator written as functools.cache", True,
         "import functools\n\n_STATE = {'n': 1}\n\n\n"
         "@functools.cache\ndef f(x):\n    return x + _STATE['n']\n",
         "import functools\n\n_state = {'n': 1}\n\n\n"
         "@functools.cache\ndef f(x):\n    return x + _state['n']\n"),
    # These three edit the READ rather than the name: an impure source replaces a pure one.
    Pair("cache_keys", "reads the environment", True,
         "import os\nfrom functools import lru_cache\n\n\n"
         "@lru_cache(maxsize=8)\ndef f(x):\n    return x + len(os.sep)\n",
         "import os\nfrom functools import lru_cache\n\n\n"
         "@lru_cache(maxsize=8)\ndef f(x):\n    return x + int(os.environ.get('N', '0'))\n"),
    Pair("cache_keys", "reads the clock", True,
         "import time\nfrom functools import lru_cache\n\n\n"
         "@lru_cache(maxsize=8)\ndef f(x):\n    return x + len(time.__name__)\n",
         "import time\nfrom functools import lru_cache\n\n\n"
         "@lru_cache(maxsize=8)\ndef f(x):\n    return x + time.time()\n"),
    Pair("cache_keys", "reads a file", True,
         "from functools import lru_cache\nfrom pathlib import Path\n\n\n"
         "@lru_cache(maxsize=8)\ndef f(x):\n    return x + len(Path('a.txt').name)\n",
         "from functools import lru_cache\nfrom pathlib import Path\n\n\n"
         "@lru_cache(maxsize=8)\ndef f(x):\n    return x + len(Path('a.txt').read_text())\n"),
)


def _write_tree(root: Path, checker: str, source: str) -> None:
    """A minimal repository containing exactly one module."""
    for part in ("untell", "eval", "tests", "docs"):
        (root / part).mkdir(parents=True, exist_ok=True)
    body = textwrap.dedent(source)
    if checker == "result_keys":
        (root / "tests" / "test_planted.py").write_text(body)
    else:
        (root / "untell" / "planted.py").write_text(body)


def _fires(checker: str, root: Path) -> bool:
    from eval import boundaries, cache_keys, constant_census, result_keys

    if checker == "result_keys":
        return bool(result_keys.reads(root, {"score_text": {"max", "flagged"}}))
    if checker == "boundaries":
        return bool(boundaries.boundaries(root))
    if checker == "constant_census":
        return any(not e["justified"] for e in constant_census.named_constants(root))
    if checker == "cache_keys":
        # `findings`, not `cached` — read from the function rather than guessed.
        return bool(cache_keys.audit(root)["findings"])
    raise ValueError(checker)


# The four outcomes of a paired plant. Only the first is a pass; the other three each name a
# different thing that is wrong, and round 106 could not tell them apart.
DETECTED = "detected"
EMPTY_PLANT = "the edit introduced no defect"
DIRTY_CONTROL = "the clean side already had a defect"
INVERTED = "the checker fires on the clean side only"


def classify(pair: Pair, tmp_root: Path, index: int) -> str:
    clean_root = tmp_root / f"clean{index}"
    dirty_root = tmp_root / f"dirty{index}"
    _write_tree(clean_root, pair.checker, pair.clean)
    _write_tree(dirty_root, pair.checker, pair.defective)
    on_clean = _fires(pair.checker, clean_root)
    on_dirty = _fires(pair.checker, dirty_root)
    if on_dirty and not on_clean:
        return DETECTED
    if not on_dirty and not on_clean:
        return EMPTY_PLANT
    if on_dirty and on_clean:
        return DIRTY_CONTROL
    return INVERTED


def measure(tmp_root: Path) -> dict:
    """Classify every pair, and refuse to report a recall if any pair is itself broken."""
    results = [
        {"checker": p.checker, "name": p.name, "hard": p.hard,
         "edit_lines": p.edit_lines(), "outcome": classify(p, tmp_root, i)}
        for i, p in enumerate(PAIRS)
    ]
    broken = [r for r in results if r["outcome"] in {EMPTY_PLANT, DIRTY_CONTROL, INVERTED}]

    by_checker: dict[str, dict] = {}
    for checker in sorted({r["checker"] for r in results}):
        rows = [r for r in results if r["checker"] == checker]
        easy = [r for r in rows if not r["hard"]]
        hard = [r for r in rows if r["hard"]]
        hit = sum(1 for r in rows if r["outcome"] == DETECTED)
        by_checker[checker] = {
            "planted": len(rows), "detected": hit,
            "recall": round(100.0 * hit / len(rows), 1),
            "easy": f"{sum(1 for r in easy if r['outcome'] == DETECTED)}/{len(easy)}",
            "hard": f"{sum(1 for r in hard if r['outcome'] == DETECTED)}/{len(hard)}",
            "missed": [r["name"] for r in rows if r["outcome"] != DETECTED],
        }

    detected = sum(1 for r in results if r["outcome"] == DETECTED)
    return {
        "pairs": len(results),
        "detected": detected,
        "recall": round(100.0 * detected / len(results), 1) if results else 0.0,
        "broken_pairs": broken,
        "by_checker": by_checker,
        "results": results,
    }


def render(report: dict) -> str:
    lines: list[str] = []
    if report["broken_pairs"]:
        lines += [
            "⚠️ REFUSING TO REPORT A RECALL: these pairs are broken, and a broken pair is scored as",
            "   a miss the checker did not commit — which is exactly how round 106 published 50%:",
            *(f"     {b['checker']}/{b['name']}: {b['outcome']}" for b in report["broken_pairs"]),
            "",
        ]
    lines += [
        f"{report['pairs']} paired plants, {report['detected']} detected — "
        f"recall {report['recall']}%.",
        "",
        f"  {'checker':<20} {'recall':>7} {'easy':>7} {'hard':>7}  not detected",
    ]
    for checker, row in report["by_checker"].items():
        lines.append(f"  {checker:<20} {row['recall']:>6.1f}% {row['easy']:>7} {row['hard']:>7}  "
                     f"{', '.join(row['missed']) or '—'}")
    lines += [
        "",
        "Every plant is a minimal edit of its own control, so a plant containing no defect shows up",
        "as its own outcome rather than as a miss. Round 106 had only the defective half and",
        "reported a checker at 50% that was at 100%.",
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
    return 1 if report["broken_pairs"] else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
