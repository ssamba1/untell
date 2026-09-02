"""What 46 real detectors' own calibration says about shipping a single threshold.

Every result elsewhere in this repository measures untell's own lite tier, which generalises to
nothing. This module measures **other people's detectors** -- GPTZero, RADAR, QuillBot,
Binoculars, Fast-DetectGPT and forty more -- and it does so without running them, without an API
key, without a GPU and without access to any gated dataset.

The trick is that [RAID](https://github.com/liamdugan/raid)'s public leaderboard makes every
submission publish, for each of eight text domains, **the threshold at which that detector's
false-positive rate on human-written text is 5%**. RAID computes it per domain by construction
(`find_threshold` in its `raid/evaluate.py` fits it separately on each domain's human, unattacked
texts), so the published numbers are each author's own answer to: *what must I set my threshold to,
on this kind of writing, to accuse 5% of innocent people?*

A domain-stable detector would report eight near-identical numbers. MEASURED 2026-09-01, the
median span across 46 detectors is **0.610 of the 0-1 score range**.

    python -m eval.detector_calibration report          # from the committed snapshot
    python -m eval.detector_calibration report --fetch  # re-fetch the live leaderboard first

**What this shows and does not.** A large span means the calibration is domain-specific: a single
shipped threshold cannot hold a uniform false-positive rate, and must therefore be close to right
for a domain or two and wrong for the rest. It does NOT say what any deployment's error rate
actually is -- that needs the score distributions, which the leaderboard does not publish. RAID's
domains are text *types*, not writer groups, so this generalises the threshold finding and not the
subgroup ones.

**Why the span and not a ratio.** The first version of this analysis reported ratios and got
63370x for a detector whose thresholds run 1.6e-05 to 0.9997. On a 0-1 probability scale a ratio
is dominated by how close the low end sits to zero, which is a property of the score scale rather
than of the detector's stability. The absolute span is scale-appropriate and is what is reported.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path

REPO = "https://github.com/liamdugan/raid"
# Only `results.json` is wanted. The sibling `predictions.json` files carry a score per example and
# run to gigabytes; a blobless, non-cone sparse checkout of just the results keeps this cheap.
SPARSE_PATTERN = "/leaderboard/submissions/*/results.json"
SNAPSHOT = Path(__file__).resolve().parent.parent / ".claude" / "probes" / "raid-per-domain-thresholds.json"
# RAID publishes calibrations at both targets. The finding is not an artifact of picking one:
# MEASURED 2026-09-01, the median span is 0.610 at the 5% target and 0.551 at 1%.
TARGET_FPR = "0.05"
TARGETS = ("0.05", "0.01")
MIN_DOMAINS = 8
CITATION = (
    "Dugan, L., et al., 'RAID: A Shared Benchmark for Robust Evaluation of Machine-Generated Text "
    "Detectors', ACL 2024. Leaderboard submissions: https://github.com/liamdugan/raid"
)


class LeaderboardUnavailable(RuntimeError):
    """The live leaderboard could not be fetched. The snapshot is still readable."""


def fetch(dest: Path, timeout: int = 900) -> Path:
    """Blobless sparse checkout of the leaderboard's results files."""
    dest.mkdir(parents=True, exist_ok=True)
    steps = (
        ["git", "clone", "--depth", "1", "--filter=blob:none", "--no-checkout", "-q", REPO, "."],
        ["git", "sparse-checkout", "init", "--no-cone"],
        ["git", "sparse-checkout", "set", SPARSE_PATTERN],
        ["git", "checkout", "-q"],
    )
    for step in steps:
        proc = subprocess.run(step, cwd=dest, capture_output=True, text=True,  # noqa: S603
                              timeout=timeout)
        if proc.returncode != 0:
            raise LeaderboardUnavailable(
                f"{' '.join(step[:3])} failed: {(proc.stderr or '').strip()[:300]}"
            )
    return dest / "leaderboard" / "submissions"


def read_submissions(root: Path, target: str = TARGET_FPR) -> list[dict]:
    """One row per detector that published thresholds for all `MIN_DOMAINS` domains."""
    rows = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        path = d / "results.json"
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            continue
        th = (raw.get("thresholds") or {}).get(target)
        if not isinstance(th, dict):
            continue
        vals = {k: v for k, v in th.items() if isinstance(v, (int, float))}
        if len(vals) < MIN_DOMAINS:
            continue
        rows.append({
            "detector": raw.get("detector_name") or d.name,
            "submission_dir": d.name,
            "date_released": raw.get("date_released"),
            "target_fpr": target,
            "thresholds_at_5pct_fpr": vals,
            "span": round(max(vals.values()) - min(vals.values()), 6),
        })
    return rows


def summarise(rows: list[dict]) -> dict:
    """Spans, the domains that systematically need the extremes, and the scale check."""
    spans = [r["span"] for r in rows]
    off_scale = [r["detector"] for r in rows
                 if not all(0.0 <= v <= 1.0 for v in r["thresholds_at_5pct_fpr"].values())]
    ranks: dict[str, list[int]] = {}
    for r in rows:
        th = r["thresholds_at_5pct_fpr"]
        for i, dom in enumerate(sorted(th, key=th.get)):
            ranks.setdefault(dom, []).append(i)
    return {
        "detectors": len(rows),
        "median_span": round(statistics.median(spans), 4) if spans else None,
        "over_quarter": sum(1 for s in spans if s > 0.25),
        "over_half": sum(1 for s in spans if s > 0.50),
        "over_ninety": sum(1 for s in spans if s > 0.90),
        "most_stable": min(rows, key=lambda r: r["span"])["detector"] if rows else None,
        "least_stable": max(rows, key=lambda r: r["span"])["detector"] if rows else None,
        # A ratio would be meaningless for any detector scoring off [0,1]; the span is not, but
        # the check is reported rather than assumed.
        "off_unit_scale": off_scale,
        "domain_mean_rank": {d: round(statistics.mean(v), 2)
                             for d, v in sorted(ranks.items(), key=lambda kv: statistics.mean(kv[1]))},
        "citation": CITATION,
    }


def render(rows: list[dict], summary: dict, top: int = 12) -> str:
    out = [
        f"Per-domain threshold needed to hold a {float(TARGET_FPR):.0%} false-positive rate",
        f"on human text, across {MIN_DOMAINS} domains, for {summary['detectors']} detectors.",
        "",
        "A domain-stable detector would report near-identical numbers. Span is on a 0-1 scale.",
        "",
    ]
    for r in sorted(rows, key=lambda r: -r["span"])[:top]:
        th = r["thresholds_at_5pct_fpr"]
        lo_d, hi_d = min(th, key=th.get), max(th, key=th.get)
        out.append(f"  {r['detector'][:32]:34} {th[lo_d]:.4f} ({lo_d:9}) -> "
                   f"{th[hi_d]:.4f} ({hi_d:9})  span {r['span']:.3f}")
    out += [
        "",
        f"  median span {summary['median_span']:.3f} of the score range",
        f"  span > 25% of the scale: {summary['over_quarter']}/{summary['detectors']}",
        f"  span > 50%:              {summary['over_half']}/{summary['detectors']}",
        f"  span > 90%:              {summary['over_ninety']}/{summary['detectors']}",
        f"  most domain-stable:      {summary['most_stable']}",
        "",
        "Text types by how permissive a threshold they need (mean rank, 0 = most permissive):",
        "  " + "  ".join(f"{d}={v}" for d, v in summary["domain_mean_rank"].items()),
        "",
        "These detectors ship ONE threshold. Their own calibration says no single value holds a",
        "uniform false-positive rate across text types, so a deployed threshold is necessarily",
        "close to right for a domain or two and wrong for the rest.",
        "",
        "This bounds CALIBRATION, not harm: it does not say what any deployment's error rate is,",
        "which needs score distributions the leaderboard does not publish. Domains here are text",
        "types, not writer groups.",
        "",
        summary["citation"],
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("report", help="span analysis from the snapshot, or a fresh fetch")
    r.add_argument("--fetch", action="store_true", help="re-fetch the live leaderboard first")
    r.add_argument("--workdir", type=Path, default=Path("/tmp/untell-raid-leaderboard"))
    r.add_argument("--json", action="store_true")
    r.add_argument("--target", choices=TARGETS, default=TARGET_FPR,
                   help="target false-positive rate the thresholds were calibrated to")
    r.add_argument("--save-snapshot", action="store_true",
                   help="overwrite the committed snapshot with what was fetched")
    a = ap.parse_args(argv)
    if a.cmd != "report":
        ap.print_help()
        return 1

    if a.fetch:
        try:
            rows = read_submissions(fetch(a.workdir), target=a.target)
        except (LeaderboardUnavailable, subprocess.TimeoutExpired, OSError) as exc:
            print(f"live leaderboard unavailable ({exc}); falling back to the snapshot",
                  file=sys.stderr)
            rows = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    else:
        if not SNAPSHOT.exists():
            print(f"no snapshot at {SNAPSHOT}; run with --fetch", file=sys.stderr)
            return 2
        rows = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    summary = summarise(rows)
    if a.save_snapshot and a.fetch:
        SNAPSHOT.write_text(json.dumps(rows, indent=1), encoding="utf-8")
        print(f"wrote {SNAPSHOT}", file=sys.stderr)
    print(json.dumps({"summary": summary, "detectors": rows}, indent=2) if a.json
          else render(rows, summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
