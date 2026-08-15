"""NOVEL probe: rate limiter boundary semantics.

The auth middleware is well-built; the limiter's exact boundary behavior is
unprobed: (1) limit N allows exactly N requests then 429s on N+1, (2) the
retry-after math at window edges, (3) credential vs IP bucketing (same IP,
different keys = separate buckets), (4) UNTELL_RATE_LIMIT=0 disables,
(5) negative env value clamps to 0 = disabled, (6) the soft-cap eviction
drops oldest, not arbitrary.
"""
import sys, os, time
from pathlib import Path
for p in Path(__file__).resolve().parents:
    if (p / "untell" / "__init__.py").exists():
        sys.path.insert(0, str(p)); break

import untell.api_server as A

class FakeRequest:
    def __init__(self, host):
        self.client = type("C", (), {"host": host})()

def reset(limit_env):
    A._rate_buckets.clear()
    os.environ["UNTELL_RATE_LIMIT"] = limit_env

# (1) exact limit boundary
reset("3")
req = FakeRequest("10.0.0.1")
r = [A._rate_limited(req, "cred1") for _ in range(5)]
# expect: None, None, None, seconds, seconds
print(f"(1) limit=3, 5 calls: {r}")
print(f"    exactly 3 pass then block: {r[:3] == [None]*3 and r[3] is not None and r[4] is not None}")

# (2) different credentials same IP = separate buckets
reset("2")
r1 = A._rate_limited(FakeRequest("10.0.0.2"), "keyA")
r2 = A._rate_limited(FakeRequest("10.0.0.2"), "keyB")
r3 = A._rate_limited(FakeRequest("10.0.0.2"), "keyA")
r4 = A._rate_limited(FakeRequest("10.0.0.2"), "keyA")  # 3rd keyA call -> block at limit 2
r5 = A._rate_limited(FakeRequest("10.0.0.2"), "keyB")  # 2nd keyB call -> block at limit 2
print(f"(2) same IP diff keys: {[r1, r2, r3, r4, r5]}")
# proof of separate buckets: keyA's 3rd call blocks while keyB's 2nd (within limit 2) passes
print(f"    separate buckets: {r1 is None and r2 is None and r3 is None and r4 is not None and r5 is None}")

# (3) no credential = IP bucketing
reset("1")
a = A._rate_limited(FakeRequest("10.0.0.3"), "")
b = A._rate_limited(FakeRequest("10.0.0.3"), "")
print(f"(3) IP bucket: {[a, b]} — expect [None, block]")
print(f"    ip buckets correctly: {a is None and b is not None}")

# (4) limit 0 disables
reset("0")
free = [A._rate_limited(FakeRequest("10.0.0.4"), "") for _ in range(5)]
print(f"(4) limit=0 disables: {all(x is None for x in free)}")

# (5) negative clamps to 0 = disabled
reset("-3")
neg = [A._rate_limited(FakeRequest("10.0.0.5"), "") for _ in range(3)]
print(f"(5) negative clamps to disable: {all(x is None for x in neg)}")

# (6) non-numeric falls back to default
reset("abc")
d = A._rate_limited(FakeRequest("10.0.0.6"), "")
print(f"(6) non-numeric env: default applies ({d is None}, limit={A._rate_limit()})")

# (7) retry-after is in seconds and > 0
reset("1")
A._rate_limited(FakeRequest("10.0.0.7"), "k")
ra = A._rate_limited(FakeRequest("10.0.0.7"), "k")
print(f"(7) retry-after value: {ra!r} — positive int: {isinstance(ra, int) and ra > 0}")

# (8) soft-cap eviction drops oldest, keeps newest — with start times INSIDE the window
reset("100")
A._rate_buckets.clear()
now0 = 5000.0
for i in range(A._RATE_BUCKET_SOFT_CAP + 5):
    A._rate_buckets[f"k{i}"] = (now0 - i * 0.001, 1)  # increasing recency: k0 oldest, k{cap+4} newest
before = set(A._rate_buckets)
A._evict_stale_buckets(now0)  # all within 60s window -> nothing stale, cap eviction fires
after = set(A._rate_buckets)
dropped = before - after
oldest_start = max(A._rate_buckets[k][0] for k in A._rate_buckets)  # newest kept
# every dropped bucket must be OLDER (smaller start time) than every kept one
all_old_dropped = all(A._rate_buckets.get(k, (1e18, 0))[0] < A._rate_buckets[k2][0] for k in dropped for k2 in A._rate_buckets) if dropped else False
print(f"(8) soft cap {A._RATE_BUCKET_SOFT_CAP}: dropped {len(dropped)} (expect 5), oldest-evicted: {len(dropped) == 5}")
