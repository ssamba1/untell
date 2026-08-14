"""humanness edge invariants: NaN/None handling, boundary bands, consistency with components."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.humanness import humanness, undetermined_reason

out = {}
# 1. Empty / too-short: must abstain, not return a confident number
for name, t in [("empty", ""), ("one_word", "Hello"), ("four_words", "The quick brown fox")]:
    h = humanness(t)
    reason = undetermined_reason(t)
    out[name] = {"score": h, "reason": reason}

# 2. Real text: score in [0,100]
good = "The team ran the experiment and recorded the results. They published the findings in the spring. The data was clear and the conclusion followed naturally."
h = humanness(good)
out["real_text_in_range"] = 0 <= h <= 100
out["real_score"] = h

# 3. German: abstains (undetermined) rather than scoring "human"
german = "Der Dienst läuft hinter einem Lastverteiler, und die Zustandsprüfung muss innerhalb von zwei Sekunden antworten."
out["german_reason"] = undetermined_reason(german)
out["german_score"] = humanness(german)
print(json.dumps(out, indent=1))
