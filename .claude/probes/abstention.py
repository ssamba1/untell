"""score_text abstention: all detectors erroring -> scored False, honest warning, no phantom verdict."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.score import score_text, _verdict_threshold

out = {}
# Normal scoring still works
s = score_text("The system reads the file and processes the records in order.", tier="lite")
out["normal_scored"] = s.get("scored") is not False
# Force all detectors to fail via monkeypatch: lite detector raises
import untell.detectors.perplexity_burstiness as pb
orig = pb.PerplexityBurstinessDetector.score
def boom(self, text):
    raise RuntimeError("model exploded")
pb.PerplexityBurstinessDetector.score = boom
try:
    s2 = score_text("Some text that should fail to score.", tier="lite")
    out["failed_scored_field"] = s2.get("scored")
    out["failed_max"] = s2.get("max")
    out["failed_flagged"] = s2.get("flagged")
    out["failed_warning"] = bool(s2.get("warning"))
finally:
    pb.PerplexityBurstinessDetector.score = orig
print(json.dumps(out, indent=1))
