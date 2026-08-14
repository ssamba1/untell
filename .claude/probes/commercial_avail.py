"""Commercial detectors: unavailable without keys, available() False never raises."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.detectors.commercial import (OriginalityDetector, WinstonDetector, GPTZeroDetector,
                                          SaplingDetector, ZeroGPTDetector, CopyleaksDetector)

dets = [OriginalityDetector(), WinstonDetector(), GPTZeroDetector(), SaplingDetector(), ZeroGPTDetector(), CopyleaksDetector()]
out = {}
for d in dets:
    try:
        out[d.name] = {"available": d.available(), "tier": d.tier}
    except Exception as e:
        out[d.name] = {"error": f"{type(e).__name__}: {str(e)[:60]}"}
# In this env, no keys -> all unavailable (or key-gated)
print(json.dumps(out, indent=1))
