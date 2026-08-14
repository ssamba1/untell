"""Every _CATEGORIES entry must fire on a known positive built from its own grammar."""
import json, os, re
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.tells import _CATEGORIES, score_tells

# Fire each category with a probe built from its pattern's literal tokens
dead = []
for name, pat in _CATEGORIES:
    # Build a probe from the pattern's quoted literals
    literals = re.findall(r'"([^"]+)"|([A-Za-z][A-Za-z ]{3,})', pat.pattern)
    words = [a or b for a, b in literals]
    # Try each literal as the core of a sentence
    hit = False
    for w in words[:6]:
        probe = f"The report {w} the finding. The team agreed with the result and published it widely."
        if pat.search(probe):
            hit = True
            break
    if not hit:
        # Try the category name itself and common trigger words
        for w in [name.replace("_", " "), "the system", "we believe", "importantly"]:
            probe = f"Importantly, {w} the finding across the whole program. The team agreed and moved on."
            if pat.search(probe):
                hit = True
                break
    if not hit:
        dead.append(name)
print(json.dumps({
    "categories": len(_CATEGORIES),
    "dead_by_literal_probe": dead,
}, indent=1))
