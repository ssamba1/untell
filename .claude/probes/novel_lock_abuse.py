"""NOVEL probe: modified-after-lock restore correctness.

The torture probe showed restore() doesn't raise on modified text. Does it restore
correctly, silently corrupt, or leave the sentinel? The lock must be tamper-evident
enough that an edit between lock and restore either restores faithfully or leaves
the sentinel visible (better than silently wrong).
"""
import sys
from pathlib import Path
for p in Path(__file__).resolve().parents:
    if (p / "untell" / "__init__.py").exists():
        sys.path.insert(0, str(p)); break

from untell.scripts.preserve import lock, restore

t = "Contact me at john@example.com today, or call +1-555-123-4567."
m, mp = lock(t)
print(f"locked:  {m!r}")

# Edit inside a locked span
edited_inside = m.replace("today", "tomorrow")
r1 = restore(edited_inside, mp)
print(f"edit inside span:  {r1!r}")
print(f"  -> email intact: {'john@example.com' in r1}, phone intact: {'+1-555-123-4567' in r1}")
print(f"  -> sentinel left behind: {'HZ' in r1 or 'LOCKED' in r1}")

# Edit the locked content itself (replace the email in locked form)
edited_email = m.replace("john@example.com", "other@example.com") if "john@example.com" in m else m.replace("john@example", "other@example")
r2 = restore(edited_email, mp)
print(f"edit locked content: {r2!r}")
print(f"  -> restored email: {'john@example.com' in r2}")

# Delete part of the lock
import re
deleted = re.sub(r"HZ\d+", "", m)
r3 = restore(deleted, mp)
print(f"sentinel deleted:   {r3!r} (len {len(r3)})")
