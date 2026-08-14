import untell.rewriter.structural as S
# Dig each suspect with several candidate positives
for name, pat in [("_TRANSITIONS_RE", S._TRANSITIONS_RE), ("_PARTICIPIAL_RE", S._PARTICIPIAL_RE), ("_HEDGE_RE", S._HEDGE_RE), ("_LEADING_SUBORDINATOR_RE", S._LEADING_SUBORDINATOR_RE)]:
    print(f"== {name} ==")
    print("   pattern:", pat.pattern[:130])
    for probe in ["not only X but also Y", "while the sun shines, we play", "although it rained", "because the data was sparse", "arguably", "perhaps", "seemingly", "Running fast, she won", "Having said that, the plan holds"]:
        if pat.search(probe):
            print(f"   HIT: {probe!r}")
