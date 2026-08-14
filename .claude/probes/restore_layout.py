"""restore_layout_lines: line-count-changing transforms must be refused, alignment preserved."""
import json
from untell.layout import restore_layout_lines

orig = "Line one here.\nLine two there.\n```\ncode block\n```\nFinal line.\n"
out = {}
# 1. Same line count, prose changed -> merged correctly
transformed = "Line one CHANGED.\nLine two there.\n```\ncode block\n```\nFinal line.\n"
out["same_count_merges"] = restore_layout_lines(orig, transformed) == transformed
# 2. Line count changed (reflow) -> returned untouched
reflowed = "Line one here.\nLine two there.\nLine three extra.\n```\ncode block\n```\nFinal line.\n"
out["reflow_refused"] = restore_layout_lines(orig, reflowed) == reflowed
# 3. Prose replaced with fenced-code-looking content -> the fence stays protected
evil = "Line one here.\nLine two there.\nLine three extra.\n"
out2 = restore_layout_lines(orig, evil)
out["fewer_lines_refused"] = out2 == evil
# 4. CRLF handling
crlf_orig = "A one.\r\nB two.\r\n```\r\ncode\r\n```\r\n"
crlf_t = "A ONE.\r\nB two.\r\n```\r\ncode\r\n```\r\n"
out["crlf_merged"] = restore_layout_lines(crlf_orig, crlf_t) == crlf_t
print(json.dumps(out, indent=1))
