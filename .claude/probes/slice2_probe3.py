"""Test range pattern and meridiem second-dot absorption directly."""
import re, sys
sys.path.insert(0, "C:/Users/Admin/Humanize")
from untell.scripts.preserve import _PATTERNS, lock

num_pat = [p for l, p in _PATTERNS if l == "number"][0]

print("range-only test:", re.compile(r"\b\d+\s*[-–—]\s*\d+\b").findall("9:30-10:30 we work"))
print("range-only en:", re.compile(r"\b\d+\s*[-–—]\s*\d+\b").findall("9:30\u201310:30 AM daily"))
m = re.compile(r"\b\d+\s*[-–—]\s*\d+\b").search("From 9:30-10:30 we work")
print("range search:", m.group(0) if m else None, m.span() if m else None)

# What matched at position 7 in '9:30-10:30'? Try each number alternative manually.
text = "From 9:30-10:30 we work. Then rest."
for label, pat in _PATTERNS:
    for mm in pat.finditer(text):
        print(f"  {label:12s} [{mm.start():3d},{mm.end():3d}) {text[mm.start():mm.end()]!r}")

print()
# Meridiem sentence-end behavior
m2, _ = lock("Lunch is at 12:30 p.m. Then work.")
print("meridiem sentence-end:", repr(m2))
m3, _ = lock("We met at 4:15 p.m. and left.")
print("meridiem mid-sentence:", repr(m3))
m4, _ = lock("We met at 4:15 p.m. GMT today.")
print("meridiem + capital abbr:", repr(m4))
