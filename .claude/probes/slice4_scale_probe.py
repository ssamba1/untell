"""Slice 4 re-run: scale-ceiling probes for the untell engine.

Measures wall time + peak memory (tracemalloc) of the core primitives on
pathological/scale inputs: 1MB+ prose, 100k sentences, deep nested markdown,
huge tables, thousands of short lines, wide lines, repeated tokens, and
adversarial regex inputs (fence/backtick/dollar runs, nested quantifiers).

Each case runs in a child process with a hard timeout so a genuine hang
cannot kill the sweep. Run with the project venv:
    export PYTHONPATH=
    UNTELL_LITE_NO_TORCH=1 ./.venv/Scripts/python.exe .claude/probes/slice4_scale_probe.py
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import time
import tracemalloc

CASES = []


def _run_case(fn, label, timeout=90):
    ctx = mp.get_context("spawn")
    q = ctx.Queue(1)
    p = ctx.Process(target=_worker, args=(fn, q))
    t0 = time.monotonic()
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join()
        return {"case": label, "status": "TIMEOUT/HANG", "seconds": round(time.monotonic() - t0, 2)}
    dt = time.monotonic() - t0
    try:
        out = q.get_nowait()
    except Exception:
        out = {"error": "worker died without result"}
    out["case"] = label
    out["seconds"] = round(dt, 2)
    out["status"] = "ok"
    return out


def _worker(fn, q):
    import sys

    # Spawn children re-import this module under `__mp_main__`; make sure `fn`
    # (a top-level function here) is resolvable by the name the pickler used.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    tracemalloc.start()
    t0 = time.monotonic()
    try:
        out = fn()
    except Exception as exc:
        out = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    _, peak = tracemalloc.get_traced_memory()
    out["peak_mb"] = round(peak / 1e6, 1)
    out["wall_s"] = round(time.monotonic() - t0, 2)
    q.put(out)


# --- input builders ---------------------------------------------------------

def _prose(words: int) -> str:
    sent = "The quick brown fox jumps over the lazy dog while the cat sleeps peacefully on the warm windowsill. "
    n = max(1, words // 12)
    return (sent * n)[: words * 7]


def _short_lines(n: int) -> str:
    return "\n".join(f"line number {i} here" for i in range(n))


def _wide_line(chars: int) -> str:
    return "x" * chars


def _repeated(n: int) -> str:
    return " ".join(["the"] * n)


def _deep_markdown(depth: int) -> str:
    return "\n".join(("#" * (i % 6) + " heading " + str(i)) for i in range(depth))


def _huge_table(rows: int, cols: int) -> str:
    head = "| " + " | ".join(f"c{j}" for j in range(cols)) + " |"
    sep = "| " + " | ".join(["---"] * cols) + " |"
    body = "\n".join(
        "| " + " | ".join(f"r{i}c{j}" for j in range(cols)) + " |" for i in range(rows)
    )
    return head + "\n" + sep + "\n" + body


# --- cases ------------------------------------------------------------------

def c_score_1mb():
    from untell.scripts.score import score_text

    text = _prose(150_000)  # ~1MB
    r = score_text(text, tier="lite")
    return {"max": r.get("max"), "chars": len(text)}


def c_score_100k_sentences():
    from untell.scripts.score import score_text

    text = _short_lines(100_000)  # 100k short lines
    r = score_text(text, tier="lite")
    return {"max": r.get("max"), "chars": len(text)}


def c_score_wide_line():
    from untell.scripts.score import score_text

    text = _wide_line(100_000)
    r = score_text(text, tier="lite")
    return {"max": r.get("max"), "chars": len(text)}


def c_score_repeated():
    from untell.scripts.score import score_text

    text = _repeated(200_000)
    r = score_text(text, tier="lite")
    return {"max": r.get("max"), "chars": len(text)}


def c_score_deep_markdown():
    from untell.scripts.score import score_text

    text = _deep_markdown(50_000)
    r = score_text(text, tier="lite")
    return {"max": r.get("max"), "chars": len(text)}


def c_score_huge_table():
    from untell.scripts.score import score_text

    text = _huge_table(5_000, 20)  # 5000 rows x 20 cols
    r = score_text(text, tier="lite")
    return {"max": r.get("max"), "chars": len(text)}


def c_lock_1mb():
    from untell.scripts.preserve import lock

    text = _prose(150_000)
    masked, mapping = lock(text)
    return {"masked_len": len(masked), "n_locked": len(mapping)}


def c_lock_adversarial_fences():
    from untell.scripts.preserve import lock

    # 100k backticks + fences: catastrophic-backtracking candidate for ```.*?```
    text = "```" * 33_000
    masked, mapping = lock(text)
    return {"masked_len": len(masked), "n_locked": len(mapping)}


def c_lock_dollar_runs():
    from untell.scripts.preserve import lock

    text = ("$" * 60 + " ") * 5_000  # dollar runs — latex_math regex stress
    masked, mapping = lock(text)
    return {"masked_len": len(masked), "n_locked": len(mapping)}


def c_split_100k():
    from untell.text_split import split_sentences

    text = _short_lines(100_000)
    s = split_sentences(text)
    return {"n_sentences": len(s), "chars": len(text)}


def c_aligned_chunks_big():
    from untell.text_split import aligned_chunks

    a = _prose(20_000)  # 20k words
    b = _prose(20_000)
    chunks = aligned_chunks(a, b)
    return {"n_chunks": len(chunks), "words": len(a.split())}


def c_token_overlap_big():
    from untell.scripts.quality import token_overlap

    a = _prose(20_000)
    b = _prose(20_000)
    v = token_overlap(a, b)
    return {"value": round(v, 4), "words": len(a.split())}


def c_tells_1mb():
    from untell.scripts.tells import score_tells

    text = _prose(150_000)
    r = score_tells(text)
    return {"tells": r.get("tells"), "chars": len(text)}


def c_regex_pat_stress():
    """Adversarial inputs against preserve._PATTERNS directly (no spaCy)."""
    import re
    import time

    from untell.scripts.preserve import _PATTERNS

    inputs = {
        "backticks_100k": "`" * 100_000,
        "fence_open_50k": "```" * 16_000 + "text",
        "dollar_50k": "$" * 50_000,
        "parens_30k": "(" * 30_000,
        "a_repeat_200k": "a" * 200_000,
        "ambiguous_run": ("ab" * 50_000) + "!",
    }
    out = {}
    for name, text in inputs.items():
        t0 = time.monotonic()
        total = 0
        for label, pat in _PATTERNS:
            for m in pat.finditer(text):
                total += m.end() - m.start()
        out[name] = {"dt": round(time.monotonic() - t0, 3), "span_chars": total}
    return out


def c_score_gpt2_quadratic():
    """The `text.find(s, pos)` loop in _full_score: measure scaling of the
    sentence-alignment pass on the torch path (2 sizes, ratio tells all)."""
    import time

    from untell.detectors.perplexity_burstiness import _full_score  # noqa: F401

    # Directly measure the find-loop without the model: replicate its cost shape.
    from untell.text_split import split_sentences

    def align(text):
        sents = split_sentences(text)
        pos = 0
        bounds = []
        for s in sents:
            idx = text.find(s, pos)
            if idx < 0:
                continue
            bounds.append((idx, idx + len(s)))
            pos = idx + len(s)
        return bounds

    sizes = [50_000, 100_000, 200_000]
    rows = {}
    for n in sizes:
        text = _prose(n // 7)  # ~n chars
        t0 = time.monotonic()
        b = align(text)
        rows[str(n)] = round(time.monotonic() - t0, 3)
    return rows


def main() -> int:
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    results = []
    for fn, label, timeout in CASES:
        print(f"running {label} ...", flush=True)
        r = _run_case(fn, label, timeout)
        print(json.dumps(r, indent=1), flush=True)
        results.append(r)
    out_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "slice4_scale_probe_results.jsonl"
    )
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(json.dumps(r) for r in results) + "\n")
    print(f"\nwrote {out_path}")
    return 0


CASES = [
    (c_score_1mb, "score_text lite, ~1MB prose", 120),
    (c_score_100k_sentences, "score_text lite, 100k short lines", 120),
    (c_score_wide_line, "score_text lite, 100k-char wide line", 60),
    (c_score_repeated, "score_text lite, 200k repeated tokens", 60),
    (c_score_deep_markdown, "score_text lite, 50k headings", 60),
    (c_score_huge_table, "score_text lite, 5000x20 markdown table", 60),
    (c_lock_1mb, "lock, ~1MB prose (spaCy NER)", 120),
    (c_lock_adversarial_fences, "lock, 33k fence-open runs", 60),
    (c_lock_dollar_runs, "lock, dollar runs", 60),
    (c_split_100k, "split_sentences, 100k lines", 60),
    (c_aligned_chunks_big, "aligned_chunks, 20k words", 60),
    (c_token_overlap_big, "token_overlap, 20k words", 60),
    (c_tells_1mb, "score_tells, ~1MB prose", 120),
    (c_regex_pat_stress, "preserve._PATTERNS adversarial regex", 120),
    (c_score_gpt2_quadratic, "gpt2 _full_score find-loop scaling", 90),
]


if __name__ == "__main__":
    raise SystemExit(main())
