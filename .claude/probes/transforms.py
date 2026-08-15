import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.structural import _flatten_negated_contrast, _flatten_vague_attribution, _flatten_copula, _flatten_cliches

out = {}
# negated contrast -> positive statement kept
out["neg_contrast"] = _flatten_negated_contrast("It's not the parser, it's the loader.")
# not-only-but-also -> both asserted, X kept (the documented fix)
out["not_only"] = _flatten_negated_contrast("It's not only faster, but also cheaper to run.")
# vague attribution flattened
out["vague"] = _flatten_vague_attribution("Some experts argue that the system works well.")
# copula flattened
out["copula"] = _flatten_copula("The tool serves as a bridge for the team.")
# cliche flattened
out["cliche"] = _flatten_cliches("It is important to note that the results are significant.")
print(json.dumps(out, indent=1))
