"""Battery 2: layout, CRLF, unicode, and rewriter-neutrality invariants."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.layout import blocks, apply_per_block
from untell.scripts.run import untell_text

out = {}

# 1. CRLF: layout blocks preserve line endings through a transform
text_crlf = "Line one here.\r\nLine two there.\r\n```\r\ncode block\r\n```\r\n"
segs = list(blocks(text_crlf))
out["crlf_blocks_parse"] = len(segs) >= 3
# apply identity transform per block, reassemble == original
def identity(unit): return unit
rebuilt = apply_per_block(text_crlf, identity)
out["crlf_roundtrip_identity"] = (rebuilt == text_crlf)

# 2. Empty / whitespace-only inputs
for name, x in [("empty", ""), ("spaces", "   "), ("newline", "\n\n"), ("tabs", "\t\t")]:
    r = untell_text(x, tier="lite", max_iters=2, seed=1)
    out[f"emptyish_{name}_no_crash"] = True
    out[f"emptyish_{name}_final_is_input"] = (r.get("final") == x)

# 3. Unicode: emoji, combining marks, CJK, RTL survive layout pass
for name, x in [("emoji", "Hello 😀 world. Next sentence here."),
                ("cjk", "这是一段中文。第二句。"),
                ("rtl", "שלום עולם. משפט שני."),
                ("accents", "Café naïve, déjà vu. Résumé.")]:
    rebuilt = apply_per_block(x, identity)
    out[f"unicode_{name}_roundtrip"] = (rebuilt == x)

# 4. A single huge word (no spaces) doesn't break the loop
big = "x" * 5000
r = untell_text(big, tier="lite", max_iters=1, seed=1)
out["huge_word_no_crash"] = True

print(json.dumps(out, indent=1))
