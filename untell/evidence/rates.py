"""Published, cited error rates for named detectors (``published_rates.json``)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

__all__ = ["all_rates", "rates_for", "best_fpr_estimate"]

_PATH = Path(__file__).with_name("published_rates.json")

_ALIASES = {
    "untell-local": "untell-local-full",
    "local": "untell-local-full",
    "local:full": "untell-local-full",
    "local:lite": "untell-local-lite",
    "roberta_openai": "open-source-roberta",
    "hc3_roberta": "open-source-roberta",
}


@lru_cache(maxsize=1)
def all_rates() -> tuple[dict, ...]:
    data = json.loads(_PATH.read_text(encoding="utf-8"))
    return tuple(data["entries"])


def _key(name: str) -> str:
    n = (name or "").strip().lower()
    if n.startswith("untell-local-") or n.startswith("cmd:") or n.startswith("manual:"):
        return n
    return _ALIASES.get(n, n)


def rates_for(detector: str) -> list[dict]:
    """Every published entry for ``detector`` (case-insensitive; a few aliases resolved)."""
    k = _key(detector)
    return [dict(e) for e in all_rates() if e["detector"].lower() == k]


def best_fpr_estimate(detector: str, population: str = "general") -> dict | None:
    """A conservative single FPR for Bayes arithmetic.

    Two rules, in order. Figures verified at their primary source (``checked == "primary"``) are
    preferred over ones seen only in summaries or vendor claims; within whichever set is used, the
    HIGHEST credible figure wins — conservative in the accused writer's favour on purpose, since a
    brief that picks the detector's best day is advocacy for the accusation. An observed zero
    becomes its 95% upper bound, and metrics that are not false-positive rates are skipped.
    A rate measured on one population of writers is never applied to another.
    """
    from .stats import rule_of_three_upper

    candidates = []
    for e in rates_for(detector):
        if e.get("metric") != "false_positive_rate":
            continue
        # A rate measured on one population of writers is not evidence about another: the 2023
        # TOEFL figures (52-76%) would otherwise swamp every general-population estimate.
        if e.get("population", "general") != population:
            continue
        v = e.get("value")
        if v is None:
            v = e.get("upper")
        elif v == 0.0:
            # An observed zero is not a zero rate: use its 95% upper bound instead.
            if e.get("n"):
                v = rule_of_three_upper(int(e["n"]))
            elif e.get("upper"):
                v = e["upper"]
        if v is not None:
            candidates.append((float(v), e))
    primary = [c for c in candidates if c[1].get("checked") == "primary"]
    pool = primary or candidates
    if not pool:
        return None
    v, e = max(pool, key=lambda c: c[0])
    return {"fpr": v, "source": e["source"], "url": e["url"], "condition": e.get("condition"),
            "checked": e.get("checked"), "population": e.get("population", "general")}
