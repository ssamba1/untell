"""NOVEL probe: does intensity actually change rewrite output?

The config exposes intensity (0-1). Composite's _intensity_sweep varies it
around the base. But does a HIGHER intensity produce MORE edits? If the knob
is inert, the sweep is theater. Measure edit counts at intensity 0.2/0.5/0.9
on the same text with the same seed.
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

for intensity in (0.2, 0.5, 0.9):
    rw = structural.StructuralRewriter()
    out = rw.rewrite(TEXT, sr, threshold=0.3, intensity=intensity)
    # count changed words via difflib
    import difflib
    a, b = TEXT.split(), out.split()
    sm = difflib.SequenceMatcher(None, a, b)
    edits = sum(1 for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != 'equal')
    changed = out != TEXT
    print(f"intensity={intensity}: changed={changed} opcodes={edits}")
