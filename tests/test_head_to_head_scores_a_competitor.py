"""The head-to-head harness must not flatter either side.

Its whole reason to exist is that `docs/why-best-open-repo.md` ranked a competitor without ever
running anything of theirs, so the failure modes that matter here are the ones that would let it
produce a comfortable number: scoring misaligned rows, silently substituting the weak similarity
metric for the meaning gate, or counting an empty rewrite as a clean pass.
"""

from __future__ import annotations

import json

import pytest

from eval.head_to_head import compare, load_jsonl, render

_SRC = [
    "The trial enrolled 42 patients and may reduce mortality by 7 percent over two years.",
    "Only 3 of the 19 builds passed, which suggests the cache layer is usually at fault.",
]


def test_an_identical_rewrite_keeps_everything():
    """The control. If this is not 100% the gates are broken and no other row means anything."""
    r = compare(_SRC, list(_SRC), label="identity")
    assert r["numerals_kept_rate"] == 1.0
    assert r["certainty_kept_rate"] == 1.0
    assert r["both_kept_rate"] == 1.0
    assert r["token_overlap_mean"] == pytest.approx(1.0)


def test_a_dropped_number_is_counted_not_averaged_away():
    rewrites = [
        "The trial enrolled dozens of patients and may reduce mortality somewhat.",
        _SRC[1],
    ]
    r = compare(_SRC, rewrites)
    assert r["numerals_kept_rate"] == 0.5
    assert r["documents_dropping_a_number"] == 1
    # 42, 7 and two all vanish into "dozens"/"somewhat": the count is of NUMBERS, not documents.
    assert r["numbers_dropped_total"] >= 2


def test_a_firmed_up_claim_fails_the_certainty_gate():
    rewrites = [
        "The trial enrolled 42 patients and reduces mortality by 7 percent over two years.",
        _SRC[1],
    ]
    r = compare(_SRC, rewrites)
    assert r["certainty_kept_rate"] == 0.5, "'may reduce' -> 'reduces' must not read as preserved"


def test_an_empty_rewrite_is_excluded_rather_than_scored():
    """An empty string evades every detector and carries zero tells.

    Scored as an ordinary row it is a perfect result, which is the single most flattering thing
    this harness could report about a competitor. It is excluded and counted separately instead.
    """
    r = compare(_SRC, ["", _SRC[1]])
    assert r["degenerate_rewrites"] == 1
    assert r["n"] == 1
    assert r["numerals_kept_rate"] == 1.0
    assert "1 empty rewrites excluded" in render(r)


def test_every_rewrite_being_empty_is_an_error_not_a_perfect_score():
    with pytest.raises(ValueError, match="no letters"):
        compare(_SRC, ["", "   "])


def test_misaligned_corpora_are_refused():
    """Truncating to the shorter list would silently compare row i to a different document."""
    with pytest.raises(ValueError, match="row counts differ"):
        compare(_SRC, _SRC[:1])


def test_the_weak_similarity_metric_never_passes_as_a_meaning_verdict():
    """token_overlap is documented as advisory; it must be labelled, and the gap declared."""
    r = compare(_SRC, list(_SRC))
    assert "token_overlap" in r["gates_run"]
    assert r["token_overlap_confidence"] in {"low", "medium", "high"}
    assert "meaning" not in {k.lower() for k in r}, "no key may read as a meaning verdict"
    # Whatever is missing has to be named. Nothing here may report a silent pass.
    for gate in r["gates_unavailable"]:
        assert "NO" in gate or "needs" in gate


def test_render_names_each_gate_that_did_not_run():
    r = compare(_SRC, list(_SRC))
    text = render(r)
    for gate in r["gates_unavailable"]:
        assert gate in text, "a gate that did not run must be visible in the human-readable output"


def test_load_jsonl_reads_both_shapes(tmp_path):
    p = tmp_path / "c.jsonl"
    p.write_text(json.dumps({"text": "one"}) + "\nplain second line\n", encoding="utf-8")
    assert load_jsonl(str(p)) == ["one", "plain second line"]
