"""numerals: missing numbers flagged; spelled/digit canonical equivalence; kept invariant."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.numerals import missing_numbers, numbers_kept

out = {}
# Dropping a number flagged
src = "The study followed 120 patients over 6 months."
cand = "The study followed patients over several months."
out["missing_flagged"] = missing_numbers(src, cand)
out["kept_false"] = not numbers_kept(src, cand)
# Same numbers -> kept
out["same_kept"] = numbers_kept(src, src)
# spelled vs digit equivalence
src2 = "There were three options and twelve teams."
cand2 = "There were 3 options and 12 teams."
out["spelled_digit_equiv"] = numbers_kept(src2, cand2)
# decimal tolerance
src3 = "The ratio was 2.50."
cand3 = "The ratio was 2.5."
out["decimal_fold"] = numbers_kept(src3, cand3)
print(json.dumps(out, indent=1))
