import untell.rewriter.structural as S
for name, pat, probes in [
    ("_TRANSITIONS_RE", S._TRANSITIONS_RE, ["Moreover, the result held.", "Furthermore, we found.", "Additionally, it works.", "In conclusion, stop.", "Overall, the data says yes."]),
    ("_PARTICIPIAL_RE", S._PARTICIPIAL_RE, [", underscoring the importance", ", highlighting the gap", ", showcasing the result", ", emphasizing the point", ", reflecting the trend"]),
    ("_HEDGE_RE", S._HEDGE_RE, ["could potentially", "may possibly", "might arguably", "would likely", "can eventually"]),
]:
    hits = [p for p in probes if pat.search(p)]
    print(f"{name}: {len(hits)}/{len(probes)}  hits={hits}")
