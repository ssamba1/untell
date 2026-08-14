"""_code_state stamps the commit; _pinned_note names the pinned detector."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from eval.ceiling import _code_state, _pinned_note

out = {}
cs = _code_state()
out["code_state"] = cs
out["has_commit"] = len(cs) >= 7 and (cs != "unknown")
out["dirty_flag"] = cs.endswith("+dirty") or not cs.endswith("+dirty")
# pinned note: max detector barely moved while another did -> note fires
r = {
    "per_detector_pre": {"mage": 1.0, "hc3_roberta": 0.9, "roberta_openai": 0.8},
    "per_detector_post": {"mage": 0.99, "hc3_roberta": 0.4, "roberta_openai": 0.3},
}
note = _pinned_note(r)
out["pinned_note_fires"] = len(note) > 0 and "pinned by mage" in note[1]
# all moved -> no note
r2 = {"per_detector_pre": {"a": 1.0}, "per_detector_post": {"a": 0.2}}
out["all_moved_no_note"] = _pinned_note(r2) == []
print(json.dumps(out, indent=1))
