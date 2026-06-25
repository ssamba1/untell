"""Render benchmark results as a markdown table (+ optional JSON)."""

from __future__ import annotations


def _bypass_rate(results: list, threshold: float) -> float:
    if not results:
        return 0.0
    passed = sum(1 for r in results if r.post["max"] < threshold)
    return passed / len(results)


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _per_detector(results: list, threshold: float) -> dict[str, dict[str, float]]:
    """Per-detector mean pre/post P(AI) and **beat rate** (% of samples scored below threshold).

    The beat rate is the honest per-checker headline — e.g. how often we get RADAR (the hardest open,
    paraphrase-robust detector) under threshold, separately from the aggregate max.
    """
    names: list[str] = []
    for r in results:
        for k in r.pre.get("detectors", {}):
            if k not in names and "__error" not in k:
                names.append(k)
    out: dict[str, dict[str, float]] = {}
    for name in names:
        pre_vals = [r.pre["detectors"][name] for r in results if isinstance(r.pre["detectors"].get(name), (int, float))]
        post_vals = [r.post["detectors"][name] for r in results if isinstance(r.post["detectors"].get(name), (int, float))]
        beat = [1.0 if v < threshold else 0.0 for v in post_vals]
        out[name] = {"pre": _mean(pre_vals), "post": _mean(post_vals), "beat_rate": _mean(beat)}
    return out


def _hardest_detector(per_detector: dict[str, dict[str, float]]) -> str | None:
    """The detector hardest to beat = lowest beat rate (ties broken by highest mean post)."""
    if not per_detector:
        return None
    return min(per_detector, key=lambda d: (per_detector[d]["beat_rate"], -per_detector[d]["post"]))


def summarize(by_strategy: dict[str, list], threshold: float) -> dict:
    """Machine-readable summary (used by `render` and available for JSON output)."""
    strategies = {}
    for name, results in by_strategy.items():
        if not results:
            continue
        pd = _per_detector(results, threshold)
        strategies[name] = {
            "n": len(results),
            "mean_pre_max": _mean([r.pre["max"] for r in results]),
            "mean_post_max": _mean([r.post["max"] for r in results]),
            "bypass_rate": _bypass_rate(results, threshold),
            "mean_similarity": _mean([r.similarity for r in results]),
            "mean_iterations": _mean([float(r.iterations) for r in results]),
            "per_detector": pd,
            "hardest_detector": _hardest_detector(pd),
        }
    summary = {"threshold": threshold, "strategies": strategies}
    if "full_loop" in strategies and "single_pass" in strategies:
        fl, sp = strategies["full_loop"], strategies["single_pass"]
        summary["thesis_pass"] = bool(
            fl["bypass_rate"] >= sp["bypass_rate"] and fl["mean_similarity"] >= sp["mean_similarity"] - 0.02
        )
    return summary


def render(by_strategy: dict[str, list], threshold: float) -> str:
    """`by_strategy`: {strategy_name: [LoopResult, ...]}. Returns a markdown report string."""
    s = summarize(by_strategy, threshold)
    lines: list[str] = []
    lines.append("# humanize benchmark\n")
    lines.append(f"Threshold (max-proxy P(AI) for bypass): **{threshold}**\n")
    lines.append("| Strategy | n | mean pre max | mean post max | bypass rate | mean sim | mean iters |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for name, st in s["strategies"].items():
        lines.append(
            f"| {name} | {st['n']} | {st['mean_pre_max']:.3f} | {st['mean_post_max']:.3f} | "
            f"{st['bypass_rate']:.0%} | {st['mean_similarity']:.3f} | {st['mean_iterations']:.1f} |"
        )

    # Per-detector pre->post breakdown (uses the richest strategy that has detectors).
    detector_names: list[str] = []
    for st in s["strategies"].values():
        for d in st["per_detector"]:
            if d not in detector_names:
                detector_names.append(d)
    if detector_names:
        lines.append("\n## Per-detector mean P(AI): pre -> post (beat% = scored < threshold)")
        header = "| Strategy | " + " | ".join(detector_names) + " | hardest |"
        lines.append(header)
        lines.append("|---|" + "---:|" * len(detector_names) + "---|")
        for name, st in s["strategies"].items():
            cells = []
            for d in detector_names:
                pd = st["per_detector"].get(d)
                cells.append(f"{pd['pre']:.2f}->{pd['post']:.2f} ({pd['beat_rate']:.0%})" if pd else "-")
            hardest = st.get("hardest_detector") or "-"
            lines.append(f"| {name} | " + " | ".join(cells) + f" | {hardest} |")
        # Headline: how the strongest strategy fares against the single hardest detector.
        best = max(s["strategies"].values(), key=lambda st: st["bypass_rate"])
        hd = best.get("hardest_detector")
        if hd and hd in best["per_detector"]:
            lines.append(
                f"\n**Hardest detector to beat: `{hd}`** - best strategy beats it on "
                f"{best['per_detector'][hd]['beat_rate']:.0%} of samples "
                f"(mean P(AI) {best['per_detector'][hd]['post']:.2f})."
            )

    lines.append("")
    if "thesis_pass" in s:
        fl = s["strategies"]["full_loop"]
        sp = s["strategies"]["single_pass"]
        verdict = "PASS" if s["thesis_pass"] else "INCONCLUSIVE"
        lines.append(
            f"**Thesis (full-loop bypass >= single-pass at equal-or-better sim): {verdict}** "
            f"(full_loop {fl['bypass_rate']:.0%}@{fl['mean_similarity']:.2f} vs "
            f"single_pass {sp['bypass_rate']:.0%}@{sp['mean_similarity']:.2f})"
        )
    return "\n".join(lines)
