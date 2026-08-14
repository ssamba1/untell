import json
from untell.rich_output import _diff_words

out = {}
# difflib-based: insertion at front marks only the inserted word
a = "the quick brown fox jumps over the lazy dog"
b = "suddenly the quick brown fox jumps over the lazy dog"
d = _diff_words(a, b)
out["front_insert_minimal"] = d.count("green") <= 2
# deletion shows struck-through
c = "the quick brown fox jumps over the lazy dog"
d2 = _diff_words(c, "the quick fox jumps over the dog")
out["delete_shows_strike"] = "strike" in d2
# identical
out["identical_plain"] = _diff_words(a, a) == a + " "
# plain fallback when no rich
print(json.dumps(out, indent=1))
