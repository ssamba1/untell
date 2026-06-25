"""Render benchmark results as a markdown table."""

from __future__ import annotations


def _bypass_rate(results: list, threshold: float) -> float:
    if not results:
        return 0.0
    passed = sum(1 for r in results if r.post["max"] < threshold)
    return passed / len(results)


def render(by_strategy: dict[str, list], threshold: float) -> str:
    """`by_strategy`: {strategy_name: [LoopResult, ...]}. Returns a markdown report string."""
    lines: list[str] = []
    lines.append("# humanize benchmark\n")
    lines.append(f"Threshold (max-proxy P(AI) for bypass): **{threshold}**\n")
    lines.append("| Strategy | n | mean pre max | mean post max | bypass rate | mean sim | mean iters |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")

    def mean(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    for name, results in by_strategy.items():
        if not results:
            continue
        pre = mean([r.pre["max"] for r in results])
        post = mean([r.post["max"] for r in results])
        bypass = _bypass_rate(results, threshold)
        sim = mean([r.similarity for r in results])
        iters = mean([float(r.iterations) for r in results])
        lines.append(
            f"| {name} | {len(results)} | {pre:.3f} | {post:.3f} | "
            f"{bypass:.0%} | {sim:.3f} | {iters:.1f} |"
        )

    lines.append("")
    # Thesis check.
    if "full_loop" in by_strategy and "single_pass" in by_strategy:
        fl = by_strategy["full_loop"]
        sp = by_strategy["single_pass"]
        if fl and sp:
            fl_bypass = _bypass_rate(fl, threshold)
            sp_bypass = _bypass_rate(sp, threshold)
            fl_sim = mean([r.similarity for r in fl])
            sp_sim = mean([r.similarity for r in sp])
            verdict = (
                "PASS ✅" if (fl_bypass >= sp_bypass and fl_sim >= sp_sim - 0.02) else "INCONCLUSIVE ⚠️"
            )
            lines.append(
                f"**Thesis (full-loop bypass ≥ single-pass at equal-or-better sim): {verdict}** "
                f"(full_loop {fl_bypass:.0%}@{fl_sim:.2f} vs single_pass {sp_bypass:.0%}@{sp_sim:.2f})"
            )
    return "\n".join(lines)
