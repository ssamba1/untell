"""surgical: substitutions respect case (UPPER/Title/lower), never break acronyms."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.surgical import SurgicalRewriter

rw = SurgicalRewriter(max_subs=12)
out = {}
# uppercase AI vocab
r = rw.rewrite("The system UTILIZES robust methods for the team.", {"max": 0.9}, 0.3)
out["upper"] = r
# title case
r2 = rw.rewrite("The System Utilizes Robust Methods for Every Team.", {"max": 0.9}, 0.3)
out["title"] = r2
# acronym preserved (UN is not a vocab word)
r3 = rw.rewrite("The UN delegates met to discuss the matter.", {"max": 0.9}, 0.3)
out["acronym_kept"] = "UN" in r3
print(json.dumps(out, indent=1))
