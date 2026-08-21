"""JSONL streaming mode tests (issue #32).

Contract requirements being verified:
  1. Each line is a complete, valid JSON object.
  2. The stream is parseable incrementally (for line in stdout: json.loads(line)).
  3. A final summary object (type="summary") closes the stream.
  4. --jsonl and --json are mutually exclusive; the conflict produces a clean error, not a
     traceback.
  5. DETERMINISM: same input + same --seed produces byte-identical JSONL across two fresh
     processes (tested with subprocess.run like test_reproducibility_across_processes.py).
  6. STREAMING PROPERTY: the first line arrives BEFORE the process exits, i.e. the process
     is still running when the first line is readable.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Two-paragraph input: short enough to keep tests fast, long enough to exercise the splitter
# and give two block lines + one summary line.
TWO_PARA = (
    "Moreover, the framework leverages a robust approach to deliver transformative outcomes "
    "for every stakeholder. Furthermore, it underscores the pivotal integration of modern "
    "methodologies."
    "\n\n"
    "In conclusion, the comprehensive solution demonstrates significant value across the "
    "entire organizational landscape and beyond. Additionally, it enables stakeholders to "
    "achieve their objectives efficiently and effectively."
)

# Three-paragraph version for the streaming property test: more paragraphs mean more
# sequential work, so para-0 completing while para-1/para-2 are still pending is reliable.
THREE_PARA = TWO_PARA + (
    "\n\n"
    "Furthermore, the underlying methodology ensures robust outcomes across all domains "
    "and comprehensively addresses the pivotal challenges identified by stakeholders."
)


def _env() -> dict:
    """Subprocess environment: lite path, offline, deterministic."""
    return {
        **os.environ,
        "PYTHONPATH": "",  # prevent a shadowing package from swapping what is under test
        "UNTELL_LITE_NO_TORCH": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "PYTHONIOENCODING": "utf-8",
    }


def _run_jsonl(text: str, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    """Run the CLI in --jsonl mode; return the CompletedProcess."""
    cmd = [
        sys.executable, "-m", "untell.scripts.run",
        "--tier", "lite",
        "--threshold", "0.0",
        "--seed", "42",
        "--max-iters", "1",
        "--jsonl",
    ] + (extra_args or [])
    return subprocess.run(
        cmd,
        input=text.encode("utf-8"),
        capture_output=True,
        env=_env(),
        cwd=str(ROOT),
        timeout=120,
    )


def _lines(proc: subprocess.CompletedProcess) -> list[dict]:
    """Parse stdout as JSONL; raise on first invalid line."""
    raw = proc.stdout.decode("utf-8", errors="replace")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# 1. Every output line is valid JSON
# ---------------------------------------------------------------------------

def test_every_line_is_valid_json() -> None:
    proc = _run_jsonl(TWO_PARA)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")[-500:]
    lines = _lines(proc)
    # We get block lines + 1 summary — must parse without error (that is the assertion above).
    assert len(lines) >= 2, f"expected at least 2 lines, got {len(lines)}"


# ---------------------------------------------------------------------------
# 2. Each block line has the required keys and the summary closes the stream
# ---------------------------------------------------------------------------

def test_block_lines_have_required_keys() -> None:
    proc = _run_jsonl(TWO_PARA)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")[-500:]
    lines = _lines(proc)

    block_lines = [ln for ln in lines if ln.get("type") == "block"]
    assert len(block_lines) == 2, f"expected 2 block lines, got {len(block_lines)}"
    for i, blk in enumerate(block_lines):
        assert blk["index"] == i
        assert blk["total_blocks"] == 2
        assert "final" in blk, f"block {i} missing 'final'"
        assert "pre" in blk, f"block {i} missing 'pre'"
        assert "post" in blk, f"block {i} missing 'post'"
        assert "seed" in blk, f"block {i} missing 'seed'"


def test_summary_line_closes_stream() -> None:
    proc = _run_jsonl(TWO_PARA)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")[-500:]
    lines = _lines(proc)

    # The LAST line must be the summary.
    last = lines[-1]
    assert last.get("type") == "summary", f"last line is not summary: {last}"
    assert "total_blocks" in last
    assert "changed" in last
    assert "flagged_after" in last
    assert "doc_seed" in last


# ---------------------------------------------------------------------------
# 3. --jsonl and --json are mutually exclusive (clean error, no traceback)
# ---------------------------------------------------------------------------

def test_mutual_exclusion_gives_clean_error() -> None:
    cmd = [
        sys.executable, "-m", "untell.scripts.run",
        "--tier", "lite",
        "--json",
        "--jsonl",
        "some text",
    ]
    proc = subprocess.run(
        cmd,
        input=b"some text",
        capture_output=True,
        env=_env(),
        cwd=str(ROOT),
        timeout=30,
    )
    # Must exit non-zero.
    assert proc.returncode != 0, "expected non-zero exit for --json --jsonl"

    # The error must arrive on stderr (not stdout) without a traceback.
    stderr = proc.stderr.decode("utf-8", "replace")
    assert "Traceback" not in stderr, (
        f"mutual exclusion raised a traceback instead of a clean error: {stderr[-300:]}"
    )

    # stderr must carry the JSON error object.
    error_lines = [ln for ln in stderr.splitlines() if ln.strip().startswith("{")]
    assert error_lines, (
        f"expected a JSON error object on stderr but got: {stderr[-300:]}"
    )
    err = json.loads(error_lines[0])
    assert "error" in err
    assert "mutually exclusive" in err["error"]


# ---------------------------------------------------------------------------
# 4. Cross-process byte identity (DETERMINISM contract)
# ---------------------------------------------------------------------------

def test_jsonl_is_byte_identical_across_processes() -> None:
    """Two fresh processes with the same input and seed must emit byte-identical JSONL.

    Without this guarantee, the streamed output cannot be used for reproducibility manifests
    or batch comparison, and the --seed flag would be meaningless in --jsonl mode.
    """
    a = _run_jsonl(TWO_PARA)
    b = _run_jsonl(TWO_PARA)

    assert a.returncode == 0, f"first process failed: {a.stderr.decode('utf-8','replace')[-300:]}"
    assert b.returncode == 0, f"second process failed: {b.stderr.decode('utf-8','replace')[-300:]}"

    assert a.stdout == b.stdout, (
        "two fresh processes at the same seed produced different JSONL. "
        "A non-deterministic component (global RNG, process entropy) reached the loop.\n"
        f"--- process A (first 500 bytes) ---\n{a.stdout[:500]!r}\n"
        f"--- process B (first 500 bytes) ---\n{b.stdout[:500]!r}"
    )


def test_different_seed_gives_different_jsonl() -> None:
    """The seed is not inert: two seeds must produce different streams.

    If seeds 42 and 43 give identical bytes, the seed argument does nothing and the
    byte-identity test above would pass trivially for the wrong reason.
    """
    a = _run_jsonl(TWO_PARA, ["--seed", "42"])
    b = _run_jsonl(TWO_PARA, ["--seed", "43"])

    assert a.returncode == 0, f"seed-42 process failed: {a.stderr.decode('utf-8','replace')[-300:]}"
    assert b.returncode == 0, f"seed-43 process failed: {b.stderr.decode('utf-8','replace')[-300:]}"

    assert a.stdout != b.stdout, (
        "seeds 42 and 43 produced byte-identical JSONL; the seed is inert in --jsonl mode"
    )


# ---------------------------------------------------------------------------
# 5. STREAMING PROPERTY: first line arrives before the process exits
# ---------------------------------------------------------------------------

def test_first_line_arrives_before_process_exits() -> None:
    """Assert the FIRST block line is readable while the process is still running.

    This is the canonical proof that --jsonl is genuinely streaming and not just
    a reformatting of the final result.  With three paragraphs, the first block
    completes while the second and third are pending, so the process must still be
    alive when the first newline is available.

    Implementation: Popen with stdout=PIPE, readline() blocks until the first '\\n'
    is available, then poll() checks whether the process has exited yet.
    """
    cmd = [
        sys.executable, "-m", "untell.scripts.run",
        "--tier", "lite",
        "--threshold", "0.0",
        "--seed", "42",
        "--max-iters", "1",
        "--jsonl",
    ]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_env(),
        cwd=str(ROOT),
    )
    proc.stdin.write(THREE_PARA.encode("utf-8"))
    proc.stdin.close()

    # Block until the first complete line (the first block's result) arrives.
    first_line_bytes = proc.stdout.readline()

    # At this moment the process should still be running (second paragraph is computing).
    still_running = proc.poll() is None

    # Let the process finish.
    rest, _ = proc.communicate(timeout=120)

    # Validate the first line is a valid block JSON.
    assert first_line_bytes, "no output: readline() returned empty bytes"
    first = json.loads(first_line_bytes.decode("utf-8", "replace"))
    assert first.get("type") == "block", f"first line is not a block object: {first}"
    assert first.get("index") == 0

    assert still_running, (
        "the process had already exited when the first JSONL block line was read — "
        "--jsonl is not streaming: it emits all lines at the end, not one at a time"
    )
