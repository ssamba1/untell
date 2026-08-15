import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.text_split import aligned_chunks

out = {}
a = " ".join(f"source{i}" for i in range(300))
b = " ".join(f"target{i}" for i in range(300))
chunks = aligned_chunks(a, b)
out["n_chunks"] = len(chunks)
out["all_pairs"] = all(isinstance(c, tuple) and len(c) == 2 for c in chunks)
out["coverage"] = sum(len(c[0].split()) for c in chunks)
# short pair -> 1 chunk
out["short_single"] = len(aligned_chunks("short text here", "short text here")) == 1
# empty
out["empty"] = aligned_chunks("", "")
print(json.dumps(out, indent=1))
