"""NOVEL probe: intensity effect on WHICH edits (content) vs count.

Count is flat (5-6). Does the actual rewritten TEXT differ by intensity?
If outputs are near-identical, the knob adds no diversity and the
_intensity_sweep's claim of 'exploring genuinely different rewrites' is false.
"""
import sys
from pathlib import Path
for p in Path(__file__).resolve().parents:
    if (p / "untell" / "__init__.py").exists():
        sys.path.insert(0, str(p)); break

import untell.rewriter.structural as structural
import untell.scripts.score as S

TEXT = ("The results demonstrate significant improvements across all metrics. "
        "Moreover, the data indicate a clear trend toward enhanced performance. "
        "Furthermore, leveraging robust methodologies optimizes crucial outcomes. "
        "Additionally, the findings suggest that further investigation is warranted "
        "and the implications for practice are substantial.")

sr = S.score_text(TEXT, tier='lite')

outputs = {}
for intensity in (0.2, 0.5, 0.9):
    rw = structural.StructuralRewriter()
    outputs[intensity] = rw.rewrite(TEXT, sr, threshold=0.3, intensity=intensity)

# Pairwise content overlap
for a in (0.2, 0.5, 0.9):
    for b in (0.2, 0.5, 0.9):
        if a < b:
            same = outputs[a] == outputs[b]
            print(f"intensity {a} vs {b}: outputs identical = {same}")

print(f"\n0.2: {outputs[0.2][:80]}...")
print(f"0.9: {outputs[0.9][:80]}...")
