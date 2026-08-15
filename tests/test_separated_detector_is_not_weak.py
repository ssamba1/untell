"""A well-separated detector must not be called WEAK.

eval/detector_audit.py:284: `elif au is not None and au < WEAK_AUROC: verdict =
"WEAK"` — WEAK requires an AUROC below 0.65. The mutation and -> or makes the
branch fire whenever au is present (always True), so a detector with AUROC 1.0
and perfect separation is downgraded from OK_SEPARATED to WEAK — a healthy
detector reported as barely-responding.
"""
from eval.detector_audit import audit_detector


class _Det:
    def available(self):
        return True

    def score(self, t):
        return {"h1": 0.1, "h2": 0.2, "a1": 0.7, "a2": 0.8}.get(t, 0.5)


def test_separated_detector_is_not_weak():
    r = audit_detector("test", _Det(), (["h1", "h2"], ["a1", "a2"]))
    assert r["auroc"] == 1.0
    assert r["verdict"] == "OK_SEPARATED", r["verdict"]
