"""Killing tests for eval/tells_auroc.py mutation survivors (2026-08-14 sweep).

  line 271  logic: and -> or        direction-holds note gate.

Killed here. 133 (`<=` -> `<` on informative) is UNKILLABLE by construction:
wilson's CI width never lands EXACTLY on 0.5 across the (s, n) search space
(verified 1..100 x 1..300, zero hits) — same class as the composite 1e-9 proofs.
Other survivors are rounding/CLI constants — annotated in survivors.md.
"""

from __future__ import annotations


class TestDirectionNoteGate:
    """Survivor tells_auroc.py:271 — `not informative and direction and p<=0.05` -> `or`.

    The "direction holds" note is ONLY for uninformative rows. With `or`, an
    informative row with a significant direction also gets the note, confusing
    the read (informative = size IS pinned)."""

    def test_informative_row_does_not_get_direction_note(self, monkeypatch, capsys) -> None:
        # em_dash: 10 human, 0 ai -> informative=True (width small) AND
        # p_direction tiny (10 vs 0 is significant). The note must NOT appear.
        human = "One word here — dash. " * 10
        ai = "plain text with no dashes here at all. "

        def _pairs(dataset, n=200, min_words=60):
            return [(human, ai) for _ in range(10)]

        monkeypatch.setattr("eval.datasets.load_pairs", _pairs)
        from eval.tells_auroc import main

        main(["--precision", "--dataset", "raid", "--pairs", "10"])
        out = capsys.readouterr().out
        assert "direction holds" not in out, f"informative row must not get direction note:\n{out}"
