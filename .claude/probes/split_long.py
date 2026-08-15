import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.structural import _split_long_sentences, _looks_like_a_serial_list

out = {}
# no-comma long sentence NOT split (the artificial-intelligence fix)
no_comma = "In the paper a team of experts in the field of artificial intelligence and medical imaging set out a set of guiding principles for the safe deployment of the technology."
out["no_comma_kept"] = len(_split_long_sentences([no_comma], rate=1.0)) == 1
# comma-carrying long sentence split at comma
with_comma = "The system reads the file, processes every record in order, and writes the output to the store for later analysis by the team."
s = _split_long_sentences([with_comma], rate=1.0)
out["comma_split"] = len(s) == 2
out["split_valid"] = all(len(x.split()) >= 5 for x in s)
# serial list never split
serial = "The system reads the file, the parser splits the records, the loader writes the output, and the checker validates the rows."
out["serial_kept"] = len(_split_long_sentences([serial], rate=1.0)) == 1
print(json.dumps(out, indent=1))
