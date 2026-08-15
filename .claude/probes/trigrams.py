import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.tells import _repeated_trigrams

out = {}
# repeated trigram above 5% -> count returned
t = "The quick brown fox jumps over the lazy dog. The quick brown fox returns to the garden."
out["repeat_count"] = _repeated_trigrams(t)
# no repetition -> 0
t2 = "The quick brown fox jumps over the lazy dog. A slow gray cat sleeps on the warm windowsill."
out["no_repeat"] = _repeated_trigrams(t2)
# heavy repetition
t3 = ("In conclusion the results show improvement. In conclusion the results show improvement. "
      "In conclusion the results show improvement. In conclusion the results show improvement. "
      "In conclusion the results show improvement. In conclusion the results show improvement.")
out["heavy_repeat"] = _repeated_trigrams(t3)
print(json.dumps(out, indent=1))
