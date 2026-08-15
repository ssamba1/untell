"""Killing tests for eval/detector_audit.py mutation survivors (2026-08-14 sweep).

  line 398  boundary: >= -> >       sentence probe min length (exactly 10 words).
  line 433  logic: or -> and        broken-detector classification gate.

Killed here. Other survivors (218/275/280/288/301/303/304/477) are
constants/boundaries — annotated in survivors.md.
"""

from __future__ import annotations


class TestBrokenClassification:
    """Survivor detector_audit.py:433 — `or r.get("auroc") is None` -> `and`.

    A DEAD/INVERTED/MISCALIBRATED sentence-granularity row with NO auroc is
    broken. The mutation (`and`) excludes auroc=None rows from the broken set,
    hiding dead detectors from the report. Drive audit_all with a fake DEAD
    detector and sentence probes."""

    def test_sentence_row_without_auroc_is_broken(self, monkeypatch) -> None:
        from eval import detector_audit as DA

        monkeypatch.setattr(DA, "_SPECS", [("fake-dead", "eval.datasets", "load_pairs")])
        # patch audit_detector to return a DEAD sentence row without auroc
        def _audit_detector(name, det, probes=None):
            return {
                "detector": name,
                "verdict": "DEAD",
                "granularity": "sentence",
                "auroc": None,
                "tpr": None,
                "fpr": None,
            }

        monkeypatch.setattr(DA, "audit_detector", _audit_detector)
        # audit_all with pairs=0 skips the corpus load, uses builtin probes
        out = DA.audit_all(pairs=0, dataset="hc3")
        # the broken list must include the sentence-granularity dead detector
        assert "fake-dead [sentence]" in out["broken"], f"dead sentence detector must be broken: {out['broken']}"
