import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.tells import _burstiness_cv

out = {}
# 1 sentence -> None (undefined)
out["one_sent"] = _burstiness_cv("Only one sentence here.")
# uniform lengths -> CV 0.0
out["uniform"] = _burstiness_cv("The cat sat on the mat. The dog lay on the rug. The bird flew in the sky.")
# varied lengths -> CV > 0
out["varied"] = _burstiness_cv("The cat sat on the mat. The extraordinarily patient dog lay quietly on the comfortable rug. Go.")
# all same single word
out["all_short"] = _burstiness_cv("Go. Now. Stop.")
print(json.dumps(out, indent=1))
