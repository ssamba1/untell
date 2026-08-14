"""split_sentences: quotes + abbreviations + parens combined (the hard boundary combos)."""
import json
from untell.text_split import split_sentences

cases = {
    "quote_abbr": 'He said "the meeting is at 3 p.m." and left.',
    "abbr_in_parens": "The team (led by Dr. Smith) approved the plan. Then they left.",
    "quote_after_abbr": "At 5 p.m. she said \"go.\" The rest followed.",
    "double_quote_nested": 'He asked "did you see \'the report\'?" and waited.',
    "url_in_quote": 'The doc said "see https://x.io/a.b for details." End.',
    "abbr_chain": "The U.S. and U.K. agreed. The E.U. joined later.",
    "decimal_quote": 'The value was "3.14" in the table. It was exact.',
}
out = {}
for name, t in cases.items():
    s = split_sentences(t)
    out[name] = {"n": len(s), "join": " ".join(s).strip() == t.strip()}
print(json.dumps(out, indent=1))
