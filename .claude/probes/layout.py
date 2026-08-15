import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.layout import apply_per_block, blocks, restore_layout_lines

out = {}
# 1. fenced code preserved, prose transformed
t = "# Header\n\nSome prose here.\n\n```python\nx = 1\n```\n\nMore prose."
out["code_kept"] = "```python" in apply_per_block(t, lambda b: b.upper())
out["prose_transformed"] = "SOME PROSE HERE." in apply_per_block(t, lambda b: b.upper())
out["header_kept"] = "# Header" in apply_per_block(t, lambda b: b.upper())
# 2. blocks() returns prose units only
b = blocks(t)
out["blocks"] = b
out["no_code_in_blocks"] = all("x = 1" not in unit for unit in b)
# 3. single paragraph passthrough
out["single_para"] = apply_per_block("One paragraph here.", lambda x: x.upper()) == "ONE PARAGRAPH HERE."
# 4. CRLF preserved
crlf = "Line one.\r\n\r\nProse here."
out["crlf_kept"] = "\r\n" in apply_per_block(crlf, lambda b: b.upper())
print(json.dumps(out, indent=1))
