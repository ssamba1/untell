import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.prompts import STYLE_NAMES, build_rewrite_prompt

out = {}
bad = []
for style in STYLE_NAMES:
    try:
        p = build_rewrite_prompt("Some text to rewrite here.", {"style": style, "flagged_sentences": ["s1"]}, 0.3)
        if not isinstance(p, str) or len(p) < 20:
            bad.append(f"{style}: short")
    except Exception as e:
        bad.append(f"{style}: {type(e).__name__}")
out["n_styles"] = len(STYLE_NAMES)
out["all_build"] = bad
# style name embedded in prompt
p = build_rewrite_prompt("Text.", {"style": "academic"}, 0.3)
out["style_embedded"] = "Voice:" in p
print(json.dumps(out, indent=1))
