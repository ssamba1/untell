"""`eval/holdout.py` turned every loop refusal into `KeyError: 'pre'`.

`untell_text` reports a refusal as `{"error": ...}` with no `pre`/`post`, and holdout indexed
straight into `result["pre"]["max"]`. MEASURED with a typo'd backend name, `--rewriter compsite`:

    File "eval/holdout.py", line 103, in run
        "pre_max": result["pre"]["max"],
    KeyError: 'pre'

A bare traceback for a message the loop had already written correctly — "rewriter 'compsite' is not
available — check the name". Every refusal took that path: an unset API key, an unavailable backend,
a meaning gate that vetoed every draw. The one thing a user needed to read was the one thing they
could not see.

`--rewriter` is deliberately left WITHOUT an argparse `choices` list. Hosted backends are valid
names here, and `untell_text` resolves them against what is actually configured, which argparse
cannot; duplicating that list would put a second, staler copy of it in this file. Surfacing the
loop's own answer is the fix.

Also in this file: `--tier` rejected `commercial`, a tier its own `score_text` call accepts. That
is the divergence `test_surface_parity.py` exists to catch, and it is why that test had been red.
`score_text(tier="commercial")` returns normally without keys and reports the tier that actually
produced numbers, so the honest answer comes from the loader rather than from an argparse list.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pytest

from untell.detectors.base import _TIER_RANK

_HOLDOUT = Path(__file__).resolve().parents[1] / "eval" / "holdout.py"


def test_the_tier_flag_accepts_every_tier_the_loader_supports() -> None:
    match = re.search(r'"--tier".{0,200}?choices=\[([^\]]*)\]', _HOLDOUT.read_text(encoding="utf-8"), re.S)
    assert match, "no --tier choices list found; the scan is wrong"
    listed = set(re.findall(r'"([^"]*)"', match.group(1)))
    missing = set(_TIER_RANK) - listed
    assert not missing, f"holdout rejects tiers score_text accepts: {sorted(missing)}"


def test_the_rewriter_flag_is_not_constrained_by_argparse() -> None:
    """Asserted deliberately, so a future edit does not "fix" this by pasting a stale name list.

    The set of usable backends depends on installed extras and configured keys. argparse knows
    neither.
    """
    source = _HOLDOUT.read_text(encoding="utf-8")
    match = re.search(r'"--rewriter".{0,200}?\)', source, re.S)
    assert match, "no --rewriter argument found"
    assert "choices=" not in match.group(0), (
        "holdout's --rewriter now has an argparse choices list, which cannot know what is "
        "installed or keyed; `untell_text` resolves the name and reports what is unavailable"
    )


def test_a_refusal_is_reported_not_indexed_into(monkeypatch) -> None:
    """The defect itself, driven through `run` with a stubbed loop so no rewriting is needed."""
    import eval.holdout as holdout

    monkeypatch.setattr(
        holdout, "untell_text",
        lambda *a, **k: {"error": "rewriter 'compsite' is not available — check the name"},
    )
    monkeypatch.setattr(holdout, "load_pairs", lambda *a, **k: [("human text", "ai text")])

    with pytest.raises(SystemExit) as excinfo:
        holdout.run(dataset="hc3", n=1, tier="lite", rewriter="compsite")

    message = str(excinfo.value)
    assert "compsite" in message, f"the refusal's own text is missing: {message!r}"
    assert "not available" in message


def test_a_normal_result_is_still_processed(monkeypatch) -> None:
    """Guards the guard. A `run` that raised on everything would pass the test above."""
    import eval.holdout as holdout

    monkeypatch.setattr(
        holdout, "untell_text",
        lambda *a, **k: {
            "pre": {"max": 0.9}, "post": {"max": 0.2}, "similarity": 0.99, "final": "rewritten",
        },
    )
    monkeypatch.setattr(holdout, "load_pairs", lambda *a, **k: [("human text", "ai text")])

    result = holdout.run(dataset="hc3", n=1, tier="lite", rewriter="composite")
    assert result, "a well-formed result produced nothing"


def _run_cli(*args: str) -> tuple[int, str]:
    """Run holdout as a subprocess and return (exit code, combined output).

    Both of these were `pytest.skip`s that imported holdout and looked for a `build_parser`, which
    it does not have — it constructs the parser inside `main()`, like most CLIs in this repo. A
    skipped test verifies nothing, and two of them sat here claiming the source check "covers it"
    while the BEHAVIOUR went unchecked. A subprocess needs no refactor of holdout and tests the
    real thing.
    """
    import os
    import subprocess
    import sys

    env = {**os.environ, "UNTELL_LITE_NO_TORCH": "1", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(_HOLDOUT), *args],
        capture_output=True, text=True, env=env, cwd=str(_HOLDOUT.parents[1]), timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def test_the_cli_really_accepts_commercial() -> None:
    """Behaviour, not just the source text the first test reads. `--tier commercial` must get PAST
    argparse; it may then fail for an unrelated reason (missing data extra), which is fine — what
    matters is that the failure is not "invalid choice"."""
    _code, output = _run_cli("--tier", "commercial", "--n", "0")
    assert "invalid choice" not in output, (
        f"argparse still rejects the commercial tier: {output[-200:]!r}"
    )


def test_the_cli_still_rejects_a_tier_the_loader_does_not_have() -> None:
    """The choices list must keep constraining something, or widening it was just deleting it."""
    code, output = _run_cli("--tier", "nonsense", "--n", "0")
    assert code != 0
    assert "invalid choice" in output, f"a bogus tier was accepted: {output[-200:]!r}"
    assert "--tier" in output


def test_the_scan_would_notice_a_missing_flag() -> None:
    """If the regexes stopped matching, the two source-reading tests would pass on nothing."""
    source = _HOLDOUT.read_text(encoding="utf-8")
    assert isinstance(argparse.ArgumentParser, type)
    assert '"--tier"' in source and '"--rewriter"' in source
