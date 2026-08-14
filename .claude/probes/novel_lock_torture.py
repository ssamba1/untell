"""NOVEL probe: lock/restore round-trip torture.

Test lock/restore under adversarial nesting: overlapping spans, adjacent spans,
sentinel collisions (user text that LOOKS like a sentinel), and restore on text
that was further modified after lock (the abuse case).
"""
import sys
from pathlib import Path
for p in Path(__file__).resolve().parents:
    if (p / "untell" / "__init__.py").exists():
        sys.path.insert(0, str(p)); break

from untell.scripts.preserve import lock, restore

fails = []

# 1. Adjacent spans
t1 = "A [1] B [2] C"
m1, mp1 = lock(t1)
r1 = restore(m1, mp1)
print(f"adjacent: {r1 == t1} ({t1!r} -> {r1!r})")
if r1 != t1: fails.append(("adjacent", t1, r1))

# 2. Text that already contains a sentinel-looking token
t2 = "The value is [LOCKED:42] and also [[HZ]"
m2, mp2 = lock(t2)
r2 = restore(m2, mp2)
print(f"sentinel-looking: {r2 == t2}")
if r2 != t2: fails.append(("sentinel-looking", t2, r2))

# 3. Restore on text modified AFTER lock (the abuse case)
t3 = "Contact me at john@example.com today"
m3, mp3 = lock(t3)
modified = m3.replace("today", "tomorrow")  # user edits the locked text
try:
    r3 = restore(modified, mp3)
    print(f"modified-after-lock: restore returned (len={len(r3)})")
except Exception as e:
    print(f"modified-after-lock: raised {type(e).__name__}: {e}")
    fails.append(("modified-after-lock", t3, str(e)))

# 4. Double lock (lock on already-locked text)
t4 = "URL: https://example.com/path"
m4a, mp4a = lock(t4)
m4b, mp4b = lock(m4a)
r4 = restore(restore(m4b, mp4b), mp4a)
print(f"double-lock: {r4 == t4}")
if r4 != t4: fails.append(("double-lock", t4, r4))

# 5. Empty text
t5 = ""
m5, mp5 = lock(t5)
r5 = restore(m5, mp5)
print(f"empty: {r5 == t5}")

# 6. Only-sentinel text
t6 = "no facts here"
m6, mp6 = lock(t6)
r6 = restore(m6, mp6)
print(f"no-facts: {r6 == t6}")

# 7. Very long text with many facts (100 emails)
t7 = " ".join(f"user{i}@example.com" for i in range(100))
m7, mp7 = lock(t7)
r7 = restore(m7, mp7)
print(f"100-facts: {r7 == t7}")
if r7 != t7: fails.append(("100-facts", t7[:50], r7[:50]))

print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAIL: {fails}'}")
