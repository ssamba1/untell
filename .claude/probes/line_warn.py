import json
from untell.scripts.score import _line_per_sentence_warning

out = {}
# many one-line blocks -> warning fires
many_lone = "\n".join(f"Line {i} has a single sentence here." for i in range(5))
out["many_lone_warns"] = _line_per_sentence_warning(many_lone) is not None
# one paragraph with many sentences -> no warning
para = "The system reads the file. The parser splits it. The loader writes it. " * 3
out["paragraph_silent"] = _line_per_sentence_warning(para) is None
# too few blocks -> silent
out["few_blocks_silent"] = _line_per_sentence_warning("Just one line here.") is None
print(json.dumps(out, indent=1))
