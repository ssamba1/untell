"""NOVEL probe: count_hidden vs scrub_hidden invariant on ALL carriers.

The documented invariant: count_hidden(t) == len(t) - len(scrub_hidden(t))
holds for DELETING scrubs. Space-normalizing carriers (NBSP etc) are
length-preserving so the invariant deliberately doesn't apply — verify the
boundary: deletion-carriers must satisfy it exactly, space-carriers must
satisfy count>0 and normalization (not deletion).
"""
import sys
from pathlib import Path
for p in Path(__file__).resolve().parents:
    if (p / "untell" / "__init__.py").exists():
        sys.path.insert(0, str(p)); break

from untell.attacks.unicode_tricks import count_hidden, scrub_hidden

# (name, text with one carrier)
DELETE_CARRIERS = {
    "ZWSP": "a\u200bb",
    "BOM": "a\ufeffb",
    "word_joiner": "a\u2060b",
    "hair": "a\u200ab",
    "figure": "a\u2007b",
    "en": "a\u2002b",
    "em": "a\u2003b",
    "invisible_times": "a\u2062b",
    "zwnj": "a\u200cb",
    "func_app": "a\u2061b",
}
SPACE_CARRIERS = {
    "nbsp": "a\u00a0b",
    "narrow_nbsp": "a\u202fb",
}

fails = []
print("deletion carriers (invariant: count == len - len(scrub)):")
for name, t in DELETE_CARRIERS.items():
    c = count_hidden(t)
    s = scrub_hidden(t)
    ok = c == len(t) - len(s) and c == 1
    print(f"  {name:16} count={c} invariant={ok}")
    if not ok: fails.append((name, "invariant"))

print("space carriers (invariant: count==1 and scrub normalizes to space):")
for name, t in SPACE_CARRIERS.items():
    c = count_hidden(t)
    s = scrub_hidden(t)
    normalized = s == t.replace("\u00a0", " ").replace("\u202f", " ")
    print(f"  {name:16} count={c} normalized={normalized}")
    if c != 1 or not normalized: fails.append((name, "space"))

print(f"\n{'ALL INVARIANTS HOLD' if not fails else f'{len(fails)} FAIL: {fails}'}")
