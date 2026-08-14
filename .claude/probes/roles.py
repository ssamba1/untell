"""role_swap: catches argument permutation, passes faithful paraphrase, None when unavailable."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.roles import role_swap, parser_available

out = {"parser_available": parser_available()}
cases = {
    "role_swap": ("The company sued the regulator over the new rules.",
                  "The regulator sued the company over the new rules."),
    "faithful": ("The intervention halved mortality in the trial group over six months.",
                 "The treatment cut deaths in the study group by half during the six months."),
    "same": ("The company sued the regulator.",
             "The company sued the regulator."),
    "different_topic": ("The company sued the regulator.",
                        "Cats are pleasant animals."),
    "empty": ("", "anything"),
}
for name, (a, b) in cases.items():
    out[name] = role_swap(a, b)
print(json.dumps(out, indent=1))
