"""prompts: STYLE_NAMES consistent with style_profile; prompt builds for every style."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.prompts import STYLE_NAMES
from untell.rewriter import build_rewrite_prompt

out = {}
out["style_names"] = STYLE_NAMES
# build prompt for every style
bad = []
for style in STYLE_NAMES:
    try:
        p = build_rewrite_prompt("Some text to rewrite here.", style=style)
        if not isinstance(p, str) or len(p) < 20:
            bad.append(f"{style}: short/empty")
    except Exception as e:
        bad.append(f"{style}: {type(e).__name__}")
out["all_styles_build"] = bad
print(json.dumps(out, indent=1))
