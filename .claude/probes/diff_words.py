import json
import untell.rich_output as R
R._RICH = True

out = {}
def marked_plain(s: str) -> str:
    return s.markup if hasattr(s, "markup") else str(s)
def count_green(s: str) -> int:
    return s.markup.count("bold green")

a = "the quick brown fox jumps over the lazy dog"
cases = {
    "insert_front": (a, "NEW the quick brown fox jumps over the lazy dog"),
    "insert_mid": (a, "the quick brown fox NEW jumps over the lazy dog"),
    "delete": (a, "the quick brown fox over the lazy dog"),
    "substitute": (a, "the quick brown fox leaps over the lazy dog"),
    "nochange": ("the quick brown fox", "the quick brown fox"),
}
for name, (x, y) in cases.items():
    d = R._diff_words(x, y)
    out[name] = {"green_words": count_green(d), "total_b": len(y.split()), "markup_len": len(d.markup)}
print(json.dumps(out, indent=1))
