"""The command lines SKILL.md hands Claude must run, not merely accept their flags.

`check_skill_commands` in the audit verifies each referenced script exists and that every flag
SKILL.md passes appears in that script's `--help`. That is the "registered and advertised" check,
and the last three loops found three surfaces that pass exactly that kind of check while being
broken on invocation — a dead MCP tool, an untested REST route, three CLI entry points that could
not import their own package.

So this runs the flag combinations SKILL.md actually gives, against real input, on a bare
interpreter (`python -S`, no site-packages, which is the zero-dependency tier a skill install
lands on). MEASURED: all eleven produce output, including the two-step lock-then-restore that
returns the original text byte for byte.

The guard below is what keeps this current: every script SKILL.md names must have an invocation
here. A step added to the procedure without one is unexercised, and an unexercised step in the
procedure the model follows fails on a user's first run.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SKILL = (REPO / "untell" / "SKILL.md").read_text(encoding="utf-8")

AI = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "It significantly improves overall efficiency across the evaluated corpus."
)
REWRITE = "The framework uses solid methods to deliver outcomes at scale, and efficiency improves."


@pytest.fixture(scope="module")
def tree(tmp_path_factory) -> Path:
    """A copy of the package plus the fixture files the skill's commands read."""
    root = tmp_path_factory.mktemp("skill")
    shutil.copytree(REPO / "untell", root / "untell", ignore=shutil.ignore_patterns("__pycache__"))
    (root / "sample.txt").write_text(AI * 3, encoding="utf-8")
    (root / "draft.txt").write_text(REWRITE * 3, encoding="utf-8")
    return root


def _argv(tree: Path, script: str, *args: str) -> list[str]:
    return [sys.executable, "-S", str(tree / "untell" / "scripts" / script), *args]


def _run(argv: list[str]) -> subprocess.CompletedProcess:
    env = dict(os.environ, UNTELL_LITE_NO_TORCH="1", PYTHONIOENCODING="utf-8")
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env)


# The flag combinations SKILL.md gives, with its placeholders filled in.
INVOCATIONS = {
    "scrub.py": (AI, "--json"),
    "preserve.py": ("See Smith (2020) for the 42% figure.",),
    "score.py": (AI, "--threshold", "0.30"),
    "quality.py": (AI, REWRITE),
    "entailment.py": (AI, REWRITE),
    "roles.py": (AI, REWRITE),
    "numerals.py": (AI, REWRITE),
    "hedges.py": (AI, REWRITE),
    "sentences.py": (AI,),
    "explain.py": (AI,),
    "batch.py": ("--help",),  # full batch run needs a directory; --help proves it loads
    "tells.py": (AI,),
    "voice.py": ("--sample", "sample.txt", "--draft", "draft.txt"),
    "latex.py": ("--help",),  # its real form needs a .tex file and a .bib; --help proves it loads
    # A real run polls a directory until it changes, so it does not terminate on its own here;
    # --help proves the module loads and the CLI parses. Behaviour is covered for real by
    # tests/test_watch_cli.py (19 tests), which drives it with --max-batches so it exits.
    "watch.py": ("--help",),
}


def test_every_script_the_skill_names_is_invoked_here():
    """The guard. An unexercised step in the model's procedure fails on a user's first run."""
    named = set(re.findall(r"scripts[/\\](\w+)\.py", SKILL))
    missing = sorted(f"{s}.py" for s in named if f"{s}.py" not in INVOCATIONS)
    assert not missing, (
        f"SKILL.md tells Claude to run {missing} and nothing here invokes them. Add an entry "
        "rather than deleting this assertion."
    )


@pytest.mark.parametrize("script", sorted(INVOCATIONS))
def test_the_command_line_runs(tree: Path, script: str):
    args = tuple(
        str(tree / a) if a.endswith(".txt") else a for a in INVOCATIONS[script]
    )
    result = _run(_argv(tree, script, *args))

    assert "Traceback" not in result.stderr, f"{script}:\n{result.stderr[-400:]}"
    assert result.returncode == 0, f"{script} exited {result.returncode}: {result.stderr[-300:]}"
    assert result.stdout.strip(), f"{script} exited 0 with no output"


def test_lock_then_restore_returns_the_original(tree: Path):
    """Two steps of the procedure joined, which is where a user's citations come back.

    Neither half failing on its own would show this: `preserve.py` can lock correctly and the
    restore step can still mangle the text, and SKILL.md pipes one into the other.
    """
    original = "See Smith (2020) for the 42% figure in config.yaml."

    locked = _run(_argv(tree, "preserve.py", original))
    assert locked.returncode == 0, locked.stderr[-300:]
    payload = json.loads(locked.stdout)
    assert payload["mapping"], "nothing was locked, so the restore proves nothing"

    restored = _run(
        _argv(tree, "preserve.py", payload["masked"], "--restore",
              "--mapping", json.dumps(payload["mapping"]))
    )
    assert restored.returncode == 0, restored.stderr[-300:]
    assert restored.stdout.strip() == original
