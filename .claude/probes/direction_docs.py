"""direction_kept false-veto rate on the free rewriters' output over every prose paragraph in the
repository's own documentation: real prose, dense with direction words because it reports
measurements. Every veto is printed with the edit that caused it, so each can be judged."""
import difflib, json, logging, random, re, sys
from pathlib import Path
logging.disable(logging.CRITICAL)
ROOT = Path(sys.argv[1]); sys.path.insert(0, str(ROOT))
from untell.rewriter import get_rewriter
from untell.scripts.hedges import _direction_counts, direction_kept
from untell.scripts.score import score_text

paras = []
for f in sorted([ROOT / "README.md", ROOT / "ROADMAP.md", *(ROOT / "docs").glob("*.md")]):
    for block in re.split(r"\n\s*\n", f.read_text(encoding="utf-8")):
        b = " ".join(block.split())
        # prose only: no tables, headings, code, lists; at least two sentences of 40+ words
        if b[:1] in "#|`-*>[<!0123456789" or "|" in b or "```" in b or len(b.split()) < 40:
            continue
        if len(re.findall(r"[.!?](\s|$)", b)) < 2:
            continue
        paras.append((f.name, b))
paras = list(dict.fromkeys(paras))
with_dir = sum(1 for _, p in paras if sum(_direction_counts(p)))
changed = vetoes = 0; shown = []
for rw_name in ("structural", "surgical", "composite"):
    rw = get_rewriter(prefer=rw_name)
    for name, p in paras:
        sc = score_text(p, tier="lite")
        for seed in range(2):
            random.seed(seed); out = rw.rewrite(p, sc, 0.30)
            if not isinstance(out, str) or out == p:
                continue
            changed += 1
            if not direction_kept(p, out):
                vetoes += 1
                sm = difflib.SequenceMatcher(a=p.split(), b=out.split())
                edits = [(" ".join(p.split()[i1:i2]), " ".join(out.split()[j1:j2])) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal"]
                shown.append((rw_name, name, edits[:6]))
print(json.dumps({"paragraphs": len(paras), "with_direction_word": with_dir, "changed_candidates": changed, "direction_vetoes": vetoes}, indent=1))
for s in shown: print("---", s[0], s[1]); [print("   ", repr(a), "->", repr(b)) for a, b in s[2]]
