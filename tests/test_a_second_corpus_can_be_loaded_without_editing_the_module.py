"""The assisted arm could read exactly one schema, and status row 19 asks for three more corpora.

Row 19 — loaders for Beemo, ARB and the LREC resume corpus — has been open as "buildable now". The
blocker was never the loaders. `load_rows` hard-coded the Pratama corpus's `Status` and `Abstract`
column names and `ARMS` hard-coded its five arm columns, so a second corpus could not be loaded at
all without editing the module. A `CorpusSpec` makes adding one a declaration.

**What this deliberately does not do is ship guessed schemas for the three named corpora.** Their
files cannot be fetched here — `huggingface.co` returns 403, VERIFIED — and a loader written against
a schema nobody has inspected is the confident-and-wrong failure this repository exists to catch: it
crashes on the real file, or worse, quietly selects nothing and reports a clean arm. What ships is
the generic path plus a validator that names the missing column before anything is scored.

The generic path is checked against the specific one on the REAL corpus rather than on a fixture,
because a generalisation that agrees with its predecessor only on data invented to make it agree has
not been checked at all.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from eval.assisted_fairness import PRATAMA, CorpusSpec, load_mapped, load_rows, validate

REAL = Path(".assisted-cache/pratama_abstracts.csv")


def _fixture(tmp_path: Path, header: list[str], rows: list[list[str]]) -> Path:
    path = tmp_path / "corpus.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return path


@pytest.mark.skipif(not REAL.exists(), reason="the Pratama corpus is not cached here")
def test_the_generic_loader_reproduces_the_hard_coded_one_on_the_real_corpus() -> None:
    """The only check that means anything: same file, same rows, no fixture in sight."""
    assert validate(REAL, PRATAMA) == [], "the shipped spec does not match the shipped corpus"
    assert len(load_mapped(REAL, PRATAMA)) == len(load_rows(REAL))


def test_a_spec_that_does_not_match_its_file_is_refused_before_scoring() -> None:
    """The failure this prevents is silent. A mistyped arm column yields no rows for that arm, and
    an arm with no rows reports as an arm with nothing to say rather than as a spec that is wrong —
    the same shape as round 115's untested-technique row, one layer down."""
    path = _fixture(Path("/tmp"), ["Status", "Abstract"], [["native", "some text here"]])
    spec = CorpusSpec(name="typo", status_column="Statuss", arms={"Abstrct": "human"})
    assert set(validate(path, spec)) == {"Statuss", "Abstrct"}
    with pytest.raises(ValueError) as excinfo:
        load_mapped(path, spec)
    assert "selects nothing" in str(excinfo.value), "the error must say why an empty arm is not a result"


def test_a_second_corpus_needs_no_edit_to_the_module(tmp_path: Path) -> None:
    """The row's actual deliverable. A corpus with entirely different column names loads through a
    declaration alone."""
    path = _fixture(
        tmp_path,
        ["author_background", "authentic_text", "enhanced_text", "generated_text"],
        [["L2", "a human wrote this", "an assisted version", "a generated version"],
         ["L1", "another human text", "", ""]],
    )
    spec = CorpusSpec(
        name="resume-like",
        status_column="author_background",
        arms={"authentic_text": "human", "enhanced_text": "assisted",
              "generated_text": "generated"},
        human_arms=("human",),
    )
    assert validate(path, spec) == []
    rows = load_mapped(path, spec)
    assert len(rows) == 2
    assert rows[0]["author_background"] == "L2"


def test_a_row_with_a_status_but_no_text_in_any_arm_is_dropped(tmp_path: Path) -> None:
    """`load_rows` required the ORIGINAL abstract specifically. The generic form cannot: a corpus
    whose human arm is absent for some rows still has usable assisted and generated arms, and
    requiring one named column would silently discard them."""
    path = _fixture(
        tmp_path,
        ["Status", "Abstract", "AI-Generated ChatGPT"],
        [["native", "", "a generated abstract"],      # keep: one arm has text
         ["native", "", ""],                          # drop: no arm has text
         ["", "orphaned text", ""]],                  # drop: no status to stratify by
    )
    spec = CorpusSpec(name="partial", status_column="Status",
                      arms={"Abstract": "human", "AI-Generated ChatGPT": "generated_chatgpt"})
    assert len(load_mapped(path, spec)) == 1
