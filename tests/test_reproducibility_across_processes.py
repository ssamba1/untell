"""Same input + seed in SEPARATE processes must produce byte-identical bytes.

In-process repeatability (`test_the_loop_is_reproducible.py`) cannot see cross-process drift:
an RNG seeded from OS entropy at process start reproduces perfectly within one process and
differs between two. Every stochastic component must therefore be re-seeded from the loop's
seed inside each fresh process — and the only way to prove that is to compare processes.

The lite tier is the contract that must hold everywhere (stdlib path, no model downloads for
the loop itself): the CLI's documented environment is `UNTELL_LITE_NO_TORCH=1`, and every
figure in this repository's published measurements was produced through it.

The sampled T5 path is the one place the seed used to NOT reach the RNG: `untell_text` seeds
Python's `random` module, which torch never consults, and `T5ParaphraseRewriter(sample=True)`
drew from OS-entropy-seeded torch RNG. MEASURED before the fix: two fresh processes, same
input, same seed — 320 bytes vs 304 bytes. After the fix both emit the same bytes. The
reproducibility test for that path loads the ~850MB model, so it runs only when the model is
already cached (it is skipped, not assumed, when it is not — a missing cache is an
environment fact, not evidence about determinism).

Every subprocess runs offline (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`) so the test
cannot depend on the network, and with `PYTHONPATH` emptied so a shadowing environment cannot
swap the package being measured.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Short enough to keep subprocess runtime low, tell-bearing enough to force rewrites at
# threshold=0.0 (the same guard `test_the_loop_is_reproducible.py` uses: at the default
# threshold this text scores below the bar and the loop no-ops, which is trivially
# reproducible and proves nothing).
TEXT = (
    "Moreover, the framework leverages a robust approach to deliver transformative outcomes "
    "for every stakeholder. Furthermore, it underscores the pivotal integration of modern "
    "methodologies. In conclusion, the comprehensive solution demonstrates significant value "
    "across the entire organizational landscape and beyond."
)

# One payload, three modes; the input travels on stdin so the test text never has to survive
# a command line, and the seed travels as argv. `-c` keeps the worker next to its assertions
# instead of a second module that can drift from what the test believes it ran.
PAYLOAD = (
    "import json, sys\n"
    "seed = int(sys.argv[1])\n"
    "mode = sys.argv[2]\n"
    "text = sys.stdin.read()\n"
    "if mode == 'untell':\n"
    "    from untell.scripts.run import untell_text\n"
    "    r = untell_text(text, tier='lite', threshold=0.0, seed=seed, max_iters=2,\n"
    "                    rewriter='composite', best_of=3)\n"
    "    print(json.dumps({'final': r['final'], 'iterations': r['iterations'],\n"
    "                      'pre_max': r['pre']['max'], 'post_max': r['post']['max'],\n"
    "                      'seed': r.get('seed')}, sort_keys=True))\n"
    "elif mode == 'score':\n"
    "    from untell.scripts.score import score_text\n"
    "    print(json.dumps(score_text(text, tier='lite'), sort_keys=True, default=str))\n"
    "elif mode == 'cli':\n"
    "    from untell.scripts.run import main\n"
    "    raise SystemExit(main(['--tier', 'lite', '--threshold', '0.0', '--seed',\n"
    "                           str(seed), '--max-iters', '2', '--rewriter', 'composite',\n"
    "                           '--json', text]))\n"
    "elif mode == 't5':\n"
    "    import random\n"
    "    random.seed(seed)  # emulate the loop's seeded region (run.py seeds global random)\n"
    "    from untell.rewriter.t5_paraphrase import T5ParaphraseRewriter\n"
    "    rw = T5ParaphraseRewriter(sample=True)\n"
    "    print(json.dumps({'final': rw.rewrite(text, {'tier': 'lite'}, 0.30)},\n"
    "                     sort_keys=True))\n"
)


def _spawn(mode: str, seed: int = 42, text: str = TEXT) -> subprocess.CompletedProcess:
    """One fresh process running `mode` at `seed`; stdout compared as raw bytes."""
    env = {
        **os.environ,
        "PYTHONPATH": "",  # a shadowing env must not swap the package under test
        "UNTELL_LITE_NO_TORCH": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    return subprocess.run(
        [sys.executable, "-c", PAYLOAD, str(seed), mode],
        input=text.encode("utf-8"),
        capture_output=True,
        env=env,
        cwd=str(ROOT),
        timeout=600,
    )


def _assert_ran(proc: subprocess.CompletedProcess, mode: str) -> None:
    assert proc.returncode == 0, (
        f"{mode} subprocess exited {proc.returncode}: "
        f"{proc.stderr.decode('utf-8', 'replace')[-500:]}"
    )
    assert proc.stdout, f"{mode} subprocess produced no stdout"


def test_untell_text_is_byte_identical_across_processes() -> None:
    a, b = _spawn("untell"), _spawn("untell")
    _assert_ran(a, "untell")
    _assert_ran(b, "untell")
    assert a.stdout == b.stdout, (
        "untell_text gave different bytes in two fresh processes at the same seed. "
        "A process-global RNG (torch, or an unseeded `random` draw) is reaching the loop."
    )


def test_score_is_byte_identical_across_processes() -> None:
    a, b = _spawn("score"), _spawn("score")
    _assert_ran(a, "score")
    _assert_ran(b, "score")
    assert a.stdout == b.stdout, "score_text gave different bytes in two fresh processes"


def test_humanize_cli_is_byte_identical_across_processes() -> None:
    a, b = _spawn("cli"), _spawn("cli")
    _assert_ran(a, "cli")
    _assert_ran(b, "cli")
    assert a.stdout == b.stdout, "untell-humanize --json gave different bytes in two fresh processes"


def test_the_rewrite_actually_happened() -> None:
    """Three identical no-ops are also 'byte-identical across processes' — the trivial pass.

    `test_the_loop_is_reproducible.py` caught this exact hazard for its own fixture; the same
    guard belongs here. threshold=0.0 exists to force the loop to run.
    """
    proc = _spawn("untell")
    _assert_ran(proc, "untell")
    import json

    assert json.loads(proc.stdout)["final"] != TEXT, "the loop left the text untouched"


def test_a_different_seed_names_a_different_stream_across_processes() -> None:
    """The byte-identity above must be PINNED to the seed, not to a constant output.

    One process at seed 42 and one at seed 43 must differ; if they match, the test above
    passes for the wrong reason (a component that ignores the seed and always emits the same
    thing is 'reproducible' in exactly the way this file checks and exactly the way a user
    does not want).
    """
    a, b = _spawn("untell", seed=42), _spawn("untell", seed=43)
    _assert_ran(a, "untell")
    _assert_ran(b, "untell")
    assert a.stdout != b.stdout, "two seeds produced identical bytes; the seed is inert"


def test_the_sampled_t5_path_is_byte_identical_across_processes() -> None:
    """The one component the loop's seed used to miss: torch sampling.

    Runs only when the ~850MB model is already cached — `pytest.skip` (not a decorator) so a
    cache-less machine reports the environment fact instead of a false failure.
    """
    cached = Path.home() / ".cache" / "huggingface" / "hub" / (
        "models--humarin--chatgpt_paraphraser_on_T5_base"
    )
    if not (cached / "snapshots").is_dir():
        pytest.skip("T5 paraphrase model not in the HF cache; sampled-path proof needs it")
    short = "Moreover, the framework leverages a robust approach to deliver outcomes."
    a = _spawn("t5", text=short)
    b = _spawn("t5", text=short)
    _assert_ran(a, "t5")
    _assert_ran(b, "t5")
    assert a.stdout == b.stdout, (
        "T5ParaphraseRewriter(sample=True) gave different bytes in two fresh processes at "
        "the same seed: torch's RNG is not being seeded from the loop seed"
    )
