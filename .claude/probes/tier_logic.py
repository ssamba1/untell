"""tier ordering: _tier_at_most, _TIER_RANK, resolved_tier across all tiers."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.detectors.base import _tier_at_most, _TIER_RANK, resolved_tier, load_detectors
from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector
from untell.detectors.hc3_roberta import HC3RobertaDetector
from untell.detectors.mage import MageDetector

out = {}
# tier at most semantics
out["lite_at_lite"] = _tier_at_most("lite", "lite")
out["lite_at_full"] = _tier_at_most("lite", "full")  # lite allowed at full
out["full_at_lite"] = not _tier_at_most("full", "lite")  # full NOT allowed at lite
out["commercial_at_heavy"] = not _tier_at_most("commercial", "heavy")
out["heavy_at_commercial"] = _tier_at_most("heavy", "commercial")
# resolved tier of a mixed list
out["resolved_mixed"] = resolved_tier([PerplexityBurstinessDetector(), HC3RobertaDetector()])
out["resolved_lite_only"] = resolved_tier([PerplexityBurstinessDetector()])
out["resolved_empty"] = resolved_tier([])
print(json.dumps(out, indent=1))
