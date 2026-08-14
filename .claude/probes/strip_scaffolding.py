import json
from untell.scripts.entailment import strip_scaffolding

out = {}
out["signoff_removed"] = "hope this helps" not in strip_scaffolding("I hope this helps! The fix works now.")
out["stance_removed"] = "important to note" not in strip_scaffolding("It is important to note that X works.")
out["content_kept"] = "The fix works now." in strip_scaffolding("I hope this helps! The fix works now.")
out["all_scaffold_removed"] = strip_scaffolding("I hope this helps!") == ""
out["no_scaffold_unchanged"] = "The parser splits the file into records." in strip_scaffolding("The parser splits the file into records.")
print(json.dumps(out, indent=1))
