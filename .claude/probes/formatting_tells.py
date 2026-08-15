import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.tells import _formatting_tells

out = {}
# diff-anchored: 2+ '+' lines -> tell
diffy = "Some text here.\n+ added line one\n+ added line two\nMore text."
out["diff_anchored"] = _formatting_tells(diffy).get("diff_anchored", 0)
# code fenced: '+' lines inside code ignored
coded = "```\n+ not a diff\n+ still code\n```\nText."
out["code_stripped"] = "diff_anchored" not in _formatting_tells(coded)
# 3 title headings -> tell
heady = "# One Two Three Four\n# Five Six Seven Eight\n# Nine Ten Eleven Twelve"
out["title_3"] = _formatting_tells(heady).get("title_case_heading", 0)
# 1 heading only -> below floor 3
out["title_1_below"] = "title_case_heading" not in _formatting_tells("# One Two Three Four")
print(json.dumps(out, indent=1))
