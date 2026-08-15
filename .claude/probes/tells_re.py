import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.tells import _META_CLOSER_RE, _ARTIFACT_RE, _INFLATED_COPULA_RE, _HEDGE_STACK_RE, _FALSE_RANGE_RE

out = {}
out["meta_closer"] = bool(_META_CLOSER_RE.search("I hope this helps! The fix works."))
out["meta_closer_case"] = bool(_META_CLOSER_RE.search("Let me know if you need more."))
out["artifact"] = bool(_ARTIFACT_RE.search("As an AI language model, I cannot help."))
out["artifact_citation"] = bool(_ARTIFACT_RE.search("see oai_citation:3 here"))
out["inflated_copula"] = bool(_INFLATED_COPULA_RE.search("The tool serves as a bridge."))
out["hedge_stack"] = bool(_HEDGE_STACK_RE.search("This could potentially work."))
out["false_range"] = bool(_FALSE_RANGE_RE.search("Whether you're a beginner or an expert, this works."))
out["false_range_headline"] = bool(_FALSE_RANGE_RE.search("from ancient civilizations to modern startups"))
print(json.dumps(out, indent=1))
