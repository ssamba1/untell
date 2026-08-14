"""Probe 4: MCP server tool functions (score / untell) under concurrent threads.

Extracts the actual registered tool closures from the FastMCP instance built by
`_server()` and calls them from threads — the same code an MCP client hits, minus
the JSON-RPC transport. Every concurrent result must equal its serial baseline.

Run:  PYTHONPATH= UNTELL_LITE_NO_TORCH=1 .venv/Scripts/python.exe .claude/probes/concurrency_mcp_tools.py
"""
from __future__ import annotations

import json
import sys
import threading
import time

from untell.mcp_server import _server

TEXT = (
    "The advancement of artificial intelligence has revolutionized the way we approach "
    "complex problems across many domains. Researchers continue to develop increasingly "
    "sophisticated models that demonstrate remarkable capabilities in natural language "
    "understanding and generation."
)

FINDINGS: list[str] = []


def canon(d) -> str:
    return json.dumps(d, sort_keys=True, default=str, ensure_ascii=True)


def main() -> int:
    srv = _server()
    tools = {t.name: t.fn for t in srv._tool_manager.list_tools()}
    print(f"[mcp] registered tools: {sorted(tools)}")
    score_fn = tools["score"]
    untell_fn = tools["untell"]

    # ---- serial baselines ---------------------------------------------------
    base_score = canon(score_fn(TEXT, tier="lite"))
    print(f"[mcp] baseline score tool ok: {base_score[:80]}...")
    print("[mcp] warmup untell tool (one-time imports) ...")
    t0 = time.time()
    base_untell = canon(untell_fn(TEXT, tier="lite", rewriter="surgical", seed=42,
                                  max_iters=1, best_of=1))
    print(f"[mcp] baseline untell tool ok in {time.time()-t0:.1f}s: {base_untell[:80]}...")

    errors: list[str] = []
    score_results: list[str] = [None] * 6
    untell_results: list[str] = [None] * 3

    def w_score(i: int) -> None:
        try:
            score_results[i] = canon(score_fn(TEXT, tier="lite"))
        except Exception as e:  # noqa: BLE001
            errors.append(f"score-{i}: {e!r}")

    def w_untell(i: int) -> None:
        try:
            untell_results[i] = canon(untell_fn(TEXT, tier="lite", rewriter="surgical",
                                                seed=42, max_iters=1, best_of=1))
        except Exception as e:  # noqa: BLE001
            errors.append(f"untell-{i}: {e!r}")

    threads = [threading.Thread(target=w_score, args=(i,)) for i in range(6)] + \
              [threading.Thread(target=w_untell, args=(i,)) for i in range(3)]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.time() - t0
    print(f"[mcp] 6 score + 3 untell tool calls concurrently: {wall:.1f}s")

    bad_s = [i for i, r in enumerate(score_results) if r != base_score]
    bad_u = [i for i, r in enumerate(untell_results) if r != base_untell]
    if bad_s:
        FINDINGS.append(
            f"RACE (mcp score): {len(bad_s)}/6 concurrent MCP score results differ from "
            f"serial baseline (threads {bad_s})"
        )
    if bad_u:
        FINDINGS.append(
            f"RACE (mcp untell): {len(bad_u)}/3 concurrent MCP untell results differ from "
            f"serial baseline (threads {bad_u}); sample: {untell_results[bad_u[0]][:150]!r} vs "
            f"{base_untell[:150]!r}"
        )
    if errors:
        FINDINGS.append(f"EXCEPTIONS in MCP tool calls: {errors[:5]}")

    print(f"[mcp] score mismatches={bad_s}, untell mismatches={bad_u}, errors={len(errors)}")

    print("\n=== FINDINGS ===")
    if not FINDINGS:
        print("none — MCP tool functions are stable under concurrent threads")
    for i, f in enumerate(FINDINGS, 1):
        print(f"{i}. {f}")
    return 1 if FINDINGS else 0


if __name__ == "__main__":
    sys.exit(main())
