"""_common_ratio + _MIN_WORDS_FOR_SIGNAL boundary: 5 words must be scoreable, 4 must abstain."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.detectors.perplexity_burstiness import _common_ratio, lite_score

out = {}
for name, t in {
    "1w_the": "the",
    "4w": "the of and for",
    "5w_common": "the of and for with",
    "5w_rare": "xylophone quagmire zephyr onyx fjord",
    "degenerate_a": "a a a a a",
}.items():
    out[name] = {"ratio": round(_common_ratio(t), 3), "score": lite_score(t)}
print(json.dumps(out, indent=1))
