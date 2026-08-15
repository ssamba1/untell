"""Debug span-level behavior for surprising cases."""
import sys
sys.path.insert(0, "C:/Users/Admin/Humanize")
from untell.scripts.preserve import _collect_labeled_spans, _merge, lock

CASES = [
    ("J2", "Call 020 7946 0958 today. It is urgent."),
    ("L", "Open 9:30\u201310:30 AM daily. Then close."),
    ("L2", "From 9:30-10:30 we work. Then rest."),
    ("T", "Lunch is at 12:30 p.m. Then work."),
    ("J", "Call +44 20 7946 0958. Then leave."),
]
for label, text in CASES:
    print(f"=== {label}: {text!r}")
    spans = _collect_labeled_spans(text)
    for lab, s, e in sorted(spans, key=lambda x: (x[1], x[2])):
        print(f"  {lab:10s} [{s:3d},{e:3d}) {text[s:e]!r}")
    print(f"  merged: {[(s, e, text[s:e]) for s, e in _merge([(s, e) for _l, s, e in spans])]}")
