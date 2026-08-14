"""layout _walk edge cases: unterminated constructs, trailing markers, mixed markers."""
import json
from untell.layout import apply_per_block

out = {}
def ident(t): return t
cases = {
    "unterminated_fence": "text before\n```\ncode never closed\n",
    "unterminated_math": "text before\n$$\nmath never closed\n",
    "trailing_list_marker": "item one\n- last item without newline",
    "fence_at_eof": "para\n```\ncode\n```",
    "empty_fence": "para\n```\n```\npara2",
    "math_then_fence": "$$\nint x dx\n$$\n```\ncode\n```\nend",
    "crlf_fence": "a\r\n```\r\ncode\r\n```\r\nb\r\n",
}
for name, t in cases.items():
    try:
        r = apply_per_block(t, ident)
        out[name] = {"roundtrip": r == t, "ok": True}
    except Exception as e:
        out[name] = {"roundtrip": False, "ok": False, "error": f"{type(e).__name__}: {str(e)[:60]}"}
print(json.dumps(out, indent=1))
