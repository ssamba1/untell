import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.tells import _rule_of_three_runs, _semicolon_crutch, _title_case_headings

out = {}
# rule of three: 3 short sentences in a row counts once
out["rule3"] = _rule_of_three_runs("Fast. Simple. Effective. The rest is a longer sentence here.")
# 5 short in a row still counts once
out["rule5_once"] = _rule_of_three_runs("Go. Now. Stop. Wait. Run. The rest is longer.")
# no short runs -> 0
out["no_rule"] = _rule_of_three_runs("The system reads the file and processes the records. The parser splits each one.")
# semicolon crutch
out["semicolon"] = _semicolon_crutch("The system reads the file; the parser splits it; the loader writes it.")
out["no_semicolon"] = _semicolon_crutch("The system reads the file and the parser splits it.")
# title case headings
out["title_heading"] = _title_case_headings("The Quick Brown Fox Jumps Over The Lazy Dog")
out["no_heading"] = _title_case_headings("The quick brown fox jumps over the lazy dog")
print(json.dumps(out, indent=1))
