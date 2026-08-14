"""by_category keys vs the reference catalogue: every emitted category must be documented."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.tells import score_tells
from pathlib import Path

# Fire every category using known positives
probes = {
    "Moreover, the framework leverages robust solutions for every team.": None,
    "It is important to note that the results were significant.": None,
    "The study shows that the data underscores the importance of the finding.": None,
    "In conclusion, this research paves the way for future work.": None,
    "We are excited to share our groundbreaking results.": None,
}
all_cats = set()
for t in probes:
    r = score_tells(t)
    all_cats.update(r.get("by_category", {}).keys())

# categories documented in the reference catalogue
ref = Path("untell/references/ai-tells.md").read_text(encoding="utf-8") if Path("untell/references/ai-tells.md").exists() else ""
print(json.dumps({
    "emitted_categories": sorted(all_cats),
    "reference_file_exists": Path("untell/references/ai-tells.md").exists(),
}, indent=1))
