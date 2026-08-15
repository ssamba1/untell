import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.text_split import aligned_chunks, CHUNK_WORDS

out = {}
# the defect case: disjoint 300-word pair
a = " ".join(f"alpha{i}" for i in range(300))
b = " ".join(f"beta{i}" for i in range(300))
chunks = aligned_chunks(a, b)
out["n_chunks"] = len(chunks)
out["a_covered"] = sum(len(c[0].split()) for c in chunks)
out["b_covered"] = sum(len(c[1].split()) for c in chunks)
out["all_under_budget"] = all(len(c[0].split()) <= CHUNK_WORDS and len(c[1].split()) <= CHUNK_WORDS for c in chunks)
# realistic pair still aligns
base = "The system reads the incoming file and processes every record in order. " * 20
r = base.replace("processes", "handles")
c2 = aligned_chunks(base, r)
out["realistic_n"] = len(c2)
out["realistic_symmetric"] = all(len(x.split()) == len(y.split()) for x, y in c2)
# short pair unchanged
out["short_single"] = len(aligned_chunks("short text here", "short text here")) == 1
print(json.dumps(out, indent=1))
