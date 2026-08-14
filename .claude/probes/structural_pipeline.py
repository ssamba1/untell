"""Pipeline robustness: no crash on adversarial input, output non-empty, idempotence-ish."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.structural import StructuralRewriter

rw = StructuralRewriter()
cases = {
    "empty": "",
    "one_word": "Hello",
    "all_punct": "!!! ??? ...",
    "repeated": "Moreover, moreover, moreover, the framework leverages robust solutions.",
    "huge_word": "antidisestablishmentarianism" * 40,
    "emoji": "The system works 🚀 well here. The team 🎉 agreed.",
    "unicode": "café naïve résumé — déjà vu",
    "mixed_case": "THE SYSTEM READS THE FILE. The parser splits it.",
    "only_numbers": "123 456 789 0123 4567",
    "markdown": "# Header\n\n**bold** and *italic* text with `code`.",
}
out = {}
for name, t in cases.items():
    try:
        r = rw.rewrite(t, {"max": 0.9}, 0.3)
        out[name] = {"ok": True, "empty_out": not r.strip(), "sane_len": len(r) <= len(t) * 3 + 100}
    except Exception as e:
        out[name] = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:60]}"}
print(json.dumps(out, indent=1))
