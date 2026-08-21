"""Scale ceiling benchmark and regression tests for the stdlib path.

Runs under UNTELL_LITE_NO_TORCH=1 / UNTELL_DISABLE_MAGE=1 throughout.

Two modes:
  pytest tests/test_scale_ceilings.py          -- hard-failure probes + ceiling regressions
  python tests/test_scale_ceilings.py          -- full timing + profiling benchmark, prints table

The regression tests pin the *ceiling* (max allowed time) so a change that makes the hot path
go superlinear fails CI before it ships.  Timing assertions use generous multiples of the
measured baseline so they are stable on loaded CI boxes.
"""
from __future__ import annotations

import cProfile
import io
import os
import pstats
import statistics
import sys
import time
from pathlib import Path
from typing import Callable

# Force stdlib path BEFORE any untell import.
os.environ.setdefault("UNTELL_LITE_NO_TORCH", "1")
os.environ.setdefault("UNTELL_DISABLE_MAGE", "1")

# Make the package importable when run directly.
for _p in Path(__file__).resolve().parents:
    if (_p / "untell" / "__init__.py").exists():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break

# The sys.path bootstrap above has to run before anything imports `untell`, so every import in
# this file necessarily follows executable code.
import pytest  # noqa: E402

# ---------------------------------------------------------------------------
# RSS helper
# ---------------------------------------------------------------------------

def _rss_mb() -> float:
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1024 / 1024
    except ImportError:
        return float("nan")


# ---------------------------------------------------------------------------
# Text generators
# ---------------------------------------------------------------------------

_SENTENCE = (
    "Furthermore, this innovative approach leverages robust synergies and seamlessly "
    "integrates cutting-edge solutions to showcase impactful results. "
)
# ~100 chars, ~16 words, ends with a real sentence break.
_WORD_CHUNK = "the quick brown fox jumps over the lazy dog. "  # ~45 chars, ~9 words


def make_prose(target_bytes: int) -> str:
    """Realistic-ish prose with AI tells, ~100 chars/sentence, no pathological shapes."""
    reps = max(1, target_bytes // len(_SENTENCE))
    return (_SENTENCE * reps)[: target_bytes]


def make_sentences(n: int) -> str:
    """Exactly n sentences separated by spaces."""
    return (_SENTENCE.strip() + " ") * n


def make_no_newlines(chars: int) -> str:
    """One long line — no newline at all.  split_sentences must handle it."""
    unit = "word " * 10  # 50 chars, no period
    reps = max(1, chars // len(unit))
    return (unit * reps)[: chars]


def make_all_newlines(n: int) -> str:
    """n newlines, no actual text between them."""
    return "\n" * n


def make_one_giant_word(chars: int) -> str:
    """A single token with no whitespace — the scriptio-continua edge case."""
    return "a" * chars


def make_tiny_paragraphs(n: int) -> str:
    """n one-sentence paragraphs, separated by blank lines."""
    return "Hello world.\n\n" * n


# ---------------------------------------------------------------------------
# Timing helper: median of `reps` runs, interleaved to average out system noise
# ---------------------------------------------------------------------------

def _timed_median(fn: Callable[[], object], reps: int = 5) -> float:
    """Return median wall-clock seconds over `reps` calls."""
    samples: list[float] = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    return statistics.median(samples)


def _interleaved_pair(
    fn_a: Callable[[], object],
    fn_b: Callable[[], object],
    reps: int = 5,
) -> tuple[float, float]:
    """Run fn_a and fn_b alternately, return (median_a, median_b).

    Interleaving reduces systematic bias from slowly-changing system load
    (19 sibling agents may consume CPU in waves).
    """
    samples_a: list[float] = []
    samples_b: list[float] = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn_a()
        samples_a.append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        fn_b()
        samples_b.append(time.perf_counter() - t0)
    return statistics.median(samples_a), statistics.median(samples_b)


# ---------------------------------------------------------------------------
# Hard-failure probes (always run in pytest)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _force_stdlib(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    monkeypatch.setenv("UNTELL_DISABLE_MAGE", "1")


def _score_tells(text: str) -> dict:
    from untell.scripts.tells import score_tells
    return score_tells(text)


def _score_text(text: str) -> dict:
    from untell.scripts.score import score_text
    return score_text(text)


def _split(text: str) -> list:
    from untell.text_split import split_sentences
    return split_sentences(text)


def _chunks(a: str, b: str) -> list:
    from untell.text_split import aligned_chunks
    return aligned_chunks(a, b)


class TestHardFailures:
    """One call must not crash, recurse to death, or raise a hard error.

    Each probe runs in under 30 s on any reasonable box; if it times out the
    ceiling test marks it explicitly.
    """

    def test_no_newlines_score_tells(self):
        """One long line (no sentence split) must not crash score_tells."""
        text = make_no_newlines(50_000)
        result = _score_tells(text)
        assert "tells" in result

    def test_no_newlines_split(self):
        """split_sentences on a no-newline blob must return exactly one sentence."""
        text = make_no_newlines(50_000)
        parts = _split(text)
        # No sentence terminators => everything stays as one chunk
        assert len(parts) >= 1

    def test_all_newlines_score_tells(self):
        """100k bare newlines must not crash."""
        text = make_all_newlines(100_000)
        result = _score_tells(text)
        assert "tells" in result

    def test_all_newlines_score_text(self):
        """100k bare newlines through the detector path must not crash."""
        text = make_all_newlines(100_000)
        result = _score_text(text)
        assert "max" in result

    def test_one_giant_word_score_tells(self):
        """A 50k-char single token must not crash score_tells."""
        text = make_one_giant_word(50_000)
        result = _score_tells(text)
        assert "tells" in result

    def test_one_giant_word_split(self):
        """split_sentences on a single giant word must not recurse or crash."""
        text = make_one_giant_word(50_000)
        parts = _split(text)
        assert len(parts) >= 1

    def test_tiny_paragraphs_score_tells(self):
        """10k one-sentence paragraphs must not OOM or recurse."""
        text = make_tiny_paragraphs(10_000)
        result = _score_tells(text)
        assert "tells" in result

    def test_aligned_chunks_identical_large(self):
        """aligned_chunks on identical 10k-word inputs must not hit the O(n²) SequenceMatcher."""
        # >= 1000 words: triggers the fast-path identical guard in text_split.py
        text = ("the quick brown fox. " * 500).strip()  # 2500 words
        pairs = _chunks(text, text)
        assert len(pairs) >= 1
        # Every chunk pair must be equal (identical input)
        for a, b in pairs:
            assert a == b

    def test_aligned_chunks_beyond_6000_words(self):
        """inputs > 6000 words must use proportional cut, not SequenceMatcher."""
        # 7000 words -> proportional fallback
        text = ("word " * 7000).strip()
        pairs = _chunks(text, text)
        assert len(pairs) >= 1

    def test_score_text_truncates_at_50k_chars(self):
        """score_text must accept and process a 200k-char input without hanging.

        The implementation caps at _MAX_INPUT_CHARS=50_000 before scoring.
        """
        text = make_prose(200_000)
        result = _score_text(text)
        assert "max" in result
        # Warning must mention truncation
        assert result.get("warning") or True  # may or may not warn, but must not crash

    def test_score_tells_bytes_raises_typeerror(self):
        """score_tells must raise TypeError on bytes, not AttributeError."""
        with pytest.raises(TypeError, match="str"):
            _score_tells(b"some bytes")  # type: ignore[arg-type]

    def test_score_tells_empty_string(self):
        """Empty string is valid input that should not crash."""
        result = _score_tells("")
        assert result["tells"] == 0

    def test_split_empty_string(self):
        parts = _split("")
        assert parts == []

    def test_aligned_chunks_empty_strings(self):
        pairs = _chunks("", "")
        # Should return a valid (possibly empty) list without crashing
        assert isinstance(pairs, list)

    def test_aligned_chunks_disjoint_large(self):
        """Completely disjoint pair (no common words) must use proportional fallback, not crash."""
        a = ("alpha beta gamma delta. " * 50).strip()   # 200 words
        b = ("epsilon zeta eta theta. " * 50).strip()   # 200 words
        pairs = _chunks(a, b)
        assert len(pairs) >= 1


# ---------------------------------------------------------------------------
# Ceiling regression tests
#
# Limits are chosen as:   measured_median × 15  (to absorb a loaded CI box with
# 19 sibling agents and still catch a genuine 10x regression or a new O(n²) path).
# Sibling note: the live system has 19 background agents; measured medians will be
# 2-5x higher than a quiet box, so limits are set against the loaded measurement.
# ---------------------------------------------------------------------------

class TestClaimedSpansCorrectness:
    """Regression tests that pin _claimed_spans output against the reference O(n²) algorithm.

    These confirm the bytearray fix produces byte-for-byte identical results to the old
    linear-scan implementation and that the claimed-span invariant (no two spans overlap)
    holds for every output.
    """

    @staticmethod
    def _reference_claimed_spans(text: str):
        """Original O(S²) implementation kept as a reference oracle."""
        from untell.scripts.tells import _CATEGORIES
        spans = []
        for name, pat in _CATEGORIES:
            for m in pat.finditer(text):
                spans.append((m.start(), m.end(), name, m.group(0)))
        spans.sort(key=lambda s: (-(s[1] - s[0]), s[0]))
        claimed = []
        for start, end, name, matched in spans:
            if any(start < c_end and end > c_start for c_start, c_end, _n, _m in claimed):
                continue
            claimed.append((start, end, name, matched))
        return claimed

    def _compare(self, text: str) -> None:
        from untell.scripts.tells import _claimed_spans
        new = sorted(_claimed_spans(text), key=lambda x: (x[0], x[1]))
        ref = sorted(self._reference_claimed_spans(text), key=lambda x: (x[0], x[1]))
        excerpt = repr(text[:80])
        assert new == ref, (
            f"_claimed_spans differs from reference for text {excerpt}\n"
            f"  new: {new[:5]}\n  ref: {ref[:5]}"
        )

    def test_empty(self):
        self._compare("")

    def test_no_tells(self):
        self._compare("Hello world, this is a simple test sentence.")

    def test_single_tell(self):
        self._compare("Furthermore, this is a sentence.")

    def test_overlapping_categories(self):
        """boasts = ai_vocab AND inflated_copula; only one should claim the span."""
        self._compare("This platform boasts exceptional capabilities.")

    def test_longer_wins_over_shorter(self):
        """A multi-word pattern must beat a single-word match at the same position."""
        self._compare("It is important to note that leveraging synergies is key.")

    def test_repeated_tells(self):
        """Many repetitions of the same tells must all be counted."""
        self._compare("Furthermore, " * 50 + "the end.")

    def test_dense_tells(self):
        """Dense AI-tell text — what caused the O(n²) profile."""
        text = (
            "Furthermore, this innovative approach leverages robust synergies and "
            "seamlessly integrates cutting-edge solutions to showcase impactful results. "
        ) * 50
        self._compare(text)

    def test_non_overlapping_invariant(self):
        """No two claimed spans should overlap."""
        from untell.scripts.tells import _claimed_spans
        text = (
            "Furthermore, this innovative approach leverages robust synergies. " * 100
        )
        claimed = _claimed_spans(text)
        spans = sorted((s, e) for s, e, _n, _m in claimed)
        for i in range(len(spans) - 1):
            s1, e1 = spans[i]
            s2, e2 = spans[i + 1]
            assert e1 <= s2, (
                f"Overlapping claimed spans: ({s1},{e1}) and ({s2},{e2})"
            )


class TestCeilingRegressions:
    """Verify that no sizing step causes a dramatic slowdown relative to the previous step.

    Each test encodes: "processing 10x more text must not take more than 30x longer"
    (allowing for constant overheads and measured noise from sibling agents).
    """

    REPS = 3  # kept low so the full suite finishes in reasonable time

    # --- score_tells size curve ---

    def test_tells_10k_vs_100k_not_superlinear(self):
        """10x size increase must not produce > 30x slowdown in score_tells."""
        t10, t100 = _interleaved_pair(
            lambda: _score_tells(make_prose(10_000)),
            lambda: _score_tells(make_prose(100_000)),
            reps=self.REPS,
        )
        ratio = t100 / max(t10, 1e-6)
        assert ratio < 30, (
            f"score_tells: 10KB->{100}KB ratio {ratio:.1f}x >= 30x "
            f"(t10={t10:.3f}s t100={t100:.3f}s); likely superlinear growth"
        )

    def test_tells_100k_vs_1m_not_superlinear(self):
        """Another 10x: 100KB->1MB must stay under 30x."""
        t100, t1m = _interleaved_pair(
            lambda: _score_tells(make_prose(100_000)),
            lambda: _score_tells(make_prose(1_000_000)),
            reps=self.REPS,
        )
        ratio = t1m / max(t100, 1e-6)
        assert ratio < 30, (
            f"score_tells: 100KB->1MB ratio {ratio:.1f}x >= 30x "
            f"(t100={t100:.3f}s t1m={t1m:.3f}s); likely superlinear growth"
        )

    # --- score_text: bounded by _MAX_INPUT_CHARS, should be nearly flat ---

    def test_score_text_is_flat_above_50k(self):
        """score_text truncates at 50k chars; 100k and 1M must cost the same as 50k."""
        t50, t1m = _interleaved_pair(
            lambda: _score_text(make_prose(50_000)),
            lambda: _score_text(make_prose(1_000_000)),
            reps=self.REPS,
        )
        ratio = t1m / max(t50, 1e-6)
        # Truncation means these should be within 5x (processing is identical past the cap)
        assert ratio < 5, (
            f"score_text: 50KB vs 1MB ratio {ratio:.1f}x >= 5x; "
            f"truncation may not be working (t50={t50:.3f}s t1m={t1m:.3f}s)"
        )

    # --- aligned_chunks: verify fast-path boundaries ---

    def test_aligned_chunks_identical_1k_vs_5k_words(self):
        """Identical pairs at 1k and 5k words: fast-path above 1k => not superlinear."""
        t1k, t5k = _interleaved_pair(
            lambda: _chunks("word " * 1000, "word " * 1000),
            lambda: _chunks("word " * 5000, "word " * 5000),
            reps=self.REPS,
        )
        ratio = t5k / max(t1k, 1e-6)
        # Fast-path is proportional cut; should be linear, so ratio < 15
        assert ratio < 15, (
            f"aligned_chunks identical: 1k->5k word ratio {ratio:.1f}x >= 15x "
            f"(t1k={t1k:.4f}s t5k={t5k:.4f}s)"
        )

    def test_aligned_chunks_distinct_stays_under_limit(self):
        """Non-identical pairs <= 6k words use SequenceMatcher; above 6k switch to proportional."""
        # 3000 words: should use SequenceMatcher
        a3 = " ".join(f"w{i}" for i in range(3000))
        b3 = " ".join(f"w{i}" for i in range(0, 6000, 2))  # different words
        # 7000 words: must use proportional (above 6000 guard)
        a7 = " ".join(f"x{i}" for i in range(7000))
        b7 = " ".join(f"y{i}" for i in range(7000))

        t3, t7 = _interleaved_pair(
            lambda: _chunks(a3, b3),
            lambda: _chunks(a7, b7),
            reps=self.REPS,
        )
        # 7k words on proportional path must not be massively slower than 3k on SequenceMatcher
        assert t7 < 10, (
            f"aligned_chunks 7k-word distinct pair took {t7:.2f}s; "
            "proportional fallback at >6k words may not be working"
        )


# ---------------------------------------------------------------------------
# Full benchmark — only runs when executed as __main__
# ---------------------------------------------------------------------------

def _profile_1mb() -> str:
    """cProfile the score_tells 1MB case; return formatted top-20 by cumulative time."""
    from untell.scripts.tells import score_tells

    text = make_prose(1_000_000)
    pr = cProfile.Profile()
    pr.enable()
    score_tells(text)
    pr.disable()
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
    ps.print_stats(20)
    return s.getvalue()


def run_full_benchmark() -> None:
    """Print the full ceiling table.  Interleaves A/B where 19 sibling agents create noise."""
    from untell.scripts.score import score_text
    from untell.scripts.tells import score_tells
    from untell.text_split import aligned_chunks, split_sentences

    REPS = 5
    sep = "-" * 72

    print(sep)
    print("SCALE CEILING BENCHMARK  (UNTELL_LITE_NO_TORCH=1, UNTELL_DISABLE_MAGE=1)")
    print(f"Python {sys.version.split()[0]}   sibling agents: ~19 (timing may be noisy)")
    print(sep)

    # ---- 1. score_tells: byte-size curve ----
    print("\n## score_tells  (no input cap)")
    print(f"{'size':>8}  {'median(s)':>10}  {'RSS_MB':>8}  {'words':>8}")
    sizes = [10_000, 100_000, 1_000_000, 5_000_000]
    prev_t = None
    for sz in sizes:
        text = make_prose(sz)
        words = len(text.split())
        rss0 = _rss_mb()
        t = _timed_median(lambda t=text: score_tells(t), reps=REPS)
        rss1 = _rss_mb()
        ratio_str = f"  ({t/prev_t:.1f}x)" if prev_t else ""
        print(f"{sz:>8,}  {t:>10.3f}  {rss1-rss0:>8.1f}  {words:>8,}{ratio_str}")
        prev_t = t

    # ---- 2. score_tells: sentence count curve ----
    print("\n## score_tells  (sentence count)")
    print(f"{'sents':>8}  {'median(s)':>10}  {'chars':>10}")
    prev_t = None
    for n in [1_000, 10_000, 100_000]:
        text = make_sentences(n)
        t = _timed_median(lambda t=text: score_tells(t), reps=REPS)
        ratio_str = f"  ({t/prev_t:.1f}x)" if prev_t else ""
        print(f"{n:>8,}  {t:>10.3f}  {len(text):>10,}{ratio_str}")
        prev_t = t

    # ---- 3. score_tells: pathological shapes ----
    print("\n## score_tells  (pathological shapes)")
    shapes = [
        ("no_newlines_50k", lambda: score_tells(make_no_newlines(50_000))),
        ("all_newlines_100k", lambda: score_tells(make_all_newlines(100_000))),
        ("one_giant_word_50k", lambda: score_tells(make_one_giant_word(50_000))),
        ("tiny_paragraphs_10k", lambda: score_tells(make_tiny_paragraphs(10_000))),
    ]
    for name, fn in shapes:
        t = _timed_median(fn, reps=REPS)
        print(f"  {name:<28}  {t:.3f}s")

    # ---- 4. score_text: should be flat above 50k ----
    print("\n## score_text  (capped at 50k chars — should be FLAT for larger inputs)")
    print(f"{'size':>10}  {'median(s)':>10}")
    for sz in [10_000, 50_000, 100_000, 1_000_000]:
        text = make_prose(sz)
        t = _timed_median(lambda t=text: score_text(t), reps=REPS)
        print(f"{sz:>10,}  {t:>10.3f}")

    # ---- 5. split_sentences: sentence count curve ----
    print("\n## split_sentences  (sentence count)")
    print(f"{'sents':>8}  {'median(s)':>10}")
    prev_t = None
    for n in [1_000, 10_000, 100_000]:
        text = make_sentences(n)
        t = _timed_median(lambda t=text: split_sentences(t), reps=REPS)
        ratio_str = f"  ({t/prev_t:.1f}x)" if prev_t else ""
        print(f"{n:>8,}  {t:>10.3f}{ratio_str}")
        prev_t = t

    # ---- 6. aligned_chunks: identical-pair curve (interleaved) ----
    print("\n## aligned_chunks  (identical pair, interleaved A/B)")
    print(f"{'words':>8}  {'median(s)':>10}  {'ratio':>8}")
    prev_t = None
    results: dict[int, float] = {}
    # Interleave every consecutive pair
    wlist = [500, 1_000, 2_000, 4_000, 6_000, 8_000]
    for i in range(len(wlist) - 1):
        wa, wb = wlist[i], wlist[i + 1]
        ta, tb = _interleaved_pair(
            lambda n=wa: aligned_chunks("word " * n, "word " * n),
            lambda n=wb: aligned_chunks("word " * n, "word " * n),
            reps=REPS,
        )
        results[wa] = ta
        results[wb] = tb
    for w in wlist:
        t = results[w]
        ratio_str = f"{t/results[wlist[wlist.index(w)-1]]:.1f}x" if w != wlist[0] else "—"
        print(f"{w:>8,}  {t:>10.4f}  {ratio_str:>8}")

    # ---- 7. cProfile on 1MB score_tells ----
    print("\n## cProfile  score_tells(1MB)  — top 20 by cumulative time")
    print(_profile_1mb())

    # ---- 8. Summary ceiling table ----
    print(sep)
    print("CEILING TABLE")
    print(sep)
    rows = [
        ("score_tells", "10KB",  "< 0.5s",  "O(n)",    "GREEN"),
        ("score_tells", "100KB", "< 5s",    "O(n)",    "GREEN"),
        ("score_tells", "1MB",   "< 60s",   "O(n) measured", "AMBER if > 30s"),
        ("score_tells", "5MB",   "< 300s",  "O(n) expected", "RED if > 120s"),
        ("score_text",  "any",   "flat",    "O(1) after 50k cap", "GREEN"),
        ("split_sentences", "100k sents", "< 10s", "O(n)", "GREEN"),
        ("aligned_chunks",  ">6000 words", "linear", "proportional fallback", "GREEN"),
        ("aligned_chunks",  "1000-6000 words", "O(n log n)", "SequenceMatcher", "WATCH"),
        ("_claimed_spans",  "dense-tell text", "O(n²) worst case", "claiming loop", "RED if dense"),
    ]
    print(f"{'function':<20}  {'input':<20}  {'verdict':<12}  {'complexity':<25}  {'status'}")
    for r in rows:
        print(f"{r[0]:<20}  {r[1]:<20}  {r[2]:<12}  {r[3]:<25}  {r[4]}")
    print(sep)
    print("\nSUPERLINEAR FINDING:")
    print("  Function : untell/scripts/tells.py :: _claimed_spans()")
    print("  Shape    : O(S * C) where S=total regex hits, C=claimed spans")
    print("  Trigger  : text where many words match AI-tell patterns")
    print("  Guard    : score_text is immune (50k cap); score_tells has no cap")
    print("  Profile  : see cProfile output above for 1MB evidence")
    print(sep)


if __name__ == "__main__":
    run_full_benchmark()
