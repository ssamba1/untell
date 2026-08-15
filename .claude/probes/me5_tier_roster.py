"""me5 pass probe: score_text tier resolution + roster note (live measurements)."""
import json
import os

os.environ["UNTELL_LITE_NO_TORCH"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from untell.scripts.score import score_text  # noqa: E402

TEXT = (
    "The rapid advancement of artificial intelligence has transformed the way we approach "
    "complex problems across numerous domains. This technological revolution presents both "
    "unprecedented opportunities and significant challenges that require careful "
    "consideration by researchers and practitioners alike."
)


def summarize(label, r):
    dets = sorted(r.get("detectors", {}).keys())
    live = [k for k in dets if not k.endswith("__error")]
    nones = [k for k in live if r["detectors"][k] is None]
    warn = r.get("warning") or ""
    roster = "ROSTER-NOTE" if ("ran without" in warn or "short roster" in warn) else "no-roster-note"
    print(json.dumps({
        "label": label,
        "tier": r.get("tier"),
        "tier_requested": r.get("tier_requested"),
        "detector_keys": live,
        "n_detectors": len([k for k in live if k not in nones]),
        "n_none": len(nones),
        "max": r.get("max"),
        "flagged": r.get("flagged"),
        "scored": r.get("scored", True),
        roster: True,
        "warning_head": warn[:160],
    }))


# PROBE 1: tier resolution
summarize("lite", score_text(TEXT, tier="lite"))
summarize("full", score_text(TEXT, tier="full"))
summarize("bogus", score_text(TEXT, tier="bogus"))
summarize("missing(default)", score_text(TEXT))
summarize("explicit-None", score_text(TEXT, tier=None))

# PROBE 2: roster note at full tier WITH mage disabled
os.environ["UNTELL_DISABLE_MAGE"] = "1"
summarize("full+UNTELL_DISABLE_MAGE=1", score_text(TEXT, tier="full"))
# lite tier with mage disabled (mage is not a lite member anyway)
summarize("lite+UNTELL_DISABLE_MAGE=1", score_text(TEXT, tier="lite"))
del os.environ["UNTELL_DISABLE_MAGE"]
# full tier again with mage re-enabled
summarize("full+mage-restored", score_text(TEXT, tier="full"))
