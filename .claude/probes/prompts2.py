import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.prompts import STYLES, STYLE_NAMES, build_rewrite_prompt

out = {}
out["styles"] = list(STYLES.keys())
out["n_styles"] = len(STYLES)
t = "Moreover, the framework leverages robust solutions."
for style in ("casual", "academic", "blunt"):
    p = build_rewrite_prompt(t, {"max": 0.9, "tier": "lite", "style": style}, 0.30)
    out[f"prompt_{style}"] = {
        "len": len(p),
        "has_text": t[:20] in p,
        "has_voice": "Voice:" in p,
    }
# unknown style -> ignored, prompt still builds
p_bad = build_rewrite_prompt(t, {"max": 0.9, "tier": "lite", "style": "nonexistent"}, 0.30)
p_none = build_rewrite_prompt(t, {"max": 0.9, "tier": "lite"}, 0.30)
out["unknown_style_same_as_none"] = p_bad == p_none
out["names_match"] = sorted(STYLE_NAMES) == sorted(STYLES.keys())
print(json.dumps(out, indent=1))
