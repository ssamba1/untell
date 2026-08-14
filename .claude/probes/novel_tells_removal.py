"""NOVEL probe: does rewriting actually reduce tell counts?

The tool's core promise: rewriting removes AI tells. Measure tells before/after
untell_text on AI-flavored text with many tells, and per-category.
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

pre = score_tells(TEXT)
r = untell_text(TEXT, tier='lite', max_iters=3, progress=False, seed=11)
post_text = r['final']
post = score_tells(post_text)

pt, q = total_tells(pre), total_tells(post)
print(f"pre tells:  {pt}")
print(f"post tells: {q}")
print(f"tells removed: {pt - q} / {pt}")
print(f"text changed: {post_text != TEXT}")
