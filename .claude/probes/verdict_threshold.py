"""_verdict_threshold: raises cut ONLY for stdlib mode, never for model-backed."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.score import _verdict_threshold

out = {}
# stdlib mode -> 0.45
out["stdlib"] = _verdict_threshold(0.3, {"perplexity_burstiness": 0.4}, {"perplexity_burstiness": "stdlib"})
# gpt2 mode -> 0.3
out["gpt2"] = _verdict_threshold(0.3, {"perplexity_burstiness": 0.4}, {"perplexity_burstiness": "gpt2"})
# mixed modes -> ?
out["mixed"] = _verdict_threshold(0.3, {"a": 0.4, "b": 0.5}, {"a": "stdlib", "b": "gpt2"})
# no modes -> threshold unchanged
out["no_modes"] = _verdict_threshold(0.3, {"a": 0.4}, {})
print(json.dumps(out, indent=1))
