import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.tells import _duplicate_sentence_starts

out = {}
# 4 sentences all starting 'The' -> fires
t = ("The system reads the file. The parser splits it. The loader writes it. The checker validates it. "
     "Each component works in sequence with the others.")
out["four_the"] = _duplicate_sentence_starts(t)
# 2 sentences starting 'The' -> below 40% (2 of ~4)
t2 = ("The system reads the file. Then the parser splits it. The loader writes it. After that the checker runs. "
      "Each component works in sequence with the others.")
out["two_the"] = _duplicate_sentence_starts(t2)
# varied starts -> 0
t3 = ("The system reads the file. Then the parser splits it. Next the loader writes it. After that the checker runs. "
      "Each component works in sequence with the others.")
out["varied"] = _duplicate_sentence_starts(t3)
print(json.dumps(out, indent=1))
