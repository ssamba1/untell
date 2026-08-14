import json
from untell.attacks.back_translation import BackTranslator

bt = BackTranslator()
tok_fn, _ = bt._pipe("en", "fr")
budget = bt._MAX_TOKENS - 16
cases = {
    "normal": "The system reads the file before anything else happens on the node.",
    "long_clause": ("The system reads the file before anything else happens on the node, "
                    "which means the parser must wait until the entire contents are in memory "
                    "before it can begin splitting them into records, and then it has to write "
                    "each one to the store, which itself can take a long time when the batch is large."),
    "many_sentences": ". ".join(f"Sentence number {i} in this paragraph goes on for a bit." for i in range(60)),
}
out = {}
for name, t in cases.items():
    pieces = bt._fit(t, tok_fn, budget)
    fits = all(len(tok_fn(p)["input_ids"]) <= budget for p in pieces)
    out[name] = {"n": len(pieces), "all_fit": fits, "tokens": [len(tok_fn(p)["input_ids"]) for p in pieces][:6],
                 "reassembles": " ".join(pieces).strip() == t.strip()}
print(json.dumps(out, indent=1))
