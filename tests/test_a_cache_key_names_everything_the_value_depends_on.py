"""A key that omits something the value depends on returns a plausible wrong answer.

Round ninety-five lost a measurement to this. CPython caches bytecode on `(mtime, size)`; every
mutation the harness makes is a single-character swap, so size is unchanged, and a write inside the
same mtime second left the stale `.pyc` valid. The key was incomplete, the lookup hit, the mutated
code never ran, and the mutant was scored a survivor. The mutation score came out **3.7 points low**
and nothing about the output looked wrong.

That is not a Python quirk. It is the general failure of caching, and this repository already has a
scar from the same shape in its own code: `untell/scripts/score.py` carries a comment about a score
cached under one torch mode being read by an env-pinned test under another, **56 assertions failing
in one full-suite run** before the scoring mode was added to the key.

So `eval/cache_keys.py` checks every cached function here for it. Two checks, because the audit
alone cannot prevent the failure it finds:

* **Key completeness** — a function wrapped in `lru_cache` returns the same value for the same
  arguments forever, so anything its body reads that is not an argument is a way two calls
  deserving different answers will not get them.
* **Tests that patch behind a cache** — `human_base_rates` has an empty key and reads a committed
  file; the one test that varies that file clears the cache on both sides, and *nothing made it*.
  A test that patches and forgets gets the previous value and, because an `lru_cache` outlives the
  test, poisons every later test in the process.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from eval import cache_keys

REPO = Path(__file__).resolve().parent.parent


def test_no_cached_function_reads_state_its_key_does_not_name():
    report = cache_keys.audit()
    assert not report["findings"], [
        f"{f['key']} args={f['arguments']} reads "
        f"{sorted({r['category'] for r in f['reads_outside_arguments']})}"
        for f in report["findings"]
    ]


def test_no_test_patches_behind_a_cache_without_clearing_it():
    findings = cache_keys.tests_that_patch_behind_a_cache()
    assert not findings, [
        f"{f['test']} patches {f['module']}.{f['patched']} without clearing "
        f"{', '.join(f['cached'])}" for f in findings
    ]


def test_the_audit_actually_found_the_caches():
    """A scan that silently stops matching reports a clean repository."""
    rows = cache_keys.cached_functions()
    assert len(rows) >= 5
    names = {r["function"] for r in rows}
    assert "human_base_rates" in names, "the one with an empty key must still be seen"


def test_every_accepted_entry_carries_a_reason_and_still_exists():
    """An allow-list without reasons is a silencing mechanism; one with dead entries is a lie."""
    live = {f"{r['file']}:{r['function']}" for r in cache_keys.cached_functions()}
    for key, reason in cache_keys.ACCEPTED.items():
        assert key in live, f"{key} is accepted but no longer exists — remove the entry"
        assert len(reason) > 60, f"{key}: a reason short enough to be a shrug is not a triage"


def test_a_patch_of_the_wrong_name_is_not_flagged(tmp_path, monkeypatch):
    """The false positive the first version produced, pinned so the rule stays narrow.

    `tests/test_detectors.py` patches `untell.scripts.tells.score_tells`, which `human_base_rates`
    does not read. Flagging it would prompt a `cache_clear()` that clears nothing.
    """
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "untell" / "scripts").mkdir(parents=True)
    (root / "eval").mkdir()
    (root / "untell" / "scripts" / "tells.py").write_text(textwrap.dedent("""
        from functools import lru_cache
        _BASE_RATES_PATH = None

        def score_tells(text):
            return {}

        @lru_cache(maxsize=1)
        def human_base_rates():
            return _BASE_RATES_PATH.read_text()
    """))
    (root / "tests" / "test_unrelated.py").write_text(
        'def test_x(monkeypatch):\n'
        '    monkeypatch.setattr("untell.scripts.tells.score_tells", lambda t: {})\n'
    )
    assert cache_keys.tests_that_patch_behind_a_cache(root) == []


def test_a_patch_of_the_right_name_is_flagged(tmp_path):
    """And the rule must still fire on the case it exists for."""
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "untell" / "scripts").mkdir(parents=True)
    (root / "eval").mkdir()
    (root / "untell" / "scripts" / "tells.py").write_text(textwrap.dedent("""
        from functools import lru_cache
        _BASE_RATES_PATH = None

        @lru_cache(maxsize=1)
        def human_base_rates():
            return _BASE_RATES_PATH.read_text()
    """))
    (root / "tests" / "test_patches.py").write_text(
        'def test_x(monkeypatch, tmp_path):\n'
        '    monkeypatch.setattr("untell.scripts.tells._BASE_RATES_PATH", tmp_path / "x")\n'
    )
    findings = cache_keys.tests_that_patch_behind_a_cache(root)
    assert len(findings) == 1
    assert findings[0]["patched"] == "_BASE_RATES_PATH"
    assert findings[0]["cached"] == ["human_base_rates"]


def test_clearing_the_cache_anywhere_in_the_test_module_satisfies_the_rule(tmp_path):
    """Deliberately module-level rather than per-test: a fixture may do the clearing."""
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "untell" / "scripts").mkdir(parents=True)
    (root / "eval").mkdir()
    (root / "untell" / "scripts" / "tells.py").write_text(textwrap.dedent("""
        from functools import lru_cache
        _BASE_RATES_PATH = None

        @lru_cache(maxsize=1)
        def human_base_rates():
            return _BASE_RATES_PATH.read_text()
    """))
    (root / "tests" / "test_patches.py").write_text(
        'from untell.scripts.tells import human_base_rates\n'
        'def test_x(monkeypatch, tmp_path):\n'
        '    human_base_rates.cache_clear()\n'
        '    monkeypatch.setattr("untell.scripts.tells._BASE_RATES_PATH", tmp_path / "x")\n'
    )
    assert cache_keys.tests_that_patch_behind_a_cache(root) == []


def test_the_existing_base_rates_test_is_the_pattern_the_rule_wants():
    """The one test that varies the file does clear the cache — on both sides."""
    body = (REPO / "tests" / "test_a_tell_count_says_how_often_humans_do_it_too.py").read_text()
    assert body.count("cache_clear") >= 2, (
        "clearing before the patch and after it: the first stops a stale read, the second stops "
        "this test's own value outliving it"
    )
