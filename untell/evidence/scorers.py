"""One interface over every way a verdict can be obtained.

An audit has to be able to ask the detector that actually produced the accusation, and most of
those are not Python objects. So a scorer is resolved from a short spec string:

``local`` / ``local:lite`` / ``local:full``
    untell's own ensemble via :func:`untell.scripts.score.score_text` (its calibrated verdict).
``<detector name>``
    any registered adapter, e.g. ``gptzero``, ``pangram``, ``originality``, ``hc3_roberta``.
``cmd:<shell command>``
    run the command with the text on stdin; read a score from stdout — a bare number, or JSON
    with a ``score`` / ``ai`` / ``probability`` field. Wraps anything: a curl call, a vendor CLI,
    a browser script.
``raw:<detector name>``
    a local model without untell's input normalisation, as an un-hardened deployment runs it.
``manual:<file>``
    scores somebody recorded by hand (from a web UI, a Turnitin report, a screenshot), keyed by
    variant id: ``base``, ``N1`` … — CSV ``id,score[,flagged]`` or a JSON object. This is how an
    audit covers detectors that have no API at all.

Every scorer reports ``None`` rather than inventing a score when it cannot produce one.
"""

from __future__ import annotations

import csv
import json
import re
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["Scorer", "Verdict", "resolve_scorer", "scorer_from_function", "known_detector_names"]


@dataclass
class Verdict:
    score: float | None
    flagged: bool | None
    detail: dict = field(default_factory=dict)


@dataclass
class Scorer:
    name: str
    kind: str  # local | detector | cmd | manual | function
    threshold: float | None  # None: the scorer's own calibrated verdict decides
    _fn: Callable[[str, str | None], Verdict]
    version: str | None = None

    def verdict(self, text: str, key: str | None = None) -> Verdict:
        try:
            return self._fn(text, key)
        except Exception as exc:  # a failing detector is an unscored variant, never a crash
            return Verdict(None, None, {"error": f"{type(exc).__name__}: {exc}"[:300]})

    def describe(self) -> dict:
        return {"name": self.name, "kind": self.kind, "threshold": self.threshold,
                "version": self.version}


def _flag(score: float | None, threshold: float) -> bool | None:
    return None if score is None or score != score else score >= threshold


def scorer_from_function(fn: Callable[[str], float | None], name: str = "function",
                         threshold: float = 0.5, version: str | None = None) -> Scorer:
    """Wrap a plain ``text -> score`` callable (handy for tests and notebooks)."""
    def run(text: str, key: str | None) -> Verdict:
        s = fn(text)
        s = None if s is None else float(s)
        return Verdict(s, _flag(s, threshold))
    return Scorer(name, "function", threshold, run, version)


def _local(tier: str, threshold: float | None) -> Scorer:
    """The local ensemble. With no explicit threshold its own calibrated verdict is used."""
    from untell.scripts.score import DEFAULT_THRESHOLD, score_text  # noqa: F401

    def run(text: str, key: str | None) -> Verdict:
        r = score_text(text, tier=tier)
        s = r.get("max")
        flagged = r.get("flagged") if threshold is None else _flag(s, threshold)
        return Verdict(s, flagged, {"tier": r.get("tier"), "detectors": r.get("detectors", {})})

    del DEFAULT_THRESHOLD  # the loop target; NOT the bar `flagged` is decided on
    return Scorer(f"untell-local-{tier}", "local", threshold, run)


def known_detector_names() -> list[str]:
    from untell.detectors.base import all_detectors
    return [d.name for d in all_detectors()]


def _raw(name: str, threshold: float) -> Scorer:
    """A local detector WITHOUT untell's input normalisation — the model as others deploy it.

    untell strips invisible characters and normalises whitespace before its own detectors see
    text, because those are measured shortcuts (one space before each full stop took hc3_roberta's
    AUROC from 0.98 to 0.14). An audit of the MODEL, as it behaves when hosted elsewhere, needs it
    without that protection; this scorer provides exactly that and nothing else.
    """
    from untell.detectors.base import RAW_INPUT

    inner = _detector(name, threshold)

    def run(text: str, key: str | None) -> Verdict:
        token = RAW_INPUT.set(True)
        try:
            return inner._fn(text, key)
        finally:
            RAW_INPUT.reset(token)

    return Scorer(f"raw:{name}", "detector", threshold, run, inner.version)


def _detector(name: str, threshold: float) -> Scorer:
    from untell.detectors.base import all_detectors

    matches = [d for d in all_detectors() if d.name == name]
    if not matches:
        raise ValueError(
            f"unknown detector {name!r}; known: {', '.join(known_detector_names())}, or use "
            "local, cmd:<command>, manual:<file>"
        )
    det = matches[0]
    if not det.available():
        raise RuntimeError(
            f"detector {name!r} is not available here (missing dependency or API key). "
            "Commercial detectors need their key in the environment — see docs/auditing.md."
        )

    def run(text: str, key: str | None) -> Verdict:
        s = det.score(text)
        return Verdict(s, _flag(s, threshold))

    return Scorer(name, "detector", threshold, run, getattr(det, "version", None))


_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _parse_score(out: str) -> float | None:
    out = out.strip()
    if not out:
        return None
    try:
        data = json.loads(out)
    except ValueError:
        data = None
    if isinstance(data, (int, float)):
        val = float(data)
    elif isinstance(data, dict):
        val = None
        for k in ("score", "ai", "probability", "ai_probability", "ai_likelihood", "p_ai"):
            if isinstance(data.get(k), (int, float)):
                val = float(data[k])
                break
        if val is None:
            return None
    else:
        m = _NUM.search(out)
        if not m:
            return None
        val = float(m.group(0))
    if val > 1.0 and val <= 100.0:  # a percentage
        val /= 100.0
    return val if 0.0 <= val <= 1.0 else None


def _cmd(command: str, threshold: float, timeout: float = 120.0) -> Scorer:
    argv = shlex.split(command)
    if not argv:
        raise ValueError("cmd: needs a command")

    def run(text: str, key: str | None) -> Verdict:
        proc = subprocess.run(argv, input=text, capture_output=True, text=True,
                              encoding="utf-8", timeout=timeout)
        if proc.returncode != 0:
            return Verdict(None, None, {"error": f"exit {proc.returncode}: {proc.stderr[:200]}"})
        s = _parse_score(proc.stdout)
        return Verdict(s, _flag(s, threshold))

    return Scorer(f"cmd:{argv[0]}", "cmd", threshold, run)


def load_manual(path: str | Path) -> dict[str, dict]:
    """Read hand-recorded scores: ``{variant_id: {"score": float|None, "flagged": bool|None}}``."""
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    rows: dict[str, dict] = {}

    def norm_flag(v) -> bool | None:
        if v is None or v == "":
            return None
        if isinstance(v, bool):
            return v
        return str(v).strip().lower() in ("1", "true", "yes", "y", "flagged", "ai")

    def norm_score(v) -> float | None:
        if v is None or v == "":
            return None
        f = float(v)
        return f / 100.0 if 1.0 < f <= 100.0 else f

    if p.suffix.lower() == ".json":
        data = json.loads(raw)
        for k, v in data.items():
            if isinstance(v, dict):
                rows[k] = {"score": norm_score(v.get("score")), "flagged": norm_flag(v.get("flagged"))}
            else:
                rows[k] = {"score": norm_score(v), "flagged": None}
    else:
        for r in csv.DictReader(raw.splitlines()):
            vid = (r.get("id") or "").strip()
            if vid:
                rows[vid] = {"score": norm_score((r.get("score") or "").strip()),
                             "flagged": norm_flag((r.get("flagged") or "").strip())}
    return rows


def _manual(path: str, threshold: float) -> Scorer:
    rows = load_manual(path)

    def run(text: str, key: str | None) -> Verdict:
        row = rows.get(key or "base")
        if row is None:
            return Verdict(None, None, {"error": f"no recorded score for {key or 'base'!r}"})
        s, f = row["score"], row["flagged"]
        return Verdict(s, f if f is not None else _flag(s, threshold))

    return Scorer(f"manual:{Path(path).name}", "manual", threshold, run)


def resolve_scorer(spec: str, threshold: float | None = None) -> Scorer:
    """Turn a spec string (see module docstring) into a :class:`Scorer`."""
    spec = (spec or "").strip()
    if not spec:
        raise ValueError("empty detector spec")
    thr = 0.5 if threshold is None else float(threshold)
    if spec == "local" or spec.startswith("local:"):
        return _local(spec.split(":", 1)[1] if ":" in spec else "full", threshold)
    if spec.startswith("raw:"):
        return _raw(spec[4:], thr)
    if spec.startswith("cmd:"):
        return _cmd(spec[4:], thr)
    if spec.startswith("manual:"):
        return _manual(spec[7:], thr)
    return _detector(spec, thr)
