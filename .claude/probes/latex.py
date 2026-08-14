"""latex: detection, citation preservation, bib resolution."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.latex import is_latex, cite_keys, bib_keys, dropped_citations, unresolved_citations

out = {}
out["detect_latex"] = is_latex(r"The model \cite{smith2019} improves accuracy.")
out["detect_plain"] = not is_latex("The model improves accuracy.")
out["cite_keys"] = cite_keys(r"See \cite{smith2019,jones2020} for details.")
bib = r"@article{smith2019, ...} @book{jones2020, ...}"
out["bib_keys"] = sorted(bib_keys(bib))
out["dropped"] = dropped_citations(r"\cite{smith2019} here", "text without citation")
out["unresolved"] = unresolved_citations(r"\cite{ghost2024}", bib)
print(json.dumps(out, indent=1))
