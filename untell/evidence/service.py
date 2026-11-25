"""The evidence commands as plain functions, for the MCP and REST surfaces.

Network surfaces get a NARROWER scorer vocabulary than the CLI, on purpose:

- ``cmd:`` is never accepted. On the CLI it runs a command the user typed; over MCP or HTTP the
  "user" can be a prompt-injected model or an anonymous caller, and accepting it would be remote
  code execution.
- ``manual:<file>`` is never accepted (it reads a server-side path). Callers pass the recorded
  scores inline instead, as ``scores={"base": 0.91, "N1": 0.12, ...}``.
- commercial detectors spend the server operator's API credit, so over HTTP they need
  ``UNTELL_API_ALLOW_COMMERCIAL=1``. Over MCP (a local process the user started) they are allowed.
"""

from __future__ import annotations

import os

from .brief import build_brief
from .perturb import all_variants
from .scorers import Scorer, Verdict, resolve_scorer
from .stability import chars_changed, measure_stability

LOCAL_SPECS = ("local", "local:lite", "local:full")


class RefusedSpec(ValueError):
    pass


def _inline_scorer(scores: dict, threshold: float) -> Scorer:
    rows: dict[str, tuple[float | None, bool | None]] = {}
    for k, v in scores.items():
        if isinstance(v, dict):
            s, f = v.get("score"), v.get("flagged")
        else:
            s, f = v, None
        if s is not None:
            s = float(s)
            s = s / 100.0 if 1.0 < s <= 100.0 else s
            if not 0.0 <= s <= 1.0:
                raise RefusedSpec(f"score for {k!r} is not a probability or a percentage")
        rows[str(k)] = (s, None if f is None else bool(f))

    def run(text: str, key: str | None) -> Verdict:
        if (key or "base") not in rows:
            return Verdict(None, None, {"error": f"no recorded score for {key or 'base'!r}"})
        s, f = rows[key or "base"]
        return Verdict(s, f if f is not None else (None if s is None else s >= threshold))

    return Scorer("recorded-scores", "manual", threshold, run)


def safe_scorer(detector: str | None, threshold: float | None, scores: dict | None,
                allow_commercial: bool) -> Scorer:
    thr = 0.5 if threshold is None else float(threshold)
    if scores:
        return _inline_scorer(scores, thr)
    spec = (detector or "local:lite").strip()
    if spec.startswith(("cmd:", "manual:")):
        raise RefusedSpec(f"{spec.split(':', 1)[0]}: detectors are CLI-only; pass recorded "
                          "scores inline as `scores` instead")
    if spec in LOCAL_SPECS:
        return resolve_scorer(spec, threshold)
    from untell.detectors.commercial import commercial_detectors

    if spec in {d.name for d in commercial_detectors()}:
        if not allow_commercial:
            raise RefusedSpec(f"{spec} spends the operator's API credit; this server does not "
                              "allow it (set UNTELL_API_ALLOW_COMMERCIAL=1 to enable)")
        return resolve_scorer(spec, threshold)
    raise RefusedSpec(f"unknown detector {spec!r}; use one of {', '.join(LOCAL_SPECS)}, a "
                      "commercial detector name, or pass recorded `scores`")


def http_allows_commercial() -> bool:
    return os.environ.get("UNTELL_API_ALLOW_COMMERCIAL", "").strip() == "1"


def variants_payload(text: str, tiers: tuple[str, ...] = ("null", "light")) -> dict:
    vs = [v for v in all_variants(text, tiers) if not v.noop]
    return {
        "variants": [{"id": v.id, "tier": v.tier, "label": v.label, "description": v.description,
                      "chars_changed": chars_changed(text, v.text), "text": v.text} for v in vs],
        "how_to_use": "Score the original (id 'base') and each variant with the detector under "
                      "test, then call stability or brief with scores={'base': s0, 'N1': s1, ...}.",
    }


def stability_payload(text: str, detector: str | None = None, threshold: float | None = None,
                      scores: dict | None = None, tiers: tuple[str, ...] = ("null", "light"),
                      allow_commercial: bool = False) -> dict:
    sc = safe_scorer(detector, threshold, scores, allow_commercial)
    return measure_stability(text, sc, tiers=tiers).to_dict()


def brief_payload(text: str, detector: str | None = None, name: str | None = None,
                  threshold: float | None = None, scores: dict | None = None,
                  documents: int = 1, fpr: float | None = None, tpr: float = 0.9,
                  detector_version: str | None = None, allow_commercial: bool = False,
                  writer: str = "general", score: float | None = None,
                  flagged: bool | None = None) -> dict:
    # Naming a detector without a way to run it (no `detector`, no `scores`) used to fall back to
    # untell's lite detector, so a brief headed "Turnitin" showed untell's stability table and
    # untell's score. With only a name, there is nothing of that detector's to test: skip the
    # stability section and build from the reported score and the published rates.
    if name and not detector and not scores:
        stab = None
    else:
        stab = stability_payload(text, detector, threshold, scores,
                                 allow_commercial=allow_commercial)
    label = name or detector or ("recorded-scores" if scores else "local:lite")
    return build_brief(text, label, stability=stab, observed_score=score, observed_flagged=flagged,
                       documents=max(1, int(documents)), fpr=fpr, tpr=tpr,
                       detector_version=detector_version, writer=writer)
