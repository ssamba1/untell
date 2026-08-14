"""similarity invariants: symmetry, identity, empty, meaning-change detection."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.quality import similarity, method

out = {"method": method()}
a = "The intervention halved mortality in the trial group over six months."
b = "The treatment reduced deaths by half during the six-month study."
c = "Cats are pleasant animals that enjoy sleeping in warm places."
same = "The intervention halved mortality in the trial group over six months."

out["identity"] = round(similarity(same, same), 4)
out["symmetry"] = abs(similarity(a, b) - similarity(b, a)) < 1e-9
out["empty_empty"] = similarity("", "  ")
out["empty_nonempty"] = similarity("", "text here")
out["paraphrase"] = round(similarity(a, b), 4)
out["meaning_change"] = round(similarity(a, c), 4)
out["change_lt_para"] = similarity(a, c) < similarity(a, b)
print(json.dumps(out, indent=1))
