import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.attacks.word_importance import _match_case, _SYN, synonyms

out = {}
# PROBE 1: case matching (invariant: replacement carries original's capitalisation)
out["title"] = _match_case("Robust", "solid")   # expect 'Solid' (title case preserved)
out["upper"] = _match_case("ROBUST", "solid")   # expect 'SOLID'
out["lower"] = _match_case("robust", "solid")   # expect 'solid'
out["mixed"] = _match_case("rObUsT", "solid")   # expect lowercase fallback 'solid' (reasonable)

# PROBE 2: synonym map self-reference + count
entries = len(_SYN)
self_refs = [(k, v) for k, v in _SYN.items() if k in v]
lev = _SYN.get("leverage")
uti = _SYN.get("utilize")
out["syn_count"] = entries
out["self_refs"] = self_refs
out["leverage"] = lev
out["leverage_self_ref"] = "leverage" in (lev or [])
out["utilize"] = uti
out["utilize_self_ref"] = "utilize" in (uti or [])
out["leverage_via_synonyms"] = synonyms("leverage")
out["utilize_via_synonyms"] = synonyms("utilize")
print(json.dumps(out, indent=1))
