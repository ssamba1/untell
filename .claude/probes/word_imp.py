"""word_importance.py invariants: article agreement, case matching, plural forms."""
import json
from untell.attacks.word_importance import agree_article, _match_case, _looks_plural, _frame_form, takes_an

out = {}
# agree_article: a/an choice by following sound
cases = [("a", "apple"), ("an", "apple"), ("a", "hour"), ("an", "hour"), ("a", "university"), ("an", "university"), ("an", "elephant"), ("a", "elephant")]
out["agree_article"] = {}
for art, word in cases:
    out["agree_article"][f"{art}|{word}"] = agree_article(art, word)
# _match_case
out["match_case"] = {
    "Model->MODEL": _match_case("Model", "model"),
    "MODEL->model": _match_case("MODEL", "model"),
    "Model->deploy": _match_case("Model", "deploy"),
}
# _looks_plural
out["looks_plural"] = {w: _looks_plural(w) for w in ["systems", "analysis", "children", "data", "framework", "series"]}
# _frame_form
out["frame_form"] = {
    "myriad": _frame_form("myriad"),
    "plethora": _frame_form("plethora"),
}
# takes_an
out["takes_an"] = {w: takes_an(w) for w in ["apple", "hour", "honest", "university", "unique", "one"]}
print(json.dumps(out, indent=1))
