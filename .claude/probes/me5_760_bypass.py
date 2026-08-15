"""Probe: humanness CLI render (untell/humanness.py main) + score bypass guard
(untell/scripts/score.py _score_with_detectors). Pass 760 assignment.
Run: PYTHONPATH= UNTELL_LITE_NO_TORCH=1 .venv/Scripts/python.exe .claude/probes/me5_760_bypass.py
"""
import io
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

out = {}

# ---------------- PROBE 1: humanness CLI render ----------------
from untell.humanness import main as humanness_main

# 1a. Valid text (>= 5 words so undetermined_reason is None -> exit 0)
VALID = (
    "The committee reviewed the proposal carefully and decided that the revised "
    "budget should be presented to the board next week for final approval."
)
buf = io.StringIO()
real_stdout = sys.stdout
sys.stdout = buf
try:
    rc = humanness_main([VALID])
finally:
    sys.stdout = real_stdout
line = buf.getvalue()
m = re.search(r"Humanness: ([\d.]+)/100\s+\(([\w ]+)\)\s+\[tier=(\w+)\]", line)
out["1a_valid_rc"] = rc
out["1a_stdout"] = line.strip()
out["1a_line_matches"] = bool(m)
if m:
    out["1a_score"] = float(m.group(1))
    out["1a_classification"] = m.group(2)
    out["1a_tier"] = m.group(3)
out["1a_score_in_line"] = m is not None and m.group(1) in line
out["1a_classword_in_line"] = m is not None and m.group(2) in line

# 1b. Literal short 'TEXT' (1 word -> documented abstention, exit 2)
buf = io.StringIO()
sys.stdout = buf
try:
    rc_short = humanness_main(["TEXT"])
finally:
    sys.stdout = real_stdout
out["1b_short_rc"] = rc_short
out["1b_short_stdout"] = buf.getvalue().strip()

# 1c. No args + empty stdin -> usage error exit 2, no crash
buf = io.StringIO()
sys.stdout = buf
old_stdin = sys.stdin
sys.stdin = io.StringIO("")
try:
    rc_empty = humanness_main([])
finally:
    sys.stdin = old_stdin
    sys.stdout = real_stdout
out["1c_noargs_rc"] = rc_empty
out["1c_noargs_stdout"] = buf.getvalue().strip()

# ---------------- PROBE 2: score bypass guard ----------------
from untell.scripts.score import _score_with_detectors


class FakeDet:
    """Minimal stand-in: name, tier, score(), mode() — all _score_with_detectors touches."""

    def __init__(self, name, value, tier="lite", raises=False):
        self.name = name
        self._value = value
        self.tier = tier
        self._raises = raises

    def score(self, text):
        if self._raises:
            raise RuntimeError("boom")
        return self._value

    def mode(self):
        return "fake"


TXT = "this is a perfectly ordinary English sentence about nothing in particular."

# 2a. ALL detectors return None -> scored=False, flagged=False, abstention warning
res_all = _score_with_detectors(
    [FakeDet("a", None), FakeDet("b", None), FakeDet("c", None)], TXT
)
out["2a_all_none"] = {
    "scored": res_all.get("scored"),
    "flagged": res_all.get("flagged"),
    "max": res_all.get("max"),
    "mean": res_all.get("mean"),
    "warning_abstention": "no detector produced a score" in (res_all.get("warning") or ""),
    "warning": res_all.get("warning"),
}

# 2b. SOME detectors None -> scores from survivors + ensemble warning
res_part = _score_with_detectors(
    [FakeDet("a", 0.1), FakeDet("b", None), FakeDet("c", 0.9)], TXT
)
w = res_part.get("warning") or ""
out["2b_partial"] = {
    "scored_key_present": "scored" in res_part,
    "flagged": res_part.get("flagged"),
    "max": res_part.get("max"),
    "mean": res_part.get("mean"),
    "ensemble_warning": "detectors produced a score" in w,
    "names_missing": "b returned nothing" in w,
    "errs_toward_not_flagged": "errs toward NOT flagged" in w,
    "warning": w,
}

# 2c. bonus: all detectors RAISE -> same refusal shape, failed_detectors named
res_err = _score_with_detectors(
    [FakeDet("x", None, raises=True), FakeDet("y", None, raises=True)], TXT
)
out["2c_all_error"] = {
    "scored": res_err.get("scored"),
    "flagged": res_err.get("flagged"),
    "failed_detectors": res_err.get("failed_detectors"),
    "warning_abstention": "no detector produced a score" in (res_err.get("warning") or ""),
}

print(json.dumps(out, indent=1, ensure_ascii=False))
