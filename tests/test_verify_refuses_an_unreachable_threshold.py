"""`untell verify --threshold 5` certified any text as passing.

Detector scores are probabilities in [0, 1], so a threshold above 1 cannot be reached by anything.
MEASURED before the fix, on text the same command rates 0.826:

    local:perplexity_burstiness AI=0.826  [PASS]
    PASSES ALL 1 CHECKERS
    exit 0

On the command whose entire job is gating, a slipped decimal point green-lights everything — and
a CI job reading the exit code sees success.

Every other surface already refused it: `untell humanize` through this same `_PROBABILITY`
validator, the REST API with 422, the MCP tools with "a value above 1 can never be reached". This
was the fourth surface and the one where it mattered most.

Found by sweeping every console command over three situations — valid arguments, bad arguments,
empty stdin — and comparing the exit codes:

    command      good   bad args   empty stdin
    score           0       2           2
    tells           0       2           2
    sentences       0       2           2
    scrub           0       2           0
    run             0       2           2
    humanness       0       2           2
    numerals        0       2           2
    hedges          0       2           2
    verify          1       0  <---     2

`verify`'s "good" column is 1 because the sample text genuinely fails, which is correct. The 0 in
the middle column is the defect.
"""
from __future__ import annotations

import subprocess
import sys

import pytest

TEXT = "Moreover, the framework leverages robust methodologies to deliver outcomes at scale."
HUMAN = "I walked to the shop and it was closed for the day, so I came home again."


def _run(args: list[str]) -> subprocess.CompletedProcess:
    import os

    env = dict(os.environ, UNTELL_LITE_NO_TORCH="1", PYTHONIOENCODING="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "untell.scripts.verify", *args],
        capture_output=True, text=True, timeout=300, env=env, input="",
    )


@pytest.mark.parametrize("value", ["5", "1.5", "-0.1", "100"])
def test_an_unreachable_threshold_is_refused(value: str):
    result = _run([TEXT, "--tier", "lite", "--threshold", value])

    assert result.returncode == 2, (
        f"--threshold {value} exited {result.returncode}; a threshold outside [0, 1] cannot be "
        "reached by a probability, so accepting it certifies any text"
    )
    assert "between 0.0 and 1.0" in (result.stderr + result.stdout), result.stderr[-200:]


@pytest.mark.parametrize("value", ["0", "0.3", "0.5", "1"])
def test_a_reachable_threshold_is_accepted(value: str):
    """The bound must not be so tight it refuses the ends of the range."""
    result = _run([HUMAN, "--tier", "lite", "--threshold", value])
    assert result.returncode in (0, 1), result.stderr[-200:]


def test_a_failing_verdict_still_exits_one():
    """The distinction the exit codes carry: 1 is a verdict, 2 is a usage error."""
    result = _run([TEXT, "--tier", "lite", "--threshold", "0.1"])
    assert result.returncode == 1, result.stdout[-200:]


def test_a_passing_verdict_still_exits_zero():
    result = _run([HUMAN, "--tier", "lite", "--threshold", "0.9"])
    assert result.returncode == 0, result.stdout[-200:]


def test_the_validator_is_the_shared_one():
    """One definition of the bound, so verify and humanize cannot drift apart."""
    import inspect

    from untell.scripts.verify import build_parser

    assert "_PROBABILITY" in inspect.getsource(build_parser), (
        "verify declares its own threshold bound again; the point of importing run's validator is "
        "that there is one definition"
    )
