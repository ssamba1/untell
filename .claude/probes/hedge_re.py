import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.structural import _HEDGE_RE

out = {}
out["could_potentially"] = bool(_HEDGE_RE.search("This could potentially work."))
out["may_eventually"] = bool(_HEDGE_RE.search("It may eventually arrive."))
out["might_possibly"] = bool(_HEDGE_RE.search("They might possibly agree."))
out["would_arguably"] = bool(_HEDGE_RE.search("It would arguably be better."))
out["can_likely"] = bool(_HEDGE_RE.search("We can likely finish."))
out["case_insensitive"] = bool(_HEDGE_RE.search("This COULD POTENTIALLY work."))
out["no_modal"] = not bool(_HEDGE_RE.search("The system reads the file."))
print(json.dumps(out, indent=1))
