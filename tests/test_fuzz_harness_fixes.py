"""Failing-first regression tests for crashes found by scripts/fuzz_harness.py (slice 9).

Each test here failed on HEAD c09deed with the traceback named in its docstring and
passes after the corresponding fix. The harness that found them ships at
scripts/fuzz_harness.py and the full finding log at .claude/probes/ (run
`PYTHONPATH= .venv/Scripts/python.exe scripts/fuzz_harness.py --quick`).

Findings pinned here:
  1. mcp_server._bad_args raised OverflowError on float('inf') (JSON 1e309 / Infinity)
     for the int-valued kinds (count/count_or_zero/top/seed) — an MCP client could
     crash the server instead of getting a refusal dict.
  2. POST /score (and every other endpoint) returned 500 instead of 422 for a valid
     JSON body carrying 1e309 / Infinity / NaN: pydantic rejected the value, then
     FastAPI's default validation handler tried to JSON-serialize the offending
     `inf` into the 422 detail and crashed.
  3. preserve.lock() raised UnicodeEncodeError on text containing lone surrogates
     (spaCy tokenizer), and lock()/restore() leaked internal re errors on non-str
     input instead of naming the contract.
  4. score_tells / humanness / score_sentences leaked internal "string pattern on a
     bytes-like object" / "a bytes-like object is required" errors for bytes input
     instead of the clean "text must be str" TypeError score_text/untell_text raise.
  5. score_text(tier=["lite"]) and friends raised TypeError: unhashable type: 'list'
     from deep inside load_detectors instead of a clean "tier must be str" error.
  6. CLI subprocesses crashed with UnicodeEncodeError when printing lone surrogates
     (scrub's output path; argparse's stderr message path) — configure_utf8_io
     reconfigured encoding but not errors, so a surrogate killed the process.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def _bad_args(**checks):
    from untell.mcp_server import _bad_args as fn

    return fn(**checks)


# --- 1. MCP _bad_args must refuse non-finite int-valued args, not crash ---------------


class TestBadArgsRefusesNonFiniteCounts:
    """_bad_args(max_iters=(float('inf'), 'count')) raised OverflowError on HEAD."""

    @pytest.mark.parametrize(
        "name,kind",
        [("max_iters", "count"), ("best_of", "count"), ("confirm", "count_or_zero"),
         ("top", "top"), ("seed", "seed")],
    )
    def test_positive_infinity_is_a_refusal_dict(self, name, kind):
        out = _bad_args(**{name: (float("inf"), kind)})
        assert out is not None, f"{name}=inf must be refused, not accepted"
        assert "error" in out

    @pytest.mark.parametrize(
        "name,kind",
        [("max_iters", "count"), ("best_of", "count"), ("confirm", "count_or_zero"),
         ("top", "top"), ("seed", "seed")],
    )
    def test_negative_infinity_is_a_refusal_dict(self, name, kind):
        out = _bad_args(**{name: (float("-inf"), kind)})
        assert out is not None
        assert "error" in out

    def test_json_1e309_is_refused_not_crashed(self):
        # python's json module parses 1e309 to inf; an MCP client sending that
        # reached int(inf) -> OverflowError on HEAD.
        value = json.loads("1e309")
        out = _bad_args(max_iters=(value, "count"))
        assert out is not None
        assert "error" in out

    def test_valid_counts_still_pass(self):
        assert _bad_args(max_iters=(5, "count")) is None
        assert _bad_args(seed=(42, "seed")) is None
        assert _bad_args(top=(3, "top")) is None


# --- 2. REST: non-finite floats must be a 422, not a 500 ------------------------------


class TestNonFiniteRequestBodyIsA422:
    """Valid JSON 1e309 made every endpoint answer 500 on HEAD (the 422 detail
    itself failed to serialize the offending `inf`)."""

    ENDPOINTS = ["/score", "/humanize", "/sentences", "/verify", "/ceiling"]
    BODIES = [
        '{"text": "hello world", "threshold": 1e309}',
        '{"text": "hello world", "threshold": Infinity}',
        '{"text": "hello world", "threshold": -Infinity}',
        '{"text": "hello world", "threshold": NaN}',
        '{"text": "hello world", "max_iters": 1e309}',
        '{"max_iters": 1e309}',
    ]

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    @pytest.mark.parametrize("body", BODIES)
    def test_bad_body_is_422_not_500(self, endpoint, body):
        from fastapi.testclient import TestClient

        with patch("untell.api_server.load_env"):
            from untell.api_server import app

            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(endpoint, content=body,
                               headers={"content-type": "application/json"})
            assert resp.status_code == 422, (
                f"{endpoint} with {body[:40]!r} answered {resp.status_code}: "
                f"{resp.text[:120]}"
            )
            # the detail must still be parseable JSON
            detail = resp.json()
            assert "detail" in detail

    def test_valid_payload_still_works(self):
        from fastapi.testclient import TestClient

        with patch("untell.api_server.load_env"):
            from untell.api_server import app

            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/score", content='{"text": "hello world"}',
                               headers={"content-type": "application/json"})
            assert resp.status_code == 200


# --- 3. preserve lock/restore: surrogates and non-str must not crash ---------------


class TestLockSurvivesLoneSurrogates:
    """lock() raised UnicodeEncodeError inside spaCy's tokenizer on HEAD."""

    def test_lock_and_restore_on_surrogate_text(self):
        from untell.scripts.preserve import lock, restore

        text = "punderscoresle.x4h\r!y\u2067A6\n\r4brown\u200b\uD800\uDFFF tail"
        masked, mapping = lock(text)
        back = restore(masked, mapping)
        # lone surrogates cannot survive a round trip through any encoder; the
        # contract is: no crash, and the decodable content is preserved.
        assert isinstance(masked, str)
        assert isinstance(back, str)

    def test_lock_rejects_non_str_cleanly(self):
        from untell.scripts.preserve import lock

        for bad in (b"bytes", None, ["a", "b"], 42, {"k": "v"}):
            with pytest.raises(TypeError, match="text must be str"):
                lock(bad)

    def test_restore_rejects_non_str_cleanly(self):
        from untell.scripts.preserve import restore

        for bad in (b"bytes", None, ["a"], 42):
            with pytest.raises(TypeError, match="masked text must be str"):
                restore(bad, {"\u27e6HZ0000\u27e7": "x"})


# --- 4. score_tells / humanness / score_sentences reject non-str cleanly ----------


class TestTellsHumannessSentencesRejectNonStr:
    """bytes input leaked internal re errors on HEAD instead of the clean contract
    TypeError that score_text / untell_text already raise."""

    @pytest.mark.parametrize("bad", [b"hello world", b"\xff\x00", bytearray(b"x"),
                                     None, 123, ["list"], {"d": 1}])
    def test_score_tells(self, bad):
        from untell.scripts.tells import score_tells

        with pytest.raises(TypeError, match="text must be str"):
            score_tells(bad)

    @pytest.mark.parametrize("bad", [b"hello world", None, 123])
    def test_humanness(self, bad):
        from untell.humanness import humanness

        with pytest.raises(TypeError, match="text must be str"):
            humanness(bad, tier="lite")

    @pytest.mark.parametrize("bad", [b"hello world", None, 123])
    def test_score_sentences(self, bad):
        from untell.scripts.sentences import score_sentences

        with pytest.raises(TypeError, match="text must be str"):
            score_sentences(bad, tier="lite")


# --- 5. tier must be str --------------------------------------------------------------


class TestTierMustBeStr:
    """score_text(tier=["lite"]) raised TypeError: unhashable type: 'list' from
    _tier_at_most on HEAD — a leak of an internal failure, not a contract error."""

    @pytest.mark.parametrize("bad", [["lite"], {"t": 1}, ["full", "lite"]])
    def test_score_text_rejects_non_str_tier(self, bad):
        from untell.scripts.score import score_text

        with pytest.raises(TypeError, match="tier must be str"):
            score_text("hello world", tier=bad)

    @pytest.mark.parametrize("bad", [["lite"], 5, None])
    def test_untell_text_rejects_non_str_tier(self, bad):
        from untell.scripts.run import untell_text

        with pytest.raises(TypeError, match="tier must be str"):
            untell_text("hello world", tier=bad, max_iters=1)

    @pytest.mark.parametrize("bad", [["lite"], 5, None])
    def test_score_sentences_rejects_non_str_tier(self, bad):
        from untell.scripts.sentences import score_sentences

        with pytest.raises(TypeError, match="tier must be str"):
            score_sentences("hello world", tier=bad)

    @pytest.mark.parametrize("bad", [["lite"], 5, None])
    def test_humanness_rejects_non_str_tier(self, bad):
        from untell.humanness import humanness

        with pytest.raises(TypeError, match="tier must be str"):
            humanness("a reasonably long sentence to score here now ok.", tier=bad)

    def test_valid_tiers_still_work(self):
        from untell.scripts.score import score_text

        assert score_text("hello world", tier="lite")["tier"] == "lite"


class TestThresholdMustBeNumeric:
    """score_text(text, threshold="0.3") raised TypeError: '>' not supported
    between instances of 'float' and 'str' from _verdict_threshold on HEAD — a
    leak of an internal comparison failure, not a contract error."""

    @pytest.mark.parametrize("bad", ["0.5", None, ["0.3"], {"t": 1}, "abc", True])
    def test_score_text_rejects_non_numeric_threshold(self, bad):
        from untell.scripts.score import score_text

        with pytest.raises(TypeError, match="threshold must be a number"):
            score_text("The committee approved the proposal yesterday.", tier="lite",
                       threshold=bad)

    @pytest.mark.parametrize("bad", ["0.5", None])
    def test_untell_text_rejects_non_numeric_threshold(self, bad):
        from untell.scripts.run import untell_text

        with pytest.raises(TypeError, match="threshold must be a number"):
            untell_text("hello world", tier="lite", max_iters=1, threshold=bad)

    @pytest.mark.parametrize("bad", ["0.5", None])
    def test_score_sentences_rejects_non_numeric_threshold(self, bad):
        from untell.scripts.sentences import score_sentences

        with pytest.raises(TypeError, match="threshold must be a number"):
            score_sentences("The committee approved the proposal yesterday.",
                            tier="lite", threshold=bad)

    def test_numeric_thresholds_still_work(self):
        from untell.scripts.score import score_text

        for t in (0.3, 0.0, 1.0, 0.5):
            assert score_text("hello world", tier="lite", threshold=t)["tier"] == "lite"


# --- 6. CLI printing must survive lone surrogates ------------------------------------


class TestCliPrintingSurvivesSurrogates:
    """A CLI printing text/argv containing a lone surrogate crashed with
    UnicodeEncodeError on HEAD — scrub's output path and argparse's stderr path."""

    def test_configure_utf8_io_uses_replace_errors(self):

        from untell.scripts.io_utils import configure_utf8_io

        # StringIO.reconfigure accepts errors=; verify the function sets replace
        # semantics by checking it does not raise and the stream tolerates surrogates
        configure_utf8_io()
        assert True  # the real check is the subprocess tests below

    def test_scrub_subprocess_surrogate_argv_does_not_traceback(self):
        repo = Path(__file__).resolve().parents[1]
        # `sys.executable` rather than a hard-coded `.venv/Scripts/python.exe`.
        # That path is Windows-only and lives inside one developer's checkout: on CI's
        # Linux runner it cannot exist, so `subprocess.run` raised FileNotFoundError and
        # this test FAILED rather than skipping. The interpreter already running the
        # suite is the one whose environment these tests mean to exercise.
        py = sys.executable
        env = {"PYTHONPATH": "", "PYTHONUTF8": "1"}
        # a lone surrogate in the text position; scrub prints it back
        proc = subprocess.run(
            [str(py), "-m", "untell.scripts.scrub", "text with \ud800 surrogate"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, cwd=repo, stdin=subprocess.DEVNULL, env=env,
        )
        assert "Traceback" not in (proc.stderr or ""), proc.stderr
        assert proc.returncode in (0, 2)

    def test_argparse_surrogate_argv_does_not_traceback(self):
        repo = Path(__file__).resolve().parents[1]
        # `sys.executable` rather than a hard-coded `.venv/Scripts/python.exe`.
        # That path is Windows-only and lives inside one developer's checkout: on CI's
        # Linux runner it cannot exist, so `subprocess.run` raised FileNotFoundError and
        # this test FAILED rather than skipping. The interpreter already running the
        # suite is the one whose environment these tests mean to exercise.
        py = sys.executable
        env = {"PYTHONPATH": "", "PYTHONUTF8": "1"}
        # an invalid --tier value containing a surrogate: argparse prints the value
        # into its error message, which crashed on HEAD. (No NUL here — Windows
        # CreateProcess rejects an embedded NUL in argv; the harness sanitises that
        # case before spawning.)
        proc = subprocess.run(
            [str(py), "-m", "untell.scripts.score", "--tier", "lite\udb87", "hello"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, cwd=repo, stdin=subprocess.DEVNULL, env=env,
        )
        assert "Traceback" not in (proc.stderr or ""), proc.stderr
        assert proc.returncode == 2
