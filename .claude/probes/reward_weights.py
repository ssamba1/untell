"""free_ensemble_score: renormalized weighted mean, no-detector refusal, RE WARD_FAST escape."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from training.reward import free_ensemble_score, _FREE_WEIGHTS

out = {}
# 1. Weighted mean < max (weights dilute the saturating detector)
import untell.scripts.score as S
orig_score_text = S.score_text
S.score_text = lambda t, tier="lite", **k: {"detectors": {"mage": 1.0, "hc3_roberta": 0.5, "perplexity_burstiness": 0.2},
                                             "max": 1.0}
try:
    s = free_ensemble_score("test", tier="lite")
    expected = (0.35*1.0 + 0.18*0.5 + 0.02*0.2) / (0.35+0.18+0.02)
    out["weighted_mean"] = round(s, 4)
    out["expected"] = round(expected, 4)
    out["matches"] = abs(s - expected) < 1e-6
    out["lt_max"] = s < 1.0
finally:
    S.score_text = orig_score_text
# 2. No detectors -> RuntimeError
S.score_text = lambda t, tier="lite", **k: {"detectors": {}, "max": 0.0, "warning": "none", "failed_detectors": []}
try:
    free_ensemble_score("test", tier="lite")
    out["no_detector_refuses"] = False
except RuntimeError as e:
    out["no_detector_refuses"] = True
    out["refusal_mentions_fast"] = "UNTELL_REWARD_FAST" in str(e)
finally:
    S.score_text = orig_score_text
print(json.dumps(out, indent=1))
