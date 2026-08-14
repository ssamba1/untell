"""Scoring cap + scrub/polish interaction: what happens past MAX_INPUT_CHARS, and does scrub run when rewriter declines?"""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import untell_text
from untell.scripts.score import MAX_INPUT_CHARS

out = {}
# 1. Text over the cap: does untell_text handle it without crash, and report truncation?
big = ("The system utilizes a comprehensive methodology throughout the year. " * 4000)
r = untell_text(big, tier="lite", max_iters=1, seed=1)
out["over_cap_no_crash"] = True
out["over_cap_chars"] = len(big)
out["cap"] = MAX_INPUT_CHARS
out["final_len"] = len(r.get("final") or "")
out["final_is_input"] = (r.get("final") == big)

# 2. scrub runs even when rewriter declines (below-threshold text with hidden chars)
dirty = "Clean human sentence here. " * 8 + "\u200b" * 3 + " More text after."
r2 = untell_text(dirty, tier="lite", max_iters=2, seed=1)
out["scrub_removed_zwsp"] = ("\u200b" not in (r2.get("final") or ""))

# 3. exactly-at-cap boundary
at_cap = "x " * (MAX_INPUT_CHARS // 2)
r3 = untell_text(at_cap, tier="lite", max_iters=1, seed=1)
out["at_cap_no_crash"] = True
print(json.dumps(out, indent=1))
