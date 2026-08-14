"""local_judge + llm_judge: the local judge's available() and error paths."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.detectors.local_judge import LocalJudgeDetector
from untell.detectors.llm_judge import LLMJudgeDetector

out = {}
for cls in (LocalJudgeDetector, LLMJudgeDetector):
    try:
        d = cls()
        out[d.name] = {"available": d.available(), "tier": d.tier}
    except Exception as e:
        out[cls.__name__] = {"error": f"{type(e).__name__}: {str(e)[:70]}"}
print(json.dumps(out, indent=1))
