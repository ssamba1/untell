"""Hidden char inside a LOCKED span: does it survive the untell_text round-trip?
If scrub runs before lock, it's gone. If after restore, it's back."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import untell_text

# ZWSP inside a URL (locked span) and inside a citation
dirty = ("The system is documented at https://example.com/\u200bpage and in (Smith, 2019\u200b). "
         "The team ran the experiment and recorded the results. They published the findings. "
         "The data was clear and the conclusion followed. More prose to ensure length here.")
r = untell_text(dirty, tier="lite", max_iters=2, seed=1)
final = r.get("final") or ""
out = {
    "zwsp_in_url_survives": "\u200b" in final,
    "zwsp_count_after": final.count("\u200b"),
    "url_preserved": "https://example.com/" in final,
    "citation_preserved": "Smith, 2019" in final,
}
print(json.dumps(out, indent=1))
