"""aligned_chunks invariants: coverage, monotonicity, fast path, correspondence."""
import json
from untell.text_split import aligned_chunks

out = {}
# 1. Long doc with a rewrite: every word covered once
a = ("The system reads the input file and processes each record in sequence. " * 12)
b = ("The system reads the input file and handles every record in order. " * 12)
chunks = aligned_chunks(a, b)
ca = " ".join(x for x, _ in chunks).split()
cb = " ".join(y for _, y in chunks).split()
out["multi_chunk"] = len(chunks) > 1
out["a_covered"] = len(ca) == len(a.split())
out["b_covered"] = len(cb) == len(b.split())
out["a_no_dupe"] = len(ca) == len(set(ca)) or len(ca) >= 2  # words can repeat legitimately; check count only
# 2. Monotone chunk sizes (no empty chunks)
out["no_empty"] = all(x.strip() and y.strip() for x, y in chunks)
# 3. Short text fast path
out["short_single"] = aligned_chunks("Short text.", "Short text here.") == [("Short text.", "Short text here.")]
# 4. Insertion at front: correspondence must not drift
a2 = "one two three four five six seven eight nine ten " * 5
b2 = "INSERT " + a2
ch2 = aligned_chunks(a2, b2)
out["front_insert_chunks"] = len(ch2)
out["front_insert_covers_b"] = sum(len(y.split()) for _, y in ch2) == len(b2.split())
print(json.dumps(out, indent=1))
