"""`--manifest` reproducibility-manifest mode (issue #31).

The manifest is the *operable* half of the determinism contract (docs/determinism.md): a JSON
file recording the inputs the output bytes depend on (input/output sha256, seed, rewriter, tier,
threshold) plus the pre/post detector maxima and an honest determinism class. Local rewriters are
"reproducible" — same input + same seed reproduce identical bytes, pinned here and in
`test_reproducibility_across_processes.py`; remote rewriters (anthropic/openai) and `--browser`
detectors are "non-deterministic by design" because their noise lives on a service the seed
cannot reach.

The manifest carries NO timestamp, so it is itself byte-identical across runs — the same
byte-identity it exists to prove.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import untell
from untell.scripts.run import _manifest_payload, main, untell_text

ROOT = Path(__file__).resolve().parents[1]


# Tell-bearing enough to force rewrites at threshold=0.0 (the same guard the reproducibility
# tests use: at the default threshold this scores below the bar and the loop no-ops).
TEXT = (
    "Moreover, the framework leverages a robust approach to deliver transformative outcomes "
    "for every stakeholder. Furthermore, it underscores the pivotal integration of modern "
    "methodologies."
)

ARGS = [
    "--tier", "lite", "--threshold", "0.0", "--seed", "42", "--max-iters", "1",
    "--rewriter", "composite",
]


def _run_cli(manifest: Path) -> int:
    """Run the `untell humanize` CLI with `--manifest` + `--json`, returning its exit code."""
    return main([*ARGS, "--manifest", str(manifest), "--json", TEXT])


def test_the_result_carries_the_rewriter_that_ran(stdlib_lite) -> None:
    r = untell_text(TEXT, tier="lite", threshold=0.0, seed=42, max_iters=1,
                    rewriter="composite", best_of=3)
    assert r.get("rewriter") == "composite"
    assert r["final"] != TEXT, "the loop left the text untouched"


def test_manifest_records_every_contract_field(stdlib_lite, tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    assert _run_cli(manifest) == 0
    data = json.loads(manifest.read_text(encoding="utf-8"))

    assert data["manifest_version"] == 1
    assert data["untell_version"] == untell.__version__
    assert data["input_sha256"] == hashlib.sha256(TEXT.encode("utf-8")).hexdigest()
    assert len(data["output_sha256"]) == 64  # sha256 hex digest of the emitted final
    assert data["seed"] == 42
    assert data["rewriter"] == "composite"
    assert data["tier"] == "lite"
    assert data["threshold"] == 0.0
    # pre/post max are the actual detector maxima, present as numbers.
    assert isinstance(data["pre_max"], (int, float))
    assert isinstance(data["post_max"], (int, float))
    assert data["determinism"] == "reproducible"

    # output_sha256 must equal the sha256 of what untell_text produced at the same seed —
    # the manifest is literally describing the bytes of this run's output.
    r = untell_text(TEXT, tier="lite", threshold=0.0, seed=42, max_iters=1,
                    rewriter="composite", best_of=3)
    assert data["output_sha256"] == hashlib.sha256(r["final"].encode("utf-8")).hexdigest()


def test_manifest_is_byte_identical_across_runs(stdlib_lite, tmp_path) -> None:
    """Same input + seed -> byte-identical manifest file (no timestamp defeats identity)."""
    m1 = tmp_path / "run1.json"
    m2 = tmp_path / "run2.json"
    assert _run_cli(m1) == 0
    assert _run_cli(m2) == 0
    assert m1.read_bytes() == m2.read_bytes(), (
        "the manifest changed between two identical runs — a timestamp or other nonce "
        "made it into the row, defeating the byte-identity it exists to prove"
    )


def test_manifest_parent_directories_are_created(stdlib_lite, tmp_path) -> None:
    manifest = tmp_path / "nested" / "deep" / "manifest.json"
    assert _run_cli(manifest) == 0
    assert manifest.exists()


def test_manifest_confirmation_goes_to_stderr_not_stdout(stdlib_lite, tmp_path, capsys) -> None:
    """With --json, stdout must stay pure JSON; the manifest path is context, so it is stderr."""
    _run_cli(tmp_path / "manifest.json")
    captured = capsys.readouterr()
    json.loads(captured.out)  # stdout must be parseable JSON alone
    assert "manifest:" in captured.err


def test_local_rewriter_is_reproducible() -> None:
    payload = _manifest_payload(
        "text", {"rewriter": "composite", "final": "out", "seed": 1, "tier": "lite",
                 "pre": {"max": 0.5}, "post": {"max": 0.2}},
        browser=None, threshold=0.3,
    )
    assert payload["determinism"] == "reproducible"


@pytest.mark.parametrize("rewriter", ["anthropic", "openai"])
def test_remote_rewriters_are_non_deterministic_by_design(rewriter) -> None:
    payload = _manifest_payload(
        "text", {"rewriter": rewriter, "final": "out", "seed": 1, "tier": "lite",
                 "pre": {"max": 0.5}, "post": {"max": 0.2}},
        browser=None, threshold=0.3,
    )
    assert payload["determinism"] == "non-deterministic by design"


def test_browser_detector_is_non_deterministic_by_design() -> None:
    # An otherwise-reproducible composite run becomes non-deterministic when a live web
    # detector is steering the loop.
    payload = _manifest_payload(
        "text", {"rewriter": "composite", "final": "out", "seed": 1, "tier": "lite",
                 "pre": {"max": 0.5}, "post": {"max": 0.2}},
        browser="zerogpt", threshold=0.3,
    )
    assert payload["determinism"] == "non-deterministic by design"


# --- Cross-process pinning: the manifest is byte-identical across FRESH processes, exactly as
# the determinism suite pins the loop output. In-process identity (above) cannot see a process
# RNG; this is the same contract `test_reproducibility_across_processes.py` enforces for `--json`.
_PAYLOAD = (
    "import json, sys\n"
    "text = sys.stdin.read()\n"
    "from untell.scripts.run import main\n"
    "rc = main(['--tier','lite','--threshold','0.0','--seed','42','--max-iters','1',\n"
    "           '--rewriter','composite','--manifest',sys.argv[1],'--json',text])\n"
    "raise SystemExit(rc)\n"
)


def _spawn_manifest(manifest: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "PYTHONPATH": "",  # a shadowing env must not swap the package under test
        "UNTELL_LITE_NO_TORCH": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    return subprocess.run(
        [sys.executable, "-c", _PAYLOAD, manifest],
        input=TEXT.encode("utf-8"),
        capture_output=True, env=env, cwd=str(ROOT), timeout=600,
    )


def test_manifest_is_byte_identical_across_processes(tmp_path) -> None:
    m1 = tmp_path / "p1.json"
    m2 = tmp_path / "p2.json"
    a = _spawn_manifest(str(m1))
    b = _spawn_manifest(str(m2))
    assert a.returncode == 0, a.stderr.decode("utf-8", "replace")[-500:]
    assert b.returncode == 0, b.stderr.decode("utf-8", "replace")[-500:]
    assert m1.read_bytes() == m2.read_bytes(), (
        "the manifest differed across two fresh processes at the same input + seed — a "
        "process-global RNG is reaching a field the manifest records"
    )
