"""End-to-end proof: humanize against the commercial checkers, then verify pass/fail.

Given a hosted-LLM rewriter key (``ANTHROPIC_API_KEY`` / ``OPENAI_API_KEY``) **and** commercial
detector keys, this runs the full closed loop at ``--tier commercial`` (with a safety margin) and
then ``humanize-verify`` on the result — printing before/after scores per checker and an honest
PASS/FAIL across every configured detector. This is the "does it actually pass the real detectors"
button. It calls the paid APIs (loop scoring + before/after verify), so **it costs credits**.

    humanize-prove "Your AI text" --margin 0.10
    humanize-prove --file draft.txt --json
"""

from __future__ import annotations

import argparse
import json
import sys

from humanize._env import load_env
from humanize.scripts.run import humanize_text
from humanize.scripts.score import DEFAULT_THRESHOLD
from humanize.scripts.verify import verify


def prove(text: str, threshold: float = DEFAULT_THRESHOLD, margin: float = 0.10, max_iters: int = 5) -> dict:
    """Verify original -> humanize at commercial tier -> verify result. Returns a structured dict."""
    before = verify(text, threshold=threshold)
    result = humanize_text(
        text, tier="commercial", threshold=threshold, margin=margin, max_iters=max_iters
    )
    if "error" in result:
        return {"error": result["error"], "before": before}
    after = verify(result["final"], threshold=threshold)
    return {
        "before": before,
        "humanized": result["final"],
        "iterations": result["iterations"],
        "after": after,
        "passes_all": after["passes_all"],
    }


def _render(v: dict) -> str:
    if "error" in v:
        return f"ERROR: {v['error']}"
    b, a = v["before"], v["after"]
    lines = ["# humanize-prove (commercial tier)", ""]
    if not a["configured"]:
        return (
            "No commercial checkers configured. Set the API keys (ORIGINALITY_API_KEY, GPTZERO_API_KEY, "
            "...) and install .[commercial]; cannot prove 'passes all' without running the real checkers."
        )
    lines.append(f"checkers: {', '.join(a['configured'])}   iterations: {v['iterations']}")
    lines.append("\n| checker | before AI | after AI | pass |")
    lines.append("|---|---:|---:|---|")
    for name in a["results"]:
        bef = b["results"].get(name, {}).get("ai")
        aft = a["results"][name].get("ai")
        bs = f"{bef:.2f}" if isinstance(bef, (int, float)) else "-"
        as_ = f"{aft:.2f}" if isinstance(aft, (int, float)) else "-"
        mark = "PASS" if a["results"][name].get("passes") else "FAIL"
        lines.append(f"| {name} | {bs} | {as_} | {mark} |")
    lines.append("")
    lines.append("PASSES ALL CHECKERS" if v["passes_all"] else f"FAILS - {a['n_passing']}/{a['n_configured']} passed")
    lines.append("\n--- humanized text ---\n" + v["humanized"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    load_env()
    parser = argparse.ArgumentParser(prog="humanize-prove", description=__doc__)
    parser.add_argument("text", nargs="?", help="text to humanize + prove (or --file / stdin)")
    parser.add_argument("--file", "-f", help="read text from this file")
    parser.add_argument("--threshold", "-t", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--margin", type=float, default=0.10)
    parser.add_argument("--max-iters", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            text = fh.read()
    elif args.text:
        text = args.text
    else:
        text = sys.stdin.read()
    if not text.strip():
        print(json.dumps({"error": "empty input"}))
        return 2

    v = prove(text, threshold=args.threshold, margin=args.margin, max_iters=args.max_iters)
    print(json.dumps(v, ensure_ascii=True, indent=2) if args.json else _render(v))
    return 0 if v.get("passes_all") else 1


if __name__ == "__main__":
    raise SystemExit(main())
