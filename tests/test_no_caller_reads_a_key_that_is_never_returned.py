"""The reverse of the documented-keys check, and the one that catches what actually happens.

`tests/test_every_returned_key_is_documented.py` checks that every key these functions RETURN
appears in `docs/result-shapes.md`. That catches an undocumented key.

**It cannot catch reading a key that is never returned**, which is the failure that keeps occurring.
`dict.get` yields `None`, and `None` flows on to become a plausible number, an empty list, or a
skipped branch. The document says so in its own opening — *"guessing wrong returns a plausible value
rather than raising"* — and this session produced **six** instances anyway, in code written by
someone who had read it: `score_text(...)["score"]` scored 0 of 6,842 documents after a twenty-minute
run; `score_sentences(...)["spread"]` made a boundary test assert nothing; `humanize_diff(...)`'s
`removed` is `removed_lines`; `score_tells(...)`'s caveat is `warning`, not `caveats`.

`eval/result_keys.py` closes it statically: track `name = FUNC(...)`, then flag every `name["k"]`
and `name.get("k")` whose key that function does not return.

MEASURED on the repository: **eight conditional keys were genuinely undocumented** — `scored`,
`out_of_range_detectors`, `timings`, `voice_warning`, `rewriter_warning`, `error`, `evidence_note`,
`matches` — every one returned only under a non-default argument or a failure path, which is exactly
what the forward check's payloads never exercise. All eight are documented now.

It also found a **tautology**: `assert result.get("detector_modes", {}) or True`, an assertion that
could not fail, reading a key `score_sentences` does not return.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from eval import result_keys

REPO = Path(__file__).resolve().parent.parent


def _scan(source: str, tmp_path: Path) -> list[dict]:
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "eval").mkdir(exist_ok=True)
    (root / "untell").mkdir(exist_ok=True)
    (root / "tests" / "test_probe.py").write_text(textwrap.dedent(source))
    return result_keys.reads(root, {"score_text": {"max", "flagged"}})


def test_no_caller_reads_a_key_its_function_does_not_return():
    findings = result_keys.audit()["findings"]
    assert not findings, [
        f"{f['file']}:{f['line']} {f['variable']}[{f['key']!r}] — {f['producer']}() returns "
        f"{f['documented']}" for f in findings[:8]
    ]


def test_the_documented_shapes_were_actually_parsed():
    """An empty parse would make the check pass on everything."""
    shapes = result_keys.documented()
    assert set(shapes) >= {"score_text", "score_tells", "score_sentences", "untell_text"}
    assert "max" in shapes["score_text"]
    assert "scored" in shapes["score_text"], "the conditional keys must be in the list too"
    assert "tells_per_100w" in shapes["score_tells"]


def test_it_catches_the_exact_mistake_that_started_this(tmp_path):
    """`score_text(...)["score"]` — the read that scored 0 of 6,842 documents."""
    found = _scan('''
        def test_x():
            result = score_text("hello")
            return result.get("score")
    ''', tmp_path)
    assert [f["key"] for f in found] == ["score"]


def test_it_catches_a_subscript_as_well_as_a_get(tmp_path):
    found = _scan('''
        def test_x():
            result = score_text("hello")
            return result["spread"]
    ''', tmp_path)
    assert [f["key"] for f in found] == ["spread"]


def test_a_documented_key_is_not_flagged(tmp_path):
    found = _scan('''
        def test_x():
            result = score_text("hello")
            return result["max"], result.get("flagged")
    ''', tmp_path)
    assert found == []


def test_reassignment_clears_the_origin(tmp_path):
    """Without this, every later read of the name is attributed to the wrong function."""
    found = _scan('''
        def test_x():
            result = score_text("hello")
            result = {"anything": 1}
            return result["anything"]
    ''', tmp_path)
    assert found == []


def test_a_loop_variable_does_not_inherit_an_earlier_origin(tmp_path):
    """`for r in rows:` rebinds. MEASURED: seven false findings in one file before this."""
    found = _scan('''
        def test_x(rows):
            r = score_text("hello")
            for r in rows:
                print(r["category"])
    ''', tmp_path)
    assert found == []


def test_a_parameter_named_result_is_not_a_module_level_result(tmp_path):
    """MEASURED: `eval/holdout.py`'s `render(result)` gave six false findings before this."""
    found = _scan('''
        result = score_text("hello")

        def render(result):
            return result["config"]
    ''', tmp_path)
    assert found == []


def test_a_nested_function_shadowing_the_name_is_not_flagged(tmp_path):
    """`inner(result)` binds its own `result`; the outer one is a different variable.

    Named for what it asserts. It was `test_the_scan_does_not_descend_into_nested_functions` until
    round 105, when the scan started descending on purpose — a test whose name states the opposite
    of the design is a defect even while it passes, because the next reader trusts the name.
    """
    found = _scan('''
        def outer():
            result = score_text("hello")

            def inner(result):
                return result["whatever"]
            return inner
    ''', tmp_path)
    assert found == []


def test_a_closure_reading_the_outer_result_IS_flagged(tmp_path):
    """The gap round 105's recall plants found, and the reason the scan now descends.

    Round 102 pruned nested bodies out of the module scan to kill false positives. That fix created
    a blind spot nobody would have noticed from the findings, because a blind spot produces none:
    a closure reading a key the outer result does not have was never checked at all.
    """
    found = _scan('''
        def outer():
            result = score_text("hello")

            def inner():
                return result["whatever"]
            return inner
    ''', tmp_path)
    assert [f["key"] for f in found] == ["whatever"]


def test_the_tautology_it_found_is_gone():
    """`assert X or True` cannot fail. It was reading a key that does not exist, too."""
    body = (REPO / "tests" / "test_targeting_caveat_follows_the_path_that_ran.py").read_text()
    # Comments are excluded: the replacement QUOTES the tautology to explain it, and a check that
    # trips on its own documentation is the false-alarm failure three checkers here have already had.
    code = [line.split("#", 1)[0] for line in body.splitlines()]
    assert not [line for line in code if "or True" in line], (
        "an assertion that cannot fail is not an assertion"
    )
