"""NOVEL probe: instrument the composite selector's cand<best firing rate.

Nobody has measured how often the (max,mean) selector actually fires vs how many
draws tie. This probes: for N docs, how many candidate draws beat the baseline on
the selection key, how many tie on max but improve on mean (the key's raison
d'etre), and how many lose.
"""
import sys
from pathlib import Path
for p in Path(__file__).resolve().parents:
    if (p / "untell" / "__init__.py").exists():
        sys.path.insert(0, str(p)); break

import untell.rewriter.composite as C
import untell.rewriter.base as B
import untell.scripts.score as S

# Instrument selection_key to log comparisons
orig_key = C._selection_key
stats = {"beats": 0, "ties_max_improves_mean": 0, "loses": 0, "total": 0, "exact_ties": 0}

def logged_key(result):
    return orig_key(result)

C._selection_key = logged_key

# Wrap the rewrite loop: count by monkeypatching score_text used inside composite
orig_score = S.score_text
firings = {"improve": 0, "no_improve": 0, "tie_mean_improve": 0, "calls": 0}

import types

# Easier: patch _selection_key to record outcomes relative to a running baseline
class Tracker:
    def __init__(self):
        self.base = None
        self.n = 0
        self.improved = 0
        self.tie_improved = 0
        self.worse = 0
        self.same = 0

tracker = Tracker()

def tracking_key(result):
    key = orig_key(result)  # (max, mean)
    tracker.n += 1
    if tracker.base is None:
        tracker.base = key
    else:
        bmax, bmean = tracker.base
        cmax, cmean = key
        if (cmax, cmean) < (bmax, bmean):
            tracker.improved += 1
            tracker.base = key
        elif cmax == bmax and cmean < bmean:
            tracker.tie_improved += 1
            tracker.base = key
        elif (cmax, cmean) == (bmax, bmean):
            tracker.same += 1
        else:
            tracker.worse += 1
    return key

C._selection_key = tracking_key

from untell.scripts.run import untell_text

TEXTS = [
    "The results demonstrate significant improvements across all metrics. Moreover, the data indicate a clear trend toward enhanced performance. Furthermore, leveraging robust methodologies optimizes crucial outcomes in every domain.",
    "Recent studies have explored the relationship between various factors. Nevertheless, additional research is needed to confirm these findings. Additionally, longitudinal designs would help establish causality.",
    "The methodology employs advanced techniques to address the research question. Nonetheless, several limitations must be acknowledged. Furthermore, future work should explore the robustness of these results.",
    "It is important to note that the findings highlight significant implications for practice. Ultimately, the evidence suggests a compelling trajectory for future investigation. However, the sample size remains a concern.",
    "This study contributes to the growing body of literature on this topic. Moreover, the results align with previous work in the field. Consequently, the implications for theory and practice are substantial.",
]

for i, t in enumerate(TEXTS):
    tracker.base = None
    r = untell_text(t, tier='lite', max_iters=2, progress=False, seed=100 + i)
    if i == 0:
        print(f"doc0 changed: {r['final'] != t}")

print(f"\nselection-key draws instrumented: {tracker.n}")
print(f"  improved (cand < best on (max,mean)): {tracker.improved}")
print(f"  tied max, improved mean:              {tracker.tie_improved}")
print(f"  exact tie:                            {tracker.same}")
print(f"  worse:                                {tracker.worse}")
