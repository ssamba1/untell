"""Profile the core humanize path (untell_text) on a realistic corpus."""
import cProfile
import io
import pstats
import sys
import time

sys.path.insert(0, r"C:/Users/Admin/Humanize")

from untell.detectors.base import load_detectors  # noqa: E402

# What actually loads here?
for tier in ("lite", "full"):
    try:
        ds = load_detectors(tier)
        print(f"tier={tier}: {[d.name for d in ds]}")
    except Exception as e:
        print(f"tier={tier}: ERROR {e}")

from untell.scripts.run import untell_text  # noqa: E402
from untell.rewriter import get_rewriter  # noqa: E402

# Build a realistic corpus: HC3 human + AI long/short, concatenated, ~19k words
with open(r"C:/Users/Admin/Humanize/.claude/corpora/hc3-human.txt", encoding="utf-8") as f:
    human = f.read()
with open(r"C:/Users/Admin/Humanize/.claude/corpora/hc3-long.txt", encoding="utf-8") as f:
    long = f.read()
with open(r"C:/Users/Admin/Humanize/.claude/corpora/hc3-short.txt", encoding="utf-8") as f:
    short = f.read()

corpus = "\n\n".join([human, long, short, long, short])
words = len(corpus.split())
print(f"corpus words: {words}, chars: {len(corpus)}")

rw = get_rewriter("composite")
print(f"rewriter: {rw.name}")

# Warmup + timing
t0 = time.perf_counter()
res = untell_text(corpus, tier="lite", max_iters=2, rewriter=rw, progress=False)
t1 = time.perf_counter()
print(f"untell_text wall: {t1 - t0:.2f}s, iterations={res.get('iterations')}, flagged={res.get('flagged')}")

# cProfile on a fresh call
pr = cProfile.Profile()
pr.enable()
res = untell_text(corpus, tier="lite", max_iters=2, rewriter=rw, progress=False)
pr.disable()
s = io.StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
ps.print_stats(40)
print(s.getvalue()[:8000])
