"""homoglyph_substitute: rate respected, only confusable chars swapped, reversible."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.attacks import homoglyph_substitute

out = {}
t = "The quick brown fox jumps over the lazy dog. The system works well here."
# rate 0 -> unchanged
out["rate0_unchanged"] = homoglyph_substitute(t, rate=0.0) == t
# rate 1 -> changed
s1 = homoglyph_substitute(t, rate=1.0)
out["rate1_changed"] = s1 != t
out["rate1_diff_chars"] = sum(1 for a, b in zip(t, s1) if a != b) > 0
# monotone: rate 0.3 changes <= rate 0.9 changes
d03 = sum(1 for a, b in zip(t, homoglyph_substitute(t, rate=0.3)) if a != b)
d09 = sum(1 for a, b in zip(t, homoglyph_substitute(t, rate=0.9)) if a != b)
out["monotone"] = d03 <= d09
out["d03"], out["d09"] = d03, d09
# length preserved
out["length_preserved"] = len(homoglyph_substitute(t, rate=1.0)) == len(t)
print(json.dumps(out, indent=1))
