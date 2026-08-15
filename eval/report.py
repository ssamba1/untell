"""Render benchmark results as a markdown table (+ optional JSON)."""

from __future__ import annotations


def _bypass_rate(results: list, threshold: float) -> float:
    """Fraction of samples whose post-rewrite max fell below threshold.

    Samples where NOTHING scored are excluded, not counted as passes. ``score_text`` returns
    ``max: 0.0`` as a placeholder when no detector produced a number, and ``0.0 < threshold`` is
    true — so a benchmark run against a broken ML stack reported a **100% bypass rate**, the most
    flattering possible number, produced by measuring nothing. ``scored: False`` exists on the
    result dict precisely to tell the two apart.
    """
    scored = [r for r in results if r.post.get("scored") is not False]
    if not scored:
        return 0.0
    passed = sum(1 for r in scored if r.post["max"] < threshold)
    return passed / len(scored)


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
        # PAIRED: a sample counts for this detector only when BOTH its pre and post scores are
        # numbers. Filtering the two sides independently is the same defect `summarize` was already
        # fixed for at the aggregate level, one row further in. Measured: a detector scoring 0.95 on
        # 4 samples pre, then erroring on the 3 hard ones, rendered as "0.95 -> 0.10, beat 100%" —
        # a pre-mean over 4 samples beside a post-mean over 1. Worse than a wrong number: because
        # `_hardest_detector` ranks by LOWEST beat rate, the detector that fell over on every hard
        # sample is promoted to the easiest one, and the genuinely hardest detector loses the
        # headline. Erroring out must never read as bypassing.
        paired = [
            (r.pre["detectors"][name], r.post["detectors"][name])
            for r in results
            if isinstance(r.pre.get("detectors", {}).get(name), (int, float))
            and isinstance(r.post.get("detectors", {}).get(name), (int, float))
        ]
        beat = [1.0 if post < threshold else 0.0 for _, post in paired]
        out[name] = {
            "pre": _mean([pre for pre, _ in paired]),
            "post": _mean([post for _, post in paired]),
            "beat_rate": _mean(beat),
            # Carried so the renderer can show the denominator rather than implying it is `n`.
            "n": float(len(paired)),
        }
    return out


def _hardest_detector(per_detector: dict[str, dict[str, float]]) -> str | None:
    """The detector hardest to beat = lowest beat rate (ties broken by highest mean post).

    Detectors with no paired sample are not candidates. `_mean([])` is 0.0, which is the lowest
    beat rate expressible — so a detector that errored on EVERY sample outranked every detector
    that actually ran, and the report named it the hardest to beat on zero observations.
    """
    usable = {d: v for d, v in per_detector.items() if v.get("n", 0.0) > 0}
    if not usable:
        return None
    return min(usable, key=lambda d: (usable[d]["beat_rate"], -usable[d]["post"]))


def summarize(by_strategy: dict[str, list], threshold: float) -> dict:
    """Machine-readable summary (used by `render` and available for JSON output)."""
    strategies = {}
    for name, results in by_strategy.items():
        if not results:
            continue
        # ONE denominator for every P(AI) figure in the row. `_bypass_rate` already excluded
        # unscored samples — max: 0.0 is a placeholder, and 0.0 < threshold would count it as a
        # pass — but the means beside it did not, so the same row mixed two populations. Measured:
        # 5 samples at 0.35 plus 5 unscored gave mean_post_max 0.175, which reads as comfortably
        # under a 0.30 threshold, next to a bypass rate of 0%. The true scored-only mean was 0.35.
        scored = [r for r in results if r.post.get("scored") is not False]
        pd = _per_detector(scored or results, threshold)
        strategies[name] = {
            "n": len(results),
            "n_scored": len(scored),
            "mean_pre_max": _mean([r.pre["max"] for r in scored]),
            "mean_post_max": _mean([r.post["max"] for r in scored]),
            "bypass_rate": _bypass_rate(results, threshold),
            "mean_similarity": _mean([r.similarity for r in results]),
            "mean_iterations": _mean([float(r.iterations) for r in results]),
            "per_detector": pd,
            "hardest_detector": _hardest_detector(pd),
        }
    summary = {"threshold": threshold, "strategies": strategies}
    if "full_loop" in strategies and "single_pass" in strategies:
        fl, sp = strategies["full_loop"], strategies["single_pass"]
        # Each bypass rate is over its OWN strategy's scored subset, so the two are only comparable
        # when both scored everything. A strategy whose detector failed on some samples gets a
        # smaller denominator and an inflated rate. Measured: full_loop with 1 pass and 9 unscored
        # reported 100% against single_pass's genuine 50% (5 of 10), and thesis_pass came back True
        # — declaring the project's headline claim proven while single_pass was five times better in
        # absolute terms.
        comparable = fl["n_scored"] == fl["n"] and sp["n_scored"] == sp["n"]
        # `>=` on the bypass rate alone passes when BOTH rates are zero, which is the most common
        # outcome on real AI text and carries no information about the thesis at all. MEASURED on 8
        # HC3 answers: single_pass 0%, full_loop 0%, thesis_pass True — the project's headline claim
        # declared proven by a run in which neither strategy cleared a single sample, and in which
        # single_pass had actually scored WORSE than doing nothing (0.6354 against noop's 0.6217).
        #
        # So the claim has to rest on a STRICT improvement somewhere. Bypass rate is the metric the
        # thesis is stated in, so it decides when it separates them; when it ties — including the
        # degenerate 0-0 tie — fall through to the mean post `max`, which is the same quantity
        # measured before it has been thresholded. `thesis_basis` records which comparison answered,
        # so a reader never has to guess whether a pass came from the informative one.
        similarity_ok = fl["mean_similarity"] >= sp["mean_similarity"] - 0.02
        if fl["bypass_rate"] != sp["bypass_rate"]:
            better, basis = fl["bypass_rate"] >= sp["bypass_rate"], "bypass_rate"
        else:
            better, basis = fl["mean_post_max"] < sp["mean_post_max"], "mean_post_max (bypass tied)"
        # And it has to beat DOING NOTHING. `single_pass` is a deliberate stand-in for a naive
        # commercial tool, and measured on 12 HC3 answers it is net-HARMFUL: it raises the detector
        # score on 8 of them, mean +0.0156, worst +0.1082. Beating a baseline that is worse than
        # `noop` is not evidence the loop works, and `noop` was already being computed and then
        # ignored here. On the 8-answer run above the margins were 0.5982 against single_pass's
        # 0.6354 but only 0.6217 for noop — a real win, and a much smaller one than the headline
        # comparison implies.
        #
        # Only applied when the harness actually ran `noop`; a caller comparing two strategies
        # without a control still gets the comparison it asked for, with the basis naming it.
        beats_nothing = True
        if "noop" in strategies:
            np = strategies["noop"]
            if np["n_scored"] != np["n"]:
                beats_nothing = False
                summary["thesis_undecided"] = (
                    f"noop scored {np['n_scored']}/{np['n']} — the control is not comparable, so "
                    "there is nothing to measure the loop against. Fix the detector stack and re-run."
                )
            else:
                beats_nothing = fl["mean_post_max"] < np["mean_post_max"]
                basis = f"{basis} + beats noop" if beats_nothing else f"{basis} but NOT better than noop"
        summary["thesis_pass"] = bool(comparable and better and similarity_ok and beats_nothing)
        summary["thesis_basis"] = basis
        if not comparable:
            summary["thesis_undecided"] = (
                f"not comparable: full_loop scored {fl['n_scored']}/{fl['n']}, "
                f"single_pass scored {sp['n_scored']}/{sp['n']} — bypass rates are over different "
                "denominators, so the comparison is meaningless. Fix the detector stack and re-run."
            )
    return summary


def render(by_strategy: dict[str, list], threshold: float) -> str:
    """`by_strategy`: {strategy_name: [LoopResult, ...]}. Returns a markdown report string."""
    s = summarize(by_strategy, threshold)
    lines: list[str] = []
    lines.append("# untell benchmark\n")
    lines.append(f"Threshold (max-proxy P(AI) for bypass): **{threshold}**\n")
    lines.append("| Strategy | n | mean pre max | mean post max | bypass rate | mean sim | mean iters |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    any_unscored = False
    for name, st in s["strategies"].items():
        # Show the denominator the P(AI) figures are actually over. `n` alone next to a percentage
        # reads as "this fraction of n", which is wrong whenever anything went unscored.
        n_cell = str(st["n"]) if st["n_scored"] == st["n"] else f"{st['n_scored']}/{st['n']}"
        any_unscored = any_unscored or st["n_scored"] != st["n"]
        lines.append(
            f"| {name} | {n_cell} | {st['mean_pre_max']:.3f} | {st['mean_post_max']:.3f} | "
            f"{st['bypass_rate']:.0%} | {st['mean_similarity']:.3f} | {st['mean_iterations']:.1f} |"
        )
    if any_unscored:
        lines.append(
            "\n> **n shown as `scored/total`.** Every P(AI) figure above — the means, the bypass "
            "rate and the per-detector beat rates — is over the SCORED samples only. Samples no "
            "detector could score carry a `max: 0.0` placeholder, and counting those would report "
            "them as passes."
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
                if not pd or not pd.get("n"):
                    # No paired sample: the detector never produced both a pre and a post number.
                    # Rendering 0.00->0.00 (0%) here would be indistinguishable from a real result.
                    cells.append("-")
                    continue
                # Flag the denominator inline when this detector saw fewer samples than the
                # strategy did, so a beat rate off 1 of 4 samples cannot be read as off 4.
                suffix = "" if int(pd["n"]) == st["n_scored"] else f" [n={int(pd['n'])}]"
                cells.append(f"{pd['pre']:.2f}->{pd['post']:.2f} ({pd['beat_rate']:.0%}){suffix}")
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
        if s.get("thesis_undecided"):
            lines.append(f"\n> {s['thesis_undecided']}")
    return "\n".join(lines)
