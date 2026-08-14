"""count_hidden vs scrub_hidden: count must equal removals; agreement on many classes."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.attacks import count_hidden, scrub_hidden

out = {}
cases = {
    "zwsp": "a\u200bb\u200bc",
    "bidi": "x\u202ey\u202cx",
    "tag": "m\uE000n\uE001o",
    "control": "a\x01b\x02c",
    "variation": "e\ufe0ef\ufe0f",
    "zwj": "g\u200dh",
    "mixed": "a\u200b\u200db\u200d\u200d\u200dc\u200b",
    "clean": "plain text here",
    "accents": "café naïve",
}
for name, t in cases.items():
    n = count_hidden(t)
    cleaned = scrub_hidden(t)
    removed = sum(1 for c in t if c not in cleaned)
    out[name] = {"count": n, "removed": removed, "agree": n == removed, "clean_zero": count_hidden(cleaned) == 0}
print(json.dumps(out, indent=1))
