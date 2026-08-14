import untell.rewriter.structural as S
probes = [
    "The method converges, underscoring the importance of the result.",
    "The data was sparse, highlighting the gap in the literature.",
    "The results are clear, showcasing the value of the approach.",
    "We proceeded, emphasizing the need for caution.",
    "The study ends, reflecting the trend in the field.",
]
hits = [p for p in probes if S._PARTICIPIAL_RE.search(p)]
print(f"_PARTICIPIAL_RE: {len(hits)}/{len(probes)}")
for p in probes:
    print("  ", bool(S._PARTICIPIAL_RE.search(p)), repr(p[:60]))
