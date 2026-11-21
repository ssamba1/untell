"""Does the verdict on THIS text survive edits that cannot change who wrote it?

Population false-positive rates answer "how often is this detector wrong on human writing in
general". A person facing a flag needs a different number: whether the verdict on their own
document is a stable property of its words. That can be measured directly, on the document, with
no corpus and no assumptions: re-score it under formatting-only edits (same words, verified) and
count how often the verdict changes.

Three tiers, never pooled:

``null``
    same words in the same order (:mod:`.perturb`); any flip is a verdict about typography.
``light``
    edits a human copy-editor makes on autopilot (contractions, Oxford comma, US/UK spelling).
``rewrite``
    untell's deterministic CPU rewriters, kept only when its meaning gate passes. Optional, and
    the weakest evidence of the three: these change wording, so a flip here is consistent with a
    detector responding to style — which is what detectors claim to measure.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field

from .perturb import Variant, all_variants
from .scorers import Scorer, Verdict
from .stats import flip_rate

__all__ = ["StabilityResult", "measure_stability", "rewrite_variants", "chars_changed"]


def chars_changed(a: str, b: str) -> int:
    """Characters inserted, deleted or replaced to get from ``a`` to ``b``."""
    if a == b:
        return 0
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    return sum(max(i2 - i1, j2 - j1) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal")


def rewrite_variants(text: str, rewriters: tuple[str, ...] = ("structural", "surgical", "composite"),
                     ) -> list[Variant]:
    """Meaning-gated rewrites from untell's free CPU rewriters (R1, R2, ...)."""
    from untell.rewriter.base import get_rewriter
    from untell.scripts import quality
    from untell.scripts.score import score_text

    out: list[Variant] = []
    try:
        hint = score_text(text, tier="lite")
    except Exception:
        hint = {"tier": "lite", "detectors": {}}
    for i, name in enumerate(rewriters, 1):
        try:
            rw = get_rewriter(name)
            if rw is None:
                continue
            cand = rw.rewrite(text, hint)
        except Exception:
            continue
        if not cand or cand == text or not quality.passes(text, cand):
            continue
        out.append(Variant(f"R{i}", "rewrite", f"Rewrite ({name})",
                           f"meaning-gated {name} rewrite; wording changes", cand, noop=False))
    return out


@dataclass
class StabilityResult:
    scorer: dict
    base: dict
    variants: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"scorer": self.scorer, "base": self.base, "variants": self.variants,
                "summary": self.summary}


def _row(v: Variant, verdict: Verdict, source: str) -> dict:
    return {
        "id": v.id, "tier": v.tier, "label": v.label, "description": v.description,
        "noop": v.noop, "chars_changed": chars_changed(source, v.text),
        "score": verdict.score, "flagged": verdict.flagged,
        **({"error": verdict.detail["error"]} if "error" in verdict.detail else {}),
    }


def _summarise(base: Verdict, rows: list[dict], tier: str) -> dict:
    rs = [r for r in rows if r["tier"] == tier and not r["noop"]]
    fr = flip_rate(bool(base.flagged), [r["flagged"] for r in rs])
    scores = [r["score"] for r in rs if r["score"] is not None]
    if base.score is not None:
        scores_all = scores + [base.score]
        fr["score_min"] = min(scores_all)
        fr["score_max"] = max(scores_all)
        fr["score_spread"] = fr["score_max"] - fr["score_min"]
    flipped = [r for r in rs if r["flagged"] is not None and r["flagged"] != base.flagged]
    if flipped:
        smallest = min(flipped, key=lambda r: r["chars_changed"])
        fr["smallest_flip"] = {k: smallest[k] for k in ("id", "label", "chars_changed", "score")}
    return fr


def measure_stability(text: str, scorer: Scorer, tiers: tuple[str, ...] = ("null", "light"),
                      variants: list[Variant] | None = None) -> StabilityResult:
    """Score ``text`` and each variant; report flips per tier.

    ``variants`` overrides generation (used when scores were recorded by hand for a fixed set).
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    if variants is None:
        variants = all_variants(text, tuple(t for t in tiers if t in ("null", "light")))
        if "rewrite" in tiers:
            variants += rewrite_variants(text)
    base = scorer.verdict(text, "base")
    rows: list[dict] = []
    for v in variants:
        verdict = Verdict(base.score, base.flagged) if v.noop else scorer.verdict(v.text, v.id)
        rows.append(_row(v, verdict, text))
    summary = {t: _summarise(base, rows, t) for t in tiers if any(r["tier"] == t for r in rows)}
    summary["finding"] = finding(base, summary)
    return StabilityResult(
        scorer=scorer.describe(),
        base={"score": base.score, "flagged": base.flagged,
              **({"error": base.detail["error"]} if "error" in base.detail else {})},
        variants=rows,
        summary=summary,
    )


def finding(base: Verdict, summary: dict) -> str:
    """One plain-language sentence a non-specialist can quote."""
    if base.flagged is None:
        return "The detector produced no verdict on the original text, so stability is undefined."
    verdict = "flagged" if base.flagged else "not flagged"
    null = summary.get("null")
    if not null or not null.get("variants_scored"):
        return f"The original was {verdict}; no formatting-only variant could be scored."
    n, k = null["variants_scored"], null["flips"]
    if k:
        s = (f"The original was {verdict}. The verdict changed in {k} of {n} versions that contain "
             "exactly the same words in the same order — only quote style, spacing, line breaks or "
             "invisible characters differ. A verdict that depends on typography is not a "
             "measurement of who wrote the words.")
        sf = null.get("smallest_flip")
        if sf:
            s += f" Smallest change that flipped it: {sf['label']} ({sf['chars_changed']} characters)."
        return s
    s = (f"The original was {verdict}, and the verdict held across all {n} formatting-only "
         "versions tested. This test found no instability; that is not evidence either way "
         "about authorship.")
    light = summary.get("light")
    if light and light.get("flips"):
        s += (f" It did change in {light['flips']} of {light['variants_scored']} light copy-edits "
              "(contractions, commas, spelling).")
    return s
