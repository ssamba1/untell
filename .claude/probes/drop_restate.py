import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.structural import _drop_restatements

out = {}
# restatement dropped (high coverage of earlier sentence)
s = ["The system reads the file.", "The parser processes the file contents.", "The tool parses the file contents and reads them."]
d = _drop_restatements(s)
out["dropped_some"] = len(d) < len(s)
# first sentence never dropped
s2 = ["The system reads the file.", "The system reads the file again and again."]
d2 = _drop_restatements(s2)
out["first_kept"] = len(d2) >= 1 and "The system reads the file." in d2
# numeral-carrying restatement kept
s3 = ["The system loads 120 records.", "The system loads 120 records from the store."]
d3 = _drop_restatements(s3)
out["numeral_kept"] = "120" in " ".join(d3)
# single sentence unchanged
out["single"] = _drop_restatements(["Only one sentence."]) == ["Only one sentence."]
print(json.dumps(out, indent=1))
