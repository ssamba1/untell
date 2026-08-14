"""Sweep: does ANY (doc, seed, rewriter) output differ across PYTHONHASHSEED?"""
import json, os, hashlib, sys
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import untell_text

DOCS = [
    "Moreover, the framework leverages a robust approach to delivery at scale across the whole programme. Furthermore, it is important to note that this underscores the pivotal integration for every team.",
    "The system utilizes a comprehensive methodology throughout the year. Additionally, the platform empowers users to streamline their daily workflows considerably. In conclusion, organizations must harness these seamless solutions today.",
    "Research indicates that the proposed method achieves superior performance on benchmark datasets. The experimental results demonstrate significant improvements over existing approaches. These findings suggest promising directions for future work.",
]
SEEDS = [0, 1, 7, 42, 99]
REWRITERS = ["structural", "surgical", "targeted", "composite"]
out = {}
for doc in DOCS:
    for seed in SEEDS:
        for rw in REWRITERS:
            r = untell_text(doc, tier="lite", max_iters=2, rewriter=rw, best_of=3, seed=seed)
            f = r.get("final") or ""
            out[(DOCS.index(doc), seed, rw)] = hashlib.sha256(f.encode()).hexdigest()[:12]
for k, v in sorted(out.items()):
    print(f"doc{k[0]} seed{k[1]:2d} {k[2]:10s} {v}")
