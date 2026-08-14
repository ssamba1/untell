"""split_sentences: abbreviations, quotes, parens, decimals, ellipsis at boundaries."""
import json
from untell.text_split import split_sentences

cases = {
    "abbr_mid": "The team met at 3 p.m. and finished by 5 p.m. sharp.",
    "abbr_end": "He earned a Ph.D. in 2020.",
    "quote_end": 'She said "stop." Then she left.',
    "paren_end": "The result was clear (see Fig. 3). It was also cheap.",
    "decimal": "The value was 3.14 and the ratio 2.5. That settled it.",
    "ellipsis": "Wait... what happened? The data is missing.",
    "semicolon": "It is robust; it scales; it delivers. The team agreed.",
    "url_end": "Visit https://example.com/page. More text follows.",
    "sentence_abbrev": "U.S. policy changed. The effect was immediate.",
    "single_sentence": "Only one sentence here with no terminator at all",
    "exclaim_question": "Really?! No way! The results were clear?",
    "nested_parens": "The test (which ran twice (in parallel)) passed. Then we stopped.",
}
out = {}
for name, t in cases.items():
    try:
        s = split_sentences(t)
        out[name] = {"n": len(s), "roundtrip_join": " ".join(s).strip() == t.strip(), "parts": [x[:35] for x in s]}
    except Exception as e:
        out[name] = {"error": f"{type(e).__name__}: {str(e)[:50]}"}
print(json.dumps(out, indent=1))
