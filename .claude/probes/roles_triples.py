import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.roles import role_swap, available

out = {}
out["available"] = available()
# the documented prep-object evade case
a = "Organizations may benefit from these tools."
b = "These tools may benefit from organizations."
out["prep_swap_caught"] = role_swap(a, b) is True
# passive normalization keeps voice changes identical
c = "The proposal was rejected by the committee."
d = "The committee rejected the proposal."
out["passive_voice_ok"] = role_swap(c, d) in (False, None)
# genuine swap caught
e = "The company sued the regulator over the licence."
f = "The regulator sued the company over the licence."
out["direct_swap_caught"] = role_swap(e, f) is True
# identical text
out["identical_fine"] = role_swap(a, a) in (False, None)
print(json.dumps(out, indent=1))
