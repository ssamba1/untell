"""L4 probe: best_of drafts in untell_text + prompts module style templates.

Probe 1: untell_text best_of=3 -> up to 3 drafts/iter, one final, no crash;
         best_of=1 -> single-draft path (1 draw/iter).
Probe 2: prompts.STYLES casual/academic/blunt templates + build_rewrite_prompt
         system prompt + style validation behavior.
"""
import os
import sys

os.environ["UNTELL_LITE_NO_TORCH"] = "1"
sys.path.insert(0, os.getcwd())

from untell.rewriter.prompts import STYLES, STYLE_NAMES, build_rewrite_prompt  # noqa: E402
from untell.scripts.run import untell_text, _unknown_style_warning  # noqa: E402

TEXT = (
    "Artificial intelligence has revolutionized the way we approach modern medicine. "
    "Moreover, researchers believe that machine learning algorithms can identify diseases "
    "earlier than traditional methods. This represents a significant advancement in patient "
    "care and could save countless lives across the globe. Furthermore, the integration of AI "
    "into healthcare systems promises to enhance efficiency and reduce costs. Ultimately, "
    "these developments underscore the transformative potential of technology in the medical "
    "field."
)

out = {}

# ---------- PROBE 1: best_of drafts ----------
# Warm-up call absorbs the cold torch/MiniLM import so the measured runs are warm.
warm = untell_text(TEXT, tier="lite", rewriter="composite", best_of=1, max_iters=1, seed=7)
out["warmup"] = {"final_is_str": isinstance(warm.get("final"), str), "error": warm.get("error")}

r1 = untell_text(TEXT, tier="lite", rewriter="composite", best_of=1, max_iters=2, seed=7)
r3 = untell_text(TEXT, tier="lite", rewriter="composite", best_of=3, max_iters=2, seed=7)

out["best_of_1"] = {
    "final_keys": [k for k in r1 if k == "final"],
    "final_is_str": isinstance(r1.get("final"), str),
    "iters": r1.get("iterations"),
    "rewrites": r1.get("rewrites"),
    "adopted": r1.get("adopted"),
    "post_max": r1.get("post", {}).get("max"),
    "stopped": r1.get("stopped"),
    "error": r1.get("error"),
}
out["best_of_3"] = {
    "final_keys": [k for k in r3 if k == "final"],
    "final_is_str": isinstance(r3.get("final"), str),
    "iters": r3.get("iterations"),
    "rewrites": r3.get("rewrites"),
    "adopted": r3.get("adopted"),
    "post_max": r3.get("post", {}).get("max"),
    "stopped": r3.get("stopped"),
    "error": r3.get("error"),
}

# ---------- PROBE 2: prompts module ----------
for style in ("casual", "academic", "blunt"):
    score_result = {
        "detectors": {"mage": 0.93, "perplexity_burstiness": 0.41},
        "style": style,
        "flagged_sentences": ["Moreover, researchers believe that machine learning algorithms "
                              "can identify diseases earlier than traditional methods."],
    }
    prompt = build_rewrite_prompt(TEXT, score_result, threshold=0.30)
    out.setdefault("prompts", {})[style] = {
        "has_rewrite_system": "Rewrite the text so it reads like an actual" in prompt,
        "voice_line": f"Voice: {STYLES[style]}" in prompt,
        "style_entry": STYLES[style],
        "prompt_len": len(prompt),
    }

out["style_validation"] = {
    "n_styles": len(STYLES),
    "style_names": STYLE_NAMES,
    "casual_academic_blunt_present": all(s in STYLES for s in ("casual", "academic", "blunt")),
    "warning_known_style_casual": _unknown_style_warning("casual"),
    "warning_unknown_style": _unknown_style_warning("bogus_style_xyz"),
    "warning_none": _unknown_style_warning(None),
}

print("PROBE RESULT")
import json
print(json.dumps(out, indent=2, default=str))
