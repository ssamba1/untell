"""Inspection report for the humanize loop: per-candidate rejection reasons and per-sentence diff.

Activated only when ``--inspect`` is passed; zero overhead on the default path.

Event schema (each item in the ``inspect`` list returned by ``untell_text``):

    type ``"candidate_rejected"``:
        iter  int    — which outer iteration (1-based)
        draw  int    — which best-of-N draw within that iteration (1-based)
        gate  str    — name of the FIRST veto that fired (the human-readable name)
        vetoes list  — ALL vetoes that fired (gate is vetoes[0])
        sim   float | None  — cosine similarity at rejection time

    type ``"candidate_accepted"``:
        iter  int
        draw  int

    type ``"candidate_identical"``:
        iter  int
        draw  int
        The rewriter returned its input BYTE-IDENTICAL — it wrote no draft. Distinct from
        ``candidate_accepted`` because it passes every gate for a reason that is not a judgement:
        an identical string reproduces every locked span, scores similarity 1.0, and ties on
        detector score. Reporting it as an accepted candidate described a rewrite that never
        happened, on precisely the run a reader opens ``--inspect`` to understand. It happens
        whenever a rewriter has no edit surface on the text — ``surgical`` on prose carrying no
        catalogued tell is the measured case; see ``rewriter/surgical.py``.

    type ``"adopted"``:
        iter  int    — the candidate from this iteration's valid pool was adopted, meaning the
                       text actually CHANGED. Emitted in lockstep with the ``adopted`` counter in
                       the result: a candidate that ties by being the incumbent itself is not an
                       adoption and gets ``not_adopted``.

    type ``"not_adopted"``:
        iter  int    — valid candidates existed but none beat the incumbent. Also the correct
                       event when every draw was ``candidate_identical``: nothing was adopted
                       because there was nothing to adopt, which the renderer says in those words
                       rather than as a contest the text narrowly won.

When the valid pool was empty (all draws were rejected), no adopted/not_adopted event is emitted
for that iteration — the rejections themselves are the record.

``render_inspect_report`` turns that list into a human-readable text block.
"""

from __future__ import annotations

import difflib


def render_inspect_report(
    source: str,
    final: str,
    events: list[dict],
    *,
    pre_score: dict | None = None,
    post_score: dict | None = None,
) -> str:
    """Render a human-readable inspection report.

    Output goes to stderr via the CLI; the raw ``events`` list is on the result dict under
    ``inspect`` for programmatic callers.

    Two sections:
    1. Sentences — post-hoc diff of source vs final, showing change status and pre-rewrite tells.
    2. Candidate log — per-iteration, per-draw rejection reasons.
    """
    lines: list[str] = []
    W = 72

    pre_max = (pre_score or {}).get("max")
    post_max = (post_score or {}).get("max")
    hdr = "INSPECT"
    if pre_max is not None:
        hdr += f"  pre {pre_max:.3f}"
    if post_max is not None:
        hdr += f"  post {post_max:.3f}"
    lines.append("=" * W)
    lines.append(hdr)
    lines.append("=" * W)

    # ------------------------------------------------------------------ sentences
    lines.append("")
    lines.append("SENTENCES (source vs final)")
    lines.append("-" * W)

    try:
        from untell.scripts.tells import score_tells
        from untell.text_split import split_sentences

        src_sents = split_sentences(source)
        out_sents = split_sentences(final)

        # Per-sentence tells from the SOURCE (what the rewriter was trying to fix).
        src_tells: dict[str, list[str]] = {}
        for s in src_sents:
            t = score_tells(s)
            cats = [k for k, v in t.items() if isinstance(v, int) and v > 0 and k not in ("tells",)]
            if cats:
                src_tells[s] = cats

        matcher = difflib.SequenceMatcher(None, src_sents, out_sents, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for s in src_sents[i1:i2]:
                    tells_str = _tells_suffix(src_tells.get(s))
                    lines.append(f"[ok]      {_clip(s)}{tells_str}")
            elif tag == "replace":
                src_block = src_sents[i1:i2]
                out_block = out_sents[j1:j2]
                pairs = min(len(src_block), len(out_block))
                for src, out in zip(src_block[:pairs], out_block[:pairs]):
                    tells_str = _tells_suffix(src_tells.get(src))
                    lines.append(f"[rewrite] src{tells_str}: {_clip(src)}")
                    lines.append(f"          out: {_clip(out)}")
                for s in src_block[pairs:]:
                    lines.append(f"[deleted] {_clip(s)}")
                for o in out_block[pairs:]:
                    lines.append(f"[added]   {_clip(o)}")
            elif tag == "delete":
                for s in src_sents[i1:i2]:
                    lines.append(f"[deleted] {_clip(s)}")
            elif tag == "insert":
                for o in out_sents[j1:j2]:
                    lines.append(f"[added]   {_clip(o)}")
    except Exception as exc:
        lines.append(f"  (sentence diff unavailable: {exc})")

    # ------------------------------------------------------------------ candidate log
    lines.append("")
    lines.append("CANDIDATE LOG")
    lines.append("-" * W)

    if not events:
        lines.append("  (no events — loop exited before the rewrite phase)")
    else:
        by_iter: dict[int, list[dict]] = {}
        for ev in events:
            by_iter.setdefault(ev.get("iter", 0), []).append(ev)

        for it in sorted(by_iter):
            lines.append(f"iter {it}:")
            draw_n = 0
            # "none beat the incumbent" is true but unhelpful when the only candidate WAS the
            # incumbent: it reads as a close contest the text lost. Distinguish the iteration in
            # which the rewriter produced nothing to contest with.
            drew = [e for e in by_iter[it]
                    if e.get("type") in ("candidate_accepted", "candidate_identical")]
            all_identical = bool(drew) and all(
                e.get("type") == "candidate_identical" for e in drew
            )
            for ev in by_iter[it]:
                t = ev.get("type")
                if t == "candidate_rejected":
                    draw_n += 1
                    gate = ev.get("gate", "unknown")
                    sim = ev.get("sim")
                    sim_str = f"  sim={sim:.3f}" if sim is not None else ""
                    vetoes = ev.get("vetoes", [])
                    if len(vetoes) > 1:
                        others = ", ".join(vetoes[1:])
                        lines.append(f"  draw {draw_n}: REJECTED  {gate}{sim_str}  (also: {others})")
                    else:
                        lines.append(f"  draw {draw_n}: REJECTED  {gate}{sim_str}")
                elif t == "candidate_accepted":
                    draw_n += 1
                    lines.append(f"  draw {draw_n}: passed gates")
                elif t == "candidate_identical":
                    draw_n += 1
                    lines.append(
                        f"  draw {draw_n}: IDENTICAL to the input — the rewriter wrote nothing"
                    )
                elif t == "adopted":
                    lines.append("  -> adopted (score improved or tied)")
                elif t == "not_adopted":
                    lines.append(
                        "  -> nothing to adopt: every draw was the input itself"
                        if all_identical
                        else "  -> valid candidates existed but none beat the incumbent"
                    )

    lines.append("=" * W)
    return "\n".join(lines)


def _clip(s: str, max_len: int = 90) -> str:
    s = s.strip()
    return (s[: max_len - 1] + "…") if len(s) > max_len else s


def _tells_suffix(cats: list[str] | None) -> str:
    if not cats:
        return ""
    return f"  [{', '.join(cats)}]"
