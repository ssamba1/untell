"""NOVEL probe: tell removal vs iterations; score movement correlation.

Does more iteration remove more tells? Does tell removal correlate with
score drop (are they the same axis or different)? Measures iters 1..5.
"""
import sys
from pathlib import Path
for p in Path(__file__).resolve().parents:
    if (p / "untell" / "__init__.py").exists():
        sys.path.insert(0, str(p)); break

from untell.scripts.tells import score_tells
from untell.scripts.run import untell_text

TEXT = (
    "In conclusion, it is important to note that the results demonstrate significant "
    "improvements across all metrics. Moreover, the data indicate a clear trend toward "
    "enhanced performance. Furthermore, leveraging robust methodologies optimizes crucial "
    "outcomes, and the findings suggest that further investigation is warranted. "
    "Ultimately, this research underscores the pivotal role of innovation in driving "
    "sustainable growth, and notably, the implications for practice are substantial."
)

def total_tells(res):
    return res.get("total") or sum(v for k, v in res.items() if isinstance(v, int) and not k.startswith("_"))

pre_t = total_tells(score_tells(TEXT))
print(f"iters | tells removed | pre_max -> post_max | changed")
for iters in (1, 2, 3, 5):
    r = untell_text(TEXT, tier='lite', max_iters=iters, progress=False, seed=11)
    post_t = total_tells(score_tells(r['final']))
    pre_max = r.get('pre', {}).get('max')
    post_max = r.get('post', {}).get('max')
    print(f"  {iters}   |     {pre_t - post_t:3d}         | {pre_max} -> {post_max}    | {r['final'] != TEXT}")
