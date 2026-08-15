import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.structural import _parenthesise_asides

out = {}
# comma-bounded aside -> parenthetical
t = "The system, which reads files, processes them in order."
out["aside_paren"] = "(" in _parenthesise_asides(t)
# serial-list aside NOT parenthesized (the documented dangling-comma fix)
t2 = "Melanin, which gives your skin, hair, and eyes their color, and another pigment."
out["serial_kept"] = _parenthesise_asides(t2).count("(") == 0
# no aside -> unchanged
t3 = "The system reads files and processes them."
out["plain_unchanged"] = _parenthesise_asides(t3) == t3
print(json.dumps(out, indent=1))
