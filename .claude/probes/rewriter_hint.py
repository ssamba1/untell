"""_stronger_rewriter_hint: fires only for weak rewriters on flagged full-tier."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
import untell.scripts.run as R

class FakeRW:
    def __init__(self, name): self.name = name

out = {}
# flagged + full + weak -> hint
out["weak_full_flagged"] = bool(R._stronger_rewriter_hint(FakeRW("composite"), True, "full"))
# not flagged -> none
out["weak_full_not_flagged"] = R._stronger_rewriter_hint(FakeRW("composite"), False, "full") == {}
# lite tier -> none
out["weak_lite_flagged"] = R._stronger_rewriter_hint(FakeRW("composite"), True, "lite") == {}
# strong rewriter -> none
out["strong_full_flagged"] = R._stronger_rewriter_hint(FakeRW("neural"), True, "full") == {}
# no name -> none
out["nameless"] = R._stronger_rewriter_hint(object(), True, "full") == {}
# hint content mentions neural and .[full]
h = R._stronger_rewriter_hint(FakeRW("composite"), True, "full")
out["hint_mentions_neural"] = "neural" in h.get("suggestion", "")
out["hint_mentions_extra"] = "[full]" in h.get("suggestion", "")
print(json.dumps(out, indent=1))
