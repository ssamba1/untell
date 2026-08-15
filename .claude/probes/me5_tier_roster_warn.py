"""me5 follow-up: print FULL warning chains for bogus/None tiers and the roster note."""
import json
import os

os.environ["UNTELL_LITE_NO_TORCH"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from untell.scripts.score import score_text  # noqa: E402

TEXT = (
    "The rapid advancement of artificial intelligence has transformed the way we approach "
    "complex problems across numerous domains. This technological revolution presents both "
    "unprecedented opportunities and significant challenges that require careful "
    "consideration by researchers and practitioners alike."
)

r = score_text(TEXT, tier="bogus")
print("BOGUS_TIER:", r.get("tier"), "| req:", r.get("tier_requested"))
print("BOGUS_WARNING:", json.dumps(r.get("warning")))

r = score_text(TEXT, tier=None)
print("NONE_TIER:", r.get("tier"), "| req:", r.get("tier_requested"))
print("NONE_WARNING:", json.dumps(r.get("warning")))

os.environ["UNTELL_DISABLE_MAGE"] = "1"
r = score_text(TEXT, tier="full")
print("MAGE_OFF_TIER:", r.get("tier"), "| req:", r.get("tier_requested"))
print("MAGE_OFF_WARNING:", json.dumps(r.get("warning")))
