import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.structural import _front_subordinate_clauses

out = {}
# trailing subordinate clause fronted
s = ["The system works because the parser is fast."]
f = _front_subordinate_clauses(s, rate=1.0)
out["fronted"] = f != s and f[0].startswith("Because")
# already-fronted not double-fronted
s2 = ["Because the parser is fast, the system works."]
out["already_kept"] = _front_subordinate_clauses(s2, rate=1.0) == s2
# question never fronted
s3 = ["Does it work because the parser is fast?"]
out["question_kept"] = _front_subordinate_clauses(s3, rate=1.0) == s3
# multi-clause with comma not fronted
s4 = ["The system works, because the parser is fast, and the loader is slow."]
out["comma_kept"] = _front_subordinate_clauses(s4, rate=1.0) == s4
print(json.dumps(out, indent=1))
