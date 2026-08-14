"""progress_iteration: format invariants — emits only when score is not None, tier labeled."""
import json
from untell.rich_output import progress_iteration

out = {}
# score present -> string with tier and score
s = progress_iteration(2, 5, "lite", 0.42)
out["with_score"] = s is not None and "lite" in s and "0.42" in s
# score None -> None (silent)
out["none_score"] = progress_iteration(2, 5, "lite", None) is None
# first iteration
s2 = progress_iteration(1, 5, "full", 0.9)
out["first_iter"] = s2 is not None
print(json.dumps(out, indent=1))
